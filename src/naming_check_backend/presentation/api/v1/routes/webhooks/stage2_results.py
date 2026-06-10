import asyncio
import logging

from fastapi import APIRouter, status

from naming_check_backend.application.use_cases.stage2.webhook_callback_processing import (
    WebhookCallbackProcessingUseCase,
)
from naming_check_backend.infrastructure.collectors.external_sources import ExternalSourceCollector
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    CollectedItem,
    CollectedSourceBatch,
    DirectCollectRequest,
    DirectCollectResponse,
    Stage2WebhookRequest,
    Stage2WebhookResponse,
)
from naming_check_backend.shared.resources import Resource

logger = logging.getLogger(__name__)
router = APIRouter()
use_case = WebhookCallbackProcessingUseCase()


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Stage2WebhookResponse,
    responses=COMMON_ERROR_RESPONSES,
    summary="Accept Stage 2 webhook result batch",
    description=(
        "Receives partial or final Stage 2 batches from the async pipeline. "
        "The endpoint is idempotent by `correlation_id` and accepts unordered deliveries."
    ),
)
async def receive_stage2_result(payload: Stage2WebhookRequest) -> Stage2WebhookResponse:
    logger.info(
        "stage2 webhook received",
        extra={
            "correlation_id": payload.correlation_id,
            "partial": payload.partial,
        },
    )
    stage2_job = use_case.execute(payload.correlation_id, payload.partial)

    try:
        collector = ExternalSourceCollector()

        task = asyncio.create_task(collector.collect_from_payload(payload.model_dump()))

        def _log_task_result(t: asyncio.Task) -> None:
            try:
                exc = t.exception()
                if exc:
                    logger.exception("Background collection failed for %s: %s", payload.correlation_id, exc)
            except asyncio.CancelledError:
                logger.info("Background collection cancelled for %s", payload.correlation_id)
            except Exception:
                logger.exception("Failed reading background task result for %s", payload.correlation_id)

        task.add_done_callback(_log_task_result)
    except Exception as e:
        logger.exception("Failed to schedule external collection for %s: %s", payload.correlation_id, e)

    return Stage2WebhookResponse(
        correlation_id=stage2_job.correlation_id,
        partial=stage2_job.partial_results_allowed,
        use_case=use_case.__class__.__name__,
    )


@router.post(
    "/collect",
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
