# app/services/anthropic_client.py
"""
Thin wrapper around the Anthropic SDK.

Kept deliberately minimal — a single function that takes a system prompt
and conversation history, returns the model's text reply. Everything
chatbot-specific (what goes IN the system prompt: FAQ content, retrieved
course context, etc.) lives in chatbot_service.py, not here. This
separation means if we ever swap providers or add streaming, only this
file changes — callers don't need to know or care.
"""

from functools import lru_cache

import anthropic

from app.core.config import get_settings

# Conversation history is a list of {"role": "user"|"assistant", "content": str}
# dicts — this matches the Anthropic API's message format directly, so no
# translation layer is needed when we pass it through.
ChatMessage = dict[str, str]

MAX_TOKENS = 1024  # response length cap; adjust if answers are getting cut off


@lru_cache(maxsize=1)
def get_anthropic_client() -> anthropic.Anthropic:
    """
    Loads the Anthropic client once and reuses it — same reasoning as
    get_embedding_model() in Phase 3: client construction is cheap here,
    but centralizing it means the API key is read from settings in exactly
    one place.
    """
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def get_chat_completion(
    system_prompt: str,
    messages: list[ChatMessage],
    model: str | None = None,
) -> str:
    """
    Sends a system prompt + conversation history to Claude, returns the
    reply as plain text.

    `model` defaults to settings.anthropic_model (the main chatbot model)
    if not given. Passing it explicitly lets callers — like the
    summarization service — use a cheaper/faster model for a different
    kind of call without duplicating this function.

    `messages` should NOT include the system prompt as a message — the
    Anthropic API takes system instructions via the separate `system`
    parameter, not as a message with role "system".
    """
    settings = get_settings()
    client = get_anthropic_client()

    response = client.messages.create(
        model=model or settings.ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    return "".join(
        block.text for block in response.content if block.type == "text"
    )
    