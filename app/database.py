from supabase import Client, create_client
from supabase.client import ClientOptions

from app.config import get_settings


def get_supabase_client(schema: str = "labs") -> Client:
    """Service-role client — bypasses RLS. Use only for admin/write operations."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key,
        options=ClientOptions(schema=schema),
    )


def get_supabase_anon_client(schema: str = "labs") -> Client:
    """Anon-role client — respects RLS. Use for public read-only operations."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(schema=schema),
    )
