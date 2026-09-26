import { Loader2 } from "lucide-react";
import type { OrderSummary } from "@/lib/procurement";
export function OrderSidebar({
  orders,
  selectedId,
  loading,
  onSelect,
}: {
  orders: OrderSummary[];
  selectedId: number | null;
  loading: boolean;
  onSelect: (id: number) => void;
}) {
  return (
    <aside className="border-r bg-background p-4">
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Orders
      </p>
      {loading ? (
        <Loader2 className="m-4 h-5 w-5 animate-spin" />
      ) : (
        orders.map((order) => (
          <button
            key={order.id}
            onClick={() => onSelect(order.id)}
            className={`mb-2 w-full rounded-md border p-3 text-left text-sm ${selectedId === order.id ? "border-primary bg-primary/5" : "hover:bg-muted"}`}
          >
            <p className="font-medium">#{order.supplier_order_number}</p>
            <p className="mt-1 text-xs text-muted-foreground">{order.status}</p>
          </button>
        ))
      )}
    </aside>
  );
}
