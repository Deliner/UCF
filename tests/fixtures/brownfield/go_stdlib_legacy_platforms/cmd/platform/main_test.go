package main

import (
	"bytes"
	"errors"
	"os"
	"os/exec"
	"strings"
	"testing"
)

func TestPlatformHelperProcess(t *testing.T) {
	if os.Getenv("UCF_PLATFORM_FIXTURE_HELPER") != "1" {
		return
	}
	separator := -1
	for index, argument := range os.Args {
		if argument == "--" {
			separator = index
			break
		}
	}
	if separator < 0 {
		os.Exit(97)
	}
	os.Exit(run(os.Args[separator+1:], os.Stdout, os.Stderr))
}

func TestCommandProcessesExposeCLIAndTemporallyDecoupledEvent(t *testing.T) {
	stdout, stderr, exitCode := runProcess(
		t,
		"quote",
		"--unit-price-cents",
		"1250",
		"--quantity",
		"2",
	)
	if exitCode != 0 || stderr != "" ||
		stdout != "{\"receipt\":\"Total: 25.00\",\"total_cents\":2500}\n" {
		t.Fatalf(
			"quote process = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}

	spoolRoot := t.TempDir()
	stdout, stderr, exitCode = runProcess(
		t,
		"event",
		"enqueue",
		"--spool",
		spoolRoot,
		"--event-id",
		"event-001",
		"--unit-price-cents",
		"1250",
		"--quantity",
		"2",
	)
	if exitCode != 0 || stderr != "" ||
		stdout != "{\"event_id\":\"event-001\",\"status\":\"enqueued\"}\n" {
		t.Fatalf(
			"enqueue process = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}

	stdout, stderr, exitCode = runProcess(
		t,
		"event",
		"observe",
		"--spool",
		spoolRoot,
		"--event-id",
		"event-001",
	)
	if exitCode != 3 || stdout != "" ||
		stderr != "observation unavailable\n" {
		t.Fatalf(
			"pre-dispatch observe = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}

	stdout, stderr, exitCode = runProcess(
		t,
		"event",
		"dispatch-once",
		"--spool",
		spoolRoot,
	)
	if exitCode != 0 || stderr != "" ||
		stdout != "{\"event_id\":\"event-001\",\"status\":\"dispatched\"}\n" {
		t.Fatalf(
			"dispatch process = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}

	stdout, stderr, exitCode = runProcess(
		t,
		"event",
		"observe",
		"--spool",
		spoolRoot,
		"--event-id",
		"event-001",
	)
	if exitCode != 0 || stderr != "" ||
		stdout != "{\"event_id\":\"event-001\",\"receipt\":\"Total: 25.00\",\"total_cents\":2500}\n" {
		t.Fatalf(
			"post-dispatch observe = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}
}

func TestCommandProcessesRejectInvalidAndDuplicateInput(t *testing.T) {
	stdout, stderr, exitCode := runProcess(
		t,
		"quote",
		"--unit-price-cents",
		"1250",
		"--quantity",
		"0",
	)
	if exitCode != 2 || stdout != "" || stderr != "invalid quote request\n" {
		t.Fatalf(
			"invalid quote = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}

	spoolRoot := t.TempDir()
	arguments := []string{
		"event",
		"enqueue",
		"--spool",
		spoolRoot,
		"--event-id",
		"event-001",
		"--unit-price-cents",
		"1250",
		"--quantity",
		"2",
	}
	if _, _, exitCode = runProcess(t, arguments...); exitCode != 0 {
		t.Fatalf("first enqueue exit = %d", exitCode)
	}
	stdout, stderr, exitCode = runProcess(t, arguments...)
	if exitCode != 2 || stdout != "" || stderr != "event enqueue failed\n" {
		t.Fatalf(
			"duplicate enqueue = stdout %q stderr %q exit %d",
			stdout,
			stderr,
			exitCode,
		)
	}
}

func runProcess(t *testing.T, arguments ...string) (string, string, int) {
	t.Helper()
	commandArguments := append(
		[]string{"-test.run=^TestPlatformHelperProcess$", "--"},
		arguments...,
	)
	command := exec.Command(os.Args[0], commandArguments...)
	command.Env = append(os.Environ(), "UCF_PLATFORM_FIXTURE_HELPER=1")
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr
	err := command.Run()
	exitCode := 0
	if err != nil {
		var exitError *exec.ExitError
		if !errors.As(err, &exitError) {
			t.Fatalf("process start error = %v", err)
		}
		exitCode = exitError.ExitCode()
	}
	return stdout.String(), normalizeTestStderr(stderr.String()), exitCode
}

func normalizeTestStderr(value string) string {
	lines := strings.Split(value, "\n")
	filtered := lines[:0]
	for _, line := range lines {
		if strings.HasPrefix(line, "--- FAIL: TestPlatformHelperProcess") ||
			strings.HasPrefix(line, "FAIL") {
			continue
		}
		filtered = append(filtered, line)
	}
	return strings.Join(filtered, "\n")
}
