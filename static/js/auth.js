/**
 * Auth Pages — Login & Register
 */

// ── Login ───────────────────────────────────
async function doLogin() {
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const errDiv = document.getElementById('errorMsg');
  
  errDiv.style.display = 'none';

  if (!email || !password) {
    errDiv.textContent = 'Email dan password wajib diisi.';
    errDiv.style.display = 'block';
    return;
  }

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (data.status === 'ok') {
      window.location.href = data.redirect;
    } else {
      errDiv.textContent = data.error || 'Login gagal.';
      errDiv.style.display = 'block';
    }
  } catch (e) {
    errDiv.textContent = 'Terjadi kesalahan. Coba lagi.';
    errDiv.style.display = 'block';
  }
}

// ── Register ────────────────────────────────
async function doRegister() {
  const username = document.getElementById('username').value.trim();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const errDiv = document.getElementById('errorMsg');
  const okDiv = document.getElementById('successMsg');

  errDiv.style.display = 'none';
  okDiv.style.display = 'none';

  if (!username || !email || !password) {
    errDiv.textContent = 'Semua field wajib diisi.';
    errDiv.style.display = 'block';
    return;
  }

  if (password.length < 6) {
    errDiv.textContent = 'Password minimal 6 karakter.';
    errDiv.style.display = 'block';
    return;
  }

  try {
    const res = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password })
    });
    const data = await res.json();

    if (data.status === 'ok') {
      okDiv.textContent = 'Akun berhasil dibuat! Mengarahkan ke login...';
      okDiv.style.display = 'block';
      setTimeout(() => {
        window.location.href = data.redirect;
      }, 1500);
    } else {
      errDiv.textContent = data.error || 'Pendaftaran gagal.';
      errDiv.style.display = 'block';
    }
  } catch (e) {
    errDiv.textContent = 'Terjadi kesalahan. Coba lagi.';
    errDiv.style.display = 'block';
  }
}

// Submit with Enter key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    const loginBtn = document.querySelector('.btn-auth');
    if (loginBtn) loginBtn.click();
  }
});