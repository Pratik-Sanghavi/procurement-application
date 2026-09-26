import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LineItem } from "@/lib/procurement";
export function LineItemsTable({ items }: { items: LineItem[] }) {
  return (
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
            {items.map((item) => (
              <tr key={item.line_number} className="border-b">
                <td className="p-3 font-medium">{item.description}</td>
                <td className="p-3">{item.confirmed_quantity ?? "—"}</td>
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
  );
}
