# app.py v3
"""
Flask Backend Bogor Smart Tourism v3
- Hari: 0-6 (Senin-Minggu)
- Tanpa depot
- TomTom untuk titik awal bebas
- Zona waktu WIB (Asia/Jakarta) fixed
- FLEXIBLE FIRST DESTINATION
- DUKUNGAN MOBIL & MOTOR (dual model)
- SINKRONISASI SERVICE TIME
"""
import json, time, os, uuid, tempfile
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import pytz
import pandas as pd
import numpy as np

import config
from itinerary_engine import build_itinerary, _load_lokasi, _load_model

app = Flask(__name__)
app.config.from_object(config.Config)

app.jinja_env.globals.update(
    enumerate=enumerate, zip=zip, len=len, range=range,
    dict=dict, list=list, str=str, int=int, float=float,
    min=min, max=max, round=round, abs=abs
)

# Cek model files (dual model: mobil & motor)
if not config.MODEL_PATH_MOBIL.exists():
    raise FileNotFoundError(f"🚨 Model MOBIL tidak ditemukan: {config.MODEL_PATH_MOBIL}")
if not config.MODEL_PATH_MOTOR.exists():
    raise FileNotFoundError(f"🚨 Model MOTOR tidak ditemukan: {config.MODEL_PATH_MOTOR}")
print("✅ Model RF (Mobil & Motor) siap.")
print(f"   🚗 Mobil: {config.MODEL_PATH_MOBIL}")
print(f"   🛵 Motor: {config.MODEL_PATH_MOTOR}")

from auth_manager import register_user, login_user, get_user_by_id
from db_logger import save_history_itinerary, save_log_prediksi, get_history_by_user
from supabase_client import supabase

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ── AUTH ───────────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET"])
def register_page():
    if 'user_id' in session: return redirect(url_for('index'))
    return render_template('register.html')

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True)
    email=data.get('email','').strip(); username=data.get('username','').strip(); password=data.get('password','')
    if not email or not username or not password: return jsonify({'error':'Semua field wajib diisi'}),400
    if len(password)<6: return jsonify({'error':'Password minimal 6 karakter'}),400
    result = register_user(email,username,password)
    if result['success']: return jsonify({'status':'ok','redirect':'/login'})
    return jsonify({'error':result['error']}),400

@app.route("/login", methods=["GET"])
def login_page():
    if 'user_id' in session: return redirect(url_for('index'))
    return render_template('login.html')

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    email=data.get('email','').strip(); password=data.get('password','')
    result = login_user(email,password)
    if result['success']:
        session['user_id']=result['user']['id']; session['username']=result['user']['username']
        return jsonify({'status':'ok','redirect':'/'})
    return jsonify({'error':result['error']}),401

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for('login_page'))

# ── DEBUG ENDPOINT ────────────────────────────────────────────────────────────
@app.route("/api/debug/time")
def debug_time():
    server_now = datetime.now()
    try:
        wib = pytz.timezone('Asia/Jakarta')
        wib_now = datetime.now(wib)
        wib_str = wib_now.strftime("%Y-%m-%d %H:%M:%S")
        wib_hari = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu'][wib_now.weekday()]
    except Exception as e:
        wib_str = f"Error: {e}"
        wib_hari = "Error"
    utc_now = datetime.now(pytz.UTC)
    utc_str = utc_now.strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({
        "server_time_raw": server_now.strftime("%Y-%m-%d %H:%M:%S"),
        "wib_time": wib_str,
        "wib_hari": wib_hari,
        "utc_time": utc_str,
    })

# ── UTAMA ──────────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    lokasi = _load_lokasi().reset_index()
    spots  = lokasi[lokasi["ID"] != 0].to_dict("records")
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.now(wib)
    current_time_info = {
        'hari': ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu'][now.weekday()],
        'jam': now.strftime("%H:%M"),
        'tanggal': now.strftime("%d %B %Y")
    }
    return render_template("index.html", spots=spots, config=config, current_time=current_time_info)

