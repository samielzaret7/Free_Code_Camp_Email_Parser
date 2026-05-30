import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

_sb: Client | None = None


def _get_supabase_key() -> str:
    """
    Prefer the new secret key; fall back to legacy service_role key
    so nothing breaks while the migration is in progress.
    """
    return os.environ.get("SUPABASE_SECRET_KEY") or os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def sb() -> Client:
    global _sb
    if _sb is None:
        _sb = create_client(
            os.environ["SUPABASE_URL"],
            _get_supabase_key(),
            options=ClientOptions(
                auto_refresh_token=False,
                persist_session=False,
            ),
        )
    return _sb
