import asyncio
from repsheet_backend.db import RepsheetDB
from repsheet_backend.summarize_members import condense_member_summary, generate_member_summary
from repsheet_backend.genai import genai_cache


MPS_TO_REGENERATE = [
    "Elizabeth May (Saanich—Gulf Islands)",
]

async def add_genai_summaries():
    await genai_cache.init()

    with RepsheetDB.connect() as db:
        print(f"Re-summarizing {len(MPS_TO_REGENERATE)} members")
        voting_records = [
            db.get_member_voting_record(member_id) for member_id in MPS_TO_REGENERATE
        ]
        member_summaries = await asyncio.gather(
            *[
                generate_member_summary(
                    voting_record, 
                    member_id, 
                    invalidate_cache=True,
                    dump_prompts_to_path="./debug"
                )
                for voting_record, member_id in zip(voting_records, MPS_TO_REGENERATE)
            ]
        )
        db.insert_member_summaries(zip(MPS_TO_REGENERATE, member_summaries))

        condensed_summaries = await asyncio.gather(*[
            condense_member_summary(summary)
            for summary in member_summaries
        ])
        db.insert_short_member_summaries(
            zip(MPS_TO_REGENERATE, condensed_summaries)
        )

        db.optimize()


if __name__ == "__main__":
    asyncio.run(add_genai_summaries())
