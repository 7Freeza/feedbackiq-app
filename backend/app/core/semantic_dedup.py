"""Deduplicación: exacta siempre; semántica solo en lotes grandes (opt-in).

La semántica (model2vec) es cara al primer load y aporta poco en samples
pequeños. Por defecto solo exacta si n < SEMANTIC_MIN_ITEMS.
"""

from __future__ import annotations

import logging
import threading
from hashlib import md5

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_encoder = None
_load_error: str | None = None
_MODEL_ID = "minishlab/potion-multilingual-128M"

# No pagar embeddings en lotes chicos (reseñas de demo ~15 filas)
SEMANTIC_MIN_ITEMS = 40


def encoder_info() -> dict:
    return {
        "ready": _encoder is not None,
        "model": _MODEL_ID if _encoder is not None else None,
        "load_error": _load_error,
        "semantic_min_items": SEMANTIC_MIN_ITEMS,
    }


def warm_up_embeddings() -> bool:
    global _encoder, _load_error
    if _encoder is not None:
        return True
    with _lock:
        if _encoder is not None:
            return True
        try:
            from model2vec import StaticModel

            _encoder = StaticModel.from_pretrained(_MODEL_ID)
            _load_error = None
            logger.info("Semantic encoder ready: %s", _MODEL_ID)
            return True
        except Exception as exc:
            _encoder = None
            _load_error = str(exc)
            logger.warning("Semantic encoder unavailable: %s", exc)
            return False


def exact_dedup(texts: list[str]) -> tuple[list[int], list[int]]:
    """Returns (canonical_indices into original list, map_item_to_canonical_pos)."""
    seen: dict[str, int] = {}
    canonical: list[int] = []
    map_idx: list[int] = []
    for i, t in enumerate(texts):
        h = md5(t.strip().lower().encode()).hexdigest()
        if h not in seen:
            seen[h] = len(canonical)
            canonical.append(i)
        map_idx.append(seen[h])
    return canonical, map_idx


def semantic_dedup(
    texts: list[str],
    *,
    threshold: float = 0.92,
    force: bool = False,
) -> tuple[list[int], list[int], str]:
    """Deduplica textos.

    Returns:
        canonical_indices, map_to_canonical_pos, method ('semantic'|'exact')
    """
    if not texts:
        return [], [], "exact"

    exact_canons, exact_map = exact_dedup(texts)
    unique_texts = [texts[i] for i in exact_canons]

    if len(unique_texts) <= 1:
        return exact_canons, exact_map, "exact"

    # Lotes pequeños: solo exacta (rápido y estable)
    if not force and len(unique_texts) < SEMANTIC_MIN_ITEMS:
        return exact_canons, exact_map, "exact"

    if not warm_up_embeddings():
        return exact_canons, exact_map, "exact"

    try:
        from semhash import SemHash

        records = [{"id": i, "text": t} for i, t in enumerate(unique_texts)]
        sh = SemHash.from_records(records, columns=["text"], model=_encoder)
        result = sh.self_deduplicate(threshold=threshold)

        kept_ids: list[int] = []
        duplicate_map: dict[int, int] = {}

        # API semhash 0.4.x: DeduplicationResult
        if hasattr(result, "selected") and result.selected is not None:
            kept_ids = [int(r["id"]) for r in result.selected]
        elif hasattr(result, "deduplicated"):
            kept_ids = [int(r["id"]) for r in result.deduplicated]
        elif isinstance(result, dict) and "deduplicated" in result:
            kept_ids = [int(r["id"]) for r in result["deduplicated"]]
        elif isinstance(result, (list, tuple)):
            kept_ids = [int(r["id"]) for r in result]

        if hasattr(result, "duplicate_map") and result.duplicate_map:
            duplicate_map = {int(k): int(v) for k, v in result.duplicate_map.items()}

        if not kept_ids:
            return exact_canons, exact_map, "exact"

        # Asegurar ids válidos
        n_u = len(unique_texts)
        kept_ids = [k for k in kept_ids if 0 <= k < n_u]
        if not kept_ids:
            return exact_canons, exact_map, "exact"

        # Posición en lista canónica
        unique_to_kept_pos: dict[int, int] = {kid: pos for pos, kid in enumerate(kept_ids)}

        # Duplicados semánticos → canónico
        for rem, keep in duplicate_map.items():
            if keep in unique_to_kept_pos:
                unique_to_kept_pos[rem] = unique_to_kept_pos[keep]

        # Cualquier unique no mapeado se mantiene como su propio canónico si estaba en kept;
        # si no, se asigna al primer kept (no colapsar todo al 0 a ciegas)
        for ui in range(n_u):
            if ui not in unique_to_kept_pos:
                # si no fue eliminado, debería estar en kept; si no, anexar
                if ui not in kept_ids:
                    unique_to_kept_pos[ui] = unique_to_kept_pos[kept_ids[0]]
                else:
                    unique_to_kept_pos[ui] = kept_ids.index(ui)

        canon_orig = [exact_canons[k] for k in kept_ids]
        map_out = [unique_to_kept_pos[exact_u] for exact_u in exact_map]
        return canon_orig, map_out, "semantic"
    except Exception as exc:
        logger.warning("Semantic dedup failed, exact only: %s", exc)
        return exact_canons, exact_map, "exact"


def cluster_stats(n_items: int, n_canonical: int) -> dict:
    saved = max(n_items - n_canonical, 0)
    return {
        "input_items": n_items,
        "canonical_items": n_canonical,
        "removed_or_merged": saved,
        "reduction_pct": round(saved / max(n_items, 1) * 100, 2),
    }
