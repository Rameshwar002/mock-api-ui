/* ═══════════════════════════════════════════
   seq-reviewer.js — Sequence Diagram Reviewer
   Supports: .puml / .txt / .png / .jpg / .svg / .gif / .webp
   Compares OLD vs NEW and explains changes via AI
═══════════════════════════════════════════ */

let oldPuml      = '';
let newPuml      = '';
let oldIsImage   = false;
let newIsImage   = false;
let oldImageB64  = '';   // base64 for LLM vision
let oldImageMime = '';
let newImageB64  = '';
let newImageMime = '';
let diffResult   = null;

const IMAGE_EXTS = ['png','jpg','jpeg','gif','webp','svg'];
const TEXT_EXTS  = ['puml','txt','plantuml','md'];

/* ══════════════════════════════════════════
   INIT & WIRING
══════════════════════════════════════════ */
function initSeqReviewer() {
  wireDropZone(
    document.getElementById('seq-old-zone'),
    document.getElementById('seq-old-input'),
    'old'
  );
  wireDropZone(
    document.getElementById('seq-new-zone'),
    document.getElementById('seq-new-input'),
    'new'
  );
  const cmpBtn = document.getElementById('btn-compare');
  if (cmpBtn) cmpBtn.addEventListener('click', runCompare);
}

function wireDropZone(zone, input, which) {
  if (!zone || !input) return;
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) loadSeqFile(e.dataTransfer.files[0], which);
  });
  input.addEventListener('change', () => {
    if (input.files[0]) loadSeqFile(input.files[0], which);
  });
}

/* ══════════════════════════════════════════
   FILE LOADING — text or image
══════════════════════════════════════════ */
function getFileExt(filename) {
  return filename.split('.').pop().toLowerCase();
}

function isImageFile(filename) {
  return IMAGE_EXTS.includes(getFileExt(filename));
}

function loadSeqFile(file, which) {
  const ext = getFileExt(file.name);

  if (isImageFile(file.name)) {
    loadImageFile(file, which);
  } else if (TEXT_EXTS.includes(ext)) {
    loadTextFile(file, which);
  } else {
    showSeqErr(`Unsupported file type ".${ext}". Please use .puml, .txt, .png, .jpg, .svg.`);
  }
}

/* ── Load text (PUML) ── */
function loadTextFile(file, which) {
  const r = new FileReader();
  r.onload = e => {
    const content = e.target.result;
    if (which === 'old') {
      oldPuml    = content;
      oldIsImage = false;
      updateZoneText('old', file.name, content);
    } else {
      newPuml    = content;
      newIsImage = false;
      updateZoneText('new', file.name, content);
    }
    updateCompareBtn();
  };
  r.readAsText(file);
}

/* ── Load image ── */
function loadImageFile(file, which) {
  const mime = file.type || 'image/png';
  const r    = new FileReader();
  r.onload = e => {
    const dataUrl = e.target.result;
    const b64     = dataUrl.split(',')[1];   // strip "data:image/png;base64,"

    if (which === 'old') {
      oldIsImage   = true;
      oldImageB64  = b64;
      oldImageMime = mime;
      oldPuml      = '';   // will be filled after LLM extraction
      updateZoneImage('old', file.name, dataUrl);
    } else {
      newIsImage   = true;
      newImageB64  = b64;
      newImageMime = mime;
      newPuml      = '';
      updateZoneImage('new', file.name, dataUrl);
    }
    // Show vision LLM notice
    const notice = document.getElementById('vision-notice');
    if (notice) notice.classList.add('show');
    updateCompareBtn();
  };
  r.readAsDataURL(file);
}

/* ══════════════════════════════════════════
   ZONE UI UPDATES
══════════════════════════════════════════ */
function updateZoneText(which, filename, content) {
  const tag     = document.getElementById(`seq-${which}-tag`);
  const preview = document.getElementById(`seq-${which}-preview`);
  const imgWrap = document.getElementById(`seq-${which}-img-wrap`);

  if (tag)     { tag.textContent = '📄 ' + filename; tag.classList.add('show'); }
  if (imgWrap) imgWrap.style.display = 'none';
  if (preview) {
    preview.textContent = content.slice(0, 800) + (content.length > 800 ? '\n...' : '');
    preview.classList.add('show');
  }
}

