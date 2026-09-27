"use client";
import { useCallback, useEffect, useState } from "react";
import {
  apiBaseUrl,
  websocketBaseUrl,
  type ChangeDraft,
  type ChatMessage,
  type OrderSummary,
  type OrderVersion,
  type ProcessingRun,
} from "@/lib/procurement";

export function useOrderWorkspace() {
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [versions, setVersions] = useState<OrderVersion[]>([]);
  const [processing, setProcessing] = useState<ProcessingRun[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [drafts, setDrafts] = useState<ChangeDraft[]>([]);
  const [loading, setLoading] = useState(true);
  async function loadOrder(id: number) {
    const [v, c, d, p] = await Promise.all([
      fetch(`${apiBaseUrl}/orders/${id}/versions`).then((r) =>
        r.ok ? r.json() : [],
      ),
      fetch(`${apiBaseUrl}/orders/${id}/chat/conversations`).then((r) =>
        r.ok ? r.json() : [],
      ),
      fetch(`${apiBaseUrl}/orders/${id}/change-drafts`).then((r) =>
        r.ok ? r.json() : [],
      ),
      fetch(`${apiBaseUrl}/orders/${id}/processing-runs`).then((r) =>
        r.ok ? r.json() : [],
      ),
    ]);
    setVersions(v);
    setMessages(c.flatMap((x: { messages: ChatMessage[] }) => x.messages));
    setDrafts(d.filter((x: ChangeDraft) => x.status === "pending"));
    setProcessing(p);
  }
  const loadOrders = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/orders`);
      const data: OrderSummary[] = response.ok ? await response.json() : [];
      setOrders(data);
      setSelectedId((current) => current ?? data[0]?.id ?? null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);
  useEffect(() => {
    const socket = new WebSocket(`${websocketBaseUrl}/ws/orders`);
    const heartbeat = window.setInterval(
      () => socket.readyState === WebSocket.OPEN && socket.send("ping"),
      25_000,
    );
    socket.onmessage = () => void loadOrders();
    return () => {
      window.clearInterval(heartbeat);
      socket.close();
    };
  }, [loadOrders]);
  useEffect(() => {
    if (selectedId) void loadOrder(selectedId);
  }, [selectedId]);
  useEffect(() => {
    if (!selectedId) return;
    const ws = new WebSocket(`${websocketBaseUrl}/ws/orders/${selectedId}`);
    ws.onmessage = () => void loadOrder(selectedId);
    return () => ws.close();
  }, [selectedId]);
  return {
    orders,
    selectedId,
    setSelectedId,
    versions,
    processing,
    messages,
    setMessages,
    drafts,
    loading,
    loadOrder,
  };
}
