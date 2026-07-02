# itinerary_engine.py v3

import pickle
import requests
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt, factorial
from itertools import permutations
import time
import random
import warnings
import math

# Suppress sklearn version warnings
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

import config
from optimizer import solve_tsp_open

# ── Global cache ───────────────────────────────────────────────────────────────
_model_mobil         = None
_model_motor         = None
_metrics_mobil       = None
_metrics_motor       = None
_lokasi_df           = None
_traffic_df          = None
_distance_cache_mobil: dict = {}
_distance_cache_motor: dict = {}
_predict_cache:  dict = {}
_rush_hour_config    = None
_peak_weekend_config = None
_congestion_threshold_cache: dict = {}  # cache threshold per-pair

# Current vehicle type (default: mobil)
_current_vehicle = "mobil"

# Batas waktu tunggu maksimal (menit)
MAX_WAIT_TIME = 15

# ── Nama hari ─────────────────────────────────────────────────────────────────
NAMA_HARI = {0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"}

# ── Jam Operasional Tempat Wisata (10 Tempat) ──────────────────────────────────
JAM_BUKA_WISATA = {
    1 : (480,  960),   # Kebun Raya Bogor       08:00-16:00
    2 : (0,    1440),  # Taman Heulang          24 jam
    3 : (540,  1020),  # Rivera Outbound        09:00-17:00
    4 : (480,  1020),  # Tirtania Waterpark     08:00-17:00
    5 : (540,  1020),  # Bogor Aquagame         09:00-17:00
    6 : (360,  1440),  # FullBelly Sports       06:00-00:00 (24:00)
    7 : (480,  1080),  # Kuntum Farmfield       08:00-18:00
    8 : (480,  1050),  # Kampung Durian (WD)    08:00-17:30
    9 : (480,  870),   # Museum PETA            08:00-14:30
    10: (600,  1260),  # BTS Bubulak            10:00-21:00
}

WEEKEND_HOURS = {
    1 : (420, 960),    # Kebun Raya: 07:00-16:00
    9 : (None, None),  # Museum PETA: TUTUP
}

KAMPUNG_DURIAN_HOURS = {
    "weekday": (480, 1050),
    "sabtu":   (480, 1320),
    "minggu":  (480, 1230),
}

# ==============================================================================
# KOREKSI TOMTOM DINAMIS
# ==============================================================================

def get_tomtom_correction(distance_km: float, vehicle_type: str = "mobil") -> int:
    from datetime import datetime
    import pytz
    
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.now(wib)
    current_minutes = now.hour * 60 + now.minute
    current_day = now.weekday()  # 0=Senin, 1=Selasa, ..., 5=Sabtu, 6=Minggu
    is_weekend = current_day >= 5
    
    if vehicle_type == "motor":
        if is_weekend:
            if distance_km <= 23:
                return -10
            else:
                return -15
        else:
            if distance_km <= 23:
                return -2
            else:
                return -5
    
    elif vehicle_type == "mobil":
        if is_weekend:
            if distance_km <= 23:
                return 5
            else:
                return 10
        else:
            if 750 <= current_minutes <= 1080:
                return 5
            return 0
    
    return 0

# ==============================================================================
# VEHICLE TYPE MANAGEMENT
# ==============================================================================

def set_vehicle_type(vehicle_type: str):
    global _current_vehicle
    if vehicle_type not in ["mobil", "motor"]:
        raise ValueError(f"Vehicle type must be 'mobil' or 'motor', got '{vehicle_type}'")
    _current_vehicle = vehicle_type
    print(f"🚗🛵 Vehicle type set to: {vehicle_type}")

def get_vehicle_type() -> str:
    return _current_vehicle

def _load_model(vehicle_type: str = None):
    global _model_mobil, _model_motor, _metrics_mobil, _metrics_motor
    if vehicle_type is None: vehicle_type = _current_vehicle
    if vehicle_type == "mobil":
        if _model_mobil is None:
            with open(config.MODEL_PATH_MOBIL, "rb") as f: _model_mobil = pickle.load(f)
            with open(config.METRICS_PATH_MOBIL, "rb") as f: _metrics_mobil = pickle.load(f)
            print(f"✅ Model MOBIL loaded")
        return _model_mobil, _metrics_mobil
    else:
        if _model_motor is None:
            with open(config.MODEL_PATH_MOTOR, "rb") as f: _model_motor = pickle.load(f)
            with open(config.METRICS_PATH_MOTOR, "rb") as f: _metrics_motor = pickle.load(f)
            print(f"✅ Model MOTOR loaded")
        return _model_motor, _metrics_motor

def clear_caches():
    global _predict_cache
    _predict_cache = {}

# ==============================================================================
# TOMTOM ROUTING API
# ==============================================================================

def get_travel_time_tomtom(origin_lat, origin_lon, dest_lat, dest_lon, vehicle_type: str = "mobil"):
    travel_mode = "car" if vehicle_type == "mobil" else "motorcycle"
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
        f"?routeType=fastest&traffic=true&travelMode={travel_mode}&departAt=now"
        f"&key={config.TOMTOM_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if "routes" not in data or not data["routes"]:
            raise ValueError(f"TomTom: tidak ada rute")
        summary = data["routes"][0]["summary"]
        tt_original = round(summary["travelTimeInSeconds"] / 60, 1)
        dk = round(summary["lengthInMeters"] / 1000, 2)
        correction = get_tomtom_correction(dk, vehicle_type)
        tt = max(1.0, round(tt_original + correction, 1))
        icon = "🚗" if vehicle_type == "mobil" else "🛵"
        print(f"✅ TomTom ({icon}): {tt} mnt | {dk} km (original: {tt_original}, correction: {correction:+d})")
        return {"travel_time": tt, "distance_km": dk, "source": f"TomTom ({vehicle_type})",
                "vehicle_type": vehicle_type, "tomtom_original": tt_original, "correction": correction}
    except Exception as e:
        print(f"⚠️ TomTom error: {e} → fallback")
        return _fallback_osrm(origin_lat, origin_lon, dest_lat, dest_lon, vehicle_type)

def _fallback_osrm(origin_lat, origin_lon, dest_lat, dest_lon, vehicle_type: str = "mobil"):
    url = f"http://router.project-osrm.org/route/v1/driving/{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=false"
    try:
        r = requests.get(url, timeout=8); data = r.json()
        tt_original = round(data["routes"][0]["duration"] / 60, 1)
        dk = round(data["routes"][0]["distance"] / 1000, 2)
        correction = get_tomtom_correction(dk, vehicle_type)
        tt = max(1.0, round(tt_original + correction, 1))
        return {"travel_time": tt, "distance_km": dk, "source": f"OSRM ({vehicle_type})"}
    except:
        dist = haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        correction = get_tomtom_correction(dist, vehicle_type)
        tt = max(1.0, round((dist / 30) * 60 + correction, 1))
        return {"travel_time": tt, "distance_km": round(dist, 2), "source": "Haversine"}

# ==============================================================================
# LOAD FUNCTIONS
# ==============================================================================

def _load_lokasi():
    global _lokasi_df
    if _lokasi_df is None: _lokasi_df = pd.read_csv(config.MASTER_LOKASI_PATH).set_index("ID")
    return _lokasi_df

def _load_traffic():
    global _traffic_df, _distance_cache_mobil, _distance_cache_motor
    if _traffic_df is None:
        _traffic_df = pd.read_csv(config.TRAFFIC_DATA_PATH)
        print(f"📂 Data traffic: {len(_traffic_df)} records")
        if 'Jarak_mobil' in _traffic_df.columns:
            grp = _traffic_df.groupby(['ID_Asal','ID_Tujuan'])['Jarak_mobil'].mean()
            for (a,t), j in grp.items(): _distance_cache_mobil[(int(a),int(t))] = round(float(j),3)
            print(f"✅ Distance cache MOBIL: {len(_distance_cache_mobil)} pasangan OD")
        if 'Jarak_motor' in _traffic_df.columns:
            grp = _traffic_df.groupby(['ID_Asal','ID_Tujuan'])['Jarak_motor'].mean()
            for (a,t), j in grp.items(): _distance_cache_motor[(int(a),int(t))] = round(float(j),3)
            print(f"✅ Distance cache MOTOR: {len(_distance_cache_motor)} pasangan OD")
    return _traffic_df

def _load_rush_hour_config():
    global _rush_hour_config
    if _rush_hour_config is None:
        p = config.RUSH_HOUR_CONFIG_PATH
        if p.exists():
            with open(p,'rb') as f: _rush_hour_config = pickle.load(f)
        else:
            df = pd.read_csv(config.TRAFFIC_DATA_PATH)
            df = df[(df['ID_Asal'].between(1,10))&(df['ID_Tujuan'].between(1,10))&(df['ID_Asal']!=df['ID_Tujuan'])]
            df['Jam_Menit'] = df['Jam'].apply(lambda x: int(x.split(':')[0])*60+int(x.split(':')[1]))
            tc = 'Waktu_Tempuh_mobil' if 'Waktu_Tempuh_mobil' in df.columns else 'Waktu_Tempuh'
            avg = df.groupby('Jam_Menit')[tc].mean(); thr = avg.quantile(0.75)
            rh = avg[avg>thr].index.tolist()
            _rush_hour_config = {'threshold':thr,'rush_hour_jam':rh,'rush_hour_times':[f"{j//60:02d}:{j%60:02d}" for j in sorted(rh)]}
    return _rush_hour_config

def _load_peak_weekend_config():
    global _peak_weekend_config
    if _peak_weekend_config is None:
        p = config.PEAK_WEEKEND_CONFIG_PATH
        if p.exists():
            with open(p,'rb') as f: _peak_weekend_config = pickle.load(f)
        else:
            df = pd.read_csv(config.TRAFFIC_DATA_PATH)
            df = df[(df['ID_Asal'].between(1,10))&(df['ID_Tujuan'].between(1,10))&(df['ID_Asal']!=df['ID_Tujuan'])]
            df['Jam_Menit'] = df['Jam'].apply(lambda x: int(x.split(':')[0])*60+int(x.split(':')[1]))
            df['Is_Weekend'] = (df['Hari_ID']>=5).astype(int); wdf = df[df['Is_Weekend']==1]
            tc = 'Waktu_Tempuh_mobil' if 'Waktu_Tempuh_mobil' in df.columns else 'Waktu_Tempuh'
            avg = wdf.groupby('Jam_Menit')[tc].mean(); thr = avg.quantile(0.75)
            pw = avg[avg>thr].index.tolist()
            _peak_weekend_config = {'threshold':thr,'peak_weekend_jam':pw,'peak_weekend_times':[f"{j//60:02d}:{j%60:02d}" for j in sorted(pw)]}
    return _peak_weekend_config

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371; lat1,lon1,lat2,lon2 = map(radians,[lat1,lon1,lat2,lon2])
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return round(2*R*asin(np.sqrt(a)),3)

def minutes_to_hhmm(m):
    m = int(round(m)); return f"{m//60:02d}:{m%60:02d}"

def hhmm_to_minutes(s):
    if isinstance(s,(int,float)): return int(s)
    h,m = map(int,str(s).split(":")); return h*60+m

def snap_to_3hour(m):
    m = int(m) % 1440; m = max(config.SNAP_MIN, min(config.SNAP_MAX, m))
    slot = round(m / config.SNAP_INTERVAL) * config.SNAP_INTERVAL
    slot = max(config.SNAP_MIN, min(config.SNAP_MAX, slot))
    return minutes_to_hhmm(int(slot))

def get_slot_before_after(m):
    m = int(m) % 1440
    m = max(config.SNAP_MIN, min(config.SNAP_MAX, m))
    interval = config.SNAP_INTERVAL  # 180 menit

    slot_before = (m // interval) * interval
    slot_after  = slot_before + interval

    slot_before = max(config.SNAP_MIN, min(config.SNAP_MAX, slot_before))
    slot_after  = max(config.SNAP_MIN, min(config.SNAP_MAX, slot_after))

    if slot_before == slot_after:
        return minutes_to_hhmm(slot_before), minutes_to_hhmm(slot_after), 0.0

    offset = m - slot_before  # jarak dari slot sebelumnya (0-180)
    
    # Zone 1: 0-60 menit → snap ke bawah (pakai slot_before)
    if offset <= 60:
        return minutes_to_hhmm(slot_before), minutes_to_hhmm(slot_before), 0.0
    
    # Zone 3: 120-180 menit → snap ke atas (pakai slot_after)
    elif offset >= 120:
        return minutes_to_hhmm(slot_after), minutes_to_hhmm(slot_after), 0.0
    
    # Zone 2: 60-120 menit → interpolasi normal
    else:
        weight_after = offset / interval
        return minutes_to_hhmm(slot_before), minutes_to_hhmm(slot_after), round(weight_after, 6)

def get_opening_hours(node_id, is_weekend, hari_id=None):
    if node_id == 8:
        if hari_id == 5: return KAMPUNG_DURIAN_HOURS["sabtu"]
        elif hari_id == 6: return KAMPUNG_DURIAN_HOURS["minggu"]
        else: return KAMPUNG_DURIAN_HOURS["weekday"]
    if is_weekend and node_id in WEEKEND_HOURS: return WEEKEND_HOURS[node_id]
    return JAM_BUKA_WISATA.get(node_id, (0, 1440))

def wait_until_open(node_id, arrival_minutes, is_weekend, hari_id=None):
    buka, tutup = get_opening_hours(node_id, is_weekend, hari_id)
    if buka is None: return float('inf')
    return max(0.0, buka - arrival_minutes)

def get_jam_buka_label(node_id, is_weekend=False, hari_id=None):
    buka, tutup = get_opening_hours(node_id, is_weekend, hari_id)
    if buka is None or tutup is None: return "Tutup"
    if buka == 0 and tutup == 1440: return "24 Jam"
    if node_id == 8:
        if hari_id == 5: return f"{minutes_to_hhmm(buka)} – {minutes_to_hhmm(tutup)} (Sabtu)"
        elif hari_id == 6: return f"{minutes_to_hhmm(buka)} – {minutes_to_hhmm(tutup)} (Minggu)"
        else: return f"{minutes_to_hhmm(buka)} – {minutes_to_hhmm(tutup)} (Weekday)"
    return f"{minutes_to_hhmm(buka)} – {minutes_to_hhmm(tutup)}"

def get_distance_from_data(id_asal, id_tujuan, vehicle_type: str = None):
    _load_traffic()
    if vehicle_type is None: vehicle_type = _current_vehicle
    cache = _distance_cache_mobil if vehicle_type == "mobil" else _distance_cache_motor
    dist = cache.get((id_asal, id_tujuan)) or cache.get((id_tujuan, id_asal))
    if dist: return dist
    lokasi = _load_lokasi()
    return haversine(lokasi.loc[id_asal,"Latitude"],lokasi.loc[id_asal,"Longitude"],
                     lokasi.loc[id_tujuan,"Latitude"],lokasi.loc[id_tujuan,"Longitude"])

def can_optimize_at_time(start_time_str, num_destinations):
    start_min = hhmm_to_minutes(start_time_str)
    end_min = start_min + (num_destinations + 1) * 15
    if end_min > 1440: print(f"⚠️  Estimasi selesai {minutes_to_hhmm(end_min % 1440)}")
    return True, None, None

# ==============================================================================
# FEATURE ENGINEERING
# ==============================================================================

def engineer_row(hari_id, jam_str, id_asal, id_tujuan, jarak, vehicle_type: str = "mobil"):
    jm = hhmm_to_minutes(jam_str)
    is_weekend = 1 if int(hari_id) >= 5 else 0
    rh_cfg = _load_rush_hour_config(); pw_cfg = _load_peak_weekend_config()
    is_rush = 1 if (is_weekend == 0 and jm in rh_cfg['rush_hour_jam']) else 0  # FIX: filter weekday
    is_peak = 1 if (is_weekend == 1 and jm in pw_cfg['peak_weekend_jam']) else 0
    row = {"Hari_ID": int(hari_id), "Is_Weekend": is_weekend, "Jam_Menit": jm,
           "Jam_Sin": np.sin(2*np.pi*jm/1440), "Jam_Cos": np.cos(2*np.pi*jm/1440),
           "Is_RushHour": is_rush, "Is_PeakWeekend": is_peak,
           "ID_Asal": int(id_asal), "ID_Tujuan": int(id_tujuan)}
    if vehicle_type == "mobil":
        row["Jarak_mobil"] = float(jarak)
        row["Jarak_Bin_mobil"] = 0 if jarak<=3 else 1 if jarak<=8 else 2 if jarak<=15 else 3
    else:
        row["Jarak_motor"] = float(jarak)
        row["Jarak_Bin_motor"] = 0 if jarak<=3 else 1 if jarak<=8 else 2 if jarak<=15 else 3
    return row

# ==============================================================================
# PREDICTION
# ==============================================================================

def predict_travel_time(hari_id, jam_str, id_asal, id_tujuan, vehicle_type: str = None):
    if vehicle_type is None: vehicle_type = _current_vehicle
    cache_key = (int(hari_id), str(jam_str), int(id_asal), int(id_tujuan), vehicle_type)
    if cache_key in _predict_cache: return _predict_cache[cache_key]
    model, metrics = _load_model(vehicle_type)
    jarak = get_distance_from_data(int(id_asal), int(id_tujuan), vehicle_type)

    # ── Interpolasi linear antar slot 3 jam ───────────────────────────────────
    jm = hhmm_to_minutes(jam_str)
    slot_b_str, slot_a_str, w = get_slot_before_after(jm)

    if w == 0.0 or slot_b_str == slot_a_str:
        # Tepat di titik slot, tidak perlu interpolasi
        row = engineer_row(hari_id, slot_b_str, id_asal, id_tujuan, jarak, vehicle_type)
        X = pd.DataFrame([row])[metrics["features"]]
        result = round(max(1.0, model.predict(X)[0]), 2)
    else:
        # Prediksi di slot sebelum dan sesudah, lalu interpolasi
        row_b = engineer_row(hari_id, slot_b_str, id_asal, id_tujuan, jarak, vehicle_type)
        row_a = engineer_row(hari_id, slot_a_str, id_asal, id_tujuan, jarak, vehicle_type)
        X = pd.DataFrame([row_b, row_a])[metrics["features"]]
        preds = model.predict(X)
        pred_b, pred_a = float(preds[0]), float(preds[1]) #rumus interpolasi
        result = round(max(1.0, pred_b + (pred_a - pred_b) * w), 2)

    _predict_cache[cache_key] = result
    return result

def predict_batch_cached(all_nodes, hari_id, jam_str, vehicle_type: str = None):
    if vehicle_type is None: vehicle_type = _current_vehicle
    model, metrics = _load_model(vehicle_type)
    jm = hhmm_to_minutes(jam_str)
    is_weekend = 1 if int(hari_id) >= 5 else 0
    rh_cfg = _load_rush_hour_config(); pw_cfg = _load_peak_weekend_config()
    is_rush = 1 if (is_weekend == 0 and jm in rh_cfg['rush_hour_jam']) else 0  # FIX: filter weekday
    is_peak = 1 if (is_weekend == 1 and jm in pw_cfg['peak_weekend_jam']) else 0
    n = len(all_nodes)
    rows_to_predict, pairs_to_predict = [], []
    for i, asal in enumerate(all_nodes):
        for j, tujuan in enumerate(all_nodes):
            if i == j: continue
            ck = (int(hari_id), jam_str, int(asal), int(tujuan), vehicle_type)
            if ck not in _predict_cache:
                jarak = get_distance_from_data(int(asal), int(tujuan), vehicle_type)
                row = engineer_row(hari_id, jam_str, asal, tujuan, jarak, vehicle_type)
                rows_to_predict.append(row); pairs_to_predict.append(ck)
    if rows_to_predict:
        X = pd.DataFrame(rows_to_predict)[metrics["features"]]
        preds = model.predict(X)
        for ck, pred in zip(pairs_to_predict, preds):
            _predict_cache[ck] = round(max(1.0, float(pred)), 2)
    mat = np.zeros((n, n))
    for i, asal in enumerate(all_nodes):
        for j, tujuan in enumerate(all_nodes):
            if i != j: mat[i][j] = _predict_cache[(int(hari_id), jam_str, int(asal), int(tujuan), vehicle_type)]
    return mat

# ==============================================================================
# TIME-DEPENDENT SIMULATION (OPEN PATH)
# ==============================================================================

def simulate_route_open(route_ids, hari_id, start_time_str, service_times, vehicle_type: str = None):
    """Simulasi rute open path (tanpa kembali ke depot)"""
    if vehicle_type is None: vehicle_type = _current_vehicle
    is_weekend = (int(hari_id) >= 5)
    current_min = hhmm_to_minutes(start_time_str)
    total_travel = 0.0
    total_wait = 0.0
    
    for i in range(len(route_ids) - 1): #Rumus Fungsi tujuan
        from_id = route_ids[i]; to_id = route_ids[i + 1]
        tt = predict_travel_time(hari_id, minutes_to_hhmm(current_min), from_id, to_id, vehicle_type)
        arr = current_min + tt; total_travel += tt #waktu tiba tujuan berikutnya
        
        buka, tutup = get_opening_hours(to_id, is_weekend, hari_id)
        if buka is None: return float('inf')
        if arr >= tutup: return float('inf') #batasan time windows
        
        wt = 0 #batasan waktu tunggu
        if arr < buka:
            wt = buka - arr
            if wt > MAX_WAIT_TIME: return float('inf')
        
        total_wait += wt
        current_min = arr + wt
        current_min += service_times.get(to_id, config.DEFAULT_SERVICE_TIME)
    
    return round(total_travel + total_wait, 1)


def perturb_route_open(route_ids, strength=0.3):
    if len(route_ids) <= 2: return route_ids
    dests = route_ids[1:]; n_swaps = max(1, int(len(dests) * strength))
    for _ in range(n_swaps):
        i, j = random.sample(range(len(dests)), 2); dests[i], dests[j] = dests[j], dests[i]
    return [route_ids[0]] + dests


def generate_diverse_starting_routes_open(all_nodes, n_starts=1, vehicle_type: str = None,
                                           hari_id=0, start_time_str="09:00"):
    if vehicle_type is None: vehicle_type = _current_vehicle
    depot = all_nodes[0]; dests = all_nodes[1:]; routes = []
    # Cache sudah di-warm-up dengan hari_id + start_time aktual sebelum fungsi ini dipanggil
    try:
        mat = predict_batch_cached(all_nodes, hari_id, start_time_str, vehicle_type)
        res = solve_tsp_open(mat.tolist())
        routes.append([all_nodes[i] for i in res["route"]])
    except:
        # Fallback: nearest-neighbor dari depot
        dfd = sorted([(d, get_distance_from_data(depot, d, vehicle_type)) for d in dests], key=lambda x: x[1])
        routes.append([depot] + [d for d, _ in dfd])
    return routes


def optimize_tsp_multi_start_open(selected_ids, hari_id, start_time_str, service_times, 
                                   n_starts=1, depot_id=None, vehicle_type: str = None):
    if vehicle_type is None: vehicle_type = _current_vehicle
    if depot_id is None: depot_id = selected_ids[0]
    all_nodes = [depot_id] + [x for x in selected_ids if x != depot_id]
    print(f"\n🚀 OPEN-PATH TSP ({len(selected_ids)} destinasi, {vehicle_type})")
    # Warm-up cache semua pair sekaligus di jam start (satu batch call RF)
    predict_batch_cached(all_nodes, hari_id, start_time_str, vehicle_type)
    start_routes = generate_diverse_starting_routes_open(all_nodes, n_starts, vehicle_type, hari_id, start_time_str)
    best_route, best_time = None, float('inf')
    
    for idx, start_route in enumerate(start_routes):
        current_route = start_route.copy()
        current_time = simulate_route_open(current_route, hari_id, start_time_str, service_times, vehicle_type)
        if current_time == float('inf'): continue
        no_improve = 0
        for _ in range(2):
            current_min = hhmm_to_minutes(start_time_str); dep_times = {depot_id: current_min}
            for i in range(len(current_route) - 1):
                fid = current_route[i]; tid = current_route[i + 1]
                tt = predict_travel_time(hari_id, minutes_to_hhmm(dep_times.get(fid, current_min)), fid, tid, vehicle_type)
                arr = dep_times.get(fid, current_min) + tt
                wt = wait_until_open(tid, arr, (int(hari_id) >= 5), hari_id)
                dep_times[tid] = arr + wt + service_times.get(tid, config.DEFAULT_SERVICE_TIME)
            n = len(all_nodes); mat = np.zeros((n, n))
            for i, asal in enumerate(all_nodes):
                jb = minutes_to_hhmm(dep_times.get(asal, hhmm_to_minutes(start_time_str)))
                for j, tujuan in enumerate(all_nodes):
                    if i != j: mat[i][j] = predict_travel_time(hari_id, jb, asal, tujuan, vehicle_type)
            try:
                res = solve_tsp_open(mat.tolist()); cand = [all_nodes[i] for i in res["route"]]
            except: cand = current_route
            ct = simulate_route_open(cand, hari_id, start_time_str, service_times, vehicle_type)
            if ct == float('inf'): continue
            if ct < current_time: current_route, current_time, no_improve = cand, ct, 0
            else:
                no_improve += 1
                if no_improve >= 2:
                    for s in [0.3]:
                        p = perturb_route_open(current_route, s)
                        pt = simulate_route_open(p, hari_id, start_time_str, service_times, vehicle_type)
                        if pt != float('inf') and pt < current_time:
                            current_route, current_time, no_improve = p, pt, 0; break
                    if no_improve >= 2: break
        if current_time <= best_time: best_time, best_route = current_time, current_route
        print(f"   Start {idx + 1}: {current_time:.1f} mnt" + (" ✅" if current_time <= best_time else ""))
    
    if best_route is None: best_route = all_nodes
    print(f"✅ Best: {best_time:.1f} mnt")
    return best_route

# ==============================================================================
# ROLLING CLOCK
# ==============================================================================

def generate_rolling_clock_matrices(route_ids, hari_id, start_time_str, service_times, vehicle_type: str = None):
    if vehicle_type is None: vehicle_type = _current_vehicle
    is_weekend = (int(hari_id) >= 5); lokasi = _load_lokasi(); rolling = []
    current_min = hhmm_to_minutes(start_time_str)
    for step in range(len(route_ids)-1):
        from_id = route_ids[step]; to_id = route_ids[step+1]
        tt = predict_travel_time(hari_id, minutes_to_hhmm(current_min), from_id, to_id, vehicle_type)
        arr = current_min + tt
        wait_time = 0
        buka, tutup = get_opening_hours(to_id, is_weekend, hari_id)
        if buka is not None and arr < buka: wait_time = buka - arr
        if tt < 15: cat,color,tc,icon = "Cepat","#dcfce7","#15803d","🚀"
        elif tt < 30: cat,color,tc,icon = "Sedang","#fef9c3","#854d0e","⏱️"
        else: cat,color,tc,icon = "Lambat","#fee2e2","#b91c1c","🐢"
        remaining = []; seen = set()
        for nid in route_ids[step:]:
            if nid not in seen: seen.add(nid); remaining.append(nid)
        n = len(remaining)
        if n <= 1: break
        matrix = np.zeros((n,n))
        for i,asal in enumerate(remaining):
            jb2 = minutes_to_hhmm(current_min) if i==0 else start_time_str
            for j,tujuan in enumerate(remaining):
                if i!=j: matrix[i][j] = predict_travel_time(hari_id, jb2, asal, tujuan, vehicle_type)
        labels = [f" {lokasi.loc[nid,'Nama_Tempat']}" for nid in remaining]
        fi = remaining.index(from_id) if from_id in remaining else 0
        ti = remaining.index(to_id) if to_id in remaining else 1
        sel_tt = matrix[fi][ti] if fi!=ti else tt
        rolling.append({"step":step+1,"departure_time":minutes_to_hhmm(current_min),
            "from_node":lokasi.loc[from_id,"Nama_Tempat"],"from_id":from_id,
            "to_node":lokasi.loc[to_id,"Nama_Tempat"],"to_id":to_id,
            "matrix":matrix.tolist(),"nodes":remaining,"labels":labels,"size":n,
            "selected_travel_time":round(sel_tt,1),"selected_category":cat,
            "selected_icon":icon,"selected_color":color,"selected_text_color":tc,
            "wait_time":round(wait_time,1),"jam_buka":get_jam_buka_label(to_id,is_weekend,hari_id)})
        current_min = arr + wait_time
        current_min += service_times.get(to_id, config.DEFAULT_SERVICE_TIME)
    return rolling

# ==============================================================================
# BRUTE FORCE - FLEXIBLE FIRST DESTINATION
# ==============================================================================

# Jumlah top rute yang ingin ditampilkan = jumlah destinasi yang dipilih
# (dinamis, bukan konstanta)

def _bnb_best_for_first_id(first_id, remaining_ids, hari_id, rf_start_time,
                            service_times, vehicle_type):
    """
    Branch & Bound: cari 1 rute terbaik dari first_id tertentu.
    Upper bound awal dari OR-Tools → pruning jauh lebih agresif dari awal DFS.
    """
    is_weekend = (int(hari_id) >= 5)
    start_min  = hhmm_to_minutes(rf_start_time)
    best = {"time": float('inf'), "route": None}

    def _try_update(route):
        t = simulate_route_open(route, hari_id, rf_start_time, service_times, vehicle_type)
        if t != float('inf') and t < best["time"]:
            best["time"] = t; best["route"] = route[:]

    # ── Upper bound 1: OR-Tools (paling ketat) ────────────────────────────────
    try:
        all_nodes = [first_id] + remaining_ids
        mat = predict_batch_cached(all_nodes, hari_id, rf_start_time, vehicle_type)
        res = solve_tsp_open(mat.tolist())
        ortools_route = [all_nodes[i] for i in res["route"]]
        _try_update(ortools_route)
    except Exception:
        pass

    # ── Upper bound 2: nearest-neighbor (fallback jika OR-Tools gagal) ────────
    nn = [first_id]; rem = remaining_ids[:]; cur = first_id
    while rem:
        nxt = min(rem, key=lambda x: get_distance_from_data(cur, x, vehicle_type))
        nn.append(nxt); rem.remove(nxt); cur = nxt
    _try_update(nn)

    # Kalau sudah ada upper bound bagus, DFS akan prune sangat agresif
    def _dfs(path, visited, current_min, accumulated):
        if accumulated >= best["time"]:
            return
        if len(visited) == len(remaining_ids):
            if accumulated < best["time"]:
                best["time"]  = accumulated
                best["route"] = [first_id] + path
            return
        last = path[-1] if path else first_id
        # Urutkan kandidat berdasarkan jarak terdekat dulu (greedy ordering)
        # agar cabang yang bagus dieksplorasi lebih awal → pruning makin efektif
        candidates = sorted(
            [nxt for nxt in remaining_ids if nxt not in visited],
            key=lambda x: get_distance_from_data(last, x, vehicle_type)
        )
        for nxt in candidates:
            tt  = predict_travel_time(hari_id, minutes_to_hhmm(current_min), last, nxt, vehicle_type)
            arr = current_min + tt
            buka, tutup = get_opening_hours(nxt, is_weekend, hari_id)
            if buka is None or arr >= tutup: continue
            wt = max(0.0, buka - arr)
            if wt > MAX_WAIT_TIME: continue
            new_acc = accumulated + tt + wt
            if new_acc >= best["time"]: continue  # pruning
            svc      = service_times.get(nxt, config.DEFAULT_SERVICE_TIME)
            next_min = arr + wt + svc
            visited.add(nxt)
            _dfs(path + [nxt], visited, next_min, new_acc)
            visited.remove(nxt)

    _dfs([], set(), start_min, 0.0)
    return best["route"], best["time"]


def generate_all_routes_flexible(selected_ids, hari_id, start_time_str, service_times,
                                  origin_lat=None, origin_lon=None, vehicle_type: str = None):
    """
    Untuk setiap first_id → cari 1 rute terbaik via Branch & Bound.
    Total hasil = N (jumlah destinasi), bukan hanya 1 best global.
    Paralel antar first_id untuk kecepatan maksimal.
    """
    if vehicle_type is None: vehicle_type = _current_vehicle
    lokasi    = _load_lokasi()
    use_tomtom = (origin_lat is not None and origin_lon is not None)
    print(f"\n🔄 B&B PER FIRST_ID ({vehicle_type}) - {len(selected_ids)} wisata")

    _load_model(vehicle_type); _load_traffic()
    _load_rush_hour_config(); _load_peak_weekend_config()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _process(first_id):
        # ── TomTom ke first_id ──────────────────────────────────────────────
        if use_tomtom:
            dest_lat = float(lokasi.loc[first_id, "Latitude"])
            dest_lon = float(lokasi.loc[first_id, "Longitude"])
            tr = get_travel_time_tomtom(float(origin_lat), float(origin_lon),
                                         dest_lat, dest_lon, vehicle_type)
            tomtom_time = tr["travel_time"]; tomtom_dist = tr["distance_km"]
            start_min  = hhmm_to_minutes(start_time_str)
            arr_first  = start_min + tomtom_time
            buka_f, tutup_f = get_opening_hours(first_id, (int(hari_id) >= 5), hari_id)
            if buka_f is None or arr_first >= tutup_f: return None
            wait_f = max(0.0, buka_f - arr_first)
            if wait_f > MAX_WAIT_TIME: return None
            visit_start_f = arr_first + wait_f
            svc_f    = service_times.get(first_id, config.DEFAULT_SERVICE_TIME)
            depart_f = visit_start_f + svc_f
            gmaps_segment = {
                "step": 0, "from_id": -1, "from_name": " Titik Keberangkatan Anda",
                "to_id": first_id, "to_name": lokasi.loc[first_id, "Nama_Tempat"],
                "departure": start_time_str, "travel_time": tomtom_time,
                "distance_km": tomtom_dist, "arrival": minutes_to_hhmm(arr_first),
                "wait_time": round(wait_f, 1), "visit_start": minutes_to_hhmm(visit_start_f),
                "service_time": svc_f, "depart_next": minutes_to_hhmm(depart_f),
                "is_depot_arrival": False, "is_google_maps": True,
                "source": tr["source"],
                "jam_operasional": get_jam_buka_label(first_id, (int(hari_id) >= 5), hari_id),
                "vehicle_type": vehicle_type}
            rf_start_time  = minutes_to_hhmm(depart_f)
            remaining_ids  = [i for i in selected_ids if i != first_id]
        else:
            tomtom_time = 0; tomtom_dist = 0; gmaps_segment = None
            rf_start_time = start_time_str
            remaining_ids = [i for i in selected_ids if i != first_id]

        # ── Branch & Bound untuk sisa destinasi ────────────────────────────
        if len(remaining_ids) == 0:
            route_ids = [first_id]
            rf_time   = 0.0
        elif len(remaining_ids) == 1:
            route_ids = [first_id] + remaining_ids
            rf_time   = simulate_route_open(route_ids, hari_id, rf_start_time,
                                             service_times, vehicle_type)
            if rf_time == float('inf'): return None
        else:
            # Warm-up prediction cache sebelum B&B
            predict_batch_cached([first_id] + remaining_ids, hari_id, rf_start_time, vehicle_type)
            route_ids, rf_time = _bnb_best_for_first_id(
                first_id, remaining_ids, hari_id, rf_start_time, service_times, vehicle_type)
            if route_ids is None or rf_time == float('inf'): return None

        total_time = round(tomtom_time + rf_time, 1)
        rf_time    = round(rf_time, 2)
        print(f"   ✅ [{lokasi.loc[first_id,'Nama_Tempat']}] {total_time:.1f} mnt")
        return {
            "first_id": first_id, "tomtom_time": tomtom_time, "tomtom_dist": tomtom_dist,
            "rf_time": rf_time, "total_time": total_time, "route_ids": route_ids,
            "gmaps_segment": gmaps_segment, "rf_start_time": rf_start_time
        }

    # Jalankan semua first_id secara paralel — tidak ada early stop
    # karena kita ingin semua N first_id dievaluasi
    all_results = []
    max_workers = min(len(selected_ids), 5)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_process, fid): fid for fid in selected_ids}
        for future in as_completed(futures):
            res = future.result()
            if res is not None:
                all_results.append(res)

    if not all_results:
        raise ValueError(
            f"❌ Tidak ada rute valid!\n- Tempat tutup atau\n- Waktu tunggu > {MAX_WAIT_TIME} menit")

    all_results.sort(key=lambda x: x["total_time"])
    best = all_results[0]
    print(f"\n✅ BEST: {lokasi.loc[best['first_id'],'Nama_Tempat']} - {best['total_time']:.1f} mnt")
    print(f"   Total {len(all_results)} first_id valid dari {len(selected_ids)} destinasi")
    return best, all_results


