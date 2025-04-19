import asyncio
import json
from math import floor
import os
from random import Random
import re
from typing import Iterable, Iterator, Literal, Optional
from pydantic import BaseModel, ValidationError

from repsheet_backend.common import BillVotingRecord, MemberSummary, load_prompt_template
from repsheet_backend.db import RepsheetDB
from repsheet_backend.genai import CLAUDE_HAIKU, CLAUDE_SONNET, generate_text, generate_text_batch, prompt_cache_key


SUMMARIZE_MEMBER_PROMPT_TEMPLATE = load_prompt_template("summarize-member/001.txt")
MERGE_SUMMARIES_PROMPT_TEMPLATE = load_prompt_template("merge-summaries/001.txt")
CONDENSE_SUMMARY_PROMPT_TEMPLATE = load_prompt_template("condense-summary/001.txt")

BATCH_COUNT = int(floor(200000 / 8192)) - 1

# fixed to make sure batches are deterministic
# to allow for caching of AI responses
RANDOM_SEED = 338

BILL_REF_REGEX = re.compile(r"\[[A-Z]-\d+\]\((\d+-\d+-[A-Z]-\d+)\)")

# Even Claude Sonnet got these wrong. Validated manually by checking what bill was meant from context in the prompt.
# TODO currently could cause a mismatch if a different error is made with the same result, should be tied to particular summaries somehow.
BROKEN_LINK_MANUAL_FIXES = {
    "44-1-S-232": "44-1-C-232",
    "42-1-C-32": "44-1-C-32",
    "44-1-C-378": "42-1-C-378"
}

os.makedirs("debug", exist_ok=True)
os.makedirs("debug/broken_links", exist_ok=True)
os.makedirs("debug/validation", exist_ok=True)


def broken_bill_links(summary: str, all_bill_ids: set[str]) -> set[str]:
    """Check if the summary contains any broken bill links."""
    bill_refs = BILL_REF_REGEX.findall(summary)
    result = set()
    for bill_ref in bill_refs:
        if bill_ref not in all_bill_ids:
            result.add(bill_ref)
    return result


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
        invalidate_cache: bool = False,
        dump_prompts_to_path: Optional[str] = None) -> MemberSummary:
    all_bill_ids = {vote.billID for vote in voting_record}
    prompts = get_member_summarisation_prompts(voting_record)
    summaries = await asyncio.gather(*[
        generate_text(
            prompt, 
            model=CLAUDE_HAIKU, 
            temperature=0.0, 
            invalidate_cache=invalidate_cache) for prompt in prompts
    ])

    for summary_i, summary in enumerate(summaries):
        assert summary is not None
        broken_links = broken_bill_links(summary, all_bill_ids)
        if len(broken_links) > 0:
            print(f"Found {len(broken_links)} broken bill links in {CLAUDE_HAIKU} summary ({broken_links}), regenerating with {CLAUDE_SONNET}...")
            new_summary = await generate_text(
                prompts[summary_i], 
                model=CLAUDE_SONNET, 
                temperature=0.0,
            )
            assert new_summary is not None
            broken_links = broken_bill_links(new_summary, all_bill_ids)
            if len(broken_links) > 0:
                raise ValueError(f"Found {len(broken_links)} broken bill links summary re-run with {CLAUDE_SONNET}")

    if dump_prompts_to_path is not None:
        write_prompts_and_summaries(
            f"{dump_prompts_to_path}/{member_id}/sub-summaries.txt", 
            zip(prompts, summaries)
        )

    processed_summaries = [validate_member_summary(summary) for summary in summaries]
    merge_summary_prompt = get_summary_merge_prompt(processed_summaries)
    # use the expensive model to merge them, as this is a small number of tokens,
    # and is also the final output so should be polished
    merged_summary = await generate_text(
        merge_summary_prompt, 
        model=CLAUDE_SONNET, 
        temperature=0.0,
        invalidate_cache=invalidate_cache)
    assert merged_summary is not None
    
    broken_links = broken_bill_links(merged_summary, all_bill_ids)
    if len(broken_links) > 0:
        raise ValueError(f"Found {len(broken_links)} broken bill links in merged summary run with {CLAUDE_SONNET}")

    if dump_prompts_to_path is not None:
        write_prompts_and_summaries(
            f"{dump_prompts_to_path}/{member_id}/final-summary.txt", 
            [(merge_summary_prompt, merged_summary)]
        )

    assert merged_summary is not None
    return validate_member_summary(merged_summary)


