"""Structured JSON logging to stdout for ELK/Filebeat."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, env: str) -> None:
        super().__init__()
        self._service = service
        self._env = env

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "@timestamp": (datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")),
            "level": record.levelname,
            "service": self._service,
            "env": self._env,
            "message": record.getMessage(),
            "logger": record.name,
        }
        req_id = request_id_ctx.get()
        if req_id:
            payload["request_id"] = req_id
        for key in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
            "upstream_status",
            "upstream_url",
            "upstream_duration_ms",
            "upload_filename",
            "content_length",
            "top_k",
            "query_length",
            "match_count",
            "mktu_count",
            "correlation_id",
            "partial",
            "logo_path",
            "error",
            "temp_path",
            "env",
            "log_level",
        ):
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:
                    payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(*, service_name: str, env: str, level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service=service_name, env=env))
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False


def get_request_id() -> str | None:
    return request_id_ctx.get()
