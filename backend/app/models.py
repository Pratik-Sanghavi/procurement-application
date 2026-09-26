from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)


class EmailThread(Base, Timestamped):
    __tablename__ = "email_threads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    emails: Mapped[list[Email]] = relationship(back_populates="thread")
    purchase_order: Mapped[Optional[PurchaseOrder]] = relationship(back_populates="thread", uselist=False)


class Email(Base, Timestamped):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id"), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sender: Mapped[str] = mapped_column(Text, nullable=False)
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    thread: Mapped[EmailThread] = relationship(back_populates="emails")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="email")


class Attachment(Base, Timestamped):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[bytes] = mapped_column(nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    email: Mapped[Email] = relationship(back_populates="attachments")


class PurchaseOrder(Base, Timestamped):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id"), nullable=False, unique=True)
    supplier_order_number: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    current_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("order_versions.id", use_alter=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    thread: Mapped[EmailThread] = relationship(back_populates="purchase_order")
    versions: Mapped[list[OrderVersion]] = relationship(back_populates="order", foreign_keys="OrderVersion.order_id")
    current_version: Mapped[Optional[OrderVersion]] = relationship(foreign_keys=[current_version_id], post_update=True)
    conversations: Mapped[list[ChatConversation]] = relationship(back_populates="order")


class OrderVersion(Base, Timestamped):
    __tablename__ = "order_versions"
    __table_args__ = (UniqueConstraint("order_id", "version_number", name="uq_order_version_number"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_email_id: Mapped[Optional[int]] = mapped_column(ForeignKey("emails.id"))
    order: Mapped[PurchaseOrder] = relationship(back_populates="versions", foreign_keys=[order_id])
    supplier: Mapped[Optional[SupplierSnapshot]] = relationship(back_populates="order_version", uselist=False, cascade="all, delete-orphan")
    details: Mapped[Optional[OrderDetailsSnapshot]] = relationship(back_populates="order_version", uselist=False, cascade="all, delete-orphan")
    shipping: Mapped[Optional[ShippingSnapshot]] = relationship(back_populates="order_version", uselist=False, cascade="all, delete-orphan")
    financial_summary: Mapped[Optional[OrderFinancialSummary]] = relationship(back_populates="order_version", uselist=False, cascade="all, delete-orphan")
    line_items: Mapped[list[LineItemSnapshot]] = relationship(back_populates="order_version", cascade="all, delete-orphan", order_by="LineItemSnapshot.line_number")


class SupplierSnapshot(Base):
    __tablename__ = "supplier_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_version_id: Mapped[int] = mapped_column(ForeignKey("order_versions.id"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    contact_information: Mapped[Optional[str]] = mapped_column(Text)
    salesperson: Mapped[Optional[str]] = mapped_column(Text)
    order_version: Mapped[OrderVersion] = relationship(back_populates="supplier")


class OrderDetailsSnapshot(Base):
    __tablename__ = "order_detail_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_version_id: Mapped[int] = mapped_column(ForeignKey("order_versions.id"), unique=True, nullable=False)
    buyer_po_reference: Mapped[Optional[str]] = mapped_column(String(128))
    document_date: Mapped[Optional[date]] = mapped_column(Date)
    order_received_date: Mapped[Optional[date]] = mapped_column(Date)
    buyer_details: Mapped[Optional[str]] = mapped_column(Text)
    billing_address: Mapped[Optional[str]] = mapped_column(Text)
    order_version: Mapped[OrderVersion] = relationship(back_populates="details")


class ShippingSnapshot(Base):
    __tablename__ = "shipping_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_version_id: Mapped[int] = mapped_column(ForeignKey("order_versions.id"), unique=True, nullable=False)
    delivery_address: Mapped[Optional[str]] = mapped_column(Text)
    shipping_method: Mapped[Optional[str]] = mapped_column(Text)
    order_version: Mapped[OrderVersion] = relationship(back_populates="shipping")

class OrderFinancialSummary(Base):
    __tablename__ = "order_financial_summaries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_version_id: Mapped[int] = mapped_column(ForeignKey("order_versions.id"), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    plant_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    variety_license_fee_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    container_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    label_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    freight: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    grand_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    order_version: Mapped[OrderVersion] = relationship(back_populates="financial_summary")

class LineItemSnapshot(Base):
    __tablename__ = "line_item_snapshots"
    __table_args__ = (UniqueConstraint("order_version_id", "line_number", name="uq_line_item_number"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_version_id: Mapped[int] = mapped_column(ForeignKey("order_versions.id"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[Optional[str]] = mapped_column(Text)
    ordered_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3))
    confirmed_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3))
    catalog_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    customer_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    variety_license_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    extended_line_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    item_notes: Mapped[Optional[str]] = mapped_column(Text)
    scheduled_shipping_date_or_week: Mapped[Optional[str]] = mapped_column(String(128))
    order_version: Mapped[OrderVersion] = relationship(back_populates="line_items")


class ProcessingRun(Base, Timestamped):
    __tablename__ = "processing_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), nullable=False, index=True)
    attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id"))
    temporal_workflow_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    stage: Mapped[Optional[str]] = mapped_column(String(64))
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ChatConversation(Base, Timestamped):
    __tablename__ = "chat_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    order: Mapped[PurchaseOrder] = relationship(back_populates="conversations")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="conversation", order_by="ChatMessage.created_at")


class ChatMessage(Base, Timestamped):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("chat_conversations.id"), nullable=False, index=True)
    reply_to_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chat_messages.id"))
    sender_type: Mapped[str] = mapped_column(String(16), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(32))
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(255))
    conversation: Mapped[ChatConversation] = relationship(back_populates="messages")


class AgentChangeDraft(Base, Timestamped):
    __tablename__ = "agent_change_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    chat_message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), nullable=False)
    base_version_id: Mapped[int] = mapped_column(ForeignKey("order_versions.id"), nullable=False)
    proposed_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base, Timestamped):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    order_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("order_versions.id"))
    chat_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chat_messages.id"))
    agent_change_draft_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agent_change_drafts.id"))
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary_json: Mapped[Optional[str]] = mapped_column(Text)
