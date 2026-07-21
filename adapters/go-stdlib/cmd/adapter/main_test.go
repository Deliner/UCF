package main

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"
)

func TestWriteReplacesOversizedResponseWithBoundedError(t *testing.T) {
	var output bytes.Buffer
	instance := &server{writer: bufio.NewWriter(&output)}
	instance.write(map[string]any{
		"jsonrpc": "2.0",
		"id":      "large-result",
		"result": map[string]any{
			"kind":  "inventory_result",
			"value": string(bytes.Repeat([]byte{'x'}, maxFrameBytes)),
		},
	})

	frame := output.Bytes()
	if len(frame) > maxFrameBytes {
		t.Fatalf("response frame has %d bytes, limit is %d", len(frame), maxFrameBytes)
	}
	if len(frame) == 0 || frame[len(frame)-1] != '\n' {
		t.Fatal("response frame is not LF terminated")
	}
	decoded, err := parseStrictJSON(frame[:len(frame)-1])
	if err != nil {
		t.Fatal(err)
	}
	response := decoded.(map[string]any)
	if response["id"] != "large-result" {
		t.Fatalf("response id = %#v", response["id"])
	}
	errorValue, ok := response["error"].(map[string]any)
	if !ok {
		t.Fatalf("response has no error: %#v", response)
	}
	data := errorValue["data"].(map[string]any)
	if data["category"] != "adapter_failure" ||
		data["ucf_code"] != "operation_failed" {
		t.Fatalf("response error data = %#v", data)
	}
}

func TestConcurrentWritesRemainWholeCanonicalFrames(t *testing.T) {
	var output bytes.Buffer
	instance := &server{writer: bufio.NewWriter(&output)}
	const frames = 32
	var group sync.WaitGroup
	group.Add(frames)
	for index := 0; index < frames; index++ {
		go func(value int) {
			defer group.Done()
			instance.writeError(
				"request-"+strconv.Itoa(value),
				"invalid_params",
				"concurrent test response",
			)
		}(index)
	}
	group.Wait()

	lines := bytes.Split(output.Bytes(), []byte{'\n'})
	if len(lines) != frames+1 || len(lines[len(lines)-1]) != 0 {
		t.Fatalf("output has %d line parts", len(lines))
	}
	identities := map[string]bool{}
	for _, line := range lines[:frames] {
		decoded, err := parseStrictJSON(line)
		if err != nil {
			t.Fatal(err)
		}
		response := decoded.(map[string]any)
		identifier, ok := response["id"].(string)
		if !ok || identities[identifier] {
			t.Fatalf("invalid response identity: %#v", response["id"])
		}
		identities[identifier] = true
	}
	if len(identities) != frames {
		t.Fatalf("received %d unique frames", len(identities))
	}
}

func TestFailedInitializeDoesNotLeakCapabilitiesIntoRetry(t *testing.T) {
	var output bytes.Buffer
	instance := &server{
		writer:               bufio.NewWriter(&output),
		lifecycle:            "new",
		selectedCapabilities: map[string]bool{},
	}
	request := func(name string) map[string]any {
		return map[string]any{
			"kind":            "capability_request",
			"name":            name,
			"minimum_version": "1.0.0",
			"required":        true,
		}
	}
	parameters := func(capabilities ...any) map[string]any {
		return map[string]any{
			"kind":             "initialize_request",
			"protocol_version": protocolVersion,
			"client": map[string]any{
				"kind":    "producer",
				"name":    "org.ucf.test.client",
				"version": "1.0.0",
			},
			"capabilities": capabilities,
		}
	}

	instance.initialize(
		"failed",
		parameters(
			request("org.ucf.adapter.inventory"),
			request("org.ucf.unsupported.required"),
		),
	)
	if len(instance.selectedCapabilities) != 0 {
		t.Fatalf(
			"failed initialize leaked capabilities: %#v",
			instance.selectedCapabilities,
		)
	}
	if instance.lifecycle != "new" {
		t.Fatalf("failed initialize lifecycle = %q", instance.lifecycle)
	}

	instance.initialize(
		"retry",
		parameters(request("org.ucf.adapter.discovery")),
	)
	if instance.lifecycle != "ready" ||
		len(instance.selectedCapabilities) != 1 ||
		!instance.selectedCapabilities["org.ucf.adapter.discovery"] {
		t.Fatalf(
			"retry capabilities = %#v, lifecycle = %q",
			instance.selectedCapabilities,
			instance.lifecycle,
		)
	}
}

