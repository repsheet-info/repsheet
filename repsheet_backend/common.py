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
CACHE_BUCKET = "repsheet-cache"

VOTES_HELD_TABLE = "votes_held"
BILLS_TABLE = "bills"
MEMBER_VOTES_TABLE = "member_votes"
MEMBERS_TABLE = "members"

os.makedirs(DATA_DIR, exist_ok=True)

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
