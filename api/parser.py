import os, httpx, json, time
from .models import ParseResult
from .categories import ALLOWED_CATEGORIES
#from dotenv import load_dotenv

#load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


PROMPT = """You are extracting FreeCodeCamp courses from an EMAIL HTML.
Return ONLY valid JSON in this schema:

{{
  "items": [
    {{
      "name": "string (required)",
      "link": "string|null",
      "time": "string|null",
      "description": "string|null",
      "categories": ["string"],      // list of 1–3 categories from the allowed list
      "category_confidence": 0.0,    // 0..1 confidence that all chosen categories fit
      "suggested_new_category": "string|null", // if none fit, propose one
      "date_added": "YYYY-MM-DD|null"
    }}
  ]
}}

Rules:
- Choose up to 3 categories from the allowed list below that best describe each course.
- If no categories apply, set categories=[] and fill suggested_new_category.
- Do NOT invent category names.
- Prefer more specific categories (e.g., 'React' instead of 'Web Development').
- Clean titles and prefer canonical course links.

Allowed categories:
{allowed}

EMAIL HTML:
<<<HTML
{html}
HTML>>>"""


def _ask_groq(model: str, html: str, allowed: list[str]) -> dict:
    content = PROMPT.format(
        html=html,
        allowed="\n- " + "\n- ".join(allowed)
    )
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role":"user","content": content}],
    }
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}

    
    with httpx.Client(timeout=45) as client:
        for attempt in range(6):  
            r = client.post(GROQ_URL, headers=headers, json=body)
            if r.status_code == 200:
                return json.loads(r.json()["choices"][0]["message"]["content"])
            if r.status_code == 429:
                wait = 2 ** attempt
               
                reset = r.headers.get("x-ratelimit-reset-requests") or r.headers.get("retry-after")
                if reset:
                    try:
                        wait = max(wait, int(float(reset)))
                    except:  
                        pass
                print(f"[groq] 429 rate-limited. sleeping {wait}s...")
                time.sleep(wait)
                continue
            
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise httpx.HTTPStatusError(f"{r.status_code}: {detail}", request=r.request, response=r)

   
    return {"items": []}


def extract_items(html: str) -> ParseResult:
    try:
        data = _ask_groq("llama-3.1-8b-instant", html, ALLOWED_CATEGORIES)
    except Exception:
       
        data = _ask_groq("gemma2-9b-it", html, ALLOWED_CATEGORIES)
    return ParseResult(**data)
