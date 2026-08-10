"""
Synthetic seed data loader.

Run with: uv run python -m app.db.seed

Reads instructor/course/user/enrollment data from seed_data.py and inserts
it into the database. This script is idempotent: it wipes existing rows
(in FK-safe order) before inserting fresh data, so it's safe to re-run any
time during development.

Populates instructors, courses, users, and enrollments with a deliberately
coherent structure (not random) so that:
  - instructor-based recommendations have something real to surface
  - content-based (embedding) recommendations have believable category
    clusters to learn from

This script is idempotent: it wipes existing rows (in FK-safe order) before
inserting fresh data, so it's safe to re-run any time during development.
"""

import asyncio

from sqlalchemy import delete

from scripts.seed_data import COURSES, ENROLLMENTS, INSTRUCTORS, USERS
from app.db.session import AsyncSessionLocal
from app.models import Course, Enrollment, Instructor, User
from app.services.embedding_service import embed_text

async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Wipe in FK-safe order: children before parents.
        await session.execute(delete(Enrollment))
        await session.execute(delete(Course))
        await session.execute(delete(Instructor))
        await session.execute(delete(User))
        await session.commit()

        # Insert instructors, keep a key -> ORM object map for course FK linking.
        instructor_map: dict[str, Instructor] = {}
        for i, data in enumerate(INSTRUCTORS):
            instructor = Instructor(id=i+1, name=data["name"], bio=data["bio"])
            session.add(instructor)
            instructor_map[data["key"]] = instructor
        await session.flush()  # assigns generated UUIDs without committing yet

        # Insert courses, linking via the `instructor` relationship — SQLAlchemy
        # fills in instructor_id automatically from the related object.
        course_map: dict[str, Course] = {}
        for i, data in enumerate(COURSES):
            course = Course(
                id = i + 1,
                title=data["title"],
                description=data["description"],
                category=data["category"],
                price=data["price"],
                rating=data["rating"],
                embedding = embed_text(f"{data["title"]} . {data["description"]}"),
                instructor=instructor_map[data["instructor"]],
            )
            session.add(course)
            course_map[data["title"]] = course
        await session.flush()

        # Insert users.
        user_map: dict[str, User] = {}
        for i, data in enumerate(USERS):
            user = User(id= i+1, name=data["name"], email=data["email"])
            session.add(user)
            user_map[data["key"]] = user
        await session.flush()

        # Insert enrollments, linking via relationships the same way.
        for user_key, course_title in ENROLLMENTS:
            enrollment = Enrollment(
                user=user_map[user_key],
                course=course_map[course_title],
            )
            session.add(enrollment)

        await session.commit()

    print(
        f"Seeded {len(INSTRUCTORS)} instructors, {len(COURSES)} courses, "
        f"{len(USERS)} users, {len(ENROLLMENTS)} enrollments."
    )


if __name__ == "__main__":
    asyncio.run(seed())