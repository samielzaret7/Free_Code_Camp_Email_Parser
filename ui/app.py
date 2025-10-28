import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import time
load_dotenv()

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from sb_rest import get_staging, insert_main, delete_staging
from api.categories import ALLOWED_CATEGORIES  

st.set_page_config(page_title="Approve Courses", layout="wide")
st.title("✅ Approve Courses")

st.caption("Review parsed items in staging. Choose which ones to save to the main table.")


rows = get_staging(limit=800)
if not rows:
    st.info("No items in staging. Parse an email first.")
    st.stop()


with st.sidebar:
    st.header("Filters")
    sender_filter = st.text_input("Sender contains", "")
    subject_filter = st.text_input("Subject contains", "")
    cat_filter = st.multiselect("Proposed category contains", ALLOWED_CATEGORIES, max_selections=1)

def row_matches(r):
    if sender_filter and (sender_filter.lower() not in (r.get("source_sender") or "").lower()):
        return False
    if subject_filter and (subject_filter.lower() not in (r.get("source_subject") or "").lower()):
        return False
    if cat_filter:
        
        if cat_filter[0].lower() not in (r.get("category") or "").lower():
            return False
    return True

rows = [r for r in rows if row_matches(r)]
if not rows:
    st.info("No items match your filters.")
    st.stop()


st.subheader("Select items to keep")
keep_map = {}
edit_map = {}

for r in rows:
    with st.expander(f'{r["name"]}  —  {r.get("category") or "Uncategorized"}', expanded=False):
        if r.get("source_subject"):
            st.write(f'**Subject:** {r["source_subject"]}')
        if r.get("source_sender"):
            st.write(f'**From:** {r["source_sender"]}')
        st.write(f'**Link:** {r.get("link") or "—"}')
        st.write(f'**Time:** {r.get("time") or "—"}')
        st.write(f'**Description:** {r.get("description") or "—"}')
        st.write(f'**Model categories:** {(r.get("categories") or [])}')
        st.write(f'**Suggested new category:** {r.get("suggested_new_category") or "—"}')

        
        model_cats = (r.get("categories") or [])
        prefill = [c for c in model_cats if c in ALLOWED_CATEGORIES]
        
        if not prefill and r.get("category") in ALLOWED_CATEGORIES:
            prefill = [r["category"]]

        final_cats = st.multiselect(
        "Final categories (pick 1–3)",
        ALLOWED_CATEGORIES,
        default=prefill[:3],  
        key=f"cats-{r['id']}",
        max_selections=3
        )

        keep = st.checkbox("Keep this course", value=False, key=f"keep-{r['id']}")
        keep_map[r["id"]] = (keep, final_cats)



colA, colB, colC = st.columns([1,1,2])
with colA:
    do_save = st.button("💾 Save selected")
with colB:
    do_reject = st.button("🗑️ Reject selected (remove from staging)")


selected_to_save = []
selected_to_delete = []

for r in rows:
    keep, chosen = keep_map[r["id"]]
    if keep and do_save:
        selected_to_save.append({
        "name": r["name"],
        "link": r.get("link"),
        "time": r.get("time"),
        "description": r.get("description"),
        "category": ", ".join(chosen) if chosen else "Uncategorized",  
        "date_added": r.get("date_added"),
        })

    if (not keep and do_reject) or (keep and do_save):  
        selected_to_delete.append(r["id"])


if do_save and selected_to_save:
    try:
        insert_main(selected_to_save)
        delete_staging(selected_to_delete)
        st.success(f"Saved {len(selected_to_save)} and removed {len(selected_to_delete)} from staging. Page will refresh in 5 seconds.")
        time.sleep(5)
        st.rerun()

    except Exception as e:
        st.error(f"Save failed: {e}")

if do_reject and selected_to_delete and not do_save:
    try:
        delete_staging(selected_to_delete)
        st.info(f"Removed {len(selected_to_delete)} items from staging. Page will refresh in 5 seconds.")
        time.sleep(5)
        st.rerun()
    except Exception as e:
        st.error(f"Reject failed: {e}")
