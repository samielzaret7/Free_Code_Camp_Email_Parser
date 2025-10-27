import os, httpx
from urllib.parse import urlencode

BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TABLE_MAIN = os.environ.get("TABLE_NAME", "FreeCodeCampMasterList")
TABLE_STAGING = os.environ.get("TABLE_STAGING", "courses_staging")

HEADERS_BASE = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
}

def get_staging(limit=500):
    url = f"{BASE}/rest/v1/{TABLE_STAGING}"
    params = {"select":"*", "order":"created_at.desc", "limit": limit}
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{url}?{urlencode(params)}", headers=HEADERS_BASE)
        r.raise_for_status()
        return r.json()

def insert_main(rows):
    url = f"{BASE}/rest/v1/{TABLE_MAIN}"
    headers = {**HEADERS_BASE, "Content-Type":"application/json", "Prefer":"return=representation"}
    with httpx.Client(timeout=30) as c:
        r = c.post(url, headers=headers, json=rows)
        r.raise_for_status()
        return r.json()

def delete_staging(ids):
    if not ids: return
    url = f"{BASE}/rest/v1/{TABLE_STAGING}"
    headers = {**HEADERS_BASE}
   
    with httpx.Client(timeout=30) as c:
        r = c.delete(f"{url}?id=in.({','.join(str(i) for i in ids)})", headers=headers)
        r.raise_for_status()
        return True