async def run_member_summary_prompts(prompts: list[str], all_bill_ids: set[str], member_id: str, model: str) -> list[Optional[MemberSummary]]:
    """Attempts to fix broken bill links, and failed JSON validation"""
    summaries = await generate_text_batch(
        prompts,
        model=model,
        temperature=0.0,
    )

    for summary_i, summary in enumerate(summaries):
        assert summary is not None
        broken_links = broken_bill_links(summary, all_bill_ids)
        if len(broken_links) > 0:
            if model == CLAUDE_HAIKU: 
                print(f"Found {len(broken_links)} broken bill links in {CLAUDE_HAIKU} summary ({broken_links}), regenerating with {CLAUDE_SONNET}...")
                # We don't batch here or this whole process will be three batches long - could take ages
                # TODO huge duplication below but I'm in a rush
                new_summary = await generate_text(
                    prompts[summary_i], 
                    model=CLAUDE_SONNET, 
                    temperature=0.0,
                )
                assert new_summary is not None
                summary = new_summary

            broken_links = broken_bill_links(summary, all_bill_ids)
            for broken_link in list(broken_links):
                if broken_link in BROKEN_LINK_MANUAL_FIXES:
                    summary = summary.replace(broken_link, BROKEN_LINK_MANUAL_FIXES[broken_link])
                    broken_links.remove(broken_link)

            if len(broken_links) > 0:
                output_file = f"debug/broken_links/{member_id}-summary.json"
                with open(output_file, "w") as f:
                    json.dump({ "broken_links": list(broken_links), "summary": summary }, f, indent=2)
                print(f"Found {len(broken_links)} unpatched broken bill links in summary re-run with {CLAUDE_SONNET}, wrote to {output_file}")
                summary = None

            summaries[summary_i] = summary

    validated_summaries = []
    for prompt, summary in zip(prompts, summaries):
        if summary is None:
            validated_summaries.append(None)
            continue
        try:
            validated = validate_member_summary(summary)
        except ValidationError as e:
            if model == CLAUDE_HAIKU:
                print(f"Validation failed, re-running with {CLAUDE_SONNET}...")
                new_summary = await generate_text(
                    prompt, 
                    model=CLAUDE_SONNET, 
                    temperature=0.0,
                )
                try:
                    validated = validate_member_summary(new_summary)
                except ValidationError as e:
                    output_file = f"debug/validation/{member_id}-summary.json"
                    with open(output_file, "w") as f:
                        json.dump({ "error": str(e), "summary": new_summary, "cache_key": prompt_cache_key(prompt, model=CLAUDE_SONNET, temperature=0.0) }, f, indent=2)
                    print(f"Validation failed with {CLAUDE_SONNET}, wrote to {output_file}")
                    validated = None
            else:
                output_file = f"debug/validation/{member_id}-summary.json"
                with open(output_file, "w") as f:
                    json.dump({ "error": str(e), "summary": summary, "cache_key": prompt_cache_key(prompt, model=CLAUDE_SONNET, temperature=0.0) }, f, indent=2)
                print(f"Validation failed with {CLAUDE_SONNET}, wrote to {output_file}")
                validated = None
        validated_summaries.append(validated)

    return validated_summaries  


async def generate_member_summary_batch(
        voting_record: list[BillVotingRecord], member_id: str
) -> Optional[MemberSummary]:
    try:
        all_bill_ids = {vote.billID for vote in voting_record}
        prompts = get_member_summarisation_prompts(voting_record)
        sub_summaries = await run_member_summary_prompts(prompts, all_bill_ids, member_id, model=CLAUDE_HAIKU)
        if any(summary is None for summary in sub_summaries):
            return None
        merge_summary_prompt = get_summary_merge_prompt(sub_summaries) # type: ignore
        # use the expensive model to merge them, as this is a small number of tokens,
        # and is also the final output so should be polished
        merged_summary = await run_member_summary_prompts([merge_summary_prompt], all_bill_ids, member_id, model=CLAUDE_SONNET)
        return merged_summary[0]
    except Exception as e:
        print(f"Error generating summary for {member_id}: {e}")
        return None
    

async def condense_member_summaries(full_summaries: Iterable[MemberSummary]) -> list[str]:
    """Generate a condensed version of the summary, which is more readable and less verbose."""
    prompts = [
        CONDENSE_SUMMARY_PROMPT_TEMPLATE.replace("{{RAW_INPUT_DATA}}", full_summary.model_dump_json())
        for full_summary in full_summaries
    ]
    condensed_summaries = await asyncio.gather(*[
        generate_text(prompt, model=CLAUDE_SONNET, temperature=0.0)
        for prompt in prompts
    ])
    assert all(summary is not None for summary in condensed_summaries)
    return condensed_summaries # type: ignore


async def condense_member_summaries_batch(full_summaries: Iterable[MemberSummary]) -> list[str]:
    """Generate a condensed version of the summary, which is more readable and less verbose."""
    prompts = [
        CONDENSE_SUMMARY_PROMPT_TEMPLATE.replace("{{RAW_INPUT_DATA}}", full_summary.model_dump_json())
        for full_summary in full_summaries
    ]
    condensed_summaries = await generate_text_batch(prompts, model=CLAUDE_SONNET, temperature=0.0)
    assert all(summary is not None for summary in condensed_summaries)
    return condensed_summaries # type: ignore
