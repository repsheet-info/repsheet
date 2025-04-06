import os
from os import path
import pandas as pd
import sqlite3
from contextlib import contextmanager
from typing import NamedTuple, Optional
import re
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

PARLIMENTARY_SESSIONS = (
    "44-1",
    "43-2",
    "43-1",
    "42-1",
    "41-2",
    "41-1",
    "40-3",
    "40-2",
    "40-1",
    "39-2",
    "39-1",
    "38-1",
)

DATA_DIR = "repsheet_backend/data"
EXPORT_DB = "repsheet.sqlite"
GCP_BILLING_PROJECT = "repsheet-app-prod"

VOTES_HELD_TABLE = "votes_held"
BILLS_TABLE = "bills"
MEMBER_VOTES_TABLE = "member_votes"
MEMBERS_TABLE = "members"

os.makedirs(DATA_DIR, exist_ok=True)

class BillId(NamedTuple):
    parliament: int
    session: int
    bill_number: str

@contextmanager
def db_connect():
    """Context manager for database connection."""
    db = sqlite3.connect(EXPORT_DB)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.commit()
        db.close()

def print_table_schema(table_name):
    """Print the schema of a given table."""
    with db_connect() as db:
        cursor = db.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        for row in rows:
            print(f"{row[1]}: {row[2]} {'NOT NULL' if row[3] else 'NULL'} {'PRIMARY KEY' if row[5] else ''}")

@retry(stop=stop_after_attempt(10), wait=wait_exponential())
def download_all_bill_texts(parliament, session, bill_number):
    bill_dir = path.join(DATA_DIR, "bill_text", str(parliament), str(session), str(bill_number))
    found = False
    for reading in (1, 2, 3, 4):
        for lang in ("-E", "_E"):
            filename = f"{bill_number}_{reading}/{bill_number}{lang}.xml"
            filepath = path.join(bill_dir, filename)
            if path.exists(filepath):
                # empty file indicates that the file was not found
                if path.getsize(filepath) > 0:
                    found = True
                continue
            for bill_type in ("Private", "Government"):
                url = f"https://www.parl.ca/Content/Bills/{parliament}{session}/{bill_type}/{bill_number}/{filename}"
                resp = httpx.get(url)
                os.makedirs(path.dirname(filepath), exist_ok=True)
                with open(filepath, "wb") as f:
                    if resp.status_code == 200:
                        f.write(resp.content)
                        print(f"Downloaded {filename} from {url}")
                        found = True
                        # break otherwise the next iteration might overwrite the file with an empty file
                        break
                    else:
                        # use an empty file to indicate that the file was not found
                        f.write(b"")
    return found