@app.route("/api/plan", methods=["POST"])
@login_required
def plan_itinerary():
    try:
        data = request.get_json(force=True)

        selected_ids      = [int(i) for i in data.get("selected_ids",[])]
        service_times_raw = data.get("service_times",{})
        service_times     = {int(k):int(v) for k,v in service_times_raw.items()}
        vehicle_type      = data.get("vehicle_type", "mobil")

        wib = pytz.timezone('Asia/Jakarta')
        now = datetime.now(wib)
        hari_id    = now.weekday()
        start_time = now.strftime("%H:%M")
        nama_hari = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu'][hari_id]
        
        icon = "🚗" if vehicle_type == "mobil" else "🛵"
        print(f"⏰ Real-time (WIB): {nama_hari}, {start_time} | {icon} {vehicle_type.upper()}")

        origin_lat = data.get("origin_lat")
        origin_lon = data.get("origin_lon")

        if origin_lat is not None: origin_lat = float(origin_lat)
        if origin_lon is not None: origin_lon = float(origin_lon)

        if not selected_ids: return jsonify({"error":"Pilih minimal 1 destinasi"}),400
        if len(selected_ids) < config.MIN_DESTINATIONS:
            return jsonify({"error":f"Minimal {config.MIN_DESTINATIONS} destinasi"}),400
        if len(selected_ids) > config.MAX_DESTINATIONS:
            return jsonify({"error":f"Maksimal {config.MAX_DESTINATIONS} destinasi"}),400

        for sid in selected_ids:
            if sid not in service_times: service_times[sid] = config.DEFAULT_SERVICE_TIME

        t0 = time.time()
        result = build_itinerary(
            selected_ids, hari_id, start_time, service_times,
            origin_lat=origin_lat, origin_lon=origin_lon,
            first_destination_id=None,
            vehicle_type=vehicle_type
        )
        t_total = time.time() - t0
        result["execution_time_ms"] = round(t_total * 1000, 2)
        print(f"⏱️ TOTAL build_itinerary: {t_total:.2f}s")

        print(f"✅ Itinerary berhasil ({vehicle_type}):")
        print(f"   Route IDs: {result['route_ids']}")
        print(f"   First destination (auto): {result.get('first_destination_id', 'N/A')}")
        print(f"   Total waktu: {result['total_travel_min']} menit")

        # ── Simpan ke Supabase di background agar tidak menunda response ──────
        user_id = session.get('user_id')
        if user_id:
            import threading, copy
            result_copy = copy.deepcopy(result)
            def _bg_save(uid, res):
                try:
                    ok = save_history_itinerary(uid, res)
                    if ok:
                        save_log_prediksi(uid, res['itinerary'], res['hari_label'])
                        print(f"[app] ✅ History tersimpan (bg)!")
                    else:
                        print(f"[app] ⚠️ History GAGAL tersimpan (bg)!")
                except Exception as ex:
                    print(f"[app] ❌ Error bg save: {ex}")
            threading.Thread(target=_bg_save, args=(user_id, result_copy), daemon=True).start()

        # ── Simpan result ke file temp (bukan session cookie) ─────────────────
        # Session cookie limit ~4KB, result 7 dest bisa >10KB → cookie overflow
        result_id = str(uuid.uuid4())
        result_path = os.path.join(tempfile.gettempdir(), f"itinerary_{result_id}.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, default=str)
        session["result_id"] = result_id  # hanya simpan UUID kecil di cookie
        return jsonify({"status":"ok","redirect":"/itinerary"})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}),500

