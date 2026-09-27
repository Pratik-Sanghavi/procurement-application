export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";
export const websocketBaseUrl = apiBaseUrl.replace(/^http/, "ws");

export type OrderSummary = {
  id: number;
  supplier_order_number: string;
  status: string;
  current_version_id: number | null;
};
export type LineItem = {
  line_number: number;
  description: string;
  size: string | null;
  ordered_quantity: string | null;
  confirmed_quantity: string | null;
  catalog_price: string | null;
  customer_price: string | null;
  variety_license_fee: string | null;
  extended_line_amount: string | null;
  item_notes: string | null;
  scheduled_shipping_date_or_week: string | null;
};
export type OrderVersion = {
  id: number;
  version_number: number;
  source_type: string;
  created_by_type: string;
  created_at: string;
  supplier_order_number: string;
  supplier: { name: string };
  details: { buyer_po_reference: string | null };
  financial_summary: { grand_total: number | null; currency: string };
  line_items: LineItem[];
};
export type ChatMessage = {
  id: number;
  sender_type: "human" | "agent" | "system";
  content: string;
  created_at: string;
};
export type ChangeDraft = {
  id: number;
  status: string;
  proposed_snapshot: { line_items: LineItem[] };
};
export type ProcessingRun = {
  id: number;
  status: string;
  stage: string | null;
  error_summary: string | null;
  created_at: string;
};
export type VersionChange = { path: string; before: unknown; after: unknown };

export function versionSnapshot(version: OrderVersion) {
  const copy = { ...version } as Record<string, unknown>;
  [
    "id",
    "version_number",
    "source_type",
    "created_by_type",
    "created_at",
  ].forEach((key) => delete copy[key]);
  return copy;
}