func TestHTTPVerificationProcedureRequiresLoopbackCapability(t *testing.T) {
	procedure := httpVerificationProcedure()
	if procedure.requiredCapability != httpLoopbackCapabilityName {
		t.Fatalf(
			"HTTP verification capability = %q",
			procedure.requiredCapability,
		)
	}
}

func TestVerificationCleanupFailureRejectsEvidenceAndOutranksCancellation(
	t *testing.T,
) {
	cancelled, cancel := context.WithCancel(context.Background())
	cancel()
	for _, contextValue := range []context.Context{
		context.Background(),
		cancelled,
	} {
		outcome, handled := verificationFailureOutcome(
			contextValue,
			errors.Join(
				errVerificationCleanup,
				errors.New("forced cleanup failure"),
			),
		)
		if !handled {
			t.Fatal("cleanup failure was not handled")
		}
		if outcome.code != "operation_failed" ||
			outcome.result != nil ||
			!outcome.cancellationCleanupFailed {
			t.Fatalf("cleanup failure outcome = %#v", outcome)
		}
	}
}

func TestExecutableSnapshotCleanupClassifiesFailure(t *testing.T) {
	snapshot := &verificationExecutableSnapshot{
		root: string([]byte{0}),
	}

	err := snapshot.cleanup()

	if !errors.Is(err, errVerificationCleanup) {
		t.Fatalf("snapshot cleanup error = %v", err)
	}
}

func TestSnapshotPreparationPreservesCleanupFailure(t *testing.T) {
	executable := t.TempDir() + "/unsupported-fixture"
	if err := os.WriteFile(
		executable,
		[]byte("#!/bin/sh\nexit 0\n"),
		0700,
	); err != nil {
		t.Fatal(err)
	}
	forced := errors.New("forced preparation cleanup failure")

	snapshot, err := prepareVerificationExecutableSnapshotWithCleanup(
		executable,
		httpVerificationProcedure(),
		func(snapshot *verificationExecutableSnapshot) error {
			return errors.Join(
				snapshot.cleanup(),
				errVerificationCleanup,
				forced,
			)
		},
	)

	if snapshot != nil ||
		!errors.Is(err, errVerificationCleanup) ||
		!errors.Is(err, forced) {
		t.Fatalf("snapshot preparation result = %#v, %v", snapshot, err)
	}
}

func TestIncompleteSnapshotCleanupPreservesOriginalAndCleanupFailures(
	t *testing.T,
) {
	original := errors.New("forced snapshot copy failure")
	snapshot := &verificationExecutableSnapshot{
		root: string([]byte{0}),
	}

	err := cleanupIncompleteVerificationExecutableSnapshot(
		snapshot,
		original,
	)

	if !errors.Is(err, original) ||
		!errors.Is(err, errVerificationCleanup) {
		t.Fatalf("incomplete snapshot cleanup error = %v", err)
	}
}

func TestProcIdentityRaceTreatsESRCHAsDisappeared(t *testing.T) {
	for _, err := range []error{
		os.ErrNotExist,
		&os.PathError{
			Op:   "read",
			Path: "/proc/123/stat",
			Err:  syscall.ESRCH,
		},
	} {
		if !verificationProcessDisappeared(err) {
			t.Fatalf("process disappearance error = %v", err)
		}
	}
}

func TestReadReadinessLineStopsAtBound(t *testing.T) {
	source := &countingNoNewlineReader{
		remaining: maxVerificationOutputBytes * 8,
	}
	reader := bufio.NewReaderSize(source, 4096)

	result := readReadinessLine(reader)

	if !result.overflow {
		t.Fatal("oversized readiness input was not rejected")
	}
	if len(result.payload) > maxVerificationOutputBytes {
		t.Fatalf(
			"readiness retained %d bytes, limit is %d",
			len(result.payload),
			maxVerificationOutputBytes,
		)
	}
	if source.consumed > maxVerificationOutputBytes+reader.Size() {
		t.Fatalf(
			"readiness consumed %d bytes before applying the limit",
			source.consumed,
		)
	}
}

func TestReadinessPrefetchRemainsTrailingOutput(t *testing.T) {
	reader := bufio.NewReaderSize(
		strings.NewReader(
			"READY http://127.0.0.1:12345\nforbidden trailing output",
		),
		4096,
	)

	readiness := readReadinessLine(reader)
	if address, ok := verificationAddress(readiness); !ok ||
		address != "127.0.0.1:12345" {
		t.Fatalf("readiness result = %#v, %q", readiness, address)
	}
	trailing := readBoundedStream(reader)
	if trailing.err != nil ||
		trailing.overflow ||
		string(trailing.payload) != "forbidden trailing output" {
		t.Fatalf("trailing output = %#v", trailing)
	}
}