function updateZoneImage(which, filename, dataUrl) {
  const tag     = document.getElementById(`seq-${which}-tag`);
  const preview = document.getElementById(`seq-${which}-preview`);
  const imgWrap = document.getElementById(`seq-${which}-img-wrap`);
  const imgEl   = document.getElementById(`seq-${which}-img`);

  if (tag)     { tag.textContent = '🖼 ' + filename; tag.classList.add('show'); }
  if (preview) { preview.textContent = ''; preview.classList.remove('show'); }
  if (imgEl)   imgEl.src = dataUrl;
  if (imgWrap) imgWrap.style.display = 'block';
}

function updateCompareBtn() {
  const btn = document.getElementById('btn-compare');
  if (!btn) return;
  // Enable if both sides have something (text or image)
  const oldReady = oldPuml.trim() || oldIsImage;
  const newReady = newPuml.trim() || newIsImage;
  btn.disabled = !(oldReady && newReady);
}

/* ══════════════════════════════════════════
   IMAGE → PUML via LLM Vision
   Sends image to backend /extract-diagram
══════════════════════════════════════════ */
async function extractPumlFromImage(b64, mime) {
  const res = await fetch(BACKEND + '/extract-diagram', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_base64: b64, image_mime: mime }),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || 'Image extraction failed: HTTP ' + res.status);
  }
  const d = await res.json();
  return d.puml || '';
}

/* ══════════════════════════════════════════
   PUML PARSER
══════════════════════════════════════════ */
function parsePuml(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith("'"));
  const result = {
    title:      '',
    actors:     [],
    messages:   [],
    conditions: [],
    notes:      [],
    groups:     [],
    rawLines:   lines,
  };

  lines.forEach(line => {
    const tl = line.toLowerCase();
    if (tl.startsWith('title '))
      result.title = line.slice(6).trim();
    // Messages — check FIRST (most specific), prevents lines like
    // "Database --> Server : User record" being mis-caught as an actor decl
    else if (/->|-->|->>|-->>/.test(line)) {
      const m = line.match(/^(\w+)\s*(?:->|-->|->>|-->>)\s*(\w+)\s*:\s*(.+)/);
      if (m) result.messages.push({ from: m[1], to: m[2], label: m[3].trim(), raw: line });
    }
    else if (/^(actor|participant|boundary|control|entity|database|component)\s/i.test(line)) {
      const m = line.match(/\S+\s+"?([^"]+)"?(?:\s+as\s+(\w+))?/i);
      if (m) result.actors.push({ label: m[2] || m[1], name: m[1] });
    }
    else if (/^(alt|else|opt|loop|break)\s/i.test(line))
      result.conditions.push(line.trim());
    else if (/^note\s/i.test(line))
      result.notes.push(line.trim());
    else if (/^group\s/i.test(line))
      result.groups.push(line.slice(5).trim());
  });

  return result;
}

