import React from "react";

/**
 * Left sidebar: new-conversation button, conversation list, and view tabs.
 */
export default function Sidebar({
  conversations,
  activeId,
  view,
  onSelect,
  onCreate,
  onCancel,
  onResume,
  onDelete,
  onViewChange,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>🔍 Inference Logger</h1>
        <button className="btn btn-primary" onClick={onCreate}>
          + New Conversation
        </button>
      </div>

      <div className="conv-list">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conv-item ${c.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <div className="conv-item-info">
              <div className="conv-item-title">{c.title}</div>
              <div className="conv-item-meta">
                <span className={`status-badge status-${c.status}`}>
                  {c.status}
                </span>{" "}
                · {c.provider}/{c.model}
              </div>
            </div>
            <div className="conv-item-actions">
              {c.status === "active" ? (
                <button
                  className="btn btn-sm btn-danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCancel(c.id);
                  }}
                  title="Cancel"
                >
                  ✕
                </button>
              ) : c.status === "cancelled" ? (
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onResume(c.id);
                  }}
                  title="Resume"
                >
                  ↻
                </button>
              ) : null}
              <button
                className="btn btn-sm btn-danger"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
                title="Delete"
              >
                🗑
              </button>
            </div>
          </div>
        ))}

        {conversations.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
            No conversations yet.
            <br />
            Click "New Conversation" to start.
          </div>
        )}
      </div>

      <div className="sidebar-tabs">
        <button
          className={`sidebar-tab ${view === "chat" ? "active" : ""}`}
          onClick={() => onViewChange("chat")}
        >
          💬 Chat
        </button>
        <button
          className={`sidebar-tab ${view === "dashboard" ? "active" : ""}`}
          onClick={() => onViewChange("dashboard")}
        >
          📊 Dashboard
        </button>
      </div>
    </aside>
  );
}
