from __future__ import annotations

from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class YouTubeVerificationError(RuntimeError):
    pass


class YouTubeSearchProvider(TextSearchProvider):
    _SEARCH_PATH = "results"
    BASE_URL = "https://www.youtube.com/"

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
            "search_query": query,
        }

        return urljoin(self.BASE_URL, self._SEARCH_PATH) + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        await self._raise_if_verification_or_consent_page()

        try:
            await self._page.wait_for_selector(
                "ytd-video-renderer, "
                "ytd-rich-item-renderer, "
                "ytd-reel-item-renderer, "
                "ytd-playlist-renderer, "
                "ytd-channel-renderer, "
                "a[href*='/watch?v='], "
                "a[href^='/shorts/']",
                timeout=25_000,
            )
        except PlaywrightTimeoutError:
            await self._raise_if_verification_or_consent_page()

        await self._page.mouse.wheel(0, 1500)
        await self._page.wait_for_timeout(1000)

    async def _raise_if_verification_or_consent_page(self) -> None:
        current_url = self._page.url.lower()
        title = (await self._page.title()).lower()

        if "consent.youtube" in current_url or "consent.google" in current_url:
            raise YouTubeVerificationError(
                "YouTube returned consent page instead of search results. "
                "Run with headless=False, accept consent manually, "
                "then rerun with the same persistent profile."
            )

        if "/sorry/" in current_url or "sorry/index" in current_url:
            raise YouTubeVerificationError("YouTube returned verification page instead of search results.")

        if "unusual traffic" in title:
            raise YouTubeVerificationError("YouTube returned unusual traffic verification page.")

        if "captcha" in title:
            raise YouTubeVerificationError("YouTube returned captcha page instead of search results.")

        sorry_forms_count = await self._page.locator(
            "form[action*='/sorry/'], form[action*='sorry/index']"
        ).count()

        if sorry_forms_count > 0:
            raise YouTubeVerificationError("YouTube returned verification form instead of search results.")

        body_text = await self._page.locator("body").inner_text(timeout=10_000)
        normalized_text = body_text.lower()

        real_verification_markers = (
            "our systems have detected unusual traffic",
            "detected unusual traffic from your computer network",
            "unusual traffic from your computer network",
        )

        if any(marker in normalized_text for marker in real_verification_markers):
            raise YouTubeVerificationError("YouTube returned unusual traffic verification page.")

        consent_markers = (
            "before you continue to youtube",
            "прежде чем перейти к youtube",
            "accept all",
            "reject all",
        )

        if (
            any(marker in normalized_text for marker in consent_markers)
            and "youtube.com/results" not in current_url
        ):
            raise YouTubeVerificationError("YouTube returned consent page instead of search results.")

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

                const looksLikeMeta = (value) => {
                    const text = cleanText(value).toLowerCase();

                    if (!text) {
                        return true;
                    }

                    const badValues = new Set([
                        "youtube",
                        "ютуб",
                        "поиск",
                        "найти",
                        "главная",
                        "shorts",
                        "подписки",
                        "библиотека",
                        "история",
                        "смотреть",
                        "смотреть позже",
                        "поделиться",
                        "сохранить",
                        "ещё",
                        "еще",
                        "открыть",
                        "войти",
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

                    const viewsRegex = new RegExp(
                        "^\\\\d+[,.]?\\\\d*\\\\s*(тыс\\\\.?|млн|k|m)?\\\\s*" +
                        "(просмотров|просмотра|просмотр|views|view)$",
                        "i"
                    );

                    const ruAgoRegex = new RegExp(
                        "^\\\\d+\\\\s*" +
                        "(секунд|секунду|секунды|минуту|минуты|минут|" +
                        "час|часа|часов|день|дня|дней|неделю|недели|недель|" +
                        "месяц|месяца|месяцев|год|года|лет)\\\\s*назад$",
                        "i"
                    );

                    const enAgoRegex = new RegExp(
                        "^\\\\d+\\\\s*" +
                        "(second|seconds|minute|minutes|hour|hours|day|days|" +
                        "week|weeks|month|months|year|years)\\\\s*ago$",
                        "i"
                    );

                    if (viewsRegex.test(text)) {
                        return true;
                    }

                    if (ruAgoRegex.test(text)) {
                        return true;
                    }

                    if (enAgoRegex.test(text)) {
                        return true;
                    }

                    if (/^\\d+\\s*(видео|video|videos)$/i.test(text)) {
                        return true;
                    }

                    if (/^\\d+\\s*(подписчик|подписчика|подписчиков|subscriber|subscribers)$/i.test(text)) {
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
                        "вам также может понравиться",
                        "смотрите также",
                        "search results",
                        "people also watched",
                        "for you",
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

                    if (value.includes("/watch?v=")) {
                        return true;
                    }

                    if (value.includes("/shorts/")) {
                        return true;
                    }

                    if (value.includes("/playlist?list=")) {
                        return true;
                    }

                    if (value.includes("/channel/")) {
                        return true;
                    }

                    if (value.includes("/c/")) {
                        return true;
                    }

                    if (value.includes("/user/")) {
                        return true;
                    }

                    if (value.includes("youtube.com/@")) {
                        return true;
                    }

                    if (value.startsWith("/@")) {
                        return true;
                    }

                    return false;
                };

                const findMainLink = (card) => {
                    const selectors = [
                        "a#video-title[href*='/watch?v=']",
                        "a#video-title-link[href*='/watch?v=']",
                        "h3 a[href*='/watch?v=']",
                        "a[href*='/watch?v=']",
                        "a[href^='/shorts/']",
                        "a[href*='/shorts/']",
                        "a[href*='/playlist?list=']",
                        "a#main-link[href*='/channel/']",
                        "a[href*='/channel/']",
                        "a[href^='/@']",
                        "a[href*='youtube.com/@']",
                        "a[href*='/c/']",
                        "a[href*='/user/']",
                    ];

                    for (const selector of selectors) {
                        const links = Array.from(card.querySelectorAll(selector));

                        for (const link of links) {
                            const href = link.href || link.getAttribute("href") || "";

                            if (!isCandidateHref(href)) {
                                continue;
                            }

                            if (!isVisible(link)) {
                                continue;
                            }

                            return link;
                        }
                    }

                    return null;
                };

                const findCardByLink = (link) => {
                    let current = link;

                    while (current && current !== document.body) {
                        const tagName = current.tagName ? current.tagName.toLowerCase() : "";

                        if (
                            [
                                "ytd-video-renderer",
                                "ytd-rich-item-renderer",
                                "ytd-reel-item-renderer",
                                "ytd-playlist-renderer",
                                "ytd-channel-renderer",
                                "ytd-compact-video-renderer",
                                "ytd-grid-video-renderer",
                                "yt-lockup-view-model"
                            ].includes(tagName)
                        ) {
                            return current;
                        }

                        const text = cleanText(current.innerText || current.textContent);
                        const links = Array.from(current.querySelectorAll("a[href]"))
                            .filter((item) => isCandidateHref(item.href || item.getAttribute("href")));

                        if (
                            text.length >= 5 &&
                            text.length <= 3000 &&
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

                    if (looksLikeTitle(ariaLabel) && ariaLabel.length <= 180) {
                        return ariaLabel;
                    }

                    const strongSelectors = [
                        "a#video-title",
                        "#video-title",
                        "#video-title-link",
                        "yt-formatted-string#video-title",
                        "h3",
                        "#channel-title",
                        "#text-container",
                        "#text",
                        "[class*='title']",
                        "[class*='Title']",
                        "[class*='headline']",
                        "[class*='Headline']",
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
                    const preferredSelectors = [
                        "#channel-name",
                        "ytd-channel-name",
                        "#metadata-line",
                        "#description-text",
                        "#video-info",
                        "#byline-container",
                        "#subscribers",
                        "#video-count",
                    ];

                    const snippets = [];

                    for (const selector of preferredSelectors) {
                        const elements = Array.from(card.querySelectorAll(selector));

                        for (const element of elements) {
                            if (!isVisible(element)) {
                                continue;
                            }

                            const text = cleanText(element.innerText || element.textContent);

                            if (!text || text === title) {
                                continue;
                            }

                            if (snippets.includes(text)) {
                                continue;
                            }

                            snippets.push(text);
                        }
                    }

                    if (snippets.length > 0) {
                        return snippets.slice(0, 4).join("; ");
                    }

                    const lines = uniqueTexts(
                        cleanText(card.innerText || card.textContent).split("\\n")
                    );

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

                const cardSelectors = [
                    "ytd-video-renderer",
                    "ytd-rich-item-renderer",
                    "ytd-reel-item-renderer",
                    "ytd-playlist-renderer",
                    "ytd-channel-renderer",
                    "ytd-compact-video-renderer",
                    "ytd-grid-video-renderer",
                    "yt-lockup-view-model",
                ];

                const cards = Array.from(document.querySelectorAll(cardSelectors.join(",")));
                const results = [];

                for (const card of cards) {
                    if (!isVisible(card)) {
                        continue;
                    }

                    const link = findMainLink(card);

                    if (!link) {
                        continue;
                    }

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
                }

                if (results.length > 0) {
                    return results;
                }

                const links = Array.from(document.querySelectorAll("a[href]"))
                    .filter((link) => isVisible(link))
                    .filter((link) => isCandidateHref(link.href || link.getAttribute("href")));

                for (const link of links) {
                    const href = link.href || link.getAttribute("href") || "";
                    const card = findCardByLink(link);
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

        allowed_hosts = {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        }

        if host not in allowed_hosts:
            return None

        path = parsed.path

        if host == "youtu.be":
            video_id = path.strip("/")

            if not video_id:
                return None

            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    "/watch",
                    "",
                    urlencode({"v": video_id}),
                    "",
                )
            )

        if path == "/watch":
            query = parse_qs(parsed.query)
            video_id_values = query.get("v")

            if not video_id_values:
                return None

            video_id = video_id_values[0].strip()

            if not video_id:
                return None

            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    "/watch",
                    "",
                    urlencode({"v": video_id}),
                    "",
                )
            )

        if path.startswith("/shorts/"):
            short_id = path.removeprefix("/shorts/").strip("/")

            if not short_id:
                return None

            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    f"/shorts/{short_id}",
                    "",
                    "",
                    "",
                )
            )

        if path == "/playlist":
            query = parse_qs(parsed.query)
            playlist_id_values = query.get("list")

            if not playlist_id_values:
                return None

            playlist_id = playlist_id_values[0].strip()

            if not playlist_id:
                return None

            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    "/playlist",
                    "",
                    urlencode({"list": playlist_id}),
                    "",
                )
            )

        if path.startswith("/channel/"):
            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    path.rstrip("/"),
                    "",
                    "",
                    "",
                )
            )

        if path.startswith("/@"):
            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    path.rstrip("/"),
                    "",
                    "",
                    "",
                )
            )

        if path.startswith("/c/") or path.startswith("/user/"):
            return urlunparse(
                (
                    "https",
                    "www.youtube.com",
                    path.rstrip("/"),
                    "",
                    "",
                    "",
                )
            )

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
            "youtube",
            "ютуб",
            "поиск",
            "найти",
            "главная",
            "shorts",
            "подписки",
            "библиотека",
            "история",
            "смотреть",
            "смотреть позже",
            "поделиться",
            "сохранить",
            "ещё",
            "еще",
            "открыть",
            "войти",
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
            "search results",
            "people also watched",
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

        if normalized.replace(":", "").isdigit() and ":" in normalized:
            return True

        if "просмотр" in normalized:
            return True

        if "views" in normalized:
            return True

        if normalized.endswith("назад"):
            return True

        if normalized.endswith("ago"):
            return True

        if normalized.endswith((" подписчик", " подписчика", " подписчиков")):
            return True

        if normalized.endswith((" subscriber", " subscribers")):
            return True

        if normalized.endswith((" видео", " video", " videos")):
            return True

        return False

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())