/* ══════════════════════════════════════════
   DIFF ENGINE
══════════════════════════════════════════ */
function computeDiff(oldText, newText) {
  const oldParsed = parsePuml(oldText);
  const newParsed = parsePuml(newText);
  const changes   = [];

  // Title
  if (oldParsed.title !== newParsed.title)
    changes.push({ type:'modified', category:'Title',
      description:`Diagram title changed`,
      old: oldParsed.title || '(none)', new: newParsed.title || '(none)' });

  // Actors
  const oldActors = oldParsed.actors.map(a => a.label);
  const newActors = newParsed.actors.map(a => a.label);
  newActors.forEach(a => { if (!oldActors.includes(a)) changes.push({ type:'added',   category:'Actor', description:`New actor: "${a}"`, old:'', new:a }); });
  oldActors.forEach(a => { if (!newActors.includes(a)) changes.push({ type:'removed', category:'Actor', description:`Actor removed: "${a}"`, old:a, new:'' }); });

  // Messages
  const oldMsgs = oldParsed.messages.map(m => m.raw.trim());
  const newMsgs = newParsed.messages.map(m => m.raw.trim());
  newParsed.messages.forEach(m => { if (!oldMsgs.includes(m.raw.trim())) changes.push({ type:'added',   category:'Message', description:`New message: ${m.from} → ${m.to}: "${m.label}"`, old:'', new:m.raw }); });
  oldParsed.messages.forEach(m => { if (!newMsgs.includes(m.raw.trim())) changes.push({ type:'removed', category:'Message', description:`Message removed: ${m.from} → ${m.to}: "${m.label}"`, old:m.raw, new:'' }); });

  // Conditions
  const oldC = oldParsed.conditions, newC = newParsed.conditions;
  newC.forEach(c => { if (!oldC.includes(c)) changes.push({ type:'added',   category:'Condition', description:`New condition: "${c}"`, old:'', new:c }); });
  oldC.forEach(c => { if (!newC.includes(c)) changes.push({ type:'removed', category:'Condition', description:`Condition removed: "${c}"`, old:c, new:'' }); });

  // Notes
  const oldN = oldParsed.notes, newN = newParsed.notes;
  newN.forEach(n => { if (!oldN.includes(n)) changes.push({ type:'added',   category:'Note', description:`New note: "${n.slice(0,60)}"`, old:'', new:n }); });
  oldN.forEach(n => { if (!newN.includes(n)) changes.push({ type:'removed', category:'Note', description:`Note removed: "${n.slice(0,60)}"`, old:n, new:'' }); });

  // Sequence order change (no content change but order changed)
  if (oldMsgs.join('|') !== newMsgs.join('|') && !changes.some(c => c.category === 'Message'))
    changes.push({ type:'modified', category:'Order', description:'Message sequence order changed', old:'', new:'' });

  const summary = {
    added:     changes.filter(c => c.type === 'added').length,
    removed:   changes.filter(c => c.type === 'removed').length,
    modified:  changes.filter(c => c.type === 'modified').length,
    unchanged: Math.max(0, oldMsgs.length - changes.filter(c => c.category === 'Message').length),
    total:     changes.length,
  };

  return { changes, summary, oldParsed, newParsed,
           oldLines: oldText.split('\n'), newLines: newText.split('\n') };
}

/* ══════════════════════════════════════════
   SIDE-BY-SIDE TEXT DIFF
══════════════════════════════════════════ */
function buildSideBySide(oldLines, newLines) {
  const maxLen = Math.max(oldLines.length, newLines.length);
  let oldHtml = '', newHtml = '';
  for (let i = 0; i < maxLen; i++) {
    const o = oldLines[i] ?? '';
    const n = newLines[i] ?? '';
    if (o === n) {
      oldHtml += `<span class="diff-line-ctx">${escHtml(o)}\n</span>`;
      newHtml += `<span class="diff-line-ctx">${escHtml(n)}\n</span>`;
    } else if (!o) {
      oldHtml += `<span class="diff-line-ctx">&nbsp;\n</span>`;
      newHtml += `<span class="diff-line-added">${escHtml(n)}\n</span>`;
    } else if (!n) {
      oldHtml += `<span class="diff-line-removed">${escHtml(o)}\n</span>`;
      newHtml += `<span class="diff-line-ctx">&nbsp;\n</span>`;
    } else {
      oldHtml += `<span class="diff-line-removed">${escHtml(o)}\n</span>`;
      newHtml += `<span class="diff-line-added">${escHtml(n)}\n</span>`;
    }
  }
  return { oldHtml, newHtml };
}

/* ══════════════════════════════════════════
   AI EXPLANATION
══════════════════════════════════════════ */
async function fetchAiExplanation(changes, oldParsed, newParsed) {
  const res = await fetch(BACKEND + '/compare-diagrams', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_puml: oldPuml, new_puml: newPuml, changes }),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.error || 'AI explanation failed: HTTP ' + res.status);
  }
  const d = await res.json();
  return d.explanation || 'Explanation not available.';
}

/* ══════════════════════════════════════════
   SHOW EXTRACTION PROGRESS
══════════════════════════════════════════ */
function showExtractProgress(msg) {
  const wrap = document.getElementById('extract-progress');
  const txt  = document.getElementById('extract-progress-text');
  if (wrap) wrap.style.display = 'flex';
  if (txt)  txt.textContent = msg;
}
function hideExtractProgress() {
  const wrap = document.getElementById('extract-progress');
  if (wrap) wrap.style.display = 'none';
}

