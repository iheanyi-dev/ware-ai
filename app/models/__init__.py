# Re-exports all models from one place so Alembic (and the rest of the app)
# can do `from app.models import Instructor, Course, ...` instead of
# reaching into individual files. This also matters for Alembic autogenerate:
# every model must be imported somewhere Alembic's env.py can see it, or it
# won't show up in the schema comparison.

from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.instructor import Instructor
from app.models.user import User

__all__ = ["Instructor", "Course", "Enrollment", "User", "ChatConversation", "ChatMessage" ]