func TestHTTPVerificationOwnsOutputReadersUntilDescendantsClose(t *testing.T) {
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	server := &http.Server{
		Handler: http.HandlerFunc(
			func(response http.ResponseWriter, request *http.Request) {
				response.Header().Set("content-type", "application/json")
				_, _ = io.WriteString(
					response,
					`{"receipt":"Total: 25.00","total_cents":2500}`,
				)
			},
		),
	}
	served := make(chan error, 1)
	go func() {
		served <- server.Serve(listener)
	}()
	t.Cleanup(func() {
		if err := server.Close(); err != nil {
			t.Error(err)
		}
		if err := <-served; !errors.Is(err, http.ErrServerClosed) {
			t.Errorf("verification HTTP server result = %v", err)
		}
	})

	root := t.TempDir()
	blockingPath := root + "/blocking.fifo"
	if err := syscall.Mkfifo(blockingPath, 0600); err != nil {
		t.Fatal(err)
	}
	scriptPath := root + "/verification-helper"
	script := `#!/bin/sh
blocking_fifo="${0%/*}/blocking.fifo"
(
    trap '' HUP
    exec /bin/cat "$blocking_fifo"
) >/dev/null &
printf 'READY http://%s\n' '` + listener.Addr().String() + `'
`
	if err := os.WriteFile(scriptPath, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}

	outcome, err := executeQuoteOrderCheck(
		context.Background(),
		scriptPath,
		verificationValues{
			quantity:           2,
			unitPriceCents:     1250,
			expectedTotalCents: 2500,
		},
	)

	if err != nil || outcome != "passed" {
		t.Fatalf("verification output ownership = %q, %v", outcome, err)
	}
}

