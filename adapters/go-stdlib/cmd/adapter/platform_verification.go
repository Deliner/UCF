package main

import (
	"bytes"
	"context"
	"errors"
	"os"
	"os/exec"
	"strconv"
	"syscall"
	"time"
)

type boundedOutputWriter struct {
	payload  []byte
	overflow bool
}

func (writer *boundedOutputWriter) Write(payload []byte) (int, error) {
	accepted := len(payload)
	remaining := maxVerificationOutputBytes - len(writer.payload)
	if remaining <= 0 {
		writer.overflow = true
		return accepted, nil
	}
	if len(payload) > remaining {
		writer.payload = append(writer.payload, payload[:remaining]...)
		writer.overflow = true
		return accepted, nil
	}
	writer.payload = append(writer.payload, payload...)
	return accepted, nil
}

type shortProcessResult struct {
	stdout   []byte
	stderr   []byte
	exitCode int
}

func executeCLIQuoteOrderCheck(
	parent context.Context,
	executable string,
	values verificationValues,
) (string, error) {
	result, err := runShortVerificationProcess(
		parent,
		executable,
		[]string{
			"quote",
			"--unit-price-cents",
			strconv.Itoa(values.unitPriceCents),
			"--quantity",
			strconv.Itoa(values.quantity),
		},
	)
	if err != nil {
		return "error", err
	}
	expected := []byte(
		`{"receipt":"Total: 25.00","total_cents":` +
			strconv.Itoa(values.expectedTotalCents) +
			"}\n",
	)
	if result.exitCode != 0 ||
		len(result.stderr) != 0 ||
		!bytes.Equal(result.stdout, expected) {
		return "failed", nil
	}
	return "passed", nil
}

func executeEventQuoteOrderCheck(
	parent context.Context,
	executable string,
	values verificationValues,
) (string, error) {
	return executeEventQuoteOrderCheckWithin(
		parent,
		executable,
		values,
		verificationDeadline,
	)
}

func executeEventQuoteOrderCheckWithin(
	parent context.Context,
	executable string,
	values verificationValues,
	deadline time.Duration,
) (string, error) {
	return executeEventQuoteOrderCheckWithinWithCleanup(
		parent,
		executable,
		values,
		deadline,
		os.RemoveAll,
	)
}

func executeEventQuoteOrderCheckWithinWithCleanup(
	parent context.Context,
	executable string,
	values verificationValues,
	deadline time.Duration,
	removeAll func(string) error,
) (outcome string, outcomeErr error) {
	if deadline <= 0 {
		return "error", errors.New(
			"event verification deadline is invalid",
		)
	}
	contextValue, cancel := context.WithTimeout(parent, deadline)
	defer cancel()
	spoolRoot, err := os.MkdirTemp("", "ucf-go-platform-spool-")
	if err != nil {
		return "error", err
	}
	defer func() {
		if cleanupErr := removeAll(spoolRoot); cleanupErr != nil {
			outcome = "error"
			outcomeErr = errors.Join(
				outcomeErr,
				errVerificationCleanup,
				errors.New("event spool cleanup failed"),
				cleanupErr,
			)
		}
	}()

	eventID := "quote-order-001"
	steps := []struct {
		arguments []string
		exitCode  int
		stdout    string
		stderr    string
	}{
		{
			arguments: []string{
				"event",
				"enqueue",
				"--spool",
				spoolRoot,
				"--event-id",
				eventID,
				"--unit-price-cents",
				strconv.Itoa(values.unitPriceCents),
				"--quantity",
				strconv.Itoa(values.quantity),
			},
			exitCode: 0,
			stdout:   `{"event_id":"quote-order-001","status":"enqueued"}` + "\n",
		},
		{
			arguments: []string{
				"event",
				"observe",
				"--spool",
				spoolRoot,
				"--event-id",
				eventID,
			},
			exitCode: 3,
			stderr:   "observation unavailable\n",
		},
		{
			arguments: []string{
				"event",
				"dispatch-once",
				"--spool",
				spoolRoot,
			},
			exitCode: 0,
			stdout:   `{"event_id":"quote-order-001","status":"dispatched"}` + "\n",
		},
		{
			arguments: []string{
				"event",
				"observe",
				"--spool",
				spoolRoot,
				"--event-id",
				eventID,
			},
			exitCode: 0,
			stdout: `{"event_id":"quote-order-001","receipt":"Total: 25.00",` +
				`"total_cents":` +
				strconv.Itoa(values.expectedTotalCents) +
				"}\n",
		},
	}
	for _, step := range steps {
		result, executionErr := runShortVerificationProcess(
			contextValue,
			executable,
			step.arguments,
		)
		if executionErr != nil {
			return "error", executionErr
		}
		if result.exitCode != step.exitCode ||
			!bytes.Equal(result.stdout, []byte(step.stdout)) ||
			!bytes.Equal(result.stderr, []byte(step.stderr)) {
			return "failed", nil
		}
	}
	return "passed", nil
}

func runShortVerificationProcess(
	parent context.Context,
	executable string,
	arguments []string,
) (shortProcessResult, error) {
	contextValue, cancel := context.WithTimeout(
		parent,
		verificationPhaseDeadline,
	)
	defer cancel()
	if err := contextValue.Err(); err != nil {
		return shortProcessResult{}, err
	}
	command := exec.Command(executable, arguments...)
	command.Env = []string{}
	command.SysProcAttr = &syscall.SysProcAttr{
		Setpgid:   true,
		Pdeathsig: syscall.SIGKILL,
	}
	stdout := &boundedOutputWriter{}
	stderr := &boundedOutputWriter{}
	command.Stdout = stdout
	command.Stderr = stderr
	owner, err := startVerificationProcess(command)
	if err != nil {
		return shortProcessResult{}, err
	}
	waited := make(chan error, 1)
	go func() {
		waited <- command.Wait()
	}()

	var waitErr error
	select {
	case waitErr = <-waited:
		completed := make(chan error, 1)
		completed <- waitErr
		cleanupErr := stopOwnedVerificationProcess(
			command,
			completed,
			owner,
		)
		if errors.Is(cleanupErr, errVerificationCleanup) {
			return shortProcessResult{}, cleanupErr
		}
	case <-contextValue.Done():
		cleanupErr := stopOwnedVerificationProcess(
			command,
			waited,
			owner,
		)
		if errors.Is(cleanupErr, errVerificationCleanup) {
			return shortProcessResult{}, cleanupErr
		}
		return shortProcessResult{}, contextValue.Err()
	}
	if stdout.overflow || stderr.overflow {
		return shortProcessResult{}, errors.New(
			"verification process output exceeds the byte limit",
		)
	}
	exitCode := 0
	if waitErr != nil {
		exitError, ok := waitErr.(*exec.ExitError)
		if !ok {
			return shortProcessResult{}, waitErr
		}
		exitCode = exitError.ExitCode()
		if exitCode < 0 {
			return shortProcessResult{}, waitErr
		}
	}
	return shortProcessResult{
		stdout:   bytes.Clone(stdout.payload),
		stderr:   bytes.Clone(stderr.payload),
		exitCode: exitCode,
	}, nil
}