def generate_all_routes_with_distance_flexible(selected_ids, hari_id, start_time_str, service_times,
                                                origin_lat=None, origin_lon=None, vehicle_type: str = None,
                                                cached_tomtom_results: dict = None,
                                                precomputed_results: list = None):
    """
    Format hasil dari precomputed_results (1 rute terbaik per first_id).
    Jumlah baris tabel = jumlah first_id valid = jumlah destinasi yang dikunjungi.
    Tidak ada komputasi ulang — O(N log N) sort saja.
    """
    if vehicle_type is None: vehicle_type = _current_vehicle
    lokasi     = _load_lokasi()
    use_tomtom = (origin_lat is not None and origin_lon is not None)
    n_dest     = len(selected_ids)
    total_math = factorial(n_dest)

    candidates = []
    for r in (precomputed_results or []):
        route_ids   = r["route_ids"]
        tomtom_time = r["tomtom_time"]
        tomtom_dist = r["tomtom_dist"]
        rf_time     = r["rf_time"]
        total_time  = r["total_time"]
        first_id    = r["first_id"]

        rf_dist    = sum(get_distance_from_data(route_ids[i], route_ids[i+1], vehicle_type)
                         for i in range(len(route_ids) - 1))
        total_dist = tomtom_dist + rf_dist

        if use_tomtom:
            names       = [" Titik Awal"] + [lokasi.loc[nid,"Nama_Tempat"] for nid in route_ids]
            short_names = [" Awal"] + [n[:15]+"..." if len(n)>15 else n for n in names[1:]]
        else:
            names       = [lokasi.loc[nid,"Nama_Tempat"] for nid in route_ids]
            short_names = [n[:20]+"..." if len(n)>20 else n for n in names]

        candidates.append({
            "route_ids": route_ids, "route_names": names, "route_short": short_names,
            "total_time": total_time, "total_distance": round(total_dist, 2),
            "rf_time": rf_time, "tomtom_time": tomtom_time, "first_id": first_id,
            "is_optimal": False, "is_worst": False
        })

    candidates.sort(key=lambda x: x["total_time"])

    if candidates:
        candidates[0]["is_optimal"] = True
        candidates[-1]["is_worst"]  = True
        opt   = candidates[0]["total_time"]
        worst = candidates[-1]["total_time"]
        sav   = worst - opt
        pct   = (sav / worst * 100) if worst > 0 else 0
    else:
        opt = worst = sav = pct = 0

    print(f"⚡ Perbandingan: {len(candidates)} rute (1 optimal per first_id), 0 komputasi ulang")

    return {
        "display_routes":   candidates,
        "total_permutations": total_math,
        "total_valid_routes": len(candidates),
        "optimal_time":     opt,
        "worst_time":       worst,
        "savings_minutes":  round(sav, 1),
        "savings_percent":  round(pct, 1),
        "num_destinations": n_dest,
        "true_optimal_route": candidates[0] if candidates else None,
        "true_optimal_time":  opt,
        "has_tomtom":   use_tomtom,
        "tomtom_time":  candidates[0]["tomtom_time"] if candidates else 0
    }




