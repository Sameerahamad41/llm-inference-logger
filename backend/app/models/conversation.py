"""Conversation and Message SQLAlchemy models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Conversation(Base):
    """A multi-turn chat conversation."""

    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(256), nullable=False, default="New Conversation")
    status = Column(
        SAEnum("active", "cancelled", "completed", name="conversation_status"),
        nullable=False,
        default="active",
    )
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )
    inference_logs = relationship(
        "InferenceLog",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """A single message within a conversation."""

    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        SAEnum("system", "user", "assistant", name="message_role"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    conversation = relationship("Conversation", back_populates="messages")
