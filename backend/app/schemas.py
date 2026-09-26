from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SupplierData(BaseModel):
    name: str
    address: str | None = None
    contact_information: str | None = None
    salesperson: str | None = None


class OrderDetailsData(BaseModel):
    buyer_po_reference: str | None = None
    document_date: date | None = None
    order_received_date: date | None = None
    buyer_details: str | None = None
    billing_address: str | None = None


class ShippingData(BaseModel):
    delivery_address: str | None = None
    shipping_method: str | None = None


class FinancialSummaryData(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    plant_cost: Decimal | None = Field(default=None, ge=0)
    variety_license_fee_total: Decimal | None = Field(default=None, ge=0)
    container_cost: Decimal | None = Field(default=None, ge=0)
    label_cost: Decimal | None = Field(default=None, ge=0)
    freight: Decimal | None = Field(default=None, ge=0)
    grand_total: Decimal | None = Field(default=None, ge=0)


class LineItemData(BaseModel):
    line_number: int = Field(ge=1)
    description: str = Field(min_length=1)
    size: str | None = None
    ordered_quantity: Decimal | None = Field(default=None, ge=0)
    confirmed_quantity: Decimal | None = Field(default=None, ge=0)
    catalog_price: Decimal | None = Field(default=None, ge=0)
    customer_price: Decimal | None = Field(default=None, ge=0)
    variety_license_fee: Decimal | None = Field(default=None, ge=0)
    extended_line_amount: Decimal | None = Field(default=None, ge=0)
    item_notes: str | None = None
    scheduled_shipping_date_or_week: str | None = None


class OrderSnapshotInput(BaseModel):
    supplier_order_number: str = Field(min_length=1, max_length=128)
    supplier: SupplierData
    details: OrderDetailsData = Field(default_factory=OrderDetailsData)
    shipping: ShippingData = Field(default_factory=ShippingData)
    financial_summary: FinancialSummaryData = Field(default_factory=FinancialSummaryData)
    line_items: list[LineItemData] = Field(default_factory=list)


class OrderVersionResponse(OrderSnapshotInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version_number: int
    source_type: str
    created_by_type: str
    created_at: datetime


class OrderSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    supplier_order_number: str
    status: str
    current_version_id: int | None
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    conversation_id: int | None = None
    content: str = Field(min_length=1, max_length=10_000)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    reply_to_message_id: int | None
    sender_type: str
    message_type: str
    content: str
    intent: str | None
    created_at: datetime
class ChatConversationResponse(BaseModel):
    id: int
    order_id: int
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse]


class AgentChangeDraftResponse(BaseModel):
    id: int
    order_id: int
    chat_message_id: int
    base_version_id: int
    proposed_snapshot: OrderSnapshotInput
    status: str
    resolved_at: datetime | None
    created_at: datetime
