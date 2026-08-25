import json
from pathlib import Path
from typing import Any, Dict, Optional
from app.schemas import SanitizedOrderResult

class OrderRepository:
    """Reads data/orders.json at runtime and performs exact normalized order lookups."""

    def __init__(self, orders_file: str | Path = "data/orders.json"):
        self.orders_file = Path(orders_file)
        self._dataset_name: Optional[str] = None
        self._snapshot_at: Optional[str] = None
        self._orders_by_id: Dict[str, Dict[str, Any]] = {}
        self._load_data()

    def _load_data(self) -> None:
        if not self.orders_file.exists():
            raise FileNotFoundError(f"Orders dataset not found at {self.orders_file}")

        with open(self.orders_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._dataset_name = data.get("dataset_name")
        self._snapshot_at = data.get("snapshot_at")

        # Index orders by normalized order_id
        for order in data.get("orders", []):
            raw_id = order.get("order_id", "")
            norm_id = self.normalize_order_id(raw_id)
            if norm_id:
                self._orders_by_id[norm_id] = order

    @staticmethod
    def normalize_order_id(raw_id: str) -> str:
        """Normalizes order ID by stripping surrounding whitespace, quotes, and uppercasing."""
        if not raw_id:
            return ""
        return raw_id.strip().strip("'\"").upper()

    def get_raw_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Returns raw order dictionary for exact normalized order ID match."""
        norm_id = self.normalize_order_id(order_id)
        return self._orders_by_id.get(norm_id)

    @property
    def snapshot_at(self) -> Optional[str]:
        return self._snapshot_at


class OrderSanitizer:
    """Applies data dictionary privacy rules, field filtering, and status precedence."""

    @staticmethod
    def sanitize(raw_order: Optional[Dict[str, Any]], requested_id: str, action: str = "lookup") -> SanitizedOrderResult:
        norm_id = OrderRepository.normalize_order_id(requested_id)

        # Handle Unknown Order
        if not raw_order:
            return SanitizedOrderResult(
                order_id=norm_id or requested_id,
                found=False,
                status="unknown",
                customer_safe_message="Order was not found in the system. Please verify your order ID or contact support.",
                handoff_required=True,
                handoff_reason="Order ID not found in system",
                action_supported=True if action == "lookup" else False
            )

        # Handle Unsupported Action
        if action != "lookup":
            return SanitizedOrderResult(
                order_id=raw_order.get("order_id", norm_id),
                found=True,
                status=raw_order.get("status", "unknown"),
                customer_safe_message=raw_order.get("customer_safe_message"),
                action_supported=False,
                handoff_required=True,
                handoff_reason=f"Action '{action}' is not supported by the lookup tool. Human support review is required."
            )

        raw_status = raw_order.get("status", "unknown")

        # Filter items to customer-safe fields only (name, quantity, final_sale)
        raw_items = raw_order.get("items", [])
        safe_items = []
        for item in raw_items:
            safe_items.append({
                "name": item.get("name"),
                "quantity": item.get("quantity"),
                "final_sale": item.get("final_sale", False)
            })

        # Apply Status Precedence & Stale Field Handling
        carrier = raw_order.get("carrier")
        tracking_number = raw_order.get("tracking_number")
        estimated_delivery = raw_order.get("estimated_delivery")
        customer_safe_message = raw_order.get("customer_safe_message")
        handoff_required = False
        handoff_reason = None

        if raw_status in ["cancelled", "returned"]:
            # Suppress stale carrier, tracking, and ETA metadata for cancelled/returned orders
            carrier = None
            tracking_number = None
            estimated_delivery = None
            if raw_status == "cancelled":
                customer_safe_message = "The order was cancelled and will not be shipped."

        elif raw_status == "exception":
            # Package damage / operational exception requires human handoff
            handoff_required = True
            handoff_reason = "Operational exception on order requires human support review"

        elif raw_status == "shipped" and not estimated_delivery:
            # Shipped without ETA (e.g. ORD-1011)
            estimated_delivery = None

        return SanitizedOrderResult(
            order_id=raw_order.get("order_id", norm_id),
            found=True,
            status=raw_status,
            membership_tier=raw_order.get("membership_tier"),
            items=safe_items,
            placed_at=raw_order.get("placed_at"),
            status_updated_at=raw_order.get("status_updated_at"),
            shipped_at=raw_order.get("shipped_at"),
            delivered_at=raw_order.get("delivered_at"),
            carrier=carrier,
            tracking_number=tracking_number,
            estimated_delivery=estimated_delivery,
            customer_safe_message=customer_safe_message,
            handoff_required=handoff_required,
            handoff_reason=handoff_reason,
            action_supported=True
        )


class OrderLookupTool:
    """Public lookup interface for order status queries."""

    def __init__(self, orders_file: str | Path = "data/orders.json"):
        self.repository = OrderRepository(orders_file)

    def lookup_order(self, order_id: str, action: str = "lookup") -> SanitizedOrderResult:
        """Looks up an order by ID and returns a customer-safe sanitized result."""
        raw_order = self.repository.get_raw_order(order_id)
        return OrderSanitizer.sanitize(raw_order, order_id, action=action)
