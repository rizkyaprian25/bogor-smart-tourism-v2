# run.py
"""
Entry point untuk menjalankan aplikasi Bogor Smart Tourism
Data: 10 titik wisata | Interval 3 jam | 63 hari | 45.360 records
Model: rf_model_mobil.pkl & rf_model_motor.pkl (dual model)
"""
import sys
from pathlib import Path


def check_dependencies():
    """Cek apakah semua dependencies terinstall"""
    try:
        import flask, pandas, numpy, sklearn, ortools, supabase, pytz
        print("✅ Semua dependencies OK (termasuk pytz untuk timezone WIB)")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Jalankan: pip install -r requirements.txt")
        return False


def check_data_files():
    """Cek keberadaan file data & model"""
    data_dir  = Path("data")
    model_dir = Path("models")

    data_dir.mkdir(exist_ok=True)
    model_dir.mkdir(exist_ok=True)

    checks = {
        # Data files
        "data/data_traffic_final.csv" : "Data traffic historis (45.360 records)",
        "data/master_lokasi.csv"      : "Master lokasi 10 titik wisata",
        
        # Model Mobil
        "models/rf_model_mobil.pkl"   : "Model Random Forest (Mobil)",
        "models/model_metrics_mobil.pkl": "Metrics model (Mobil)",
        
        # Model Motor
        "models/rf_model_motor.pkl"   : "Model Random Forest (Motor)",
        "models/model_metrics_motor.pkl": "Metrics model (Motor)",
        
        # Config files
        "models/rush_hour_config.pkl" : "Konfigurasi Rush Hour",
        "models/peak_weekend_config.pkl": "Konfigurasi Peak Weekend",
    }

    all_ok = True
    for path, label in checks.items():
        if Path(path).exists():
            print(f"   ✅ {label:35s} → {path}")
        else:
            print(f"   ❌ {label:35s} → {path} TIDAK DITEMUKAN")
            all_ok = False

    if not all_ok:
        print("\n⚠️  File model tidak ditemukan!")
        print("   Pastikan Anda sudah menjalankan notebook training:")
        print("   📓 bogor_tourism_training_final.ipynb")
        print("   File yang diperlukan:")
        print("   - rf_model_mobil.pkl & model_metrics_mobil.pkl")
        print("   - rf_model_motor.pkl & model_metrics_motor.pkl")
        print("   - rush_hour_config.pkl & peak_weekend_config.pkl")

    return all_ok


def main():
    print("=" * 60)
    print("🚀 BOGOR SMART TOURISM")
    print("   Hybrid Random Forest + OR-Tools + TomTom")
    print("   Timezone: WIB (Asia/Jakarta)")
    print("   Data: 10 Titik Wisata | Interval 3 Jam | 63 Hari | 45.360 Records")
    print("   Model: Dual RF (Mobil & Motor)")
    print("=" * 60)

    if not check_dependencies():
        sys.exit(1)

    print("\n📋 Cek file:")
    if not check_data_files():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🌐 Starting Flask server...")
    print("   http://localhost:5000")
    print("   Debug time endpoint: http://localhost:5000/api/debug/time")
    print("=" * 60 + "\n")

    from app import app
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == "__main__":
    main()