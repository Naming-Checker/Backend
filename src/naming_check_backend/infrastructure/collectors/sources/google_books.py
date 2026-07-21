from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class GoogleSearchVerificationError(RuntimeError):
    pass


class GoogleUdm36SearchProvider(TextSearchProvider):
    _SEARCH_PATH = "search"
    _UDM = "36"
    BASE_URL = "https://www.google.com/"

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
            "udm": self._UDM,
            "q": query,
            "hl": "ru",
        }

        return (
            urljoin(self.BASE_URL, self._SEARCH_PATH)
            + "?"
            + urlencode(params)
        )

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        await self._raise_if_verification_or_consent_page()

        try:
            await self._page.wait_for_selector(
                "a[href]",
                timeout=20_000,
            )
        except PlaywrightTimeoutError:
            await self._raise_if_verification_or_consent_page()

        await self._page.mouse.wheel(0, 1200)
        await self._page.wait_for_timeout(1000)

    async def _raise_if_verification_or_consent_page(self) -> None:
        current_url = self._page.url.lower()
        title = (await self._page.title()).lower()

        if "consent.google." in current_url:
            raise GoogleSearchVerificationError(
                "Google returned consent page instead of search results. "
                "Run with headless=False, accept consent manually, then rerun "
                "with the same persistent profile."
            )

        if "/sorry/" in current_url or "sorry/index" in current_url:
            raise GoogleSearchVerificationError(
                "Google returned verification page instead of search results."
            )

        if "unusual traffic" in title:
            raise GoogleSearchVerificationError(
                "Google returned unusual traffic verification page."
            )

        sorry_forms_count = await self._page.locator(
            "form[action*='/sorry/'], "
            "form[action*='sorry/index']"
        ).count()

        if sorry_forms_count > 0:
            raise GoogleSearchVerificationError(
                "Google returned verification form instead of search results."
            )

        body_text = await self._page.locator("body").inner_text(timeout=10_000)
        normalized_text = body_text.lower()

        real_verification_markers = (
            "our systems have detected unusual traffic",
            "detected unusual traffic from your computer network",
            "unusual traffic from your computer network",
        )

        if any(marker in normalized_text for marker in real_verification_markers):
            raise GoogleSearchVerificationError(
                "Google returned unusual traffic verification page."
            )

        consent_markers = (
            "before you continue to google",
            "прежде чем перейти к google",
        )

        if (
            any(marker in normalized_text for marker in consent_markers)
            and "google.com/search" not in current_url
        ):
            raise GoogleSearchVerificationError(
                "Google returned consent page instead of search results."
            )

    async def _extract_results_from_dom(self) -> list[dict[str, str]]:
        return await self._page.evaluate(
            r"""
            () => {
                const cleanText = (value) => {
                    if (!value) {
                        return "";
                    }

                    return String(value)
                        .replace(/\u00a0/g, " ")
                        .replace(/\s+/g, " ")
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

                const looksLikeTechnicalText = (value) => {
                    const text = cleanText(value).toLowerCase();

                    if (!text) {
                        return true;
                    }

                    const badValues = new Set([
                        "google",
                        "поиск",
                        "найти",
                        "картинки",
                        "видео",
                        "новости",
                        "карты",
                        "покупки",
                        "книги",
                        "ещё",
                        "еще",
                        "инструменты",
                        "настройки",
                        "войти",
                        "открыть",
                        "поделиться",
                        "сохранить",
                        "перевести эту страницу",
                        "translate this page",
                        "cached",
                        "кэш",
                        "реклама",
                        "ad",
                        "ads",
                    ]);

                    if (badValues.has(text)) {
                        return true;
                    }

                    const dateRegex = new RegExp(
                        "^\\d{1,2}\\s*" +
                        "(янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)",
                        "i"
                    );

                    if (dateRegex.test(text)) {
                        return true;
                    }

                    if (/^\d{4}$/.test(text)) {
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

                    if (looksLikeTechnicalText(text)) {
                        return false;
                    }

                    const badPrefixes = [
                        "результаты поиска",
                        "похожие запросы",
                        "вам также может понравиться",
                        "люди также спрашивают",
                        "people also ask",
                        "related searches",
                        "search results",
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

                        if (
                            result.some((existing) => {
                                return existing.includes(text) && existing !== text;
                            })
                        ) {
                            continue;
                        }

                        result.push(text);
                    }

                    return result;
                };

                const isCandidateHref = (href) => {
                    if (!href) {
                        return false;
                    }

                    const value = String(href);

                    if (value.startsWith("#")) {
                        return false;
                    }

                    if (value.startsWith("javascript:")) {
                        return false;
                    }

                    if (value.startsWith("mailto:")) {
                        return false;
                    }

                    if (value.startsWith("tel:")) {
                        return false;
                    }

                    if (value.includes("accounts.google.")) {
                        return false;
                    }

                    if (value.includes("consent.google.")) {
                        return false;
                    }

                    if (value.includes("support.google.")) {
                        return false;
                    }

                    if (value.includes("policies.google.")) {
                        return false;
                    }

                    if (value.includes("webcache.googleusercontent.")) {
                        return false;
                    }

                    if (value.includes("/search?")) {
                        return false;
                    }

                    if (value.includes("/preferences?")) {
                        return false;
                    }

                    if (value.includes("/setprefs?")) {
                        return false;
                    }

                    if (value.includes("/advanced_search")) {
                        return false;
                    }

                    return true;
                };

                const findCard = (link) => {
                    let current = link;

                    while (current && current !== document.body) {
                        const text = cleanText(current.innerText || current.textContent);

                        const links = Array.from(current.querySelectorAll("a[href]"))
                            .filter((item) => {
                                return isCandidateHref(
                                    item.href || item.getAttribute("href")
                                );
                            });

                        const tagName = current.tagName
                            ? current.tagName.toLowerCase()
                            : "";

                        const className = String(current.className || "");

                        const looksLikeGoogleCard = (
                            className.includes("MjjYud") ||
                            className.includes("g ") ||
                            current.hasAttribute("data-hveid") ||
                            current.hasAttribute("data-ved") ||
                            tagName === "div"
                        );

                        if (
                            looksLikeGoogleCard &&
                            text.length >= 5 &&
                            text.length <= 3500 &&
                            links.length <= 8
                        ) {
                            return current;
                        }

                        current = current.parentElement;
                    }

                    return link;
                };

                const getTitle = (link, card) => {
                    const titleAttr = cleanText(link.getAttribute("title"));

                    if (looksLikeTitle(titleAttr)) {
                        return titleAttr;
                    }

                    const ariaLabel = cleanText(link.getAttribute("aria-label"));

                    if (looksLikeTitle(ariaLabel)) {
                        return ariaLabel;
                    }

                    const strongSelectors = [
                        "h3",
                        "[role='heading']",
                        "[aria-level='3']",
                        "[class*='LC20lb']",
                        "[class*='DKV0Md']",
                        "[class*='title']",
                        "[class*='Title']",
                    ];

                    for (const selector of strongSelectors) {
                        const insideLink = link.querySelector(selector);
                        const insideCard = card.querySelector(selector);

                        for (const element of [insideLink, insideCard]) {
                            if (!element || !isVisible(element)) {
                                continue;
                            }

                            const text = cleanText(
                                element.innerText || element.textContent
                            );

                            if (looksLikeTitle(text)) {
                                return text;
                            }
                        }
                    }

                    const linkLines = uniqueTexts(
                        cleanText(link.innerText || link.textContent).split("\n")
                    );

                    for (const line of linkLines) {
                        if (looksLikeTitle(line)) {
                            return line;
                        }
                    }

                    const cardLines = uniqueTexts(
                        cleanText(card.innerText || card.textContent).split("\n")
                    );

                    for (const line of cardLines) {
                        if (looksLikeTitle(line)) {
                            return line;
                        }
                    }

                    return "";
                };

                const getSnippet = (card, title) => {
                    const preferredSelectors = [
                        ".VwiC3b",
                        ".aCOpRe",
                        ".IsZvec",
                        "[data-sncf]",
                        "[class*='snippet']",
                        "[class*='Snippet']",
                        "[style*='-webkit-line-clamp']",
                    ];

                    const snippets = [];

                    for (const selector of preferredSelectors) {
                        const elements = Array.from(card.querySelectorAll(selector));

                        for (const element of elements) {
                            if (!isVisible(element)) {
                                continue;
                            }

                            const text = cleanText(
                                element.innerText || element.textContent
                            );

                            if (!text || text === title) {
                                continue;
                            }

                            if (looksLikeTechnicalText(text)) {
                                continue;
                            }

                            if (snippets.includes(text)) {
                                continue;
                            }

                            snippets.push(text);

                            if (snippets.length >= 3) {
                                return snippets.join("; ");
                            }
                        }
                    }

                    const lines = uniqueTexts(
                        cleanText(card.innerText || card.textContent).split("\n")
                    );

                    for (const line of lines) {
                        if (!line || line === title) {
                            continue;
                        }

                        if (looksLikeTechnicalText(line)) {
                            continue;
                        }

                        snippets.push(line);

                        if (snippets.length >= 4) {
                            break;
                        }
                    }

                    return snippets.join("; ");
                };

                const cardSelectors = [
                    "div.MjjYud",
                    "div.g",
                    "div[data-hveid]",
                    "div[data-ved]",
                    "div[jscontroller][data-hveid]",
                    "div[data-sokoban-container]",
                ];

                const cards = Array.from(
                    document.querySelectorAll(cardSelectors.join(","))
                );

                const results = [];

                for (const card of cards) {
                    if (!isVisible(card)) {
                        continue;
                    }

                    const links = Array.from(card.querySelectorAll("a[href]"))
                        .filter((link) => isVisible(link))
                        .filter((link) => {
                            return isCandidateHref(
                                link.href || link.getAttribute("href")
                            );
                        });

                    for (const link of links) {
                        const href = link.href || link.getAttribute("href") || "";
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

                        break;
                    }
                }

                if (results.length > 0) {
                    return results;
                }

                const links = Array.from(document.querySelectorAll("a[href]"))
                    .filter((link) => isVisible(link))
                    .filter((link) => {
                        return isCandidateHref(
                            link.href || link.getAttribute("href")
                        );
                    });

                for (const link of links) {
                    const href = link.href || link.getAttribute("href") || "";
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

        if self._is_google_redirect_url(parsed):
            extracted_url = self._extract_wrapped_url(parsed)

            if extracted_url:
                return self._normalize_result_url(extracted_url)

            return None

        if self._is_blocked_google_url(parsed):
            return None

        return raw_url

    @staticmethod
    def _is_google_redirect_url(parsed_url) -> bool:
        host = parsed_url.netloc.lower()
        path = parsed_url.path.lower()

        google_hosts = {
            "google.com",
            "www.google.com",
            "google.ru",
            "www.google.ru",
        }

        if host not in google_hosts:
            return False

        return path in {
            "/url",
            "/interstitial",
            "/imgres",
        }

    @staticmethod
    def _extract_wrapped_url(parsed_url) -> str | None:
        query = parse_qs(parsed_url.query)

        for key in ("q", "url", "u", "target", "to"):
            values = query.get(key)

            if not values:
                continue

            candidate = values[0].strip()
            candidate_parsed = urlparse(candidate)

            if candidate_parsed.scheme in {"http", "https"}:
                return candidate

        return None

    @staticmethod
    def _is_blocked_google_url(parsed_url) -> bool:
        host = parsed_url.netloc.lower()
        path = parsed_url.path.lower()

        blocked_hosts = {
            "accounts.google.com",
            "consent.google.com",
            "support.google.com",
            "policies.google.com",
            "www.gstatic.com",
            "webcache.googleusercontent.com",
        }

        if host in blocked_hosts:
            return True

        google_search_hosts = {
            "google.com",
            "www.google.com",
            "google.ru",
            "www.google.ru",
        }

        if host in google_search_hosts:
            blocked_paths = (
                "/search",
                "/preferences",
                "/setprefs",
                "/advanced_search",
                "/sorry",
            )

            if path.startswith(blocked_paths):
                return True

        return False

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
            "google",
            "поиск",
            "найти",
            "картинки",
            "видео",
            "новости",
            "карты",
            "покупки",
            "книги",
            "ещё",
            "еще",
            "инструменты",
            "настройки",
            "войти",
            "открыть",
            "поделиться",
            "сохранить",
            "перевести эту страницу",
            "translate this page",
            "cached",
            "кэш",
            "реклама",
            "ad",
            "ads",
        }

        if normalized in bad_values:
            return False

        bad_prefixes = (
            "результаты поиска",
            "похожие запросы",
            "вам также может понравиться",
            "люди также спрашивают",
            "people also ask",
            "related searches",
            "search results",
        )

        if normalized.startswith(bad_prefixes):
            return False

        return True

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())