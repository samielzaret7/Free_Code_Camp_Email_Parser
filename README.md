# FreeCodeCamp Email Parser

Automatically parses FreeCodeCamp newsletter emails, extracts course information using an LLM, stages them in Supabase, and provides a Streamlit UI to review and approve courses into a master list.

## Architecture

The project has evolved through two pipeline versions:

### Active Pipeline: Google Apps Script (`google_apps_script/Code.gs`)

The current production ingest runs entirely in Google Apps Script on a timer trigger:

1. **Gmail** — fetches unread emails from `quincy@freecodecamp.org`
2. **Groq LLM** — extracts course name, link, duration, description, and categories from the email HTML
3. **Supabase** — inserts parsed courses into `courses_staging`
4. **Mark as read** — only after successful insert

Setup instructions are in the comments at the top of `Code.gs`. Requires three Script Properties: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `GROQ_API_KEY`.

### Legacy Pipeline: Python (`emlScript.py`)

The original Python-based ingest is no longer active but preserved for reference:

- `emlScript.py` — queries Gmail via [gmail-utils](https://github.com/samielzaret7/gmail-utils), posts to a local FastAPI server
- `eml_reader.py` — alternative input mode that reads `.eml` files from disk
- `api/` — FastAPI server that parsed emails and inserted into Supabase

### Streamlit UI (`ui/app.py`) — Still Active

A review dashboard for approving staged courses into the master list:

- View all items in `courses_staging`
- Filter by sender, subject, or category
- Adjust LLM-proposed categories
- Approve courses to the main table or reject them from staging

## Setup

1. **Google Apps Script (ingest):** Follow the setup instructions in `google_apps_script/Code.gs`.

2. **Streamlit UI (review):**
   ```bash
   cp .env.example .env
   # Fill in your Supabase credentials
   pip install -r requirements.txt
   streamlit run ui/app.py
   ```

## Project Structure

```
├── google_apps_script/    # Active ingest pipeline (Apps Script)
│   ├── Code.gs
│   └── appsscript.json
├── ui/                    # Streamlit approval dashboard
│   ├── app.py
│   └── sb_rest.py
├── api/                   # Legacy FastAPI server
│   ├── main.py
│   ├── parser.py
│   ├── db.py
│   ├── categories.py
│   └── models.py
├── emlScript.py           # Legacy Python ingest
└── eml_reader.py          # Legacy EML file reader
```

## Dependencies

- [gmail-utils](https://github.com/samielzaret7/gmail-utils) — Gmail API utilities (legacy pipeline only)
- [Streamlit](https://streamlit.io/) — approval UI
- [httpx](https://www.python-httpx.org/) — Supabase REST client
- [Groq](https://groq.com/) — LLM inference (via Apps Script)
- [Supabase](https://supabase.com/) — database
