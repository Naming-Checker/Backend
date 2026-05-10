from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class KinopoiskVerificationError(RuntimeError):
    pass


class KinopoiskSearchProvider(TextSearchProvider):
    BASE_URL = "https://www.kinopoisk.ru/"
    _SEARCH_PATH = "new-search/"

    def __init__(
        self,
        page: Page,
    ) -> None:
        self._page = page

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[TextSearchResult]:
        if not query.strip():
            return []

        if limit <= 0:
            return []

        search_url = self._build_search_url(query=query)

        await self._page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        await self._wait_for_page_ready()

        html = await self._page.content()

        return self._parse_html(
            html,
            limit=limit,
        )

    def _build_search_url(
        self,
        *,
        query: str,
    ) -> str:
        params = {
            "text": query,
        }

        return urljoin(self.BASE_URL, self._SEARCH_PATH) + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        html = await self._page.content()
        soup = BeautifulSoup(html, "html.parser")

        if self._is_verification_page(soup):
            raise KinopoiskVerificationError(
                "Kinopoisk returned verification/captcha page instead of search results. "
                "Run with headless=False, pass verification manually, "
                "then rerun with the same persistent profile."
            ) from None

        try:
            await self._page.wait_for_selector(
                "a[href*='/film/'], a[href*='/series/'], a[href*='/name/']",
                timeout=20_000,
            )
        except PlaywrightTimeoutError:
            html = await self._page.content()
            soup = BeautifulSoup(html, "html.parser")

            if self._is_verification_page(soup):
                raise KinopoiskVerificationError(
                    "Kinopoisk returned verification/captcha page instead of search results."
                ) from None

    def _parse_html(
        self,
        html: str,
        *,
        limit: int,
    ) -> list[TextSearchResult]:
        soup = BeautifulSoup(html, "html.parser")

        if self._is_verification_page(soup):
            raise KinopoiskVerificationError(
                "Kinopoisk returned verification/captcha page instead of search results."
            )

        results = self._parse_cards(
            soup,
            limit=limit,
        )

        if results:
            return results

        return self._fallback_parse_links(
            soup,
            limit=limit,
        )

    def _parse_cards(
        self,
        soup: BeautifulSoup,
        *,
        limit: int,
    ) -> list[TextSearchResult]:
        results: list[TextSearchResult] = []
        seen_urls: set[str] = set()

        for card in self._find_result_cards(soup):
            result = self._parse_card(card)

            if result is None:
                continue

            if result.url in seen_urls:
                continue

            seen_urls.add(result.url)
            results.append(result)

            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _find_result_cards(soup: BeautifulSoup) -> list[Tag]:
        cards: list[Tag] = []
        seen_ids: set[int] = set()

        links = soup.select("a[href*='/film/'], a[href*='/series/'], a[href*='/name/']")

        for link in links:
            if not isinstance(link, Tag):
                continue

            href = link.get("href")

            if not isinstance(href, str):
                continue

            if not KinopoiskSearchProvider._is_entity_href(href):
                continue

            card = KinopoiskSearchProvider._find_nearest_result_container(link)

            if card is None:
                continue

            item_id = id(card)

            if item_id in seen_ids:
                continue

            seen_ids.add(item_id)
            cards.append(card)

        return cards

    @staticmethod
    def _find_nearest_result_container(link: Tag) -> Tag | None:
        allowed_entity_link_count_limit = 4

        current = link.parent

        while isinstance(current, Tag):
            text = KinopoiskSearchProvider._clean_text(current.get_text(" ", strip=True))

            entity_links = [
                entity_link
                for entity_link in current.select("a[href*='/film/'], a[href*='/series/'], a[href*='/name/']")
                if isinstance(entity_link, Tag)
                and isinstance(entity_link.get("href"), str)
                and KinopoiskSearchProvider._is_entity_href(str(entity_link.get("href")))
            ]

            if text and 10 <= len(text) <= 2500 and len(entity_links) <= allowed_entity_link_count_limit:
                return current

            current = current.parent

        return link

    @staticmethod
    def _is_entity_href(href: str) -> bool:
        parsed = urlparse(href)
        path = parsed.path.lower()

        return path.startswith(
            (
                "/film/",
                "/series/",
                "/name/",
            )
        )

    def _parse_card(
        self,
        card: Tag,
    ) -> TextSearchResult | None:
        link = self._find_main_link(card)

        if link is None:
            return None

        href = link.get("href")

        if not isinstance(href, str):
            return None

        url = self._normalize_result_url(href)

        if url is None:
            return None

        title = self._extract_title_from_link(link)

        if not title:
            title = self._extract_title_from_card(card)

        if not title:
            return None

        snippet = self._extract_snippet_from_card(
            card,
            title=title,
        )

        return TextSearchResult(
            title=title,
            url=url,
            snippet=snippet,
        )

    def _find_main_link(
        self,
        card: Tag,
    ) -> Tag | None:
        selectors = [
            "a[href*='/film/']",
            "a[href*='/series/']",
            "a[href*='/name/']",
        ]

        for selector in selectors:
            for link in card.select(selector):
                if not isinstance(link, Tag):
                    continue

                href = link.get("href")

                if not isinstance(href, str):
                    continue

                url = self._normalize_result_url(href)

                if url is None:
                    continue

                if self._is_technical_url(url):
                    continue

                title = self._extract_title_from_link(link)

                if not title:
                    title = self._extract_title_from_card(card)

                if not title:
                    continue

                return link

        return None

    @classmethod
    def _extract_title_from_link(
        cls,
        link: Tag,
    ) -> str | None:
        title_attr = link.get("title")

        if isinstance(title_attr, str):
            title = cls._clean_text(title_attr)

            if cls._looks_like_title(title):
                return title

        aria_label = link.get("aria-label")

        if isinstance(aria_label, str):
            title = cls._clean_text(aria_label)

            if cls._looks_like_title(title):
                return title

        selectors = [
            "[class*='title']",
            "[class*='Title']",
            "[class*='name']",
            "[class*='Name']",
            "[data-test-id*='title']",
            "[data-testid*='title']",
            "h1",
            "h2",
            "h3",
            "h4",
        ]

        for selector in selectors:
            element = link.select_one(selector)

            if element is None:
                continue

            title = cls._clean_text(element.get_text(" ", strip=True))

            if cls._looks_like_title(title):
                return title

        title = cls._clean_text(link.get_text(" ", strip=True))

        if cls._looks_like_title(title):
            return title

        return None

    @classmethod
    def _extract_title_from_card(
        cls,
        card: Tag,
    ) -> str | None:
        selectors = [
            "[class*='title']",
            "[class*='Title']",
            "[class*='name']",
            "[class*='Name']",
            "[data-test-id*='title']",
            "[data-testid*='title']",
            "h1",
            "h2",
            "h3",
            "h4",
        ]

        for selector in selectors:
            for element in card.select(selector):
                title = cls._clean_text(element.get_text(" ", strip=True))

                if cls._looks_like_title(title):
                    return title

        return None

    @classmethod
    def _extract_snippet_from_card(
        cls,
        card: Tag,
        *,
        title: str,
    ) -> str | None:
        selectors = [
            "[class*='caption']",
            "[class*='Caption']",
            "[class*='description']",
            "[class*='Description']",
            "[class*='info']",
            "[class*='Info']",
            "[class*='year']",
            "[class*='Year']",
            "[class*='rating']",
            "[class*='Rating']",
            "[data-test-id*='description']",
            "[data-testid*='description']",
        ]

        snippets: list[str] = []

        for selector in selectors:
            for element in card.select(selector):
                text = cls._clean_text(element.get_text(" ", strip=True))

                if not text:
                    continue

                if text == title:
                    continue

                if cls._is_bad_snippet(text):
                    continue

                if text in snippets:
                    continue

                snippets.append(text)

        if snippets:
            return "; ".join(snippets[:5])

        card_text = cls._clean_text(card.get_text(" ", strip=True))

        if not card_text:
            return None

        snippet = card_text.replace(title, "", 1).strip()

        if not snippet:
            return None

        if cls._is_bad_snippet(snippet):
            return None

        if len(snippet) > 700:
            snippet = snippet[:700].rsplit(" ", 1)[0].strip()

        return snippet or None

    def _fallback_parse_links(
        self,
        soup: BeautifulSoup,
        *,
        limit: int,
    ) -> list[TextSearchResult]:
        results: list[TextSearchResult] = []
        seen_urls: set[str] = set()

        for link in soup.select("a[href*='/film/'], a[href*='/series/'], a[href*='/name/']"):
            if not isinstance(link, Tag):
                continue

            href = link.get("href")

            if not isinstance(href, str):
                continue

            url = self._normalize_result_url(href)

            if url is None:
                continue

            if self._is_technical_url(url):
                continue

            if url in seen_urls:
                continue

            title = self._extract_title_from_link(link)

            if not title:
                continue

            seen_urls.add(url)

            results.append(
                TextSearchResult(
                    title=title,
                    url=url,
                    snippet=None,
                )
            )

            if len(results) >= limit:
                break

        return results

    def _normalize_result_url(
        self,
        raw_url: str,
    ) -> str | None:
        raw_url = raw_url.strip()

        if not raw_url:
            return None

        if raw_url.startswith("//"):
            raw_url = "https:" + raw_url

        if raw_url.startswith("/"):
            raw_url = urljoin(self.BASE_URL, raw_url)

        parsed = urlparse(raw_url)

        if parsed.scheme not in {"http", "https"}:
            return None

        host = parsed.netloc.lower()

        if host not in {"kinopoisk.ru", "www.kinopoisk.ru"}:
            return None

        path = parsed.path.lower()

        allowed_prefixes = (
            "/film/",
            "/series/",
            "/name/",
        )

        if not path.startswith(allowed_prefixes):
            return None

        return raw_url

    @staticmethod
    def _is_technical_url(url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()

        technical_paths = (
            "/new-search/",
            "/lists/",
            "/media/",
            "/mykp/",
            "/user/",
            "/s/",
            "/level/",
            "/docs/",
            "/help/",
        )

        if path in technical_paths:
            return True

        return False

    @staticmethod
    def _is_verification_page(soup: BeautifulSoup) -> bool:
        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        page_text = soup.get_text(" ", strip=True).lower()

        markers = (
            "captcha",
            "капча",
            "подтвердите, что вы не робот",
            "докажите, что вы не робот",
            "access denied",
            "доступ ограничен",
            "403 forbidden",
            "smartcaptcha",
        )

        if any(marker in title for marker in markers):
            return True

        if any(marker in page_text for marker in markers):
            if "новый поиск" not in page_text and "результаты поиска" not in page_text:
                return True

        if soup.select_one("form[action*='captcha']") is not None:
            return True

        if soup.select_one("iframe[src*='captcha']") is not None:
            return True

        return False

    @staticmethod
    def _looks_like_title(value: str) -> bool:
        if not value:
            return False

        value = value.strip()
        normalized = value.lower()

        if len(value) < 2:
            return False

        technical_values = {
            "кинопоиск",
            "поиск",
            "найти",
            "войти",
            "регистрация",
            "фильмы",
            "сериалы",
            "персоны",
            "онлайн-кинотеатр",
            "смотреть",
            "смотреть онлайн",
            "подписка",
            "реклама",
            "18+",
            "16+",
            "12+",
            "6+",
            "0+",
        }

        if normalized in technical_values:
            return False

        bad_prefixes = (
            "билеты в кино",
            "1. билеты в кино",
            "2. билеты в кино",
            "3. билеты в кино",
            "сейчас в кино",
            "скоро в кино",
            "популярное",
            "рекомендуем",
        )

        if normalized.startswith(bad_prefixes):
            return False

        return True

    @staticmethod
    def _is_bad_snippet(value: str) -> bool:
        normalized = value.strip().lower()

        bad_values = {
            "кинопоиск",
            "поиск",
            "войти",
            "регистрация",
            "фильмы",
            "сериалы",
            "персоны",
            "реклама",
        }

        if normalized in bad_values:
            return True

        bad_prefixes = (
            "билеты в кино",
            "1. билеты в кино",
            "2. билеты в кино",
            "3. билеты в кино",
            "сейчас в кино",
            "скоро в кино",
            "популярное",
            "рекомендуем",
        )

        return normalized.startswith(bad_prefixes)

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())
