"""FeedbackIQ — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.core.tokenizer import count_tokens


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm-up solo de lo crítico (tokenizer + CT2). Embeddings semánticos = lazy.
    count_tokens("warmup")
    get_settings().export_path
    try:
        from app.core.translator import warm_up as warm_translator

        warm_translator()
    except Exception:
        pass
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FeedbackIQ",
        description="Ingesta Excel → tokenización o200k_base → optimización opcional → clasificación → export + analítica de ahorro.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CORS_ORIGIN, "http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
