# app/models/chat_message.py
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatMessage(Base):
    """
    A single turn in a chat conversation — either the user's message or
    the assistant's reply. Both roles live in the same table (rather than
    separate user_messages/assistant_messages tables) since they share the
    same shape and always need to be read back together, in order, to
    reconstruct a conversation.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True
    )

    # Matches the Anthropic API's role values directly — no translation
    # needed when building the messages list for a Claude call.
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage role={self.role!r} conversation_id={self.conversation_id}>"