def _load_result_from_session():
    """Baca result dari file temp berdasarkan result_id di session."""
    result_id = session.get("result_id")
    if not result_id: return None
    result_path = os.path.join(tempfile.gettempdir(), f"itinerary_{result_id}.json")
    if not os.path.exists(result_path): return None
    with open(result_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/itinerary")
@login_required
def itinerary_page():
    result = _load_result_from_session()
    if not result: return redirect(url_for("index"))
    return render_template("itinerary.html", result=result)

@app.route("/dashboard")
@login_required
def dashboard_page():
    result = _load_result_from_session()
    if not result: return redirect(url_for("index"))
    return render_template("dashboard.html", result=result)

@app.route("/history")
@login_required
def history_page():
    history = get_history_by_user(session.get('user_id'), limit=20)
    return render_template('history.html', history=history)

@app.route("/history/<history_id>")
@login_required
def history_detail_page(history_id):
    user_id = session.get('user_id')
    try:
        res = supabase.table('history_itinerary').select('*').eq('id',history_id).eq('user_id',user_id).execute()
        if not res.data: return redirect(url_for('history_page'))
        h = res.data[0]
    except: return redirect(url_for('history_page'))

    # Parse JSON fields
    for col in ('destinasi_dipilih','rute_optimal','display_routes','service_times','pair_thresholds'):
        val = h.get(col)
        if isinstance(val,str):
            try: 
                h[col] = json.loads(val)
            except: 
                h[col] = [] if col not in ('service_times','pair_thresholds') else {}
        elif val is None: 
            h[col] = [] if col not in ('service_times','pair_thresholds') else {}

    if not isinstance(h.get('display_routes'),list): 
        h['display_routes'] = []
    
    valid = []
    for r in h['display_routes']:
        if isinstance(r,str):
            try: r = json.loads(r)
            except: r = {}
        if not isinstance(r,dict): r = {}
        r.setdefault('total_time', 0)
        r.setdefault('total_distance', 0)
        r.setdefault('route_short', [])
        r.setdefault('is_optimal', False)
        r.setdefault('is_worst', False)
        r.setdefault('rf_time', 0)
        r.setdefault('tomtom_time', 0)
        valid.append(r)
    h['display_routes'] = valid

    # Set default values
    for col in ('total_permutations','optimal_time','worst_time','savings_minutes',
                'savings_percent','num_destinations','has_tomtom','tomtom_time',
                'tomtom_distance','vehicle_type'):
        h.setdefault(col, 0)

    vehicle_type = h.get('vehicle_type', 'mobil')
    service_times = h.get('service_times', {})
    pair_thresholds = h.get('pair_thresholds', {})
    is_weekend_int = h.get('is_weekend', 0)
    
    # Konversi key service_times ke int
    service_times = {int(k): v for k, v in service_times.items()}
    
    segments = []
    rute = h.get('rute_optimal', [])
    lokasi = _load_lokasi()
    jam = h.get('jam_berangkat', '09:00')
    
    try:
        log_res = supabase.table('log_prediksi_rf').select('*')\
            .eq('user_id', user_id)\
            .eq('hari', h.get('hari', ''))\
            .eq('vehicle_type', h.get('vehicle_type', 'mobil'))\
            .order('timestamp', desc=False).execute()
        log_lookup = {(r['id_asal'],r['id_tujuan']):r for r in (log_res.data or [])}
        from itinerary_engine import haversine, hhmm_to_minutes, minutes_to_hhmm
        
        cur = hhmm_to_minutes(jam)
        
        for i in range(len(rute) - 1):
            fn = rute[i]
            tn = rute[i + 1]
            fid = fn['id']
            tid = tn['id']
            
            is_tomtom = (fn.get('is_origin', False) or fid == -1)
            
            if is_tomtom:
                tt = h.get('tomtom_time', 10)
                dk = h.get('tomtom_distance', 3)
                svc = service_times.get(tid, config.DEFAULT_SERVICE_TIME)
            else:
                le = log_lookup.get((fid, tid))
                if le:
                    tt = le['prediksi_menit']
                    dk = le['jarak_km']
                else:
                    try:
                        dk = haversine(
                            lokasi.loc[fid, 'Latitude'], lokasi.loc[fid, 'Longitude'],
                            lokasi.loc[tid, 'Latitude'], lokasi.loc[tid, 'Longitude']
                        )
                        tt = dk * 3
                    except:
                        dk = 0
                        tt = 10
                svc = service_times.get(tid, config.DEFAULT_SERVICE_TIME)
            
            arr = cur + tt
            
            # ── Label kemacetan per-pair ──
            from itinerary_engine import get_congestion_label
            if not is_tomtom:
                cong = get_congestion_label(round(tt, 1), fid, tid, is_weekend_int, pair_thresholds)
            else:
                cong = {'label': '-', 'icon': '🛰️', 'css_class': 'kemacetan-sedang'}
            
            segments.append({
                'from_name': fn['name'],
                'to_name': tn['name'],
                'departure': minutes_to_hhmm(cur),
                'travel_time': round(tt, 1),
                'arrival': minutes_to_hhmm(arr),
                'distance_km': round(dk, 3),
                'service_time': svc,
                'depart_next': minutes_to_hhmm(arr + svc),
                'is_depot_arrival': False,
                'is_tomtom': is_tomtom,
                'congestion_label': cong['label'],
                'congestion_icon':  cong['icon'],
                'congestion_class': cong['css_class'],
            })
            cur = arr + svc
            
    except Exception as e:
        print(f'[history_detail] Error: {e}')
        import traceback; traceback.print_exc()
    
    h['segments'] = segments
    h['has_tomtom'] = any(s.get('is_tomtom', False) for s in segments)
    h['vehicle_icon'] = "🚗" if vehicle_type == "mobil" else "🛵"
    
    return render_template('history_detail.html', h=h)

@app.route("/dashboard/<history_id>")
@login_required
def dashboard_history_page(history_id):
    """Dashboard teknikal untuk sesi history tertentu"""
    user_id = session.get('user_id')
    try:
        res = supabase.table('history_itinerary').select('*').eq('id', history_id).eq('user_id', user_id).execute()
        if not res.data:
            return redirect(url_for('history_page'))
        h = res.data[0]
    except:
        return redirect(url_for('history_page'))

    # Parse JSON fields
    for col in ('destinasi_dipilih', 'rute_optimal', 'display_routes', 'service_times', 'pair_thresholds'):
        val = h.get(col)
        if isinstance(val, str):
            try:
                h[col] = json.loads(val)
            except:
                h[col] = [] if col not in ('service_times', 'pair_thresholds') else {}
        elif val is None:
            h[col] = [] if col not in ('service_times', 'pair_thresholds') else {}

    # Normalize display_routes
    if not isinstance(h.get('display_routes'), list):
        h['display_routes'] = []

    valid_routes = []
    for r in h['display_routes']:
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except:
                r = {}
        if not isinstance(r, dict):
            r = {}
        r.setdefault('total_time', 0)
        r.setdefault('total_distance', 0)
        r.setdefault('route_short', [])
        r.setdefault('is_optimal', False)
        r.setdefault('is_worst', False)
        r.setdefault('rf_time', 0)
        r.setdefault('tomtom_time', 0)
        valid_routes.append(r)
    h['display_routes'] = valid_routes

    # Set default values
    for col in ('total_permutations', 'optimal_time', 'worst_time', 'savings_minutes',
                'savings_percent', 'num_destinations', 'has_tomtom', 'tomtom_time',
                'tomtom_distance', 'vehicle_type', 'execution_time_ms'):
        h.setdefault(col, 0)

    vehicle_type = h.get('vehicle_type', 'mobil')
    service_times = h.get('service_times', {})
    pair_thresholds = h.get('pair_thresholds', {})
    is_weekend_int = h.get('is_weekend', 0)

    service_times = {int(k): v for k, v in service_times.items()}

    segments = []
    rute = h.get('rute_optimal', [])
    lokasi = _load_lokasi()
    jam = h.get('jam_berangkat', '09:00')

    log_lookup = {}
    try:
        log_res = supabase.table('log_prediksi_rf').select('*')\
            .eq('user_id', user_id)\
            .eq('hari', h.get('hari', ''))\
            .eq('vehicle_type', h.get('vehicle_type', 'mobil'))\
            .order('timestamp', desc=False).execute()
        log_lookup = {(r['id_asal'], r['id_tujuan']): r for r in (log_res.data or [])}
    except:
        pass

    try:
        from itinerary_engine import haversine, hhmm_to_minutes, minutes_to_hhmm

        cur = hhmm_to_minutes(jam)
        total_travel = 0.0
        total_distance = 0.0

        for i in range(len(rute) - 1):
            fn = rute[i]
            tn = rute[i + 1]
            fid = fn['id']
            tid = tn['id']

            is_tomtom = (fn.get('is_origin', False) or fid == -1)

            if is_tomtom:
                tt = h.get('tomtom_time', 10)
                dk = h.get('tomtom_distance', 3)
                svc = service_times.get(tid, config.DEFAULT_SERVICE_TIME)
            else:
                le = log_lookup.get((fid, tid))
                if le:
                    tt = le['prediksi_menit']
                    dk = le['jarak_km']
                else:
                    try:
                        dk = haversine(
                            lokasi.loc[fid, 'Latitude'], lokasi.loc[fid, 'Longitude'],
                            lokasi.loc[tid, 'Latitude'], lokasi.loc[tid, 'Longitude']
                        )
                        tt = dk * 3
                    except:
                        dk = 0
                        tt = 10
                svc = service_times.get(tid, config.DEFAULT_SERVICE_TIME)

            arr = cur + tt
            total_travel += tt
            total_distance += dk

            from itinerary_engine import get_congestion_label
            if not is_tomtom:
                cong = get_congestion_label(round(tt, 1), fid, tid, is_weekend_int, pair_thresholds)
            else:
                cong = {'label': '-', 'icon': '🛰️', 'css_class': 'kemacetan-sedang'}

            segments.append({
                'step': i + 1,
                'from_id': fid,
                'from_name': fn['name'],
                'to_id': tid,
                'to_name': tn['name'],
                'departure': minutes_to_hhmm(cur),
                'travel_time': round(tt, 1),
                'arrival': minutes_to_hhmm(arr),
                'distance_km': round(dk, 3),
                'service_time': svc,
                'depart_next': minutes_to_hhmm(arr + svc),
                'is_depot_arrival': False,
                'is_tomtom': is_tomtom,
                'is_google_maps': is_tomtom,
                'congestion_label': cong['label'],
                'congestion_icon': cong['icon'],
                'congestion_class': cong['css_class'],
                'source': 'TomTom' if is_tomtom else f'Random Forest ({vehicle_type})',
                'wait_time': 0,
                'jam_operasional': '-',
            })
            cur = arr + svc

    except Exception as e:
        print(f'[dashboard_history] Error building segments: {e}')
        import traceback
        traceback.print_exc()

    # Load model metrics
    try:
        _, metrics = _load_model(vehicle_type)
        model_metrics = {
            'mae': round(metrics["test"]["mae"], 4),
            'mse': round(metrics["test"]["mse"], 4),
            'rmse': round(metrics["test"]["rmse"], 4),
            'r2': round(metrics["test"]["r2"], 4),
            'cv_mae': round(metrics["cv"]["mae_mean"], 5),
            'cv_std': round(metrics["cv"]["mae_std"], 5),
        }
    except:
        model_metrics = {'mae': 0.354, 'mse': 0.288, 'rmse': 0.537, 'r2': 0.9965, 'cv_mae': 0.368, 'cv_std': 0.004}

    # Build display_routes
    display_routes = h.get('display_routes', [])
    if display_routes:
        display_routes.sort(key=lambda x: x.get('total_time', 0))
        if len(display_routes) > 0:
            display_routes[0]['is_optimal'] = True
        if len(display_routes) > 1:
            display_routes[-1]['is_worst'] = True

    all_times = [r.get('total_time', 0) for r in display_routes if r.get('total_time', 0) > 0]
    optimal_time = min(all_times) if all_times else h.get('optimal_time', 0)
    worst_time = max(all_times) if all_times else h.get('worst_time', 0)
    savings_minutes = round(worst_time - optimal_time, 1) if worst_time > optimal_time else h.get('savings_minutes', 0)
    savings_percent = round((worst_time - optimal_time) / worst_time * 100, 1) if worst_time > 0 else h.get('savings_percent', 0)
    total_permutations = h.get('total_permutations', len(display_routes))

    # Build rolling matrices dari segments (konsisten dengan Detail Segmen)
    rolling_matrices = []
    try:
        rf_segments = [seg for seg in segments if not seg.get('is_google_maps') and not seg.get('is_depot_arrival')]
        
        if len(rf_segments) >= 1:
            for step_idx, seg in enumerate(rf_segments):
                from_id = seg['from_id']
                to_id = seg['to_id']
                departure_time = seg['departure']
                selected_tt = seg['travel_time']
                
                remaining_ids = []
                seen = set()
                for s in rf_segments[step_idx:]:
                    if s['from_id'] not in seen:
                        remaining_ids.append(s['from_id'])
                        seen.add(s['from_id'])
                last_seg = rf_segments[-1]
                if last_seg['to_id'] not in seen:
                    remaining_ids.append(last_seg['to_id'])
                
                n = len(remaining_ids)
                if n <= 1:
                    continue
                
                labels = []
                for nid in remaining_ids:
                    try:
                        labels.append(f" {lokasi.loc[nid, 'Nama_Tempat']}")
                    except:
                        labels.append(f" ID {nid}")
                
                matrix = []
                for i, asal in enumerate(remaining_ids):
                    row = []
                    for j, tujuan in enumerate(remaining_ids):
                        if i == j:
                            row.append(0)
                        else:
                            log_key = (asal, tujuan)
                            if log_key in log_lookup:
                                row.append(round(log_lookup[log_key]['prediksi_menit'], 1))
                            else:
                                try:
                                    dk = haversine(
                                        lokasi.loc[asal, 'Latitude'], lokasi.loc[asal, 'Longitude'],
                                        lokasi.loc[tujuan, 'Latitude'], lokasi.loc[tujuan, 'Longitude']
                                    )
                                    row.append(round(dk * 3, 1))
                                except:
                                    row.append(0)
                    matrix.append(row)
                
                fi = remaining_ids.index(from_id) if from_id in remaining_ids else 0
                ti = remaining_ids.index(to_id) if to_id in remaining_ids else min(1, n-1)
                
                cat, color, tc, icon = 'Sedang', '#fef9c3', '#854d0e', '⏱️'
                if selected_tt < 15:
                    cat, color, tc, icon = 'Cepat', '#dcfce7', '#15803d', '🚀'
                elif selected_tt >= 30:
                    cat, color, tc, icon = 'Lambat', '#fee2e2', '#b91c1c', '🐢'
                
                rolling_matrices.append({
                    'step': step_idx + 1,
                    'departure_time': departure_time,
                    'from_node': lokasi.loc[from_id, 'Nama_Tempat'] if from_id in lokasi.index else f"ID {from_id}",
                    'from_id': from_id,
                    'to_node': lokasi.loc[to_id, 'Nama_Tempat'] if to_id in lokasi.index else f"ID {to_id}",
                    'to_id': to_id,
                    'matrix': matrix,
                    'nodes': remaining_ids,
                    'labels': labels,
                    'size': n,
                    'selected_travel_time': round(selected_tt, 1),
                    'selected_category': cat,
                    'selected_icon': icon,
                    'selected_color': color,
                    'selected_text_color': tc,
                    'wait_time': 0,
                    'jam_buka': '-',
                })
    except Exception as e:
        print(f'[dashboard_history] ❌ Failed to build rolling matrices: {e}')

    result = {
        'route_ids': [n['id'] for n in rute if not n.get('is_origin')],
        'nodes_info': rute,
        'itinerary': segments,
        'total_travel_min': round(total_travel, 2),
        'total_distance_km': round(total_distance, 3),
        'rolling_matrices': rolling_matrices,
        'display_routes': display_routes,
        'total_permutations': total_permutations,
        'optimal_time': optimal_time,
        'worst_time': worst_time,
        'savings_minutes': savings_minutes,
        'savings_percent': savings_percent,
        'num_destinations': len([n for n in rute if not n.get('is_origin')]),
        'solver_used': h.get('solver_used', ''),
        'has_custom_origin': h.get('has_tomtom', False),
        'hari_id': 0,
        'hari_label': h.get('hari', ''),
        'start_time': h.get('jam_berangkat', '09:00'),
        'service_times': service_times,
        'vehicle_type': vehicle_type,
        'vehicle_icon': '🚗' if vehicle_type == 'mobil' else '🛵',
        'pair_thresholds': pair_thresholds,
        'is_weekend': is_weekend_int,
        'execution_time_ms': h.get('execution_time_ms', 0),
        'model_metrics': model_metrics,
    }

    return render_template('dashboard.html', result=result)

# ── API PUBLIK ────────────────────────────────────────────────────────────────
@app.route("/api/locations")
def get_locations():
    from itinerary_engine import get_jam_buka_label
    lokasi = _load_lokasi().reset_index()
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.now(wib)
    hari_id = now.weekday()
    is_weekend = hari_id >= 5
    records = lokasi.to_dict("records")
    for r in records:
        if r.get("ID") != 0:
            r["jam_operasional"] = get_jam_buka_label(r["ID"], is_weekend, hari_id)
    return jsonify(records)

@app.route("/api/model/metrics")
def get_model_metrics():
    vehicle = request.args.get('vehicle', 'mobil')
    from itinerary_engine import _load_model as load_vehicle_model
    _, metrics = load_vehicle_model(vehicle)
    return jsonify(metrics)

@app.route("/api/traffic/pattern")
def traffic_pattern():
    import pandas as pd
    vehicle = request.args.get('vehicle', 'mobil')
    df = pd.read_csv(config.TRAFFIC_DATA_PATH)
    df["Jam_H"] = df["Jam"].apply(lambda x: int(x.split(":")[0]))
    time_col = 'Waktu_Tempuh_mobil' if vehicle == 'mobil' else 'Waktu_Tempuh_motor'
    agg = df.groupby(["Hari_ID","Jam_H"])[time_col].agg(["mean","std","min","max"]).reset_index()
    return jsonify(agg.to_dict("records"))

@app.route("/api/traffic/pair_pattern")
def traffic_pair_pattern():
    """
    API untuk grafik pola kemacetan PER PASANGAN OD (Origin-Destination).
    
    Parameter:
        vehicle    : 'mobil' atau 'motor'
        is_weekend : 0 atau 1
        from_id    : ID node asal
        to_id      : ID node tujuan
    
    Return:
        [
            {
                "jam_h": 0,
                "jam_label": "00:00",
                "mean": 15.2,
                "min": 10.1,
                "max": 22.5
            },
            ...
        ]
    """
    import pandas as pd
    import numpy as np
    
    vehicle = request.args.get('vehicle', 'mobil')
    is_weekend = int(request.args.get('is_weekend', 0))
    from_id_str = request.args.get('from_id', '')
    to_id_str = request.args.get('to_id', '')
    
    if not from_id_str or not to_id_str:
        return jsonify({"error": "from_id and to_id required"}), 400
    
    try:
        from_id = int(from_id_str)
        to_id = int(to_id_str)
    except ValueError:
        return jsonify({"error": "from_id and to_id must be integers"}), 400
    
    # Load data traffic
    df = pd.read_csv(config.TRAFFIC_DATA_PATH)
    
    # Filter by weekend/weekday
    if 'Is_Weekend' in df.columns:
        df = df[df['Is_Weekend'] == is_weekend]
    else:
        if is_weekend:
            df = df[df['Hari_ID'] >= 5]
        else:
            df = df[df['Hari_ID'] < 5]
    
    # Tentukan kolom waktu tempuh berdasarkan vehicle
    if vehicle == 'motor' and 'Waktu_Tempuh_motor' in df.columns:
        time_col = 'Waktu_Tempuh_motor'
    elif vehicle == 'mobil' and 'Waktu_Tempuh_mobil' in df.columns:
        time_col = 'Waktu_Tempuh_mobil'
    else:
        waktu_cols = [c for c in df.columns if 'Waktu_Tempuh' in c]
        time_col = waktu_cols[0] if waktu_cols else df.select_dtypes(include=[np.number]).columns[0]
    
    print(f"📊 [pair_pattern] vehicle={vehicle}, time_col={time_col}, is_weekend={is_weekend}, {from_id}→{to_id}")
    
    # Filter untuk pasangan spesifik
    mask = ((df['ID_Asal'] == from_id) & (df['ID_Tujuan'] == to_id))
    df_filtered = df[mask]
    
    if df_filtered.empty:
        # Fallback: gunakan bidirectional + semua data
        mask = (
            ((df['ID_Asal'] == from_id) & (df['ID_Tujuan'] == to_id)) |
            ((df['ID_Asal'] == to_id) & (df['ID_Tujuan'] == from_id))
        )
        df_filtered = df[mask]
    
    if df_filtered.empty:
        # Fallback: semua data
        print(f"⚠️ [pair_pattern] Tidak ada data untuk {from_id}→{to_id}, menggunakan semua data")
        df_filtered = df
    
    # Agregasi per 3 jam
    agg = df_filtered.groupby('Jam')[time_col].agg(['mean', 'min', 'max']).reset_index()
    agg.columns = ['jam', 'mean', 'min', 'max']
    agg['jam_h'] = agg['jam'].apply(lambda x: int(x.split(':')[0]) if isinstance(x, str) else 0)
    agg = agg.sort_values('jam_h')
    
    # Isi slot kosong
    all_slots = pd.DataFrame({
        'jam': config.TIME_SLOTS,
        'jam_h': [int(t.split(':')[0]) for t in config.TIME_SLOTS]
    })
    agg = all_slots.merge(agg, on=['jam', 'jam_h'], how='left')
    
    # Fill NaN
    overall_mean = df_filtered[time_col].mean() if not df_filtered.empty else 20
    agg['mean'] = agg['mean'].fillna(overall_mean)
    agg['min'] = agg['min'].fillna(agg['mean'] * 0.7)
    agg['max'] = agg['max'].fillna(agg['mean'] * 1.3)
    
    agg['mean'] = agg['mean'].round(2)
    agg['min'] = agg['min'].round(2)
    agg['max'] = agg['max'].round(2)
    agg['jam_label'] = agg['jam']
    agg = agg.sort_values('jam_h')
    
    result = agg[['jam_h', 'jam_label', 'mean', 'min', 'max']].to_dict('records')
    
    print(f"✅ [pair_pattern] Mengembalikan {len(result)} slot untuk {from_id}→{to_id}")
    
    return jsonify(result)

@app.route("/api/history/<history_id>", methods=["DELETE"])
@login_required
def delete_history(history_id):
    user_id = session.get('user_id')
    try:
        check = supabase.table('history_itinerary').select('id').eq('id',history_id).eq('user_id',user_id).execute()
        if not check.data: return jsonify({'status':'error','error':'Tidak ditemukan'}),404
        supabase.table('history_itinerary').delete().eq('id',history_id).execute()
        return jsonify({'status':'ok'})
    except Exception as e:
        return jsonify({'status':'error','error':str(e)}),500

if __name__ == "__main__":
    app.run(debug=True, port=5000)