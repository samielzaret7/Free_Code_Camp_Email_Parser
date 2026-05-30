"""
emlScript.py

Two input modes:
- EML mode: reads .eml files from /EML_Files, parses, moves to /Processed
- Gmail mode: queries Gmail and parses messages directly (no downloads)

Keeps:
- Daily logs folder logs/YYYY-MM-DD/
- Per-run log files:
    FreeCodeCampRequestLog_1.log, FreeCodeCampRequestLog_2.log, ...

A2 semantics:
- Emails are marked READ only after successful downstream POSTs.
- Duplicate constraint responses can be treated as idempotent success.
"""

import requests
import logging
from datetime import date
import os
import time
import asyncio
import random
from typing import List, Dict, Optional

from gmail_utils import get_email_items_main, mark_messages_as_read
from eml_reader import eml_to_html


# -----------------------
# Ingest configuration
# -----------------------

ENABLE_POLLING = False     # True = run forever, False = run once then idle forever (honcho-safe)
POLL_SECONDS = 60          # Used only when ENABLE_POLLING=True


# -----------------------
# Logging setup (per-run file)
# -----------------------

def _next_log_file_path(base_dir: str, prefix: str) -> str:
    """
    Creates logs/YYYY-MM-DD/ and returns the next available log filename:
    FreeCodeCampRequestLog_1.log, FreeCodeCampRequestLog_2.log, ...
    """
    today = str(date.today())
    day_dir = os.path.join(base_dir, "logs", today)
    os.makedirs(day_dir, exist_ok=True)

    n = 1
    while True:
        candidate = os.path.join(day_dir, f"{prefix}_{n}.log")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def setup_logging() -> str:
    """
    Sets up logging to a per-run file (and console).
    Returns the log file path.
    """
    # Important if you run repeatedly (polling loop or interactive)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    cwd = os.getcwd()
    log_file = _next_log_file_path(cwd, "FreeCodeCampRequestLog")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w", encoding="utf-8"),
            logging.StreamHandler(),  # keep console output; remove if you only want file
        ],
    )

    logging.info("Logging initialized. log_file=%s", log_file)
    return log_file


# -----------------------
# Async main (honcho-safe)
# -----------------------

async def main():
    if ENABLE_POLLING:
        print(f"Polling mode ENABLED (interval={POLL_SECONDS}s)")

        while True:
            log_file = setup_logging()
            print(f"Log file: {log_file}")

            try:
                request_main()
            except Exception:
                logging.exception("Ingestion loop failed")

            await asyncio.sleep(POLL_SECONDS)

    else:
        log_file = setup_logging()
        print("Polling mode DISABLED (single run)")
        print(f"Log file: {log_file}")

        try:
            request_main()
        except Exception:
            logging.exception("Single ingestion run failed")

        # Keep process alive so honcho does not kill other services
        while True:
            await asyncio.sleep(3600)


# -----------------------
# POST to inbound (A2)
# -----------------------

def request_func(html_list: List[Dict[str, str]], SCOPES: Optional[List[str]] = None):
    """
    Posts each item to /inbound.
    If SCOPES is provided and gmail_message_id exists, marks the source email as read
    ONLY when all items from that email have posted successfully.

    Idempotent behavior:
    - If API returns a duplicate constraint error (23505), treat as success for that item.
    """
    print("Request function started.")
    logging.info("Request function started.")

    email_status: dict[str, dict[str, int]] = {}
    total_items = 0

    for item in html_list:
        msg_id = item.get("gmail_message_id")

        if msg_id:
            if msg_id not in email_status:
                email_status[msg_id] = {"total": 0, "ok": 0}
            email_status[msg_id]["total"] += 1

        data = {
            "from": item.get("From", ""),
            "subject": item.get("Subject", ""),
            "html": item.get("Body", "<html><body>No content found</body></html>"),
        }

        try:
            r = requests.post("http://127.0.0.1:8000/inbound", json=data, timeout=30)

            if not r.ok:
                body_text = (r.text or "")

                if ("duplicate key value violates unique constraint" in body_text) or ('"code":"23505"' in body_text):
                    logging.warning("Duplicate detected (treating as success). status=%s", r.status_code)
                    if msg_id:
                        email_status[msg_id]["ok"] += 1
                    time.sleep(random.uniform(2.5, 4.0))
                    continue

                logging.error("POST failed. status=%s text=%r", r.status_code, body_text[:2000])
                time.sleep(random.uniform(2.5, 4.0))
                continue

            try:
                resp = r.json()
            except Exception:
                logging.error("Non-JSON response. status=%s text=%r", r.status_code, (r.text or "")[:2000])
                time.sleep(random.uniform(2.5, 4.0))
                continue

            staged = int(resp.get("staged", 0))
            total_items += staged

            if msg_id:
                email_status[msg_id]["ok"] += 1

            logging.info("Request posted successfully: %s", resp)
            print(resp)

            time.sleep(random.uniform(2.5, 4.0))

        except Exception as e:
            logging.exception("Error when posting item: %s", item)
            print(f"There was an error when posting the item {item}")
            print(f"Exception: {e}")
            time.sleep(random.uniform(2.5, 4.0))

    if SCOPES:
        to_mark_read = [
            mid for mid, stats in email_status.items()
            if stats["total"] > 0 and stats["ok"] == stats["total"]
        ]
        logging.info("Emails eligible to mark as read: %s", len(to_mark_read))

        if to_mark_read:
            mark_messages_as_read(SCOPES, to_mark_read, logger=logging.getLogger(__name__))

    total_items_string = f"Total Items Staged: {total_items}"
    print(total_items_string)
    logging.info(total_items_string)


# -----------------------
# Main driver (no longer configures logging)
# -----------------------

def request_main():
    print("Request main started")

    parent_folder = os.getcwd()
    print(f"Parent folder: {parent_folder}")

    logging.info("Request main started.")

    try:
        USE_GMAIL = True
        SCOPES: Optional[List[str]] = None

        if USE_GMAIL:
            SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
            query = "from:quincy@freecodecamp.org is:unread"
            format = "raw"

            html_list = get_email_items_main(
                SCOPES=SCOPES,
                query=query,
                format=format,
                body_preference=("html", "plain"),
                max_results=None,
                mark_as_read=False,  # A2: do NOT mark read here
                logger=logging.getLogger(__name__),
            )
        else:
            html_list = eml_to_html(parent_folder)

        logging.info("Emails fetched: %s", len(html_list))
        print(f"Emails fetched: {len(html_list)}")

        request_func(html_list, SCOPES=SCOPES)

    except Exception as e:
        logging.exception("Exception on main")
        print(f"Exception: {e}")

    logging.info("Request main finished.")
    print("Request main finished.")


if __name__ == "__main__":
    # If you run emlScript directly (not via honcho), make it work:
    setup_logging()
    request_main()
