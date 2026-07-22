/* ═══════════════════════════════════════════
   diagram.js — Diagram Generation Tool
   Generates PlantUML from a text description,
   then renders it visually via the backend
   (plantuml.jar locally, or Kroki.io fallback).
═══════════════════════════════════════════ */

let lastGeneratedPuml = '';
let dgViewMode        = 'preview';   // 'preview' | 'code'
let dgImageUrl         = '';
let rendererInfo        = null;       // { jar_available, renderer }

/* ══════════════════════════════════════════
   RENDERER STATUS — check once on load
══════════════════════════════════════════ */
async function checkRendererStatus() {
  try {
    const res = await fetch(BACKEND + '/render-status', { signal: AbortSignal.timeout(4000) });
    if (!res.ok) throw new Error('status check failed');
    rendererInfo = await res.json();
  } catch {
    rendererInfo = { jar_available: false, renderer: 'unavailable' };
  }
  updateRendererBadge();
}

function updateRendererBadge() {
  const badge    = document.getElementById('dg-renderer-badge');
  const setupBox = document.getElementById('dg-jar-setup');
  if (!badge || !rendererInfo) return;

  if (rendererInfo.jar_available) {
    badge.textContent = `⚙ Rendering via plantuml.jar (local) — ${rendererInfo.jar_path}`;
    badge.style.color       = 'var(--green)';
    badge.style.borderColor = '#bbf7d0';
    badge.style.background  = 'var(--green-soft)';
    if (setupBox) setupBox.style.display = 'none';
  } else {
    badge.textContent = '🌐 Rendering via Kroki.io (online) — plantuml.jar not found';
    badge.style.color       = 'var(--amber)';
    badge.style.borderColor = '#fde68a';
    badge.style.background  = '#fefce8';

    // Show setup instructions
    if (setupBox && rendererInfo.setup_hint) {
      setupBox.style.display = 'block';
      const pathEl  = document.getElementById('dg-jar-path');
      const dlLink  = document.getElementById('dg-jar-dl');
      if (pathEl) pathEl.textContent = rendererInfo.setup_hint;
      if (dlLink) dlLink.href = rendererInfo.download_url || 'https://plantuml.com/download';
    }
  }
}

/* ══════════════════════════════════════════
   GENERATE PUML FROM DESCRIPTION
══════════════════════════════════════════ */
async function generateDiagram() {
  const descEl = document.getElementById('dg-desc');
  const typeEl = document.getElementById('dg-type');
  const desc   = descEl?.value.trim() || '';

  const errEl  = document.getElementById('dg-err');
  const phEl   = document.getElementById('dg-placeholder');
  const ldEl   = document.getElementById('dg-loading');
  const dgBtn  = document.getElementById('dg-btn');
  const actEl  = document.getElementById('dg-actions');
  const outBox = document.getElementById('dg-result-box');

  if (!desc) { alert('Please enter a system description.'); return; }
  if (desc.length < 10) { alert('Description is too short. Please provide more detail.'); return; }

  errEl?.classList.remove('show');
  actEl?.classList.remove('show');
  if (outBox) outBox.style.display = 'none';
  if (phEl)  phEl.style.display = 'none';
  if (ldEl)  { ldEl.classList.add('show'); setLoadingText('Generating PlantUML with LLM...'); }
  if (dgBtn) dgBtn.disabled = true;

  try {
    const res = await fetch(BACKEND + '/generate-diagram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: desc, diagram_type: typeEl?.value || 'sequence' }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || 'HTTP ' + res.status);
    }
    const d = await res.json();
    lastGeneratedPuml = d.puml || '';
    if (!lastGeneratedPuml.includes('@startuml')) {
      throw new Error('LLM did not return valid PlantUML. Try rephrasing your description.');
    }

    // Show code immediately, then render
    showDiagramCode(lastGeneratedPuml);
    actEl?.classList.add('show');
    if (outBox) outBox.style.display = 'block';

    await renderDiagramImage(lastGeneratedPuml);

  } catch (err) {
    if (errEl) {
      errEl.innerHTML = `<strong>Generation failed</strong><br>${escHtml(err.message)}`;
      errEl.classList.add('show');
    }
    if (phEl) phEl.style.display = '';
  } finally {
    ldEl?.classList.remove('show');
    if (dgBtn) dgBtn.disabled = false;
  }
}

/* ══════════════════════════════════════════
   RENDER PUML → IMAGE (calls backend)
══════════════════════════════════════════ */
async function renderDiagramImage(pumlText) {
  setLoadingText('Rendering diagram image...');
  const ldEl  = document.getElementById('dg-loading');
  const errEl = document.getElementById('dg-render-err');
  ldEl?.classList.add('show');
  errEl?.classList.remove('show');

  try {
    const res = await fetch(BACKEND + '/render-diagram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ puml: pumlText, format: 'png' }),
    });

    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || 'HTTP ' + res.status);
    }

    const blob = await res.blob();
    if (dgImageUrl) URL.revokeObjectURL(dgImageUrl);
    dgImageUrl = URL.createObjectURL(blob);

    const img = document.getElementById('dg-image');
    if (img) { img.src = dgImageUrl; img.style.display = 'block'; }

    setDiagramView('preview');

  } catch (err) {
    if (errEl) {
      errEl.innerHTML = `<strong>⚠ Diagram preview unavailable</strong><br>${escHtml(err.message)}<br>` +
        `<span style="font-size:10px;color:var(--faint)">The PlantUML code itself was generated successfully — switch to "Code" view to copy it.</span>`;
      errEl.classList.add('show');
    }
    setDiagramView('code');
  } finally {
    ldEl?.classList.remove('show');
  }
}

