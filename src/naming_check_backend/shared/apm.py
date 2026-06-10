"""Optional Elastic APM distributed tracing."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def is_apm_enabled() -> bool:
    return os.environ.get("ELASTIC_APM_ENABLED", "").lower() in {"1", "true", "yes"}


def append_trace_context(payload: dict[str, Any]) -> None:
    """Add ECS trace fields so logs link to APM transactions in Kibana."""
    if not is_apm_enabled():
        return
    try:
        import elasticapm

        trace_id = elasticapm.get_trace_id()
        transaction_id = elasticapm.get_transaction_id()
        if trace_id:
            payload["trace.id"] = trace_id
        if transaction_id:
            payload["transaction.id"] = transaction_id
    except Exception:
        return


def label_current_transaction(**labels: object) -> None:
    if not is_apm_enabled():
        return
    try:
        import elasticapm

        if elasticapm.get_client():
            elasticapm.label(**{key: value for key, value in labels.items() if value is not None})
    except Exception:
        return


def configure_apm(app: FastAPI, *, service_name: str) -> None:
    if not is_apm_enabled():
        logger.info("Elastic APM disabled (set ELASTIC_APM_ENABLED=true to enable)")
        return

    try:
        from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
    except ImportError:
        logger.warning("elastic-apm is not installed; tracing disabled")
        return

    server_url = os.environ.get("ELASTIC_APM_SERVER_URL", "http://apm-server:8200")
    environment = os.environ.get("ELASTIC_APM_ENVIRONMENT") or os.environ.get("APP_ENV", "local")
    client = make_apm_client(
        {
            "SERVICE_NAME": os.environ.get("ELASTIC_APM_SERVICE_NAME", service_name),
            "SERVER_URL": server_url,
            "ENVIRONMENT": environment,
            "TRANSACTION_SAMPLE_RATE": float(os.environ.get("ELASTIC_APM_TRANSACTION_SAMPLE_RATE", "1.0")),
            "CAPTURE_BODY": os.environ.get("ELASTIC_APM_CAPTURE_BODY", "errors"),
            "USE_ELASTIC_TRACEPARENT_HEADER": True,
            "ENABLED": True,
        }
    )
    if client is None:
        return

    app.add_middleware(ElasticAPM, client=client)  # type: ignore[arg-type]
    logger.info("Elastic APM enabled", extra={"apm_server_url": server_url})
