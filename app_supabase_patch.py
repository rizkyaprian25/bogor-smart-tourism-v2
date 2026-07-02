# ============================================================
# TAMBAHAN UNTUK app.py
# Salin bagian ini dan tambahkan ke app.py Anda
# ============================================================

# 1. Tambahkan import ini di bagian atas app.py
# ---------------------------------------------------
# from auth_manager import register_user, login_user, get_user_by_id
# from db_logger import save_history_itinerary, save_log_prediksi, get_history_by_user
# from functools import wraps


# 2. Tambahkan helper login_required di bawah baris app = Flask(...)
# ---------------------------------------------------
"""
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated
"""


# 3. Salin semua route di bawah ini ke app.py
# ---------------------------------------------------

# ── AUTH ROUTES ─────────────────────────────────────────────

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from auth_manager import register_user, login_user
from db_logger import save_history_itinerary, save_log_prediksi, get_history_by_user

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


# --- Register ---
def route_register_page():
    """GET /register"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

def route_register_post():
    """POST /api/register"""
    data     = request.get_json(force=True)
    email    = data.get('email', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not email or not username or not password:
        return jsonify({'error': 'Semua field wajib diisi'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password minimal 6 karakter'}), 400

    result = register_user(email, username, password)
    if result['success']:
        return jsonify({'status': 'ok', 'redirect': '/login'})
    return jsonify({'error': result['error']}), 400


# --- Login ---
def route_login_page():
    """GET /login"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

def route_login_post():
    """POST /api/login"""
    data     = request.get_json(force=True)
    email    = data.get('email', '').strip()
    password = data.get('password', '')

    result = login_user(email, password)
    if result['success']:
        session['user_id']  = result['user']['id']
        session['username'] = result['user']['username']
        return jsonify({'status': 'ok', 'redirect': '/'})
    return jsonify({'error': result['error']}), 401


# --- Logout ---
def route_logout():
    """GET /logout"""
    session.clear()
    return redirect(url_for('login_page'))


# --- History ---
def route_history_page():
    """GET /history"""
    user_id = session.get('user_id')
    history = get_history_by_user(user_id, limit=20)
    return render_template('history.html', history=history)


# ── MODIFIKASI route /api/plan ───────────────────────────────
# Ganti fungsi plan_itinerary() yang sudah ada dengan ini:

def plan_itinerary_with_db():
    """POST /api/plan — dengan simpan ke Supabase"""
    import json, time
    import config
    from itinerary_engine import build_itinerary

    try:
        data = request.get_json(force=True)

        selected_ids      = [int(i) for i in data.get('selected_ids', [])]
        hari              = int(data.get('hari', 0))
        start_time        = data.get('start_time', '09:00')
        service_times_raw = data.get('service_times', {})
        service_times     = {int(k): int(v) for k, v in service_times_raw.items()}

        if not selected_ids:
            return jsonify({'error': 'Pilih minimal 1 destinasi'}), 400
        if len(selected_ids) > config.MAX_DESTINATIONS:
            return jsonify({'error': f'Maksimal {config.MAX_DESTINATIONS} destinasi'}), 400

        for sid in selected_ids:
            if sid not in service_times:
                service_times[sid] = config.DEFAULT_SERVICE_TIME

        t0     = time.time()
        result = build_itinerary(selected_ids, hari, start_time, service_times)
        result['execution_time_ms'] = round((time.time() - t0) * 1000, 2)

        # ── Simpan ke Supabase jika user login ──────────────
        user_id = session.get('user_id')
        if user_id:
            save_history_itinerary(user_id, result)
            save_log_prediksi(user_id, result['itinerary'], result['hari_label'])

        session['result'] = json.dumps(result, ensure_ascii=False, default=str)
        return jsonify({'status': 'ok', 'redirect': '/itinerary'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ── CARA MENDAFTARKAN SEMUA ROUTE KE app ────────────────────
# Tambahkan baris-baris ini di bawah inisialisasi app di app.py:
"""
app.add_url_rule('/register',     'register_page', route_register_page,      methods=['GET'])
app.add_url_rule('/api/register', 'api_register',  route_register_post,      methods=['POST'])
app.add_url_rule('/login',        'login_page',    route_login_page,          methods=['GET'])
app.add_url_rule('/api/login',    'api_login',     route_login_post,          methods=['POST'])
app.add_url_rule('/logout',       'logout',        route_logout,              methods=['GET'])
app.add_url_rule('/history',      'history_page',  login_required(route_history_page), methods=['GET'])

# Ganti route /api/plan yang lama dengan yang baru:
app.add_url_rule('/api/plan', 'plan_itinerary', login_required(plan_itinerary_with_db), methods=['POST'])
"""
