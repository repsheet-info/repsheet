
import asyncio
import json
from math import floor
from random import Random
from typing import Iterable, Iterator, Literal
from pydantic import BaseModel

from repsheet_backend.common import BillVotingRecord, MemberSummary
from repsheet_backend.db import RepsheetDB
from repsheet_backend.genai import CLAUDE_HAIKU, CLAUDE_SONNET, generate_text


with open("prompts/summarize-member/001.txt", "r") as f:
    SUMMARIZE_MEMBER_PROMPT_TEMPLATE = f.read()
with open("prompts/merge-summaries/001.txt", "r") as f:
    MERGE_SUMMARIES_PROMPT_TEMPLATE = f.read()


BATCH_COUNT = int(floor(200000 / 8192)) - 1

# fixed to make sure batches are deterministic
# to allow for caching of AI responses
RANDOM_SEED = 338

def batched(iterable: list, batches: int) -> Iterator[list]:
    batch_size = len(iterable) // batches
    for i in range(0, batches):
        if i == batches - 1:
            yield iterable
            return
        else:
            yield iterable[:batch_size]
            iterable = iterable[batch_size:]


def get_member_summarisation_prompts(voting_record: list[BillVotingRecord]) -> list[str]:
    """We split the voting record into batches, and summarize each batch separately.
    This returns a list of prompts to be sent to the AI, one for each batch."""
    voting_record_objs = [vote.model_dump(mode="json", exclude_none=True) for vote in voting_record]
    Random(RANDOM_SEED).shuffle(voting_record_objs)
    result = []
    for obj_batch in batched(voting_record_objs, BATCH_COUNT):
        batch_json = json.dumps(obj_batch, indent=2, sort_keys=True)
        result.append(SUMMARIZE_MEMBER_PROMPT_TEMPLATE.replace("{{RAW_INPUT_DATA}}", batch_json))
    return result


def get_summary_merge_prompt(summaries: list[MemberSummary]) -> str:
    """Generate the promp for merging multiple summaries together into a single summary."""
    summaries_json = [summary.model_dump(mode="json") for summary in summaries]
    summaries_json = json.dumps(summaries_json, indent=2, sort_keys=True)
    return MERGE_SUMMARIES_PROMPT_TEMPLATE.replace("{{RAW_INPUT_DATA}}", summaries_json)


def validate_member_summary(response: str | None) -> MemberSummary:
    assert response is not None
    response = response.removeprefix("```json\n").removesuffix("\n```")
    return MemberSummary.model_validate_json(response)


async def generate_member_summary(voting_record: list[BillVotingRecord]) -> MemberSummary:
    prompts = get_member_summarisation_prompts(voting_record)
    summaries = await asyncio.gather(*[
        # use the cheaper model for the batched summaries, since we process a lot of tokens this way
        generate_text(prompt, model=CLAUDE_HAIKU)
        for prompt in prompts
    ])
    processed_summaries = [
        validate_member_summary(summary)
        for summary in summaries
    ]
    merge_summary_prompt = get_summary_merge_prompt(processed_summaries)
    # use the expensive model to merge them, as this is a small number of tokens,
    # and is also the final output so should be polished
    merged_summary = await generate_text(merge_summary_prompt, model=CLAUDE_SONNET)
    assert merged_summary is not None
    return validate_member_summary(merged_summary)
