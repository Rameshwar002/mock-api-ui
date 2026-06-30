/* ═══════════════════════════════════════════
   auth.js — Authentication & Session
═══════════════════════════════════════════ */

const USERS = {
  admin: {
    pass: 'admin123',
    name: 'Admin User',
    role: 'admin',
    initials: 'A',
    color: '#111',
    permissions: ['generate','export','import','knowledge','diagrams','admin','settings'],
  },
  qa_eng: {
    pass: 'qa2024',
    name: 'Alex Chen - Senior QA Eng',
    role: 'qa_eng',
    initials: 'Q',
    color: '#1d6fcf',
    permissions: ['generate','export','import','diagrams','knowledge'],
  },
};

let currentUser = null;

/* ── Validation helpers ── */
function validateUsername(u) {
  if (!u) return 'Username is required.';
  if (u.length < 2) return 'Username must be at least 2 characters.';
  return null;
}
function validatePassword(p) {
  if (!p) return 'Password is required.';
  if (p.length < 4) return 'Password must be at least 4 characters.';
  return null;
}

/* ── Login ── */
function doLogin() {
  const u = document.getElementById('login-user').value.trim();
  const p = document.getElementById('login-pass').value;
  const errEl = document.getElementById('login-err');

  // Clear previous error
  errEl.style.display = 'none';

  // Field validation
  const uErr = validateUsername(u);
  if (uErr) { showLoginErr(uErr); return; }
  const pErr = validatePassword(p);
  if (pErr) { showLoginErr(pErr); return; }

  // Credential check
  const usr = USERS[u];
  if (!usr || usr.pass !== p) {
    showLoginErr('Invalid username or password. Please try again.');
    document.getElementById('login-pass').value = '';
    document.getElementById('login-pass').focus();
    return;
  }

  // Success
  currentUser = { ...usr, username: u };
  errEl.style.display = 'none';
  onLoginSuccess();
}

function showLoginErr(msg) {
  const el = document.getElementById('login-err');
  el.textContent = msg;
  el.style.display = 'block';
}

function onLoginSuccess() {
  // Hide login, show app
  const loginScreen = document.getElementById('login-screen');
  const appEl       = document.getElementById('app');
  if (loginScreen) loginScreen.style.display = 'none';
  if (appEl) {
    appEl.classList.add('active');
    appEl.style.display = 'flex';   // fallback in case CSS hasn't applied yet
  }

  // Update topbar
  document.getElementById('tb-avatar').textContent = currentUser.initials;
  document.getElementById('tb-avatar').style.background = currentUser.color;
  document.getElementById('tb-uname').textContent = currentUser.name;

  // Update sidebar bottom username
  const sbUser = document.getElementById('sb-username-label');
  if (sbUser) sbUser.textContent = currentUser.name.split(' ')[0];

  // Update settings page session info
  const sessionEl = document.getElementById('lbl-session-user');
  if (sessionEl) sessionEl.textContent = currentUser.username + ' (' + currentUser.role + ')';

  // Apply role-based UI restrictions
  applyPermissions();

  // Init post-login tasks
  if (typeof buildPipelineRow === 'function') buildPipelineRow();
  if (typeof checkLlmHealth === 'function') checkLlmHealth();
}

/* ── Permissions ── */
function applyPermissions() {
  if (!currentUser) return;
  const isAdmin = currentUser.role === 'admin';

  // Hide admin-only sidebar items for non-admins
  document.querySelectorAll('[data-admin-only]').forEach(el => {
    el.style.display = isAdmin ? '' : 'none';
  });

  // Hide knowledge management for non-admins
  const kbItem = document.querySelector('.sb-item[data-view="knowledge"]');
  if (kbItem && !isAdmin) kbItem.style.display = 'none';
}

function hasPermission(perm) {
  if (!currentUser) return false;
  return currentUser.permissions.includes(perm);
}

/* ── Logout ── */
function doLogout() {
  currentUser = null;

  // Reset form
  document.getElementById('login-user').value = '';
  document.getElementById('login-pass').value = '';
  document.getElementById('login-err').style.display = 'none';

  // Show login, hide app
  const appEl = document.getElementById('app');
  if (appEl) { appEl.classList.remove('active'); appEl.style.display = 'none'; }
  const loginScreen = document.getElementById('login-screen');
  if (loginScreen) loginScreen.style.display = 'flex';

  // Reset any state
  if (typeof resetAppState === 'function') resetAppState();
}

/* ── getCurrentUser (exported) ── */
function getCurrentUser() { return currentUser; }

/* ── Event listeners ── */
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-login').addEventListener('click', doLogin);
  document.getElementById('btn-logout').addEventListener('click', doLogout);

  document.getElementById('login-pass').addEventListener('keydown', e => {
    if (e.key === 'Enter') doLogin();
  });
  document.getElementById('login-user').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('login-pass').focus();
  });
});