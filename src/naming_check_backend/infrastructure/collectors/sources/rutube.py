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


class RutubeSearchProvider(TextSearchProvider):
    BASE_URL = "https://rutube.ru/"
    _SEARCH_PATH = "search/"

    def __init__(self, page: Page) -> None:
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

        search_url = self._build_search_url(
            query=query,
        )

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
            "query": query,
        }

        return urljoin(self.BASE_URL, self._SEARCH_PATH) + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        try:
            await self._page.wait_for_selector(
                "a[href*='/video/'], a[href*='/channel/'], a[href*='/plst/'], a[href]",
                timeout=20_000,
            )
        except PlaywrightTimeoutError:
            pass

    def _parse_html(
        self,
        html: str,
        *,
        limit: int,
    ) -> list[TextSearchResult]:
        soup = BeautifulSoup(html, "html.parser")

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
    def _is_age_rating(value: str) -> bool:
        return value.strip() in {"0+", "6+", "12+", "16+", "18+"}

    @staticmethod
    def _find_result_cards(soup: BeautifulSoup) -> list[Tag]:
        selectors = [
            "article",
            "li",
            "div[class*='card']",
            "div[class*='Card']",
            "div[class*='video']",
            "div[class*='Video']",
            "div[class*='search']",
            "div[class*='Search']",
            "div[data-testid]",
        ]

        cards: list[Tag] = []
        seen_ids: set[int] = set()

        for selector in selectors:
            for item in soup.select(selector):
                if not isinstance(item, Tag):
                    continue

                item_id = id(item)

                if item_id in seen_ids:
                    continue

                if item.select_one("a[href]") is None:
                    continue

                item_text = item.get_text(" ", strip=True)

                if not item_text:
                    continue

                seen_ids.add(item_id)
                cards.append(item)

        return cards

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
            "a[href*='/video/']",
            "a[href*='/channel/']",
            "a[href*='/plst/']",
            "a[href]",
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
            "[data-testid*='title']",
            "[data-testid*='Title']",
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

        return None

    @classmethod
    def _extract_title_from_card(
        cls,
        card: Tag,
    ) -> str | None:
        selectors = [
            "[class*='title']",
            "[class*='Title']",
            "[data-testid*='title']",
            "[data-testid*='Title']",
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
            "[class*='description']",
            "[class*='Description']",
            "[class*='meta']",
            "[class*='Meta']",
            "[class*='info']",
            "[class*='Info']",
            "[class*='date']",
            "[class*='Date']",
            "[class*='duration']",
            "[class*='Duration']",
            "[data-testid*='description']",
            "[data-testid*='meta']",
        ]

        snippets: list[str] = []

        for selector in selectors:
            for element in card.select(selector):
                if element is None:
                    continue

                text = cls._clean_text(element.get_text(" ", strip=True))

                if not text:
                    continue

                if text == title:
                    continue

                if text in snippets:
                    continue

                snippets.append(text)

        if snippets:
            return "; ".join(snippets[:4])

        card_text = cls._clean_text(card.get_text(" ", strip=True))

        if not card_text:
            return None

        snippet = card_text.replace(title, "", 1).strip()

        if not snippet:
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

        for link in soup.select("a[href]"):
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

        if host not in {"rutube.ru", "www.rutube.ru"}:
            return None

        return raw_url

    @staticmethod
    def _is_technical_url(url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()

        technical_paths = (
            "/search/",
            "/feeds/",
            "/account/",
            "/profile/",
            "/login/",
            "/register/",
            "/about/",
            "/help/",
            "/legal/",
            "/terms/",
            "/privacy/",
        )

        if path in technical_paths:
            return True

        if path.startswith("/account/"):
            return True

        if path.startswith("/login"):
            return True

        return False

    @classmethod
    def _looks_like_title(cls, value: str) -> bool:
        if not value:
            return False

        value = value.strip()

        if len(value) < 2:
            return False

        if cls._is_age_rating(value):
            return False

        technical_values = {
            "rutube",
            "поиск",
            "войти",
            "регистрация",
            "главная",
            "эфир",
            "каналы",
            "подписки",
            "история",
            "смотреть позже",
            "0+",
            "6+",
            "12+",
            "16+",
            "18+",
        }

        if value.lower() in technical_values:
            return False

        return True

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())
