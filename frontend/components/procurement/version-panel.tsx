import { Bot, ChevronRight, GitCompareArrows, UserRound } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OrderVersion, VersionChange } from "@/lib/procurement";

export function VersionPanel({
  versions,
  activeVersionId,
  changes,
  onSelect,
}: {
  versions: OrderVersion[];
  activeVersionId: number | null;
  changes: VersionChange[];
  onSelect: (id: number) => void;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[220px_1fr]">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Versions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {versions.map((version) => (
            <button
              key={version.id}
              onClick={() => onSelect(version.id)}
              className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-sm ${activeVersionId === version.id ? "bg-muted font-medium" : "hover:bg-muted/60"}`}
            >
              <span className="flex items-center gap-2">
                {version.created_by_type === "human" ? (
                  <UserRound
                    className="h-4 w-4 text-sky-700"
                    aria-label="Human edit"
                    title="Human edit"
                  />
                ) : (
                  <Bot
                    className="h-4 w-4 text-violet-700"
                    aria-label="Agent edit"
                    title="Agent edit"
                  />
                )}
                Version {version.version_number}
              </span>
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
              Select a non-current version or wait for a revision to compare.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
