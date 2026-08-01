import * as api from '../api.js';
import { destroyCharts, renderModelCostChart, renderProjectionChart, renderStageChart, renderTypeChart } from '../charts.js';
import {
  animateNumber,
  esc,
  formatInt,
  formatMs,
  formatUsd,
  setActiveNav,
} from '../ui.js';

/** @type {{ files: File[], lastResult: any }} */
const state = {
  files: [],
  lastResult: null,
  busy: false,
};

export function renderAnalyze(root) {
  setActiveNav('/');
  destroyCharts();

  root.innerHTML = `
    <section class="block block--tight">
      <p class="eyebrow">Analizar</p>
      <h1 class="page-title">Tokens reales. Ahorro medible.</h1>
      <p class="lead">
        Sube un Excel o un lote. En menos de dos segundos: conteo o200k_base,
        clasificación estructurada y archivo de salida listo para descargar.
      </p>
    </section>

    <section class="block">
      <div class="drop" id="drop" tabindex="0" role="button" aria-label="Zona de carga de Excel">
        <p class="drop__title">Suelta .xlsx aquí</p>
        <p class="drop__hint">Un archivo o varios a la vez · detección automática de columna de texto</p>
        <p class="drop__meta" id="drop-meta" hidden></p>
        <input type="file" id="file-input" accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple />
      </div>

      <div class="controls">
        <div class="field">
          <label for="domain">Dominio</label>
          <select id="domain">
            <option value="reviews">Reseñas de apps</option>
            <option value="contracts">Contratos de arrendamiento</option>
            <option value="incidents">Incidencias</option>
          </select>
        </div>
        <div class="field">
          <label for="price">USD / millón de tokens</label>
          <input type="number" id="price" min="0.01" step="0.01" value="2.50" />
        </div>
        <div class="field">
          <label for="volume">Volumen diario (proyección)</label>
          <input type="number" id="volume" min="1" step="100" value="10000" />
        </div>
        <div class="field">
          <label>Optimización de tokens</label>
          <label class="toggle">
            <input type="checkbox" id="optimize" checked />
            <span class="toggle__track" aria-hidden="true"></span>
            <span class="toggle__text">
              <span class="toggle__label">Activada</span>
              <span class="toggle__sub">Traducción / compresión previa</span>
            </span>
          </label>
        </div>
      </div>

      <div class="actions">
        <button type="button" class="btn" id="run-btn" disabled>Procesar</button>
        <p class="state state--info" id="status"></p>
      </div>
    </section>

    <div id="processing" hidden></div>
    <div id="core-out" hidden></div>
    <div id="analytics-out" hidden></div>
    <div id="preview-out" hidden></div>
  `;

  bind(root);
  restoreIfAny(root);
}

function bind(root) {
  const drop = root.querySelector('#drop');
  const input = root.querySelector('#file-input');
  const meta = root.querySelector('#drop-meta');
  const runBtn = root.querySelector('#run-btn');
  const optimize = root.querySelector('#optimize');
  const status = root.querySelector('#status');

  function setFiles(fileList) {
    const arr = Array.from(fileList || []).filter((f) =>
      /\.xlsx?$/i.test(f.name)
    );
    state.files = arr;
    runBtn.disabled = arr.length === 0 || state.busy;
    if (arr.length) {
      meta.hidden = false;
      const size = arr.reduce((s, f) => s + f.size, 0);
      meta.textContent =
        arr.length === 1
          ? `${arr[0].name} · ${(size / 1024).toFixed(1)} KB`
          : `${arr.length} archivos · ${(size / 1024).toFixed(1)} KB`;
      status.textContent = '';
      status.className = 'state state--info';
    } else {
      meta.hidden = true;
      meta.textContent = '';
    }
  }

  input.addEventListener('change', () => setFiles(input.files));

  drop.addEventListener('dragover', (e) => {
    e.preventDefault();
    drop.classList.add('is-drag');
  });
  drop.addEventListener('dragleave', () => drop.classList.remove('is-drag'));
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.classList.remove('is-drag');
    setFiles(e.dataTransfer.files);
  });
  drop.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      input.click();
    }
  });

  optimize.addEventListener('change', () => {
    const sub = optimize.closest('.toggle')?.querySelector('.toggle__label');
    if (sub) sub.textContent = optimize.checked ? 'Activada' : 'Desactivada';
  });

  runBtn.addEventListener('click', () => runAnalysis(root));
}

