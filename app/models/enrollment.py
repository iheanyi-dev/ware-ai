import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
#from app.models import Course, User

class Enrollment(Base):
    """
    Records that a user enrolled in (purchased/started) a course.
    This is the core signal our recommendation engine reads from —
    both instructor-based and content-based recs start by looking up
    a user's enrollments.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        # A user can't enroll in the same course twice — enforced at the
        # database level, not just in application code.
        UniqueConstraint("user_id", "course_id", name="uq_user_course_enrollment"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id"), nullable=False, index=True
    )

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Using backref instead of back_populates here: it auto-creates the
    # reverse attribute (course.enrollments / user.enrollments) without
    # needing to go back and edit the Course/User model files directly.
    # back_populates is more explicit and is what we used for
    # Instructor <-> Course; backref is the more convenient shorthand for
    # this join-table case where we don't need anything else on those models.
    course: Mapped["Course"] = relationship(backref="enrollments")
    user: Mapped["User"] = relationship(backref="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment user_id={self.user_id} course_id={self.course_id}>"