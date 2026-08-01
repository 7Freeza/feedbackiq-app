"""Cola simple de trabajos pesados (ThreadPoolExecutor).

Aísla archivos grandes del hilo del servidor HTTP para que un Excel
de 50k filas no congele solicitudes pequeñas posteriores.
"""

from __future__ import annotations

import gc
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_executor: ThreadPoolExecutor | None = None
_heavy_sem: threading.Semaphore | None = None


def _ensure_pool() -> ThreadPoolExecutor:
    global _executor, _heavy_sem
    settings = get_settings()
    if _executor is None:
        n = max(1, settings.MAX_HEAVY_WORKERS)
        _executor = ThreadPoolExecutor(max_workers=n, thread_name_prefix="fiq-heavy")
        _heavy_sem = threading.Semaphore(n)
    return _executor


@dataclass
class JobRequest:
    file_paths: list[Path]
    optimize_tokens: bool = True
    domain_id: str = "reviews"
    price_per_million: float | None = None
    daily_volume: int | None = None
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def list_jobs(limit: int = 20) -> list[dict]:
    with _lock:
        items = sorted(_jobs.values(), key=lambda x: x.get("created_at", 0), reverse=True)
        return [dict(x) for x in items[:limit]]


def _set_job(job_id: str, **kwargs) -> None:
    with _lock:
        if job_id not in _jobs:
            _jobs[job_id] = {}
        _jobs[job_id].update(kwargs)


def _cleanup_old_jobs(max_keep: int = 40) -> None:
    with _lock:
        if len(_jobs) <= max_keep:
            return
        ordered = sorted(_jobs.items(), key=lambda kv: kv[1].get("created_at", 0))
        for jid, _ in ordered[: max(0, len(_jobs) - max_keep)]:
            _jobs.pop(jid, None)


def _run_pipeline_job(req: JobRequest) -> None:
    from app.core.pipeline import run_core_pipeline

    assert _heavy_sem is not None
    _set_job(req.job_id, status="running", started_at=time.time(), progress=0.05, message="Procesando…")
    acquired = _heavy_sem.acquire(timeout=600)
    if not acquired:
        _set_job(req.job_id, status="error", error="Cola de trabajos llena. Reintenta en unos segundos.", finished_at=time.time())
        return
    try:
        result = run_core_pipeline(
            req.file_paths,
            optimize_tokens=req.optimize_tokens,
            domain_id=req.domain_id,
            price_per_million=req.price_per_million,
            daily_volume=req.daily_volume,
            job_id=req.job_id,
            include_comparisons=True,
        )
        if result.get("ok"):
            _set_job(
                req.job_id,
                status="done",
                result=result,
                progress=1.0,
                message="Completado",
                finished_at=time.time(),
            )
        else:
            _set_job(
                req.job_id,
                status="error",
                error=result.get("error", "Fallo de procesamiento"),
                result=result,
                finished_at=time.time(),
            )
    except Exception as exc:
        logger.exception("Job %s failed", req.job_id)
        _set_job(req.job_id, status="error", error=str(exc), finished_at=time.time())
    finally:
        _heavy_sem.release()
        # Liberar memoria residual del worker
        gc.collect()
        _cleanup_old_jobs()


def submit_analyze_job(req: JobRequest) -> str:
    pool = _ensure_pool()
    _set_job(
        req.job_id,
        job_id=req.job_id,
        status="queued",
        created_at=time.time(),
        progress=0.0,
        message="En cola",
        optimize_tokens=req.optimize_tokens,
        domain=req.domain_id,
        files=[str(p.name) for p in req.file_paths],
    )
    pool.submit(_run_pipeline_job, req)
    return req.job_id


def run_pipeline_isolated(**kwargs) -> dict[str, Any]:
    """Ejecuta el pipeline en el pool (aislado del event loop)."""
    from app.core.pipeline import run_core_pipeline

    _ensure_pool()
    assert _heavy_sem is not None
    acquired = _heavy_sem.acquire(timeout=120)
    if not acquired:
        return {
            "ok": False,
            "error": "El servidor está procesando otros archivos grandes. Espera un momento e intenta de nuevo.",
        }
    try:
        return run_core_pipeline(**kwargs)
    finally:
        _heavy_sem.release()
        gc.collect()
