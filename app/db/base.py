from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy models in this project.

    Every model (Course, Instructor, Enrollment, User) inherits from this
    class. Alembic also imports this Base's metadata to autogenerate
    migrations by comparing it against the actual database schema.
    """

    pass