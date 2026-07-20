package quote

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRealHTTPQuoteOrderReturnsLegacyResult(t *testing.T) {
	server := httptest.NewServer(Handler())
	t.Cleanup(server.Close)

	response := postJSON(t, server.URL+"/quote-order", `{"unit_price_cents":1250,"quantity":2}`)
	if response.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.StatusCode)
	}
	assertJSON(t, response.Body, map[string]any{
		"receipt":     "Total: 25.00",
		"total_cents": float64(2500),
	})
}

func TestRealHTTPQuoteOrderRejectsZeroQuantity(t *testing.T) {
	server := httptest.NewServer(Handler())
	t.Cleanup(server.Close)

	response := postJSON(t, server.URL+"/quote-order", `{"unit_price_cents":1250,"quantity":0}`)
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.StatusCode)
	}
	assertJSON(t, response.Body, map[string]any{"error": "quantity must be positive"})
}

func TestLegacyBusinessFunctionsRetainStandaloneSemantics(t *testing.T) {
	total, err := QuoteOrder(1250, 2)
	if err != nil || total != 2500 {
		t.Fatalf("QuoteOrder(1250, 2) = (%d, %v)", total, err)
	}
	if _, err := QuoteOrder(-1, 2); err == nil || err.Error() != "unit price must not be negative" {
		t.Fatalf("negative price error = %v", err)
	}
	if _, err := QuoteOrder(1250, 0); err == nil || err.Error() != "quantity must be positive" {
		t.Fatalf("zero quantity error = %v", err)
	}
	if got := FormatReceipt(2500); got != "Total: 25.00" {
		t.Fatalf("FormatReceipt = %q", got)
	}
	if got := NormalizeCoupon(" save5 "); got != "SAVE5" {
		t.Fatalf("NormalizeCoupon = %q", got)
	}
	if got := LegacyDiscountHint(" save5 "); got == nil || *got != 5 {
		t.Fatalf("LegacyDiscountHint(save5) = %v", got)
	}
	if got := LegacyDiscountHint("unknown"); got != nil {
		t.Fatalf("LegacyDiscountHint(unknown) = %v", got)
	}
}

func postJSON(t *testing.T, url string, body string) *http.Response {
	t.Helper()
	response, err := http.Post(url, "application/json", bytes.NewBufferString(body))
	if err != nil {
		t.Fatal(err)
	}
	return response
}

func assertJSON(t *testing.T, body io.ReadCloser, expected map[string]any) {
	t.Helper()
	defer body.Close()
	var actual map[string]any
	if err := json.NewDecoder(body).Decode(&actual); err != nil {
		t.Fatal(err)
	}
	if len(actual) != len(expected) {
		t.Fatalf("JSON = %#v, want %#v", actual, expected)
	}
	for key, value := range expected {
		if actual[key] != value {
			t.Fatalf("JSON[%q] = %#v, want %#v", key, actual[key], value)
		}
	}
}
