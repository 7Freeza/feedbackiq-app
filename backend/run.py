#!/usr/bin/env python3
"""Arranque del backend FeedbackIQ (uvicorn multi-worker)."""

import os

import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    # Un solo proceso: el job store en memoria y el pool de hilos pesados
    # deben compartir estado. Concurrencia real = ThreadPoolExecutor (jobs.py)
    # + asyncio.to_thread en /analyze. Ajustable con UVICORN_WORKERS (solo si
    # se migra a Redis/RQ para jobs).
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        workers=workers,
        reload=False,
        log_level="info",
        timeout_keep_alive=30,
        limit_concurrency=40,
        # Hilos para requests concurrentes mientras un job pesado corre en pool
        timeout_graceful_shutdown=15,
    )
