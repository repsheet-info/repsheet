import os
from os import path
import pandas as pd
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Literal, NamedTuple, Optional
import re
from httpx import AsyncClient
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

PARLIMENTARY_SESSIONS = (
    "44-1",
    "43-2",
    "43-1",
    "42-1",
    "41-2",
    "41-1",
    # Only considering the most recent four parliaments for now
    # "40-3",
    # "40-2",
    # "40-1",
    # "39-2",
    # "39-1",
    # "38-1",
)

LATEST_PARLIAMENT = int(max(PARLIMENTARY_SESSIONS).split("-")[0])
assert LATEST_PARLIAMENT == 44

DATA_DIR = "repsheet_backend/data"
GCP_BILLING_PROJECT = "repsheet-app-prod"
CACHE_BUCKET = "repsheet-cache"

VOTES_HELD_TABLE = "votes_held"
BILLS_TABLE = "bills"
MEMBER_VOTES_TABLE = "member_votes"
MEMBERS_TABLE = "members"

JT = "Justin Trudeau (Papineau)"
PP = "Pierre Poilievre (Carleton)"
EM = "Elizabeth May (Saanich—Gulf Islands)"

os.makedirs(DATA_DIR, exist_ok=True)

httpx = AsyncClient()


class BillId(NamedTuple):
    parliament: int
    session: int
    bill_number: str

    def __str__(self):
        return f"{self.parliament}-{self.session}-{self.bill_number}"


class BillIssues(BaseModel):
    climateAndEnergy: Optional[str]
    affordabilityAndHousing: Optional[str]
    defense: Optional[str]
    healthcare: Optional[str]
    immigration: Optional[str]
    infrastructure: Optional[str]
    spendingAndTaxation: Optional[str]
    indigenousRelations: Optional[str]
    crimeAndJustice: Optional[str]
    civilRights: Optional[str]


class BillSummary(BaseModel):
    summary: str
    issues: BillIssues


class BillVotingRecord(BaseModel):
    summary: str
    billID: str
    billNumber: str
    voted: Literal["yea", "nay", "abstain"]
    issues: BillIssues


class MemberSummary(BaseModel):
    summary: str
    issues: BillIssues
