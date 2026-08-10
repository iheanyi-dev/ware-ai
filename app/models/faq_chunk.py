"""
app/models/faq_chunk.py

Stores crawled + chunked site content with embeddings, queried the same
way recommendation_service.py queries Course.embedding — pgvector
cosine_distance search, just against FAQ content instead of courses.
"""

from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class FaqChunk(Base):
    __tablename__ = "faq_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_url: Mapped[str] = mapped_column(String, index=True)  # page it came from
    title: Mapped[str] = mapped_column(String)
    chunk_index: Mapped[int] = mapped_column(Integer)  # position within the source page
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))  # matches embedding_service dim