/* ═══════════════════════════════════════════
   knowledge.js — Knowledge Base Management
═══════════════════════════════════════════ */

let knowledge = {
  project:    '',
  desc:       '',
  tech:       '',
  tags:       [],
  rules:      '',
  focus:      'all',
  mincount:   8,
  extra:      '',
  vdb:        '',
  collection: '',
};

let tags = [];

/* ── Tags ── */
function addTag() {
  const inp = document.getElementById('tag-input');
  if (!inp) return;
  const val = inp.value.trim();
  if (!val) return;
  if (tags.length >= 20) { alert('Maximum 20 keywords allowed.'); return; }
  if (!tags.includes(val)) { tags.push(val); renderTags(); }
  inp.value = '';
}

function removeTag(t) {
  tags = tags.filter(x => x !== t);
  renderTags();
}

function renderTags() {
  const row = document.getElementById('tag-row');
  if (!row) return;
  row.innerHTML = tags.map(t =>
    `<div class="tag">${escHtml(t)}<span class="rm" onclick="removeTag('${escHtml(t)}')">&times;</span></div>`
  ).join('');
}

/* ── Vector DB ── */
function updateVdb() {
  const v   = document.getElementById('vdb-provider')?.value || '';
  const dot = document.getElementById('vdb-dot');
  const lbl = document.getElementById('vdb-label');
  const sta = document.getElementById('vdb-status');
  if (!dot || !lbl || !sta) return;

  if (!v) {
    dot.className   = 'vdb-dot';
    lbl.textContent = 'Not configured';
    sta.textContent = '--';
    return;
  }
  dot.className = 'vdb-dot on';
  const names   = { chroma: 'ChromaDB (localhost:8000)', pinecone: 'Pinecone', weaviate: 'Weaviate', qdrant: 'Qdrant' };
  lbl.textContent = (names[v] || v) + ' selected';
  sta.textContent = 'Ready';
}

/* ── Save knowledge ── */
function saveKnowledge() {
  const proj = document.getElementById('k-project')?.value?.trim() || '';
  if (!proj) { alert('Please enter a project name before saving.'); return; }

  knowledge = {
    project:    proj,
    desc:       document.getElementById('k-desc')?.value    || '',
    tech:       document.getElementById('k-tech')?.value    || '',
    tags:       [...tags],
    rules:      document.getElementById('k-rules')?.value   || '',
    focus:      document.getElementById('k-focus')?.value   || 'all',
    mincount:   parseInt(document.getElementById('k-mincount')?.value) || 8,
    extra:      document.getElementById('k-extra')?.value   || '',
    vdb:        document.getElementById('vdb-provider')?.value || '',
    collection: document.getElementById('vdb-collection')?.value || '',
  };

  // Persist to localStorage for session
  try { localStorage.setItem('tc_knowledge', JSON.stringify(knowledge)); } catch (_) {}

  const btn = document.querySelector('.btn-save');
  if (btn) {
    const orig = btn.textContent;
    btn.textContent = '✓ Saved';
    btn.style.background = '#16a34a';
    setTimeout(() => { btn.textContent = orig; btn.style.background = ''; }, 1600);
  }
}

/* ── Reset knowledge ── */
function resetKnowledge() {
  if (!confirm('Reset all knowledge base data? This cannot be undone.')) return;
  knowledge = { project:'', desc:'', tech:'', tags:[], rules:'', focus:'all', mincount:8, extra:'', vdb:'', collection:'' };
  tags = [];
  ['k-project','k-desc','k-tech','k-rules','k-extra'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const focusEl = document.getElementById('k-focus');
  if (focusEl) focusEl.value = 'all';
  const mincountEl = document.getElementById('k-mincount');
  if (mincountEl) mincountEl.value = '8';
  const vdbEl = document.getElementById('vdb-provider');
  if (vdbEl) vdbEl.value = '';
  updateVdb();
  renderTags();
  try { localStorage.removeItem('tc_knowledge'); } catch (_) {}
  alert('Knowledge base has been reset.');
}

/* ── Load saved knowledge from localStorage ── */
function loadKnowledge() {
  try {
    const saved = localStorage.getItem('tc_knowledge');
    if (!saved) return;
    const k = JSON.parse(saved);
    knowledge = { ...knowledge, ...k };
    tags = Array.isArray(k.tags) ? [...k.tags] : [];

    if (document.getElementById('k-project')) document.getElementById('k-project').value = knowledge.project;
    if (document.getElementById('k-desc'))    document.getElementById('k-desc').value    = knowledge.desc;
    if (document.getElementById('k-tech'))    document.getElementById('k-tech').value    = knowledge.tech;
    if (document.getElementById('k-rules'))   document.getElementById('k-rules').value   = knowledge.rules;
    if (document.getElementById('k-focus'))   document.getElementById('k-focus').value   = knowledge.focus;
    if (document.getElementById('k-mincount'))document.getElementById('k-mincount').value= knowledge.mincount;
    if (document.getElementById('k-extra'))   document.getElementById('k-extra').value   = knowledge.extra;
    if (document.getElementById('vdb-provider')) {
      document.getElementById('vdb-provider').value = knowledge.vdb;
      updateVdb();
    }
    if (document.getElementById('vdb-collection'))
      document.getElementById('vdb-collection').value = knowledge.collection;

    renderTags();
  } catch (_) {}
}

/* ── Get current knowledge (for pipeline use) ── */
function getKnowledge() {
  return {
    ...knowledge,
    tags: [...tags],
    min_cases: parseInt(document.getElementById('tc-limit')?.value) || knowledge.mincount,
  };
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  const saveBtn = document.querySelector('.btn-save');
  if (saveBtn) saveBtn.addEventListener('click', saveKnowledge);

  const tagInput = document.getElementById('tag-input');
  if (tagInput) {
    tagInput.addEventListener('keydown', e => { if (e.key === 'Enter') addTag(); });
  }
  const tagAddBtn = document.querySelector('.tag-add button');
  if (tagAddBtn) tagAddBtn.addEventListener('click', addTag);

  const vdbSel = document.getElementById('vdb-provider');
  if (vdbSel) vdbSel.addEventListener('change', updateVdb);

  // Load saved data
  loadKnowledge();
});
