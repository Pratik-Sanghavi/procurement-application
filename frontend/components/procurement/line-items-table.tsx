import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LineItem } from "@/lib/procurement";

const value = (input: string | null) => input ?? "--";

export function LineItemsTable({ items }: { items: LineItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Line items</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-[calc(100vh-20rem)] min-h-[18rem] overflow-auto">
          <table className="min-w-[1180px] w-full text-sm">
            <thead className="sticky top-0 z-10 border-y bg-muted text-left text-xs text-muted-foreground shadow-sm">
              <tr>
                <th className="min-w-[16rem] p-3">Description</th>
                <th className="p-3">Size</th>
                <th className="p-3 text-right">Ordered</th>
                <th className="p-3 text-right">Confirmed</th>
                <th className="p-3 text-right">Catalog price</th>
                <th className="p-3 text-right">Your price</th>
                <th className="p-3 text-right">Var. fee</th>
                <th className="p-3 text-right">Extended</th>
                <th className="p-3">Ship week</th>
                <th className="min-w-[14rem] p-3">Notes</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.line_number} className="border-b align-top">
                  <td className="p-3 font-medium">{item.description}</td>
                  <td className="p-3">{value(item.size)}</td>
                  <td className="p-3 text-right tabular-nums">{value(item.ordered_quantity)}</td>
                  <td className="p-3 text-right tabular-nums">{value(item.confirmed_quantity)}</td>
                  <td className="p-3 text-right tabular-nums">{value(item.catalog_price)}</td>
                  <td className="p-3 text-right tabular-nums">{value(item.customer_price)}</td>
                  <td className="p-3 text-right tabular-nums">{value(item.variety_license_fee)}</td>
                  <td className="p-3 text-right tabular-nums">{value(item.extended_line_amount)}</td>
                  <td className="p-3">{value(item.scheduled_shipping_date_or_week)}</td>
                  <td className="whitespace-pre-line p-3 text-muted-foreground">{value(item.item_notes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}