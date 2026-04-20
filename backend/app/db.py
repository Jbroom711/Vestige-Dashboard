"""Supabase client factory.

Two clients, two purposes:
  - `anon_client()` for per-request authenticated calls. RLS applies.
  - `service_client()` for admin/system work (scheduled fee computation,
    migrations, etc.). BYPASSES RLS — never expose to user input paths.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def anon_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def service_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def user_client(access_token: str) -> Client:
    """Per-request client that sets the user's JWT so RLS policies apply."""
    s = get_settings()
    client = create_client(s.supabase_url, s.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
