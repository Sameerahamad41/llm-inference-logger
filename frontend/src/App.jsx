import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatView from "./components/ChatView";
import Dashboard from "./components/Dashboard";
import {
  listConversations,
  createConversation,
  getConversation,
  cancelConversation,
  resumeConversation,
  deleteConversation,
  getProviders,
} from "./utils/api";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [providers, setProviders] = useState([]);
  const [view, setView] = useState("chat");

  // ── Fetch conversation list ───────────────────────────────────
  const refreshList = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(data);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  }, []);

  // ── Fetch providers ───────────────────────────────────────────
  useEffect(() => {
    getProviders()
      .then((data) => setProviders(data.providers || []))
      .catch(console.error);
    refreshList();
  }, []);

  // ── Load active conversation ──────────────────────────────────
  const loadConversation = useCallback(async (id) => {
    if (!id) return;
    try {
      const data = await getConversation(id);
      setActiveConv(data);
      setMessages(data.messages || []);
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  }, []);

  useEffect(() => {
    if (activeId) loadConversation(activeId);
  }, [activeId]);

  // ── Handlers ──────────────────────────────────────────────────
  const handleCreate = async () => {
    try {
      const conv = await createConversation();
      await refreshList();
      setActiveId(conv.id);
      setView("chat");
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  };

  const handleCancel = async (id) => {
    try {
      await cancelConversation(id);
      await refreshList();
      if (id === activeId) loadConversation(id);
    } catch (err) {
      console.error("Failed to cancel:", err);
    }
  };

  const handleResume = async (id) => {
    try {
      await resumeConversation(id);
      await refreshList();
      if (id === activeId) loadConversation(id);
    } catch (err) {
      console.error("Failed to resume:", err);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteConversation(id);
      if (id === activeId) {
        setActiveId(null);
        setActiveConv(null);
        setMessages([]);
      }
      await refreshList();
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  };

  const handleMessageSent = (tempMsg) => {
    if (tempMsg) {
      // Optimistic update: append user message immediately
      setMessages((prev) => [...prev, tempMsg]);
    } else {
      // Full refresh after streaming completes
      loadConversation(activeId);
      refreshList();
    }
  };

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className="app-layout">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        view={view}
        onSelect={(id) => {
          setActiveId(id);
          setView("chat");
        }}
        onCreate={handleCreate}
        onCancel={handleCancel}
        onResume={handleResume}
        onDelete={handleDelete}
        onViewChange={setView}
      />

      {view === "chat" ? (
        <ChatView
          conversation={activeConv}
          messages={messages}
          providers={providers}
          onMessageSent={handleMessageSent}
        />
      ) : (
        <Dashboard />
      )}
    </div>
  );
}
