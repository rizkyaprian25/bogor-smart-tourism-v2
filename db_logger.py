# db_logger.py
"""
Fungsi untuk menyimpan history itinerary dan log prediksi RF ke Supabase.
"""
import json
import traceback
from supabase_client import supabase


def save_history_itinerary(user_id: str, result: dict) -> bool:
    """
    Simpan hasil itinerary ke tabel history_itinerary.
    """
    try:
        display_routes = result.get('display_routes', [])
        
        valid_routes = []
        for route in display_routes:
            if not isinstance(route, dict):
                route = {}
            route.setdefault('total_time', 0)
            route.setdefault('total_distance', 0)
            route.setdefault('route_short', [])
            route.setdefault('is_optimal', False)
            route.setdefault('is_worst', False)
            route.setdefault('rf_time', 0)
            route.setdefault('tomtom_time', 0)
            valid_routes.append(route)
        
        gmaps_segment = result.get('gmaps_segment', {})
        tomtom_time = gmaps_segment.get('travel_time', 0) if gmaps_segment else 0
        tomtom_distance = gmaps_segment.get('distance_km', 0) if gmaps_segment else 0
        
        data = {
            'user_id': user_id,
            'hari': result.get('hari_label', ''),
            'jam_berangkat': result.get('start_time', ''),
            'destinasi_dipilih': json.dumps(result.get('route_ids', [])),
            'rute_optimal': json.dumps(result.get('nodes_info', [])),
            'total_waktu_menit': result.get('total_travel_min', 0),
            'total_jarak_km': result.get('total_distance_km', 0),
            'solver_used': result.get('solver_used', ''),
            'total_permutations': result.get('total_permutations', 0),
            'total_valid_routes': result.get('total_valid_routes', result.get('total_permutations', 0)),
            'optimal_time': result.get('optimal_time', 0),
            'worst_time': result.get('worst_time', 0),
            'savings_minutes': result.get('savings_minutes', 0),
            'savings_percent': result.get('savings_percent', 0),
            'num_destinations': result.get('num_destinations', len(result.get('route_ids', []))),
            'display_routes': json.dumps(valid_routes),
            'has_tomtom': result.get('has_custom_origin', False),
            'tomtom_time': tomtom_time,
            'tomtom_distance': tomtom_distance,
            'vehicle_type': result.get('vehicle_type', 'mobil'),
            'service_times': json.dumps(result.get('service_times', {})),
            'pair_thresholds': json.dumps(result.get('pair_thresholds', {})),
            'is_weekend': result.get('is_weekend', 0),
            'execution_time_ms': result.get('execution_time_ms', 0),
        }
        
        print(f"[db_logger] Menyimpan history untuk user {user_id}...")
        print(f"[db_logger] Data: hari={data['hari']}, jam={data['jam_berangkat']}, waktu={data['total_waktu_menit']} menit, vehicle={data['vehicle_type']}, has_tomtom={data['has_tomtom']}, exec_time={data['execution_time_ms']}ms")
        
        response = supabase.table('history_itinerary').insert(data).execute()
        
        if response.data:
            print(f"[db_logger] ✅ History berhasil disimpan! ID: {response.data[0].get('id', 'unknown')}")
            return True
        else:
            print(f"[db_logger] ❌ Gagal simpan history: tidak ada data returned")
            return False
            
    except Exception as e:
        print(f'[db_logger] ❌ Gagal simpan history: {e}')
        traceback.print_exc()
        return False


def save_log_prediksi(user_id: str, itinerary: list, hari_label: str) -> bool:
    """
    Simpan log prediksi RF per segmen perjalanan ke tabel log_prediksi_rf.
    """
    try:
        records = []
        for step in itinerary:
            if step.get('is_google_maps', False):
                continue
            records.append({
                'user_id': user_id,
                'id_asal': step['from_id'],
                'id_tujuan': step['to_id'],
                'hari': hari_label,
                'jam_berangkat': step['departure'],
                'jarak_km': step['distance_km'],
                'prediksi_menit': step['travel_time'],
                'vehicle_type': step.get('vehicle_type', 'mobil'),
            })
        if records:
            print(f"[db_logger] Menyimpan {len(records)} log prediksi RF...")
            supabase.table('log_prediksi_rf').insert(records).execute()
            print(f"[db_logger] ✅ Log prediksi RF berhasil disimpan!")
        return True
    except Exception as e:
        print(f'[db_logger] ❌ Gagal simpan log RF: {e}')
        traceback.print_exc()
        return False


def get_history_by_user(user_id: str, limit: int = 20) -> list:
    """
    Ambil history itinerary milik user tertentu.
    """
    try:
        print(f"[db_logger] Mengambil history untuk user {user_id}...")
        result = (
            supabase.table('history_itinerary')
            .select('*')
            .eq('user_id', user_id)
            .order('timestamp', desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        print(f"[db_logger] ✅ Ditemukan {len(rows)} history")

        for row in rows:
            for col in ('destinasi_dipilih', 'rute_optimal', 'display_routes', 'service_times', 'pair_thresholds'):
                val = row.get(col)
                if isinstance(val, str):
                    try:
                        row[col] = json.loads(val)
                    except Exception:
                        row[col] = [] if col not in ('service_times', 'pair_thresholds') else {}
                elif val is None:
                    row[col] = [] if col not in ('service_times', 'pair_thresholds') else {}
            
            row.setdefault('total_permutations', 0)
            row.setdefault('total_valid_routes', 0)
            row.setdefault('optimal_time', 0)
            row.setdefault('worst_time', 0)
            row.setdefault('savings_minutes', 0)
            row.setdefault('savings_percent', 0)
            row.setdefault('num_destinations', 0)
            row.setdefault('has_tomtom', False)
            row.setdefault('tomtom_time', 0)
            row.setdefault('tomtom_distance', 0)
            row.setdefault('vehicle_type', 'mobil')
            row.setdefault('pair_thresholds', {})
            row.setdefault('is_weekend', 0)
            row.setdefault('execution_time_ms', 0)

        return rows
    except Exception as e:
        print(f'[db_logger] ❌ Gagal ambil history: {e}')
        traceback.print_exc()
        return []


def get_lokasi_from_db() -> list:
    """
    Ambil master lokasi dari Supabase.
    """
    try:
        result = supabase.table('master_lokasi').select('*').order('id').execute()
        return result.data or []
    except Exception as e:
        print(f'[db_logger] Gagal ambil lokasi: {e}')
        return []