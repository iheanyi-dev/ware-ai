# app/schemas/sync.py
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CourseSyncPayload(BaseModel):
    id: int
    title: str
    description: str
    category: str
    price: Decimal
    instructor_id: int
    rating: Optional[Decimal] = None


class InstructorSyncPayload(BaseModel):
    id: int
    name: str
    bio: Optional[str] = None


class UserSyncPayload(BaseModel):
    id: int
    name: str
    email: str


class EnrollmentSyncPayload(BaseModel):
    id: int | None = None
    user_id: int
    course_id: int