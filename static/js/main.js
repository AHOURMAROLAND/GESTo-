// ── THEME MODE SOMBRE ──────────────────────────────────────────
(function() {
  const saved = localStorage.getItem('gesto_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('gesto_theme', next);
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = next === 'dark' ? '☀' : '☾';
}

// ── SESSION WARNING ────────────────────────────────────────────
function initSessionWarning(remaining, warningThreshold) {
  const box = document.getElementById('session-warning');
  if (!box) return;

  function checkSession() {
    const r = parseInt(document.body.dataset.sessionRemaining || remaining);
    if (r <= warningThreshold && r > 0) {
      box.classList.add('visible');
      const mins = Math.ceil(r / 60);
      const msg = document.getElementById('session-msg');
      if (msg) msg.textContent = `Votre session expire dans ${mins} minute(s).`;
    } else {
      box.classList.remove('visible');
    }
  }

  setInterval(checkSession, 30000);
  checkSession();
}

function prolongerSession() {
  fetch('/messagerie/api/session/prolonger/', { method: 'POST',
    headers: { 'X-CSRFToken': getCookie('csrftoken') }
  }).then(() => {
    document.getElementById('session-warning').classList.remove('visible');
  }).catch(() => {});
}

// ── NOTIFICATIONS DROPDOWN ─────────────────────────────────────
function toggleNotifs(e) {
  e.stopPropagation();
  const d = document.getElementById('notif-dropdown');
  if (d) d.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  const d = document.getElementById('notif-dropdown');
  if (d && !d.contains(e.target)) d.classList.remove('open');
});

// ── SIDEBAR DESKTOP ET MOBILE ──────────────────────────────────
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const content = document.querySelector('.main-content');
  const overlay = document.getElementById('sidebar-overlay');

  if (sidebar.classList.contains('collapsed')) {
    sidebar.classList.remove('collapsed');
    if (content) content.style.marginLeft = 'var(--sidebar-width)';
    if (overlay) overlay.style.display = 'none';
  } else {
    sidebar.classList.add('collapsed');
    if (content) content.style.marginLeft = '0';
    if (overlay) overlay.style.display = 'none';
  }
}

// ── SPINNER ────────────────────────────────────────────────────
function showSpinner() {
  const el = document.getElementById('spinner-overlay');
  if (el) el.style.display = 'flex';
}

function hideSpinner() {
  const el = document.getElementById('spinner-overlay');
  if (el) el.style.display = 'none';
}

// ── PROGRESS BAR ───────────────────────────────────────────────
function setProgress(pct, label) {
  const fill = document.getElementById('progress-fill');
  const lbl = document.getElementById('progress-label');
  if (fill) fill.style.width = pct + '%';
  if (lbl && label) lbl.textContent = label;
}

// ── ALERTS AUTO-DISMISS ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(function() {
    document.querySelectorAll('.alert-auto').forEach(function(a) {
      a.style.opacity = '0';
      a.style.transition = 'opacity 0.5s';
      setTimeout(function() { a.remove(); }, 500);
    });
  }, 4000);
});

// ── CSRF COOKIE ────────────────────────────────────────────────
function getCookie(name) {
  const v = document.cookie.split(';');
  for (let i = 0; i < v.length; i++) {
    const c = v[i].trim();
    if (c.startsWith(name + '=')) return decodeURIComponent(c.slice(name.length + 1));
  }
  return null;
}

// ── CONFIRM DELETE ─────────────────────────────────────────────
function confirmerSuppression(message) {
  return confirm(message || 'Confirmer la suppression ?');
}

// ── FILTRER SELECT ─────────────────────────────────────────────
function filtrerParSalle(classeId) {
  const select = document.getElementById('select-eleve');
  if (!select) return;
  select.querySelectorAll('option').forEach(function(opt) {
    if (!opt.value) return;
    opt.style.display = (!classeId || opt.dataset.salle === classeId) ? '' : 'none';
  });
  select.value = '';
}