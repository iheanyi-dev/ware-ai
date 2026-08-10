"""
app/services/gemini_client.py

Google Gemini backend, matching the same interface as anthropic_client.py
and llama_cpp_client.py: get_chat_completion() and
get_chat_completion_stream(), same three-argument signature. Swapping
chatbot_service.py's import to this module requires no other changes.

Uses the google-genai SDK (the current unified SDK — NOT the older,
deprecated google-generativeai package). Free tier via Google AI Studio:
no credit card, rate-limited (roughly ~1,500 requests/day, generous
tokens-per-minute on Flash-tier models as of this writing — check
Google's current pricing page, these numbers change). Note: on the free
tier, Google may use prompts/responses to improve their products; this
does not apply once billing is enabled on the project.

Setup:
    uv add google-genai
    export GEMINI_API_KEY=...   # from https://aistudio.google.com/apikey
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import get_settings

# Same ChatMessage shape used across all three client modules:
# {"role": "user"|"assistant", "content": str}
ChatMessage = dict[str, str]

MAX_OUTPUT_TOKENS = 1024

DEFAULT_MODEL = "gemini-3.6-flash"


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """
    Loads the Gemini client once and reuses it — same reasoning as
    get_anthropic_client() in anthropic_client.py.
    """
    settings = get_settings()
    print(settings.GEMINI_API_KEY)
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _to_gemini_contents(messages: list[ChatMessage]) -> list[types.Content]:
    """
    Translates the shared {"role": "user"|"assistant", "content": str}
    message format into Gemini's Content/Part objects.

    Gemini uses "model" as the assistant role, not "assistant" — this is
    the one silent-mismatch spot that would otherwise cause every
    assistant turn in history to be misattributed to the user without
    erroring.
    """
    contents = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=message["content"])])
        )
    return contents


async def get_chat_completion(
    system_prompt: str,
    messages: list[ChatMessage],
    model: str | None = None,
) -> str:
    """
    Sends a system prompt + conversation history to Gemini, returns the
    reply as plain text.

    `messages` should NOT include the system prompt as a message — same
    convention as anthropic_client.py — it's passed via
    GenerateContentConfig.system_instruction instead.
    """
    client = _get_client()

    response = await client.aio.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=_to_gemini_contents(messages),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.7,
        ),
    )

    return response.text


async def get_chat_completion_stream(
    system_prompt: str,
    messages: list[ChatMessage],
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming counterpart to get_chat_completion() — same signature as
    the Anthropic and llama.cpp versions, `async for`-able.

    Note the double-await shape here: generate_content_stream() itself is
    a coroutine that resolves to an async iterator, so it needs `await`
    on the call AND `async for` on iterating it — easy to get wrong (a
    known sharp edge in this SDK, not specific to this codebase). Getting
    only one of the two right either raises a TypeError immediately or
    silently returns an un-iterated coroutine, so this shape is
    deliberate, not stylistic.
    """
    client = _get_client()

    stream = await client.aio.models.generate_content_stream(
        model=model or DEFAULT_MODEL,
        contents=_to_gemini_contents(messages),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.7,
        ),
    )

    async for chunk in stream:
        if chunk.text:
            yield chunk.text