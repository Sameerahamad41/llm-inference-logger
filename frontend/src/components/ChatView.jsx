import React, { useState, useEffect, useRef } from "react";
import { streamMessage } from "../utils/api";

/**
 * Main chat panel: message history + input box with streaming support.
 */
export default function ChatView({
  conversation,
  messages,
  providers,
  onMessageSent,
}) {
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText]);

  // Reset provider/model selectors when conversation changes
  useEffect(() => {
    if (conversation) {
      setProvider(conversation.provider);
      setModel(conversation.model);
    }
  }, [conversation?.id]);

  if (!conversation) {
    return (
      <div className="main-content">
        <div className="empty-state">
          Select or create a conversation to start chatting
        </div>
      </div>
    );
  }

  const isCancelled = conversation.status === "cancelled";

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming || isCancelled) return;

    setInput("");
    setStreaming(true);
    setStreamText("");

    // Optimistically show the user message
    onMessageSent({ role: "user", content: text, id: "temp-user" });

    try {
      await streamMessage(conversation.id, text, provider, model, {
        onChunk: (chunk) => setStreamText((prev) => prev + chunk),
        onDone: (messageId) => {
          setStreaming(false);
          // Trigger a full refresh of messages
          onMessageSent(null);
        },
        onError: (err) => {
          console.error("Stream error:", err);
          setStreaming(false);
          setStreamText(`Error: ${err.message}`);
        },
      });
    } catch (err) {
      console.error("Send error:", err);
      setStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Available models for the currently selected provider
  const providerObj = providers.find((p) => p.id === provider);
  const availableModels = providerObj?.models || [];

  return (
    <div className="main-content">
      <div className="chat-header">
        <h2>{conversation.title}</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className={`status-badge status-${conversation.status}`}>
            {conversation.status}
          </span>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div className="message" key={msg.id || i}>
            <div className={`message-avatar ${msg.role}`}>
              {msg.role === "user" ? "U" : "A"}
            </div>
            <div className="message-content">
              <div className="message-role">{msg.role}</div>
              <div className="message-text">{msg.content}</div>
            </div>
          </div>
        ))}

        {streaming && streamText && (
          <div className="message">
            <div className="message-avatar assistant">A</div>
            <div className="message-content">
              <div className="message-role">assistant</div>
              <div className="message-text">
                {streamText}
                <span className="spinner" style={{ marginLeft: 8 }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        {providers.length > 0 && (
          <div className="provider-selector">
            <select value={provider} onChange={(e) => {
              setProvider(e.target.value);
              const p = providers.find((p) => p.id === e.target.value);
              if (p?.models?.length) setModel(p.models[0]);
            }}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {availableModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        )}
        <div className="chat-input-wrapper">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isCancelled
                ? "Conversation is cancelled. Resume to continue."
                : "Type a message… (Enter to send, Shift+Enter for newline)"
            }
            disabled={streaming || isCancelled}
            rows={1}
          />
          <button
            className="btn btn-primary"
            onClick={handleSend}
            disabled={streaming || isCancelled || !input.trim()}
          >
            {streaming ? <span className="spinner" /> : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
