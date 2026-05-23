"""Pydantic schemas for conversation and message endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Messages ─────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Conversations ────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    provider: str = ""
    model: str = ""


class ConversationOut(BaseModel):
    id: UUID
    title: str
    status: str
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


# ── Chat ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    provider: str | None = None
    model: str | None = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: MessageOut
    inference: "InferenceLogOut | None" = None


# ── Inference Logs ───────────────────────────────────────────────────

class InferenceLogOut(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID | None
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    status: str
    error_message: str | None
    input_preview: str | None
    output_preview: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InferenceLogCreate(BaseModel):
    """Payload the SDK sends to the ingestion endpoint."""
    conversation_id: UUID
    message_id: UUID | None = None
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    status: str = "success"
    error_message: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    metadata: dict | None = None


# ── Dashboard ────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_requests: int
    success_count: int
    error_count: int
    avg_latency_ms: float
    p95_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    requests_per_provider: dict[str, int]
    requests_per_model: dict[str, int]
    errors_per_provider: dict[str, int]
    latency_over_time: list[dict]
    throughput_over_time: list[dict]
