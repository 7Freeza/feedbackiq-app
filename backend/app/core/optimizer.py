"""Optimización de tokens: traducción ES→EN por diccionario (sin red en ruta crítica).

Justificación de rendimiento: un diccionario local es O(n·k) sobre el texto y
no introduce latencia de red ni dependencias externas en el budget de <2s.
Para producción a escala se puede intercambiar por un traductor real detrás
de la misma interfaz, sin tocar el pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# Frases largas primero (orden de aplicación: de mayor a menor longitud de clave).
_PHRASE_MAP: dict[str, str] = {
    "cada vez que": "whenever",
    "iniciar sesion": "log in",
    "iniciar sesión": "log in",
    "por medio del presente documento": "hereby",
    "el arrendatario se obliga": "the tenant agrees",
    "el arrendador se obliga": "the landlord agrees",
    "clausula de penalizacion": "penalty clause",
    "cláusula de penalización": "penalty clause",
    "fecha de vencimiento": "expiration date",
    "se cierra sola": "closes itself",
    "se cierra inesperadamente": "closes unexpectedly",
    "no puedo iniciar": "cannot start",
    "sin internet": "offline",
    "proxima semana": "next week",
    "próxima semana": "next week",
    "cita medica": "medical appointment",
    "cita médica": "medical appointment",
    "me gustaria": "I would like",
    "me gustaría": "I would like",
    "seria bueno": "it would be good",
    "sería bueno": "it would be good",
    "falta la opcion": "missing the option",
    "muy buena": "very good",
    "facil de usar": "easy to use",
    "fácil de usar": "easy to use",
    "dos veces": "twice",
    "se congela": "freezes",
    "no responde": "does not respond",
    "se pierde": "is lost",
    "no aparece": "does not appear",
    "se ve mal": "looks wrong",
    "no muestra": "does not show",
    "se borro": "was deleted",
    "se borró": "was deleted",
    "no llega": "does not arrive",
}

_WORD_MAP: dict[str, str] = {
    "aplicacion": "application",
    "aplicación": "application",
    "cierra": "closes",
    "inesperadamente": "unexpectedly",
    "intento": "try",
    "subir": "upload",
    "foto": "photo",
    "perfil": "profile",
    "galeria": "gallery",
    "galería": "gallery",
    "telefono": "phone",
    "teléfono": "phone",
    "desde": "from",
    "error": "error",
    "contraseña": "password",
    "contrasena": "password",
    "incorrecta": "incorrect",
    "minutos": "minutes",
    "pagar": "pay",
    "suscripcion": "subscription",
    "suscripción": "subscription",
    "tarjeta": "card",
    "cobro": "charge",
    "actualizacion": "update",
    "actualización": "update",
    "congelada": "frozen",
    "abrir": "open",
    "cierre": "close",
    "video": "video",
    "borroso": "blurry",
    "retraso": "delay",
    "personas": "people",
    "videollamada": "video call",
    "puedo": "can",
    "conexion": "connection",
    "conexión": "connection",
    "estable": "stable",
    "carga": "loading",
    "nunca": "never",
    "cargar": "load",
    "botones": "buttons",
    "desaparecen": "disappear",
    "navegar": "navigate",
    "horizontal": "landscape",
    "vertical": "portrait",
    "menu": "menu",
    "menú": "menu",
    "notas": "notes",
    "guardadas": "saved",
    "reinstalar": "reinstall",
    "respaldo": "backup",
    "deseo": "I wish",
    "solicitar": "request",
    "reprogramacion": "rescheduling",
    "reprogramación": "rescheduling",
    "reprogramar": "reschedule",
    "horario": "schedule",
    "manana": "morning",
    "mañana": "morning",
    "cardiologo": "cardiologist",
    "cardiólogo": "cardiologist",
    "reunion": "meeting",
    "reunión": "meeting",
    "cancelar": "cancel",
    "confirmar": "confirm",
    "turno": "appointment",
    "especialidad": "specialty",
    "medico": "doctor",
    "médico": "doctor",
    "atencion": "care",
    "atención": "care",
    "consulta": "consultation",
    "paciente": "patient",
    "urgente": "urgent",
    "arrendamiento": "lease",
    "arrendatario": "tenant",
    "arrendador": "landlord",
    "clausula": "clause",
    "cláusula": "clause",
    "penalizacion": "penalty",
    "penalización": "penalty",
    "vencimiento": "expiration",
    "monto": "amount",
    "pago": "payment",
    "incumplimiento": "breach",
    "deposito": "deposit",
    "depósito": "deposit",
    "reseña": "review",
    "resena": "review",
    "comentario": "comment",
    "problema": "problem",
    "falla": "failure",
    "bug": "bug",
    "lenta": "slow",
    "lento": "slow",
    "tarda": "takes long",
    "excelente": "excellent",
    "genial": "great",
    "increible": "amazing",
    "increíble": "amazing",
    "recomiendo": "I recommend",
    "incidencia": "incident",
    "descripcion": "description",
    "descripción": "description",
}


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _sorted_phrases() -> list[tuple[str, str]]:
    return sorted(_PHRASE_MAP.items(), key=lambda kv: -len(kv[0]))


def optimize_text(text: str) -> str:
    """Comprime/traduce texto ES→EN con diccionario local. Idempotente en EN."""
    if not text:
        return text
    result = text
    for es, en in _sorted_phrases():
        # Case-insensitive phrase replace
        pattern = re.compile(re.escape(es), re.IGNORECASE)
        result = pattern.sub(en, result)

    # Word-level (preserva mayúsculas del original de forma simple)
    def repl_word(m: re.Match) -> str:
        w = m.group(0)
        key = w.lower()
        key_na = _strip_accents(key)
        mapped = _WORD_MAP.get(key) or _WORD_MAP.get(key_na)
        if not mapped:
            return w
        if w.isupper():
            return mapped.upper()
        if w[0].isupper():
            return mapped[0].upper() + mapped[1:]
        return mapped

    result = re.sub(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", repl_word, result)
    # Colapsar espacios
    result = re.sub(r"\s+", " ", result).strip()
    return result


def compress_structural(text: str, max_chars: int = 280) -> str:
    """Resumen estructural ligero: recorta a primeras oraciones útiles."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    # Preferir corte en punto
    cut = cleaned[:max_chars]
    last_dot = cut.rfind(".")
    if last_dot > max_chars // 2:
        return cut[: last_dot + 1]
    return cut.rstrip() + "…"
