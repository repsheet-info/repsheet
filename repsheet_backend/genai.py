import asyncio
import os
from typing import Any, Iterable, Optional
from repsheet_backend.cache import GCSCache
from repsheet_backend.common import GCP_BILLING_PROJECT, CACHE_BUCKET
from google import genai
from google.genai.errors import ClientError
from google.genai._api_client import _load_auth
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt, retry_if_exception
from anthropic import NOT_GIVEN, Anthropic, NotGiven, RateLimitError
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from anthropic.types.messages import MessageBatchRequestCounts

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

MAX_CONCURRENT_REQUESTS = 32

# I think there's a weird thread-safety bug or something but it was unable to get the access token
# unless I generated the credentials separately like this
credentials, _ = _load_auth(project=GCP_BILLING_PROJECT)
google_ai = genai.Client(
    vertexai=True, project=GCP_BILLING_PROJECT, location="us-central1", credentials=credentials
)

anthropic = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
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
    prompt: str, model: str, output_tokens: Optional[int] = None, temperature: Optional[float] = None
) -> Optional[str]:
    """Generate text using Anthropic."""
    print(f"Generating text with {model} ({len(prompt)} chars)")
    response = anthropic.messages.create(
        model=model,
        max_tokens=output_tokens or MAX_OUTPUT_TOKENS[model],
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature if temperature is not None else NOT_GIVEN,
    )
    result = response.content[0].text  # type: ignore
    print(f"Received response from {model} ({len(result)} chars)")
    return result


async def generate_text(
    prompt: str, 
    model: str = GEMINI_FLASH_2, 
    output_tokens: Optional[int] = None, 
    temperature: Optional[float] = None,
    invalidate_cache: bool = False,
) -> Optional[str]:
    if "{{" in prompt:
        raise ValueError("Prompt contains unresolved template variables")    

    cache_key: dict[str, Any] = {
        "method": "generate_text",
        "model": model,
        "prompt": prompt,
    }
    if temperature is not None:
        cache_key["temperature"] = temperature
    if not invalidate_cache:
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
                _generate_text_anthropic, prompt, model, output_tokens, temperature
            )
        else:
            response = await asyncio.to_thread(_generate_text_google, prompt, model)
    await genai_cache.set(cache_key, response)
    return response


def summarize_batch_counts(counts: MessageBatchRequestCounts) -> str:
    total = counts.canceled + counts.errored + counts.expired + counts.processing + counts.succeeded
    result = ""
    if counts.canceled > 0:
        result += f"{counts.canceled} canceled, "
    if counts.errored > 0:
        result += f"{counts.errored} errored, "
    if counts.expired > 0:
        result += f"{counts.expired} expired, "
    result += f"{counts.succeeded} succeeded, {total} total"
    return result


async def anthropic_wait_for_batch(anthropic_batch_id: str, sleep: int = 60) -> dict[str, str]:
    while True:
        async with api_semaphore:
            batch_resp = await asyncio.to_thread(anthropic.messages.batches.retrieve, anthropic_batch_id)
        if batch_resp.processing_status == "ended":
            break
        print(f"Batch {anthropic_batch_id} is still processing ({summarize_batch_counts(batch_resp.request_counts)})")
        await asyncio.sleep(sleep)
    print(f"Batch {anthropic_batch_id} is finished ({summarize_batch_counts(batch_resp.request_counts)})")
    result = {}
    for message in await asyncio.to_thread(anthropic.messages.batches.results, anthropic_batch_id):
        result[message.custom_id] = message.result.message.content[0].text # type: ignore
    return result


async def generate_text_batch(
    prompts: Iterable[str],
    model: str,
    temperature: float = 1.0,
    output_tokens: Optional[int] = None,
) -> list[Optional[str]]:
    if not model.startswith("claude"):
        raise ValueError("Batch generation is only supported for Anthropic models")
    
    prompts = list(prompts)
    for prompt in prompts:
        if "{{" in prompt:
            raise ValueError("Prompt contains unresolved template variables")
    
    results: dict[int, Optional[str]] = {}
    cache_key_objs = [
        {
            "method": "generate_text",
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
        }
        for prompt in prompts
    ]
    cached_responses = await asyncio.gather(*[
        genai_cache.get(cache_key_obj) for cache_key_obj in cache_key_objs
    ])
    for i, cached_response in enumerate(cached_responses):
        if cached_response is None:
            # No way to distinguish between a cache miss and a cached None value
            # so we have to check if the cache key exists.
            # Parallelize this if it becomes a bottle-neck
            is_cached_none = await genai_cache.has(cache_key_objs[i])
            if is_cached_none:
                results[i] = None
        else:
            results[i] = cached_response

    if all(i in results.keys() for i in range(len(prompts))):
        # All prompts are cached
        return [results[i] for i in range(len(prompts))]

    # we use the cache key as the ID if we fail waiting on the job we can 
    # inject the result into the cache post-hoc and re-run
    cache_keys = [genai_cache.cache_key(cache_key_obj) for cache_key_obj in cache_key_objs]

    # TODO key against cache key so it can be inserted after the fact?
    output_tokens = output_tokens or MAX_OUTPUT_TOKENS[model]  
    batch_requests = [
        Request(
            custom_id=cache_keys[i],
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=output_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            ),
        )
        for i, prompt in enumerate(prompts)
        if i not in results.keys()
    ]
    async with api_semaphore:
        batch_resp = await asyncio.to_thread(anthropic.messages.batches.create,
            requests=batch_requests
        )

    print(f"Submitted batch ({batch_resp.id}) with {len(batch_requests)} requests using {model} (total {sum(len(prompt) for prompt in prompts)} chars)")
    batch_results = await anthropic_wait_for_batch(batch_resp.id)
    for result_key, result in batch_results.items():
        result_i = next(i for i, key in enumerate(cache_keys) if key == result_key)
        results[result_i] = result
        await genai_cache.set(cache_key_objs[result_i], result)
    return [results[i] for i in range(len(prompts))]
