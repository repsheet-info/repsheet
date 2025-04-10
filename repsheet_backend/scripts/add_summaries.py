import asyncio
from repsheet_backend.db import RepsheetDB
from repsheet_backend.summarize_bills import summarize_bill


async def add_genai_summaries():
    with RepsheetDB.connect() as db:
        bills = db.every_bill_voted_on_by_a_current_member()
        print(f"Summarizing {len(bills)} bills voted on by a current member")
        bill_summaries = await asyncio.gather(*[summarize_bill(bill) for bill in bills])
        bill_summaries_by_id = {
            bill: summary.model_dump_json()
            for bill, summary in zip(bills, bill_summaries)
            if summary is not None
        }
        db.insert_bill_summaries(bill_summaries_by_id)


if __name__ == "__main__":
    asyncio.run(add_genai_summaries())
