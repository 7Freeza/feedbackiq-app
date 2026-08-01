"""Analítica extendida: multi-modelo, proyecciones, punto de equilibrio.

Se calcula FUERA del budget de <2s (o en paralelo). No debe bloquear
la respuesta núcleo.
"""

from __future__ import annotations

from app.config import get_settings
from app.core.tokenizer import DEFAULT_MODEL_PRICING, cost_usd, multi_model_costs


def build_extended_analytics(
    *,
    tokens_original: int,
    tokens_optimized: int,
    item_count: int,
    optimize_enabled: bool,
    price_per_million: float | None = None,
    daily_volume: int | None = None,
    model_pricing: list[dict] | None = None,
    timings: dict | None = None,
    type_distribution: dict | None = None,
) -> dict:
    settings = get_settings()
    ppm = price_per_million if price_per_million is not None else settings.REFERENCE_PRICE_PER_MILLION
    daily = daily_volume if daily_volume is not None else settings.DEFAULT_DAILY_VOLUME
    pricing = model_pricing or DEFAULT_MODEL_PRICING

    savings_tokens = max(tokens_original - tokens_optimized, 0)
    cost_orig = cost_usd(tokens_original, ppm)
    cost_opt = cost_usd(tokens_optimized, ppm)
    cost_save = round(cost_orig - cost_opt, 6)

    avg_orig = tokens_original / max(item_count, 1)
    avg_opt = tokens_optimized / max(item_count, 1)

    # Proyección: escalar el lote actual al volumen diario de referencia
    scale = daily / max(item_count, 1)
    proj_tokens_day_orig = int(tokens_original * scale)
    proj_tokens_day_opt = int(tokens_optimized * scale)
    proj_tokens_month_orig = proj_tokens_day_orig * 30
    proj_tokens_month_opt = proj_tokens_day_opt * 30
    proj_save_day = cost_usd(proj_tokens_day_orig - proj_tokens_day_opt, ppm)
    proj_save_month = cost_usd(proj_tokens_month_orig - proj_tokens_month_opt, ppm)

    # Comparativa multi-modelo sobre el lote actual (ambos escenarios)
    models_original = multi_model_costs(tokens_original, pricing)
    models_optimized = multi_model_costs(tokens_optimized, pricing)
    model_compare = []
    opt_by_id = {m["id"]: m for m in models_optimized}
    for m in models_original:
        mo = opt_by_id.get(m["id"], m)
        model_compare.append(
            {
                "id": m["id"],
                "model": m["model"],
                "provider": m["provider"],
                "price_per_1m": m["price_per_1m"],
                "cost_original_usd": m["cost_usd"],
                "cost_optimized_usd": mo["cost_usd"],
                "savings_usd": round(m["cost_usd"] - mo["cost_usd"], 6),
            }
        )
    model_compare.sort(key=lambda x: x["cost_optimized_usd"])

    # Punto de equilibrio:
    # Costo de optimizar ≈ 0 en tokens de API (diccionario local), pero modelamos
    # un "overhead" conceptual: tiempo + tokens de un paso de preproceso si fuera LLM.
    # Equilibrio por longitud media: ahorro por item * precio debe superar overhead fijo.
    # Overhead estimado por item (tokens del preproceso si se usara un mini-modelo):
    preprocess_tokens_per_item = max(int(avg_orig * 0.15), 5)  # ~15% del original como costo de optimizar
    preprocess_cost_per_item = cost_usd(preprocess_tokens_per_item, ppm)
    savings_per_item = cost_usd(max(avg_orig - avg_opt, 0), ppm)

    if savings_per_item > 0:
        # Volumen (items) donde ahorro acumulado supera costo de preproceso acumulado
        # Con diccionario local el break-even real es ~0; reportamos el teórico si optimize fuera LLM.
        break_even_items = max(1, int(preprocess_cost_per_item / savings_per_item)) if savings_per_item else None
        # Longitud media a partir de la cual conviene (tokens originales por item)
        # Si el ahorro fraccional es s, y overhead es o tokens: (s * tokens) > o → tokens > o/s
        frac = (avg_orig - avg_opt) / max(avg_orig, 1)
        break_even_tokens_per_item = (
            int(preprocess_tokens_per_item / frac) if frac > 0 else None
        )
    else:
        break_even_items = None
        break_even_tokens_per_item = None

    # Serie de proyección 30 días (acumulado de ahorro)
    daily_save_tokens = int(savings_tokens * scale)
    projection_series = []
    cum = 0
    for day in range(1, 31):
        cum += daily_save_tokens
        projection_series.append(
            {
                "day": day,
                "cumulative_savings_tokens": cum,
                "cumulative_savings_usd": cost_usd(cum, ppm),
            }
        )

    # Desglose de timings del pipeline
    stage_breakdown = []
    if timings:
        for key, label in [
            ("ingest_ms", "Lectura Excel"),
            ("dedup_ms", "Deduplicación"),
            ("tokenize_ms", "Tokenización"),
            ("optimize_ms", "Optimización"),
            ("classify_ms", "Clasificación"),
            ("export_ms", "Exportación"),
            ("total_ms", "Total núcleo"),
        ]:
            if key in timings:
                stage_breakdown.append({"stage": label, "ms": timings[key]})

    return {
        "assumptions": {
            "price_per_million_usd": ppm,
            "daily_volume": daily,
            "monthly_multiplier": 30,
            "tokenizer": "o200k_base",
            "optimize_enabled": optimize_enabled,
            "preprocess_tokens_per_item_estimate": preprocess_tokens_per_item,
            "note": (
                "El paso de optimización actual usa diccionario local (0 tokens de API). "
                "El punto de equilibrio modela un preproceso LLM hipotético (~15% tokens del original)."
            ),
        },
        "batch": {
            "item_count": item_count,
            "tokens_original": tokens_original,
            "tokens_optimized": tokens_optimized,
            "savings_tokens": savings_tokens,
            "savings_pct": round(savings_tokens / max(tokens_original, 1) * 100, 2),
            "avg_tokens_original": round(avg_orig, 2),
            "avg_tokens_optimized": round(avg_opt, 2),
            "cost_original_usd": cost_orig,
            "cost_optimized_usd": cost_opt,
            "cost_savings_usd": cost_save,
        },
        "projection": {
            "daily_volume": daily,
            "tokens_day_original": proj_tokens_day_orig,
            "tokens_day_optimized": proj_tokens_day_opt,
            "tokens_month_original": proj_tokens_month_orig,
            "tokens_month_optimized": proj_tokens_month_opt,
            "savings_tokens_day": proj_tokens_day_orig - proj_tokens_day_opt,
            "savings_tokens_month": proj_tokens_month_orig - proj_tokens_month_opt,
            "savings_usd_day": proj_save_day,
            "savings_usd_month": proj_save_month,
            "series_30d": projection_series,
        },
        "break_even": {
            "items": break_even_items,
            "tokens_per_item": break_even_tokens_per_item,
            "savings_per_item_usd": savings_per_item,
            "preprocess_cost_per_item_usd": preprocess_cost_per_item,
            "recommendation": (
                "Conviene optimizar siempre con diccionario local (overhead ~0)."
                if optimize_enabled and savings_tokens > 0
                else (
                    "Activa optimización para medir ahorro real en este lote."
                    if not optimize_enabled
                    else "El lote no genera ahorro medible con la optimización actual."
                )
            ),
        },
        "models": model_compare,
        "stage_timings": stage_breakdown,
        "type_distribution": type_distribution or {},
    }
