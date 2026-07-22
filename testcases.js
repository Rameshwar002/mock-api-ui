/* ═══════════════════════════════════════════
   testcases.js — Test Case Table & Export
═══════════════════════════════════════════ */

let cases      = [];
let expandedId = null;
let sortField  = '';
let sortAsc    = true;
let filterTerm = '';

/* ── Helpers ── */
function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function trunc(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : (s || '--'); }
function priClass(p) { return { High: 'p-high', Medium: 'p-med', Low: 'p-low' }[p] ?? 'p-low'; }
function typBadge(t) {
  const map = { Positive: 'badge-positive', Negative: 'badge-negative', Functional: 'badge-functional', Security: 'badge-security' };
  return `<span class="badge ${map[t] ?? 'badge-functional'}">${escHtml(t)}</span>`;
}
function stsBadge(s) {
  const map = { Pass: 'badge-pass', Fail: 'badge-fail', Blocked: 'badge-blocked' };
  return `<span class="badge ${map[s] ?? 'badge-pending'}">${escHtml(s || 'Pending')}</span>`;
}
function priHtml(p) {
  const cls = { High: '#dc2626', Medium: '#b45309', Low: '#71717a' }[p] ?? '#71717a';
  return `<span style="color:${cls};font-weight:700;font-family:var(--mono);font-size:10px">${escHtml(p)}</span>`;
}

/* ── Sort ── */
function sortTable(field) {
  if (sortField === field) sortAsc = !sortAsc;
  else { sortField = field; sortAsc = true; }
  renderTable();
}

/* ── Filter ── */
function filterTable() {
  filterTerm = (document.getElementById('tc-search')?.value || '').toLowerCase();
  renderTable();
}

