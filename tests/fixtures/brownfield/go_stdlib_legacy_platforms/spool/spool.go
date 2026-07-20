package spool

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"example.com/legacyplatforms/quote"
)

const maxEnvelopeBytes = 4096

var (
	ErrDuplicateEvent         = errors.New("event already exists")
	ErrEventUnavailable       = errors.New("event unavailable")
	ErrInvalidEvent           = errors.New("invalid event")
	ErrObservationUnavailable = errors.New("observation unavailable")
	ErrUnsafeSpool            = errors.New("unsafe spool")
	eventIDPattern            = regexp.MustCompile(
		`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`,
	)
)

type Request struct {
	EventID        string `json:"event_id"`
	Quantity       int    `json:"quantity"`
	UnitPriceCents int    `json:"unit_price_cents"`
}

type Observation struct {
	EventID    string `json:"event_id"`
	Receipt    string `json:"receipt"`
	TotalCents int    `json:"total_cents"`
}

type layout struct {
	pending    string
	processing string
	observed   string
}

func Enqueue(root string, request Request) error {
	if err := validateRequest(request); err != nil {
		return err
	}
	directories, err := prepareLayout(root)
	if err != nil {
		return err
	}
	for _, directory := range []string{
		directories.pending,
		directories.processing,
		directories.observed,
	} {
		path := filepath.Join(directory, request.EventID+".json")
		if _, err := os.Lstat(path); err == nil {
			return ErrDuplicateEvent
		} else if !errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("%w: event state is unreadable", ErrUnsafeSpool)
		}
	}
	return writeExclusive(
		filepath.Join(directories.pending, request.EventID+".json"),
		request,
	)
}

func DispatchOne(root string) (Observation, error) {
	directories, err := prepareLayout(root)
	if err != nil {
		return Observation{}, err
	}
	entries, err := os.ReadDir(directories.pending)
	if err != nil {
		return Observation{}, fmt.Errorf("%w: pending directory", ErrUnsafeSpool)
	}
	if len(entries) == 0 {
		return Observation{}, ErrEventUnavailable
	}
	entry := entries[0]
	if entry.IsDir() || entry.Type()&os.ModeSymlink != 0 ||
		!strings.HasSuffix(entry.Name(), ".json") {
		return Observation{}, fmt.Errorf("%w: pending entry", ErrUnsafeSpool)
	}
	eventID := strings.TrimSuffix(entry.Name(), ".json")
	if !validEventID(eventID) {
		return Observation{}, fmt.Errorf("%w: pending event ID", ErrUnsafeSpool)
	}
	pendingPath := filepath.Join(directories.pending, entry.Name())
	processingPath := filepath.Join(directories.processing, entry.Name())
	if _, err := os.Lstat(processingPath); err == nil {
		return Observation{}, ErrDuplicateEvent
	} else if !errors.Is(err, os.ErrNotExist) {
		return Observation{}, fmt.Errorf("%w: processing state", ErrUnsafeSpool)
	}
	if err := os.Rename(pendingPath, processingPath); err != nil {
		return Observation{}, fmt.Errorf("%w: claim event", ErrUnsafeSpool)
	}

	var request Request
	if err := readEnvelope(processingPath, &request); err != nil {
		return Observation{}, err
	}
	if request.EventID != eventID {
		return Observation{}, fmt.Errorf("%w: event identity", ErrInvalidEvent)
	}
	if err := validateRequest(request); err != nil {
		return Observation{}, err
	}
	total, err := quote.QuoteOrder(request.UnitPriceCents, request.Quantity)
	if err != nil {
		return Observation{}, fmt.Errorf("%w: quote values", ErrInvalidEvent)
	}
	observation := Observation{
		EventID:    request.EventID,
		Receipt:    quote.FormatReceipt(total),
		TotalCents: total,
	}
	observedPath := filepath.Join(directories.observed, entry.Name())
	if err := writeExclusive(observedPath, observation); err != nil {
		return Observation{}, err
	}
	if err := os.Remove(processingPath); err != nil {
		return Observation{}, fmt.Errorf("%w: complete event", ErrUnsafeSpool)
	}
	return observation, nil
}