async function runAnalysis(root) {
  if (!state.files.length || state.busy) return;

  const runBtn = root.querySelector('#run-btn');
  const status = root.querySelector('#status');
  const processing = root.querySelector('#processing');
  const coreOut = root.querySelector('#core-out');
  const analyticsOut = root.querySelector('#analytics-out');
  const previewOut = root.querySelector('#preview-out');

  state.busy = true;
  runBtn.disabled = true;
  status.textContent = '';
  coreOut.hidden = true;
  analyticsOut.hidden = true;
  previewOut.hidden = true;
  destroyCharts();

  // Skeleton inmediato
  processing.hidden = false;
  processing.innerHTML = `
    <div class="skeleton" aria-live="polite" aria-busy="true">
      <div class="sk sk--hero"></div>
      <div class="sk sk--line"></div>
      <div class="sk sk--wide"></div>
      <p class="progress" id="proc-msg">Procesando <strong>${state.files.length}</strong> archivo${state.files.length > 1 ? 's' : ''}…</p>
    </div>
  `;

  const opts = {
    optimize_tokens: root.querySelector('#optimize').checked,
    domain: root.querySelector('#domain').value,
    price_per_million: Number(root.querySelector('#price').value) || 2.5,
    daily_volume: Number(root.querySelector('#volume').value) || 10000,
  };

  try {
    const result = await api.analyze(state.files, opts, {
      onAsync: (info) => {
        const el = root.querySelector('#proc-msg');
        if (el) {
          el.innerHTML = `Archivo grande (~${formatInt(info.rows_estimate || 0)} filas). Trabajo <strong>${esc(info.job_id)}</strong> en segundo plano…`;
        }
      },
    });
    state.lastResult = result;
    processing.hidden = true;
    renderCore(coreOut, result);
    // Progressive disclosure: núcleo primero, analytics después del paint
    requestAnimationFrame(() => {
      renderAnalytics(analyticsOut, result);
      renderPreview(previewOut, result);
    });
  } catch (err) {
    processing.hidden = true;
    status.className = 'state state--error';
    status.textContent = err.message || 'Error al procesar';
  } finally {
    state.busy = false;
    runBtn.disabled = state.files.length === 0;
  }
}

