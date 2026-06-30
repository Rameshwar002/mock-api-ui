/* ═══════════════════════════════════════════
   admin.js — Admin Panel & Settings
═══════════════════════════════════════════ */

/* ── Toggle switches ── */
function initToggles() {
  document.querySelectorAll('.toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('off');
      const isOn = !toggle.classList.contains('off');
      toggle.title = isOn ? 'On' : 'Off';
    });
  });
}

/* ── Render user list (admin only) ── */
function renderUserList() {
  const container = document.getElementById('user-list');
  if (!container) return;

  const USERS_DISPLAY = [
    { initials: 'A', color: '#111',    name: 'Admin User',                role: 'admin',  username: 'admin',  status: 'active' },
    { initials: 'Q', color: '#1d6fcf', name: 'Alex Chen - Senior QA Eng', role: 'qa_eng', username: 'qa_eng', status: 'active' },
  ];

  container.innerHTML = USERS_DISPLAY.map(u => `
    <div class="user-row">
      <div class="user-av" style="background:${u.color}">${u.initials}</div>
      <div class="user-info">
        <div class="user-name">${escHtml(u.name)}</div>
        <div class="user-role">${u.username} &nbsp;&#183;&nbsp; ${u.role === 'admin' ? 'Full access' : 'Test generation, export'}</div>
      </div>
      <span class="user-status-badge us-${u.status}">${u.status === 'active' ? 'Active' : 'Inactive'}</span>
    </div>
  `).join('');
}

/* ── Danger zone actions ── */
function dangerClearCases() {
  if (typeof clearAllCases === 'function') clearAllCases();
}
function dangerResetKnowledge() {
  if (typeof resetKnowledge === 'function') resetKnowledge();
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  initToggles();
  renderUserList();

  const clearBtn = document.getElementById('btn-danger-clear');
  if (clearBtn) clearBtn.addEventListener('click', dangerClearCases);

  const resetBtn = document.getElementById('btn-danger-reset');
  if (resetBtn) resetBtn.addEventListener('click', dangerResetKnowledge);
});
