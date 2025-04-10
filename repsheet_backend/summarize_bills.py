
import re
from typing import Optional
from pydantic import BaseModel

from repsheet_backend.common import BillId, BillSummary
from repsheet_backend.fetch_data import fetch_latest_bill_text
from repsheet_backend.genai import generate_text, GEMINI_FLASH_2


with open("prompts/summarize-bill/001.txt", "r") as f:
    SUMMARIZE_BILL_PROMPT_TEMPLATE = f.read()

xref_external_regex = re.compile(r"<XRefExternal[^>]*>(.*?)<\/XRefExternal>")
trailing_comma_regex = re.compile(r",\s*}")
missing_comma_regex = re.compile(r'"\s*"')


def simplify_bill_xml(xml_text: str) -> str:
    # The ichor permeates MY FACE MY FACE
    # Remove all the XRefExternal tags
    return xref_external_regex.sub(r"\1", xml_text)

async def get_bill_summarization_prompt(bill: BillId) -> Optional[str]:
    xml_text = await fetch_latest_bill_text(bill)
    if xml_text is None:
        return None
    xml_text = simplify_bill_xml(xml_text)
    return SUMMARIZE_BILL_PROMPT_TEMPLATE.replace("{{BILL_XML}}", xml_text)


async def summarize_bill(bill: BillId) -> Optional[BillSummary]:
    prompt = await get_bill_summarization_prompt(bill)
    if prompt is None:
        return None
    # Gemini Flash 2 has a 1M context window, needed for appropriation bills
    # and is not too costly
    response = await generate_text(prompt, model=GEMINI_FLASH_2)
    if response is None:
        print(f"Error generating summary for {bill}, likely exceeded token count")
        return None
    return cleanup_and_validate_summary_json(response)


def cleanup_and_validate_summary_json(json_text: str) -> Optional[BillSummary]:
    json_text = json_text.removeprefix("```json\n").removesuffix("\n```")
    # Remove trailing commas before closing braces
    json_text = trailing_comma_regex.sub("}", json_text)
    # Add any missing commas
    json_text = missing_comma_regex.sub('", "', json_text)
    # Never seen this as an escape character before, but the AI seems to think it's real
    json_text = json_text.replace("\\$", "$").replace("\\$", "$")
    try:
        return BillSummary.model_validate_json(json_text)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        print(f"JSON text: {json_text}")
        return None
