"""Chat endpoint — sends user messages through the SDK and streams responses."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.conversation import ChatRequest, ChatResponse, MessageOut
from app.sdk.llm_client import LLMClient

router = APIRouter(prefix="/chat", tags=["chat"])

# Maximum number of recent messages sent as context to the LLM
CONTEXT_WINDOW = 20


@router.post("/{conversation_id}", response_model=ChatResponse)
async def chat(
    conversation_id: UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a non-streaming response."""
    conv = await _get_active_conversation(conversation_id, db)

    # Persist user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.flush()

    # Build context for the LLM
    context = _build_context(conv.messages, body.message)

    # Call LLM via SDK (which logs automatically)
    provider = body.provider or conv.provider
    model = body.model or conv.model
    client = LLMClient(provider=provider, model=model)
    result = await client.chat(
        context,
        conversation_id=conv.id,
        message_id=user_msg.id,
    )

    # Persist assistant message
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=result["content"],
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    # Auto-title on first exchange
    if len(conv.messages) <= 1:
        conv.title = body.message[:80]

    return ChatResponse(
        conversation_id=conv.id,
        message=MessageOut.model_validate(assistant_msg),
    )


@router.post("/{conversation_id}/stream")
async def chat_stream(
    conversation_id: UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and stream the response as Server-Sent Events."""
    conv = await _get_active_conversation(conversation_id, db)

    # Persist user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)

    context = _build_context(conv.messages, body.message)
    provider = body.provider or conv.provider
    model = body.model or conv.model
    client = LLMClient(provider=provider, model=model)

    async def event_generator():
        full_content = ""
        async for chunk in client.chat_stream(
            context,
            conversation_id=conv.id,
            message_id=user_msg.id,
        ):
            full_content += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        # Persist the full assistant message after streaming completes
        async with db.begin_nested():
            assistant_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=full_content,
            )
            db.add(assistant_msg)
            await db.flush()
            await db.refresh(assistant_msg)

            # Auto-title on first exchange
            result = await db.execute(
                select(Message).where(Message.conversation_id == conv.id)
            )
            msg_count = len(result.scalars().all())
            if msg_count <= 2:
                conv.title = body.message[:80]
                db.add(conv)

        yield f"data: {json.dumps({'done': True, 'message_id': str(assistant_msg.id)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helpers ───────────────────────────────────────────────────────────

async def _get_active_conversation(
    conversation_id: UUID,
    db: AsyncSession,
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == str(conversation_id))
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Conversation is cancelled. Resume it first.",
        )
    return conv


def _build_context(
    existing_messages: list[Message],
    new_message: str,
) -> list[dict[str, str]]:
    """Build the message list sent to the LLM.

    Includes a system prompt, the last CONTEXT_WINDOW messages, and
    the new user message.
    """
    context: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are a helpful, concise assistant. "
                "Answer the user's questions clearly."
            ),
        }
    ]
    recent = existing_messages[-CONTEXT_WINDOW:]
    for msg in recent:
        context.append({"role": msg.role, "content": msg.content})
    context.append({"role": "user", "content": new_message})
    return context
