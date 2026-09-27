"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronRight,
  FileText,
  GitCompareArrows,
  Loader2,
  MessageSquare,
  Pencil,
  Save,
  Send,
  X,
} from "lucide-react";

import { useOrderWorkspace } from "@/hooks/use-order-workspace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

import {
  apiBaseUrl as api,
  websocketBaseUrl as wsBase,
  versionSnapshot as snapshot,
  type VersionChange as Change,
} from "@/lib/procurement";

export default function Home() {
  const {
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
  } = useOrderWorkspace();
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(
    null,
  );
  const [changes, setChanges] = useState<Change[]>([]);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(false);
  const [editorValue, setEditorValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const selectedVersion = useMemo(
    () =>
      versions.find((version) => version.id === selectedVersionId) ??
      versions[0] ??
      null,
    [versions, selectedVersionId],
  );

  useEffect(() => {
    if (!selectedId) return;
    const socket = new WebSocket(`${wsBase}/ws/orders/${selectedId}`);
    const heartbeat = window.setInterval(
      () => socket.readyState === WebSocket.OPEN && socket.send("ping"),
      25000,
    );
    socket.onmessage = () => void loadOrder(selectedId);
    return () => {
      window.clearInterval(heartbeat);
      socket.close();
    };
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !selectedVersionId || versions.length < 2) {
      setChanges([]);
      return;
    }
    const base = versions.find((version) => version.id !== selectedVersionId);
    if (!base) return;
    fetch(
      `${api}/orders/${selectedId}/versions/${selectedVersionId}/diff?base_version_id=${base.id}`,
    )
      .then((r) => (r.ok ? r.json() : { changes: [] }))
      .then((data) => setChanges(data.changes));
  }, [selectedId, selectedVersionId, versions]);

  function selectOrder(id: number) {
    setSelectedId(id);
    setSelectedVersionId(null);
    setEditing(false);
    setChanges([]);
  }
  function beginEdit() {
    if (selectedVersion) {
      setEditorValue(JSON.stringify(snapshot(selectedVersion), null, 2));
      setEditing(true);
      setError(null);
    }
  }

  async function saveEdit() {
    if (!selectedId) return;
    try {
      const payload = JSON.parse(editorValue);
      const response = await fetch(`${api}/orders/${selectedId}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await response.text());
      setEditing(false);
      await loadOrder(selectedId);
    } catch {
      setError(
        "The snapshot must be valid JSON that matches the order schema.",
      );
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!selectedId || !message.trim()) return;
    const response = await fetch(`${api}/orders/${selectedId}/chat/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: message }),
    });
    if (response.ok) {
      const createdMessage = await response.json();
      setMessages((items) => [...items, createdMessage]);
      setMessage("");
    }
  }

  async function resolveDraft(draftId: number, action: "accept" | "discard") {
    if (!selectedId) return;
    const response = await fetch(
      `${api}/orders/${selectedId}/change-drafts/${draftId}/${action}`,
      { method: "POST" },
    );
    if (response.ok) await loadOrder(selectedId);
  }

  return (
    <main className="min-h-screen bg-slate-50 text-foreground">
      <header className="flex h-[72px] items-center justify-between border-b border-slate-200 bg-white px-7">
        <div className="flex items-center gap-3.5">
          <div className="rounded-xl bg-slate-900 p-2.5 text-white shadow-sm">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold tracking-tight">Procurement Assistant</h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Purchase-order acknowledgements
            </p>
          </div>
        </div>
        <Badge className="border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-emerald-700 hover:bg-emerald-50">Live workflow status</Badge>
      </header>
      <div className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <aside className="border-r border-slate-200 bg-white/80 p-5">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            Orders
          </p>
          {loading ? (
            <Loader2 className="m-4 h-5 w-5 animate-spin" />
          ) : orders.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No orders have been processed yet.
            </p>
          ) : (
            <div className="space-y-2">
              {orders.map((item) => (
                <button
                  key={item.id}
                  onClick={() => selectOrder(item.id)}
                  className={`w-full rounded-md border p-3 text-left text-sm ${selectedId === item.id ? "border-primary bg-primary/5" : "hover:bg-muted"}`}
                >
                  <p className="font-medium">#{item.supplier_order_number}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.status}
                  </p>
                </button>
              ))}
            </div>
          )}
        </aside>
        <section className="space-y-6 p-7 lg:p-8">
          {selectedVersion ? (
            <>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">
                    {selectedVersion.supplier.name}
                  </p>
                  <h2 className="text-2xl font-semibold">
                    Order #{selectedVersion.supplier_order_number}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Buyer PO:{" "}
                    {selectedVersion.details.buyer_po_reference ??
                      "Not supplied"}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={beginEdit}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit snapshot
                  </Button>
                  <Card>
                    <CardContent className="p-3">
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Grand total
                      </p>
                      <p className="font-semibold">
                        {selectedVersion.financial_summary.grand_total == null
                          ? "—"
                          : new Intl.NumberFormat("en-US", {
                              style: "currency",
                              currency:
                                selectedVersion.financial_summary.currency,
                            }).format(
                              selectedVersion.financial_summary.grand_total,
                            )}
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </div>
              <div className="grid gap-4 xl:grid-cols-[220px_1fr]">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Versions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    {versions.map((version) => (
                      <button
                        key={version.id}
                        onClick={() => setSelectedVersionId(version.id)}
                        className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-sm ${selectedVersionId === version.id ? "bg-muted font-medium" : "hover:bg-muted/60"}`}
                      >
                        <span>Version {version.version_number}</span>
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    ))}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <GitCompareArrows className="h-4 w-4" />
                      Changes from previous version
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {changes.length ? (
                      <ul className="space-y-2 text-sm">
                        {changes.slice(0, 8).map((change) => (
                          <li key={change.path}>
                            <span className="font-medium">{change.path}</span>
                            <span className="ml-2 text-muted-foreground">
                              {String(change.before ?? "—")} →{" "}
                              {String(change.after ?? "—")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Select a non-current version or wait for a revision to
                        compare.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </div>
              {editing && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">
                      Edit complete snapshot
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Textarea
                      className="min-h-72 font-mono text-xs"
                      value={editorValue}
                      onChange={(event) => setEditorValue(event.target.value)}
                    />
                    {error && (
                      <p className="mt-2 text-sm text-destructive">{error}</p>
                    )}
                    <div className="mt-3 flex gap-2">
                      <Button onClick={saveEdit}>
                        <Save className="mr-2 h-4 w-4" />
                        Save new version
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setEditing(false)}
                      >
                        <X className="mr-2 h-4 w-4" />
                        Cancel
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Line items</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto p-0">
                  <table className="w-full text-sm">
                    <thead className="border-y bg-muted/40 text-left text-xs text-muted-foreground">
                      <tr>
                        <th className="p-3">Description</th>
                        <th className="p-3">Confirmed</th>
                        <th className="p-3">Your price</th>
                        <th className="p-3">Ship week</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedVersion.line_items.map((item) => (
                        <tr key={item.line_number} className="border-b">
                          <td className="p-3 font-medium">
                            {item.description}
                          </td>
                          <td className="p-3">
                            {item.confirmed_quantity ?? "—"}
                          </td>
                          <td className="p-3">{item.customer_price ?? "—"}</td>
                          <td className="p-3">
                            {item.scheduled_shipping_date_or_week ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="flex min-h-[520px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-6 text-center">
              <FileText className="mb-4 h-9 w-9 text-slate-300" />
              <h2 className="text-base font-semibold text-slate-800">Your order workspace is ready</h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">Send a supplier acknowledgement through the email simulator to create your first order and see its processing timeline here.</p>
            </div>
          )}
        </section>
        <aside className="border-l border-slate-200 bg-white/80 p-5">
          <Card className="mb-5 border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm">Processing</CardTitle>
            </CardHeader>
            <CardContent>
              {processing[0] ? (
                <div className="text-sm">
                  <Badge
                    variant={
                      processing[0].status === "failed"
                        ? "destructive"
                        : "secondary"
                    }
                  >
                    {processing[0].status}
                  </Badge>
                  <p className="mt-2">
                    {processing[0].stage ?? "Waiting to start"}
                  </p>
                  {processing[0].error_summary && (
                    <p className="mt-2 text-xs text-destructive">
                      {processing[0].error_summary}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No processing run yet.
                </p>
              )}
            </CardContent>
          </Card>
          <div className="mb-4 flex items-center gap-2 text-slate-800">
            <MessageSquare className="h-4 w-4" />
            <h2 className="font-semibold">Order chat</h2>
          </div>
          <div className="space-y-3">
            {messages.map((item) => (
              <div
                key={item.id}
                className={`rounded-md p-3 text-sm ${item.sender_type === "human" ? "ml-6 bg-primary text-primary-foreground" : "mr-6 bg-muted"}`}
              >
                {item.content}
              </div>
            ))}
          </div>
          <Separator className="my-4" />
          {drafts.map((draft) => (
            <Card key={draft.id} className="mb-3">
              <CardContent className="p-3">
                <p className="text-sm font-medium">Proposed change</p>
                <div className="mt-3 flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => resolveDraft(draft.id, "accept")}
                  >
                    <Check className="mr-1 h-3 w-3" />
                    Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => resolveDraft(draft.id, "discard")}
                  >
                    Discard
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
          <form onSubmit={sendMessage} className="mt-4">
            <Textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Ask about this order or request a change…"
            />
            <Button
              className="mt-2 w-full"
              disabled={!selectedId || !message.trim()}
            >
              <Send className="mr-2 h-4 w-4" />
              Send
            </Button>
          </form>
        </aside>
      </div>
    </main>
  );
}
