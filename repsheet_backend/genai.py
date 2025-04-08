import asyncio
from typing import Optional
from repsheet_backend.cache import GCSCache
from repsheet_backend.common import GCP_BILLING_PROJECT, CACHE_BUCKET
from google import genai
from google.genai.errors import ClientError
from tenacity import retry, wait_exponential, stop_after_attempt

GEMINI_FLASH_2 = "gemini-2.0-flash"

COST_PER_MTOK = {GEMINI_FLASH_2: 0.15}

CONTEXT_WINDOW = {GEMINI_FLASH_2: 1e6}

google_ai = genai.Client(
    vertexai=True, project=GCP_BILLING_PROJECT, location="us-central1"
)

# TODO I messed up the cache key prefix so
# at some point we should migrate this over to having a "google-ai/" prefix
google_ai_cache = GCSCache(
    project=GCP_BILLING_PROJECT,
    cache_bucket=CACHE_BUCKET,
    key_prefix="google-ai/",
    mode="json",
)

@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential()
)
def _generate_text(prompt: str, model: str) -> Optional[str]:
    """Generate text using Google Gemini."""
    print(f"Generating text with {model} ({len(prompt)} chars)")
    try:
        response = google_ai.models.generate_content(model=model, contents=prompt)
    except ClientError as e:
        if e.code == 400 and e.message is not None and "exceeds the maximum number of tokens allowed" in e.message:
            return None
        raise e
    print(f"Received response from {model} ({len(response.text or "")} chars)")
    return response.text


def _estimate_cost_usd_input_only(prompt: str, model: str) -> float:
    """Estimate the cost of generating text using Google Gemini.
    Only counts input tokens, not output tokens."""
    # Example cost estimation logic
    response = google_ai.models.count_tokens(model=model, contents=prompt)
    tokens = response.total_tokens
    if tokens is None:  
        raise ValueError("Failed to count tokens")
    if tokens > CONTEXT_WINDOW[model]:
        raise ValueError(f"Prompt exceeds context window of {CONTEXT_WINDOW[model]} tokens")
    cost = tokens * (COST_PER_MTOK[model] / 1e6)
    return cost


async def estimate_cost_usd_input_only(
    prompt: str, model: str = GEMINI_FLASH_2
) -> float:
    """Estimate the cost of generating text using Google Gemini."""
    cache_key = {
        "method": "estimate_cost_usd_input_only",
        "model": model,
        "prompt": prompt,
    }
    cached_response = await google_ai_cache.get(cache_key)
    if cached_response:
        return cached_response
    cost = await asyncio.to_thread(_estimate_cost_usd_input_only, prompt, model)
    await google_ai_cache.set(cache_key, cost)
    return cost


async def generate_text(prompt: str, model: str = GEMINI_FLASH_2) -> Optional[str]:
    cache_key = {
        "method": "generate_text",
        "model": model,
        "prompt": prompt,
    }
    cached_response = await google_ai_cache.get(cache_key)
    if cached_response:
        return cached_response
    response = await asyncio.to_thread(_generate_text, prompt, model)
    if response is not None:
        await google_ai_cache.set(cache_key, response)
    return response
