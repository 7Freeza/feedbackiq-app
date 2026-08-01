"""Reglas para incidencias (soporte / operaciones / citas)."""

from __future__ import annotations

FALLBACK = {
    "incident_type": "other",
    "priority": "low",
    "department": "general",
    "summary": "Unclassified incident.",
}

_RULES: dict[str, dict] = {
    "reschedule": {
        "keywords": ["reprogramar", "reprogramacion", "reprogramación", "cambiar cita", "otra fecha", "otro horario"],
        "priority": "medium",
        "department": "scheduling",
        "summary": "Request to reschedule an appointment.",
    },
    "cancel": {
        "keywords": ["cancelar", "cancelacion", "cancelación", "anular", "no podre", "no podré"],
        "priority": "medium",
        "department": "scheduling",
        "summary": "Request to cancel an appointment.",
    },
    "urgent_care": {
        "keywords": ["urgente", "emergencia", "dolor fuerte", "inmediato", "critico", "crítico"],
        "priority": "critical",
        "department": "clinical",
        "summary": "Urgent care or emergency request.",
    },
    "billing_dispute": {
        "keywords": ["factura", "cobro", "cobraron", "seguro", "pago", "reembolso"],
        "priority": "high",
        "department": "billing",
        "summary": "Billing or insurance dispute.",
    },
    "system_outage": {
        "keywords": ["sistema caido", "sistema caído", "no funciona", "error del sistema", "offline"],
        "priority": "critical",
        "department": "it",
        "summary": "System outage or platform failure.",
    },
    "info_request": {
        "keywords": ["consulta", "informacion", "información", "quiero saber", "horario de atencion", "horario de atención"],
        "priority": "low",
        "department": "support",
        "summary": "General information request.",
    },
}


def apply_rules(text: str) -> dict | None:
    t = text.lower()
    best_type, best_score, best_info = None, 0, None
    for incident_type, info in _RULES.items():
        score = sum(1 for kw in info["keywords"] if kw in t)
        if score > best_score:
            best_score, best_type, best_info = score, incident_type, info
    if best_type and best_score >= 1:
        return {
            "incident_type": best_type,
            "priority": best_info["priority"],
            "department": best_info["department"],
            "summary": best_info["summary"],
        }
    return None
