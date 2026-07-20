package quote

import "testing"

func TestQuoteOrderReturnsTheLegacyTotal(t *testing.T) {
	total, err := QuoteOrder(1250, 2)
	if err != nil || total != 2500 {
		t.Fatalf("QuoteOrder(1250, 2) = (%d, %v)", total, err)
	}
	if receipt := FormatReceipt(total); receipt != "Total: 25.00" {
		t.Fatalf("FormatReceipt(2500) = %q", receipt)
	}
}

func TestQuoteOrderRejectsInvalidValues(t *testing.T) {
	if _, err := QuoteOrder(-1, 2); err == nil ||
		err.Error() != "unit price must not be negative" {
		t.Fatalf("negative unit price error = %v", err)
	}
	if _, err := QuoteOrder(1250, 0); err == nil ||
		err.Error() != "quantity must be positive" {
		t.Fatalf("zero quantity error = %v", err)
	}
}
