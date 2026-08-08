"""Clasificación local de reportes de problema (reglas, sin IA).

Misma lógica que docs/n8n/code-clasificacion.js — mantener ambos alineados.
"""

from __future__ import annotations

from typing import Any

# Orden importa: se evalúa crítica antes que baja.
CLAVES_CRITICAS = [
    "no carga",
    "no funciona",
    "no sirve",
    "se cae",
    "se cierra",
    "se cerro",
    "se cerró",
    "se cierra sola",
    "cierra sola",
    "de golpe",
    "crash",
    "crashea",
    "error 500",
    "error 502",
    "error 503",
    "no responde",
    "pantalla en blanco",
    "pantalla blanca",
    "no abre",
    "no arranca",
    "perdi",
    "perdí",
    "se borro",
    "se borró",
    "se congela",
    "congelad",
    "timeout",
    "time out",
    "corrupto",
    "no exporta",
    "no descarga",
    "falla total",
    "imposible",
    "urgente",
    "roto",
    "rompe",
    "exception",
    "traceback",
    "500 internal",
]

CLAVES_BAJAS = [
    "sugerencia",
    "seria bueno",
    "sería bueno",
    "estaria bien",
    "estaría bien",
    "detalle",
    "color",
    "estetica",
    "estética",
    "tipografia",
    "tipografía",
    "podria mejorar",
    "podría mejorar",
    "me gustaria",
    "me gustaría",
    "nice to have",
    "opcional",
    "cosmetico",
    "cosmético",
    "ux",
    "ui menor",
]

# (substring en minúsculas, nombre del módulo) — primera coincidencia gana
MODULOS: list[tuple[str, str]] = [
    # Excel / archivos
    ("excel", "Carga/exportación de Excel"),
    ("xlsx", "Carga/exportación de Excel"),
    ("xls", "Carga/exportación de Excel"),
    ("csv", "Carga/exportación de Excel"),
    ("subir archivo", "Carga/exportación de Excel"),
    ("subir el", "Carga/exportación de Excel"),
    ("subir", "Carga/exportación de Excel"),
    ("export", "Carga/exportación de Excel"),
    ("descarg", "Carga/exportación de Excel"),
    ("hoja de calculo", "Carga/exportación de Excel"),
    ("hoja de cálculo", "Carga/exportación de Excel"),
    ("openpyxl", "Carga/exportación de Excel"),
    # Tokens / traducción
    ("traduc", "Traducción de tokens"),
    ("ctranslate", "Traducción de tokens"),
    ("opus", "Traducción de tokens"),
    ("token", "Tokenización / conteo"),
    ("o200k", "Tokenización / conteo"),
    ("tiktoken", "Tokenización / conteo"),
    ("optimiz", "Optimización de tokens"),
    ("ahorro", "Analítica / ahorro"),
    # UI
    ("boton", "Interfaz (botones)"),
    ("botón", "Interfaz (botones)"),
    ("toggle", "Interfaz (UI)"),
    ("interfaz", "Interfaz (UI)"),
    ("pantalla", "Interfaz (UI)"),
    ("footer", "Interfaz (UI)"),
    ("navbar", "Interfaz (UI)"),
    ("menu", "Interfaz (UI)"),
    ("menú", "Interfaz (UI)"),
    ("grafic", "Analítica / gráficas"),
    ("chart", "Analítica / gráficas"),
    ("dashboard", "Analítica / gráficas"),
    ("kpi", "Analítica / gráficas"),
    # Rendimiento
    ("tarda", "Rendimiento del backend"),
    ("lento", "Rendimiento del backend"),
    ("demora", "Rendimiento del backend"),
    ("timeout", "Rendimiento del backend"),
    ("colg", "Rendimiento del backend"),
    ("freeze", "Rendimiento del backend"),
    ("memoria", "Rendimiento del backend"),
    ("cpu", "Rendimiento del backend"),
    # Automatización / reportes
    ("correo", "Automatización de reportes"),
    ("email", "Automatización de reportes"),
    ("gmail", "Automatización de reportes"),
    ("telegram", "Automatización de reportes"),
    ("n8n", "Automatización de reportes"),
    ("webhook", "Automatización de reportes"),
    ("reporte", "Automatización de reportes"),
    # Dominio / clasificación de reseñas
    ("dominio", "Clasificación por dominio"),
    ("reseña", "Clasificación de reseñas"),
    ("resena", "Clasificación de reseñas"),
    ("review", "Clasificación de reseñas"),
    ("incidenc", "Clasificación de incidencias"),
    ("contrato", "Clasificación de contratos"),
    # Auth / login futuro
    ("login", "Autenticación"),
    ("sesion", "Autenticación"),
    ("sesión", "Autenticación"),
    ("password", "Autenticación"),
    ("contraseña", "Autenticación"),
    # IA local
    ("ollama", "IA local / Ollama"),
    ("gemini", "IA externa / Gemini"),
    ("llm", "IA / modelos"),
]


def classify_report(mensaje: str) -> dict[str, Any]:
    texto = (mensaje or "").strip()
    lower = texto.lower()

    severidad = "media"
    if any(p in lower for p in CLAVES_CRITICAS):
        severidad = "critica"
    elif any(p in lower for p in CLAVES_BAJAS):
        severidad = "baja"

    modulo_probable = "Sin clasificar"
    for clave, nombre in MODULOS:
        if clave in lower:
            modulo_probable = nombre
            break

    # Resumen corto: primera oración o 100 chars (no duplicar lógica de UI)
    resumen = texto
    for sep in (". ", "。", "\n"):
        if sep in texto:
            resumen = texto.split(sep)[0].strip()
            if len(resumen) >= 12:
                break
    if len(resumen) > 100:
        resumen = resumen[:97].rstrip() + "…"

    return {
        "severidad": severidad,
        "modulo_probable": modulo_probable,
        "resumen": resumen,
        "texto_original": texto,
    }