function setLoadingText(text) {
  const span = document.querySelector('#dg-loading span');
  if (span) span.textContent = text;
}

/* ══════════════════════════════════════════
   VIEW TOGGLE — Preview / Code
══════════════════════════════════════════ */
function setDiagramView(mode) {
  dgViewMode = mode;
  const imgWrap  = document.getElementById('dg-image-wrap');
  const codeWrap = document.getElementById('dg-output');
  const btnPrev  = document.getElementById('dg-tab-preview');
  const btnCode  = document.getElementById('dg-tab-code');

  if (mode === 'preview') {
    if (imgWrap)  imgWrap.style.display  = 'flex';
    if (codeWrap) codeWrap.style.display = 'none';
    btnPrev?.classList.add('active');
    btnCode?.classList.remove('active');
  } else {
    if (imgWrap)  imgWrap.style.display  = 'none';
    if (codeWrap) codeWrap.style.display = 'block';
    btnCode?.classList.add('active');
    btnPrev?.classList.remove('active');
  }
}

function showDiagramCode(puml) {
  const codeWrap = document.getElementById('dg-output');
  if (codeWrap) codeWrap.textContent = puml;
}

/* ══════════════════════════════════════════
   RE-RENDER (after manual code edits)
══════════════════════════════════════════ */
async function rerenderDiagram() {
  if (!lastGeneratedPuml.trim()) return;
  await renderDiagramImage(lastGeneratedPuml);
}

/* ══════════════════════════════════════════
   COPY / DOWNLOAD / USE-IN-TC
══════════════════════════════════════════ */
function copyDiagramPuml() {
  if (!lastGeneratedPuml) return;
  navigator.clipboard.writeText(lastGeneratedPuml).then(() => {
    const btn = document.getElementById('dg-copy');
    if (!btn) return;
    const orig = btn.textContent;
    btn.textContent = '✓ Copied!';
    setTimeout(() => { btn.textContent = orig; }, 1400);
  }).catch(() => alert('Copy failed. Please select the code manually.'));
}

function downloadDiagramImage() {
  if (!dgImageUrl) { alert('No rendered image to download.'); return; }
  const a = Object.assign(document.createElement('a'), {
    href: dgImageUrl,
    download: (fileTitle || 'diagram') + '.png',
  });
  a.click();
}

function useDiagramForTC() {
  if (!lastGeneratedPuml) return;
  pumlContent = lastGeneratedPuml;
  fileTitle   = 'generated_diagram';

  const ftName = document.getElementById('file-tag-name');
  const ftRow  = document.getElementById('file-tag-row');
  if (ftName) ftName.textContent = 'generated_diagram.puml (from Diagram Generation)';
  if (ftRow)  ftRow.classList.add('show');

  const genBtn = document.getElementById('btn-generate');
  if (genBtn) genBtn.disabled = false;

  if (typeof navigateTo === 'function') navigateTo('tc');
}

/* ══════════════════════════════════════════
   RESET
══════════════════════════════════════════ */
function resetDiagramState() {
  lastGeneratedPuml = '';
  if (dgImageUrl) { URL.revokeObjectURL(dgImageUrl); dgImageUrl = ''; }

  const outEl  = document.getElementById('dg-output');
  const actEl  = document.getElementById('dg-actions');
  const errEl  = document.getElementById('dg-err');
  const rErrEl = document.getElementById('dg-render-err');
  const phEl   = document.getElementById('dg-placeholder');
  const descEl = document.getElementById('dg-desc');
  const img    = document.getElementById('dg-image');
  const outBox = document.getElementById('dg-result-box');

  if (outEl)  outEl.textContent = '';
  if (actEl)  actEl.classList.remove('show');
  if (errEl)  errEl.classList.remove('show');
  if (rErrEl) rErrEl.classList.remove('show');
  if (phEl)   phEl.style.display = '';
  if (descEl) descEl.value = '';
  if (img)    { img.src = ''; img.style.display = 'none'; }
  if (outBox) outBox.style.display = 'none';
}

/* ══════════════════════════════════════════
   INIT
══════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  const dgBtn = document.getElementById('dg-btn');
  if (dgBtn) dgBtn.addEventListener('click', generateDiagram);

  const copyBtn = document.getElementById('dg-copy');
  if (copyBtn) copyBtn.addEventListener('click', copyDiagramPuml);

  const dlBtn = document.getElementById('dg-download');
  if (dlBtn) dlBtn.addEventListener('click', downloadDiagramImage);

  const useBtn = document.getElementById('dg-use-tc');
  if (useBtn) useBtn.addEventListener('click', useDiagramForTC);

  const rerenderBtn = document.getElementById('dg-rerender');
  if (rerenderBtn) rerenderBtn.addEventListener('click', rerenderDiagram);

  const tabPreview = document.getElementById('dg-tab-preview');
  if (tabPreview) tabPreview.addEventListener('click', () => setDiagramView('preview'));

  const tabCode = document.getElementById('dg-tab-code');
  if (tabCode) tabCode.addEventListener('click', () => setDiagramView('code'));

  checkRendererStatus();
});
