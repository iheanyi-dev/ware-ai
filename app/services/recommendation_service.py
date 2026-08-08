# app/services/recommendation_service.py
"""
Recommendation service.

Two independent signal sources, merged into one ranked list:

  1. Instructor-based: other courses taught by instructors the user is
     already enrolled with. Strong signal — if a user liked one course
     enough to enroll, they're plausibly interested in more from the same
     teacher.

  2. Content-based: courses whose embedding is closest (cosine similarity)
     to the average embedding of the user's enrolled courses. Uses the
     Phase 2 fine-tuned model's vectors, stored on Course.embedding.

Both exclude courses the user is already enrolled in. Used by the
recommendations API endpoint (next step).
"""

import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Course, Enrollment
from app.schemas.recommendation import RecommendedCourse

# How many candidates to pull from EACH signal before merging. Kept higher
# than the final result limit so the merge step (which combines/dedupes)
# has enough material to work with — pulling exactly `limit` from each
# source would under-fill the final list whenever the two sources overlap.
CANDIDATES_PER_SOURCE = 15


async def _get_enrolled_course_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Shared by both recommendation functions below — every recommendation
    query needs to know what to exclude."""
    result = await db.execute(
        select(Enrollment.course_id).where(Enrollment.user_id == user_id)
    )
    return set(result.scalars().all())


async def get_instructor_based_candidates(
    db: AsyncSession, user_id: uuid.UUID, enrolled_course_ids: set[uuid.UUID]
) -> list[Course]:
    """
    Other courses by instructors this user has already enrolled with,
    ranked by rating (highest first) as a reasonable default ordering
    within a single instructor's catalog — revisit if a better signal
    (e.g. popularity) becomes available later.
    """
    if not enrolled_course_ids:
        return []

    instructor_ids_result = await db.execute(
        select(Course.instructor_id)
        .where(Course.id.in_(enrolled_course_ids))
        .distinct()
    )
    instructor_ids = set(instructor_ids_result.scalars().all())

    if not instructor_ids:
        return []

    stmt = (
        select(Course)
        .options(selectinload(Course.instructor))
        .where(Course.instructor_id.in_(instructor_ids))
        .where(Course.id.notin_(enrolled_course_ids))
        .order_by(Course.rating.desc().nulls_last())
        .limit(CANDIDATES_PER_SOURCE)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_content_based_candidates(
    db: AsyncSession, user_id: uuid.UUID, enrolled_course_ids: set[uuid.UUID]
) -> list[Course]:
    """
    Courses most similar (cosine distance) to the AVERAGE embedding of the
    user's enrolled courses. Averaging gives one representative "taste
    vector" per user rather than running N separate similarity searches
    (one per enrolled course) and merging those — simpler, and works well
    when a user's enrollments share a coherent theme (which our seed data
    is deliberately structured to do).

    Revisit if users end up with wildly unrelated enrollments — averaging
    unrelated vectors can land in a semantic "no man's land" between them.
    Per-course search + merge would handle that better at the cost of
    more queries.
    """
    if not enrolled_course_ids:
        return []

    embeddings_result = await db.execute(
        select(Course.embedding)
        .where(Course.id.in_(enrolled_course_ids))
        .where(Course.embedding.is_not(None))
    )
    embeddings = [e for e in embeddings_result.scalars().all() if e is not None]

    if not embeddings:
        # Enrolled courses exist but none have embeddings yet — likely
        # means the backfill script hasn't been run. Fail soft rather than
        # erroring, since instructor-based recs can still work fine.
        return []

    # Average, then re-normalize to unit length — averaging normalized
    # vectors doesn't preserve unit length, and our stored embeddings are
    # unit-normalized (see embed_text's normalize_embeddings=True), so
    # comparisons stay consistent with how the model was trained.
    avg_embedding = np.mean(np.array(embeddings), axis=0)
    norm = np.linalg.norm(avg_embedding)
    if norm > 0:
        avg_embedding = avg_embedding / norm
    query_vector = avg_embedding.tolist()

    stmt = (
        select(Course)
        .options(selectinload(Course.instructor))
        .where(Course.id.notin_(enrolled_course_ids))
        .where(Course.embedding.is_not(None))
        .order_by(Course.embedding.cosine_distance(query_vector))
        .limit(CANDIDATES_PER_SOURCE)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _merge_and_rank(
    instructor_candidates: list[Course],
    content_candidates: list[Course],
    limit: int,
) -> list[RecommendedCourse]:
    """
    Combines both candidate lists into one ranked result.

    Scoring: each list is already ordered best-to-worst by its own source,
    so we score by POSITION within that list (first place scores highest)
    rather than trying to compare raw ratings against raw cosine
    distances — those aren't on the same scale, so summing them directly
    would be meaningless. A course appearing in both lists sums both
    positional scores, naturally floating courses that both signals agree
    on to the top — that's the "both" case in RecommendedCourse.reason.

    This is a deliberately simple weighting scheme (documented here as an
    open decision) — revisit if one signal turns out to produce much
    weaker matches than the other in practice.
    """
    scores: dict[uuid.UUID, float] = {}
    reasons: dict[uuid.UUID, set[str]] = {}
    course_lookup: dict[uuid.UUID, Course] = {}

    for idx, course in enumerate(instructor_candidates):
        # Linearly decaying score: 1.0 for 1st place, down toward 0 by the
        # end of CANDIDATES_PER_SOURCE.
        position_score = 1.0 - (idx / CANDIDATES_PER_SOURCE)
        scores[course.id] = scores.get(course.id, 0.0) + position_score
        reasons.setdefault(course.id, set()).add("instructor")
        course_lookup[course.id] = course

    for idx, course in enumerate(content_candidates):
        position_score = 1.0 - (idx / CANDIDATES_PER_SOURCE)
        scores[course.id] = scores.get(course.id, 0.0) + position_score
        reasons.setdefault(course.id, set()).add("similar_content")
        course_lookup[course.id] = course

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]

    results: list[RecommendedCourse] = []
    for course_id in ranked_ids:
        course = course_lookup[course_id]
        course_reasons = reasons[course_id]

        if course_reasons == {"instructor", "similar_content"}:
            reason: str = "both"
        else:
            reason = next(iter(course_reasons))  # the single reason present

        results.append(
            RecommendedCourse(
                id=course.id,
                title=course.title,
                description=course.description,
                category=course.category,
                price=float(course.price),
                rating=float(course.rating) if course.rating is not None else None,
                instructor_id=course.instructor_id,
                instructor_name=course.instructor.name,
                reason=reason,  # type: ignore[arg-type]  # Literal narrows fine at runtime
            )
        )

    return results


async def get_recommendations_for_user(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 10
) -> list[RecommendedCourse]:
    """
    Main entry point — call this from the API endpoint. Runs both signal
    sources and returns one merged, ranked list capped at `limit`.
    """
    enrolled_course_ids = await _get_enrolled_course_ids(db, user_id)

    instructor_candidates = await get_instructor_based_candidates(db, user_id, enrolled_course_ids)
    content_candidates = await get_content_based_candidates(db, user_id, enrolled_course_ids)

    return _merge_and_rank(instructor_candidates, content_candidates, limit)