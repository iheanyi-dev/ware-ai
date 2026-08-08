# app/models/course.py
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models import Instructor

# Output dimension of all-MiniLM-L6-v2 (and our fine-tuned version of it —
# fine-tuning changes weights, not the output size). If we ever swap base
# models later, this constant is the one place that needs updating, and a
# new migration would be required since it changes the column type itself.
EMBEDDING_DIM = 384


class Course(Base):
    """
    A course available for purchase on the platform, taught by exactly one
    instructor (confirmed: no co-teaching support needed).
    """

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Full description — this is also the text we feed into the embedding
    # model to produce `embedding` below, so keep it descriptive rather
    # than terse.
    description: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Numeric (not Float) for money — avoids floating-point rounding errors
    # on prices. precision=10, scale=2 supports values up to 99,999,999.99.
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Average rating, denormalized here for fast reads (recomputed whenever
    # a new review comes in, once the review system exists). Nullable
    # because a brand-new course has no ratings yet.
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    # Content embedding of `title + description`, produced by 
    # fine-tuned model. Nullable because:
    #   - existing seeded courses won't have one until the Phase 3 backfill
    #     script runs
    #   - newly created courses won't have one until the embedding
    #     generation step runs for them (wired in later, when course
    #     creation exists on the main backend)
    # This is what pgvector similarity search (content-based recommendations)
    # queries against.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    # The "many" side of the relationship holds the foreign key.
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instructors.id"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Gives us course.instructor to access the full Instructor object,
    # not just its id — the other half of Instructor.courses.
    instructor: Mapped[Instructor] = relationship(back_populates="courses")

    def __repr__(self) -> str:
        return f"<Course id={self.id} title={self.title!r}>"