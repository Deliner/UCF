"""Business functions retained from the legacy quote service."""


def quote_order(unit_price_cents: int, quantity: int) -> int:
    """Return the order total in cents."""
    if unit_price_cents < 0:
        raise ValueError("unit price must not be negative")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    return unit_price_cents * quantity


def format_receipt(total_cents: int) -> str:
    """Render a receipt total."""
    return f"Total: {total_cents / 100:.2f}"


def normalize_coupon(code: str) -> str:
    """Normalize a coupon token for internal lookup."""
    return code.strip().upper()


def legacy_discount_hint(code: str) -> int | None:
    """Return a historical discount hint when one is known."""
    return {"SAVE5": 5}.get(normalize_coupon(code))