# ==============================================================================
# CONGESTION THRESHOLD PER-PAIR
# ==============================================================================

def compute_pair_thresholds(node_ids: list, is_weekend: int, vehicle_type: str) -> dict:

    global _congestion_threshold_cache
    cache_key = (tuple(sorted(node_ids)), is_weekend, vehicle_type)
    if cache_key in _congestion_threshold_cache:
        return _congestion_threshold_cache[cache_key]

    df = _load_traffic()
    time_col = f'Waktu_Tempuh_{vehicle_type}'
    if time_col not in df.columns:
        time_col = 'Waktu_Tempuh_mobil'

    df_filtered = df[df['Is_Weekend'] == is_weekend] if 'Is_Weekend' in df.columns else df.copy()
    if 'Is_Weekend' not in df.columns:
        df_filtered = df[(df['Hari_ID'] >= 5) == bool(is_weekend)]

    thresholds = {}
    node_set = list(set(node_ids))
    for i in range(len(node_set)):
        for j in range(i + 1, len(node_set)):
            a, b = node_set[i], node_set[j]
            key = f"{min(a,b)}_{max(a,b)}_{is_weekend}"
            if key in thresholds:
                continue
            # Bidirectional: ambil data A→B dan B→A sekaligus
            mask = (
                ((df_filtered['ID_Asal'] == a) & (df_filtered['ID_Tujuan'] == b)) |
                ((df_filtered['ID_Asal'] == b) & (df_filtered['ID_Tujuan'] == a))
            )
            sub = df_filtered[mask][time_col].dropna()
            if len(sub) < 5:
                # Fallback ke global jika data kurang
                thresholds[key] = {'p25': 16.0, 'p75': 28.0, 'mean': 22.0}
                continue
            thresholds[key] = {
                'p25': round(float(sub.quantile(0.25)), 2),
                'p75': round(float(sub.quantile(0.75)), 2),
                'mean': round(float(sub.mean()), 2),
            }

    _congestion_threshold_cache[cache_key] = thresholds
    return thresholds


