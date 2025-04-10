import asyncio
from repsheet_backend.common import EM, PP
from repsheet_backend.db import RepsheetDB
from repsheet_backend.summarize_bills import summarize_bill
from repsheet_backend.summarize_members import generate_member_summary


async def add_genai_summaries():
    with RepsheetDB.connect() as db:
        bills = db.get_every_bill_voted_on_by_a_current_member()
        print(f"Summarizing {len(bills)} bills voted on by a current member")
        bill_summaries = await asyncio.gather(*[summarize_bill(bill) for bill in bills])
        bill_summaries_by_id = {
            bill: summary.model_dump_json()
            for bill, summary in zip(bills, bill_summaries)
            if summary is not None
        }
        db.insert_bill_summaries(bill_summaries_by_id)

        print(f"Summarizing PP and EM")
        all_member_ids = [PP, EM]

        voting_records = [
            db.get_member_voting_record(member_id)
            for member_id in all_member_ids
        ]
        member_summaries = await asyncio.gather(*[
            generate_member_summary(voting_record)
            for voting_record in voting_records
        ])
        member_summaries_by_id = [
            {"member_id": member_id, "summary": summary.model_dump_json()}
            for member_id, summary in zip(all_member_ids, member_summaries)
            if summary is not None
        ]
        db.insert_member_summaries(member_summaries_by_id)

        db.optimize()


if __name__ == "__main__":
    asyncio.run(add_genai_summaries())
