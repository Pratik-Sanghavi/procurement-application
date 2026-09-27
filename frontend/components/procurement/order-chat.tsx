import type { FormEvent } from "react";
import { Check, MessageSquare, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import type { ChangeDraft, ChatMessage } from "@/lib/procurement";

export function OrderChat({
  messages,
  drafts,
  message,
  disabled,
  error,
  setMessage,
  onSend,
  onResolve,
}: {
  messages: ChatMessage[];
  drafts: ChangeDraft[];
  message: string;
  disabled: boolean;
  error: string | null;
  setMessage: (value: string) => void;
  onSend: (event: FormEvent<HTMLFormElement>) => void;
  onResolve: (id: number, action: "accept" | "discard") => void;
}) {
  return (
    <>
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
              <Button size="sm" onClick={() => onResolve(draft.id, "accept")}>
                <Check className="mr-1 h-3 w-3" />
                Accept
              </Button>
              <Button size="sm" variant="outline" onClick={() => onResolve(draft.id, "discard")}>
                Discard
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
      <form onSubmit={onSend} className="mt-4">
        <Textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask about this order or request a change..."
        />
        <Button type="submit" className="mt-2 w-full" disabled={disabled || !message.trim()}>
          <Send className="mr-2 h-4 w-4" />
          Send
        </Button>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      </form>
    </>
  );
}