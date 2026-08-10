# app/services/chatbot_service.py — full updated version

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatConversation, ChatMessage
from app.services.gemini_client import get_chat_completion, get_chat_completion_stream
from app.services.chat_context_service import format_courses_for_prompt, retrieve_relevant_courses
from app.services.chat_summarization_service import summarize_new_messages
#from app.services.faq_knowledge_base import format_faq_for_prompt
from app.services.chat_context_service import get_relevant_faq_chunks

# Same ChatMessage shape used across all three client modules:
# {"role": "user"|"assistant", "content": str}
AnthropicChatMessage = dict[str, str]

SYSTEM_PROMPT_TEMPLATE = """\
You are Wareford Assistant, a helpful assistant embedded in an online learning platform where \
users browse, purchase, and take courses taught by instructors.

Your job is to help users navigate the site and answer questions about \
how it works, using the reference material below. You can also help users \
find courses using the "Matching courses" section, which is retrieved \
based on their current message.

Guidelines:
- Only use the FAQ and course information provided below — do not invent \
policies, features, prices, or courses that aren't listed.
- If the "Matching courses" section doesn't actually relate to what the \
user asked, ignore it rather than forcing it into your answer.
- If a question needs specifics you don't have (e.g. their personal order \
history, account details), say so plainly and suggest they check their \
account page or contact support — don't guess.
- Keep answers concise and conversational. This is a chat interface, not \
a documentation page
- When you are not sure of an answer or the user asked a question not related to what you are given, simply tell the user to contact us on (+234) 8071885074, Email: contact@waresford.com, WHATSAPP: (+234) 8071885074
.

{summary_section}
--- SITE FAQ ---
{faq_content}

--- MATCHING COURSES FOR THIS MESSAGE ---
{course_context}
"""

# Once total message count exceeds this, older messages get summarized
# instead of sent verbatim. Chosen so short/typical conversations (a
# handful of exchanges) never trigger summarization at all — only genuinely
# long ones do, which is where the token savings actually matter.
SUMMARY_TRIGGER_MESSAGES = 20

# How many of the MOST RECENT messages are always sent verbatim, regardless
# of summarization — keeps immediate context sharp (exact wording of the
# last few turns matters more than older ones).
KEEP_RECENT_VERBATIM = 8


async def _get_or_create_conversation(
    db: AsyncSession, conversation_id: int | None, user_id: int | None
) -> ChatConversation:
    if conversation_id is not None:
        result = await db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            return conversation

    conversation = ChatConversation(user_id=user_id)
    db.add(conversation)
    await db.flush()
    return conversation


