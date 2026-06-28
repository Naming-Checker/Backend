from __future__ import annotations

import asyncio
import time
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


class AsyncResultStore:
    """Lightweight in-memory store for Stage2 job lifecycle and results.

    This is intentionally simple: it's an asyncio-safe in-memory store used
    by the demo/test environment. For production replace with a durable
    store (Redis, DB, etc.).
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        # default TTL in seconds (10 minutes)
        self._default_ttl_seconds: int = 10 * 60

    async def create_job(
        self,
        correlation_id: str,
        partial_allowed: bool = True,
        naming: str | None = None,
        sources: list[str] | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        async with self._lock:
            await self._purge_expired_locked()
            if correlation_id not in self._store:
                now = time.time()
                ttl = int(ttl_seconds) if ttl_seconds is not None else self._default_ttl_seconds
                expires_at = now + ttl if ttl > 0 else None
                self._store[correlation_id] = {
                    "correlation_id": correlation_id,
                    "status": "accepted",
                    "partial_allowed": partial_allowed,
                    "naming": naming,
                    "sources": list(sources) if sources else [],
                    "results": [],
                    "errors": [],
                    "created_at": now,
                    "updated_at": now,
                    "ttl_seconds": ttl,
                    "expires_at": expires_at,
                }

    async def mark_in_progress(self, correlation_id: str) -> None:
        async with self._lock:
            await self._purge_expired_locked()
            job = self._store.get(correlation_id)
            if job is None:
                await self.create_job(correlation_id)
                job = self._store[correlation_id]
            job["status"] = "partial"
            job["updated_at"] = time.time()
            # refresh expiration
            ttl = job.get("ttl_seconds", self._default_ttl_seconds)
            job["expires_at"] = time.time() + ttl if ttl > 0 else None

    async def add_results(
        self,
        correlation_id: str,
        batches: list[dict[str, Any]],
        partial: bool = True,
    ) -> None:
        async with self._lock:
            await self._purge_expired_locked()
            job = self._store.get(correlation_id)
            if job is None:
                await self.create_job(correlation_id, partial_allowed=partial)
                job = self._store[correlation_id]

            for b in batches:
                if not isinstance(b, dict):
                    continue

                # support both collector batches ({'source', 'results'})
                # and webhook-shaped payloads that contain `matches`.
                if "results" in b:
                    src = b.get("source")
                    items = b.get("results", []) or []
                else:
                    src = b.get("source") or "webhook"
                    items = b.get("matches", []) or []

                for item in items:
                    if isinstance(item, dict):
                        record = {"source": src, **item}
                    else:
                        # best-effort conversion for model instances
                        try:
                            record = {"source": src, **item.__dict__}
                        except Exception:
                            record = {"source": src}
                    job["results"].append(record)

            job["status"] = "partial" if partial else "completed"
            job["updated_at"] = time.time()
            # refresh expiration after adding results
            ttl = job.get("ttl_seconds", self._default_ttl_seconds)
            job["expires_at"] = time.time() + ttl if ttl > 0 else None

    async def set_completed(self, correlation_id: str, batches: list[dict[str, Any]]) -> None:
        await self.add_results(correlation_id, batches, partial=False)

    async def set_failed(self, correlation_id: str, error: str) -> None:
        async with self._lock:
            await self._purge_expired_locked()
            job = self._store.get(correlation_id)
            if job is None:
                await self.create_job(correlation_id, partial_allowed=False)
                job = self._store[correlation_id]
            job["status"] = "failed"
            job["errors"].append({"message": error, "at": time.time()})
            job["updated_at"] = time.time()
            ttl = job.get("ttl_seconds", self._default_ttl_seconds)
            job["expires_at"] = time.time() + ttl if ttl > 0 else None

    async def get_job(self, correlation_id: str) -> dict[str, Any] | None:
        async with self._lock:
            await self._purge_expired_locked()
            job = self._store.get(correlation_id)
            if job is None:
                return None
            # return a shallow copy to avoid accidental mutation
            return dict(job)

    async def _purge_expired_locked(self) -> None:
        """Purge expired jobs from the store. Caller MUST hold the lock."""
        now = time.time()
        to_delete = [
            cid
            for cid, job in self._store.items()
            if job.get("expires_at") and job["expires_at"] <= now
        ]
        if not to_delete:
            return
        for cid in to_delete:
            logger.debug("Purging expired job %s", cid)
            try:
                del self._store[cid]
            except KeyError:
                pass


# Single in-memory instance used by API handlers
result_store = AsyncResultStore()
