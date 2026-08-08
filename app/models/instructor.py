# app/models/instructor.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Instructor(Base):
    """
    An instructor who teaches one or more courses on the platform.
    """

    __tablename__ = "instructors"

    # UUID primary key generated in Python (uuid4) rather than relying on a
    # Postgres extension like pgcrypto — one less thing to set up in the DB.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Free-text bio, used both for display and as input text when we embed
    # instructor info for search/chatbot context later.
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Reverse side of Course.instructor — lets us do instructor.courses to
    # get every course they teach. "Course" is a string here because the
    # Course class doesn't exist yet in this file (defined in course.py);
    # SQLAlchemy resolves the string once both classes are registered.
    courses: Mapped[list["Course"]] = relationship(back_populates="instructor")

    def __repr__(self) -> str:
        return f"<Instructor id={self.id} name={self.name!r}>"