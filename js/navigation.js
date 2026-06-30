/* ═══════════════════════════════════════════
   navigation.js — View Routing & Sidebar
═══════════════════════════════════════════ */

const VIEW_MAP = {
  tc:             'view-tc',
  knowledge:      'view-knowledge',
  dg:             'view-dg',
  seq:            'view-seq',
  'admin-users':  'view-admin-users',
  'admin-settings': 'view-admin-settings',
};

let currentView = 'tc';

/* ── Switch by sidebar element ── */
function switchView(el) {
  if (!el.dataset.view) return;
  const viewKey = el.dataset.view;
  navigateTo(viewKey);

  // Update sidebar active state
  document.querySelectorAll('.sb-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');
}

/* ── Navigate programmatically ── */
function navigateTo(viewKey) {
  currentView = viewKey;
  const viewId = VIEW_MAP[viewKey];
  if (!viewId) { console.warn('[nav] Unknown view:', viewKey); return; }

  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById(viewId);
  if (target) {
    target.classList.add('active');
  } else {
    console.warn('[nav] View element not found:', viewId);
  }

  // Sync sidebar highlight
  document.querySelectorAll('.sb-item').forEach(i => {
    i.classList.toggle('active', i.dataset.view === viewKey);
  });

  // Scroll main to top on navigation
  const main = document.querySelector('.main');
  if (main) main.scrollTop = 0;
}

/* ── Named shortcut (used by related-links etc) ── */
function switchViewById(id) {
  navigateTo(id);
}

/* ── Global search ── */
function initGlobalSearch() {
  const input = document.getElementById('global-search');
  if (!input) return;

  input.addEventListener('input', e => {
    const term = e.target.value.trim().toLowerCase();
    if (!term) return;

    // If on TC view, delegate to table filter
    if (currentView === 'tc' && typeof filterTable === 'function') {
      const tcSearch = document.getElementById('tc-search');
      if (tcSearch) { tcSearch.value = e.target.value; }
      filterTable();
    }
    // If on seq view, filter diff
    if (currentView === 'seq' && typeof filterDiff === 'function') {
      filterDiff(term);
    }
  });

  // Clear search on Enter navigation
  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      input.value = '';
      if (typeof filterTable === 'function') {
        const tcSearch = document.getElementById('tc-search');
        if (tcSearch) tcSearch.value = '';
        filterTable();
      }
    }
  });
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  initGlobalSearch();

  // Wire sidebar items
  document.querySelectorAll('.sb-item[data-view]').forEach(el => {
    el.addEventListener('click', () => switchView(el));
  });
});