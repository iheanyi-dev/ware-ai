# app/api/routes/sync.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
#from app.api.deps import verify_internal_api_key
from app.models.course import Course
from app.models.instructor import Instructor
from app.models.user import User
from app.models.enrollment import Enrollment
from app.schemas.sync import (
    CourseSyncPayload,
    InstructorSyncPayload,
    UserSyncPayload,
    EnrollmentSyncPayload,
)
from app.services.embedding_service import embed_text

router = APIRouter(
    prefix="/sync", tags=["sync"], 
    #dependencies=[Depends(verify_internal_api_key)]
    )


@router.post("/courses")
async def sync_course(payload: CourseSyncPayload, db: AsyncSession = Depends(get_db)):
    # instructor must already exist — FK is NOT NULL on Course.instructor_id
    instructor_check = await db.execute(
        select(Instructor).where(Instructor.id == payload.instructor_id)
    )
    if not instructor_check.scalar_one_or_none():
        raise HTTPException(
            status_code=422,
            detail=f"Instructor {payload.instructor_id} not found — sync instructor before course",
        )

    result = await db.execute(select(Course).where(Course.id == payload.id))
    course = result.scalar_one_or_none()

    embedding = embed_text(f"{payload.title} . {payload.description}")

    if course:
        course.title = payload.title
        course.description = payload.description
        course.category = payload.category
        course.price = payload.price
        course.instructor_id = payload.instructor_id
        if payload.rating is not None:
            course.rating = payload.rating
        course.embedding = embedding
    else:
        course = Course(
            id=payload.id,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            price=payload.price,
            instructor_id=payload.instructor_id,
            rating=payload.rating,
            embedding=embedding,
        )
        db.add(course)

    await db.commit()
    return {"status": "ok", "course_id": str(payload.id)}


@router.post("/instructors")
async def sync_instructor(payload: InstructorSyncPayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Instructor).where(Instructor.id == payload.id))
    instructor = result.scalar_one_or_none()

    if instructor:
        instructor.name = payload.name
        instructor.bio = payload.bio
    else:
        instructor = Instructor(id=payload.id, name=payload.name, bio=payload.bio)
        db.add(instructor)

    await db.commit()
    return {"status": "ok", "instructor_id": str(payload.id)}


@router.post("/users")
async def sync_user(payload: UserSyncPayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == payload.id))
    user = result.scalar_one_or_none()

    if user:
        user.name = payload.name
        user.email = payload.email
    else:
        user = User(id=payload.id, name=payload.name, email=payload.email)
        db.add(user)

    await db.commit()
    return {"status": "ok", "user_id": str(payload.id)}


@router.post("/enrollments")
async def sync_enrollment(payload: EnrollmentSyncPayload, db: AsyncSession = Depends(get_db)):
    # both sides of the FK must already exist
    user_check = await db.execute(select(User).where(User.id == payload.user_id))
    if not user_check.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=f"User {payload.user_id} not found")

    course_check = await db.execute(select(Course).where(Course.id == payload.course_id))
    if not course_check.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=f"Course {payload.course_id} not found")

    result = await db.execute(select(Enrollment).where(Enrollment.id == payload.id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Enrollment already synced")

    # the DB-level UniqueConstraint on (user_id, course_id) will also catch
    # this, but checking first avoids an ugly IntegrityError round-trip
    dup = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == payload.user_id,
            Enrollment.course_id == payload.course_id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already enrolled in this course")

    enrollment = Enrollment(user_id=payload.user_id, course_id=payload.course_id)
    db.add(enrollment)
    await db.commit()
    return {"status": "ok", "enrollment_id": str(enrollment.id)}