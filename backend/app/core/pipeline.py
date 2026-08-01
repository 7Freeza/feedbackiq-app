"""Pipeline núcleo: ingesta → dedup → (opt) traducción real → clasificar → exportar.

Optimización ON  → CTranslate2 OPUS-MT ES→EN (real).
Optimización OFF → no traduce; tokens/texto optimizado = original (sin engaños).
"""

from __future__ import annotations

import gc
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.analytics import build_extended_analytics
from app.core.classifier import classify_batch
from app.core.excel_ingest import extract_from_files
from app.core.export import export_results
from app.core.semantic_dedup import cluster_stats, exact_dedup, semantic_dedup
from app.core.tokenizer import cost_usd, count_tokens_batch
from app.core.translator import dictionary_batch, engine_info, translate_batch, warm_up
from app.domains import get_domain


def _chunked_translate(texts: list[str], chunk_size: int) -> tuple[list[str], str]:
    """Traduce por bloques para no retener todo el estado de CT2 a la vez."""
    if not texts:
        return [], "passthrough"
    if len(texts) <= chunk_size:
        return translate_batch(texts)
    out: list[str] = []
    method = "ctranslate2"
    for i in range(0, len(texts), chunk_size):
        chunk = texts[i : i + chunk_size]
        part, m = translate_batch(chunk)
        out.extend(part)
        if m != "ctranslate2":
            method = m
    return out, method


def _chunked_count(texts: list[str], chunk_size: int) -> list[int]:
    if not texts:
        return []
    if len(texts) <= chunk_size:
        return count_tokens_batch(texts)
    out: list[int] = []
    for i in range(0, len(texts), chunk_size):
        out.extend(count_tokens_batch(texts[i : i + chunk_size]))
    return out


