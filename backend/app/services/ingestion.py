"""Ingestion pipeline — receives inference log events and persists them.

Subscribes to the "inference_completed" event published by the SDK.
Validates the payload, enriches it, and writes to PostgreSQL.

In a production system this would batch writes or use a message queue
(e.g. Kafka). Here we write synchronously per event for simplicity,
but the event-driven design means the chat endpoint never blocks on
database writes for logs.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert

from app.core.database import async_session_factory
from app.core.events import subscribe
from app.models.inference_log import InferenceLog

logger = logging.getLogger(__name__)


async def handle_inference_completed(payload: dict) -> None:
    """Validate and persist a single inference log row."""
    required_fields = {"provider", "model", "latency_ms", "status"}
    missing = required_fields - set(payload.keys())
    if missing:
        logger.warning("Dropping log — missing fields: %s", missing)
        return

    row = {
        "id": uuid.uuid4(),
        "conversation_id": (
            uuid.UUID(payload["conversation_id"])
            if payload.get("conversation_id")
            else None
        ),
        "message_id": (
            uuid.UUID(payload["message_id"])
            if payload.get("message_id")
            else None
        ),
        "provider": payload["provider"],
        "model": payload["model"],
        "latency_ms": payload["latency_ms"],
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "total_tokens": payload.get("total_tokens"),
        "status": payload["status"],
        "error_message": payload.get("error_message"),
        "input_preview": payload.get("input_preview"),
        "output_preview": payload.get("output_preview"),
        "metadata": payload.get("metadata"),
        "created_at": datetime.now(timezone.utc),
    }

    async with async_session_factory() as session:
        await session.execute(insert(InferenceLog).values(**row))
        await session.commit()

    logger.info(
        "Ingested log id=%s provider=%s model=%s latency=%.1fms status=%s",
        row["id"],
        row["provider"],
        row["model"],
        row["latency_ms"],
        row["status"],
    )


def register_ingestion_handlers() -> None:
    """Wire up event subscribers. Called once at app startup."""
    subscribe("inference_completed", handle_inference_completed)
