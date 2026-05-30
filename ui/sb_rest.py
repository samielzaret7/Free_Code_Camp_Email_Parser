import os, httpx
from urllib.parse import urlencode


def _get_config(key: str, default: str | None = None) -> str:
    """
    Read a config value.  Priority:
      1. Streamlit secrets  (st.secrets)   — used on Streamlit Cloud
      2. Environment variable              — used locally with .env
    """
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Missing required config: {key}")
    return val


def _get_supabase_key() -> str:
    """Prefer the new secret key; fall back to legacy service_role key."""
    try:
        return _get_config("SUPABASE_SECRET_KEY")
    except RuntimeError:
        return _get_config("SUPABASE_SERVICE_ROLE_KEY")


BASE = _get_config("SUPABASE_URL").rstrip("/")
KEY = _get_supabase_key()
TABLE_MAIN = _get_config("TABLE_NAME", "FreeCodeCampMasterList")
TABLE_STAGING = _get_config("TABLE_STAGING", "courses_staging")

HEADERS_BASE = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
}


def get_staging(limit=500):
    url = f"{BASE}/rest/v1/{TABLE_STAGING}"
    params = {"select": "*", "order": "created_at.desc", "limit": limit}
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{url}?{urlencode(params)}", headers=HEADERS_BASE)
        r.raise_for_status()
        return r.json()


def insert_main(rows):
    url = f"{BASE}/rest/v1/{TABLE_MAIN}"
    headers = {**HEADERS_BASE, "Content-Type": "application/json", "Prefer": "return=representation"}
    with httpx.Client(timeout=30) as c:
        r = c.post(url, headers=headers, json=rows)
        r.raise_for_status()
        return r.json()


def delete_staging(ids):
    if not ids:
        return
    # Validate that all IDs are integers to prevent injection via the in.() filter
    safe_ids = [str(int(i)) for i in ids]
    url = f"{BASE}/rest/v1/{TABLE_STAGING}"
    with httpx.Client(timeout=30) as c:
        r = c.delete(f"{url}?id=in.({','.join(safe_ids)})", headers=HEADERS_BASE)
        r.raise_for_status()
        return True
