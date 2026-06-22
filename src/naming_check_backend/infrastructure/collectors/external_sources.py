from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import async_playwright

from naming_check_backend.infrastructure.collectors.search_provider import TextSearchProvider
from naming_check_backend.shared.resources import Resource

logger = logging.getLogger(__name__)


class ExternalSourceCollector:
    def __init__(self, browser_headless: bool = True) -> None:
        self.browser_headless = browser_headless

    async def collect_from_payload(self, payload: dict[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
        correlation_id = payload.get("correlation_id", "unknown")
        naming = payload.get("naming") or payload.get("subject_ref") or ""
        matches = payload.get("matches", []) or []
        source_batch = payload.get("source_batch", []) or []

        query = naming or (matches[0].get("candidate_name") if matches else "")

        # default to Yandex when no explicit sources provided
        sources = [s for s in source_batch] if source_batch else [Resource.YANDEX.value]

        results: list[dict[str, Any]] = []

        alias_map: dict[str, Resource] = {
            Resource.YANDEX.value: Resource.YANDEX,
            Resource.YANDEX_VIDEO.value: Resource.YANDEX_VIDEO,
            Resource.YANDEX_MUSIC.value: Resource.YANDEX_MUSIC,
            Resource.KINOPOISK.value: Resource.KINOPOISK,
            Resource.RKN_MEDIA.value: Resource.RKN_MEDIA,
            Resource.RUTUBE.value: Resource.RUTUBE,
            Resource.GOOGLE_PLAY.value: Resource.GOOGLE_PLAY,
            Resource.RAO_RUSSIAN.value: Resource.RAO_RUSSIAN,
            Resource.RAO_FOREIGN.value: Resource.RAO_FOREIGN,
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.browser_headless)
            context = await browser.new_context()
            page = await context.new_page()

            for src in sources:
                # single provider declaration to satisfy type checker
                provider: TextSearchProvider | None = None
                # Normalize source to Resource enum when possible
                src_enum: Resource | None = None

                if isinstance(src, Resource):
                    src_enum = src
                else:
                    try:
                        if isinstance(src, str):
                            key = src.strip().lower()
                        else:
                            key = str(getattr(src, "value", src)).strip().lower()

                        src_enum = alias_map.get(key)

                        if src_enum is None:
                            try:
                                src_enum = Resource(key)
                            except Exception:
                                src_enum = None
                    except Exception:
                        src_enum = None

                src_name = src_enum.value if src_enum is not None else str(src)

                try:
                    logger.info("[%s] collecting from %s for query=%s", correlation_id, src_name, query)

                    if src_enum is Resource.YANDEX:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.yandex_search import (
                                YandexTextSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import Yandex provider: %s", e)
                            continue

                        provider = YandexTextSearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.YANDEX.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.YANDEX.value,
                        )

                    elif src_enum is Resource.YANDEX_MUSIC:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.yandex_music import (
                                YandexMusicSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import Yandex Music provider: %s", e)
                            continue

                        provider = YandexMusicSearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.YANDEX_MUSIC.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.YANDEX_MUSIC.value,
                        )

                    elif src_enum is Resource.YANDEX_VIDEO:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.yandex_video import (
                                YandexVideoSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import Yandex video provider: %s", e)
                            continue

                        provider = YandexVideoSearchProvider(page, YandexVideoSearchProvider.BASE_URL)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.YANDEX_VIDEO.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.YANDEX_VIDEO.value,
                        )

                    elif src_enum is Resource.KINOPOISK:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.kinopoisk import (
                                KinopoiskSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import Kinopoisk provider: %s", e)
                            continue

                        provider = KinopoiskSearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.KINOPOISK.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.KINOPOISK.value,
                        )

                    elif src_enum is Resource.RKN_MEDIA:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.rkn_media import (
                                RknMediaRegistrySearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import RKN provider: %s", e)
                            continue

                        provider = RknMediaRegistrySearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.RKN_MEDIA.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.RKN_MEDIA.value,
                        )

                    elif src_enum is Resource.RUTUBE:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.rutube import (
                                RutubeSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import Rutube provider: %s", e)
                            continue

                        provider = RutubeSearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.RUTUBE.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.RUTUBE.value,
                        )

                    elif src_enum is Resource.RAO_RUSSIAN:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.rao_russian import (
                                RaoRegistrySearchProvider as RaoRussianSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import RAO (russian) provider: %s", e)
                            continue

                        provider = RaoRussianSearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.RAO_RUSSIAN.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.RAO_RUSSIAN.value,
                        )

                    elif src_enum is Resource.RAO_FOREIGN:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.rao_foreign import (
                                RaoRegistrySearchProvider as RaoForeignSearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import RAO (foreign) provider: %s", e)
                            continue

                        provider = RaoForeignSearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.RAO_FOREIGN.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.RAO_FOREIGN.value,
                        )

                    elif src_enum is Resource.GOOGLE_PLAY:
                        try:
                            from naming_check_backend.infrastructure.collectors.sources.google_play import (
                                GooglePlaySearchProvider,
                            )
                        except Exception as e:
                            logger.exception("Failed to import Google Play provider: %s", e)
                            continue

                        provider = GooglePlaySearchProvider(page)
                        items = await provider.search(query, limit=limit)
                        converted = [self._to_dict_item(i) for i in items]
                        results.append({"source": Resource.GOOGLE_PLAY.value, "results": converted})
                        logger.info(
                            "[%s] parsed %d results from %s",
                            correlation_id,
                            len(converted),
                            Resource.GOOGLE_PLAY.value,
                        )

                except Exception as e:
                    logger.exception("[%s] error collecting from %s: %s", correlation_id, src, e)

            try:
                await context.close()
            except Exception:
                pass

            try:
                await browser.close()
            except Exception:
                pass

        logger.info("[%s] collected results from %d source(s)", correlation_id, len(results))
        return results

    @staticmethod
    def _to_dict_item(item: Any) -> dict[str, Any]:
        return {
            "title": getattr(item, "title", ""),
            "url": getattr(item, "url", ""),
            "snippet": getattr(item, "snippet", None),
        }
