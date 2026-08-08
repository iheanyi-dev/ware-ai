# app/models/chat_conversation.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatConversation(Base):
    """
    A single chat session between a user and the chatbot. Groups messages
    together so history can be loaded/continued across multiple requests
    instead of the caller resending the full transcript every time.
    """

    __tablename__ = "chat_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Nullable: the chatbot should work for anonymous/pre-login visitors
    # too (e.g. someone asking "how does this site work" before signing
    # up), not just enrolled users.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Running summary of older turns in this conversation, kept up to date
    # by chat_summarization_service.py. Null until the conversation grows
    # past the summarization threshold for the first time.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp of the newest message already folded into `summary`.
    # Messages created AFTER this point are not yet summarized and must
    # either be sent verbatim (if recent) or included in the next
    # summarization pass — this is what lets us summarize incrementally
    # instead of re-summarizing the whole conversation every time.
    summary_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation", order_by="ChatMessage.created_at"
    )

    def __repr__(self) -> str:
        return f"<ChatConversation id={self.id} user_id={self.user_id}>"