async def _get_history_for_prompt(
    db: AsyncSession, conversation: ChatConversation
) -> tuple[str | None, list[AnthropicChatMessage]]:
    """
    Returns (summary_text, verbatim_messages_for_prompt).

    If the conversation hasn't hit SUMMARY_TRIGGER_MESSAGES yet, no
    summarization happens — summary_text is whatever was already stored
    (usually None) and all messages are returned verbatim, same as before
    we added summarization.

    If it HAS hit the threshold, any messages older than the
    KEEP_RECENT_VERBATIM window that aren't already covered by
    conversation.summary get folded in via summarize_new_messages(), the
    conversation row is updated, and only the recent window is returned
    for the prompt — keeping prompt size roughly constant no matter how
    long the conversation grows.
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at)
    )
    all_messages = list(result.scalars().all())

    if len(all_messages) <= SUMMARY_TRIGGER_MESSAGES:
        anthropic_history = [{"role": m.role, "content": m.content} for m in all_messages]
        return conversation.summary, anthropic_history

    recent_messages = all_messages[-KEEP_RECENT_VERBATIM:]
    older_messages = all_messages[:-KEEP_RECENT_VERBATIM]

    # Only summarize the slice not already folded into the existing
    # summary — this is what makes summarization incremental rather than
    # re-processing the whole conversation on every single turn after the
    # threshold is crossed.
    if conversation.summary_updated_at is not None:
        new_to_summarize = [
            m for m in older_messages if m.created_at > conversation.summary_updated_at
        ]
    else:
        new_to_summarize = older_messages

    if new_to_summarize:
        updated_summary = summarize_new_messages(conversation.summary, new_to_summarize)
        conversation.summary = updated_summary
        conversation.summary_updated_at = new_to_summarize[-1].created_at
        # Not committing here — get_chatbot_reply() commits everything
        # together at the end of the turn, keeping this an atomic update.

    anthropic_history = [{"role": m.role, "content": m.content} for m in recent_messages]
    return conversation.summary, anthropic_history


async def _prepare_turn(
    db: AsyncSession,
    user_message: str,
    conversation_id: int | None,
    user_id: int | None,
) -> tuple[ChatConversation, str, list[AnthropicChatMessage]]:
    """
    Shared setup for a chat turn: resolve/create the conversation, build the
    (possibly summarized) history, pull FAQ + course context, and assemble
    the final system prompt and message list.

    Used by both get_chatbot_reply() (non-streaming) and
    stream_chatbot_reply() (streaming) so the two paths can't drift apart on
    prompt construction — only what happens with the completion call differs.
    """
    conversation = await _get_or_create_conversation(db, conversation_id, user_id)

    summary, anthropic_history = await _get_history_for_prompt(db, conversation)

    summary_section = f"--- CONVERSATION SO FAR (summarized) ---\n{summary}\n" if summary else ""

    faq_content = await get_relevant_faq_chunks(user_message, db)
    relevant_courses = await retrieve_relevant_courses(db, user_message)
    course_context = format_courses_for_prompt(relevant_courses)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        summary_section=summary_section,
        faq_content=faq_content,
        course_context=course_context,
    )

    messages: list[AnthropicChatMessage] = [
        *anthropic_history,
        {"role": "user", "content": user_message},
    ]

    return conversation, system_prompt, messages


async def get_chatbot_reply(
    db: AsyncSession,
    user_message: str,
    conversation_id: int | None = None,
    user_id: int | None = None,
) -> tuple[str, int]:
    """
    Main entry point (non-streaming). Returns (assistant_reply, conversation_id).
    """
    conversation, system_prompt, messages = await _prepare_turn(
        db, user_message, conversation_id, user_id
    )

    reply = await get_chat_completion(system_prompt, messages)  # uses settings.anthropic_model by default

    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=user_message))
    db.add(ChatMessage(conversation_id=conversation.id, role="assistant", content=reply))
    await db.commit()

    return reply, conversation.id


async def stream_chatbot_reply(
    db: AsyncSession,
    user_message: str,
    conversation_id: int | None = None,
    user_id: int | None = None,
):
    """
    Streaming entry point. Async-generator, yields (new_conversation_id, chunk)
    tuples where exactly one of the two is set per item:

      - First item: (conversation.id, None) — sent once, immediately, before
        any generated text, so the caller learns the conversation id right
        away (needed for brand-new conversations, since it doesn't exist
        until _prepare_turn() creates it).
      - Every following item: (None, chunk) — a piece of generated text.

    The full exchange (user message + assembled assistant reply) is saved to
    the DB only after the stream is fully exhausted — same save shape as
    get_chatbot_reply(), just deferred until generation completes rather
    than happening before it starts.

    Caveat: if the caller stops iterating early (e.g. client disconnects
    mid-stream), this generator is abandoned before reaching the DB save,
    so the partial reply is NOT persisted. If you want partial replies kept,
    wrap the save in a try/finally instead — deliberately left out here
    since a half-generated answer being saved as if it were complete has its
    own downsides (a future turn would treat it as the full prior answer).
    """
    conversation, system_prompt, messages = await _prepare_turn(
        db, user_message, conversation_id, user_id
    )

    yield conversation.id, None

    full_reply_parts: list[str] = []
    async for chunk in get_chat_completion_stream(system_prompt, messages):
        full_reply_parts.append(chunk)
        yield None, chunk

    full_reply = "".join(full_reply_parts)

    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=user_message))
    db.add(ChatMessage(conversation_id=conversation.id, role="assistant", content=full_reply))
    await db.commit()