/* ══════════════════════════════════════════
   RUN COMPARE
══════════════════════════════════════════ */
async function runCompare() {
  const errEl     = document.getElementById('seq-err');
  const resultsEl = document.getElementById('diff-results');
  const cmpBtn    = document.getElementById('btn-compare');

  if (errEl) errEl.classList.remove('show');
  if (cmpBtn) { cmpBtn.disabled = true; cmpBtn.textContent = '⏳ Processing...'; }

  try {
    // ── Step 1: Extract PUML from images if needed ──
    if (oldIsImage && !oldPuml.trim()) {
      showExtractProgress('🖼 Extracting diagram from old image via LLM...');
      oldPuml = await extractPumlFromImage(oldImageB64, oldImageMime);
      const preview = document.getElementById('seq-old-preview');
      if (preview) { preview.textContent = oldPuml.slice(0, 800); preview.classList.add('show'); }
    }
    if (newIsImage && !newPuml.trim()) {
      showExtractProgress('🖼 Extracting diagram from new image via LLM...');
      newPuml = await extractPumlFromImage(newImageB64, newImageMime);
      const preview = document.getElementById('seq-new-preview');
      if (preview) { preview.textContent = newPuml.slice(0, 800); preview.classList.add('show'); }
    }
    hideExtractProgress();

    if (!oldPuml.trim() || !newPuml.trim()) {
      throw new Error('Could not extract diagram content. Make sure the image shows a sequence diagram clearly.');
    }

    // ── Step 2: Compute diff ──
    diffResult = computeDiff(oldPuml, newPuml);
    const { changes, summary, oldParsed, newParsed, oldLines, newLines } = diffResult;

    // Show results
    if (resultsEl) resultsEl.style.display = 'block';

    // Summary chips
    const chipsEl = document.getElementById('diff-chips');
    if (chipsEl) chipsEl.innerHTML =
      `<span class="diff-chip chip-added">+${summary.added} Added</span>` +
      `<span class="diff-chip chip-removed">-${summary.removed} Removed</span>` +
      `<span class="diff-chip chip-modified">~${summary.modified} Modified</span>` +
      `<span class="diff-chip chip-unchanged">${summary.unchanged} Unchanged</span>`;

    // Side-by-side diff
    const { oldHtml, newHtml } = buildSideBySide(oldLines, newLines);
    const oldBody = document.getElementById('diff-old-body');
    const newBody = document.getElementById('diff-new-body');
    if (oldBody) oldBody.innerHTML = oldHtml;
    if (newBody) newBody.innerHTML = newHtml;

    const oldTitle = document.getElementById('diff-old-title');
    const newTitle = document.getElementById('diff-new-title');
    const oldSuffix = oldIsImage ? ' (from image)' : '';
    const newSuffix = newIsImage ? ' (from image)' : '';
    if (oldTitle) oldTitle.textContent = `OLD — ${oldParsed.title || 'Untitled'}${oldSuffix}`;
    if (newTitle) newTitle.textContent = `NEW — ${newParsed.title || 'Untitled'}${newSuffix}`;

    // Change cards
    renderChangeCards(changes);

    // Diff table
    renderDiffTable(changes);

    // ── Step 3: AI Explanation ──
    const aiBox  = document.getElementById('ai-explanation-body');
    const aiLoad = document.getElementById('ai-explanation-loading');
    if (aiBox)  aiBox.style.display  = 'none';
    if (aiLoad) aiLoad.style.display = 'flex';

    try {
      if (changes.length === 0) {
        if (aiLoad) aiLoad.style.display = 'none';
        if (aiBox)  { aiBox.style.display = 'block'; aiBox.innerHTML = '<p>No changes were detected between the two diagrams. They appear to be structurally identical.</p>'; }
      } else {
        const explanation = await fetchAiExplanation(changes, oldParsed, newParsed);
        if (aiLoad) aiLoad.style.display = 'none';
        if (aiBox)  {
          aiBox.style.display = 'block';
          aiBox.innerHTML = explanation.split('\n\n').filter(Boolean)
            .map(p => `<p>${escHtml(p)}</p>`).join('');
        }
      }
    } catch (e) {
      if (aiLoad) aiLoad.style.display = 'none';
      if (aiBox)  { aiBox.style.display = 'block'; aiBox.innerHTML = `<p style="color:var(--sub)">AI explanation unavailable (${escHtml(e.message)}). See change cards below.</p>`; }
    }

    resultsEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    hideExtractProgress();
    if (errEl) { errEl.innerHTML = `<strong>Compare failed</strong><br>${escHtml(err.message)}`; errEl.classList.add('show'); }
  } finally {
    if (cmpBtn) { cmpBtn.disabled = false; cmpBtn.innerHTML = '&#128269; Compare Diagrams &amp; Explain Changes'; }
  }
}

