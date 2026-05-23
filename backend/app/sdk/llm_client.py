"""Lightweight SDK that wraps LLM provider calls and captures telemetry.

Usage:
    client = LLMClient(provider="groq", model="llama-3.3-70b-versatile")
    response = await client.chat(messages, conversation_id=conv_id)

The SDK automatically:
  1. Measures wall-clock latency.
  2. Extracts token usage from the provider response.
  3. Publishes an "inference_completed" event with the full log payload
     so the ingestion pipeline can persist it asynchronously.
"""

import time
import uuid
from typing import AsyncIterator

import anthropic
import google.generativeai as genai
import openai
from groq import AsyncGroq

from app.core.config import settings
from app.core.events import publish
from app.services.pii_redactor import redact


class LLMClient:
    """Unified interface for multiple LLM providers."""

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider or settings.DEFAULT_PROVIDER
        self.model = model or settings.DEFAULT_MODEL

    # ── Non-streaming chat ────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, str]],
        conversation_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> dict:
        """Send messages to the provider and return the assistant reply.

        Returns a dict with keys: content, input_tokens, output_tokens,
        total_tokens, latency_ms, status, error_message.
        """
        start = time.perf_counter()
        result = {
            "content": "",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "latency_ms": 0.0,
            "status": "success",
            "error_message": None,
        }

        try:
            if self.provider == "openai":
                result = await self._call_openai(messages, result)
            elif self.provider == "anthropic":
                result = await self._call_anthropic(messages, result)
            elif self.provider == "google":
                result = await self._call_google(messages, result)
            elif self.provider == "groq":
                result = await self._call_groq(messages, result)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as exc:
            result["status"] = "error"
            result["error_message"] = str(exc)

        result["latency_ms"] = (time.perf_counter() - start) * 1000

        # Fire event so the ingestion pipeline stores the log
        await self._emit_log(messages, result, conversation_id, message_id)
        return result

    # ── Streaming chat ────────────────────────────────────────────

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        conversation_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> AsyncIterator[str]:
        """Yield content chunks from the provider, then log the full call."""
        start = time.perf_counter()
        full_content = ""
        result = {
            "content": "",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "latency_ms": 0.0,
            "status": "success",
            "error_message": None,
        }

        try:
            if self.provider == "openai":
                async for chunk in self._stream_openai(messages):
                    full_content += chunk
                    yield chunk
            elif self.provider == "anthropic":
                async for chunk in self._stream_anthropic(messages):
                    full_content += chunk
                    yield chunk
            elif self.provider == "google":
                async for chunk in self._stream_google(messages):
                    full_content += chunk
                    yield chunk
            elif self.provider == "groq":
                async for chunk in self._stream_groq(messages):
                    full_content += chunk
                    yield chunk
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            result["content"] = full_content
        except Exception as exc:
            result["status"] = "error"
            result["error_message"] = str(exc)

        result["latency_ms"] = (time.perf_counter() - start) * 1000
        await self._emit_log(messages, result, conversation_id, message_id)

    # ── Provider implementations ──────────────────────────────────

    async def _call_openai(self, messages: list[dict], result: dict) -> dict:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        choice = response.choices[0]
        result["content"] = choice.message.content or ""
        if response.usage:
            result["input_tokens"] = response.usage.prompt_tokens
            result["output_tokens"] = response.usage.completion_tokens
            result["total_tokens"] = response.usage.total_tokens
        return result

    async def _call_anthropic(self, messages: list[dict], result: dict) -> dict:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        # Anthropic requires a separate system param
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_messages.append(m)

        response = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_msg or "You are a helpful assistant.",
            messages=chat_messages,
        )
        result["content"] = response.content[0].text
        result["input_tokens"] = response.usage.input_tokens
        result["output_tokens"] = response.usage.output_tokens
        result["total_tokens"] = (
            response.usage.input_tokens + response.usage.output_tokens
        )
        return result

    async def _call_google(self, messages: list[dict], result: dict) -> dict:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(self.model)
        # Convert to Gemini format
        history = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            history.append({"role": role, "parts": [m["content"]]})

        last_msg = history.pop()
        chat = model.start_chat(history=history)
        response = chat.send_message(last_msg["parts"][0])
        result["content"] = response.text
        if response.usage_metadata:
            result["input_tokens"] = response.usage_metadata.prompt_token_count
            result["output_tokens"] = response.usage_metadata.candidates_token_count
            result["total_tokens"] = response.usage_metadata.total_token_count
        return result

    async def _call_groq(self, messages: list[dict], result: dict) -> dict:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        choice = response.choices[0]
        result["content"] = choice.message.content or ""
        if response.usage:
            result["input_tokens"] = response.usage.prompt_tokens
            result["output_tokens"] = response.usage.completion_tokens
            result["total_tokens"] = response.usage.total_tokens
        return result

    # ── Streaming implementations ─────────────────────────────────

    async def _stream_openai(self, messages: list[dict]) -> AsyncIterator[str]:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def _stream_anthropic(self, messages: list[dict]) -> AsyncIterator[str]:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_messages.append(m)

        async with client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system_msg or "You are a helpful assistant.",
            messages=chat_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_google(self, messages: list[dict]) -> AsyncIterator[str]:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(self.model)
        history = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            history.append({"role": role, "parts": [m["content"]]})

        last_msg = history.pop()
        chat = model.start_chat(history=history)
        response = chat.send_message(last_msg["parts"][0], stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_groq(self, messages: list[dict]) -> AsyncIterator[str]:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    # ── Telemetry emission ────────────────────────────────────────

    async def _emit_log(
        self,
        messages: list[dict],
        result: dict,
        conversation_id: uuid.UUID | None,
        message_id: uuid.UUID | None,
    ) -> None:
        """Build and publish an inference log event."""
        input_text = messages[-1]["content"] if messages else ""
        payload = {
            "conversation_id": str(conversation_id) if conversation_id else None,
            "message_id": str(message_id) if message_id else None,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": result["latency_ms"],
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "total_tokens": result.get("total_tokens"),
            "status": result["status"],
            "error_message": result.get("error_message"),
            "input_preview": redact(input_text[:500]),
            "output_preview": redact((result.get("content") or "")[:500]),
        }
        await publish("inference_completed", payload)
