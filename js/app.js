/* ═══════════════════════════════════════════
   app.js — Main Entry Point
   Wires all modules together on DOMContentLoaded
═══════════════════════════════════════════ */

/* ── Reset full app state (called on logout) ── */
function resetAppState() {
  if (typeof resetUploadState   === 'function') resetUploadState();
  if (typeof resetTableState    === 'function') resetTableState();
  if (typeof resetPipeline      === 'function') resetPipeline();
  if (typeof resetDiagramState  === 'function') resetDiagramState();
  if (typeof resetSeqState      === 'function') resetSeqState();

  // Reset export button
  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.disabled = true;

  // Navigate back to TC view
  if (typeof navigateTo === 'function') navigateTo('tc');
}

/* ── Wire topbar actions ── */
function initTopbar() {
  // Export button (wired here as a central listener)
  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.addEventListener('click', () => {
    if (typeof doExport === 'function') doExport();
  });

  // Import button
  const importBtn = document.getElementById('btn-import');
  if (importBtn) importBtn.addEventListener('click', () => {
    if (typeof doImport === 'function') doImport();
  });

  // Add Case button
  const addBtn = document.getElementById('btn-add-case-btn');
  if (addBtn) addBtn.addEventListener('click', () => {
    if (typeof addCase === 'function') addCase();
  });

  // Global search
  const searchEl = document.getElementById('global-search');
  if (searchEl) {
    searchEl.addEventListener('input', e => {
      const term = e.target.value.trim();
      if (!term) return;
      // Delegate to current view
      if (typeof currentView !== 'undefined') {
        if (currentView === 'tc') {
          const tcSearch = document.getElementById('tc-search');
          if (tcSearch) { tcSearch.value = term; }
          if (typeof filterTable === 'function') filterTable();
        }
        if (currentView === 'seq' && typeof filterDiff === 'function') {
          filterDiff(term.toLowerCase());
        }
      }
    });
  }
}

/* ── Wire "Related Tools" links ── */
function initRelatedLinks() {
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      if (typeof navigateTo === 'function') navigateTo(el.dataset.nav);
    });
  });
}

/* ── Init everything ── */
document.addEventListener('DOMContentLoaded', () => {
  initTopbar();
  initRelatedLinks();

  // Initial table render (empty state)
  if (typeof renderTable === 'function') renderTable();

  console.log('[Multi-Tool Suite] App initialised.');
});
