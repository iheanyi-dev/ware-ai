import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """
    A student/learner account on the platform. This is intentionally minimal —
    your main backend almost certainly already owns the full user record
    (auth, profile, payment info, etc). This service only needs enough of a
    User row to join against for recommendations, so we keep it lean rather
    than duplicating your entire user schema here.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # In production this ID would typically match the user ID from your main
    # backend's own user table (not a new, unrelated ID), so joins between
    # systems stay consistent. Worth revisiting when we wire in real data.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Note: `user.enrollments` becomes available automatically via the
    # backref defined on Enrollment.user — nothing needed here for that.

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"