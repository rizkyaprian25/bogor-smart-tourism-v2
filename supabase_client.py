# supabase_client.py
"""
Inisialisasi koneksi Supabase.
Import file ini di mana pun butuh akses database.
"""
from supabase import create_client, Client
import config

# Singleton client 
_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


supabase = get_client()