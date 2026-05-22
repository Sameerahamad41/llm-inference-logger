/**
 * Thin HTTP client for the backend API.
 * All methods return parsed JSON or throw on non-2xx responses.
 */

const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Providers ────────────────────────────────────────────────────
export const getProviders = () => request("/providers");

// ── Conversations ────────────────────────────────────────────────
export const listConversations = () => request("/conversations");

export const createConversation = (data = {}) =>
  request("/conversations", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const getConversation = (id) => request(`/conversations/${id}`);

export const cancelConversation = (id) =>
  request(`/conversations/${id}/cancel`, { method: "POST" });

export const resumeConversation = (id) =>
  request(`/conversations/${id}/resume`, { method: "POST" });

export const deleteConversation = (id) =>
  request(`/conversations/${id}`, { method: "DELETE" });

// ── Chat ─────────────────────────────────────────────────────────
export const sendMessage = (conversationId, message, provider, model) =>
  request(`/chat/${conversationId}`, {
    method: "POST",
    body: JSON.stringify({ message, provider, model }),
  });

/**
 * Stream chat response as Server-Sent Events.
 * Calls `onChunk(text)` for each content chunk, `onDone(messageId)` when complete.
 */
export async function streamMessage(
  conversationId,
  message,
  provider,
  model,
  { onChunk, onDone, onError }
) {
  const res = await fetch(`${BASE}/chat/${conversationId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, provider, model }),
  });

  if (!res.ok) {
    const body = await res.text();
    onError?.(new Error(`${res.status}: ${body}`));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.chunk) onChunk?.(data.chunk);
        if (data.done) onDone?.(data.message_id);
      } catch {
        // skip malformed lines
      }
    }
  }
}

// ── Dashboard ────────────────────────────────────────────────────
export const getDashboardStats = (hours = 24) =>
  request(`/dashboard/stats?hours=${hours}`);

export const getDashboardLogs = (limit = 50) =>
  request(`/dashboard/logs?limit=${limit}`);
