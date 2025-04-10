import asyncio
import os

from repsheet_backend.db import RepsheetDB, REPSHEET_DB
from repsheet_backend.fetch_data import fetch_all_member_votes_by_vote_id, fetch_members_csv, fetch_all_bills_by_session, fetch_all_votes_by_session, fetch_member_votes
from repsheet_backend.summarize_bills import summarize_bill

async def build_repsheet_db():
    members, bills_by_session, votes_by_session = await asyncio.gather(*[
        fetch_members_csv(),
        fetch_all_bills_by_session(),
        fetch_all_votes_by_session(),
    ])
    with RepsheetDB.connect() as db:
        db.create_members_table(members)
        db.create_bills_table(bills_by_session)
        db.create_votes_table(votes_by_session)
        votes_held = db.get_all_votes_held()
        member_votes = await fetch_all_member_votes_by_vote_id(votes_held)
        db.create_member_votes_table(member_votes)

if __name__ == "__main__":
    if os.path.exists(REPSHEET_DB):
        os.remove(REPSHEET_DB) 
        print(f"Deleted {REPSHEET_DB}")
    asyncio.run(build_repsheet_db())
