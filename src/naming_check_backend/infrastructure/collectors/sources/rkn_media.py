from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page

from naming_check_backend.infrastructure.collectors.search_provider import (
    TextSearchProvider,
    TextSearchResult,
)


class RknMediaRegistrySearchProvider(TextSearchProvider):
    BASE_URL = "https://rkn.gov.ru/"
    _REGISTRY_PATH = "activity/mass-media/for-founders/media/"

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
        return await self.search_media(
            smi_name=query,
            limit=limit,
        )

    async def search_media(
        self,
        *,
        smi_name: str = "",
        cert_num: str = "",
        staff_address: str = "",
        terr_id: str = "0",
        status_id: str = "0",
        limit: int = 10,
    ) -> list[TextSearchResult]:
        if not smi_name.strip() and not cert_num.strip() and not staff_address.strip():
            return []

        if limit <= 0:
            return []

        registry_url = self._build_registry_url()

        response = await self._page.context.request.post(
            registry_url,
            form={
                "act": "search",
                "cert_num": cert_num,
                "smi_name": smi_name,
                "staff_address": staff_address,
                "TERR_ID": terr_id,
                "STATUS_ID": status_id,
            },
            headers={
                "Referer": registry_url,
                "Origin": self.BASE_URL.rstrip("/"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=60_000,
        )

        if not response.ok:
            raise RuntimeError(f"RKN media registry request failed: {response.status} {response.status_text}")

        html = await response.text()

        return self._parse_html(
            html,
            page_url=registry_url,
            limit=limit,
        )

    def _build_registry_url(self) -> str:
        return urljoin(self.BASE_URL, self._REGISTRY_PATH)

    def _parse_html(
        self,
        html: str,
        *,
        page_url: str,
        limit: int,
    ) -> list[TextSearchResult]:
        soup = BeautifulSoup(html, "html.parser")

        table_results = self._parse_table_results(
            soup,
            page_url=page_url,
            limit=limit,
        )

        return table_results

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
            cert_index = header_indexes.get("cert")
            status_index = header_indexes.get("status")
            territory_index = header_indexes.get("territory")
            address_index = header_indexes.get("address")
            founder_index = header_indexes.get("founder")
            form_index = header_indexes.get("form")

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

                if title.strip().lower() == "наименование сми":
                    continue

                cert_num = self._get_value_by_index(values, cert_index)
                status = self._get_value_by_index(values, status_index)
                territory = self._get_value_by_index(values, territory_index)
                address = self._get_value_by_index(values, address_index)
                founder = self._get_value_by_index(values, founder_index)
                media_form = self._get_value_by_index(values, form_index)

                results.append(
                    self._build_result(
                        title=title,
                        cert_num=cert_num,
                        status=status,
                        territory=territory,
                        address=address,
                        founder=founder,
                        media_form=media_form,
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
        results: list[TextSearchResult] = []

        candidate_blocks = soup.select("div, li, article, section")

        for block in candidate_blocks:
            if not isinstance(block, Tag):
                continue

            text = self._clean_text(block.get_text(" ", strip=True))

            if not text:
                continue

            lowered = text.lower()

            if not self._looks_like_media_result(lowered):
                continue

            title = self._extract_labeled_value(
                text,
                labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Наименование",
                    "Название",
                ),
                stop_labels=(
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Свидетельство",
                    "Статус",
                    "Территория",
                    "Адрес редакции",
                    "Учредитель",
                    "Форма распространения",
                ),
            )

            cert_num = self._extract_labeled_value(
                text,
                labels=(
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Свидетельство",
                ),
                stop_labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Статус",
                    "Территория",
                    "Адрес редакции",
                    "Учредитель",
                    "Форма распространения",
                ),
            )

            status = self._extract_labeled_value(
                text,
                labels=("Статус",),
                stop_labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Территория",
                    "Адрес редакции",
                    "Учредитель",
                    "Форма распространения",
                ),
            )

            territory = self._extract_labeled_value(
                text,
                labels=("Территория", "Территория распространения"),
                stop_labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Статус",
                    "Адрес редакции",
                    "Учредитель",
                    "Форма распространения",
                ),
            )

            address = self._extract_labeled_value(
                text,
                labels=("Адрес редакции", "Адрес"),
                stop_labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Статус",
                    "Территория",
                    "Учредитель",
                    "Форма распространения",
                ),
            )

            founder = self._extract_labeled_value(
                text,
                labels=("Учредитель", "Учредители"),
                stop_labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Статус",
                    "Территория",
                    "Адрес редакции",
                    "Форма распространения",
                ),
            )

            media_form = self._extract_labeled_value(
                text,
                labels=("Форма распространения", "Форма СМИ"),
                stop_labels=(
                    "Наименование СМИ",
                    "Название СМИ",
                    "СМИ",
                    "Регистрационный номер",
                    "Номер свидетельства",
                    "Статус",
                    "Территория",
                    "Адрес редакции",
                    "Учредитель",
                ),
            )

            if not title:
                title = self._guess_title_from_text(text)

            if not title:
                continue

            results.append(
                self._build_result(
                    title=title,
                    cert_num=cert_num,
                    status=status,
                    territory=territory,
                    address=address,
                    founder=founder,
                    media_form=media_form,
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
                    "наименование сми",
                    "название сми",
                    "сми",
                    "наименование",
                    "название",
                ),
            )

            cert_index = self._find_header_index(
                headers,
                variants=(
                    "регистрационный номер",
                    "номер свидетельства",
                    "свидетельство",
                    "рег. номер",
                    "рег номер",
                    "номер",
                ),
            )

            status_index = self._find_header_index(
                headers,
                variants=(
                    "статус",
                    "состояние",
                ),
            )

            territory_index = self._find_header_index(
                headers,
                variants=(
                    "территория распространения",
                    "территория",
                    "регион",
                    "субъект",
                ),
            )

            address_index = self._find_header_index(
                headers,
                variants=(
                    "адрес редакции",
                    "адрес",
                    "местонахождение",
                ),
            )

            founder_index = self._find_header_index(
                headers,
                variants=(
                    "учредитель",
                    "учредители",
                    "заявитель",
                ),
            )

            form_index = self._find_header_index(
                headers,
                variants=(
                    "форма распространения",
                    "форма сми",
                    "форма",
                    "тип сми",
                    "вид сми",
                ),
            )

            if title_index is None:
                title_index = self._guess_title_index(
                    headers=headers,
                    cert_index=cert_index,
                    status_index=status_index,
                )

            if title_index is None:
                continue

            return {
                "title": title_index,
                **({"cert": cert_index} if cert_index is not None else {}),
                **({"status": status_index} if status_index is not None else {}),
                **({"territory": territory_index} if territory_index is not None else {}),
                **({"address": address_index} if address_index is not None else {}),
                **({"founder": founder_index} if founder_index is not None else {}),
                **({"form": form_index} if form_index is not None else {}),
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
    def _guess_title_index(
        *,
        headers: list[str],
        cert_index: int | None,
        status_index: int | None,
    ) -> int | None:
        for index, header in enumerate(headers):
            if index == cert_index or index == status_index:
                continue

            if header:
                return index

        return None

    @staticmethod
    def _looks_like_media_result(text: str) -> bool:
        markers = (
            "регистрационный номер",
            "номер свидетельства",
            "наименование сми",
            "название сми",
            "адрес редакции",
            "учредитель",
            "территория распространения",
        )

        return any(marker in text for marker in markers)

    @staticmethod
    def _guess_title_from_text(text: str) -> str | None:
        parts = [part.strip(" :—-") for part in text.split("  ") if part.strip()]

        for part in parts:
            lowered = part.lower()

            if any(
                marker in lowered
                for marker in (
                    "регистрационный номер",
                    "номер свидетельства",
                    "статус",
                    "территория",
                    "адрес",
                    "учредитель",
                )
            ):
                continue

            if len(part) >= 2:
                return part

        return None

    @staticmethod
    def _extract_labeled_value(
        text: str,
        *,
        labels: tuple[str, ...],
        stop_labels: tuple[str, ...],
    ) -> str | None:
        lower_text = text.lower()

        label_index: int | None = None
        found_label: str | None = None

        for label in labels:
            current_index = lower_text.find(label.lower())

            if current_index == -1:
                continue

            if label_index is None or current_index < label_index:
                label_index = current_index
                found_label = label

        if label_index is None or found_label is None:
            return None

        value_start = label_index + len(found_label)

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
    def _normalize_header(value: str) -> str:
        return " ".join(value.lower().replace("\xa0", " ").split())

    @staticmethod
    def _build_result(
        *,
        title: str,
        cert_num: str | None,
        status: str | None,
        territory: str | None,
        address: str | None,
        founder: str | None,
        media_form: str | None,
        page_url: str,
    ) -> TextSearchResult:
        snippet_parts: list[str] = []

        if cert_num:
            snippet_parts.append(f"Рег. номер: {cert_num}")

        if status:
            snippet_parts.append(f"Статус: {status}")

        if media_form:
            snippet_parts.append(f"Форма: {media_form}")

        if territory:
            snippet_parts.append(f"Территория: {territory}")

        if founder:
            snippet_parts.append(f"Учредитель: {founder}")

        if address:
            snippet_parts.append(f"Адрес редакции: {address}")

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
