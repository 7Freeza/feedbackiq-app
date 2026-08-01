"""Reglas para contratos de arrendamiento (extracción estructural ligera)."""

from __future__ import annotations

import re

FALLBACK = {
    "clause_type": "general",
    "amount_hint": None,
    "date_hint": None,
    "severity": "low",
    "summary": "Unclassified contract clause.",
}

_RULES: dict[str, dict] = {
    "penalty": {
        "keywords": ["penalizacion", "penalización", "multa", "sancion", "sanción", "incumplimiento"],
        "severity": "high",
        "summary": "Penalty or sanction clause.",
    },
    "payment": {
        "keywords": ["renta", "canon", "pago mensual", "monto", "pesos", "usd", "deposito", "depósito"],
        "severity": "high",
        "summary": "Payment or deposit obligation.",
    },
    "termination": {
        "keywords": ["terminacion", "terminación", "rescision", "rescisión", "finalizacion", "finalización", "vencimiento"],
        "severity": "medium",
        "summary": "Termination or expiration terms.",
    },
    "maintenance": {
        "keywords": ["mantenimiento", "reparacion", "reparación", "danos", "daños", "desperfectos"],
        "severity": "medium",
        "summary": "Maintenance and damage responsibility.",
    },
    "use_restrictions": {
        "keywords": ["prohibido", "no podra", "no podrá", "uso exclusivo", "subarrendar", "mascotas"],
        "severity": "medium",
        "summary": "Use restrictions or prohibitions.",
    },
    "legal_boilerplate": {
        "keywords": ["por medio del presente", "en fe de lo cual", "comparecen", "otorgan"],
        "severity": "low",
        "summary": "Legal boilerplate / ceremonial language.",
    },
}

_AMOUNT_RE = re.compile(
    r"(?:\$|USD|COP|EUR|MXN)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:pesos|dolares|dólares|usd|eur)?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\b",
    re.IGNORECASE,
)


def apply_rules(text: str) -> dict | None:
    t = text.lower()
    best_type, best_score, best_info = None, 0, None
    for clause_type, info in _RULES.items():
        score = sum(1 for kw in info["keywords"] if kw in t)
        if score > best_score:
            best_score, best_type, best_info = score, clause_type, info
    if not best_type or best_score < 1:
        return None

    amount = None
    m = _AMOUNT_RE.search(text)
    if m:
        amount = m.group(0).strip()
    date_hint = None
    d = _DATE_RE.search(text)
    if d:
        date_hint = d.group(1)

    return {
        "clause_type": best_type,
        "amount_hint": amount,
        "date_hint": date_hint,
        "severity": best_info["severity"],
        "summary": best_info["summary"],
    }
