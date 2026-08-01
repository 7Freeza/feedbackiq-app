"""Tokenización exacta con tiktoken o200k_base + costos multi-modelo."""

from __future__ import annotations

from functools import lru_cache
from hashlib import md5

import tiktoken

from app.config import get_settings

# Precios de referencia (USD / millón de tokens de entrada). Configurables en runtime vía API.
DEFAULT_MODEL_PRICING: list[dict] = [
    {"id": "deepseek-v3", "model": "DeepSeek V3", "provider": "DeepSeek", "price_per_1m": 0.27},
    {"id": "gemini-2-flash", "model": "Gemini 2.0 Flash", "provider": "Google", "price_per_1m": 0.10},
    {"id": "gpt-4o-mini", "model": "GPT-4o Mini", "provider": "OpenAI", "price_per_1m": 0.15},
    {"id": "gpt-4o", "model": "GPT-4o", "provider": "OpenAI", "price_per_1m": 2.50},
    {"id": "claude-35-sonnet", "model": "Claude 3.5 Sonnet", "provider": "Anthropic", "price_per_1m": 3.00},
    {"id": "grok-2", "model": "Grok 2", "provider": "xAI", "price_per_1m": 2.00},
]


@lru_cache(maxsize=1)
def _encoding():
    settings = get_settings()
    return tiktoken.get_encoding(settings.TOKENIZER_ENCODING)


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_encoding().encode(text))


def count_tokens_batch(texts: list[str]) -> list[int]:
    """Batch encode: un solo acceso al tokenizer, menos overhead por llamada."""
    if not texts:
        return []
    enc = _encoding()
    return [len(enc.encode(t)) if t else 0 for t in texts]


@lru_cache(maxsize=8192)
def count_tokens_cached(text_hash: str, text: str) -> int:
    """Cache por hash de texto (deduplicación de conteos repetidos)."""
    return count_tokens(text)


def text_hash(text: str) -> str:
    return md5(text.strip().lower().encode("utf-8")).hexdigest()


def cost_usd(tokens: int, price_per_million: float | None = None) -> float:
    if price_per_million is None:
        price_per_million = get_settings().REFERENCE_PRICE_PER_MILLION
    return round((tokens / 1_000_000) * price_per_million, 6)


def multi_model_costs(
    tokens: int,
    pricing: list[dict] | None = None,
) -> list[dict]:
    models = pricing or DEFAULT_MODEL_PRICING
    rows = []
    for m in models:
        price = float(m["price_per_1m"])
        rows.append(
            {
                "id": m.get("id", m["model"]),
                "model": m["model"],
                "provider": m["provider"],
                "price_per_1m": price,
                "tokens": tokens,
                "cost_usd": round((tokens / 1_000_000) * price, 6),
            }
        )
    rows.sort(key=lambda r: r["cost_usd"])
    return rows
