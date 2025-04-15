import asyncio
from repsheet_backend.common import LOCAL_MPS, PARTY_LEADERS
from repsheet_backend.db import RepsheetDB
from repsheet_backend.summarize_bills import summarize_bill
from repsheet_backend.summarize_members import condense_member_summary, generate_member_summary
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

        all_member_ids =  (
            # PARTY_LEADERS[0],
            # LOCAL_MPS[0],
            *PARTY_LEADERS,
            *LOCAL_MPS,
        )
        print(f"Summarizing {len(all_member_ids)} members")
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

        condensed_summaries = await asyncio.gather(*[
            condense_member_summary(summary)
            for summary in member_summaries
        ])
        db.insert_short_member_summaries(
            zip(all_member_ids, condensed_summaries)
        )

        db.optimize()


if __name__ == "__main__":
    asyncio.run(add_genai_summaries())
