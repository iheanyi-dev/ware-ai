# app/services/chatbot_service.py — full updated version

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatConversation, ChatMessage
from app.services.anthropic_client import ChatMessage as AnthropicChatMessage
from app.services.anthropic_client import get_chat_completion
from app.services.chat_context_service import format_courses_for_prompt, retrieve_relevant_courses
from app.services.chat_summarization_service import summarize_new_messages
from app.services.faq_knowledge_base import format_faq_for_prompt

SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful assistant embedded in an online learning platform where \
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
a documentation page.

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
    db: AsyncSession, conversation_id: uuid.UUID | None, user_id: uuid.UUID | None
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


async def get_chatbot_reply(
    db: AsyncSession,
    user_message: str,
    conversation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[str, uuid.UUID]:
    """
    Main entry point. Returns (assistant_reply, conversation_id).
    """
    conversation = await _get_or_create_conversation(db, conversation_id, user_id)

    summary, anthropic_history = await _get_history_for_prompt(db, conversation)

    summary_section = f"--- CONVERSATION SO FAR (summarized) ---\n{summary}\n" if summary else ""

    faq_content = format_faq_for_prompt()
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

    reply = get_chat_completion(system_prompt, messages)  # uses settings.anthropic_model by default

    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=user_message))
    db.add(ChatMessage(conversation_id=conversation.id, role="assistant", content=reply))
    await db.commit()

    return reply, conversation.id