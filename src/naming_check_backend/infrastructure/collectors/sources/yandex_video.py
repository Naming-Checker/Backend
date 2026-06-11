from __future__ import annotations

from typing import Any, cast
from urllib.parse import ParseResult, parse_qs, urlencode, urljoin, urlparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class YandexVideoVerificationError(RuntimeError):
    pass


class YandexVideoSearchProvider(TextSearchProvider):
    _SEARCH_PATH = "video/search"
    BASE_URL = "https://yandex.ru/"

    def __init__(
        self,
        page: Page,
        base_url: str,
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
            "utm_source": "main_stripe_big",
            "text": query,
        }

        return urljoin(self.BASE_URL, self._SEARCH_PATH) + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        await self._raise_if_verification_page()

        try:
            await self._page.wait_for_selector(
                "a[href]",
                timeout=20_000,
            )
        except PlaywrightTimeoutError:
            await self._raise_if_verification_page()

        await self._page.mouse.wheel(0, 1200)
        await self._page.wait_for_timeout(1000)

    async def _raise_if_verification_page(self) -> None:
        current_url = self._page.url.lower()
        title = (await self._page.title()).lower()

        if "showcaptcha" in current_url:
            raise YandexVideoVerificationError(
                "Yandex returned captcha page instead of video search results."
            )

        if "checkcaptcha" in current_url:
            raise YandexVideoVerificationError(
                "Yandex returned captcha page instead of video search results."
            )

        if "captcha" in title:
            raise YandexVideoVerificationError(
                "Yandex returned captcha page instead of video search results."
            )

        captcha_forms_count = await self._page.locator(
            "form[action*='checkcaptcha'], form[action*='showcaptcha'], form[action*='captcha']"
        ).count()

        if captcha_forms_count > 0:
            raise YandexVideoVerificationError(
                "Yandex returned captcha form instead of video search results."
            )

        body_text = await self._page.locator("body").inner_text(timeout=10_000)
        normalized_text = body_text.lower()

        captcha_markers = (
            "подтвердите, что запросы отправляли вы",
            "подтвердите, что вы не робот",
            "введите символы с картинки",
            "captcha",
        )

        if any(marker in normalized_text for marker in captcha_markers):
            raise YandexVideoVerificationError(
                "Yandex returned captcha page instead of video search results."
            )

    async def _extract_results_from_dom(self) -> list[dict[str, str]]:
        result = await self._page.evaluate(
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

                const looksLikeTechnicalText = (value) => {
                    const text = cleanText(value).toLowerCase();

                    if (!text) {
                        return true;
                    }

                    const badValues = new Set([
                        "яндекс",
                        "yandex",
                        "видео",
                        "картинки",
                        "поиск",
                        "найти",
                        "ещё",
                        "еще",
                        "смотреть",
                        "перейти",
                        "поделиться",
                        "скопировать ссылку",
                        "открыть",
                        "реклама",
                        "ad",
                        "ads",
                    ]);

                    if (badValues.has(text)) {
                        return true;
                    }

                    if (/^\\d{1,2}:\\d{2}$/.test(text)) {
                        return true;
                    }

                    if (/^\\d{1,2}:\\d{2}:\\d{2}$/.test(text)) {
                        return true;
                    }

                    const viewsPattern = new RegExp(
                        "^\\d+[,.]?\\d*\\s*" +
                        "(тыс\\.?|млн|k|m)?\\s*" +
                        "(просмотров|просмотра|просмотр)$",
                        "i"
                    );

                    const dateAgoPattern = new RegExp(
                        "^\\d+\\s*" +
                        "(день|дня|дней|час|часа|часов|" +
                        "минуту|минуты|минут|" +
                        "месяц|месяца|месяцев|" +
                        "год|года|лет)\\s*назад$",
                        "i"
                    );

                    if (viewsPattern.test(text)) {
                        return true;
                    }

                    if (dateAgoPattern.test(text)) {
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
                        "смотрите также",
                        "видео по запросу",
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

                    if (value.includes("/video/preview/")) {
                        return true;
                    }

                    if (value.includes("/video/touch/")) {
                        return true;
                    }

                    if (value.includes("/video/search?")) {
                        return false;
                    }

                    if (value.includes("yandex.ru/video")) {
                        return true;
                    }

                    if (value.includes("yandex.ru/clck/")) {
                        return true;
                    }

                    if (value.includes("yabs.yandex")) {
                        return false;
                    }

                    return false;
                };

                const findCard = (link) => {
                    let current = link;

                    while (current && current !== document.body) {
                        const text = cleanText(current.innerText || current.textContent);
                        const links = Array.from(current.querySelectorAll("a[href]"))
                            .filter((item) => isCandidateHref(item.href || item.getAttribute("href")));

                        if (
                            text.length >= 5 &&
                            text.length <= 2500 &&
                            links.length <= 5
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
                        "[class*='Title']",
                        "[class*='title']",
                        "[class*='OrganicTitle']",
                        "[class*='organic__title']",
                        "[class*='SerpItem-Title']",
                        "[class*='VideoCard-Title']",
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

                    const linkLines = uniqueTexts(
                        cleanText(link.innerText || link.textContent).split("\\n")
                    );

                    for (const line of linkLines) {
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

                const links = Array.from(document.querySelectorAll("a[href]"))
                    .filter((link) => isVisible(link))
                    .filter((link) => isCandidateHref(link.href || link.getAttribute("href")));

                const results = [];

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
        return cast(list[dict[str, str]], result)

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

        if host.endswith("yabs.yandex.ru"):
            return None

        if host not in {
            "yandex.ru",
            "www.yandex.ru",
            "ya.ru",
            "www.ya.ru",
        }:
            return None

        path = parsed.path.lower()

        if path.startswith("/video/search"):
            return None

        if path.startswith("/video/preview") or path.startswith("/video/touch"):
            return raw_url

        if path.startswith("/clck/"):
            extracted_url = self._extract_wrapped_url(parsed)

            if extracted_url:
                return extracted_url

            return raw_url

        if "/video/" in path:
            return raw_url

        return None

    @staticmethod
    def _extract_wrapped_url(parsed_url: ParseResult) -> str | None:
        query = parse_qs(parsed_url.query)

        for key in ("url", "u", "target", "to"):
            values = query.get(key)

            if not values:
                continue

            candidate = values[0].strip()
            candidate_parsed = urlparse(candidate)

            if candidate_parsed.scheme in {"http", "https"}:
                return candidate

        return None

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
            "яндекс",
            "yandex",
            "видео",
            "картинки",
            "поиск",
            "найти",
            "ещё",
            "еще",
            "смотреть",
            "перейти",
            "поделиться",
            "скопировать ссылку",
            "открыть",
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
            "смотрите также",
            "видео по запросу",
        )

        if normalized.startswith(bad_prefixes):
            return False

        if cls._looks_like_video_meta(value):
            return False

        return True

    @staticmethod
    def _looks_like_video_meta(value: str) -> bool:
        normalized = value.strip().lower()

        if not normalized:
            return True

        if normalized in {
            "0+",
            "6+",
            "12+",
            "16+",
            "18+",
        }:
            return True

        if normalized.replace(":", "").isdigit() and ":" in normalized:
            return True

        if "просмотр" in normalized:
            return True

        if normalized.endswith("назад"):
            return True

        return False

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())
