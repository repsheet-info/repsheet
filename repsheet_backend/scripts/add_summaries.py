import asyncio
from repsheet_backend.common import EM, PP
from repsheet_backend.db import RepsheetDB
from repsheet_backend.summarize_bills import summarize_bill
from repsheet_backend.summarize_members import generate_member_summary
from repsheet_backend.genai import genai_cache


async def add_genai_summaries():
    await genai_cache.init()

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
        all_member_ids = [
            PP,
            EM,
        ]
        voting_records = [
            db.get_member_voting_record(member_id) for member_id in all_member_ids
        ]
        member_summaries = await asyncio.gather(
            *[
                generate_member_summary(
                    voting_record, 
                    member_id, 
                    # dump_prompts_to_path="./debug"
                )
                for voting_record, member_id in zip(voting_records, all_member_ids)
            ]
        )
        db.insert_member_summaries(zip(all_member_ids, member_summaries))

        db.optimize()


if __name__ == "__main__":
    asyncio.run(add_genai_summaries())
