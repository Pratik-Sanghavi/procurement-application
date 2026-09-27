import { Bot, ChevronRight, GitCompareArrows, UserRound } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OrderVersion, VersionChange } from "@/lib/procurement";

const label = (field: string) =>
  field.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const display = (value: unknown) => (value == null ? "--" : String(value));
type DiffRow = { item: string; field: string; before: unknown; after: unknown };

function toRows(changes: VersionChange[]): DiffRow[] {
  return changes.map((change) => {
    const match = change.path.match(/^line_items\[([^\]]+)]\.(.+)$/);
    if (!match)
      return {
        item: "Order details",
        field: label(change.path.split(".").at(-1) ?? change.path),
        before: change.before,
        after: change.after,
      };
    return {
      item: match[1],
      field: label(match[2]),
      before: change.before,
      after: change.after,
    };
  });
}

export function VersionPanel({
  versions,
  activeVersionId,
  baseVersionId,
  changes,
  onSelect,
  onBaseSelect,
}: {
  versions: OrderVersion[];
  activeVersionId: number | null;
  baseVersionId: number | null;
  changes: VersionChange[];
  onSelect: (id: number) => void;
  onBaseSelect: (id: number) => void;
}) {
  const rows = toRows(changes);
  const active = versions.find((version) => version.id === activeVersionId);
  const comparisonVersions = versions.filter(
    (version) => version.id !== activeVersionId,
  );

  return (
    <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Versions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {versions.map((version) => {
            const human = version.created_by_type === "human";
            return (
              <button
                key={version.id}
                onClick={() => onSelect(version.id)}
                className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-sm ${activeVersionId === version.id ? "bg-muted font-medium" : "hover:bg-muted/60"}`}
              >
                <span className="flex items-center gap-2">
                  <span title={human ? "Human edit" : "Agent edit"}>
                    {human ? (
                      <UserRound
                        className="h-4 w-4 text-sky-700"
                        aria-label="Human edit"
                      />
                    ) : (
                      <Bot
                        className="h-4 w-4 text-violet-700"
                        aria-label="Agent edit"
                      />
                    )}
                  </span>
                  Version {version.version_number}
                </span>
                <ChevronRight className="h-4 w-4" />
              </button>
            );
          })}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <GitCompareArrows className="h-4 w-4" />
            Compare Version {active?.version_number ?? "--"}
          </CardTitle>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Against
            <select
              value={baseVersionId ?? ""}
              onChange={(event) => onBaseSelect(Number(event.target.value))}
              disabled={!comparisonVersions.length}
              className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground"
            >
              {comparisonVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  Version {version.version_number}
                </option>
              ))}
            </select>
          </label>
        </CardHeader>
        <CardContent className="max-h-80 overflow-auto px-0">
          {!rows.length ? (
            <p className="px-6 text-sm text-muted-foreground">
              No differences for this comparison.
            </p>
          ) : (
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="sticky top-0 bg-background text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-y">
                  <th className="px-6 py-3 font-medium">Item</th>
                  <th className="px-4 py-3 font-medium">Field</th>
                  <th className="px-4 py-3 font-medium">Before</th>
                  <th className="px-6 py-3 font-medium">After</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr
                    key={`${row.item}-${row.field}-${index}`}
                    className="border-b last:border-0"
                  >
                    <td className="max-w-56 px-6 py-3 font-medium">
                      {row.item}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {row.field}
                    </td>
                    <td className="max-w-52 px-4 py-3 text-muted-foreground">
                      {display(row.before)}
                    </td>
                    <td className="max-w-52 px-6 py-3 font-medium text-emerald-700">
                      {display(row.after)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
