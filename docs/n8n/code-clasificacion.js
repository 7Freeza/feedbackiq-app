/**
 * FeedbackIQ — Nodo Code n8n (clasificación por reglas).
 * Alineado con backend/app/core/report_rules.py
 *
 * Soporta: body.mensaje (webhook n8n) y mensaje (backend FeedbackIQ).
 */

const results = [];

for (const it of $input.all()) {
  const item = it.json;
  const mensaje = String(
    item.mensaje ||
      item.texto_original ||
      (item.body && item.body.mensaje) ||
      (item.body && item.body.texto_original) ||
      ""
  ).trim();

  const texto = mensaje.toLowerCase();

  const clavesCriticas = [
    "no carga", "no funciona", "no sirve", "se cae", "se cierra", "se cerro",
    "se cerró", "se cierra sola", "cierra sola", "de golpe", "crash", "crashea",
    "error 500", "error 502", "error 503", "no responde", "pantalla en blanco",
    "pantalla blanca", "no abre", "no arranca", "perdi", "perdí", "se borro",
    "se borró", "se congela", "congelad", "timeout", "time out", "corrupto",
    "no exporta", "no descarga", "falla total", "imposible", "urgente", "roto",
    "rompe", "exception", "traceback",
  ];

  const clavesBajas = [
    "sugerencia", "seria bueno", "sería bueno", "estaria bien", "estaría bien",
    "detalle", "color", "estetica", "estética", "tipografia", "tipografía",
    "podria mejorar", "podría mejorar", "me gustaria", "me gustaría",
    "nice to have", "opcional", "cosmetico", "cosmético", "ux", "ui menor",
  ];

  let severidad = "media";
  if (mensaje && clavesCriticas.some((p) => texto.includes(p))) severidad = "critica";
  else if (mensaje && clavesBajas.some((p) => texto.includes(p))) severidad = "baja";

  const modulos = [
    ["excel", "Carga/exportación de Excel"],
    ["xlsx", "Carga/exportación de Excel"],
    ["xls", "Carga/exportación de Excel"],
    ["csv", "Carga/exportación de Excel"],
    ["subir archivo", "Carga/exportación de Excel"],
    ["subir el", "Carga/exportación de Excel"],
    ["subir", "Carga/exportación de Excel"],
    ["export", "Carga/exportación de Excel"],
    ["descarg", "Carga/exportación de Excel"],
    ["hoja de calculo", "Carga/exportación de Excel"],
    ["hoja de cálculo", "Carga/exportación de Excel"],
    ["traduc", "Traducción de tokens"],
    ["ctranslate", "Traducción de tokens"],
    ["token", "Tokenización / conteo"],
    ["optimiz", "Optimización de tokens"],
    ["boton", "Interfaz (botones)"],
    ["botón", "Interfaz (botones)"],
    ["toggle", "Interfaz (UI)"],
    ["interfaz", "Interfaz (UI)"],
    ["footer", "Interfaz (UI)"],
    ["grafic", "Analítica / gráficas"],
    ["chart", "Analítica / gráficas"],
    ["tarda", "Rendimiento del backend"],
    ["lento", "Rendimiento del backend"],
    ["demora", "Rendimiento del backend"],
    ["timeout", "Rendimiento del backend"],
    ["correo", "Automatización de reportes"],
    ["email", "Automatización de reportes"],
    ["gmail", "Automatización de reportes"],
    ["n8n", "Automatización de reportes"],
    ["webhook", "Automatización de reportes"],
    ["dominio", "Clasificación por dominio"],
    ["reseña", "Clasificación de reseñas"],
    ["resena", "Clasificación de reseñas"],
    ["review", "Clasificación de reseñas"],
    ["ollama", "IA local / Ollama"],
    ["gemini", "IA externa / Gemini"],
  ];

  let modulo_probable = "Sin clasificar";
  for (const [clave, nombre] of modulos) {
    if (texto.includes(clave)) {
      modulo_probable = nombre;
      break;
    }
  }

  let resumen = mensaje;
  const dot = mensaje.indexOf(". ");
  if (dot > 12) resumen = mensaje.slice(0, dot).trim();
  if (resumen.length > 100) resumen = resumen.slice(0, 97).trim() + "…";

  const email = String(
    item.email ||
      (item.body && item.body.email) ||
      ""
  ).trim().toLowerCase();

  results.push({
    json: {
      mensaje,
      severidad,
      modulo_probable,
      resumen,
      texto_original: mensaje,
      email,
      source: item.source || (item.body && item.body.source) || "webhook",
      timestamp: item.timestamp || (item.body && item.body.timestamp) || new Date().toISOString(),
      page: item.page || (item.body && item.body.page) || "",
    },
  });
}

return results;
