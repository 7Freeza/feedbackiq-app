/**
 * FeedbackIQ — Nodo Code n8n (auto-reply por plantillas, sin IA).
 *
 * Colocar DESPUÉS del nodo de clasificación (Code reglas).
 * Produce:
 *   - email_usuario, tiene_email
 *   - asunto_auto, cuerpo_texto, pasos (array), saludo_severidad
 *   - respuesta_auto (texto plano listo para Gmail texto o base del HTML)
 *
 * Si no hay email → tiene_email=false; el IF de n8n no envía Gmail al usuario.
 */

const results = [];

/** Pasos de mitigación por módulo (playbook de soporte). */
const PLAYBOOK = {
  "Carga/exportación de Excel": [
    "Comprueba que el archivo sea .xlsx o .csv (no .xls antiguo ni PDF renombrado).",
    "Si el archivo es muy grande, prueba con menos filas o divide el Excel en partes.",
    "Vuelve a subir el archivo y espera a que el job termine (no cierres la pestaña a mitad).",
    "Si falla al exportar, recarga la página e intenta de nuevo; el backend guarda el job un tiempo.",
    "Si el error continúa, indícanos el nombre del archivo y si falló al subir o al descargar.",
  ],
  "Traducción de tokens": [
    "Confirma que el backend arrancó con el modelo CTranslate2/OPUS-MT (revisa el log de arranque).",
    "Si el modelo no está cargado, la app puede usar el camino de diccionario (menor calidad).",
    "Reinicia el backend tras cambiar modelos o variables de entorno.",
    "Prueba con un Excel pequeño de 5–10 filas para aislar el fallo.",
  ],
  "Tokenización / conteo": [
    "El conteo usa tiktoken (o200k). Un archivo vacío o sin texto en la columna esperada da 0 tokens.",
    "Revisa que la columna de reseñas/texto no esté vacía o con solo espacios.",
    "Recarga la página y vuelve a procesar el mismo archivo.",
  ],
  "Optimización de tokens": [
    "Desactiva y vuelve a activar la optimización para forzar un recálculo limpio.",
    "Prueba sin optimización: si el flujo base funciona, el fallo está en el paso de optimización.",
    "Archivos con mucho ruido (HTML, URLs) a veces reducen menos tokens de lo esperado; es normal.",
  ],
  "Interfaz (botones)": [
    "Haz un refresco forzado (Ctrl+Shift+R / Cmd+Shift+R) por si el navegador cacheó JS antiguo.",
    "Prueba en una ventana de incógnito para descartar extensiones.",
    "Indica qué botón exacto y en qué página (#/, analítica, etc.).",
  ],
  "Interfaz (UI)": [
    "Prueba otro navegador o una ventana de incógnito.",
    "Revisa el zoom del navegador (100%) y el ancho de la ventana.",
    "Si es un detalle visual, lo registramos como mejora de UX (prioridad baja).",
  ],
  "Analítica / gráficas": [
    "La analítica necesita un proceso completado con tokens originales y optimizados.",
    "Sube y procesa un archivo primero; luego abre la vista de analítica.",
    "Si los números no cambian, usa «recalcular» o vuelve a procesar el dataset.",
  ],
  "Rendimiento del backend": [
    "La primera carga del modelo de traducción puede tardar varios minutos.",
    "Evita enviar varios Excel grandes a la vez; procesa de uno en uno.",
    "Si hay timeout, reduce filas o reinicia el backend y vuelve a intentar.",
  ],
  "Automatización de reportes": [
    "El canal de reportes depende de n8n activo y del webhook configurado en el backend.",
    "Sin N8N_WEBHOOK_URL el formulario puede quedar en modo demo (dry-run).",
    "Si no recibes este correo, revisa spam y que el workflow n8n esté Published/Active.",
  ],
  "Clasificación por dominio": [
    "Revisa que el dominio/tipo de reseña esté soportado en la configuración de la app.",
    "Prueba con un dominio conocido (p. ej. el de la demo) y compara el resultado.",
  ],
  "Clasificación de reseñas": [
    "Comprueba que la columna de texto de reseñas no esté vacía.",
    "Algunas reseñas muy cortas o solo emojis se clasifican con menor confianza.",
  ],
  "IA local / Ollama": [
    "Ollama es opcional en el pipeline de reportes; la clasificación principal usa reglas.",
    "Si activaste IA local, confirma que Ollama escucha en el puerto configurado.",
  ],
  "IA externa / Gemini": [
    "Las integraciones externas requieren API key y red; en demo preferimos reglas locales.",
    "Si falló una llamada externa, el flujo de reportes sigue con clasificación por reglas.",
  ],
  "Sin clasificar": [
    "Describe el paso exacto donde falla (subir, procesar, exportar, analítica…).",
    "Si puedes, adjunta o copia el mensaje de error de la pantalla.",
    "Indica navegador y si ocurre siempre o solo con un archivo concreto.",
  ],
};

