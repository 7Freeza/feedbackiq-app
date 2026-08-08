/**
 * FeedbackIQ — Nodo "Code" opcional: parsear respuesta de Ollama.
 * Solo en la rama exitosa del HTTP Request a Ollama.
 */

const raw = $input.item.json.response ?? $input.item.json.message?.content ?? "";
let parsed;
try {
  parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
} catch (e) {
  // Si falla el parse, devolvemos un objeto mínimo para no romper el flujo
  parsed = {
    severidad: "media",
    modulo_probable: "Sin clasificar",
    resumen: String(raw).slice(0, 120),
    texto_original: $input.item.json.mensaje || "",
  };
}

return [
  {
    json: {
      severidad: parsed.severidad || "media",
      modulo_probable: parsed.modulo_probable || "Sin clasificar",
      resumen: parsed.resumen || String(parsed.texto_original || "").slice(0, 120),
      texto_original: parsed.texto_original || $input.item.json.mensaje || "",
      // conservar contexto del webhook
      mensaje: $input.item.json.mensaje,
      source: $input.item.json.source,
      timestamp: $input.item.json.timestamp,
      via: "ollama",
    },
  },
];
