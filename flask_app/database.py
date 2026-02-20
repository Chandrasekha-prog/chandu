import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Initialize Supabase client
def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Warning: SUPABASE_URL or SUPABASE_KEY not found. Using dummy client or will fail.")
        # Return a dummy client or handle gracefully to not crash the app
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()
