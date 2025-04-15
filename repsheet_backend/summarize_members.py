import asyncio
import json
from math import floor
import os
from random import Random
from typing import Iterable, Iterator, Literal, Optional
from pydantic import BaseModel

from repsheet_backend.common import BillVotingRecord, MemberSummary, load_prompt_template
from repsheet_backend.db import RepsheetDB
from repsheet_backend.genai import CLAUDE_HAIKU, CLAUDE_SONNET, generate_text, generate_text_batch


SUMMARIZE_MEMBER_PROMPT_TEMPLATE = load_prompt_template("summarize-member/001.txt")
MERGE_SUMMARIES_PROMPT_TEMPLATE = load_prompt_template("merge-summaries/001.txt")

BATCH_COUNT = int(floor(200000 / 8192)) - 1

# fixed to make sure batches are deterministic
# to allow for caching of AI responses
RANDOM_SEED = 338


def batched(iterable: list, batches: int) -> Iterator[list]:
    batch_size = len(iterable) // batches
    if batch_size == 0:
        yield iterable
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


def write_prompts_and_summaries(filename: str, prompts_and_summaries: Iterable[tuple[str | None, str | None]]):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        for i, (prompt, summary) in enumerate(prompts_and_summaries):
            f.write(f"### Prompt {i+1} ###\n\n{prompt}\n")
            f.write(f"### Summary {i+1} ###\n\n{summary}\n")
            f.write("\n\n")


async def generate_member_summary(
        voting_record: list[BillVotingRecord], 
        member_id: str, 
        dump_prompts_to_path: Optional[str] = None) -> MemberSummary:
    prompts = get_member_summarisation_prompts(voting_record)
    summaries = await generate_text_batch(
        prompts,
        model=CLAUDE_HAIKU,
    )
    if dump_prompts_to_path is not None:
        write_prompts_and_summaries(
            f"{dump_prompts_to_path}/{member_id}/sub-summaries.txt", 
            zip(prompts, summaries)
        )

    processed_summaries = [validate_member_summary(summary) for summary in summaries]
    merge_summary_prompt = get_summary_merge_prompt(processed_summaries)
    # use the expensive model to merge them, as this is a small number of tokens,
    # and is also the final output so should be polished
    merged_summary = (await generate_text_batch([merge_summary_prompt], model=CLAUDE_SONNET))[0]

    if dump_prompts_to_path is not None:
        write_prompts_and_summaries(
            f"{dump_prompts_to_path}/{member_id}/final-summary.txt", 
            [(merge_summary_prompt, merged_summary)]
        )

    assert merged_summary is not None
    return validate_member_summary(merged_summary)