def get_congestion_label(travel_time: float, from_id: int, to_id: int,
                         is_weekend: int, thresholds: dict) -> dict:
    """
    Tentukan label kemacetan berdasarkan threshold per-pair.
    
    Kategori:
      🟢 Lancar  : tt <= P25
      🟡 Sedang  : P25 < tt <= mean
      🟠 Padat   : mean < tt <= P75
      🔴 Macet   : tt > P75
    
    Return: { 'label': str, 'css_class': str, 'icon': str }
    """
    key = f"{min(from_id, to_id)}_{max(from_id, to_id)}_{is_weekend}"
    thr = thresholds.get(key)

    if thr is None:
        # Fallback global jika pair tidak ditemukan
        thr = {'p25': 16.0, 'p75': 28.0, 'mean': 22.0}

    p25  = thr['p25']
    mean = thr['mean']
    p75  = thr['p75']

    if travel_time <= p25:
        return {'label': 'Lancar',  'css_class': 'kemacetan-lancar', 'icon': '🟢'}
    elif travel_time <= mean:
        return {'label': 'Sedang',  'css_class': 'kemacetan-sedang', 'icon': '🟡'}
    elif travel_time <= p75:
        return {'label': 'Padat',   'css_class': 'kemacetan-padat',  'icon': '🟠'}
    else:
        return {'label': 'Macet',   'css_class': 'kemacetan-macet',  'icon': '🔴'}