function renderCore(el, result) {
  const c = result.core;
  el.hidden = false;

  const heroTokens = c.optimize_tokens ? c.savings_tokens : c.tokens_original;
  const heroLabel = c.optimize_tokens
    ? 'tokens ahorrados en este lote'
    : 'tokens del lote (optimización off)';

  el.innerHTML = `
    <section class="core block" aria-live="polite">
      <p class="eyebrow">Resultado núcleo</p>
      <div class="core__hero">
        <div class="core__hero-value" id="hero-num">0</div>
        <p class="core__hero-label">${heroLabel}</p>
      </div>

      <div class="kpi-grid">
        <div class="kpi">
          <p class="kpi__label">Tokens originales</p>
          <p class="kpi__value kpi__value--ink" id="kpi-orig">0</p>
        </div>
        <div class="kpi">
          <p class="kpi__label">${c.optimize_tokens ? 'Tokens optimizados' : 'Tokens si optimizas'}</p>
          <p class="kpi__value kpi__value--mint" id="kpi-opt">0</p>
          ${!c.optimize_tokens ? `<p class="kpi__sub">estimación · ${formatInt(c.tokens_optimized_estimate)}</p>` : ''}
        </div>
        <div class="kpi">
          <p class="kpi__label">Tiempo de proceso</p>
          <p class="kpi__value kpi__value--ink" id="kpi-ms">0</p>
          <p class="kpi__sub">SLA &lt; 2000 ms</p>
        </div>
        <div class="kpi">
          <p class="kpi__label">Costo ref. ahorrado</p>
          <p class="kpi__value kpi__value--mint" id="kpi-cost">$0</p>
          <p class="kpi__sub">@ $${Number(c.price_per_million).toFixed(2)} / MTok</p>
        </div>
      </div>

      <p class="sla">
        Latencia núcleo
        <strong class="${c.within_sla ? '' : 'is-over'}" id="sla-val">${formatMs(c.elapsed_ms)}</strong>
        · ${c.item_count} filas · ${c.unique_count} únicas · dominio ${esc(c.domain)}
      </p>

      <div class="actions">
        <a class="btn" href="${api.downloadUrl(c.export_filename)}" download>Descargar Excel</a>
        <span class="state state--info">
          Clasificación: reglas · optimización ${c.optimize_tokens ? 'ON' : 'OFF'}
          ${c.optimize_method_label ? ` · ${esc(c.optimize_method_label)}` : ''}
        </span>
      </div>

      ${renderFileList(result.files, result.errors)}
    </section>
  `;

  animateNumber(el.querySelector('#hero-num'), heroTokens, { duration: 800 });
  animateNumber(el.querySelector('#kpi-orig'), c.tokens_original, { duration: 650 });
  animateNumber(
    el.querySelector('#kpi-opt'),
    c.optimize_tokens ? c.tokens_optimized : c.tokens_optimized_estimate,
    { duration: 650 }
  );
  animateNumber(el.querySelector('#kpi-ms'), c.elapsed_ms, {
    duration: 500,
    formatter: (v) => formatMs(v),
  });
  animateNumber(el.querySelector('#kpi-cost'), c.cost_savings_usd || 0, {
    duration: 700,
    formatter: (v) => formatUsd(v, 6),
  });
}

function renderComparisons(comp) {
  if (!comp || !comp.b_ctranslate2) return '';
  const a = comp.a_dictionary || {};
  const b = comp.b_ctranslate2 || {};
  const c = comp.c_semantic_dedup || {};
  return `
    <div class="block" style="margin-bottom: var(--space-xl)">
      <h3 class="chart-block" style="margin-bottom: var(--space-md)">
        <span style="font-size:var(--fs-sm);letter-spacing:0.08em;text-transform:uppercase;color:var(--mute)">
          Comparativa de optimización (mismo lote)
        </span>
      </h3>
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr>
              <th>Escenario</th>
              <th>Método</th>
              <th>Tokens</th>
              <th>Ahorro vs original</th>
              <th>Nota</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>(a) Diccionario</td>
              <td>${esc(a.method || 'dictionary')}</td>
              <td>${formatInt(a.tokens)}</td>
              <td class="neg">${a.savings_pct != null ? a.savings_pct + '%' : '—'} <span style="color:var(--mute)">solo referencia</span></td>
              <td style="font-family:var(--font-ui);color:var(--mute);max-width:16rem">${esc(a.note || '')}</td>
            </tr>
            <tr>
              <td>(b) Neuronal local ★</td>
              <td>${esc(b.method || 'ctranslate2')}</td>
              <td>${b.tokens != null ? formatInt(b.tokens) : '—'}</td>
              <td class="pos">${b.savings_pct != null ? b.savings_pct + '%' : '—'} <span style="color:var(--mute)">reportado</span></td>
              <td style="font-family:var(--font-ui);color:var(--mute);max-width:16rem">${esc(b.note || '')}</td>
            </tr>
            <tr>
              <td>(c) Dedup semántica</td>
              <td>${esc(c.method || '—')}</td>
              <td>${formatInt(c.tokens_canonical_translated ?? c.tokens_canonical_original)}</td>
              <td class="pos">${c.volume_reduction_pct != null ? c.volume_reduction_pct + '% vol.' : '—'}</td>
              <td style="font-family:var(--font-ui);color:var(--mute);max-width:16rem">
                ${formatInt(c.items_before)} → ${formatInt(c.items_after)} ítems · ${esc(c.note || '')}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="state state--info" style="margin-top:1rem">
        El ahorro reportado al cliente usa solo (b) traducción neuronal. (a) no se presenta como optimización profesional.
      </p>
    </div>
  `;
}

