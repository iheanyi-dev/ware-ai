# app/api/routes/recommendations.py
"""
Recommendations API.

Exposes GET /users/{user_id}/recommendations, backed by the merge logic in
app/services/recommendation_service.py.

"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import User
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation_service import get_recommendations_for_user, get_recommendations_by_text

from app.core.security import verify_internal_api_key

router = APIRouter(
    prefix="/users",
    tags=["recommendations"],
    #dependencies=[Depends(verify_internal_api_key)],  # applies to every route in this router
)

@router.get("/{user_id}/recommendations", response_model=RecommendationResponse)
async def get_user_recommendations(
    user_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),

) -> RecommendationResponse:
    """
    Returns up to `limit` recommended courses for a user, combining
    instructor-based and content-based (embedding similarity) signals.

    404s if the user doesn't exist — distinguishes "unknown user" from
    "known user with no recommendations yet" (the latter returns 200 with
    an empty list, e.g. a user with zero enrollments).
    """
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    recommendations = await get_recommendations_for_user(db, user_id, limit=limit)

    return RecommendationResponse(user_id=user_id, recommendations=recommendations)

@router.post("/recommendations", response_model= RecommendationResponse)
async def get_recommendations(
    request,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),

):
    """
    Returns up to `limit` recommended courses 

    """
    text = request.text

    recommendations = await get_recommendations_by_text(db, text, limit=limit)

    return RecommendationResponse(recommendations=recommendations)