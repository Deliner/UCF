package spool

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestEventRemainsUnobservedUntilIndependentDispatch(t *testing.T) {
	root := t.TempDir()
	request := Request{
		EventID:        "event-001",
		UnitPriceCents: 1250,
		Quantity:       2,
	}
	if err := Enqueue(root, request); err != nil {
		t.Fatalf("Enqueue() error = %v", err)
	}
	if _, err := Observe(root, request.EventID); !errors.Is(
		err,
		ErrObservationUnavailable,
	) {
		t.Fatalf("Observe() before dispatch error = %v", err)
	}
	observation, err := DispatchOne(root)
	if err != nil {
		t.Fatalf("DispatchOne() error = %v", err)
	}
	if observation.EventID != request.EventID ||
		observation.TotalCents != 2500 ||
		observation.Receipt != "Total: 25.00" {
		t.Fatalf("DispatchOne() observation = %#v", observation)
	}
	observed, err := Observe(root, request.EventID)
	if err != nil || observed != observation {
		t.Fatalf("Observe() = (%#v, %v)", observed, err)
	}
}

func TestEventSpoolRejectsDuplicatesInvalidIDsAndSymlinks(t *testing.T) {
	root := t.TempDir()
	request := Request{
		EventID:        "event-001",
		UnitPriceCents: 1250,
		Quantity:       2,
	}
	if err := Enqueue(root, request); err != nil {
		t.Fatalf("first Enqueue() error = %v", err)
	}
	if err := Enqueue(root, request); !errors.Is(err, ErrDuplicateEvent) {
		t.Fatalf("duplicate Enqueue() error = %v", err)
	}
	invalid := request
	invalid.EventID = "../escape"
	if err := Enqueue(root, invalid); !errors.Is(err, ErrInvalidEvent) {
		t.Fatalf("invalid ID Enqueue() error = %v", err)
	}

	symlinkRoot := filepath.Join(t.TempDir(), "spool-link")
	if err := os.Symlink(root, symlinkRoot); err != nil {
		t.Fatalf("Symlink() error = %v", err)
	}
	if err := Enqueue(symlinkRoot, Request{
		EventID:        "event-002",
		UnitPriceCents: 1250,
		Quantity:       2,
	}); !errors.Is(err, ErrUnsafeSpool) {
		t.Fatalf("symlink-root Enqueue() error = %v", err)
	}
}
