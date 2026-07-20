"""Implementation for use case: complete-purchase.

@implements("use-cases/complete-purchase")
@implements("actions/finalize-order")
@implements("actions/send-order-confirmation")
@implements("actions/send-payment-failure-notification")
@implements("actions/send-stock-unavailable-notification")
@implements("actions/send-timeout-notification")
"""

from __future__ import annotations

from typing import Any

import pytest

from .interface import (
    CompletePurchaseInterface,
    ConfirmToCustomerResult,
    FinalizeOrderResult,
)


class EcommerceService:
    """E-commerce business logic (hides DB, payment gateway, email service)."""

    def __init__(self) -> None:
        self._orders = {}
        self._inventory = {
            "product-1": 100,
            "product-2": 50,
        }
        self._carts = {}

    def create_cart(self, cart_id: str, items: list[dict]) -> None:
        """Create shopping cart with items."""
        self._carts[cart_id] = {
            "items": items,
            "user_id": "test-user",
        }

    def finalize_order(
        self,
        cart_id: str,
        payment_method_id: str,
        shipping_address_id: str,
    ) -> dict[str, Any]:
        """Finalize order: validate, reserve inventory, charge payment, create order."""
        # 1. Validate cart
        if cart_id not in self._carts:
            raise ValueError("INVALID_CART")

        cart = self._carts[cart_id]

        # 2. Check inventory
        for item in cart["items"]:
            product_id = item["product_id"]
            quantity = item["quantity"]
            if self._inventory.get(product_id, 0) < quantity:
                raise ValueError("ITEM_OUT_OF_STOCK")

        # 3. Calculate total (tax + shipping hidden here!)
        subtotal = sum(item["price"] * item["quantity"] for item in cart["items"])
        tax = subtotal * 0.08  # 8% tax
        shipping = 9.99
        total = subtotal + tax + shipping

        # 4. Reserve inventory
        for item in cart["items"]:
            product_id = item["product_id"]
            quantity = item["quantity"]
            self._inventory[product_id] -= quantity

        # 5. Charge payment (simulated)
        if payment_method_id == "declined-card":
            raise ValueError("PAYMENT_DECLINED")

        # 6. Create order
        order_id = f"ORD-{len(self._orders) + 1}"
        self._orders[order_id] = {
            "order_id": order_id,
            "cart_id": cart_id,
            "user_id": cart["user_id"],
            "items": cart["items"],
            "total": total,
            "status": "charged",
            "payment_method_id": payment_method_id,
            "shipping_address_id": shipping_address_id,
        }

        return {
            "id": order_id,
            "total": total,
            "status": "charged",
        }

    def send_confirmation(self, order_id: str, total_amount: float) -> bool:
        """Send order confirmation email."""
        if order_id not in self._orders:
            raise ValueError("INVALID_ORDER")
        # Simulate email sending
        return True


class CompletePurchaseImpl(CompletePurchaseInterface):
    """Implementation for complete-purchase use case."""

    def __init__(self) -> None:
        self.service = EcommerceService()
        self._order_id = None
        self._total = None
        self._email_sent = False
        self._initial_inventory = dict(self.service._inventory)
        self._notifications: list[dict[str, Any]] = []

    # ── Actions ──

    def action_finalize_order(
        self,
        cart_id: Any,
        payment_method_id: Any,
        shipping_address_id: Any,
    ) -> FinalizeOrderResult:
        """Finalize order (hides: validate, calculate, reserve, charge)."""
        result = self.service.finalize_order(
            cart_id,
            payment_method_id,
            shipping_address_id,
        )

        self._order_id = result["id"]
        self._total = result["total"]

        return FinalizeOrderResult(
            order_id=result["id"],
            total_amount=result["total"],
            payment_status=result["status"],
        )

    def action_confirm_to_customer(
        self, order_id: Any, total_amount: Any
    ) -> ConfirmToCustomerResult:
        """Send confirmation email."""
        sent = self.service.send_confirmation(order_id, total_amount)
        self._email_sent = sent
        return ConfirmToCustomerResult(sent=sent)

    def action_notify_payment_failure(self, cart_id: Any, reason: Any) -> None:
        """Notify customer of payment failure."""
        self._notifications.append(
            {
                "kind": "payment-failure",
                "cart_id": cart_id,
                "reason": reason,
            }
        )

    def action_notify_stock_issue(self, cart_id: Any) -> None:
        """Notify customer of stock issue."""
        self._notifications.append({"kind": "stock-issue", "cart_id": cart_id})

    def action_notify_timeout(self, cart_id: Any) -> None:
        """Notify customer of timeout."""
        self._notifications.append({"kind": "timeout", "cart_id": cart_id})

    def action_notify_cart_issue(self, cart_id: Any, reason: Any) -> None:
        """Notify customer of cart issue."""
        self._notifications.append(
            {
                "kind": "cart-issue",
                "cart_id": cart_id,
                "reason": reason,
            }
        )

    def action_notify_address_issue(self, shipping_address_id: Any) -> None:
        """Notify customer of address issue."""
        self._notifications.append(
            {
                "kind": "address-issue",
                "shipping_address_id": shipping_address_id,
            }
        )

    # ── Verifications ──

    def verify_order_is_placed_and_confirmed(self) -> None:
        """Verify order exists."""
        assert self._order_id is not None, "No order was created"
        assert self._order_id.startswith("ORD-"), "Invalid order ID format"

    def verify_payment_is_processed_successfully(self) -> None:
        """Verify payment went through."""
        assert self._order_id in self.service._orders, "Order not found"
        order = self.service._orders[self._order_id]
        assert order["status"] == "charged", (
            f"Expected 'charged', got {order['status']}"
        )

    def verify_customer_receives_order_confirmation_email(self) -> None:
        """Verify email was sent."""
        assert self._email_sent is True, "Confirmation email not sent"

    def verify_inventory_is_reserved_for_order_items(self) -> None:
        """Verify inventory was decremented."""
        assert self._order_id is not None
        for item in self.service._orders[self._order_id]["items"]:
            product_id = item["product_id"]
            assert self.service._inventory[product_id] == (
                self._initial_inventory[product_id] - item["quantity"]
            )

    def verify_customer_can_view_order_in_order_history(self) -> None:
        """Verify order is queryable."""
        assert self._order_id is not None
        assert self._order_id in self.service._orders
        order = self.service._orders[self._order_id]
        assert "items" in order, "Order missing items"

    def verify_required_inputs_validated(self) -> None:
        """Verify framework enforces required inputs."""
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def complete_purchase_impl() -> CompletePurchaseImpl:
    impl = CompletePurchaseImpl()

    # Pre-populate test cart
    impl.service.create_cart(
        cart_id="test-cart",
        items=[
            {"product_id": "product-1", "price": 29.99, "quantity": 2},
            {"product_id": "product-2", "price": 15.50, "quantity": 1},
        ],
    )

    return impl
