"""External ingestion endpoint.

Accepts inference log payloads from the SDK (or any external client),
validates them, and persists to the database. This is the HTTP
counterpart to the in-process event-driven ingestion.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.inference_log import InferenceLog
from app.schemas.conversation import InferenceLogCreate, InferenceLogOut
from app.services.pii_redactor import redact

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=InferenceLogOut, status_code=201)
async def ingest_log(
    body: InferenceLogCreate,
    db: AsyncSession = Depends(get_db),
):
    """Receive, validate, redact, and store a single inference log."""
    log = InferenceLog(
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        provider=body.provider,
        model=body.model,
        latency_ms=body.latency_ms,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        total_tokens=body.total_tokens,
        status=body.status,
        error_message=body.error_message,
        input_preview=redact(body.input_preview),
        output_preview=redact(body.output_preview),
        metadata_=body.metadata,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)
    return log


@router.post("/batch", response_model=list[InferenceLogOut], status_code=201)
async def ingest_batch(
    logs: list[InferenceLogCreate],
    db: AsyncSession = Depends(get_db),
):
    """Receive a batch of inference logs in one request."""
    if len(logs) > 200:
        raise HTTPException(
            status_code=400,
            detail="Batch size must not exceed 200.",
        )

    results = []
    for body in logs:
        log = InferenceLog(
            conversation_id=body.conversation_id,
            message_id=body.message_id,
            provider=body.provider,
            model=body.model,
            latency_ms=body.latency_ms,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            total_tokens=body.total_tokens,
            status=body.status,
            error_message=body.error_message,
            input_preview=redact(body.input_preview),
            output_preview=redact(body.output_preview),
            metadata_=body.metadata,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
        results.append(log)
    return results
