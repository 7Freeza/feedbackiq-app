/** Cliente HTTP hacia el backend FeedbackIQ */

const BASE = '/api';
const FETCH_TIMEOUT_MS = 120_000; // 2 min máx por request síncrona
const POLL_INTERVAL_MS = 1500;
const POLL_MAX_MS = 30 * 60 * 1000; // 30 min jobs grandes

async function parseError(res) {
  let detail = res.statusText;
  try {
    const j = await res.json();
    if (typeof j.detail === 'string') detail = j.detail;
    else if (j.detail?.message)
      detail =
        j.detail.message +
        (j.detail.errors?.length ? ': ' + j.detail.errors.join('; ') : '');
    else if (j.message) detail = j.message;
    else if (j.error) detail = j.error;
  } catch {
    /* ignore */
  }
  return detail;
}

async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: ctrl.signal });
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new Error(
        'El servidor tardó demasiado. Si el archivo es muy grande, espera o divídelo.'
      );
    }
    throw err;
  } finally {
    clearTimeout(id);
  }
}

async function pollJob(jobId) {
  const start = Date.now();
  while (Date.now() - start < POLL_MAX_MS) {
    const res = await fetchWithTimeout(`${BASE}/jobs/${encodeURIComponent(jobId)}`, {}, 15_000);
    if (!res.ok) throw new Error(await parseError(res));
    const data = await res.json();
    if (data.status === 'done' && data.result) return data.result;
    if (data.status === 'error') {
      throw new Error(data.error || data.message || 'Error en trabajo en segundo plano');
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  throw new Error('El procesamiento en segundo plano superó el tiempo máximo. Revisa /api/jobs/' + jobId);
}

export async function health() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getDomains() {
  const res = await fetch(`${BASE}/domains`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getModels() {
  const res = await fetch(`${BASE}/models`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/**
 * @param {File[]} files
 * @param {{ optimize_tokens: boolean, domain: string, price_per_million: number, daily_volume: number }} opts
 * @param {{ onAsync?: (info: {job_id: string, rows_estimate?: number, message?: string}) => void }} [hooks]
 */
export async function analyze(files, opts, hooks = {}) {
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  fd.append('optimize_tokens', String(opts.optimize_tokens));
  fd.append('domain', opts.domain);
  fd.append('price_per_million', String(opts.price_per_million));
  fd.append('daily_volume', String(opts.daily_volume));

  const res = await fetchWithTimeout(`${BASE}/analyze`, { method: 'POST', body: fd });

  // 202 = job en segundo plano (archivo grande)
  if (res.status === 202) {
    const meta = await res.json();
    hooks.onAsync?.({
      job_id: meta.job_id,
      rows_estimate: meta.rows_estimate,
      message: meta.message,
    });
    return pollJob(meta.job_id);
  }

  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function recalculateAnalytics(payload) {
  const res = await fetch(`${BASE}/analytics/recalculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export function downloadUrl(filename) {
  return `${BASE}/download/${encodeURIComponent(filename)}`;
}