func TestVerificationCleanupDoesNotRepeatGracefulTermination(t *testing.T) {
	if os.Getenv("UCF_GRACEFUL_TERMINATION_HELPER") == "1" {
		runGracefulTerminationHelper(t)
		os.Exit(0)
		return
	}

	ready, readyWriter, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer ready.Close()
	term, termWriter, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer term.Close()
	releaseReader, release, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer release.Close()

	command := exec.Command(
		os.Args[0],
		"-test.run=^TestVerificationCleanupDoesNotRepeatGracefulTermination$",
	)
	command.Env = append(
		os.Environ(),
		"UCF_GRACEFUL_TERMINATION_HELPER=1",
		"GORACE=atexit_sleep_ms=0",
	)
	command.ExtraFiles = []*os.File{readyWriter, termWriter, releaseReader}
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	owner, err := startVerificationProcess(command)
	readyWriter.Close()
	termWriter.Close()
	releaseReader.Close()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGKILL)
	})
	waited := make(chan error, 1)
	go func() {
		waited <- command.Wait()
	}()
	if line, err := bufio.NewReader(ready).ReadString('\n'); err != nil ||
		line != "ready\n" {
		t.Fatalf("verification readiness = %q, %v", line, err)
	}

	terminationGrace := 20 * verificationCleanupPollInterval
	cleanupDeadline := 100 * verificationCleanupPollInterval
	stopped := make(chan error, 1)
	go func() {
		stopped <- stopVerificationProcessWithinOwned(
			command,
			waited,
			owner,
			terminationGrace,
			cleanupDeadline,
		)
	}()
	type markerResult struct {
		line string
		err  error
	}
	terminated := make(chan markerResult, 1)
	go func() {
		line, readErr := bufio.NewReader(term).ReadString('\n')
		terminated <- markerResult{line: line, err: readErr}
	}()
	select {
	case result := <-terminated:
		if result.err != nil || result.line != "term\n" {
			t.Fatalf(
				"verification termination marker = %q, %v",
				result.line,
				result.err,
			)
		}
	case err := <-stopped:
		t.Fatalf(
			"verification cleanup returned before termination marker: %v",
			err,
		)
	case <-time.After(cleanupDeadline + terminationGrace):
		t.Fatal("verification termination marker was not bounded")
	}
	timer := time.NewTimer(4 * verificationCleanupPollInterval)
	select {
	case <-timer.C:
	case err := <-stopped:
		timer.Stop()
		t.Fatalf("verification cleanup returned before release: %v", err)
	}
	if _, err := release.WriteString("release\n"); err != nil {
		t.Fatal(err)
	}

	select {
	case err := <-stopped:
		if err != nil {
			t.Fatalf("graceful verification cleanup = %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("graceful verification cleanup did not return")
	}
}

func runGracefulTerminationHelper(t *testing.T) {
	ready := os.NewFile(3, "ready")
	term := os.NewFile(4, "term")
	release := os.NewFile(5, "release")
	if ready == nil || term == nil || release == nil {
		t.Fatal("graceful termination helper pipe is unavailable")
	}
	defer ready.Close()
	defer term.Close()
	defer release.Close()

	terminated := make(chan os.Signal, 1)
	signal.Notify(terminated, syscall.SIGTERM)
	if _, err := ready.WriteString("ready\n"); err != nil {
		t.Fatal(err)
	}
	<-terminated
	signal.Stop(terminated)
	signal.Reset(syscall.SIGTERM)
	if _, err := term.WriteString("term\n"); err != nil {
		t.Fatal(err)
	}
	line, err := bufio.NewReader(release).ReadString('\n')
	if err != nil || line != "release\n" {
		t.Fatalf("graceful termination helper release = %q, %v", line, err)
	}
}

func TestStopVerificationProcessReapsBlockingProcessGroup(t *testing.T) {
	readinessReader, readinessWriter, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer readinessReader.Close()
	command := exec.Command(
		"/bin/sh",
		"-c",
		"cat >/dev/null & child=$!; "+
			"trap 'kill \"$child\" 2>/dev/null || true; "+
			"wait \"$child\" 2>/dev/null || true; exit 0' TERM; "+
			"printf ready >&3; wait \"$child\"",
	)
	command.ExtraFiles = []*os.File{readinessWriter}
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	input, err := command.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	owner, err := startVerificationProcess(command)
	if err != nil {
		t.Fatal(err)
	}
	readinessWriter.Close()
	waited := make(chan error, 1)
	go func() {
		waited <- command.Wait()
	}()
	ready := make([]byte, len("ready"))
	if _, err := io.ReadFull(readinessReader, ready); err != nil {
		t.Fatal(err)
	}
	if string(ready) != "ready" {
		t.Fatalf("unexpected helper readiness: %q", ready)
	}

	if err := stopVerificationProcessWithinOwned(
		command,
		waited,
		owner,
		20*time.Millisecond,
		500*time.Millisecond,
	); err != nil {
		t.Fatal(err)
	}
	input.Close()
	if err := syscall.Kill(-command.Process.Pid, 0); !errors.Is(
		err,
		syscall.ESRCH,
	) {
		t.Fatalf("process group remains after cleanup: %v", err)
	}
}

func TestStopVerificationProcessKillsGroupAfterLeaderExits(t *testing.T) {
	root := t.TempDir()
	blockingPath := root + "/blocking.fifo"
	armedPath := root + "/armed.fifo"
	for _, path := range []string{blockingPath, armedPath} {
		if err := syscall.Mkfifo(path, 0600); err != nil {
			t.Fatal(err)
		}
	}
	readinessReader, readinessWriter, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer readinessReader.Close()
	command := exec.Command(
		"/bin/sh",
		"-c",
		`trap 'exit 0' TERM
exec 9<>"$1"
(
    trap '' TERM
    printf 'armed\n' >"$2"
    exec /bin/cat <&9 >/dev/null
) &
child=$!
read marker <"$2"
test "$marker" = armed
printf '%s\n' "$child" >&3
wait "$child"`,
		"cleanup-helper",
		blockingPath,
		armedPath,
	)
	command.ExtraFiles = []*os.File{readinessWriter}
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	owner, err := startVerificationProcess(command)
	if err != nil {
		t.Fatal(err)
	}
	readinessWriter.Close()
	waited := make(chan error, 1)
	go func() {
		waited <- command.Wait()
	}()
	t.Cleanup(func() {
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGKILL)
	})
	childLine, err := bufio.NewReader(readinessReader).ReadString('\n')
	if err != nil {
		t.Fatal(err)
	}
	childID, err := strconv.Atoi(strings.TrimSpace(childLine))
	if err != nil {
		t.Fatal(err)
	}

	if err := stopVerificationProcessWithinOwned(
		command,
		waited,
		owner,
		20*time.Millisecond,
		500*time.Millisecond,
	); err != nil {
		t.Fatal(err)
	}
	for _, identifier := range []int{command.Process.Pid, childID} {
		if err := syscall.Kill(identifier, 0); !errors.Is(
			err,
			syscall.ESRCH,
		) {
			t.Fatalf(
				"verification process %d remains after cleanup: %v",
				identifier,
				err,
			)
		}
	}
	if err := syscall.Kill(-command.Process.Pid, 0); !errors.Is(
		err,
		syscall.ESRCH,
	) {
		t.Fatalf("process group remains after cleanup: %v", err)
	}
}

