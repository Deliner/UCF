"""Executable inputs for the complete-purchase generated tests."""

import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    return {
        "cart_id": "test-cart",
        "payment_method_id": "test-card",
        "shipping_address_id": "test-address",
    }
