import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ChangeDraft, LineItem } from "@/lib/procurement";

const comparableFields = [
  ["ordered_quantity", "Ordered"],
  ["confirmed_quantity", "Confirmed"],
  ["catalog_price", "Catalog price"],
  ["customer_price", "Your price"],
  ["variety_license_fee", "Variety fee"],
  ["extended_line_amount", "Extended amount"],
  ["scheduled_shipping_date_or_week", "Ship week"],
] as const;

const display = (value: string | null) => value ?? "--";

export function PendingChangeReview({
  drafts,
  currentItems,
  onResolve,
}: {
  drafts: ChangeDraft[];
  currentItems: LineItem[];
  onResolve: (id: number, action: "accept" | "discard") => void;
}) {
  if (!drafts.length) return null;
  const currentByLine = new Map(currentItems.map((item) => [item.line_number, item]));

  return (
    <section aria-label="Pending order changes" className="space-y-3">
      {drafts.map((draft) => {
        const changes = draft.proposed_snapshot.line_items.flatMap((proposed) => {
          const current = currentByLine.get(proposed.line_number);
          if (!current) return [];
          return comparableFields.flatMap(([field, label]) =>
            current[field] === proposed[field]
              ? []
              : [{ description: proposed.description, label, before: current[field], after: proposed[field] }],
          );
        });
        return (
          <Card key={draft.id} className="border-amber-300 bg-amber-50 shadow-sm">
            <CardContent className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-amber-950">Proposed order update</p>
                  <p className="mt-1 text-sm text-amber-900">Review the exact changes before applying them.</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => onResolve(draft.id, "accept")}>
                    <Check className="mr-1 h-3 w-3" />
                    Accept change
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => onResolve(draft.id, "discard")}>
                    Discard
                  </Button>
                </div>
              </div>
              <div className="mt-4 overflow-x-auto rounded-md border border-amber-200 bg-white">
                {changes.length ? (
                  <table className="min-w-[680px] w-full text-sm">
                    <thead className="bg-amber-100/70 text-left text-xs text-amber-950">
                      <tr><th className="p-2">Line item</th><th className="p-2">Field</th><th className="p-2">Current</th><th className="p-2">Proposed</th></tr>
                    </thead>
                    <tbody>
                      {changes.map((change, index) => (
                        <tr key={`${change.description}-${change.label}-${index}`} className="border-t border-amber-100">
                          <td className="p-2 font-medium">{change.description}</td>
                          <td className="p-2">{change.label}</td>
                          <td className="p-2 text-muted-foreground">{display(change.before)}</td>
                          <td className="p-2 font-medium text-emerald-700">{display(change.after)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <p className="p-3 text-sm text-amber-900">No line-item delta could be calculated for this proposal.</p>}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </section>
  );
}