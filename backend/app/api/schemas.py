from __future__ import annotations

from pydantic import BaseModel, Field


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
