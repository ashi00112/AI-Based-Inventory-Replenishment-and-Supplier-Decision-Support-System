"""
SQLAlchemy models for SmartSupply AI Assistant chat conversations and messages.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ChatConversation(Base):
    """
    Represents an authenticated conversation session between a user and SmartSupply AI Assistant.
    Strictly isolated per-user; deleting a conversation cascades to all its messages.
    """
    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )
    user: Mapped["User"] = relationship("User", backref="chat_conversations")

    def __repr__(self) -> str:
        return f"<ChatConversation id={self.id} user_id={self.user_id} title='{self.title[:30]}'>"


class ChatMessage(Base):
    """
    Represents a single message turn in a chat conversation (either 'user' or 'assistant').
    Includes structured JSON metadata for context memory, agent provenance, citations, and intent.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    conversation: Mapped["ChatConversation"] = relationship(
        "ChatConversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} conv_id={self.conversation_id} role='{self.role}'>"
