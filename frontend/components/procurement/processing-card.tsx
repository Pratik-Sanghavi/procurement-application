import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProcessingRun } from "@/lib/procurement";

export function ProcessingCard({ run }: { run?: ProcessingRun }) {
  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle className="text-sm">Processing</CardTitle>
      </CardHeader>
      <CardContent>
        {run ? (
          <div className="text-sm">
            <Badge
              variant={run.status === "failed" ? "destructive" : "secondary"}
            >
              {run.status}
            </Badge>
            <p className="mt-2">{run.stage ?? "Waiting to start"}</p>
            {run.error_summary && (
              <p className="mt-2 text-xs text-destructive">
                {run.error_summary}
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
  );
}
