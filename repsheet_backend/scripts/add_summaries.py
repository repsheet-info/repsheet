import asyncio
from repsheet_backend.common import LOCAL_MPS, PARTY_LEADERS
from repsheet_backend.db import RepsheetDB
from repsheet_backend.summarize_bills import summarize_bill
from repsheet_backend.summarize_members import (
    condense_member_summaries,
    condense_member_summaries_batch,
    generate_member_summary,
    generate_member_summary_batch,
)
from repsheet_backend.genai import genai_cache

BATCH_MODE = True
assert BATCH_MODE, (
    "the non batch-mode code has drifted heavily from the batch code at this point, "
    "please add in all the various fixes or merge the two approaches together before turning this off"
)


async def add_genai_summaries():
    await genai_cache.init()

    with RepsheetDB.connect() as db:
        bills = db.get_nonunanimous_bills_voted_on_by_a_current_member()
        print(f"Summarizing {len(bills)} bills voted on by a current member")
        bill_summaries = await asyncio.gather(*[summarize_bill(bill) for bill in bills])
        bill_summaries_by_id = {
            bill: summary.model_dump_json()
            for bill, summary in zip(bills, bill_summaries)
            if summary is not None
        }
        db.insert_bill_summaries(bill_summaries_by_id)

        # all_member_ids = (
        # *PARTY_LEADERS,
        # *LOCAL_MPS,
        # )
        
        all_member_ids = [member.id for member in db.get_current_members()]
        print(f"Summarizing {len(all_member_ids)} members")
        voting_records = (
            db.get_member_voting_record(member_id) for member_id in all_member_ids
            # TODO URGENT temporarily exclude MPs where generated JSON is broken
            if member_id not in ("Hedy Fry (Vancouver Centre)", "Lisa Hepfner (Hamilton Mountain)")
        )

        if BATCH_MODE:
            print(f"Summarizing voting records in batch mode")
            member_summaries = await asyncio.gather(
                *[
                    generate_member_summary_batch(voting_record, member_id)
                    for voting_record, member_id in zip(voting_records, all_member_ids)
                ]
            )
        else:
            member_summaries = await asyncio.gather(
                *[
                    generate_member_summary(
                        voting_record, member_id, dump_prompts_to_path="./debug"
                    )
                    for voting_record, member_id in zip(voting_records, all_member_ids)
                ]
            )

        # strip out failures
        member_ids_and_summaries = [
            (member_id, summary)
            for member_id, summary in zip(all_member_ids, member_summaries)
            if summary is not None
        ]

        db.insert_member_summaries(member_ids_and_summaries)

        if BATCH_MODE:
            condensed_summaries = await condense_member_summaries_batch(
                summary for _, summary in member_ids_and_summaries
            )
        else:
            condensed_summaries = await condense_member_summaries(
                summary for _, summary in member_ids_and_summaries
            )
        summarized_member_ids = [member_id for member_id, _ in member_ids_and_summaries]
        db.insert_short_member_summaries(zip(summarized_member_ids, condensed_summaries))

        db.optimize()

        failed_member_ids = set(all_member_ids) - set(summarized_member_ids)
        if len(failed_member_ids) > 0:
            print(f"Failed to summarize {len(failed_member_ids)} members:")
            for member_id in failed_member_ids:
                print(f"  {member_id}")


if __name__ == "__main__":
    asyncio.run(add_genai_summaries())
