# scripts/backfill_course_embeddings.py
"""
Backfill embeddings for existing courses (Phase 3).

Run with: uv run python -m scripts.backfill_course_embeddings

One-time (or re-run-as-needed) script that embeds every course currently
in the database using the Phase 2 fine-tuned model, and writes the result
into Course.embedding. Needed because:
  - courses seeded before this column existed have embedding = NULL
  - re-running after a model update (re-fine-tune) requires re-embedding
    everything, since old and new model embeddings aren't comparable

Safe to re-run any time — it always re-embeds every course and overwrites
existing values, rather than skipping ones that already have an embedding.
That's intentional: if you've re-trained the model, you WANT everything
re-embedded, not silently left stale.
"""

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Course
from app.services.embedding_service import build_course_text, embed_texts


async def backfill_embeddings() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Course))
        courses = result.scalars().all()

        if not courses:
            print("No courses found — run the seed script first.")
            return

        # Batch-embed all courses in one forward pass instead of looping
        # embed_text() per course — much faster, especially on CPU.
        texts = [build_course_text(c.title, c.description) for c in courses]
        embeddings = embed_texts(texts)

        for course, embedding in zip(courses, embeddings):
            course.embedding = embedding

        await session.commit()

    print(f"Backfilled embeddings for {len(courses)} courses.")


if __name__ == "__main__":
    asyncio.run(backfill_embeddings())