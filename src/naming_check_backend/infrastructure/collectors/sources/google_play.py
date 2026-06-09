from __future__ import annotations

from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class GooglePlayVerificationError(RuntimeError):
    pass


class GooglePlaySearchProvider(TextSearchProvider):
    BASE_URL = "https://play.google.com/"
    _SEARCH_PATH = "store/search"

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

        raw_results = await self._extract_results_from_dom()

        results: list[TextSearchResult] = []
        seen_app_ids: set[str] = set()
        seen_urls: set[str] = set()

        for raw_result in raw_results:
            if len(results) >= limit:
                break

            title = self._clean_text(raw_result.get("title"))
            url = self._normalize_result_url(str(raw_result.get("url") or ""))
            snippet = self._clean_text(raw_result.get("snippet"))

            if not title or not url:
                continue

            if not self._looks_like_title(title):
                continue

            app_id = self._extract_app_id(url)

            if app_id:
                if app_id in seen_app_ids:
                    continue

                seen_app_ids.add(app_id)

            if url in seen_urls:
                continue

            seen_urls.add(url)

            results.append(
                TextSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet or None,
                )
            )

        return results

    def _build_search_url(
        self,
        *,
        query: str,
    ) -> str:
        params = {
            "q": query,
            "c": "apps",
            "hl": "ru",
            "gl": "US",
        }

        return urljoin(self.BASE_URL, self._SEARCH_PATH) + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        await self._raise_if_real_verification_page()

        try:
            await self._page.wait_for_selector(
                "a[href*='/store/apps/details?id=']",
                timeout=20_000,
            )
        except PlaywrightTimeoutError:
            await self._raise_if_real_verification_page()

        await self._page.mouse.wheel(0, 1200)
        await self._page.wait_for_timeout(1000)

    async def _raise_if_real_verification_page(self) -> None:
        current_url = self._page.url.lower()
        title = (await self._page.title()).lower()

        if "consent.google." in current_url:
            raise GooglePlayVerificationError("Google Play returned consent page instead of search results.")

        if "/sorry/" in current_url or "sorry/index" in current_url:
            raise GooglePlayVerificationError(
                "Google Play returned verification page instead of search results."
            )

        if "unusual traffic" in title:
            raise GooglePlayVerificationError("Google Play returned unusual traffic verification page.")

        has_sorry_form = await self._page.locator(
            "form[action*='/sorry/'], form[action*='sorry/index']"
        ).count()

        if has_sorry_form > 0:
            raise GooglePlayVerificationError(
                "Google Play returned verification form instead of search results."
            )

        page_text = await self._page.locator("body").inner_text(timeout=10_000)

        normalized_text = page_text.lower()

        real_verification_markers = (
            "our systems have detected unusual traffic",
            "detected unusual traffic from your computer network",
            "unusual traffic from your computer network",
        )

        if any(marker in normalized_text for marker in real_verification_markers):
            raise GooglePlayVerificationError("Google Play returned unusual traffic verification page.")

    async def _extract_results_from_dom(self) -> list[dict[str, str]]:
        return cast(
            list[dict[str, str]],
            await self._page.evaluate(
                """
            () => {
                const cleanText = (value) => {
                    if (!value) {
                        return "";
                    }

                    return String(value)
                        .replace(/\\u00a0/g, " ")
                        .replace(/\\s+/g, " ")
                        .trim();
                };

                const isVisible = (element) => {
                    if (!element) {
                        return false;
                    }

                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();

                    return (
                        style.display !== "none" &&
                        style.visibility !== "hidden" &&
                        Number(style.opacity || "1") !== 0 &&
                        rect.width > 0 &&
                        rect.height > 0
                    );
                };

                const looksLikeMeta = (value) => {
                    const text = cleanText(value).toLowerCase();

                    if (!text) {
                        return true;
                    }

                    const exactMetaValues = new Set([
                        "google play",
                        "play google",
                        "google",
                        "play",
                        "приложения",
                        "игры",
                        "фильмы",
                        "книги",
                        "детям",
                        "поиск",
                        "войти",
                        "установить",
                        "открыть",
                        "подробнее",
                        "ещё",
                        "еще",
                        "реклама",
                        "ads",
                        "ad",
                        "0+",
                        "3+",
                        "6+",
                        "7+",
                        "12+",
                        "16+",
                        "18+",
                        "есть реклама",
                        "покупки в приложении",
                        "contains ads",
                        "in-app purchases",
                    ]);

                    if (exactMetaValues.has(text)) {
                        return true;
                    }

                    if (/^\\d+(?:[,.]\\d+)?$/.test(text)) {
                        return true;
                    }

                    if (/^\\d+(?:[,.]\\d+)?\\s*[★*]$/.test(text)) {
                        return true;
                    }

                    if (/^[★*]\\s*\\d+(?:[,.]\\d+)?$/.test(text)) {
                        return true;
                    }

                    if (/^\\d+(?:[,.]\\d+)?\\s*(тыс\\.?|млн|k|m)\\+?$/i.test(text)) {
                        return true;
                    }

                    if (/^\\d+\\s*(мб|mb|gb|гб)$/i.test(text)) {
                        return true;
                    }

                    if (/^\\d{1,2}\\s*(янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)/i.test(text)) {
                        return true;
                    }

                    if (text.includes("★")) {
                        return true;
                    }

                    return false;
                };

                const looksLikeTitle = (value) => {
                    const text = cleanText(value);
                    const lower = text.toLowerCase();

                    if (text.length < 2) {
                        return false;
                    }

                    if (looksLikeMeta(text)) {
                        return false;
                    }

                    const badPrefixes = [
                        "результаты поиска",
                        "похожие запросы",
                        "вам также могут понравиться",
                        "рекомендуем",
                        "популярные приложения",
                        "популярные игры",
                    ];

                    return !badPrefixes.some((prefix) => lower.startsWith(prefix));
                };

                const uniqueTexts = (values) => {
                    const result = [];

                    for (const value of values) {
                        const text = cleanText(value);

                        if (!text) {
                            continue;
                        }

                        if (result.includes(text)) {
                            continue;
                        }

                        if (result.some((existing) => existing.includes(text) && existing !== text)) {
                            continue;
                        }

                        result.push(text);
                    }

                    return result;
                };

                const findCard = (link) => {
                    let current = link;

                    while (current && current !== document.body) {
                        const text = cleanText(current.innerText || current.textContent);
                        const links = Array.from(
                            current.querySelectorAll("a[href*='/store/apps/details?id=']")
                        );

                        if (
                            text.length >= 3 &&
                            text.length <= 1600 &&
                            links.length <= 3
                        ) {
                            return current;
                        }

                        current = current.parentElement;
                    }

                    return link;
                };

                const getTitle = (link, card) => {
                    const attrTitle = cleanText(link.getAttribute("title"));
                    if (looksLikeTitle(attrTitle)) {
                        return attrTitle;
                    }

                    const ariaLabel = cleanText(link.getAttribute("aria-label"));
                    if (looksLikeTitle(ariaLabel)) {
                        return ariaLabel;
                    }

                    const strongSelectors = [
                        ".Epkrse",
                        ".DdYX5",
                        "[itemprop='name']",
                        "[class*='Epkrse']",
                        "[class*='DdYX5']",
                        "[class*='title']",
                        "[class*='Title']",
                        "[class*='name']",
                        "[class*='Name']",
                        "h1",
                        "h2",
                        "h3",
                        "h4",
                    ];

                    for (const selector of strongSelectors) {
                        const insideLink = link.querySelector(selector);
                        const insideCard = card.querySelector(selector);

                        for (const element of [insideLink, insideCard]) {
                            if (!element || !isVisible(element)) {
                                continue;
                            }

                            const text = cleanText(element.innerText || element.textContent);

                            if (looksLikeTitle(text)) {
                                return text;
                            }
                        }
                    }

                    const lines = uniqueTexts(
                        cleanText(link.innerText || link.textContent).split("\\n")
                    );

                    for (const line of lines) {
                        if (looksLikeTitle(line)) {
                            return line;
                        }
                    }

                    const cardLines = uniqueTexts(
                        cleanText(card.innerText || card.textContent).split("\\n")
                    );

                    for (const line of cardLines) {
                        if (looksLikeTitle(line)) {
                            return line;
                        }
                    }

                    return "";
                };

                const getSnippet = (card, title) => {
                    const lines = uniqueTexts(
                        cleanText(card.innerText || card.textContent).split("\\n")
                    );

                    const snippets = [];

                    for (const line of lines) {
                        if (!line || line === title) {
                            continue;
                        }

                        if (looksLikeMeta(line)) {
                            continue;
                        }

                        snippets.push(line);

                        if (snippets.length >= 4) {
                            break;
                        }
                    }

                    return snippets.join("; ");
                };

                const links = Array.from(
                    document.querySelectorAll("a[href*='/store/apps/details?id=']")
                );

                const results = [];

                for (const link of links) {
                    if (!isVisible(link)) {
                        continue;
                    }

                    const href = link.href || link.getAttribute("href") || "";

                    if (!href.includes("/store/apps/details")) {
                        continue;
                    }

                    const card = findCard(link);
                    const title = getTitle(link, card);

                    if (!looksLikeTitle(title)) {
                        continue;
                    }

                    const snippet = getSnippet(card, title);

                    results.push({
                        title,
                        url: href,
                        snippet,
                    });
                }

                return results;
            }
            """
            ),
        )

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

        if host not in {"play.google.com", "www.play.google.com"}:
            return None

        if parsed.path.lower() != "/store/apps/details":
            return None

        query = parse_qs(parsed.query)
        app_id_values = query.get("id")

        if not app_id_values:
            return None

        app_id = app_id_values[0].strip()

        if not app_id:
            return None

        clean_query = urlencode(
            {
                "id": app_id,
                "hl": "ru",
                "gl": "US",
            }
        )

        return urlunparse(
            (
                "https",
                "play.google.com",
                "/store/apps/details",
                "",
                clean_query,
                "",
            )
        )

    @staticmethod
    def _extract_app_id(url: str) -> str | None:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        values = query.get("id")

        if not values:
            return None

        app_id = values[0].strip()

        return app_id or None

    @classmethod
    def _looks_like_title(
        cls,
        value: str,
    ) -> bool:
        value = cls._clean_text(value)
        normalized = value.lower()

        if len(value) < 2:
            return False

        bad_values = {
            "google play",
            "play google",
            "google",
            "play",
            "приложения",
            "игры",
            "фильмы",
            "книги",
            "детям",
            "поиск",
            "войти",
            "установить",
            "открыть",
            "подробнее",
            "ещё",
            "еще",
            "реклама",
            "ads",
            "ad",
            "0+",
            "3+",
            "6+",
            "7+",
            "12+",
            "16+",
            "18+",
            "есть реклама",
            "покупки в приложении",
            "contains ads",
            "in-app purchases",
        }

        if normalized in bad_values:
            return False

        bad_prefixes = (
            "результаты поиска",
            "похожие запросы",
            "вам также могут понравиться",
            "рекомендуем",
            "популярные приложения",
            "популярные игры",
        )

        if normalized.startswith(bad_prefixes):
            return False

        if cls._looks_like_rating_or_meta(value):
            return False

        return True

    @staticmethod
    def _looks_like_rating_or_meta(value: str) -> bool:
        normalized = value.strip().lower()

        if not normalized:
            return True

        meta_values = {
            "0+",
            "3+",
            "6+",
            "7+",
            "12+",
            "16+",
            "18+",
            "есть реклама",
            "покупки в приложении",
            "in-app purchases",
            "contains ads",
        }

        if normalized in meta_values:
            return True

        if "★" in normalized:
            return True

        if normalized.replace(",", ".").replace(".", "", 1).isdigit():
            return True

        suffixes = (
            " млн+",
            " тыс.+",
            " тыс+",
            "k+",
            "m+",
            " мб",
            " mb",
            " гб",
            " gb",
        )

        if normalized.endswith(suffixes):
            return True

        return False

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())