def run_core_pipeline(
    file_paths: list[str | Path],
    *,
    optimize_tokens: bool = True,
    domain_id: str = "reviews",
    price_per_million: float | None = None,
    daily_volume: int | None = None,
    job_id: str | None = None,
    semantic_dedup_enabled: bool = True,
    include_comparisons: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    chunk = settings.PIPELINE_CHUNK_SIZE
    ppm = (
        price_per_million
        if price_per_million is not None
        else settings.REFERENCE_PRICE_PER_MILLION
    )
    domain = get_domain(domain_id)
    job_id = job_id or uuid.uuid4().hex[:12]
    timings: dict[str, float] = {}
    t_start = time.perf_counter()

    # 1. Ingesta
    t0 = time.perf_counter()
    ingest = extract_from_files(file_paths)
    timings["ingest_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    if not ingest.items:
        return {
            "ok": False,
            "job_id": job_id,
            "error": "No se extrajo texto usable de los archivos.",
            "errors": ingest.errors,
            "files": [
                {
                    "filename": f.filename,
                    "rows": f.row_count,
                    "column": f.column_detected,
                    "error": f.error,
                }
                for f in ingest.files
            ],
            "timings": timings,
            "translator": engine_info(),
        }

    sources = [s for s, _ in ingest.items]
    texts = [t for _, t in ingest.items]
    n_all = len(texts)

    # 2. Dedup
    t0 = time.perf_counter()
    if semantic_dedup_enabled:
        canon_idx, map_idx, dedup_method = semantic_dedup(texts)
    else:
        canon_idx, map_idx = exact_dedup(texts)
        dedup_method = "exact"
    unique_texts = [texts[i] for i in canon_idx]
    unique_sources = [sources[i] for i in canon_idx]
    timings["dedup_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    timings["unique_items"] = len(unique_texts)
    timings["total_items"] = n_all
    timings["dedup_method"] = dedup_method
    timings["dedup_ratio"] = round(1 - (len(unique_texts) / max(n_all, 1)), 3)
    dedup_stats = cluster_stats(n_all, len(unique_texts))

    # 3. Tokens originales (por chunks)
    t0 = time.perf_counter()
    tokens_orig_u = _chunked_count(unique_texts, chunk)
    timings["tokenize_original_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    # 4. Optimización — UNA sola traducción real (CT2). Diccionario solo en comparativa muestreada.
    translate_method = "none"
    t0 = time.perf_counter()
    if optimize_tokens:
        if not warm_up():
            optimized_texts = dictionary_batch(unique_texts)
            translate_method = "dictionary"
        else:
            optimized_texts, translate_method = _chunked_translate(unique_texts, chunk)
    else:
        optimized_texts = list(unique_texts)
        translate_method = "none"
    timings["translate_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    timings["optimize_ms"] = timings["translate_ms"]

    t0 = time.perf_counter()
    if optimize_tokens:
        tokens_opt_u = _chunked_count(optimized_texts, chunk)
    else:
        tokens_opt_u = list(tokens_orig_u)
    timings["tokenize_optimized_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    timings["tokenize_ms"] = round(
        timings["tokenize_original_ms"] + timings["tokenize_optimized_ms"], 2
    )

    # Comparativa (a): muestra de diccionario (máx 200) — NO re-traduce el lote entero con CT2
    tokens_dict_u: list[int] | None = None
    tokens_ct2_est_u: list[int] | None = None
    if include_comparisons:
        t0 = time.perf_counter()
        sample_n = min(200, len(unique_texts))
        sample = unique_texts[:sample_n]
        dict_sample = dictionary_batch(sample)
        tok_dict_s = count_tokens_batch(dict_sample)
        tok_orig_s = tokens_orig_u[:sample_n]
        # Escalar muestra → lote completo
        if sum(tok_orig_s) > 0:
            ratio = sum(tok_dict_s) / sum(tok_orig_s)
            tokens_dict_u = [max(1, int(t * ratio)) for t in tokens_orig_u]
        else:
            tokens_dict_u = list(tokens_orig_u)
        tokens_ct2_est_u = tokens_opt_u if optimize_tokens else None
        timings["comparison_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    else:
        timings["comparison_ms"] = 0.0

    # 5. Clasificación (reglas sobre texto original ES)
    t0 = time.perf_counter()
    classifications = classify_batch(
        unique_texts,
        domain["rules_fn"],
        domain["fallback"],
        method_override="rules",
    )
    timings["classify_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    # 6. Resultados por fila única → expand
    unique_results = []
    for i, text in enumerate(unique_texts):
        to = tokens_orig_u[i]
        tn = tokens_opt_u[i]
        savings = to - tn if optimize_tokens else 0
        en_text = optimized_texts[i] if optimize_tokens else ""
        unique_results.append(
            {
                "source": unique_sources[i],
                "text": text[:300],
                "text_optimized": en_text[:300] if en_text else "",
                "tokens_original": to,
                "tokens_optimized": tn if optimize_tokens else to,
                "tokens_optimized_estimate": tn if optimize_tokens else to,
                "savings_tokens": savings,
                "savings_pct": round(savings / max(to, 1) * 100, 1),
                "optimized": optimize_tokens,
                "optimize_method": translate_method if optimize_tokens else "none",
                "method": classifications[i].get("_method", "rules"),
                "classification": {
                    k: v
                    for k, v in classifications[i].items()
                    if not k.startswith("_") or k == "_method"
                },
            }
        )

    results: list[dict] = []
    for i, text in enumerate(texts):
        r = dict(unique_results[map_idx[i]])
        r["source"] = sources[i]
        r["text"] = text[:300]
        results.append(r)

    total_orig = sum(r["tokens_original"] for r in results)
    total_opt = sum(r["tokens_optimized"] for r in results)
    total_opt_est = total_opt  # solo hay estimación real cuando CT2 corrió
    savings = total_orig - total_opt

    # 7. Export
    t0 = time.perf_counter()
    export_name = f"feedbackiq_{job_id}.xlsx"
    export_path = settings.export_path / export_name
    export_results(results, export_path, domain["result_keys"])
    timings["export_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
    timings["total_ms"] = elapsed_ms

    type_key = {
        "reviews": "error_type",
        "contracts": "clause_type",
        "incidents": "incident_type",
    }.get(domain_id, "error_type")
    dist = Counter(
        (r.get("classification") or {}).get(type_key, "other") for r in results
    )

    comparisons: dict[str, Any] = {}
    if include_comparisons and tokens_dict_u is not None:
        sum_orig_u = sum(tokens_orig_u)
        sum_dict = sum(tokens_dict_u)
        sum_ct2 = sum(tokens_ct2_est_u) if tokens_ct2_est_u is not None else None
        comparisons = {
            "a_dictionary": {
                "label": "Stub diccionario (referencia histórica)",
                "method": "dictionary",
                "tokens": sum_dict,
                "savings_vs_original": sum_orig_u - sum_dict,
                "savings_pct": round((sum_orig_u - sum_dict) / max(sum_orig_u, 1) * 100, 2),
                "note": "No es traducción real; no reportar como optimización profesional.",
            },
            "b_ctranslate2": {
                "label": "Traducción neuronal local (CTranslate2 OPUS-MT es→en)",
                "method": translate_method if optimize_tokens else "not_run",
                "tokens": sum_ct2,
                "savings_vs_original": (sum_orig_u - sum_ct2) if sum_ct2 is not None else None,
                "savings_pct": (
                    round((sum_orig_u - sum_ct2) / max(sum_orig_u, 1) * 100, 2)
                    if sum_ct2 is not None
                    else None
                ),
                "note": (
                    "Traducción real del lote (optimización ON)."
                    if optimize_tokens
                    else "Activa optimización para medir ahorro real CT2 en este lote."
                ),
            },
            "c_semantic_dedup": {
                "label": "Con deduplicación",
                "method": dedup_method,
                "items_before": n_all,
                "items_after": len(unique_texts),
                "tokens_canonical_original": sum_orig_u,
                "tokens_canonical_translated": sum_ct2 if sum_ct2 is not None else sum_orig_u,
                "volume_reduction_pct": dedup_stats["reduction_pct"],
                "note": "Reduce cuántos textos se traducen; en lotes <40 solo exacta.",
            },
            "primary_reported": "b_ctranslate2" if optimize_tokens else "none",
        }

    core = {
        "tokens_original": total_orig,
        "tokens_optimized": total_opt,
        "tokens_optimized_estimate": total_opt_est,
        "savings_tokens": savings,
        "savings_tokens_estimate": total_orig - total_opt_est,
        "savings_pct": round(savings / max(total_orig, 1) * 100, 2),
        "item_count": len(results),
        "unique_count": len(unique_texts),
        "elapsed_ms": elapsed_ms,
        "cost_original_usd": cost_usd(total_orig, ppm),
        "cost_optimized_usd": cost_usd(total_opt, ppm),
        "cost_savings_usd": cost_usd(savings, ppm),
        "download_url": f"/api/download/{export_name}",
        "export_filename": export_name,
        "optimize_tokens": optimize_tokens,
        "optimize_method": translate_method if optimize_tokens else "none",
        "optimize_method_label": _method_label(
            translate_method if optimize_tokens else "none"
        ),
        "dedup_method": dedup_method,
        "domain": domain_id,
        "price_per_million": ppm,
        "within_sla": elapsed_ms < 2000,
    }

    analytics = build_extended_analytics(
        tokens_original=total_orig,
        tokens_optimized=total_opt,
        item_count=len(results),
        optimize_enabled=optimize_tokens,
        price_per_million=ppm,
        daily_volume=daily_volume,
        timings=timings,
        type_distribution=dict(dist),
    )
    analytics["comparisons"] = comparisons
    analytics["dedup"] = dedup_stats
    analytics["translator"] = engine_info()

    out = {
        "ok": True,
        "job_id": job_id,
        "core": core,
        "timings": timings,
        "files": [
            {
                "filename": f.filename,
                "rows": f.row_count,
                "column": f.column_detected,
                "error": f.error,
                "truncated": getattr(f, "truncated", False),
            }
            for f in ingest.files
        ],
        "errors": ingest.errors,
        "results_preview": results[:50],
        "results_total": len(results),
        "analytics": analytics,
        "comparisons": comparisons,
        "type_key": type_key,
        "translator": engine_info(),
    }

    # Liberar objetos grandes antes de devolver (aislamiento entre requests)
    del unique_texts, unique_results, results, optimized_texts, tokens_orig_u, tokens_opt_u
    if n_all >= 2000:
        gc.collect()

    return out


def _method_label(method: str) -> str:
    return {
        "ctranslate2": "Traducción neuronal local (CTranslate2 / OPUS-MT es→en)",
        "dictionary": "Fallback diccionario (motor CT2 no disponible)",
        "passthrough": "Sin optimización",
        "none": "Optimización desactivada",
    }.get(method, method)
