from supabase import Client, create_client

from app.config import config

url: str = config.SUPABASE_URL
key: str = config.SUPABASE_API_KEY

supabase: Client = create_client(url, key)
