import { setActiveNav } from '../ui.js';

export function renderDocs(root) {
  setActiveNav('/docs');
  root.innerHTML = `
    <section class="docs block">
      <p class="eyebrow">Método</p>
      <h1 class="page-title">Cómo mide FeedbackIQ</h1>
      <p class="lead">
        Producto de conteo exacto y ahorro de tokens. Sin aproximaciones por caracteres.
      </p>

      <h2>Pipeline núcleo (&lt; 2 s)</h2>
      <ul>
        <li>Ingesta de uno o varios Excel con detección automática de la columna de texto.</li>
        <li>Deduplicación de filas idénticas antes de tokenizar y clasificar.</li>
        <li>Tokenización real con <code class="mono">tiktoken / o200k_base</code>.</li>
        <li>Optimización opcional: traducción neuronal local ES→EN (CTranslate2 + OPUS-MT int8), sin red.</li>
        <li>Deduplicación semántica (model2vec + semhash) antes de traducir.</li>
        <li>El diccionario solo es fallback de emergencia; no se reporta como optimización profesional.</li>
        <li>Clasificación por reglas heurísticas → JSON estructurado.</li>
        <li>Exportación a Excel descargable.</li>
      </ul>

      <h2>Analítica extendida</h2>
      <ul>
        <li>Comparativa de costo entre varios modelos de IA (precios configurables).</li>
        <li>Proyección a volumen diario × 30 días.</li>
        <li>Punto de equilibrio teórico si el preproceso fuera un LLM.</li>
        <li>Desglose de latencia por etapa del pipeline.</li>
      </ul>

      <h2>Transparencia</h2>
      <p>
        Cada fila indica si pasó por optimización y si la clasificación vino de reglas.
        Los supuestos de precio y volumen se muestran y se pueden recalcular en caliente.
      </p>
    </section>
  `;
}
