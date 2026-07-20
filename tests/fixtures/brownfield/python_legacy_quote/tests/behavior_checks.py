"""Dependency-free native checks for the legacy quote service."""

from legacy_quote.service import format_receipt, quote_order


def test_quote_order() -> None:
    assert quote_order(1250, 2) == 2500


def test_invalid_quantity() -> None:
    try:
        quote_order(1250, 0)
    except ValueError as error:
        assert str(error) == "quantity must be positive"
    else:
        raise AssertionError("zero quantity must be rejected")


def test_receipt_format() -> None:
    assert format_receipt(2500) == "Total: 25.00"


if __name__ == "__main__":
    test_quote_order()
    test_invalid_quantity()
    test_receipt_format()
    print("3 native behavior checks passed")
