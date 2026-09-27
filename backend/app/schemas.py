from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    @model_validator(mode="after")
    def require_complete_line_item_set(self) -> "OrderSnapshotInput":
        if not self.line_items:
            raise ValueError("Acknowledgement must contain at least one line item before it can be persisted")
        line_numbers = [item.line_number for item in self.line_items]
        if len(line_numbers) != len(set(line_numbers)):
            raise ValueError("Acknowledgement contains duplicate line numbers")
        return self

class OrderSnapshotChunk(BaseModel):
    """A partial extraction from a bounded range of acknowledgement pages."""

    supplier_order_number: str | None = Field(default=None, max_length=128)
    supplier: SupplierData | None = None
    details: OrderDetailsData | None = None
    shipping: ShippingData | None = None
    financial_summary: FinancialSummaryData | None = None
    line_items: list[LineItemData] = Field(default_factory=list)

class OrderFieldChange(BaseModel):
    section: Literal["supplier", "details", "shipping", "financial_summary"]
    field: str = Field(min_length=1)
    value: str | None = None


class LineItemFieldChange(BaseModel):
    line_number: int = Field(ge=1)
    field: str = Field(min_length=1)
    value: str | None = None


class OrderChangePlan(BaseModel):
    """A compact, explicit patch proposed from a chat request."""

    order_updates: list[OrderFieldChange] = Field(default_factory=list)
    line_item_updates: list[LineItemFieldChange] = Field(default_factory=list)

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
class ProcessingRunResponse(BaseModel):
    id: int
    email_id: int
    attachment_id: int | None
    temporal_workflow_id: str
    status: str
    stage: str | None
    error_summary: str | None
    completed_at: datetime | None
    created_at: datetime


class VersionChange(BaseModel):
    path: str
    before: Any | None
    after: Any | None


class VersionDiffResponse(BaseModel):
    base_version_id: int
    version_id: int
    changes: list[VersionChange]
