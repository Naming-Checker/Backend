from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class YandexSearchVerificationError(RuntimeError):
    pass


class YandexTextSearchProvider(TextSearchProvider):
    _DEFAULT_LR = "121642"
    BASE_URL = "https://ya.ru/"

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

        search_url = self._build_search_url(query)

        await self._page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        await self._wait_for_page_ready()

        html = await self._page.content()

        return self._parse_html(html, limit=limit)

    def _build_search_url(self, query: str) -> str:
        params = {
            "text": query,
            "lr": self._DEFAULT_LR,
            "family": "yes",
            "search_source": "yaru_desktop_common",
            "search_domain": "yaru",
        }

        return urljoin(self.BASE_URL, "search/") + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeoutError:
            pass

        html = await self._page.content()
        soup = BeautifulSoup(html, "html.parser")

        if self._is_verification_page(soup):
            raise YandexSearchVerificationError(
                "Yandex returned browser verification page instead of search results. "
                "Open the browser in headed mode, pass verification manually, then rerun. "
                "Do not try to parse this page as search results."
            )

        try:
            await self._page.wait_for_selector(
                "li.serp-item, div.serp-item, li[data-cid], div[data-cid], "
                "li[class*='serp-item'], div[class*='serp-item'], "
                "li[class*='Organic'], div[class*='Organic']",
                timeout=15_000,
            )
        except PlaywrightTimeoutError:
            html = await self._page.content()
            soup = BeautifulSoup(html, "html.parser")

            if self._is_verification_page(soup):
                raise YandexSearchVerificationError(
                    "Yandex returned browser verification page instead of search results."
                ) from None

    @classmethod
    def _parse_html(
        cls,
        html: str,
        *,
        limit: int,
    ) -> list[TextSearchResult]:
        soup = BeautifulSoup(html, "html.parser")

        if cls._is_verification_page(soup):
            raise YandexSearchVerificationError(
                "Yandex returned browser verification page instead of search results."
            )

        results: list[TextSearchResult] = []
        seen_urls: set[str] = set()

        for card in cls._find_result_cards(soup):
            result = cls._parse_card(card)

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
    def _is_verification_page(soup: BeautifulSoup) -> bool:
        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""

        if "верификация" in title:
            return True

        if soup.select_one('form[action*="checkcaptcha"]') is not None:
            return True

        if soup.select_one('form[action*="showcaptcha"]') is not None:
            return True

        page_text = soup.get_text(" ", strip=True).lower()

        verification_phrases = (
            "проверка браузера перед переходом",
            "подождите несколько секунд",
            "checkcaptchafast",
            "showcaptcha",
            "smart-captcha",
            "captcha",
        )

        return any(phrase in page_text for phrase in verification_phrases)

    @staticmethod
    def _find_result_cards(soup: BeautifulSoup) -> list[Tag]:
        selectors = [
            "li.serp-item",
            "div.serp-item",
            "li[data-cid]",
            "div[data-cid]",
            "li.Organic",
            "div.Organic",
            "li[class*='serp-item']",
            "div[class*='serp-item']",
            "li[class*='Organic']",
            "div[class*='Organic']",
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

                seen_ids.add(item_id)
                cards.append(item)

        return cards

    @classmethod
    def _parse_card(cls, card: Tag) -> TextSearchResult | None:
        link = cls._find_main_link(card)

        if link is None:
            return None

        href = link.get("href")

        if not isinstance(href, str):
            return None

        url = cls._normalize_result_url(href)

        if url is None:
            return None

        title = cls._clean_text(link.get_text(" ", strip=True))

        if not title:
            alt_title = cls._extract_title_from_card(card)
            if alt_title:
                title = alt_title

        if not title:
            return None

        snippet = cls._extract_snippet_from_card(card, title=title)

        return TextSearchResult(
            title=title,
            url=url,
            snippet=snippet,
        )

    @classmethod
    def _find_main_link(cls, card: Tag) -> Tag | None:
        selectors = [
            "a.OrganicTitle-Link[href]",
            "a[class*='OrganicTitle'][href]",
            "a[class*='organic__title'][href]",
            "h2 a[href]",
            "h3 a[href]",
            "a[href]",
        ]

        for selector in selectors:
            for link in card.select(selector):
                if not isinstance(link, Tag):
                    continue

                href = link.get("href")
                title = cls._clean_text(link.get_text(" ", strip=True))

                if not isinstance(href, str):
                    continue

                if not title:
                    continue

                if cls._normalize_result_url(href) is None:
                    continue

                return link

        return None

    @classmethod
    def _extract_title_from_card(cls, card: Tag) -> str | None:
        selectors = [
            ".OrganicTitle",
            "[class*='OrganicTitle']",
            ".organic__title",
            "[class*='organic__title']",
            "h2",
            "h3",
        ]

        for selector in selectors:
            element = card.select_one(selector)

            if element is None:
                continue

            title = cls._clean_text(element.get_text(" ", strip=True))

            if title:
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
            ".OrganicTextContentSpan",
            "[class*='OrganicTextContent']",
            ".organic__text",
            "[class*='organic__text']",
            ".text-container",
            ".extended-text",
            ".serp-item__text",
            "[class*='TextContainer']",
        ]

        for selector in selectors:
            element = card.select_one(selector)

            if element is None:
                continue

            snippet = cls._clean_text(element.get_text(" ", strip=True))

            if snippet and snippet != title:
                return snippet

        card_text = cls._clean_text(card.get_text(" ", strip=True))

        if not card_text:
            return None

        snippet = card_text.replace(title, "", 1).strip()

        if not snippet:
            return None

        if len(snippet) > 500:
            snippet = snippet[:500].rsplit(" ", 1)[0].strip()

        return snippet or None

    @staticmethod
    def _normalize_result_url(raw_url: str) -> str | None:
        raw_url = raw_url.strip()

        if not raw_url:
            return None

        if raw_url.startswith("//"):
            raw_url = "https:" + raw_url

        if raw_url.startswith("/"):
            return None

        parsed = urlparse(raw_url)

        if parsed.scheme not in {"http", "https"}:
            return None

        host = parsed.netloc.lower()

        yandex_hosts = (
            "ya.ru",
            "www.ya.ru",
            "yandex.ru",
            "www.yandex.ru",
            "yabs.yandex.ru",
            "passport.yandex.ru",
            "webcache.yandex.ru",
            "mc.yandex.ru",
        )

        if host in yandex_hosts or host.endswith(".yandex.ru"):
            query = parse_qs(parsed.query)

            for key in ("url", "u", "target", "to"):
                values = query.get(key)

                if not values:
                    continue

                extracted_url = unquote(values[0])
                extracted_parsed = urlparse(extracted_url)

                if extracted_parsed.scheme in {"http", "https"}:
                    return extracted_url

            return None

        return raw_url

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.split())
