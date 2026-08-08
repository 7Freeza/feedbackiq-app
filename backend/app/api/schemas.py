from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Validación simple (sin dependencia email-validator)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class HealthResponse(BaseModel):
    ok: bool
    version: str
    tokenizer: str
    domains: list[str]


class AnalyticsRecalcRequest(BaseModel):
    tokens_original: int = Field(ge=0)
    tokens_optimized: int = Field(ge=0)
    item_count: int = Field(ge=1)
    optimize_enabled: bool = True
    price_per_million: float = Field(default=2.50, gt=0)
    daily_volume: int = Field(default=10_000, ge=1)


class ProblemReportRequest(BaseModel):
    mensaje: str = Field(min_length=10, max_length=4000)
    page: str | None = Field(default=None, max_length=200)
    # Opcional: si viene, n8n puede enviar auto-reply por plantilla
    email: str | None = Field(default=None, max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if len(s) > 254 or not _EMAIL_RE.match(s):
            raise ValueError("El correo no es válido.")
        return s.lower()
