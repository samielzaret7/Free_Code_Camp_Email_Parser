import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions  

_sb: Client | None = None

def sb() -> Client:
    global _sb
    if _sb is None:
        _sb = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            options=ClientOptions(
                auto_refresh_token=False,   
                persist_session=False,    
            ),
        )
    return _sb
