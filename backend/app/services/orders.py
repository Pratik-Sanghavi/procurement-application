from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    AuditEvent,
    LineItemSnapshot,
    OrderDetailsSnapshot,
    OrderFinancialSummary,
    OrderVersion,
    PurchaseOrder,
    ShippingSnapshot,
    SupplierSnapshot,
)
from ..schemas import OrderSnapshotInput, OrderSummaryResponse, OrderVersionResponse


def order_query():
    return select(PurchaseOrder).options(
        selectinload(PurchaseOrder.current_version),
        selectinload(PurchaseOrder.versions).selectinload(OrderVersion.supplier),
        selectinload(PurchaseOrder.versions).selectinload(OrderVersion.details),
        selectinload(PurchaseOrder.versions).selectinload(OrderVersion.shipping),
        selectinload(PurchaseOrder.versions).selectinload(OrderVersion.financial_summary),
        selectinload(PurchaseOrder.versions).selectinload(OrderVersion.line_items),
    )


def get_order(session: Session, order_id: int) -> PurchaseOrder:
    order = session.scalar(order_query().where(PurchaseOrder.id == order_id))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return order


def version_response(version: OrderVersion) -> OrderVersionResponse:
    if version.supplier is None:
        raise RuntimeError(f"Order version {version.id} has no supplier snapshot")
    summary = version.financial_summary
    return OrderVersionResponse(
        id=version.id,
        version_number=version.version_number,
        source_type=version.source_type,
        created_by_type=version.created_by_type,
        created_at=version.created_at,
        supplier_order_number=version.order.supplier_order_number,
        supplier={
            "name": version.supplier.name,
            "address": version.supplier.address,
            "contact_information": version.supplier.contact_information,
            "salesperson": version.supplier.salesperson,
        },
        details={
            "buyer_po_reference": version.details.buyer_po_reference if version.details else None,
            "document_date": version.details.document_date if version.details else None,
            "order_received_date": version.details.order_received_date if version.details else None,
            "buyer_details": version.details.buyer_details if version.details else None,
            "billing_address": version.details.billing_address if version.details else None,
        },
        shipping={
            "delivery_address": version.shipping.delivery_address if version.shipping else None,
            "shipping_method": version.shipping.shipping_method if version.shipping else None,
        },
        financial_summary={
            "currency": summary.currency if summary else "USD",
            "plant_cost": summary.plant_cost if summary else None,
            "variety_license_fee_total": summary.variety_license_fee_total if summary else None,
            "container_cost": summary.container_cost if summary else None,
            "label_cost": summary.label_cost if summary else None,
            "freight": summary.freight if summary else None,
            "grand_total": summary.grand_total if summary else None,
        },
        line_items=[
            {
                "line_number": item.line_number,
                "description": item.description,
                "size": item.size,
                "ordered_quantity": item.ordered_quantity,
                "confirmed_quantity": item.confirmed_quantity,
                "catalog_price": item.catalog_price,
                "customer_price": item.customer_price,
                "variety_license_fee": item.variety_license_fee,
                "extended_line_amount": item.extended_line_amount,
                "item_notes": item.item_notes,
                "scheduled_shipping_date_or_week": item.scheduled_shipping_date_or_week,
            }
            for item in version.line_items
        ],
    )


def summary_response(order: PurchaseOrder) -> OrderSummaryResponse:
    return OrderSummaryResponse(
        id=order.id,
        supplier_order_number=order.supplier_order_number,
        status=order.status,
        current_version_id=order.current_version_id,
        updated_at=order.updated_at,
    )


def append_version(
    session: Session,
    *,
    order: PurchaseOrder,
    snapshot: OrderSnapshotInput,
    source_type: str,
    actor_type: str,
    source_email_id: int | None = None,
    audit_action: str = "version.created",
) -> OrderVersion:
    if order.supplier_order_number != snapshot.supplier_order_number:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Supplier order number is immutable")

    next_number = max((version.version_number for version in order.versions), default=0) + 1
    version = OrderVersion(
        order=order,
        version_number=next_number,
        source_type=source_type,
        created_by_type=actor_type,
        source_email_id=source_email_id,
        supplier=SupplierSnapshot(**snapshot.supplier.model_dump()),
        details=OrderDetailsSnapshot(**snapshot.details.model_dump()),
        shipping=ShippingSnapshot(**snapshot.shipping.model_dump()),
        financial_summary=OrderFinancialSummary(**snapshot.financial_summary.model_dump()),
        line_items=[LineItemSnapshot(**item.model_dump()) for item in snapshot.line_items],
    )
    session.add(version)
    session.flush()
    order.current_version = version
    order.updated_at = datetime.now(UTC)
    session.add(
        AuditEvent(
            order_id=order.id,
            order_version_id=version.id,
            actor_type=actor_type,
            action=audit_action,
            change_summary_json=json.dumps({"version_number": next_number, "source_type": source_type}),
        )
    )
    session.flush()
    return version