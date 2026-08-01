"""Clasificación estructurada: reglas (rápido) con marca de método."""

from __future__ import annotations

from typing import Callable


def classify_batch(
    texts: list[str],
    rules_fn: Callable[[str], dict | None],
    fallback: dict,
    method_override: str | None = None,
) -> list[dict]:
    """Clasifica textos con reglas. Siempre devuelve JSON estructurado validable.

    method_override permite forzar la etiqueta (p.ej. 'llm' si en el futuro
    se enruta a un modelo). Por defecto 'rules'.
    """
    method = method_override or "rules"
    out: list[dict] = []
    for t in texts:
        cls = rules_fn(t)
        if cls is None:
            cls = dict(fallback)
            used = method
            matched = False
        else:
            cls = dict(cls)
            used = method
            matched = True
        cls["_method"] = used
        cls["_matched"] = matched
        out.append(cls)
    return out
