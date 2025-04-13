from os import path
import asyncio
import os
from typing import Iterable, NamedTuple, Optional
import pandas as pd
import json

from tenacity import retry, stop_after_attempt, wait_exponential

from repsheet_backend.common import (
    BILLS_TABLE,
    DATA_DIR,
    PARLIMENTARY_SESSIONS,
    LATEST_PARLIAMENT,
    VOTES_HELD_TABLE,
    MEMBER_VOTES_TABLE,
    BillId,
    httpx,
)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(path.join(DATA_DIR, BILLS_TABLE), exist_ok=True)
os.makedirs(path.join(DATA_DIR, VOTES_HELD_TABLE), exist_ok=True)
os.makedirs(path.join(DATA_DIR, MEMBER_VOTES_TABLE), exist_ok=True)

# maximum concurrent API requests to Parliamentary data
data_api_semaphore = asyncio.Semaphore(8)


async def fetch_members_csv() -> pd.DataFrame:
    filepath = path.join(DATA_DIR, f"members-{LATEST_PARLIAMENT}.csv")
    if not path.exists(filepath):
        async with data_api_semaphore:
            resp = await httpx.get(
                f"https://www.ourcommons.ca/Members/en/search/csv?parliament={LATEST_PARLIAMENT}&caucusId=all&province=all&gender=all"
            )
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"Downloaded {filepath}")
    return pd.read_csv(filepath, low_memory=False)


async def fetch_bills_json(session: str) -> list[dict]:
    filepath = path.join(DATA_DIR, BILLS_TABLE, f"bills-{session}.json")
    if not path.exists(filepath):
        async with data_api_semaphore:
            resp = await httpx.get(
                f"https://www.parl.ca/legisinfo/en/bills/json?parlsession={session}"
            )
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"Downloaded {filepath}")
    with open(filepath, "r") as f:
        return json.load(f)


async def fetch_all_bills_by_session() -> dict[str, list[dict]]:
    bills = await asyncio.gather(
        *[fetch_bills_json(session) for session in PARLIMENTARY_SESSIONS],
        return_exceptions=False,
    )
    return {session: bills for session, bills in zip(PARLIMENTARY_SESSIONS, bills)}


async def fetch_votes_csv(session: str) -> pd.DataFrame:
    filepath = path.join(DATA_DIR, VOTES_HELD_TABLE, f"votes-{session}.csv")
    if not path.exists(filepath):
        async with data_api_semaphore:
            resp = await httpx.get(
                f"https://www.ourcommons.ca/Members/en/votes/csv?parlSession={session}"
            )
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"Downloaded {filepath}")
    return pd.read_csv(filepath, low_memory=False)


async def fetch_all_votes_by_session() -> dict[str, pd.DataFrame]:
    votes = await asyncio.gather(
        *[fetch_votes_csv(session) for session in PARLIMENTARY_SESSIONS],
        return_exceptions=False,
    )
    return {session: votes for session, votes in zip(PARLIMENTARY_SESSIONS, votes)}


async def fetch_member_votes(vote_id: str) -> pd.DataFrame:
    parliament, session, vote_number = vote_id.split("-")
    parliament = int(parliament)
    session = int(session)
    vote_number = int(vote_number)
    filepath = path.join(DATA_DIR, MEMBER_VOTES_TABLE, f"member-votes-{vote_id}.csv")
    if not path.exists(filepath):
        async with data_api_semaphore:
            resp = await httpx.get(
                f"https://www.ourcommons.ca/Members/en/votes/{parliament}/{session}/{vote_number}/csv"
            )
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"Downloaded {filepath}")
    return pd.read_csv(filepath, low_memory=False)


async def fetch_all_member_votes_by_vote_id(vote_ids: Iterable[str]) -> dict[str, pd.DataFrame]:
    votes = await asyncio.gather(*[fetch_member_votes(vote_id) for vote_id in vote_ids])
    return {vote_id: votes for vote_id, votes in zip(vote_ids, votes)}


@retry(stop=stop_after_attempt(10), wait=wait_exponential())
async def fetch_latest_bill_text(bill: BillId) -> Optional[str]:
    parliament, session, bill_number = bill
    bill_dir = path.join(DATA_DIR, "bill_text", str(parliament), str(session), str(bill_number))
    found_files = []
    for reading in (1, 2, 3, 4):
        for lang in ("-E", "_E"):
            filename = f"{bill_number}_{reading}/{bill_number}{lang}.xml"
            filepath = path.join(bill_dir, filename)
            if path.exists(filepath):
                # empty file indicates that the file was not found
                if path.getsize(filepath) > 0:
                    found_files.append(filepath)
                continue
            for bill_type in ("Private", "Government"):
                url = f"https://www.parl.ca/Content/Bills/{parliament}{session}/{bill_type}/{bill_number}/{filename}"
                async with data_api_semaphore:
                    resp = await httpx.get(url)
                os.makedirs(path.dirname(filepath), exist_ok=True)
                with open(filepath, "wb") as f:
                    if resp.status_code == 200:
                        f.write(resp.content)
                        print(f"Downloaded {filename} from {url}")
                        found_files.append(filepath)
                        # break otherwise the next iteration might overwrite the file with an empty file
                        break
                    else:
                        # use an empty file to indicate that the file was not found
                        f.write(b"")
    if not found_files:
        return None
    latest_reading_path = max(found_files)
    with open(latest_reading_path, "r") as f:
        return f.read()
