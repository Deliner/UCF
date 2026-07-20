package quote

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
)

func QuoteOrder(unitPriceCents int, quantity int) (int, error) {
	if unitPriceCents < 0 {
		return 0, errors.New("unit price must not be negative")
	}
	if quantity <= 0 {
		return 0, errors.New("quantity must be positive")
	}
	return unitPriceCents * quantity, nil
}

func FormatReceipt(totalCents int) string {
	return fmt.Sprintf("Total: %d.%02d", totalCents/100, totalCents%100)
}

func NormalizeCoupon(code string) string {
	return strings.ToUpper(strings.TrimSpace(code))
}

func LegacyDiscountHint(code string) *int {
	if NormalizeCoupon(code) != "SAVE5" {
		return nil
	}
	value := 5
	return &value
}

type quoteOrderBody struct {
	UnitPriceCents *int `json:"unit_price_cents"`
	Quantity       *int `json:"quantity"`
}

func Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /quote-order", func(response http.ResponseWriter, request *http.Request) {
		decoder := json.NewDecoder(request.Body)
		decoder.DisallowUnknownFields()
		var body quoteOrderBody
		if err := decoder.Decode(&body); err != nil {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "invalid request"})
			return
		}
		if body.UnitPriceCents == nil {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "unit price must be an integer"})
			return
		}
		if body.Quantity == nil {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": "quantity must be an integer"})
			return
		}
		total, err := QuoteOrder(*body.UnitPriceCents, *body.Quantity)
		if err != nil {
			writeJSON(response, http.StatusBadRequest, map[string]any{"error": err.Error()})
			return
		}
		writeJSON(response, http.StatusOK, map[string]any{
			"receipt":     FormatReceipt(total),
			"total_cents": total,
		})
	})
	return mux
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("content-type", "application/json")
	response.WriteHeader(status)
	if err := json.NewEncoder(response).Encode(value); err != nil {
		panic(err)
	}
}
