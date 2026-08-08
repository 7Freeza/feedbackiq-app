/** Footer: reporte de problemas → backend → n8n */

import { submitReport } from './api.js';
import { esc } from './ui.js';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function initReportForm() {
  const form = document.getElementById('report-form');
  const ta = document.getElementById('report-msg');
  const emailEl = document.getElementById('report-email');
  const btn = document.getElementById('report-submit');
  const status = document.getElementById('report-status');
  if (!form || !ta || !btn || !status) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const mensaje = ta.value.trim();
    if (mensaje.length < 10) {
      setStatus(status, 'Escribe al menos 10 caracteres.', 'err');
      ta.focus();
      return;
    }

    const emailRaw = emailEl ? emailEl.value.trim() : '';
    if (emailRaw && !EMAIL_RE.test(emailRaw)) {
      setStatus(status, 'El correo no es válido (o déjalo vacío).', 'err');
      emailEl?.focus();
      return;
    }

    btn.disabled = true;
    setStatus(status, 'Enviando…', 'info');

    try {
      const payload = {
        mensaje,
        page: location.hash || '#/',
      };
      if (emailRaw) payload.email = emailRaw;

      const res = await submitReport(payload);
      const sev = res.classification?.severidad;
      const mod = res.classification?.modulo_probable;
      let extra = '';
      if (sev || mod) {
        extra = ` · ${esc(sev || '')}${mod ? ' · ' + esc(mod) : ''}`;
      }
      if (res.dry_run) {
        setStatus(
          status,
          `Gracias (demo local)${extra}. Cuando conectes n8n llegará a Sheets/Email.`,
          'ok'
        );
      } else if (emailRaw) {
        setStatus(
          status,
          `Gracias, lo revisamos${extra}. Te enviamos una guía a ${esc(emailRaw)}.`,
          'ok'
        );
      } else {
        setStatus(status, `Gracias, lo revisamos${extra}.`, 'ok');
      }
      ta.value = '';
      if (emailEl) emailEl.value = '';
    } catch (err) {
      setStatus(status, err.message || 'No se pudo enviar el reporte.', 'err');
    } finally {
      btn.disabled = false;
    }
  });
}

function setStatus(el, text, kind) {
  el.textContent = text;
  el.className = 'report-form__status state';
  if (kind === 'ok') el.classList.add('is-ok');
  else if (kind === 'err') el.classList.add('is-err', 'state--error');
  else el.classList.add('state--info');
}
