import asyncio
import os
from typing import Optional
from repsheet_backend.cache import GCSCache
from repsheet_backend.common import GCP_BILLING_PROJECT, CACHE_BUCKET
from google import genai
from google.genai.errors import ClientError
from google.genai._api_client import _load_auth
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt, retry_if_exception
from anthropic import Anthropic, RateLimitError

GEMINI_FLASH_2 = "gemini-2.0-flash"
GEMINI_PRO_2_5 = "gemini-2.5-pro-preview-03-25"
CLAUDE_SONNET = "claude-3-7-sonnet-20250219"
CLAUDE_HAIKU = "claude-3-5-haiku-20241022"

COST_PER_MTOK = {GEMINI_FLASH_2: 0.15}

CONTEXT_WINDOW = {GEMINI_FLASH_2: 1e6}

MAX_OUTPUT_TOKENS = {
    CLAUDE_HAIKU: 8192,
    CLAUDE_SONNET: 8192,
}

MAX_CONCURRENT_REQUESTS = 16

# I think there's a weird thread-safety bug or something but it was unable to get the access token
# unless I generated the credentials separately like this
credentials, _ = _load_auth(project=GCP_BILLING_PROJECT)
google_ai = genai.Client(
    vertexai=True, project=GCP_BILLING_PROJECT, location="us-central1", credentials=credentials
)

anthropic = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "none"),
)

api_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# It says "google-ai" but I use it for everything
genai_cache = GCSCache(
    project=GCP_BILLING_PROJECT,
    cache_bucket=CACHE_BUCKET,
    key_prefix="google-ai/",
    mode="json",
)

@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(min=5, max=5 * 60),
    retry=retry_if_exception(lambda e: isinstance(e, ClientError) and e.code == 429),
)
def _generate_text_google(prompt: str, model: str) -> Optional[str]:
    """Generate text using Google Gemini."""
    print(f"Generating text with {model} ({len(prompt)} chars)")
    try:
        response = google_ai.models.generate_content(model=model, contents=prompt)
    except ClientError as e:
        if (
            e.code == 400
            and e.message is not None
            and "exceeds the maximum number of tokens allowed" in e.message
        ):
            print(f"Prompt too long for {model} ({len(prompt)} chars)")
            return None
        raise e
    print(f"Received response from {model} ({len(response.text or "")} chars)")
    return response.text


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(min=5, max=5 * 60),
    retry=retry_if_exception_type(RateLimitError),
)
def _generate_text_anthropic(
    prompt: str, model: str, output_tokens: Optional[int] = None
) -> Optional[str]:
    """Generate text using Anthropic."""
    print(f"Generating text with {model} ({len(prompt)} chars)")
    response = anthropic.messages.create(
        model=model,
        max_tokens=output_tokens or MAX_OUTPUT_TOKENS[model],
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.content[0].text  # type: ignore
    print(f"Received response from {model} ({len(result)} chars)")
    return result


async def generate_text(
    prompt: str, model: str = GEMINI_FLASH_2, output_tokens: Optional[int] = None
) -> Optional[str]:
    if "{{" in prompt or "}}" in prompt:
        raise ValueError("Prompt contains unresolved template variables")    

    cache_key = {
        "method": "generate_text",
        "model": model,
        "prompt": prompt,
    }
    cached_response = await genai_cache.get(cache_key)
    if cached_response is None:
        # No way to distinguish between a cache miss and a cached None value
        # so we have to check if the cache key exists
        is_cached_none = await genai_cache.has(cache_key)
        if is_cached_none:
            return None
    else:
        return cached_response
    async with api_semaphore:
        if model.startswith("claude"):
            response = await asyncio.to_thread(
                _generate_text_anthropic, prompt, model, output_tokens
            )
        else:
            response = await asyncio.to_thread(_generate_text_google, prompt, model)
    await genai_cache.set(cache_key, response)
    return response
