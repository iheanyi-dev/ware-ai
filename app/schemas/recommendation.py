# app/schemas/recommendation.py
"""
Pydantic schemas for recommendation responses. Kept separate from the
SQLAlchemy Course model so the API response shape can evolve independently
of the DB schema (e.g. we don't want to accidentally expose `embedding`,
a 384-float array, in an API response).
"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RecommendedCourse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # lets us build this directly from a Course ORM object

    id: uuid.UUID
    title: str
    description: str
    category: str
    price: float
    rating: float | None
    instructor_id: uuid.UUID
    instructor_name: str

    # Why this course was recommended. "both" means it scored highly on
    # both instructor-based and content-based signals — the strongest
    # possible recommendation, since two independent signals agree.
    reason: Literal["instructor", "similar_content", "both"]


class RecommendationResponse(BaseModel):
    user_id: uuid.UUID
    recommendations: list[RecommendedCourse]