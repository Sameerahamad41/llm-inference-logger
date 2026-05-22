"""REST endpoints for conversation management.

Supports: list, get, create, cancel, resume, and delete conversations.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """Return all conversations ordered by most recently updated."""
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start a new conversation."""
    from app.core.config import settings

    conv = Conversation(
        title=body.title,
        provider=body.provider or settings.DEFAULT_PROVIDER,
        model=body.model or settings.DEFAULT_MODEL,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return a conversation with its full message history."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/{conversation_id}/cancel", response_model=ConversationOut)
async def cancel_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark a conversation as cancelled so no further messages are accepted."""
    result = await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(status="cancelled")
        .returning(Conversation)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/{conversation_id}/resume", response_model=ConversationOut)
async def resume_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Re-activate a cancelled conversation."""
    result = await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(status="active")
        .returning(Conversation)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a conversation and its messages."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
