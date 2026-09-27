"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { FileText, Pencil, Save, X } from "lucide-react";
import { toast } from "sonner";

import { useOrderWorkspace } from "@/hooks/use-order-workspace";
import { LineItemsTable } from "@/components/procurement/line-items-table";
import { OrderChat } from "@/components/procurement/order-chat";
import { OrderSidebar } from "@/components/procurement/order-sidebar";
import { ProcessingCard } from "@/components/procurement/processing-card";
import { PendingChangeReview } from "@/components/procurement/pending-change-review";
import { VersionPanel } from "@/components/procurement/version-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

import {
  apiBaseUrl as api,
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
  const [baseVersionId, setBaseVersionId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(false);
  const [editorValue, setEditorValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const notifiedDraftIds = useRef(new Set<number>());

  const selectedVersion = useMemo(
    () =>
      versions.find((version) => version.id === selectedVersionId) ??
      [...versions].sort(
        (left, right) => right.version_number - left.version_number,
      )[0] ??
      null,
    [versions, selectedVersionId],
  );

  useEffect(() => {
    if (!selectedVersion) {
      setBaseVersionId(null);
      return;
    }
    setBaseVersionId((current) => {
      if (
        current !== null &&
        current !== selectedVersion.id &&
        versions.some((version) => version.id === current)
      )
        return current;
      return (
        [...versions]
          .filter(
            (version) =>
              version.version_number < selectedVersion.version_number,
          )
          .sort((left, right) => right.version_number - left.version_number)[0]
          ?.id ?? null
      );
    });
  }, [selectedVersion, versions]);

  useEffect(() => {
    if (!selectedId || !selectedVersion || !baseVersionId) {
      setChanges([]);
      return;
    }
    fetch(
      `${api}/orders/${selectedId}/versions/${selectedVersion.id}/diff?base_version_id=${baseVersionId}`,
    )
      .then((r) => (r.ok ? r.json() : { changes: [] }))
      .then((data) => setChanges(data.changes));
  }, [selectedId, selectedVersion, baseVersionId]);

  useEffect(() => {
    for (const draft of drafts) {
      if (notifiedDraftIds.current.has(draft.id)) continue;
      notifiedDraftIds.current.add(draft.id);
      toast.success("Change proposal ready", {
        description: "Review it below, then accept or discard the update.",
      });
    }
  }, [drafts]);
  function selectOrder(id: number) {
    setSelectedId(id);
    setSelectedVersionId(null);
    setBaseVersionId(null);
    setEditing(false);
    setChanges([]);
  }

  function selectVersion(id: number) {
    setSelectedVersionId(id);
    const version = versions.find((candidate) => candidate.id === id);
    const previous = version
      ? [...versions]
          .filter(
            (candidate) => candidate.version_number < version.version_number,
          )
          .sort((left, right) => right.version_number - left.version_number)[0]
      : null;
    setBaseVersionId(previous?.id ?? null);
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
    if (!response.ok) {
      setChatError("Message could not be sent. Please try again.");
      return;
    }
    const createdMessage = await response.json();
    setMessages((items) => [...items, createdMessage]);
    setMessage("");
    setChatError(null);
  }

  async function resolveDraft(draftId: number, action: "accept" | "discard") {
    if (!selectedId) return;
    const response = await fetch(
      `${api}/orders/${selectedId}/change-drafts/${draftId}/${action}`,
      { method: "POST" },
    );
    if (response.ok) {
      await loadOrder(selectedId);
      toast.success(
        action === "accept" ? "Change accepted" : "Change discarded",
      );
      return;
    }
    toast.error("Could not update the change proposal.");
  }

  return (
    <main className="min-h-screen bg-slate-50 text-foreground">
      <header className="flex h-[72px] items-center justify-between border-b border-slate-200 bg-white px-7">
        <div className="flex items-center gap-3.5">
          <div className="rounded-xl bg-slate-900 p-2.5 text-white shadow-sm">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold tracking-tight">
              Procurement Assistant
            </h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Purchase-order acknowledgements
            </p>
          </div>
        </div>
        <Badge className="border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-emerald-700 hover:bg-emerald-50">
          Live workflow status
        </Badge>
      </header>
      <div className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <OrderSidebar
          orders={orders}
          selectedId={selectedId}
          loading={loading}
          onSelect={selectOrder}
        />
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
              <VersionPanel
                versions={versions}
                activeVersionId={selectedVersion.id}
                baseVersionId={baseVersionId}
                changes={changes}
                onSelect={selectVersion}
                onBaseSelect={setBaseVersionId}
              />
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
              <PendingChangeReview
                drafts={drafts}
                currentItems={selectedVersion.line_items}
                onResolve={resolveDraft}
              />
              <LineItemsTable items={selectedVersion.line_items} />
            </>
          ) : (
            <div className="flex min-h-[520px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-6 text-center">
              <FileText className="mb-4 h-9 w-9 text-slate-300" />
              <h2 className="text-base font-semibold text-slate-800">
                Your order workspace is ready
              </h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
                Send a supplier acknowledgement through the email simulator to
                create your first order and see its processing timeline here.
              </p>
            </div>
          )}
        </section>
        <aside className="border-l border-slate-200 bg-white/80 p-5">
          <ProcessingCard run={processing[0]} />
          <OrderChat
            messages={messages}
            message={message}
            disabled={!selectedId}
            error={chatError}
            setMessage={setMessage}
            onSend={sendMessage}
          />
        </aside>
      </div>
    </main>
  );
}