func TestCancelledVerificationReapsProcessGroupBeforeReturn(t *testing.T) {
	root := t.TempDir()
	startedPath := root + "/started.fifo"
	blockingPath := root + "/blocking.fifo"
	for _, path := range []string{startedPath, blockingPath} {
		if err := syscall.Mkfifo(path, 0600); err != nil {
			t.Fatal(err)
		}
	}
	scriptPath := root + "/blocking-verification"
	script := `#!/bin/sh
fifo="${0%/*}/started.fifo"
blocking_fifo="${0%/*}/blocking.fifo"
child=
trap 'kill "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; exit 0' TERM INT
/bin/cat "$blocking_fifo" >/dev/null &
child=$!
printf '%s %s\n' "$$" "$child" > "$fifo"
wait "$child"
`
	if err := os.WriteFile(scriptPath, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}

	contextValue, cancel := context.WithCancel(context.Background())
	defer cancel()
	type executionResult struct {
		outcome string
		err     error
	}
	finished := make(chan executionResult, 1)
	go func() {
		outcome, err := executeQuoteOrderCheck(
			contextValue,
			scriptPath,
			verificationValues{
				quantity:           2,
				unitPriceCents:     1250,
				expectedTotalCents: 2500,
			},
		)
		finished <- executionResult{outcome: outcome, err: err}
	}()

	started := make(chan []byte, 1)
	go func() {
		payload, _ := os.ReadFile(startedPath)
		started <- payload
	}()
	var payload []byte
	select {
	case payload = <-started:
	case <-time.After(verificationPhaseDeadline):
		cancel()
		t.Fatal("blocking verification did not start")
	}
	identities := strings.Fields(string(payload))
	if len(identities) != 2 {
		cancel()
		t.Fatalf("invalid process identities: %q", payload)
	}
	processID, err := strconv.Atoi(identities[0])
	if err != nil {
		cancel()
		t.Fatal(err)
	}
	childID, err := strconv.Atoi(identities[1])
	if err != nil {
		cancel()
		t.Fatal(err)
	}
	for _, identifier := range []int{processID, childID} {
		if err := syscall.Kill(identifier, 0); err != nil {
			cancel()
			t.Fatalf(
				"verification process %d was not live before cancellation: %v",
				identifier,
				err,
			)
		}
	}

	cancel()
	var result executionResult
	select {
	case result = <-finished:
	case <-time.After(verificationCleanupDeadline + time.Second):
		t.Fatal("cancelled verification did not finish cleanup")
	}
	if result.outcome != "error" ||
		!errors.Is(result.err, context.Canceled) {
		t.Fatalf(
			"cancelled verification result = %q, %v",
			result.outcome,
			result.err,
		)
	}
	for _, identifier := range []int{processID, childID} {
		if err := syscall.Kill(identifier, 0); !errors.Is(
			err,
			syscall.ESRCH,
		) {
			t.Fatalf(
				"verification process %d remains after return: %v",
				identifier,
				err,
			)
		}
	}
}