/* ── Get display cases (filtered + sorted) ── */
function getDisplayCases() {
  let c = [...cases];
  if (filterTerm) {
    c = c.filter(x =>
      Object.values(x).some(v => String(v).toLowerCase().includes(filterTerm))
    );
  }
  if (sortField) {
    c.sort((a, b) => {
      const av = String(a[sortField] ?? '').toLowerCase();
      const bv = String(b[sortField] ?? '').toLowerCase();
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
  }
  return c;
}

/* ── Main render ── */
function renderTable() {
  const display = getDisplayCases();
  const badge   = document.getElementById('tc-count-badge');
  if (badge) badge.textContent = `${cases.length} case${cases.length !== 1 ? 's' : ''}`;

  const tbody = document.getElementById('tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (display.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:28px;color:var(--faint);font-size:12px">
      ${filterTerm ? 'No test cases match your search.' : 'No test cases yet. Upload a PUML file and click Generate.'}
    </td></tr>`;
    return;
  }

  display.forEach(tc => {
    /* ── Data row ── */
    const tr = document.createElement('tr');
    tr.className = 'dr' + (expandedId === tc.tc_id ? ' open' : '');
    tr.innerHTML =
      `<td class="tc-id-c">${escHtml(tc.tc_id)}</td>` +
      `<td class="dim">${escHtml(trunc(tc.module, 16))}</td>` +
      `<td style="font-weight:500">${escHtml(trunc(tc.name, 48))}</td>` +
      `<td>${typBadge(tc.type)}</td>` +
      `<td>${priHtml(tc.priority)}</td>` +
      `<td class="dim" style="font-size:11px">${escHtml(trunc(tc.prerequisite, 55))}</td>` +
      `<td class="dim" style="font-size:11px">${escHtml(trunc(tc.steps, 65))}</td>` +
      `<td class="dim" style="font-size:11px">${escHtml(trunc(tc.expected_output, 55))}</td>` +
      `<td>${stsBadge(tc.status)}</td>` +
      `<td style="text-align:center;vertical-align:middle"><span class="chev">&#9654;</span></td>`;
    tr.addEventListener('click', () => toggleRow(tc.tc_id));
    tbody.appendChild(tr);

    /* ── Expand row ── */
    const er = document.createElement('tr');
    er.className = 'xr';
    er.id = 'xr-' + tc.tc_id;
    er.style.display = expandedId === tc.tc_id ? '' : 'none';

    const typeOptions  = ['Positive','Negative','Functional','Security'].map(s => `<option${tc.type===s?' selected':''}>${s}</option>`).join('');
    const priOptions   = ['High','Medium','Low'].map(s => `<option${tc.priority===s?' selected':''}>${s}</option>`).join('');
    const statusOpts   = ['Pending','Pass','Fail','Blocked'].map(s => `<option${(tc.status||'Pending')===s?' selected':''}>${s}</option>`).join('');
    const createdBy    = typeof getCurrentUser === 'function' && getCurrentUser()?.name || 'Unknown';
    const today        = new Date().toLocaleDateString();

    er.innerHTML = `<td colspan="10">
      <div class="xi">
        <div class="xg">
          <div class="fld">
            <label>TC ID</label>
            <input type="text" data-f="tc_id" value="${escHtml(tc.tc_id)}" style="font-family:var(--mono);font-weight:700"/>
          </div>
          <div class="fld">
            <label>Module</label>
            <input type="text" data-f="module" value="${escHtml(tc.module)}"/>
          </div>
          <div class="fld" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px">
            <div>
              <label style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:700;display:block;margin-bottom:4px">Type</label>
              <select data-f="type">${typeOptions}</select>
            </div>
            <div>
              <label style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:700;display:block;margin-bottom:4px">Priority</label>
              <select data-f="priority">${priOptions}</select>
            </div>
            <div>
              <label style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:700;display:block;margin-bottom:4px">Status</label>
              <select data-f="status">${statusOpts}</select>
            </div>
          </div>
          <div class="fld s3">
            <label>Test Case Name</label>
            <input type="text" data-f="name" value="${escHtml(tc.name)}"/>
          </div>
          <div class="fld s3">
            <label>Prerequisite</label>
            <textarea rows="2" data-f="prerequisite">${escHtml(tc.prerequisite)}</textarea>
          </div>
          <div class="fld s3">
            <label>Test Steps / Process</label>
            <textarea rows="3" data-f="steps">${escHtml(tc.steps)}</textarea>
          </div>
          <div class="fld s3">
            <label>Expected Output</label>
            <textarea rows="2" data-f="expected_output">${escHtml(tc.expected_output)}</textarea>
          </div>
        </div>
        <div class="xfoot">
          <span class="xfoot-meta">By ${escHtml(createdBy)} &nbsp;&#183;&nbsp; ${today}</span>
          <button class="btn-danger" data-del="${escHtml(tc.tc_id)}">&#128465; Remove</button>
        </div>
      </div>
    </td>`;

    // Bind inline edits
    er.querySelectorAll('[data-f]').forEach(el => {
      el.addEventListener('input',  () => patchCase(tc.tc_id, el.dataset.f, el.value));
      el.addEventListener('change', () => patchCase(tc.tc_id, el.dataset.f, el.value));
    });
    er.querySelector('[data-del]').addEventListener('click', e => {
      e.stopPropagation();
      removeCase(tc.tc_id);
    });

    tbody.appendChild(er);
  });
}

/* ── Toggle expand ── */
function toggleRow(id) {
  expandedId = expandedId === id ? null : id;
  renderTable();
  if (expandedId) {
    document.getElementById('xr-' + expandedId)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

/* ── Patch a field ── */
function patchCase(id, field, value) {
  cases = cases.map(c => c.tc_id === id ? { ...c, [field]: value } : c);
}

/* ── Remove ── */
function removeCase(id) {
  if (!confirm('Remove test case ' + id + '?')) return;
  cases = cases.filter(c => c.tc_id !== id);
  if (expandedId === id) expandedId = null;
  renderTable();
  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.disabled = cases.length === 0;
}

/* ── Add ── */
function addCase() {
  const id = 'TC-' + String(cases.length + 1).padStart(3, '0');
  cases.push({
    tc_id: id, module: '', name: 'New Test Case',
    type: 'Functional', priority: 'Medium',
    prerequisite: '', steps: '', expected_output: '', status: 'Pending',
  });
  expandedId = id;
  renderTable();
  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.disabled = false;
}

/* ── Clear all ── */
function clearAllCases() {
  if (!cases.length) { alert('No cases to clear.'); return; }
  if (!confirm(`Clear all ${cases.length} test cases?`)) return;
  cases = []; expandedId = null;
  renderTable();
  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.disabled = true;
}

/* ── Export ── */
async function doExport() {
  if (!cases.length) {
    alert('No test cases to export.\nGenerate test cases first or add them manually.');
    return;
  }

  const exportBtn = document.getElementById('btn-export');
  const origText  = exportBtn?.textContent || '';
  if (exportBtn) { exportBtn.disabled = true; exportBtn.textContent = '⏳ Exporting...'; }

  try {
    const payload = {
      cases,
      filename: (fileTitle || 'testcases') + '_testcases.xlsx',
      title:    fileTitle || 'Test Cases',
    };

    const res = await fetch(BACKEND + '/export', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    // Try to parse error as JSON first
    if (!res.ok) {
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const errData = await res.json();
        throw new Error(errData.error || `Server error ${res.status}`);
      }
      throw new Error(`Export failed with status ${res.status}`);
    }

    // Get blob and trigger download
    const blob     = await res.blob();
    const url      = URL.createObjectURL(blob);
    const filename = (fileTitle || 'testcases') + '_testcases.xlsx';

    // Must append to DOM for Firefox compatibility
    const a = document.createElement('a');
    a.href     = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();

    // Cleanup after short delay
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1500);

    if (exportBtn) { exportBtn.textContent = '✓ Downloaded!'; }
    setTimeout(() => {
      if (exportBtn) { exportBtn.disabled = false; exportBtn.textContent = origText; }
    }, 2000);

  } catch (err) {
    if (exportBtn) { exportBtn.disabled = false; exportBtn.textContent = origText; }
    alert('Export error:\n' + err.message);
  }
}

/* ── Import ── */
function doImport() {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = '.xlsx,.csv,.json';
  input.onchange = () => {
    if (input.files[0]) {
      alert(`Import: "${input.files[0].name}" received.\nFull parse & populate coming via /import endpoint.`);
    }
  };
  input.click();
}

/* ── Reset state (called on logout) ── */
function resetTableState() {
  cases = []; expandedId = null; sortField = ''; sortAsc = true; filterTerm = '';
  renderTable();
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  const addBtn = document.getElementById('btn-add-case-btn');
  if (addBtn) addBtn.addEventListener('click', addCase);

  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.addEventListener('click', doExport);

  const importBtn = document.getElementById('btn-import');
  if (importBtn) importBtn.addEventListener('click', doImport);

  const searchEl = document.getElementById('tc-search');
  if (searchEl) searchEl.addEventListener('input', filterTable);

  // Initial empty render
  renderTable();
});
