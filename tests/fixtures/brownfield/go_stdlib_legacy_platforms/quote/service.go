package quote

import (
	"errors"
	"fmt"
)

func QuoteOrder(unitPriceCents int, quantity int) (int, error) {
	switch {
	case unitPriceCents < 0:
		return 0, errors.New("unit price must not be negative")
	case quantity <= 0:
		return 0, errors.New("quantity must be positive")
	default:
		return unitPriceCents * quantity, nil
	}
}

func FormatReceipt(totalCents int) string {
	return fmt.Sprintf(
		"Total: %d.%02d",
		totalCents/100,
		totalCents%100,
	)
}
