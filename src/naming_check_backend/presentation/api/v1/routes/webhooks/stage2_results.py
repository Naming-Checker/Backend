import asyncio
import logging
import uuid
from collections import defaultdict

from fastapi import APIRouter, HTTPException, status

from naming_check_backend.infrastructure.async_pipeline.async_result_store import result_store
from naming_check_backend.infrastructure.collectors.external_sources import ExternalSourceCollector
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    CollectedItem,
    CollectedSourceBatch,
    DirectCollectRequest,
    DirectCollectResponse,
)
from naming_check_backend.presentation.schemas.contracts import (
    ProcessingStatus,
    Stage2StatusResponse,
    StartStage2Request,
    StartStage2Response,
)
from naming_check_backend.shared.resources import Resource

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start", status_code=status.HTTP_202_ACCEPTED, response_model=StartStage2Response)
async def start_stage2_job(payload: StartStage2Request) -> StartStage2Response:
    correlation_id = uuid.uuid4()

    await result_store.create_job(
        str(correlation_id),
        partial_allowed=True,
        naming=payload.naming,
        sources=[r.value for r in payload.resources] if payload.resources else None,
    )

    async def _bg() -> None:
        try:
            await result_store.mark_in_progress(str(correlation_id))
            collector = ExternalSourceCollector()

            internal_payload = {
                "correlation_id": str(correlation_id),
                "naming": payload.naming,
                "source_batch": [r.value for r in payload.resources] if payload.resources else [],
            }

            raw_results = await collector.collect_from_payload(internal_payload)

            await result_store.set_completed(str(correlation_id), raw_results)
        except Exception as exc:  # pragma: no cover - background logging
            logger.exception("Background Stage2 job %s failed: %s", correlation_id, exc)
            await result_store.set_failed(str(correlation_id), str(exc))

    task = asyncio.create_task(_bg())

    def _log(t: asyncio.Task) -> None:  # pragma: no cover - background logging
        try:
            exc = t.exception()
            if exc:
                logger.exception("Background job %s failed: %s", correlation_id, exc)
        except asyncio.CancelledError:
            logger.info("Background job %s cancelled", correlation_id)

    task.add_done_callback(_log)

    return StartStage2Response(correlation_id=correlation_id)


@router.get("/{correlation_id}", response_model=Stage2StatusResponse)
async def get_stage2_job_status(correlation_id: uuid.UUID) -> Stage2StatusResponse:
    job = await result_store.get_job(str(correlation_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    results = job.get("results", []) or []

    if results:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for rec in results:
            try:
                src = str(rec.get("source", "unknown"))
            except Exception:
                src = "unknown"

            grouped[src].append(rec if isinstance(rec, dict) else {})

        response_models_list: list[CollectedSourceBatch] = []
        for src, recs in grouped.items():
            src_enum = next((r for r in Resource if r.value == src), None)
            if src_enum is None:
                try:
                    src_enum = Resource(src)
                except Exception:
                    src_enum = Resource.YANDEX

            items_list: list[CollectedItem] = []
            for rec in recs:
                title = rec.get("title", "") if isinstance(rec, dict) else ""
                url = rec.get("url", "") if isinstance(rec, dict) else ""
                snippet = rec.get("snippet", None) if isinstance(rec, dict) else None
                items_list.append(CollectedItem(title=title, url=url, snippet=snippet))

            response_models_list.append(CollectedSourceBatch(source=src_enum, results=items_list))
    else:
        response_models_list = []

    # normalize status string from store to ProcessingStatus enum
    raw_status = job.get("status")
    try:
        status_enum = ProcessingStatus(raw_status) if isinstance(raw_status, str) else ProcessingStatus.FAILED
    except Exception:
        status_enum = ProcessingStatus.FAILED

    response_models: list[CollectedSourceBatch] | None = response_models_list or None

    return Stage2StatusResponse(
        correlation_id=correlation_id,
        status=status_enum,
        response=response_models,
    )


@router.post(
    "/direct",
    status_code=status.HTTP_200_OK,
    response_model=DirectCollectResponse,
    responses=COMMON_ERROR_RESPONSES,
    summary="Direct collect: query external resources",
    description="Invoke external collectors synchronously for a query and return per-resource results.",
)
async def collect_direct_simple(payload: DirectCollectRequest) -> DirectCollectResponse:
    collector = ExternalSourceCollector()

    internal_payload = {
        "correlation_id": f"direct:{payload.query}",
        "naming": payload.query,
        "source_batch": payload.resources,
    }

    try:
        raw_results = await collector.collect_from_payload(internal_payload)

        converted_results: list[CollectedSourceBatch] = []
        for batch in raw_results:
            src_raw = batch.get("source") if isinstance(batch, dict) else None
            src_str = str(src_raw).lower() if src_raw is not None else ""
            src_enum = next((r for r in Resource if r.value == src_str), Resource.YANDEX)

            items = batch.get("results", []) if isinstance(batch, dict) else []
            converted_items: list[CollectedItem] = []
            for it in items:
                if isinstance(it, dict):
                    converted_items.append(
                        CollectedItem(
                            title=it.get("title", ""), url=it.get("url", ""), snippet=it.get("snippet")
                        )
                    )
                else:
                    converted_items.append(
                        CollectedItem(
                            title=getattr(it, "title", ""),
                            url=getattr(it, "url", ""),
                            snippet=getattr(it, "snippet", None),
                        )
                    )

            converted_results.append(CollectedSourceBatch(source=src_enum, results=converted_items))

        return DirectCollectResponse(results=converted_results)
    except Exception as e:
        logger.exception("Direct collection failed for query=%s: %s", payload.query, e)
        return DirectCollectResponse(results=[])
