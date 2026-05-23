"""InferenceLog SQLAlchemy model — stores per-request LLM telemetry."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class InferenceLog(Base):
    """One row per LLM API call.

    Captures timing, token counts, status, and short previews of the
    request/response so operators can debug and monitor without storing
    full prompts (which may contain PII).
    """

    __tablename__ = "inference_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Provider / model info
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)

    # Performance metrics
    latency_ms = Column(Float, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Request outcome
    status = Column(String(32), nullable=False, default="success", index=True)
    error_message = Column(Text, nullable=True)

    # Short previews (truncated, PII-redacted)
    input_preview = Column(String(500), nullable=True)
    output_preview = Column(String(500), nullable=True)

    # Flexible metadata bag for provider-specific fields
    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    conversation = relationship("Conversation", back_populates="inference_logs")