const PASOS_GENERICOS = [
  "Recarga la página e intenta de nuevo el mismo flujo.",
  "Prueba con un archivo o acción más simple para aislar el fallo.",
  "Si el problema es bloqueante, responde a este correo con más detalle o un pantallazo.",
];

function pasosPara(modulo) {
  const key = String(modulo || "").trim();
  if (PLAYBOOK[key]) return PLAYBOOK[key].slice();
  // Coincidencia parcial por si cambia el nombre
  for (const [k, pasos] of Object.entries(PLAYBOOK)) {
    if (key && (k.includes(key) || key.includes(k))) return pasos.slice();
  }
  return PASOS_GENERICOS.slice();
}

function introPorSeveridad(sev) {
  const s = String(sev || "media").toLowerCase();
  if (s === "critica") {
    return (
      "Registramos tu reporte con prioridad alta. Mientras el equipo lo revisa, " +
      "puedes probar estos pasos de mitigación:"
    );
  }
  if (s === "baja") {
    return (
      "Gracias por la sugerencia o el detalle. Lo tenemos anotado. " +
      "Si te sirve de ayuda, aquí van algunas orientaciones relacionadas:"
    );
  }
  return (
    "Recibimos tu reporte. Mientras lo revisamos, prueba estos pasos de solución:"
  );
}

function cierrePorSeveridad(sev) {
  const s = String(sev || "media").toLowerCase();
  if (s === "critica") {
    return "Si sigue fallando tras estos pasos, no hace falta reintentar muchas veces: el equipo ya tiene el ticket.";
  }
  if (s === "baja") {
    return "No es un fallo crítico; lo priorizamos según impacto. Gracias por ayudarnos a mejorar FeedbackIQ.";
  }
  return "Si con estos pasos se resolvió, no necesitas hacer nada más. Si no, responde con el resultado.";
}

for (const it of $input.all()) {
  const item = it.json;
  const email = String(item.email || "").trim().toLowerCase();
  const tiene_email = Boolean(email && email.includes("@"));

  const severidad = String(item.severidad || "media");
  const modulo = String(item.modulo_probable || "Sin clasificar");
  const mensaje = String(item.texto_original || item.mensaje || "").trim();
  const resumen = String(item.resumen || mensaje.slice(0, 100));

  const pasos = pasosPara(modulo);
  const intro = introPorSeveridad(severidad);
  const cierre = cierrePorSeveridad(severidad);

  const pasosNumerados = pasos.map((p, i) => `${i + 1}. ${p}`).join("\n");

  const cuerpo_texto = [
    "Hola,",
    "",
    intro,
    "",
    `Módulo detectado: ${modulo}`,
    `Severidad: ${severidad}`,
    "",
    "Tu mensaje:",
    mensaje || "—",
    "",
    "Pasos sugeridos:",
    pasosNumerados,
    "",
    cierre,
    "",
    "— Equipo FeedbackIQ",
    "(Respuesta automática por plantillas; clasificación por reglas, sin IA generativa.)",
  ].join("\n");

  const asunto_auto = `[FeedbackIQ] Guía de solución · ${modulo}`;

  results.push({
    json: {
      ...item,
      email_usuario: email,
      tiene_email,
      asunto_auto,
      cuerpo_texto,
      pasos,
      intro_auto: intro,
      cierre_auto: cierre,
      respuesta_auto: cuerpo_texto,
      // Para Sheets / tracking
      auto_reply_estado: tiene_email ? "pendiente_envio" : "sin_email",
    },
  });
}

return results;
