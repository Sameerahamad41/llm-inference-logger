# LLM Inference Logger

A lightweight inference logging and ingestion system for LLM applications. Captures per-request telemetry (latency, tokens, errors) through an event-driven SDK and surfaces it in a real-time analytics dashboard.

![Architecture](docs/architecture.png)

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Sameerahamad41/llm-inference-logger.git
cd llm-inference-logger

# 2. Configure API keys (at least one required)
cp backend/.env.example backend/.env
# Edit backend/.env and add your API keys

# 3. Launch everything
docker compose up --build
```

| Service   | URL                        |
|-----------|----------------------------|
| Frontend  | http://localhost:3000       |
| Backend   | http://localhost:8000       |
| API Docs  | http://localhost:8000/docs  |
| Postgres  | localhost:5432              |

---

## Architecture Overview

```
┌─────────────┐    ┌──────────────────────────────────────────────────┐
│   React UI  │───▶│  FastAPI Backend                                 │
│  (port 3000)│    │                                                  │
└─────────────┘    │  ┌─────────────┐   ┌──────────────────────────┐ │
                   │  │ Chat API    │──▶│ LLM SDK (Wrapper)        │ │
                   │  │ /api/chat/* │   │                          │ │
                   │  └─────────────┘   │ • Measures latency       │ │
                   │                    │ • Extracts token usage   │ │
                   │  ┌─────────────┐   │ • Redacts PII            │ │
                   │  │ Ingestion   │   │ • Publishes events       │ │
                   │  │ /api/ingest │   └────────────┬─────────────┘ │
                   │  └──────┬──────┘                │               │
                   │         │          ┌────────────▼─────────────┐ │
                   │         └─────────▶│ Event Bus                │ │
                   │                    │ "inference_completed"    │ │
                   │  ┌─────────────┐   └────────────┬─────────────┘ │
                   │  │ Dashboard   │                │               │
                   │  │ /api/dash/* │   ┌────────────▼─────────────┐ │
                   │  └─────────────┘   │ Ingestion Handler        │ │
                   │                    │ Validates → Persists     │ │
                   └────────────────────└────────────┬─────────────┘─┘
                                                     │
                                        ┌────────────▼─────────────┐
                                        │    PostgreSQL             │
                                        │  conversations            │
                                        │  messages                 │
                                        │  inference_logs           │
                                        └───────────────────────────┘
```

### Component Breakdown

| Component | Purpose | Tech |
|-----------|---------|------|
| **React Frontend** | Chat UI, conversation management, analytics dashboard | React 18, Recharts, Vite |
| **FastAPI Backend** | REST API, SSE streaming, CORS, routing | FastAPI, Uvicorn |
| **LLM SDK** | Wraps provider calls, measures latency, extracts tokens, publishes telemetry events | Python async |
| **Event Bus** | In-process pub/sub to decouple chat flow from logging | asyncio tasks |
| **Ingestion Pipeline** | Validates payloads, redacts PII, persists to DB | Event subscriber + HTTP endpoint |
| **Dashboard** | Aggregated analytics: latency, throughput, errors | SQL aggregates, Recharts |
| **PostgreSQL** | Persistent storage for conversations, messages, and inference logs | PostgreSQL 16, SQLAlchemy async |

---

## Features

### Core
- **Multi-turn conversations** with short conversational context (last 20 messages)
- **Multi-provider support**: OpenAI, Anthropic, Google (Gemini)
- **Streaming responses** via Server-Sent Events
- **Inference metadata capture**: model, provider, latency, tokens, status, errors
- **PII redaction** on log previews (emails, phones, SSNs, credit cards, IPs)

### Frontend
- **List conversations** with status badges (active/cancelled)
- **Cancel** a conversation (blocks further messages)
- **Resume** a cancelled conversation
- **Delete** conversations
- **Provider/model selector** per message
- **Real-time streaming** with typing indicator
- **Analytics dashboard** with charts and log table

### Dashboard Metrics
- Total requests, success/error counts, error rate
- Average and P95 latency
- Token usage (input/output)
- Requests by provider and model
- Errors by provider
- Latency over time (line chart)
- Throughput over time (bar chart)
- Recent inference logs table

### Bonus Features
- **Event-driven architecture** — chat endpoint never blocks on log writes
- **PII redaction** — regex-based redaction before persistence
- **Docker Compose** — one-command setup
- **External ingestion API** — `/api/ingest` accepts logs from any client
- **Batch ingestion** — `/api/ingest/batch` for bulk log submission

---

## Schema Design

### `conversations`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| title | VARCHAR(256) | Auto-set from first message |
| status | ENUM(active, cancelled, completed) | Controls message acceptance |
| provider | VARCHAR(64) | Default provider for this conversation |
| model | VARCHAR(128) | Default model for this conversation |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated |

### `messages`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| conversation_id | UUID | FK → conversations (CASCADE) |
| role | ENUM(system, user, assistant) | |
| content | TEXT | Full message text |
| created_at | TIMESTAMPTZ | |

### `inference_logs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| conversation_id | UUID | FK → conversations (CASCADE) |
| message_id | UUID | FK → messages (SET NULL) |
| provider | VARCHAR(64) | Indexed for dashboard queries |
| model | VARCHAR(128) | Indexed |
| latency_ms | FLOAT | Wall-clock time for the LLM call |
| input_tokens | INTEGER | Nullable (not all providers report) |
| output_tokens | INTEGER | |
| total_tokens | INTEGER | |
| status | VARCHAR(32) | "success" or "error", indexed |
| error_message | TEXT | Null on success |
| input_preview | VARCHAR(500) | Truncated + PII-redacted |
| output_preview | VARCHAR(500) | Truncated + PII-redacted |
| metadata | JSONB | Provider-specific fields |
| created_at | TIMESTAMPTZ | Indexed for time-range queries |

### Design Decisions

1. **UUIDs for primary keys**: Avoids sequential ID leakage, safe for distributed systems.
2. **Separate inference_logs table**: Decouples telemetry from chat data. Logs can be archived or sampled independently.
3. **JSONB metadata column**: Captures provider-specific fields without schema migration for each provider.
4. **Truncated previews**: Stores only 500 chars of input/output to limit storage while enabling debugging. Full content lives in `messages`.
5. **CASCADE deletes**: Deleting a conversation removes its messages and logs. Simple ownership model.
6. **Indexed columns**: provider, model, status, created_at on inference_logs for fast dashboard queries.

---

## Architecture Notes

### Ingestion Flow

1. User sends a message via `/api/chat/{id}` or `/api/chat/{id}/stream`.
2. The `LLMClient` SDK wraps the provider call:
   - Records `start_time` before the call.
   - Extracts `token_usage` from the provider response.
   - Computes `latency_ms = (end - start) * 1000`.
   - Truncates input/output to 500 chars.
   - Applies PII redaction to previews.
   - Publishes an `"inference_completed"` event with the payload.
3. The event bus dispatches to the ingestion handler asynchronously.
4. The handler validates required fields and inserts a row into `inference_logs`.
5. The chat endpoint returns the assistant response without waiting for log persistence.

External clients can also POST directly to `/api/ingest` (single) or `/api/ingest/batch` (up to 200 logs).

### Logging Strategy

- **In-process event bus** for low-latency, zero-infrastructure logging.
- **Async handlers** ensure log failures never break chat responses.
- **Structured logging** via Python's `logging` module with timestamps and levels.
- **PII redaction** applied before persistence, not after — data at rest is already clean.

### Scaling Considerations

| Concern | Current | At Scale |
|---------|---------|----------|
| Event bus | In-process asyncio | Replace with Kafka/Redis Streams for multi-worker |
| Database writes | Single INSERT per event | Batch inserts with configurable flush interval |
| Dashboard queries | Direct SQL aggregates | Pre-computed materialized views or TimescaleDB |
| Streaming | SSE per connection | Consider WebSockets for bidirectional control |
| Frontend | Polling (15s interval) | WebSocket push for real-time dashboard |
| Multi-instance | Single process | Shared message queue + connection pooler (PgBouncer) |

### Failure Handling

- **LLM call failure**: Caught by the SDK, logged with `status="error"` and `error_message`. Chat endpoint returns a 500 but the log is still persisted.
- **Ingestion failure**: `_safe_call` wrapper catches all exceptions in event handlers and logs them. The chat response is unaffected.
- **Database down**: Log writes fail silently (logged to stderr). Chat works if the conversation is cached, but new conversations can't be created.
- **Invalid log payload**: Validated at ingestion time; missing required fields cause the log to be dropped with a warning.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/providers` | List available LLM providers |
| GET | `/api/conversations` | List all conversations |
| POST | `/api/conversations` | Create a new conversation |
| GET | `/api/conversations/{id}` | Get conversation with messages |
| POST | `/api/conversations/{id}/cancel` | Cancel a conversation |
| POST | `/api/conversations/{id}/resume` | Resume a cancelled conversation |
| DELETE | `/api/conversations/{id}` | Delete a conversation |
| POST | `/api/chat/{id}` | Send message (non-streaming) |
| POST | `/api/chat/{id}/stream` | Send message (SSE streaming) |
| POST | `/api/ingest` | Submit a single inference log |
| POST | `/api/ingest/batch` | Submit up to 200 logs at once |
| GET | `/api/dashboard/stats` | Aggregated metrics |
| GET | `/api/dashboard/logs` | Recent inference logs |

Full interactive docs at `http://localhost:8000/docs` (Swagger UI).

---

## Project Structure

```
llm-inference-logger/
├── backend/
│   ├── app/
│   │   ├── api/               # Route handlers
│   │   │   ├── chat.py        # Chat endpoints (streaming + non-streaming)
│   │   │   ├── conversations.py # CRUD + cancel/resume
│   │   │   ├── dashboard.py   # Analytics aggregation
│   │   │   └── ingestion.py   # External log ingestion endpoint
│   │   ├── core/
│   │   │   ├── config.py      # Environment-based settings
│   │   │   ├── database.py    # Async SQLAlchemy setup
│   │   │   └── events.py      # In-process pub/sub event bus
│   │   ├── models/
│   │   │   ├── conversation.py # Conversation + Message ORM models
│   │   │   └── inference_log.py # InferenceLog ORM model
│   │   ├── schemas/
│   │   │   └── conversation.py # Pydantic request/response schemas
│   │   ├── sdk/
│   │   │   └── llm_client.py  # Multi-provider LLM wrapper with telemetry
│   │   ├── services/
│   │   │   ├── ingestion.py   # Event handler for log persistence
│   │   │   └── pii_redactor.py # Regex-based PII redaction
│   │   └── main.py            # FastAPI app entry point
│   ├── migrations/            # Alembic migration config
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.jsx    # Conversation list + navigation
│   │   │   ├── ChatView.jsx   # Chat interface with streaming
│   │   │   └── Dashboard.jsx  # Analytics charts + log table
│   │   ├── utils/
│   │   │   └── api.js         # HTTP client
│   │   ├── App.jsx            # Root component
│   │   ├── main.jsx           # Entry point
│   │   └── index.css          # Global styles (dark theme)
│   ├── Dockerfile             # Dev mode
│   ├── Dockerfile.prod        # Production (nginx)
│   └── nginx.conf
├── docker-compose.yml         # One-command setup
└── README.md
```

---

## What I Would Improve With More Time

1. **Message queue** (Kafka/Redis Streams) instead of in-process event bus for multi-worker deployments.
2. **Materialized views** for dashboard aggregations to avoid repeated full-table scans.
3. **WebSocket** connections for real-time dashboard updates instead of polling.
4. **Rate limiting** and authentication on the ingestion endpoint.
5. **Conversation search** and filtering in the UI.
6. **Message editing/regeneration** support.
7. **Cost tracking** per provider based on token pricing.
8. **Alerting** on error rate thresholds or latency spikes.
9. **Kubernetes manifests** with HPA for auto-scaling.
10. **Integration tests** with mocked LLM providers.
11. **OpenTelemetry** integration for distributed tracing.
12. **Multi-tenant** support with org/user scoping on conversations and logs.

---

## License

MIT