func TestCancelledShortVerificationReapsDetachedDescendantAndAllowsReuse(
	t *testing.T,
) {
	root := t.TempDir()
	processPath := root + "/detached.pid"
	scriptPath := root + "/detached-verification"
	script := `#!/bin/sh
/usr/bin/setsid /bin/sh -c '
    trap "" TERM INT
    printf "%s\n" "$$" >"$1"
    exec /bin/sleep 30
' detached "$1" </dev/null >/dev/null 2>&1 &
wait
`
	if err := os.WriteFile(scriptPath, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	contextValue, cancel := context.WithCancel(context.Background())
	type executionResult struct {
		result shortProcessResult
		err    error
	}
	finished := make(chan executionResult, 1)
	go func() {
		result, err := runShortVerificationProcess(
			contextValue,
			scriptPath,
			[]string{processPath},
		)
		finished <- executionResult{result: result, err: err}
	}()

	var detachedID int
	deadline := time.Now().Add(verificationPhaseDeadline)
	for time.Now().Before(deadline) {
		payload, readErr := os.ReadFile(processPath)
		if readErr == nil {
			detachedID, readErr = strconv.Atoi(
				strings.TrimSpace(string(payload)),
			)
			if readErr != nil {
				cancel()
				t.Fatal(readErr)
			}
			break
		}
		if !errors.Is(readErr, os.ErrNotExist) {
			cancel()
			t.Fatal(readErr)
		}
		time.Sleep(verificationCleanupPollInterval)
	}
	if detachedID == 0 {
		cancel()
		t.Fatal("detached verification descendant did not start")
	}
	t.Cleanup(func() {
		_ = syscall.Kill(detachedID, syscall.SIGKILL)
	})

	cancel()
	select {
	case result := <-finished:
		if !errors.Is(result.err, context.Canceled) {
			t.Fatalf(
				"cancelled short verification = %#v, %v",
				result.result,
				result.err,
			)
		}
	case <-time.After(verificationCleanupDeadline + time.Second):
		t.Fatal("detached verification cleanup did not return")
	}
	if err := syscall.Kill(detachedID, 0); !errors.Is(err, syscall.ESRCH) {
		t.Fatalf("detached descendant remains after return: %v", err)
	}

	reused, err := runShortVerificationProcess(
		context.Background(),
		"/bin/sh",
		[]string{"-c", "printf 'reused\\n'"},
	)
	if err != nil {
		t.Fatal(err)
	}
	if reused.exitCode != 0 ||
		string(reused.stdout) != "reused\n" ||
		len(reused.stderr) != 0 {
		t.Fatalf("reused verification result = %#v", reused)
	}
}

func TestVerificationExecutableSnapshotRunsAttestedBytesAfterPathSwap(
	t *testing.T,
) {
	root := t.TempDir()
	sourcePath := root + "/fixture"
	if err := os.WriteFile(
		sourcePath,
		[]byte("#!/bin/sh\nprintf 'trusted\\n'\n"),
		0700,
	); err != nil {
		t.Fatal(err)
	}
	snapshot, err := copyVerificationExecutableSnapshot(sourcePath)
	if err != nil {
		t.Fatal(err)
	}
	defer snapshot.cleanup()

	replacement := root + "/replacement"
	if err := os.WriteFile(
		replacement,
		[]byte("#!/bin/sh\nprintf 'forged\\n'\n"),
		0700,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(replacement, sourcePath); err != nil {
		t.Fatal(err)
	}
	result, err := runShortVerificationProcess(
		context.Background(),
		snapshot.path,
		nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	if result.exitCode != 0 ||
		string(result.stdout) != "trusted\n" ||
		len(result.stderr) != 0 {
		t.Fatalf("snapshot execution = %#v", result)
	}
}

func TestEventVerificationUsesOneOverallDeadline(t *testing.T) {
	executable := t.TempDir() + "/slow-event-fixture"
	script := `#!/bin/sh
sleep 0.12
spool=
event_id=
while test "$#" -gt 0; do
    case "$1" in
        --spool) spool=$2; shift 2 ;;
        --event-id) event_id=$2; shift 2 ;;
        --unit-price-cents|--quantity) shift 2 ;;
        *) command="${command:+$command }$1"; shift ;;
    esac
done
case "$command" in
    "event enqueue")
        printf '{"event_id":"%s","status":"enqueued"}\n' "$event_id"
        ;;
    "event observe")
        if test -f "$spool/dispatched"; then
            printf '{"event_id":"%s","receipt":"Total: 25.00","total_cents":2500}\n' "$event_id"
        else
            printf 'observation unavailable\n' >&2
            exit 3
        fi
        ;;
    "event dispatch-once")
        : >"$spool/dispatched"
        printf '{"event_id":"quote-order-001","status":"dispatched"}\n'
        ;;
    *) exit 2 ;;
esac
`
	if err := os.WriteFile(executable, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	startedAt := time.Now()
	outcome, err := executeEventQuoteOrderCheckWithin(
		context.Background(),
		executable,
		verificationValues{
			quantity:           2,
			unitPriceCents:     1250,
			expectedTotalCents: 2500,
		},
		250*time.Millisecond,
	)
	elapsed := time.Since(startedAt)
	if outcome != "error" || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("event deadline result = %q, %v", outcome, err)
	}
	if elapsed >= time.Second {
		t.Fatalf("overall event deadline took %s", elapsed)
	}
}

func TestCancelledEventVerificationRemovesSpoolBeforeReturn(t *testing.T) {
	root := t.TempDir()
	spoolMarker := root + "/spool"
	executable := root + "/blocking-event-fixture"
	script := `#!/bin/sh
spool=
while test "$#" -gt 0; do
    if test "$1" = "--spool"; then
        spool=$2
        shift 2
    else
        shift
    fi
done
printf '%s\n' "$spool" >"${0%/*}/spool"
exec /bin/sleep 30
`
	if err := os.WriteFile(executable, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	contextValue, cancel := context.WithCancel(context.Background())
	type executionResult struct {
		outcome string
		err     error
	}
	finished := make(chan executionResult, 1)
	go func() {
		outcome, err := executeEventQuoteOrderCheck(
			contextValue,
			executable,
			verificationValues{
				quantity:           2,
				unitPriceCents:     1250,
				expectedTotalCents: 2500,
			},
		)
		finished <- executionResult{outcome: outcome, err: err}
	}()

	var spoolRoot string
	deadline := time.Now().Add(verificationPhaseDeadline)
	for time.Now().Before(deadline) {
		payload, err := os.ReadFile(spoolMarker)
		if err == nil {
			spoolRoot = strings.TrimSpace(string(payload))
			break
		}
		if !errors.Is(err, os.ErrNotExist) {
			cancel()
			t.Fatal(err)
		}
		time.Sleep(verificationCleanupPollInterval)
	}
	if spoolRoot == "" {
		cancel()
		t.Fatal("event verification did not expose its spool")
	}
	cancel()
	select {
	case result := <-finished:
		if result.outcome != "error" ||
			!errors.Is(result.err, context.Canceled) {
			t.Fatalf(
				"cancelled event verification = %q, %v",
				result.outcome,
				result.err,
			)
		}
	case <-time.After(verificationCleanupDeadline + time.Second):
		t.Fatal("cancelled event verification did not return")
	}
	if _, err := os.Lstat(spoolRoot); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("event spool remains after cancellation: %v", err)
	}
}

func TestEventSpoolCleanupFailureIsVerificationCleanupFailure(t *testing.T) {
	forced := errors.New("forced spool cleanup failure")
	outcome, err := executeEventQuoteOrderCheckWithinWithCleanup(
		context.Background(),
		"/bin/true",
		verificationValues{
			quantity:           2,
			unitPriceCents:     1250,
			expectedTotalCents: 2500,
		},
		verificationDeadline,
		func(string) error {
			return forced
		},
	)

	if outcome != "error" ||
		!errors.Is(err, errVerificationCleanup) ||
		!errors.Is(err, forced) {
		t.Fatalf("event spool cleanup result = %q, %v", outcome, err)
	}
}

func TestEventVerificationRejectsUnexpectedProcessOutput(t *testing.T) {
	executable := t.TempDir() + "/unexpected-event-fixture"
	if err := os.WriteFile(
		executable,
		[]byte("#!/bin/sh\nprintf 'unexpected\\n'\n"),
		0700,
	); err != nil {
		t.Fatal(err)
	}
	outcome, err := executeEventQuoteOrderCheck(
		context.Background(),
		executable,
		verificationValues{
			quantity:           2,
			unitPriceCents:     1250,
			expectedTotalCents: 2500,
		},
	)
	if err != nil || outcome != "failed" {
		t.Fatalf("unexpected event output result = %q, %v", outcome, err)
	}
}

func TestShortVerificationRejectsOutputOverflow(t *testing.T) {
	result, err := runShortVerificationProcess(
		context.Background(),
		"/bin/sh",
		[]string{
			"-c",
			"/usr/bin/head -c 65537 /dev/zero",
		},
	)
	if err == nil ||
		err.Error() != "verification process output exceeds the byte limit" {
		t.Fatalf("overflow result = %#v, %v", result, err)
	}
}

type countingNoNewlineReader struct {
	remaining int
	consumed  int
}

func (instance *countingNoNewlineReader) Read(payload []byte) (int, error) {
	if instance.remaining == 0 {
		return 0, io.EOF
	}
	count := min(len(payload), instance.remaining)
	for index := range count {
		payload[index] = 'x'
	}
	instance.remaining -= count
	instance.consumed += count
	return count, nil
}

func TestQueuedCancellationRemovesJobBeforeExecution(t *testing.T) {
	instance, output := newRunnerTestServer()
	contextValue, cancel := context.WithCancel(context.Background())
	job := &operationJob{
		id:      "queued",
		method:  "ucf.inventory",
		context: contextValue,
		cancel:  cancel,
	}
	instance.operationJobs[job.id] = job
	instance.operationQueue = []*operationJob{job}

	instance.cancelOperation(job.id)

	if contextValue.Err() != context.Canceled {
		t.Fatalf("queued context error = %v", contextValue.Err())
	}
	if len(instance.operationQueue) != 0 ||
		len(instance.operationJobs) != 0 {
		t.Fatalf(
			"queued job remains: queue=%d jobs=%d",
			len(instance.operationQueue),
			len(instance.operationJobs),
		)
	}
	assertSingleTerminalCode(
		t,
		output,
		job.id,
		"request_cancelled",
	)
}

func TestRunningCancellationCompletesOnlyAfterHandlerCleanup(t *testing.T) {
	cleanupComplete := false
	var output bytes.Buffer
	guard := &cleanupGuardWriter{
		output:          &output,
		cleanupComplete: &cleanupComplete,
	}
	instance := &server{
		writer:        bufio.NewWriter(guard),
		operationJobs: map[string]*operationJob{},
	}
	contextValue, cancel := context.WithCancel(context.Background())
	job := &operationJob{
		id:      "running",
		method:  "ucf.verify",
		context: contextValue,
		cancel:  cancel,
		started: true,
	}
	instance.operationJobs[job.id] = job

	instance.cancelOperation(job.id)

	if contextValue.Err() != context.Canceled {
		t.Fatalf("running context error = %v", contextValue.Err())
	}
	if output.Len() != 0 {
		t.Fatal("running cancellation was acknowledged before cleanup")
	}

	cleanupComplete = true
	instance.completeOperation(
		job,
		successfulOperation(map[string]any{"kind": "unexpected"}),
	)
	assertSingleTerminalCode(
		t,
		&output,
		job.id,
		"request_cancelled",
	)

	beforeLateCancel := output.String()
	instance.cancelOperation(job.id)
	if output.String() != beforeLateCancel {
		t.Fatal("late cancellation wrote a second terminal response")
	}
}

func TestCancellationCleanupFailureOutranksCancellationAcknowledgement(
	t *testing.T,
) {
	instance, output := newRunnerTestServer()
	contextValue, cancel := context.WithCancel(context.Background())
	job := &operationJob{
		id:        "cleanup-failed",
		method:    "ucf.verify",
		context:   contextValue,
		cancel:    cancel,
		started:   true,
		cancelled: true,
	}
	instance.operationJobs[job.id] = job

	instance.completeOperation(
		job,
		cleanupFailedOperation("verification process cleanup failed"),
	)

	assertSingleTerminalCode(
		t,
		output,
		job.id,
		"operation_failed",
	)
}

func TestCompletedOperationWinsLateCancellation(t *testing.T) {
	instance, output := newRunnerTestServer()
	contextValue, cancel := context.WithCancel(context.Background())
	job := &operationJob{
		id:      "completed",
		method:  "ucf.inventory",
		context: contextValue,
		cancel:  cancel,
		started: true,
	}
	instance.operationJobs[job.id] = job

	instance.completeOperation(
		job,
		successfulOperation(map[string]any{"kind": "inventory_result"}),
	)
	instance.cancelOperation(job.id)

	lines := bytes.Split(bytes.TrimSpace(output.Bytes()), []byte{'\n'})
	if len(lines) != 1 {
		t.Fatalf("terminal frame count = %d", len(lines))
	}
	decoded, err := parseStrictJSON(lines[0])
	if err != nil {
		t.Fatal(err)
	}
	response := decoded.(map[string]any)
	if response["id"] != job.id {
		t.Fatalf("terminal response id = %#v", response["id"])
	}
	result, ok := response["result"].(map[string]any)
	if !ok || result["kind"] != "inventory_result" {
		t.Fatalf("terminal result = %#v", response["result"])
	}
}

type cleanupGuardWriter struct {
	output          *bytes.Buffer
	cleanupComplete *bool
}

func (instance *cleanupGuardWriter) Write(payload []byte) (int, error) {
	if !*instance.cleanupComplete {
		return 0, errors.New("terminal response preceded handler cleanup")
	}
	return instance.output.Write(payload)
}

func newRunnerTestServer() (*server, *bytes.Buffer) {
	var output bytes.Buffer
	return &server{
		writer:        bufio.NewWriter(&output),
		operationJobs: map[string]*operationJob{},
	}, &output
}

func assertSingleTerminalCode(
	t *testing.T,
	output *bytes.Buffer,
	requestID string,
	code string,
) {
	t.Helper()
	lines := bytes.Split(bytes.TrimSpace(output.Bytes()), []byte{'\n'})
	if len(lines) != 1 {
		t.Fatalf("terminal frame count = %d", len(lines))
	}
	decoded, err := parseStrictJSON(lines[0])
	if err != nil {
		t.Fatal(err)
	}
	response := decoded.(map[string]any)
	if response["id"] != requestID {
		t.Fatalf("terminal response id = %#v", response["id"])
	}
	errorValue, ok := response["error"].(map[string]any)
	if !ok {
		t.Fatalf("terminal response has no error: %#v", response)
	}
	data := errorValue["data"].(map[string]any)
	if data["ucf_code"] != code {
		t.Fatalf("terminal response code = %#v", data["ucf_code"])
	}
}
