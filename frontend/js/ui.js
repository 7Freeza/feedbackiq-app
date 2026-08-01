/** Utilidades de UI: conteo animado, formato */

export function formatInt(n) {
  if (n == null || Number.isNaN(n)) return '—';
  return Math.round(n).toLocaleString('es-ES');
}

export function formatUsd(n, digits = 4) {
  if (n == null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  const d = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return (
    '$' +
    n.toLocaleString('en-US', {
      minimumFractionDigits: Math.min(d, digits),
      maximumFractionDigits: Math.max(d, digits),
    })
  );
}

export function formatMs(ms) {
  if (ms == null) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/**
 * Conteo ascendente breve al llegar el valor.
 */
export function animateNumber(el, target, { duration = 700, formatter = formatInt } = {}) {
  if (!el) return;
  const start = performance.now();
  const from = 0;
  const to = Number(target) || 0;

  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    // easeOutCubic
    const e = 1 - Math.pow(1 - t, 3);
    const val = from + (to - from) * e;
    el.textContent = formatter(val);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = formatter(to);
  }
  requestAnimationFrame(tick);
}

export function setActiveNav(route) {
  document.querySelectorAll('.nav__link').forEach((a) => {
    const r = a.getAttribute('data-route');
    a.classList.toggle('is-active', r === route || (route === '/' && r === '/'));
  });
}

export function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
