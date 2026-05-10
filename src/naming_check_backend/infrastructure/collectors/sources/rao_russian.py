from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class RaoRegistrySearchProvider(TextSearchProvider):
    BASE_URL = "https://rao.ru/"
    _RESULTS_PATH = "information/reestry/reestr-proizvedenij-rossijskih-pravoobladatelej/"

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

        search_url = self._build_search_url(
            work=query,
            author="",
            page_number=1,
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
            page_url=self._page.url,
            limit=limit,
        )

    def _build_search_url(
        self,
        *,
        work: str,
        author: str,
        page_number: int,
    ) -> str:
        params = {
            "work": work,
            "author": author,
            "pg": str(page_number),
        }

        return urljoin(self.BASE_URL, self._RESULTS_PATH) + "?" + urlencode(params)

    async def _wait_for_page_ready(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeoutError:
            pass

        try:
            await self._page.wait_for_selector(
                "table, body",
                timeout=15_000,
            )
        except PlaywrightTimeoutError:
            pass

    def _parse_html(
        self,
        html: str,
        *,
        page_url: str,
        limit: int,
    ) -> list[TextSearchResult]:
        soup = BeautifulSoup(html, "html.parser")

        results = self._parse_table_results(
            soup,
            page_url=page_url,
            limit=limit,
        )

        if results:
            return results

        return self._parse_div_like_results(
            soup,
            page_url=page_url,
            limit=limit,
        )

    def _parse_table_results(
        self,
        soup: BeautifulSoup,
        *,
        page_url: str,
        limit: int,
    ) -> list[TextSearchResult]:
        results: list[TextSearchResult] = []

        for table in soup.select("table"):
            if not isinstance(table, Tag):
                continue

            rows = table.select("tr")

            if not rows:
                continue

            header_indexes = self._extract_header_indexes(rows)

            if header_indexes is None:
                continue

            title_index = header_indexes["title"]
            genre_index = header_indexes.get("genre")
            author_index = header_indexes.get("author")

            for row in rows:
                cells = row.select("td")

                if not cells:
                    continue

                values = [self._clean_text(cell.get_text(" ", strip=True)) for cell in cells]

                if title_index >= len(values):
                    continue

                title = values[title_index]

                if not title:
                    continue

                genre = self._get_value_by_index(values, genre_index)
                author = self._get_value_by_index(values, author_index)

                results.append(
                    self._build_result(
                        title=title,
                        genre=genre,
                        author=author,
                        page_url=page_url,
                    )
                )

                if len(results) >= limit:
                    return results

        return results

    def _parse_div_like_results(
        self,
        soup: BeautifulSoup,
        *,
        page_url: str,
        limit: int,
    ) -> list[TextSearchResult]:
        """
        Fallback на случай, если РАО изменит table на div-верстку.

        Здесь мы не угадываем жанры.
        Мы ищем текстовые блоки, где явно есть подписи:
        "Название произведения", "Жанр", "Автор".
        """
        results: list[TextSearchResult] = []

        candidate_blocks = soup.select("div, li, article, section")

        for block in candidate_blocks:
            if not isinstance(block, Tag):
                continue

            text = self._clean_text(block.get_text(" ", strip=True))

            if not text:
                continue

            lowered = text.lower()

            if "название произведения" not in lowered:
                continue

            if "жанр" not in lowered:
                continue

            title = self._extract_labeled_value(
                text,
                label="Название произведения",
                stop_labels=("Жанр", "Автор"),
            )
            genre = self._extract_labeled_value(
                text,
                label="Жанр",
                stop_labels=("Название произведения", "Автор"),
            )
            author = self._extract_labeled_value(
                text,
                label="Автор",
                stop_labels=("Название произведения", "Жанр"),
            )

            if not title:
                continue

            results.append(
                self._build_result(
                    title=title,
                    genre=genre,
                    author=author,
                    page_url=page_url,
                )
            )

            if len(results) >= limit:
                break

        return results

    def _extract_header_indexes(
        self,
        rows: list[Tag],
    ) -> dict[str, int] | None:
        for row in rows:
            header_cells = row.select("th")

            if not header_cells:
                header_cells = row.select("td")

            headers = [self._normalize_header(cell.get_text(" ", strip=True)) for cell in header_cells]

            if not headers:
                continue

            title_index = self._find_header_index(
                headers,
                variants=(
                    "название произведения",
                    "произведение",
                    "название",
                ),
            )

            if title_index is None:
                continue

            genre_index = self._find_header_index(
                headers,
                variants=(
                    "жанр",
                    "вид произведения",
                ),
            )

            author_index = self._find_header_index(
                headers,
                variants=(
                    "автор",
                    "авторы",
                    "правообладатель",
                    "правообладатели",
                ),
            )

            return {
                "title": title_index,
                **({"genre": genre_index} if genre_index is not None else {}),
                **({"author": author_index} if author_index is not None else {}),
            }

        return None

    @staticmethod
    def _find_header_index(
        headers: list[str],
        *,
        variants: tuple[str, ...],
    ) -> int | None:
        for index, header in enumerate(headers):
            for variant in variants:
                if variant in header:
                    return index

        return None

    @staticmethod
    def _normalize_header(value: str) -> str:
        return " ".join(value.lower().replace("\xa0", " ").split())

    @staticmethod
    def _get_value_by_index(
        values: list[str],
        index: int | None,
    ) -> str | None:
        if index is None:
            return None

        if index >= len(values):
            return None

        value = values[index].strip()

        return value or None

    @staticmethod
    def _extract_labeled_value(
        text: str,
        *,
        label: str,
        stop_labels: tuple[str, ...],
    ) -> str | None:
        lower_text = text.lower()
        lower_label = label.lower()

        label_index = lower_text.find(lower_label)

        if label_index == -1:
            return None

        value_start = label_index + len(label)

        while value_start < len(text) and text[value_start] in ": —-":
            value_start += 1

        value_end = len(text)

        for stop_label in stop_labels:
            stop_index = lower_text.find(stop_label.lower(), value_start)

            if stop_index != -1:
                value_end = min(value_end, stop_index)

        value = text[value_start:value_end].strip(" :—-")

        return value or None

    @staticmethod
    def _build_result(
        *,
        title: str,
        genre: str | None,
        author: str | None,
        page_url: str,
    ) -> TextSearchResult:
        snippet_parts: list[str] = []

        if genre:
            snippet_parts.append(f"Жанр: {genre}")

        if author:
            snippet_parts.append(f"Автор: {author}")

        return TextSearchResult(
            title=title,
            url=page_url,
            snippet="; ".join(snippet_parts) if snippet_parts else None,
        )

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.replace("\xa0", " ").split())
