# app/services/chat_context_service.py
"""
Retrieves relevant course/instructor context for a chatbot query.

Reuses the Phase 3 embedding service — the user's chat message is embedded
with the SAME fine-tuned model used for courses, then compared against
Course.embedding via pgvector. This means the chatbot benefits from the
same fine-tuning that powers recommendations: a question like "something
similar to React" will surface web-dev courses even without exact keyword
overlap.

This is deliberately a SEPARATE retrieval path from recommendation_service.py
— recommendations are personalized (based on a user's enrollment history),
this is query-based (based on what the user just typed). They share the
embedding model and the pgvector column, nothing else.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Course
from app.services.embedding_service import embed_text

# How many courses to pull into context per chat turn. Kept small — this
# text goes straight into the prompt on every message, so a larger number
# increases both cost and the chance of Claude citing something only
# loosely relevant. 5 is enough to answer "what courses do you have on X"
# well without bloating the prompt.
CONTEXT_COURSES_LIMIT = 5


async def retrieve_relevant_courses(db: AsyncSession, user_message: str) -> list[Course]:
    """
    Embeds the user's message and returns the most similar courses via
    pgvector cosine distance. Returns an empty list (not an error) if no
    courses have embeddings yet — same fail-soft approach as
    get_content_based_candidates() in recommendation_service.py, since a
    chatbot with no course context can still answer general FAQ questions.
    """
    query_vector = embed_text(user_message)

    stmt = (
        select(Course)
        .options(selectinload(Course.instructor))
        .where(Course.embedding.is_not(None))
        .order_by(Course.embedding.cosine_distance(query_vector))
        .limit(CONTEXT_COURSES_LIMIT)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def format_courses_for_prompt(courses: list[Course]) -> str:
    """
    Formats retrieved courses into text for the chatbot's system prompt.
    Kept plain and factual (title, instructor, category, price, rating,
    short description) — Claude does the work of deciding which of these
    are actually relevant to what the user asked and how to phrase the
    answer; this function's only job is presenting accurate raw material.
    """
    if not courses:
        return "No matching courses found for this query."

    lines = []
    for course in courses:
        rating_str = f"{course.rating:.1f}/5" if course.rating is not None else "not yet rated"
        lines.append(
            f"- \"{course.title}\" by {course.instructor.name} "
            f"({course.category}, ${course.price:.2f}, {rating_str})\n"
            f"  {course.description}"
        )

    return "\n".join(lines)