function renderFileList(files, errors) {
  if (!files?.length) return '';
  const items = files
    .map((f) => {
      if (f.error) {
        return `<li class="is-err">${esc(f.filename)} — ${esc(f.error)}</li>`;
      }
      return `<li><span>${esc(f.filename)}</span> · ${f.rows} filas · col. ${esc(f.column || '—')}</li>`;
    })
    .join('');
  const errNote =
    errors?.length > 0
      ? `<p class="state state--error" style="margin-top:1rem">${errors.length} archivo(s) con aviso; el resto se procesó.</p>`
      : '';
  return `<ul class="file-list">${items}</ul>${errNote}`;
}

function renderAnalytics(el, result) {
  const a = result.analytics;
  if (!a) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const c = result.core;
  const be = a.break_even;
  const proj = a.projection;

  el.innerHTML = `
    <section class="analytics" id="analytics-panel">
      <div class="analytics__head">
        <p class="eyebrow">Analítica extendida</p>
        <h2>Impacto económico y comparativas</h2>
        <p class="analytics__assumptions" id="assumptions">
          Supuestos: <code>$${Number(a.assumptions.price_per_million_usd).toFixed(2)}</code> USD / millón ·
          volumen diario <code>${formatInt(a.assumptions.daily_volume)}</code> ·
          tokenizer <code>${a.assumptions.tokenizer}</code>
          ${c.optimize_method_label ? ` · motor <code>${esc(c.optimize_method || 'none')}</code>` : ''}
        </p>
      </div>

      ${renderComparisons(result.comparisons || a.comparisons)}

      <div class="recalc">
        <div class="field">
          <label for="re-price">Recalcular precio / MTok</label>
          <input type="number" id="re-price" min="0.01" step="0.01" value="${a.assumptions.price_per_million_usd}" />
        </div>
        <div class="field">
          <label for="re-vol">Volumen diario</label>
          <input type="number" id="re-vol" min="1" step="100" value="${a.assumptions.daily_volume}" />
        </div>
        <div class="field">
          <label>&nbsp;</label>
          <button type="button" class="btn btn--ghost" id="recalc-btn">Actualizar proyecciones</button>
        </div>
      </div>

      <div class="kpi-grid" id="proj-kpis">
        <div class="kpi">
          <p class="kpi__label">Ahorro mensual est.</p>
          <p class="kpi__value kpi__value--mint mono" id="proj-month">${formatUsd(proj.savings_usd_month, 2)}</p>
          <p class="kpi__sub">${formatInt(proj.savings_tokens_month)} tokens / mes</p>
        </div>
        <div class="kpi">
          <p class="kpi__label">Ahorro diario est.</p>
          <p class="kpi__value kpi__value--ink mono" id="proj-day">${formatUsd(proj.savings_usd_day, 4)}</p>
        </div>
        <div class="kpi">
          <p class="kpi__label">Punto de equilibrio</p>
          <p class="kpi__value kpi__value--amber mono" id="be-items">${be.items != null ? formatInt(be.items) : '—'}</p>
          <p class="kpi__sub">ítems (modelo LLM de preproceso)</p>
        </div>
        <div class="kpi">
          <p class="kpi__label">Break-even tokens/ítem</p>
          <p class="kpi__value kpi__value--ink mono" id="be-tok">${be.tokens_per_item != null ? formatInt(be.tokens_per_item) : '—'}</p>
        </div>
      </div>

      <p class="state state--info" style="margin-top:1.5rem" id="be-note">${esc(be.recommendation)}</p>

      <div class="chart-grid">
        <div class="chart-block">
          <h3>Costo por modelo (lote actual)</h3>
          <div class="chart-wrap"><canvas id="chart-models"></canvas></div>
        </div>
        <div class="chart-block">
          <h3>Proyección de ahorro 30 días</h3>
          <div class="chart-wrap chart-wrap--wide"><canvas id="chart-proj"></canvas></div>
        </div>
        <div class="chart-block">
          <h3>Latencia por etapa</h3>
          <div class="chart-wrap"><canvas id="chart-stages"></canvas></div>
        </div>
        <div class="chart-block">
          <h3>Distribución de tipos</h3>
          <div class="chart-wrap"><canvas id="chart-types"></canvas></div>
        </div>
      </div>

      <div class="block" style="margin-top: var(--space-2xl)">
        <h3 class="chart-block" style="margin-bottom:0"><span style="font-size:var(--fs-sm);letter-spacing:0.08em;text-transform:uppercase;color:var(--mute)">Tabla comparativa multi-modelo</span></h3>
        <div class="table-wrap">
          <table class="data" id="models-table">
            <thead>
              <tr>
                <th>Modelo</th>
                <th>Proveedor</th>
                <th>$/MTok</th>
                <th>Sin opt.</th>
                <th>Con opt.</th>
                <th>Ahorro</th>
              </tr>
            </thead>
            <tbody>
              ${a.models
                .map(
                  (m) => `
                <tr>
                  <td>${esc(m.model)}</td>
                  <td>${esc(m.provider)}</td>
                  <td>${formatUsd(m.price_per_1m, 2)}</td>
                  <td>${formatUsd(m.cost_original_usd, 6)}</td>
                  <td>${formatUsd(m.cost_optimized_usd, 6)}</td>
                  <td class="pos">${formatUsd(m.savings_usd, 6)}</td>
                </tr>`
                )
                .join('')}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  // Charts after DOM paint
  requestAnimationFrame(() => {
    renderModelCostChart(el.querySelector('#chart-models'), a.models);
    renderProjectionChart(el.querySelector('#chart-proj'), a.projection.series_30d);
    renderStageChart(el.querySelector('#chart-stages'), a.stage_timings);
    renderTypeChart(el.querySelector('#chart-types'), a.type_distribution);
  });

  el.querySelector('#recalc-btn')?.addEventListener('click', async () => {
    const price = Number(el.querySelector('#re-price').value) || 2.5;
    const vol = Number(el.querySelector('#re-vol').value) || 10000;
    try {
      const res = await api.recalculateAnalytics({
        tokens_original: c.tokens_original,
        tokens_optimized: c.tokens_optimized_estimate ?? c.tokens_optimized,
        item_count: c.item_count,
        optimize_enabled: c.optimize_tokens,
        price_per_million: price,
        daily_volume: vol,
      });
      // Update stored analytics and re-render panel
      result.analytics = res.analytics;
      destroyCharts();
      renderAnalytics(el, result);
    } catch (err) {
      const note = el.querySelector('#be-note');
      if (note) {
        note.className = 'state state--error';
        note.textContent = err.message;
      }
    }
  });
}

function renderPreview(el, result) {
  const rows = result.results_preview || [];
  if (!rows.length) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const typeKey = result.type_key || 'error_type';
  const more =
    result.results_total > rows.length
      ? ` · mostrando ${rows.length} de ${result.results_total}`
      : '';

  el.innerHTML = `
    <section class="preview">
      <h2>Clasificación${more}</h2>
      ${rows
        .map((r) => {
          const cls = r.classification || {};
          const kind = cls[typeKey] || cls.error_type || cls.clause_type || cls.incident_type || '—';
          return `
          <article class="row-card">
            <div class="row-card__meta">
              <span class="tag-mint">${esc(kind)}</span>
              <span>${esc(r.method || 'rules')}</span>
              <span>${r.optimized ? esc(r.optimize_method || 'opt') : 'opt OFF'}</span>
              <span class="tag-amber">${formatInt(r.tokens_original)} → ${formatInt(r.tokens_optimized)} tok</span>
              <span>${esc(r.source || '')}</span>
            </div>
            <p class="row-card__text">${esc(r.text)}</p>
          </article>`;
        })
        .join('')}
    </section>
  `;
}

function restoreIfAny(root) {
  if (state.lastResult?.ok) {
    const coreOut = root.querySelector('#core-out');
    const analyticsOut = root.querySelector('#analytics-out');
    const previewOut = root.querySelector('#preview-out');
    renderCore(coreOut, state.lastResult);
    renderAnalytics(analyticsOut, state.lastResult);
    renderPreview(previewOut, state.lastResult);
  }
}
