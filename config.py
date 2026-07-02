# config.py
"""
Konfigurasi sistem Bogor Smart Tourism v3
Data: 10 titik wisata (tanpa depot ID=0)
      Interval 3 jam, 00:00-21:00 (8 slot)
      63 hari (1 Jan - 4 Mar 2026) → 45.360 records
      Hari: 0-6 (Senin-Minggu)
      FITUR: Dukungan Mobil & Motor dengan model terpisah
      FOKUS: TomTom menggunakan jalan utama

PENTING: Semua credential (API key, Supabase key, secret key) dibaca dari
environment variable (.env), TIDAK di-hardcode di file ini.
File .env berisi nilai asli dan WAJIB ada di .gitignore — jangan pernah
di-commit ke git.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load variabel dari file .env di root project
load_dotenv()

BASE_DIR      = Path(__file__).parent.absolute()
DATA_DIR      = BASE_DIR / "data"
MODELS_DIR    = BASE_DIR / "models"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR    = BASE_DIR / "static"

MASTER_LOKASI_PATH       = DATA_DIR   / "master_lokasi.csv"
TRAFFIC_DATA_PATH        = DATA_DIR   / "data_traffic_final.csv"

# Model paths - MOBIL & MOTOR TERPISAH
MODEL_PATH_MOBIL         = MODELS_DIR / "rf_model_mobil.pkl"
MODEL_PATH_MOTOR         = MODELS_DIR / "rf_model_motor.pkl"
METRICS_PATH_MOBIL       = MODELS_DIR / "model_metrics_mobil.pkl"
METRICS_PATH_MOTOR       = MODELS_DIR / "model_metrics_motor.pkl"

# Config paths (shared)
RUSH_HOUR_CONFIG_PATH    = MODELS_DIR / "rush_hour_config.pkl"
PEAK_WEEKEND_CONFIG_PATH = MODELS_DIR / "peak_weekend_config.pkl"

# Untuk kompatibilitas
MODEL_PATH               = MODEL_PATH_MOBIL
METRICS_PATH             = METRICS_PATH_MOBIL

# ── Node Constants ─────────────────────────────────────────────────────────────
DEPOT_ID             = 0
MIN_DESTINATIONS     = 2
MAX_DESTINATIONS     = 5
MIN_SERVICE_TIME     = 15
MAX_SERVICE_TIME     = 360
DEFAULT_SERVICE_TIME = 60

TRAIN_TEST_RATIO = 0.2

# ── Time Slots (interval 3 jam) ────────────────────────────────────────────────
TIME_SLOTS = ["00:00","03:00","06:00","09:00","12:00","15:00","18:00","21:00"]

SNAP_MIN      = 0     # 00:00
SNAP_MAX      = 1260  # 21:00 (7 slot × 3 jam = 21:00)
SNAP_INTERVAL = 180   # 3 jam

USER_START_MIN = 0     # 00:00 — user bisa mulai kapan saja
USER_START_MAX = 1260  # 21:00 — batas atas input user

# ── TomTom API ─────────────────────────────────────────────────────────────────
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY")

# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ── Validasi: gagal cepat & jelas kalau .env belum diisi ────────────────────────
_REQUIRED_ENV = {
    "TOMTOM_API_KEY": TOMTOM_API_KEY,
    "SUPABASE_URL"  : SUPABASE_URL,
    "SUPABASE_KEY"  : SUPABASE_KEY,
}
_missing = [k for k, v in _REQUIRED_ENV.items() if not v]
if _missing:
    raise RuntimeError(
        "❌ Environment variable berikut belum di-set: "
        f"{', '.join(_missing)}.\n"
        "   Buat file .env di root project (lihat .env.example) "
        "atau set langsung di environment sistem/Docker."
    )

# ── Vehicle Types ──────────────────────────────────────────────────────────────
VEHICLE_TYPES = {
    "mobil": {"name": "Mobil", "icon": "🚗", "tomtom_mode": "car"},
    "motor": {"name": "Motor", "icon": "🛵", "tomtom_mode": "motorcycle"},
}
DEFAULT_VEHICLE = "mobil"

# ── Routing Preferences (FOKUS JALAN UTAMA) ────────────────────────────────────
ROUTING_PREFERENCES = {
    "avoid": "unpavedRoads,ferries",
    "route_type": "shortest",
    "traffic": False,
}

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError(
            "❌ FLASK_SECRET_KEY belum di-set di .env. "
            "Generate dengan: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    # DEBUG dikontrol lewat .env supaya tidak ke-push True ke production.
    # Default False jika tidak diset (aman by default).
    DEBUG                 = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    TEMPLATES_AUTO_RELOAD = DEBUG

for dir_path in [DATA_DIR, MODELS_DIR, STATIC_DIR/"css", STATIC_DIR/"js", TEMPLATES_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)