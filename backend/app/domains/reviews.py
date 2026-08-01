"""Reglas heurísticas para reseñas de aplicaciones (sin costo de IA)."""

from __future__ import annotations

FALLBACK = {
    "error_type": "other",
    "component": "general",
    "severity": "low",
    "sentiment": "neutral",
    "summary": "Unclassified feedback item.",
}

_RULES: dict[str, dict] = {
    "crash": {
        "keywords": ["se cierra", "crash", "se detiene", "sale de la app", "se cayo", "se cayó", "se cierra sola"],
        "severity": "high",
        "sentiment": "negative",
        "component": "app_core",
        "summary": "App crashes unexpectedly during use.",
    },
    "freeze": {
        "keywords": ["se congela", "no responde", "se queda", "congelada", "frozen"],
        "severity": "high",
        "sentiment": "negative",
        "component": "app_core",
        "summary": "App freezes and stops responding.",
    },
    "login_error": {
        "keywords": ["no puedo iniciar", "iniciar sesion", "iniciar sesión", "contrasena", "contraseña", "password", "login", "autenticacion", "autenticación", "credenciales"],
        "severity": "critical",
        "sentiment": "negative",
        "component": "authentication",
        "summary": "User cannot sign in due to authentication failure.",
    },
    "payment_error": {
        "keywords": ["pago", "cobro", "tarjeta", "suscripcion", "suscripción", "factura", "cobraron", "reembolso"],
        "severity": "critical",
        "sentiment": "negative",
        "component": "billing",
        "summary": "Payment or billing issue reported.",
    },
    "network_error": {
        "keywords": ["conexion", "conexión", "sin internet", "red", "servidor", "se pierde", "timeout", "offline"],
        "severity": "high",
        "sentiment": "negative",
        "component": "network",
        "summary": "Network or server connectivity failure.",
    },
    "ui_bug": {
        "keywords": ["boton", "botón", "menu", "menú", "interfaz", "no aparece", "desaparece", "se ve mal", "no muestra"],
        "severity": "medium",
        "sentiment": "negative",
        "component": "ui",
        "summary": "UI element behaves incorrectly or disappears.",
    },
    "performance_issue": {
        "keywords": ["lenta", "tarda", "lento", "borroso", "retraso", "pesada", "demora"],
        "severity": "medium",
        "sentiment": "negative",
        "component": "performance",
        "summary": "App performance is slow or degraded.",
    },
    "data_loss": {
        "keywords": ["se borro", "se borró", "perdi", "perdí", "datos", "informacion", "información", "notas", "desaparecieron"],
        "severity": "critical",
        "sentiment": "negative",
        "component": "data",
        "summary": "User data was lost or disappeared.",
    },
    "battery_drain": {
        "keywords": ["bateria", "batería", "drena", "consume", "duracion", "duración"],
        "severity": "high",
        "sentiment": "negative",
        "component": "power",
        "summary": "App drains battery excessively.",
    },
    "notification_bug": {
        "keywords": ["notificacion", "notificación", "no llega", "aviso", "alerta"],
        "severity": "medium",
        "sentiment": "negative",
        "component": "notifications",
        "summary": "Notifications are not delivered correctly.",
    },
    "feature_request": {
        "keywords": ["me gustaria", "me gustaría", "podrian", "podrían", "seria bueno", "sería bueno", "falta la opcion", "agregar", "necesito", "deberia tener", "debería tener"],
        "severity": "low",
        "sentiment": "neutral",
        "component": "features",
        "summary": "User requests a new feature or improvement.",
    },
    "positive_feedback": {
        "keywords": ["excelente", "muy buena", "genial", "increible", "increíble", "recomiendo", "me encanta", "perfecta", "facil de usar", "fácil de usar", "supero mis expectativas"],
        "severity": "low",
        "sentiment": "positive",
        "component": "general",
        "summary": "User expresses satisfaction with the app.",
    },
}


def apply_rules(text: str) -> dict | None:
    t = text.lower()
    best_type, best_score, best_info = None, 0, None
    for error_type, info in _RULES.items():
        score = sum(1 for kw in info["keywords"] if kw in t)
        if score > best_score:
            best_score, best_type, best_info = score, error_type, info
    if best_type and best_score >= 1:
        return {
            "error_type": best_type,
            "component": best_info["component"],
            "severity": best_info["severity"],
            "sentiment": best_info["sentiment"],
            "summary": best_info["summary"],
        }
    return None
