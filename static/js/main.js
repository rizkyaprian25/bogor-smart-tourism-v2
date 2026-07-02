/**
 * Global Utility Functions — Bogor Smart Tourism
 */

// ── Toast Notification ──────────────────────
window.showToast = function(message, isError = true) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.style.background = isError ? 'var(--danger)' : 'var(--text)';
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
};

// ── Loading Overlay ─────────────────────────
window.showLoading = function(show, text = 'Memproses...', subText = '') {
  const overlay = document.getElementById('loadingOverlay');
  if (!overlay) return;
  const loadingText = overlay.querySelector('.loading-text');
  const loadingSub = overlay.querySelector('.loading-sub');
  
  if (show) {
    if (text && loadingText) loadingText.textContent = text;
    if (subText && loadingSub) loadingSub.textContent = subText;
    overlay.classList.add('show');
  } else {
    overlay.classList.remove('show');
    if (loadingText) loadingText.textContent = 'Memproses...';
    if (loadingSub) loadingSub.textContent = 'Random Forest & OR-Tools bekerja';
  }
};

// ── Format Utilities ────────────────────────
function formatMinutes(minutes) {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h > 0) return `${h}j ${m}m`;
  return `${m} menit`;
}

function formatTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

// ── API Wrapper ─────────────────────────────
const api = {
  async get(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  },
  async post(url, data) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
};

// ── Export ke global scope ──────────────────
window.utils = {
  formatMinutes,
  formatTime,
  api
};

console.log('Bogor Smart Tourism — ready');