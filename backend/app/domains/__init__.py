"""Dominios de clasificación (presets). Pipeline unificado con reglas intercambiables."""

from app.domains.reviews import apply_rules as reviews_rules, FALLBACK as REVIEWS_FALLBACK
from app.domains.contracts import apply_rules as contracts_rules, FALLBACK as CONTRACTS_FALLBACK
from app.domains.incidents import apply_rules as incidents_rules, FALLBACK as INCIDENTS_FALLBACK

DOMAINS = {
    "reviews": {
        "id": "reviews",
        "label": "Reseñas de apps",
        "description": "Clasifica fallas técnicas y feedback de App Store / Play Store.",
        "rules_fn": reviews_rules,
        "fallback": REVIEWS_FALLBACK,
        "result_keys": ["error_type", "component", "severity", "sentiment", "summary"],
    },
    "contracts": {
        "id": "contracts",
        "label": "Contratos de arrendamiento",
        "description": "Extrae cláusulas, montos, fechas y penalizaciones de textos legales.",
        "rules_fn": contracts_rules,
        "fallback": CONTRACTS_FALLBACK,
        "result_keys": ["clause_type", "amount_hint", "date_hint", "severity", "summary"],
    },
    "incidents": {
        "id": "incidents",
        "label": "Incidencias",
        "description": "Clasifica incidencias operativas / médicas / soporte.",
        "rules_fn": incidents_rules,
        "fallback": INCIDENTS_FALLBACK,
        "result_keys": ["incident_type", "priority", "department", "summary"],
    },
}


def get_domain(domain_id: str) -> dict:
    if domain_id not in DOMAINS:
        return DOMAINS["reviews"]
    return DOMAINS[domain_id]


def list_domains() -> list[dict]:
    return [
        {
            "id": d["id"],
            "label": d["label"],
            "description": d["description"],
            "result_keys": d["result_keys"],
        }
        for d in DOMAINS.values()
    ]