func Observe(root string, eventID string) (Observation, error) {
	if !validEventID(eventID) {
		return Observation{}, ErrInvalidEvent
	}
	directories, err := prepareLayout(root)
	if err != nil {
		return Observation{}, err
	}
	var observation Observation
	path := filepath.Join(directories.observed, eventID+".json")
	if err := readEnvelope(path, &observation); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return Observation{}, ErrObservationUnavailable
		}
		return Observation{}, err
	}
	if observation.EventID != eventID {
		return Observation{}, fmt.Errorf(
			"%w: observation identity",
			ErrInvalidEvent,
		)
	}
	return observation, nil
}

func validateRequest(request Request) error {
	if !validEventID(request.EventID) {
		return fmt.Errorf("%w: event ID", ErrInvalidEvent)
	}
	if _, err := quote.QuoteOrder(
		request.UnitPriceCents,
		request.Quantity,
	); err != nil {
		return fmt.Errorf("%w: quote values", ErrInvalidEvent)
	}
	return nil
}

func validEventID(value string) bool {
	return len(value) <= 64 && eventIDPattern.MatchString(value)
}

func prepareLayout(root string) (layout, error) {
	if !filepath.IsAbs(root) || filepath.Clean(root) != root {
		return layout{}, fmt.Errorf("%w: root path", ErrUnsafeSpool)
	}
	info, err := os.Lstat(root)
	switch {
	case errors.Is(err, os.ErrNotExist):
		if err := os.Mkdir(root, 0o700); err != nil {
			return layout{}, fmt.Errorf("%w: create root", ErrUnsafeSpool)
		}
	case err != nil:
		return layout{}, fmt.Errorf("%w: inspect root", ErrUnsafeSpool)
	case info.Mode()&os.ModeSymlink != 0 || !info.IsDir():
		return layout{}, fmt.Errorf("%w: root type", ErrUnsafeSpool)
	}
	directories := layout{
		pending:    filepath.Join(root, "pending"),
		processing: filepath.Join(root, "processing"),
		observed:   filepath.Join(root, "observed"),
	}
	for _, path := range []string{
		directories.pending,
		directories.processing,
		directories.observed,
	} {
		info, err := os.Lstat(path)
		switch {
		case errors.Is(err, os.ErrNotExist):
			if err := os.Mkdir(path, 0o700); err != nil {
				return layout{}, fmt.Errorf(
					"%w: create state directory",
					ErrUnsafeSpool,
				)
			}
		case err != nil:
			return layout{}, fmt.Errorf(
				"%w: inspect state directory",
				ErrUnsafeSpool,
			)
		case info.Mode()&os.ModeSymlink != 0 || !info.IsDir():
			return layout{}, fmt.Errorf(
				"%w: state directory type",
				ErrUnsafeSpool,
			)
		}
	}
	return directories, nil
}

func writeExclusive(path string, value any) error {
	payload, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("%w: encode envelope", ErrInvalidEvent)
	}
	payload = append(payload, '\n')
	if len(payload) > maxEnvelopeBytes {
		return fmt.Errorf("%w: envelope size", ErrInvalidEvent)
	}
	directory := filepath.Dir(path)
	temporary, err := os.CreateTemp(directory, ".event-*.tmp")
	if err != nil {
		return fmt.Errorf("%w: create envelope", ErrUnsafeSpool)
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)
	if err := temporary.Chmod(0o600); err != nil {
		temporary.Close()
		return fmt.Errorf("%w: envelope mode", ErrUnsafeSpool)
	}
	if _, err := temporary.Write(payload); err != nil {
		temporary.Close()
		return fmt.Errorf("%w: write envelope", ErrUnsafeSpool)
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return fmt.Errorf("%w: sync envelope", ErrUnsafeSpool)
	}
	if err := temporary.Close(); err != nil {
		return fmt.Errorf("%w: close envelope", ErrUnsafeSpool)
	}
	if err := os.Link(temporaryPath, path); err != nil {
		if errors.Is(err, os.ErrExist) {
			return ErrDuplicateEvent
		}
		return fmt.Errorf("%w: publish envelope", ErrUnsafeSpool)
	}
	return nil
}

func readEnvelope(path string, destination any) error {
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() ||
		info.Size() > maxEnvelopeBytes {
		return fmt.Errorf("%w: envelope type or size", ErrUnsafeSpool)
	}
	payload, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("%w: read envelope", ErrUnsafeSpool)
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(destination); err != nil {
		return fmt.Errorf("%w: decode envelope", ErrInvalidEvent)
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return fmt.Errorf("%w: trailing envelope data", ErrInvalidEvent)
	}
	return nil
}
