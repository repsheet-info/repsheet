import os
from os import path
import pandas as pd
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Literal, NamedTuple, Optional
import re
from httpx import AsyncClient
from pydantic import BaseModel, Field
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

PARLIAMENT_META = {
    44: {
        "government": "Liberal",
        "opposition": "Conservative",
        "supply-and-confidence": "NDP",
    },
    43: {
        "government": "Liberal",
        "opposition": "Conservative",
    },
    42: {
        "government": "Liberal",
        "opposition": "Conservative",
    },
    41: {
        "government": "Conservative",
        "opposition": "Liberal",
    },
}

LATEST_PARLIAMENT = int(max(PARLIMENTARY_SESSIONS).split("-")[0])
assert LATEST_PARLIAMENT == 44

DATA_DIR = "repsheet_backend/data"
GCP_BILLING_PROJECT = "repsheet-app-prod"
CACHE_BUCKET = "repsheet-cache"

VOTES_HELD_TABLE = "votes_held"
BILLS_TABLE = "bills"
MEMBER_VOTES_TABLE = "member_votes"
VOTE_SUMMARY_TABLE = "vote_summary"
VOTE_PARTY_SUMMARY_TABLE = "vote_party_summary"
MEMBERS_TABLE = "members"
PARLIAMENTS_TABLE = "parliaments"
PARTY_LEADERS = (
    "Pierre Poilievre (Carleton)",
    "Jagmeet Singh (Burnaby South)",
    "Yves-François Blanchet (Beloeil—Chambly)",
)

LOCAL_MPS = (
    "Elizabeth May (Saanich—Gulf Islands)",
    "Laurel Collins (Victoria)",
)

os.makedirs(DATA_DIR, exist_ok=True)

httpx = AsyncClient()

with open("prompts/partials/issues/001.txt", "r") as f:
    ISSUE_SUMMARY_PARTIAL = f.read()

with open("prompts/partials/context/001.txt", "r") as f:
    CONTEXT_PARTIAL = f.read()

with open("prompts/partials/parliament/001.txt", "r") as f:
    PARLIAMENT_PARTIAL = f.read()


def load_prompt_template(file_name: str) -> str:
    """Read a template file and return its contents."""
    with open(path.join("prompts", file_name), "r") as f:
        return (
            f.read()
            .replace("{{PARTIALS/ISSUES/001}}", ISSUE_SUMMARY_PARTIAL)
            .replace("{{PARTIALS/CONTEXT/001}}", CONTEXT_PARTIAL)
            .replace("{{PARTIALS/PARLIAMENT/001}}", PARLIAMENT_PARTIAL)
        )

def fix_broken_newlines_in_json(text: str):
    """Sometimes the AI puts unescaped new lines in JSON strings, this should fix that."""
    inside_quote = False 
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\n" and inside_quote:
            text = text[:i] + "\\n" + text[i+1:]
            i = i + 1
        if c == '"' and text[i - 1] != "\\":
            inside_quote = not inside_quote
        i = i + 1
    return text


class BillId(NamedTuple):
    parliament: int
    session: int
    bill_number: str

    def __str__(self):
        return f"{self.parliament}-{self.session}-{self.bill_number}"


class BillIssues(BaseModel):
    inflationAndCostOfLiving: Optional[str] = Field(None)
    jobs: Optional[str] = Field(None)
    taxation: Optional[str] = Field(None)
    spending: Optional[str] = Field(None)
    healthcare: Optional[str] = Field(None)
    childcare: Optional[str] = Field(None)
    seniorsAndPensions: Optional[str] = Field(None)
    climate: Optional[str] = Field(None)
    environmentalProtection: Optional[str] = Field(None)
    energy: Optional[str] = Field(None)
    reconciliation: Optional[str] = Field(None)
    immigrationAndIntegration: Optional[str] = Field(None)
    incomeInequalityAndPoverty: Optional[str] = Field(None)
    reproductiveRights: Optional[str] = Field(None)
    genderAndSexuality: Optional[str] = Field(None)
    racism: Optional[str] = Field(None)
    crime: Optional[str] = Field(None)
    gunControl: Optional[str] = Field(None)
    defense: Optional[str] = Field(None)
    foreignAid: Optional[str] = Field(None)


class BillSummary(BaseModel):
    summary: str
    issues: BillIssues


class PartyVotes(BaseModel):
    yea: int
    nay: int
    abstain: int
    # percentages are represented as strings under the entirely unvalidated assumption that
    # this will be simpler for the AI to interpret
    percentageYea: str

    @staticmethod
    def build(yea: int, nay: int, abstain: int) -> "PartyVotes":
        total = yea + nay + abstain
        if total == 0:
            return PartyVotes(yea=0, nay=0, abstain=0, percentageYea="N/A")
        return PartyVotes(
            yea=yea,
            nay=nay,
            abstain=abstain,
            percentageYea=f"{yea / total:.0%}",
        )


class BillVotingRecord(BaseModel):
    summary: str
    billID: str
    billNumber: str
    memberVote: Literal["yea", "nay", "abstain"]
    billBecameLaw: bool
    billIsBudget: bool
    privateBillOfMember: bool
    percentageOfPartyWithSameVote: Optional[str]
    issues: BillIssues
    memberInGovernment: bool
    memberInOpposition: bool
    memberInSupplyAndConfidence: bool    
    # percentages are represented as strings under the entirely unvalidated assumption that
    # this will be simpler for the AI to interpret
    parliamentYeaPercentage: str


class MemberSummary(BaseModel):
    summary: str
    issues: BillIssues


class MemberInfo(BaseModel):
    id: str
    first_name: str
    last_name: str
    party: str

    @property
    def url_slug(self) -> str:
        return f"{self.first_name}_{self.last_name}"
