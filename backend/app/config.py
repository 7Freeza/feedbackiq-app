from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 4004
    CORS_ORIGIN: str = "http://localhost:5173"
    EXPORT_DIR: str = "../exports"
    MAX_UPLOAD_MB: int = 80
    # Filas: sync hasta este umbral; por encima → job en segundo plano
    MAX_SYNC_ROWS: int = 3_000
    # Tope absoluto (síncrono o job)
    MAX_ROWS: int = 50_000
    # Chunks internos de traducción/tokenización
    PIPELINE_CHUNK_SIZE: int = 500
    # Jobs pesados concurrentes (no bloquear todo el proceso)
    MAX_HEAVY_WORKERS: int = 2
    REFERENCE_PRICE_PER_MILLION: float = 2.50
    DEFAULT_DAILY_VOLUME: int = 10_000
    TOKENIZER_ENCODING: str = "o200k_base"

    # --- Reportes de problemas → n8n ---
    # URL completa del Webhook de n8n (ej. http://localhost:5678/webhook/feedbackiq-report)
    N8N_WEBHOOK_URL: str = ""
    # Header secreto compartido con n8n (Header Auth). Vacío = sin header extra.
    N8N_WEBHOOK_SECRET: str = ""
    # Nombre del header (n8n Header Auth suele usar "Authorization" o un custom)
    N8N_WEBHOOK_HEADER_NAME: str = "X-FeedbackIQ-Secret"
    # Timeout al llamar n8n (segundos)
    N8N_TIMEOUT_SEC: float = 15.0
    # Si true y no hay URL, el endpoint igual clasifica local y responde ok (modo demo)
    N8N_DRY_RUN: bool = False

    @property
    def export_path(self) -> Path:
        p = Path(self.EXPORT_DIR)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent.parent / p).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
