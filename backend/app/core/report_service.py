"""Envío de reportes de problema al webhook de n8n."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.core.report_rules import classify_report

logger = logging.getLogger(__name__)


async def submit_problem_report(
    mensaje: str,
    *,
    page: str | None = None,
    user_agent: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Clasifica localmente y reenvía a n8n si está configurado.

    Returns:
        dict con ok, classification, n8n_status, dry_run, message
    """
    settings = get_settings()
    texto = (mensaje or "").strip()
    if len(texto) < 10:
        return {
            "ok": False,
            "error": "El mensaje es demasiado corto (mínimo 10 caracteres).",
        }
    if len(texto) > 4000:
        return {
            "ok": False,
            "error": "El mensaje supera el máximo de 4000 caracteres.",
        }

    reply_email = (email or "").strip().lower() or None

    classification = classify_report(texto)
    payload = {
        "mensaje": texto,
        "source": "feedbackiq-web",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "page": page or "",
        "user_agent": (user_agent or "")[:300],
        # Vacío si el usuario no dejó correo → n8n no envía auto-reply
        "email": reply_email or "",
        # Copia de la clasificación local (n8n puede recalcular igual)
        **classification,
    }

    url = (settings.N8N_WEBHOOK_URL or "").strip()
    if not url:
        if settings.N8N_DRY_RUN:
            logger.info("Report dry-run (no N8N_WEBHOOK_URL): %s", classification)
            return {
                "ok": True,
                "dry_run": True,
                "n8n_status": "skipped",
                "classification": classification,
                "message": "Reporte recibido (modo demo: n8n no configurado).",
            }
        return {
            "ok": False,
            "error": (
                "El canal de reportes no está configurado. "
                "Define N8N_WEBHOOK_URL en backend/.env (ver docs/N8N_REPORTES.md)."
            ),
            "classification": classification,
        }

    headers = {"Content-Type": "application/json"}
    secret = (settings.N8N_WEBHOOK_SECRET or "").strip()
    if secret:
        headers[settings.N8N_WEBHOOK_HEADER_NAME] = secret

    try:
        async with httpx.AsyncClient(timeout=settings.N8N_TIMEOUT_SEC) as client:
            res = await client.post(url, json=payload, headers=headers)
        if res.status_code >= 400:
            logger.warning("n8n webhook HTTP %s: %s", res.status_code, res.text[:300])
            return {
                "ok": False,
                "error": (
                    f"n8n respondió con error HTTP {res.status_code}. "
                    "Revisa que el workflow esté activo y la URL del webhook sea correcta."
                ),
                "classification": classification,
                "n8n_status": res.status_code,
            }
        return {
            "ok": True,
            "dry_run": False,
            "n8n_status": res.status_code,
            "classification": classification,
            "message": "Gracias, lo revisamos.",
        }
    except httpx.TimeoutException:
        logger.exception("n8n timeout")
        return {
            "ok": False,
            "error": "n8n no respondió a tiempo. ¿Está corriendo en :5678?",
            "classification": classification,
            "n8n_status": "timeout",
        }
    except httpx.RequestError as exc:
        logger.exception("n8n request error: %s", exc)
        return {
            "ok": False,
            "error": (
                "No se pudo contactar n8n. Comprueba que Docker/n8n esté en marcha "
                f"({type(exc).__name__})."
            ),
            "classification": classification,
            "n8n_status": "unreachable",
        }
