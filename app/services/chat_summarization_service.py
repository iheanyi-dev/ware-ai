# app/services/chat_summarization_service.py
"""
Conversation history summarization.

Once a conversation grows past SUMMARY_TRIGGER_MESSAGES, older turns get
folded into a running text summary (via a cheap/fast model call) instead
of being sent verbatim on every subsequent request. This keeps the main
chatbot's prompt size roughly constant regardless of how long the
conversation gets, trading a small Haiku call for a much larger reduction
in Sonnet input tokens on every turn after that.

Runs incrementally: each call only summarizes messages newer than
conversation.summary_updated_at, folding them into the EXISTING summary
rather than re-summarizing the whole conversation from scratch every time.
"""

from app.models import ChatConversation, ChatMessage
from app.services.anthropic_client import get_chat_completion
from app.core.config import get_settings

SUMMARIZATION_SYSTEM_PROMPT = """\
You summarize conversations between a user and a customer support/course \
recommendation chatbot for an online learning platform. You will be given \
an existing summary (which may be empty) and a block of new messages.

Produce an updated summary that captures: what the user is trying to \
accomplish, any preferences or constraints they've stated (topics of \
interest, budget, experience level, etc.), and any unresolved questions. \
Do not include pleasantries or small talk. Be concise — a few sentences \
is usually enough, even for a long conversation. Write it as plain \
narrative text, not a transcript."""


def _format_messages_for_summarization(messages: list[ChatMessage]) -> str:
    lines = [f"{msg.role.upper()}: {msg.content}" for msg in messages]
    return "\n".join(lines)


def summarize_new_messages(existing_summary: str | None, new_messages: list[ChatMessage]) -> str:
    """
    Calls the cheap/fast model to fold `new_messages` into `existing_summary`.
    Returns the updated summary text. Pure function w.r.t. the DB — caller
    is responsible for persisting the result and updating summary_updated_at.
    """
    settings = get_settings()

    prompt_parts = []
    if existing_summary:
        prompt_parts.append(f"EXISTING SUMMARY:\n{existing_summary}")
    else:
        prompt_parts.append("EXISTING SUMMARY: (none yet — this is the first summarization pass)")

    prompt_parts.append(f"\nNEW MESSAGES TO FOLD IN:\n{_format_messages_for_summarization(new_messages)}")

    user_prompt = "\n".join(prompt_parts)

    return get_chat_completion(
        system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        model=settings.anthropic_summary_model,  # cheap/fast model, not the main chatbot model
    )