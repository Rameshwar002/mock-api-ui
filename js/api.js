/* ═══════════════════════════════════════════
   api.js — Backend API & Health Check
═══════════════════════════════════════════ */

const BACKEND = 'http://localhost:5050';

/* ── LLM Health Check ── */
async function checkLlmHealth() {
  const badge   = document.getElementById('llm-status-badge');
  const urlLbl  = document.getElementById('lbl-llm-url');
  const modelLbl= document.getElementById('lbl-llm-model');

  if (badge) { badge.textContent = 'Checking...'; badge.style.background = '#f5f5f5'; badge.style.color = '#666'; }

  try {
    const r = await fetch(BACKEND + '/health', { signal: AbortSignal.timeout(5000) });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();

    if (d.llm_reachable) {
      if (badge)    { badge.textContent = 'Connected'; badge.style.background = '#dcfce7'; badge.style.color = '#15803d'; }
      if (urlLbl)   urlLbl.textContent   = d.llm_url   || 'localhost:11434/v1';
      if (modelLbl) modelLbl.textContent = d.llm_model || 'llama3';
    } else {
      if (badge) { badge.textContent = 'LLM Offline'; badge.style.background = '#fef9c3'; badge.style.color = '#92400e'; }
    }
  } catch (err) {
    if (badge) { badge.textContent = 'Offline'; badge.style.background = '#fee2e2'; badge.style.color = '#b91c1c'; }
  }
}

/* ── Periodic health poll (every 15s) ── */
setInterval(() => {
  if (typeof currentUser !== 'undefined' && currentUser) checkLlmHealth();
}, 15000);

/* ── Generic fetch wrapper with error handling ── */
async function apiFetch(path, options = {}) {
  const res = await fetch(BACKEND + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Download blob from API ── */
async function apiDownload(path, options = {}, filename = 'download.xlsx') {
  const res = await fetch(BACKEND + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(blob),
    download: filename,
  });
  a.click();
  URL.revokeObjectURL(a.href);
}