/* ══════════════════════════════════════════
   RENDER HELPERS
══════════════════════════════════════════ */
function renderChangeCards(changes) {
  const cardsEl = document.getElementById('change-cards');
  if (!cardsEl) return;
  if (changes.length === 0) {
    cardsEl.innerHTML = `<div style="text-align:center;padding:24px;color:var(--faint);font-size:12px">
      ✅ No structural differences detected.</div>`;
    return;
  }
  const iconMap = { added:'➕', removed:'➖', modified:'✏️' };
  cardsEl.innerHTML = changes.map(c => `
    <div class="change-card">
      <div class="change-card-icon ${c.type}">${iconMap[c.type] || '•'}</div>
      <div class="change-card-body">
        <div class="change-card-title">
          <span class="badge badge-${c.type}">${c.type.toUpperCase()}</span>
          &nbsp;${escHtml(c.category)}
        </div>
        <div class="change-card-desc">${escHtml(c.description)}</div>
        ${c.old ? `<div class="change-card-detail">Before: ${escHtml(c.old.slice(0,80))}</div>` : ''}
        ${c.new ? `<div class="change-card-detail">After: ${escHtml(c.new.slice(0,80))}</div>` : ''}
      </div>
    </div>`).join('');
}

function renderDiffTable(changes) {
  const tbody = document.getElementById('diff-table-body');
  if (!tbody) return;
  if (changes.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:16px;color:var(--faint);font-size:12px">No changes detected.</td></tr>`;
    return;
  }
  tbody.innerHTML = changes.map(c => `
    <tr class="row-${c.type}">
      <td><span class="badge badge-${c.type}">${escHtml(c.type)}</span></td>
      <td><strong>${escHtml(c.category)}</strong></td>
      <td style="font-size:11px">${escHtml(c.description)}</td>
      <td style="font-size:10px;font-family:var(--mono);color:var(--sub)">
        ${c.old ? `<del style="color:#b91c1c">${escHtml(c.old.slice(0,60))}</del><br>` : ''}
        ${c.new ? `<ins style="color:#15803d;text-decoration:none">${escHtml(c.new.slice(0,60))}</ins>` : ''}
      </td>
    </tr>`).join('');
}

function filterDiff(term) {
  if (!diffResult) return;
  const filtered = term
    ? diffResult.changes.filter(c => Object.values(c).some(v => String(v).toLowerCase().includes(term)))
    : diffResult.changes;
  renderDiffTable(filtered);
}

/* ══════════════════════════════════════════
   RESET
══════════════════════════════════════════ */
function resetSeqState() {
  oldPuml = ''; newPuml = '';
  oldIsImage = false; newIsImage = false;
  oldImageB64 = ''; newImageB64 = '';
  diffResult = null;

  ['old','new'].forEach(w => {
    const tag     = document.getElementById(`seq-${w}-tag`);
    const preview = document.getElementById(`seq-${w}-preview`);
    const imgWrap = document.getElementById(`seq-${w}-img-wrap`);
    const imgEl   = document.getElementById(`seq-${w}-img`);
    const input   = document.getElementById(`seq-${w}-input`);
    if (tag)     { tag.textContent = ''; tag.classList.remove('show'); }
    if (preview) { preview.textContent = ''; preview.classList.remove('show'); }
    if (imgWrap) imgWrap.style.display = 'none';
    if (imgEl)   imgEl.src = '';
    if (input)   input.value = '';
  });

  const res = document.getElementById('diff-results');
  if (res) res.style.display = 'none';
  hideExtractProgress();
  updateCompareBtn();

  const notice = document.getElementById('vision-notice');
  if (notice) notice.classList.remove('show');
  oldImageB64 = ''; oldImageMime = '';
  newImageB64 = ''; newImageMime = '';

  const errEl = document.getElementById('seq-err');
  if (errEl) errEl.classList.remove('show');
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  initSeqReviewer();
  const res = document.getElementById('diff-results');
  if (res) res.style.display = 'none';
});