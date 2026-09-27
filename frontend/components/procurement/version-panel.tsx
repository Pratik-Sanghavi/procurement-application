import { Bot, ChevronRight, GitCompareArrows, UserRound } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OrderVersion, VersionChange } from "@/lib/procurement";

const label = (field: string) => field.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const display = (value: unknown) => value == null ? "--" : String(value);

function changeGroups(changes: VersionChange[]) {
  const summary: VersionChange[] = [];
  const items = new Map<string, VersionChange[]>();
  for (const change of changes) {
    const match = change.path.match(/^line_items\[([^\]]+)]\.(.+)$/);
    if (!match) {
      summary.push(change);
      continue;
    }
    const [, item, field] = match;
    const grouped = items.get(item) ?? [];
    grouped.push({ ...change, path: field });
    items.set(item, grouped);
  }
  return { summary, items };
}

export function VersionPanel({ versions, activeVersionId, changes, onSelect }: {
  versions: OrderVersion[];
  activeVersionId: number | null;
  changes: VersionChange[];
  onSelect: (id: number) => void;
}) {
  const groups = changeGroups(changes);
  return (
    <div className="grid gap-4 xl:grid-cols-[220px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-sm">Versions</CardTitle></CardHeader>
        <CardContent className="space-y-1">
          {versions.map((version) => {
            const human = version.created_by_type === "human";
            return <button key={version.id} onClick={() => onSelect(version.id)} className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-sm ${activeVersionId === version.id ? "bg-muted font-medium" : "hover:bg-muted/60"}`}>
              <span className="flex items-center gap-2"><span title={human ? "Human edit" : "Agent edit"}>{human ? <UserRound className="h-4 w-4 text-sky-700" aria-label="Human edit" /> : <Bot className="h-4 w-4 text-violet-700" aria-label="Agent edit" />}</span>Version {version.version_number}</span>
              <ChevronRight className="h-4 w-4" />
            </button>;
          })}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><GitCompareArrows className="h-4 w-4" />Changes from previous version</CardTitle></CardHeader>
        <CardContent className="max-h-80 overflow-y-auto pr-2">
          {!changes.length ? <p className="text-sm text-muted-foreground">Select a non-current version or wait for a revision to compare.</p> : (
            <div className="space-y-3">
              {groups.summary.length > 0 && <section><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Order details</p>{groups.summary.map((change) => <div key={change.path} className="grid grid-cols-[9rem_1fr_1fr] gap-2 border-t py-2 text-sm"><span className="font-medium">{label(change.path.split(".").at(-1) ?? change.path)}</span><span className="text-muted-foreground">{display(change.before)}</span><span className="font-medium text-emerald-700">{display(change.after)}</span></div>)}</section>}
              {Array.from(groups.items.entries()).map(([item, itemChanges]) => <details key={item} className="rounded-md border bg-muted/20 p-2"><summary className="cursor-pointer text-sm font-medium">{item} <span className="text-muted-foreground">({itemChanges.length} changes)</span></summary><div className="mt-2 space-y-1">{itemChanges.map((change) => <div key={change.path} className="grid grid-cols-[8rem_1fr_1fr] gap-2 border-t py-2 text-sm"><span className="font-medium">{label(change.path)}</span><span className="text-muted-foreground">{display(change.before)}</span><span className="font-medium text-emerald-700">{display(change.after)}</span></div>)}</div></details>)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}