# ==============================================================================
# BUILD ITINERARY — ENTRY POINT
# ==============================================================================

def build_itinerary(selected_ids, hari_id, start_time_str, service_times,
                    origin_lat=None, origin_lon=None, first_destination_id=None,
                    vehicle_type: str = "mobil"):
    set_vehicle_type(vehicle_type); lokasi = _load_lokasi()
    is_weekend = (int(hari_id) >= 5); hari_nama = NAMA_HARI.get(int(hari_id), str(hari_id))
    if len(selected_ids) < config.MIN_DESTINATIONS: 
        raise ValueError(f"Minimal {config.MIN_DESTINATIONS} destinasi.")
    is_possible, _, msg = can_optimize_at_time(start_time_str, len(selected_ids))
    if not is_possible: raise ValueError(msg)
    
    tutup_list = []
    for sid in selected_ids:
        buka, tutup = get_opening_hours(sid, is_weekend, hari_id)
        if buka is None: tutup_list.append(f"• {lokasi.loc[sid,'Nama_Tempat']} — TUTUP")
        elif hhmm_to_minutes(start_time_str) >= tutup:
            tutup_list.append(f"• {lokasi.loc[sid,'Nama_Tempat']} — sudah TUTUP")
    if tutup_list: raise ValueError("❌ Destinasi tutup:\n" + '\n'.join(tutup_list))
    
    _load_rush_hour_config(); _load_peak_weekend_config(); _load_traffic(); clear_caches()
    icon = "🚗" if vehicle_type == "mobil" else "🛵"
    print(f"\n{'='*60}\n🚀 BUILD ITINERARY ({icon} {vehicle_type.upper()}) | {hari_nama} | {start_time_str}\n{'='*60}")
    use_gmaps = (origin_lat is not None and origin_lon is not None)

    # ── Hitung pair_thresholds dan generate_all_routes PARALEL ──
    is_weekend_int = 1 if is_weekend else 0
    from concurrent.futures import ThreadPoolExecutor as _TPE
    with _TPE(max_workers=2) as _ex:
        _ft = _ex.submit(compute_pair_thresholds, selected_ids, is_weekend_int, vehicle_type)
        _fr = _ex.submit(generate_all_routes_flexible,
                         selected_ids, hari_id, start_time_str, service_times,
                         origin_lat, origin_lon, vehicle_type)
        pair_thresholds = _ft.result()
        best_result, all_results = _fr.result()
    print(f"📊 Threshold kemacetan per-pair: {len(pair_thresholds)} kombinasi dihitung")
    
    first_id = best_result["first_id"]
    gmaps_segment = best_result["gmaps_segment"]
    rf_start_time = best_result["rf_start_time"]
    route_ids = best_result["route_ids"]

    # ── STEP 2: Detail simulasi ──
    current_min = hhmm_to_minutes(rf_start_time)
    itinerary_rf = []
    total_dist = best_result["tomtom_dist"] if use_gmaps else 0
    all_departures = {}

    for si in range(len(route_ids) - 1):
        from_id = route_ids[si]; to_id = route_ids[si + 1]
        jm_cur = current_min
        tt = predict_travel_time(hari_id, minutes_to_hhmm(jm_cur), from_id, to_id, vehicle_type)
        arr = current_min + tt; dist = get_distance_from_data(from_id, to_id, vehicle_type)
        wait_time = 0.0
        buka, tutup = get_opening_hours(to_id, is_weekend, hari_id)
        if buka is None: raise ValueError(f"{lokasi.loc[to_id,'Nama_Tempat']} tutup")
        if arr < buka: wait_time = buka - arr #batasan time window
        elif arr >= tutup: raise ValueError(f"{lokasi.loc[to_id,'Nama_Tempat']} sudah tutup")
        svc = service_times.get(to_id, config.DEFAULT_SERVICE_TIME)
        visit_start = arr + wait_time; depart_next = visit_start + svc #waktu keberangkatan
        all_departures[to_id] = minutes_to_hhmm(depart_next)
        # ── Label kemacetan per-pair ──
        cong = get_congestion_label(round(tt, 1), from_id, to_id, is_weekend_int, pair_thresholds)
        itinerary_rf.append({"step":si+1,"from_id":from_id,"from_name":lokasi.loc[from_id,"Nama_Tempat"],
            "to_id":to_id,"to_name":lokasi.loc[to_id,"Nama_Tempat"],
            "departure":minutes_to_hhmm(current_min),"travel_time":round(tt,1),
            "arrival":minutes_to_hhmm(arr),"wait_time":round(wait_time,1),
            "visit_start":minutes_to_hhmm(visit_start),"distance_km":dist,
            "service_time":svc,"depart_next":minutes_to_hhmm(depart_next),
            "is_depot_arrival":False,"is_tomtom":False,
            "source":f"Random Forest ({vehicle_type})",
            "jam_operasional":get_jam_buka_label(to_id,is_weekend,hari_id),"vehicle_type":vehicle_type,
            "congestion_label": cong['label'],
            "congestion_icon":  cong['icon'],
            "congestion_class": cong['css_class'],
            "congestion_threshold": pair_thresholds.get(
                f"{min(from_id,to_id)}_{max(from_id,to_id)}_{is_weekend_int}", {}
            )})
        total_dist += dist
        current_min = depart_next

    # ── Total travel = jumlah travel_time dari itinerary (konsisten dengan tampilan) ──
    rf_travel_total = sum(s["travel_time"] for s in itinerary_rf)
    total_travel = round((best_result["tomtom_time"] if use_gmaps else 0) + rf_travel_total, 2)

    full_itinerary = ([gmaps_segment] if gmaps_segment else []) + itinerary_rf
    for i, step in enumerate(full_itinerary): step["step"] = i + 1
    
    rolling = generate_rolling_clock_matrices(route_ids, hari_id, rf_start_time, service_times, vehicle_type) if len(route_ids) > 1 else []
    
    nodes_info = []; seen_ids = set()
    if use_gmaps:
        nodes_info.append({"id":-1,"name":" Titik Keberangkatan Anda",
            "lat":float(origin_lat),"lon":float(origin_lon),"is_depot":False,"is_origin":True,"jam_operasional":"-"})
        seen_ids.add(-1)
    for nid in route_ids:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes_info.append({"id":nid,"name":lokasi.loc[nid,"Nama_Tempat"],
                "lat":float(lokasi.loc[nid,"Latitude"]),"lon":float(lokasi.loc[nid,"Longitude"]),
                "is_depot":False,"is_origin":False,"jam_operasional":get_jam_buka_label(nid,is_weekend,hari_id)})
    
    route_comparison = generate_all_routes_with_distance_flexible(
        selected_ids, hari_id, start_time_str, service_times,
        origin_lat=origin_lat, origin_lon=origin_lon, vehicle_type=vehicle_type,
        precomputed_results=all_results)
    
    _, metrics = _load_model(vehicle_type)
    solver_name = f"TomTom+OR-Tools+RF ({vehicle_type})" if use_gmaps else f"OR-Tools+RF ({vehicle_type})"
    
    return {"route_ids":route_ids,"nodes_info":nodes_info,"itinerary":full_itinerary,
        "total_travel_min":round(total_travel,2),"total_distance_km":round(total_dist,3),
        "rolling_matrices":rolling,"rf_matrix":[],"matrix_labels":[],"all_departures":all_departures,
        "display_routes":route_comparison["display_routes"],
        "total_permutations":route_comparison["total_permutations"],
        "total_valid_routes": route_comparison.get("total_valid_routes", route_comparison["total_permutations"]),
        "optimal_time":route_comparison["true_optimal_time"],
        "worst_time":route_comparison["worst_time"],
        "savings_minutes":route_comparison["savings_minutes"],
        "savings_percent":route_comparison["savings_percent"],
        "num_destinations":len(selected_ids),"solver_used":solver_name,
        "model_metrics":{"mae":round(metrics["test"]["mae"],4),"mse":round(metrics["test"]["mse"],4),
            "rmse":round(metrics["test"]["rmse"],4),"r2":round(metrics["test"]["r2"],4),
            "cv_mae":round(metrics["cv"]["mae_mean"],4),"cv_std":round(metrics["cv"]["mae_std"],4)},
        "hari_id":int(hari_id),"hari_label":hari_nama,"start_time":start_time_str,
        "service_times":service_times,"has_custom_origin":use_gmaps,
        "gmaps_segment":gmaps_segment,
        "origin_coords":{"lat":origin_lat,"lon":origin_lon} if use_gmaps else None,
        "first_destination_id":first_id,"vehicle_type":vehicle_type,"vehicle_icon":icon,
        "pair_thresholds":pair_thresholds,"is_weekend":is_weekend_int}