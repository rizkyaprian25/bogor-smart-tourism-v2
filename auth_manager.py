# auth_manager.py
"""
Manajemen Register & Login menggunakan tabel users di Supabase.
Password di-hash menggunakan werkzeug.

PENTING: Tabel users di Supabase harus memiliki kolom `password TEXT`.
Jalankan SQL berikut di Supabase SQL Editor jika belum ada:

    ALTER TABLE users ADD COLUMN IF NOT EXISTS password TEXT;
"""
from supabase_client import supabase
from werkzeug.security import generate_password_hash, check_password_hash


def register_user(email: str, username: str, password: str) -> dict:
    """
    Daftarkan user baru.
    Return: {'success': True, 'user': {...}} atau {'success': False, 'error': '...'}
    """
    try:
        # Cek apakah email sudah terdaftar
        existing = supabase.table('users').select('id').eq('email', email).execute()
        if existing.data:
            return {'success': False, 'error': 'Email sudah terdaftar'}

        # Hash password
        hashed = generate_password_hash(password)

        # Insert ke tabel users
        result = supabase.table('users').insert({
            'email'    : email,
            'username' : username,
            'password' : hashed
        }).execute()

        user = result.data[0] if result.data else {}
        return {'success': True, 'user': user}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def login_user(email: str, password: str) -> dict:
    """
    Login user.
    Return: {'success': True, 'user': {...}} atau {'success': False, 'error': '...'}
    """
    try:
        result = supabase.table('users').select('*').eq('email', email).execute()

        if not result.data:
            return {'success': False, 'error': 'Email tidak ditemukan'}

        user = result.data[0]

        if not check_password_hash(user.get('password', ''), password):
            return {'success': False, 'error': 'Password salah'}

        # Jangan kirim password ke session
        user.pop('password', None)
        return {'success': True, 'user': user}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_user_by_id(user_id: str) -> dict | None:
    """Ambil data user berdasarkan ID (tanpa password)."""
    try:
        result = (
            supabase.table('users')
            .select('id, email, username, created_at')
            .eq('id', user_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None