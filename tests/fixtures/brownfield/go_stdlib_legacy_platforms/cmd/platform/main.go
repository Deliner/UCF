package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"

	"example.com/legacyplatforms/quote"
	"example.com/legacyplatforms/spool"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(arguments []string, stdout io.Writer, stderr io.Writer) int {
	if len(arguments) == 0 {
		fmt.Fprintln(stderr, "invalid command")
		return 2
	}
	switch arguments[0] {
	case "quote":
		return runQuote(arguments[1:], stdout, stderr)
	case "event":
		return runEvent(arguments[1:], stdout, stderr)
	default:
		fmt.Fprintln(stderr, "invalid command")
		return 2
	}
}

func runQuote(arguments []string, stdout io.Writer, stderr io.Writer) int {
	flags := flag.NewFlagSet("quote", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	unitPriceCents := flags.Int("unit-price-cents", -1, "")
	quantity := flags.Int("quantity", 0, "")
	if flags.Parse(arguments) != nil || flags.NArg() != 0 {
		fmt.Fprintln(stderr, "invalid quote request")
		return 2
	}
	total, err := quote.QuoteOrder(*unitPriceCents, *quantity)
	if err != nil {
		fmt.Fprintln(stderr, "invalid quote request")
		return 2
	}
	result := struct {
		Receipt    string `json:"receipt"`
		TotalCents int    `json:"total_cents"`
	}{
		Receipt:    quote.FormatReceipt(total),
		TotalCents: total,
	}
	if json.NewEncoder(stdout).Encode(result) != nil {
		return 4
	}
	return 0
}

func runEvent(arguments []string, stdout io.Writer, stderr io.Writer) int {
	if len(arguments) == 0 {
		fmt.Fprintln(stderr, "invalid event command")
		return 2
	}
	switch arguments[0] {
	case "enqueue":
		return runEnqueue(arguments[1:], stdout, stderr)
	case "dispatch-once":
		return runDispatch(arguments[1:], stdout, stderr)
	case "observe":
		return runObserve(arguments[1:], stdout, stderr)
	default:
		fmt.Fprintln(stderr, "invalid event command")
		return 2
	}
}

func runEnqueue(
	arguments []string,
	stdout io.Writer,
	stderr io.Writer,
) int {
	flags := flag.NewFlagSet("event enqueue", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	root := flags.String("spool", "", "")
	eventID := flags.String("event-id", "", "")
	unitPriceCents := flags.Int("unit-price-cents", -1, "")
	quantity := flags.Int("quantity", 0, "")
	if flags.Parse(arguments) != nil || flags.NArg() != 0 {
		fmt.Fprintln(stderr, "event enqueue failed")
		return 2
	}
	err := spool.Enqueue(*root, spool.Request{
		EventID:        *eventID,
		UnitPriceCents: *unitPriceCents,
		Quantity:       *quantity,
	})
	if err != nil {
		fmt.Fprintln(stderr, "event enqueue failed")
		return eventErrorExit(err)
	}
	result := struct {
		EventID string `json:"event_id"`
		Status  string `json:"status"`
	}{
		EventID: *eventID,
		Status:  "enqueued",
	}
	if json.NewEncoder(stdout).Encode(result) != nil {
		return 4
	}
	return 0
}

func runDispatch(
	arguments []string,
	stdout io.Writer,
	stderr io.Writer,
) int {
	flags := flag.NewFlagSet("event dispatch-once", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	root := flags.String("spool", "", "")
	if flags.Parse(arguments) != nil || flags.NArg() != 0 {
		fmt.Fprintln(stderr, "event dispatch failed")
		return 2
	}
	observation, err := spool.DispatchOne(*root)
	if err != nil {
		if errors.Is(err, spool.ErrEventUnavailable) {
			fmt.Fprintln(stderr, "event dispatch unavailable")
		} else {
			fmt.Fprintln(stderr, "event dispatch failed")
		}
		return eventErrorExit(err)
	}
	result := struct {
		EventID string `json:"event_id"`
		Status  string `json:"status"`
	}{
		EventID: observation.EventID,
		Status:  "dispatched",
	}
	if json.NewEncoder(stdout).Encode(result) != nil {
		return 4
	}
	return 0
}

func runObserve(
	arguments []string,
	stdout io.Writer,
	stderr io.Writer,
) int {
	flags := flag.NewFlagSet("event observe", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	root := flags.String("spool", "", "")
	eventID := flags.String("event-id", "", "")
	if flags.Parse(arguments) != nil || flags.NArg() != 0 {
		fmt.Fprintln(stderr, "event observe failed")
		return 2
	}
	observation, err := spool.Observe(*root, *eventID)
	if err != nil {
		if errors.Is(err, spool.ErrObservationUnavailable) {
			fmt.Fprintln(stderr, "observation unavailable")
		} else {
			fmt.Fprintln(stderr, "event observe failed")
		}
		return eventErrorExit(err)
	}
	if json.NewEncoder(stdout).Encode(observation) != nil {
		return 4
	}
	return 0
}

func eventErrorExit(err error) int {
	switch {
	case errors.Is(err, spool.ErrEventUnavailable),
		errors.Is(err, spool.ErrObservationUnavailable):
		return 3
	case errors.Is(err, spool.ErrDuplicateEvent),
		errors.Is(err, spool.ErrInvalidEvent):
		return 2
	default:
		return 4
	}
}
