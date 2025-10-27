import os
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from .parser import extract_items
from .db import sb
from .categories import ALLOWED_CATEGORIES


TABLE_STAGING = os.environ.get("TABLE_STAGING", "courses_staging")
TODAY = date.today().isoformat()

app = FastAPI(title="FCC Email Ingest")

@app.post("/inbound")
async def inbound(req: Request):
    payload = await req.json()
    html = payload.get("html") or payload.get("text")
    if not html:
        raise HTTPException(status_code=400, detail="Missing html/text body")

    sender = payload.get("from")
    subject = payload.get("subject")

    parsed = extract_items(html)

    rows = []
    for it in parsed.items:
        cats = (getattr(it, "categories", None) or [])
        cats = [c for c in cats if c in ALLOWED_CATEGORIES]
        best = cats[0] if cats else "Uncategorized"

        rows.append({
            "source_sender": sender,
            "source_subject": subject,
            "name": it.name,
            "link": it.link,
            "time": it.time,
            "description": it.description,
            "categories": cats or None,                    
            "category": best,
            "category_confidence": getattr(it, "category_confidence", None),
            "suggested_new_category": getattr(it, "suggested_new_category", None),
            "date_added": TODAY,                          
        })

    if rows:
        sb().table(TABLE_STAGING).insert(rows).execute()

    return {"staged": len(rows)}

