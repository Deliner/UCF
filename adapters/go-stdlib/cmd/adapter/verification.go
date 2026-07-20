package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"debug/buildinfo"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	runtimedebug "runtime/debug"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const (
	verificationVersion                  = "1.0.0"
	verificationRequestSchemaURI         = "urn:ucf:adapter:execution-verification-request:1.0.0"
	verificationResultSchemaURI          = "urn:ucf:adapter:execution-verification-result:1.0.0"
	verificationProfileProcedureURI      = "urn:ucf:implementation-evidence:verify:1.0.0"
	verificationAdapterProcedureURI      = "urn:ucf:adapter:go-stdlib-real-http-verification:1.0.0"
	verificationEnvironmentURI           = "urn:ucf:fixture-environment:go1.26.5-linux-amd64-cgo0-loopback:1.0.0"
	verificationCheckProcedureURI        = "urn:ucf:fixture-check:quote-order-http-contract:1.0.0"
	cliVerificationAdapterProcedureURI   = "urn:ucf:adapter:go-stdlib-real-cli-verification:1.0.0"
	cliVerificationEnvironmentURI        = "urn:ucf:fixture-environment:go1.26.5-linux-amd64-cgo0-cli-process:1.0.0"
	cliVerificationCheckProcedureURI     = "urn:ucf:fixture-check:quote-order-cli-process-contract:1.0.0"
	eventVerificationAdapterProcedureURI = "urn:ucf:adapter:go-stdlib-file-spool-event-verification:1.0.0"
	eventVerificationEnvironmentURI      = "urn:ucf:fixture-environment:go1.26.5-linux-amd64-cgo0-file-spool-event:1.0.0"
	eventVerificationCheckProcedureURI   = "urn:ucf:fixture-check:quote-order-event-enqueue-dispatch-observe:1.0.0"
	verificationDeadline                 = 5 * time.Second
	verificationPhaseDeadline            = 2 * time.Second
	verificationTerminationGrace         = 1 * time.Second
	verificationCleanupDeadline          = 2 * time.Second
	verificationCleanupPollInterval      = 5 * time.Millisecond
	maxVerificationOutputBytes           = 65_536
	maxVerificationExecutableBytes       = 64 * 1024 * 1024
)

var errVerificationCleanup = errors.New("verification process cleanup failed")

type verificationProcedureSpec struct {
	adapterProcedureURI string
	requiredCapability  string
	environmentURI      string
	checkID             string
	checkProcedureURI   string
	fixtureModulePath   string
	runtimeBoundary     string
}

type verificationValues struct {
	quantity           int
	unitPriceCents     int
	expectedTotalCents int
}

type boundedStream struct {
	payload  []byte
	overflow bool
	err      error
}

type verificationOutputPipes struct {
	stdoutReader *os.File
	stdoutWriter *os.File
	stderrReader *os.File
	stderrWriter *os.File
}

func openVerificationOutputPipes(
	command *exec.Cmd,
) (*verificationOutputPipes, error) {
	stdoutReader, stdoutWriter, err := os.Pipe()
	if err != nil {
		return nil, err
	}
	pipes := &verificationOutputPipes{
		stdoutReader: stdoutReader,
		stdoutWriter: stdoutWriter,
	}
	stderrReader, stderrWriter, err := os.Pipe()
	if err != nil {
		return nil, errors.Join(err, pipes.closeAll())
	}
	pipes.stderrReader = stderrReader
	pipes.stderrWriter = stderrWriter
	command.Stdout = stdoutWriter
	command.Stderr = stderrWriter
	return pipes, nil
}

func (pipes *verificationOutputPipes) closeWriters() error {
	if pipes == nil {
		return nil
	}
	return errors.Join(
		closeVerificationOutputFile(&pipes.stdoutWriter),
		closeVerificationOutputFile(&pipes.stderrWriter),
	)
}

func (pipes *verificationOutputPipes) closeReaders() error {
	if pipes == nil {
		return nil
	}
	return errors.Join(
		closeVerificationOutputFile(&pipes.stdoutReader),
		closeVerificationOutputFile(&pipes.stderrReader),
	)
}

func (pipes *verificationOutputPipes) closeAll() error {
	if pipes == nil {
		return nil
	}
	return errors.Join(pipes.closeWriters(), pipes.closeReaders())
}

func closeVerificationOutputFile(file **os.File) error {
	if file == nil || *file == nil {
		return nil
	}
	owned := *file
	*file = nil
	return owned.Close()
}

func (instance *server) verification(
	parent context.Context,
	payload map[string]any,
) (operationResult operationOutcome) {
	run := instance.inventoryRun
	mapping := instance.mappingResult
	if run == nil || !run.completed || mapping == nil {
		return failedOperation(
			"operation_failed",
			"verification requires current inventory and mapping",
		)
	}
	if !instance.mappingRunIsCurrent(run) {
		instance.inventoryRun = nil
		instance.mappingResult = nil
		return failedOperation(
			"operation_failed",
			"verification source is no longer current",
		)
	}
	request, err := decodeVerificationEnvelope(payload)
	if err != nil {
		return failedOperation(
			"invalid_params",
			"verification request is outside the Go fixture profile",
		)
	}
	procedure, err := instance.verificationProcedure(request)
	if err != nil {
		return failedOperation(
			"invalid_params",
			"verification request is outside the Go fixture profile",
		)
	}
	if procedure.requiredCapability != "" &&
		!instance.selectedCapabilities[procedure.requiredCapability] {
		return failedOperation(
			"capability_not_negotiated",
			"verification platform capability was not negotiated",
		)
	}
	snapshot, err := prepareVerificationExecutableSnapshot(
		instance.fixtureExecutable,
		procedure,
	)
	if err != nil {
		if failure, handled := verificationFailureOutcome(
			parent,
			err,
		); handled {
			return failure
		}
		return failedOperation(
			"operation_failed",
			"verification executable is unavailable",
		)
	}
	defer func() {
		if cleanupErr := snapshot.cleanup(); cleanupErr != nil {
			operationResult = cleanupFailedOperation(
				"verification executable cleanup failed",
			)
		}
	}()
	environment, err := instance.executionEnvironmentFromSnapshot(
		run,
		procedure,
		snapshot,
	)
	if err != nil {
		return failedOperation(
			"operation_failed",
			"verification execution environment is unavailable",
		)
	}
	values, err := instance.validateVerificationRequest(
		request,
		run,
		mapping,
		environment,
		procedure,
	)
	if err != nil {
		return failedOperation(
			"invalid_params",
			"verification request is outside the Go fixture profile",
		)
	}

	outcome, executionErr := instance.executeVerificationProcedure(
		parent,
		procedure,
		values,
		snapshot.path,
	)
	if failure, handled := verificationFailureOutcome(
		parent,
		executionErr,
	); handled {
		return failure
	}

	currentEnvironment, currentErr := instance.executionEnvironment(
		run,
		procedure,
	)
	if currentErr != nil ||
		!sameCanonicalLogicalValue(currentEnvironment, environment) ||
		!instance.mappingRunIsCurrent(run) {
		instance.inventoryRun = nil
		instance.mappingResult = nil
		return failedOperation(
			"operation_failed",
			"verification context changed during execution",
		)
	}
	result, err := buildVerificationResult(
		request,
		outcome,
		time.Now().UTC().Truncate(time.Second).Format(
			"2006-01-02T15:04:05Z",
		),
		procedure,
	)
	if err != nil {
		return failedOperation(
			"internal_error",
			"verification result construction failed",
		)
	}
	tagged, ok := encodeProfileValue(result, 0)
	if !ok {
		return failedOperation(
			"internal_error",
			"verification result cannot be encoded",
		)
	}
	return successfulOperation(map[string]any{
		"kind": "verify_result",
		"payload": map[string]any{
			"kind":           "adapter_payload",
			"schema_uri":     verificationResultSchemaURI,
			"schema_version": verificationVersion,
			"value":          tagged,
		},
	})
}

func (instance *server) verificationExecutableAvailable() bool {
	if err := ensureVerificationSubreaper(); err != nil {
		return false
	}
	procedure := httpVerificationProcedure()
	if instance.platformMode {
		procedure = cliVerificationProcedure()
	}
	_, _, err := instance.executionBinaryCoordinates(procedure)
	return err == nil
}

func (instance *server) verificationProcedure(
	request map[string]any,
) (verificationProcedureSpec, error) {
	procedureURI, ok := request["adapter_procedure_uri"].(string)
	if !ok {
		return verificationProcedureSpec{}, errors.New(
			"verification procedure is invalid",
		)
	}
	if instance.platformMode {
		switch procedureURI {
		case cliVerificationAdapterProcedureURI:
			return cliVerificationProcedure(), nil
		case eventVerificationAdapterProcedureURI:
			return eventVerificationProcedure(), nil
		default:
			return verificationProcedureSpec{}, errors.New(
				"verification procedure is outside the platform profile",
			)
		}
	}
	if procedureURI != verificationAdapterProcedureURI {
		return verificationProcedureSpec{}, errors.New(
			"verification procedure is outside the HTTP profile",
		)
	}
	return httpVerificationProcedure(), nil
}

func httpVerificationProcedure() verificationProcedureSpec {
	return verificationProcedureSpec{
		adapterProcedureURI: verificationAdapterProcedureURI,
		requiredCapability:  httpLoopbackCapabilityName,
		environmentURI:      verificationEnvironmentURI,
		checkID:             "check.quote-order.real-http",
		checkProcedureURI:   verificationCheckProcedureURI,
		fixtureModulePath:   "example.com/legacyquotes",
	}
}

func verificationFailureOutcome(
	parent context.Context,
	executionErr error,
) (operationOutcome, bool) {
	if errors.Is(executionErr, errVerificationCleanup) {
		return cleanupFailedOperation(
			"verification process cleanup failed",
		), true
	}
	if parent.Err() != nil {
		return failedOperation(
			"request_cancelled",
			"verification was cancelled",
		), true
	}
	return operationOutcome{}, false
}

func cliVerificationProcedure() verificationProcedureSpec {
	return verificationProcedureSpec{
		adapterProcedureURI: cliVerificationAdapterProcedureURI,
		requiredCapability:  cliProcessCapabilityName,
		environmentURI:      cliVerificationEnvironmentURI,
		checkID:             "check.quote-order.real-cli",
		checkProcedureURI:   cliVerificationCheckProcedureURI,
		fixtureModulePath:   "example.com/legacyplatforms",
		runtimeBoundary:     "cli-process",
	}
}

func eventVerificationProcedure() verificationProcedureSpec {
	return verificationProcedureSpec{
		adapterProcedureURI: eventVerificationAdapterProcedureURI,
		requiredCapability:  fileSpoolEventCapabilityName,
		environmentURI:      eventVerificationEnvironmentURI,
		checkID:             "check.quote-order.file-spool-event",
		checkProcedureURI:   eventVerificationCheckProcedureURI,
		fixtureModulePath:   "example.com/legacyplatforms",
		runtimeBoundary:     "file-spool-event",
	}
}

func (instance *server) executionEnvironment(
	run *inventoryRun,
	procedure verificationProcedureSpec,
) (map[string]any, error) {
	adapter, fixture, err := instance.executionBinaryCoordinates(procedure)
	if err != nil {
		return nil, err
	}
	return buildExecutionEnvironment(run, procedure, adapter, fixture)
}

func (instance *server) executionEnvironmentFromSnapshot(
	run *inventoryRun,
	procedure verificationProcedureSpec,
	snapshot *verificationExecutableSnapshot,
) (map[string]any, error) {
	adapter, fixture, err := instance.executionBinaryCoordinatesFromSnapshot(
		procedure,
		snapshot,
	)
	if err != nil {
		return nil, err
	}
	return buildExecutionEnvironment(run, procedure, adapter, fixture)
}

func buildExecutionEnvironment(
	run *inventoryRun,
	procedure verificationProcedureSpec,
	adapter map[string]any,
	fixture map[string]any,
) (map[string]any, error) {
	sourceRevision, ok := run.snapshot["source_revision"].(map[string]any)
	if !ok || !validMappingDigest(sourceRevision) {
		return nil, errors.New("verification source revision is invalid")
	}
	runtimeCoordinates := map[string]any{
		"kind":    "go_runtime_coordinates",
		"version": "go1.26.5",
		"goos":    "linux",
		"goarch":  "amd64",
		"network": "loopback-only",
	}
	if procedure.runtimeBoundary != "" {
		runtimeCoordinates["network"] = "disabled"
		runtimeCoordinates["boundary"] = procedure.runtimeBoundary
	}
	receipt := map[string]any{
		"kind":            "go_stdlib_execution_receipt",
		"receipt_version": verificationVersion,
		"binaries":        []any{adapter, fixture},
		"toolchain": map[string]any{
			"kind":    "go_toolchain",
			"version": "go1.26.5",
			"mode":    "local",
		},
		"build": map[string]any{
			"kind":             "go_build_coordinates",
			"build_mode":       "exe",
			"compiler":         "gc",
			"trimpath":         true,
			"cgo_enabled":      false,
			"goos":             "linux",
			"goarch":           "amd64",
			"goamd64":          "v1",
			"external_modules": []any{},
		},
		"runtime": runtimeCoordinates,
		"source": map[string]any{
			"kind":            "source_identity",
			"subject_uri":     run.snapshot["subject_uri"],
			"source_revision": sourceRevision,
		},
	}
	revision, err := canonicalLogicalDigest(receipt)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"kind":         "execution_environment",
		"identity_uri": procedure.environmentURI,
		"revision":     digestValue(revision),
	}, nil
}

func (instance *server) executionBinaryCoordinatesFromSnapshot(
	procedure verificationProcedureSpec,
	snapshot *verificationExecutableSnapshot,
) (
	map[string]any,
	map[string]any,
	error,
) {
	if snapshot == nil ||
		snapshot.path == "" ||
		snapshot.digest == "" ||
		snapshot.size < 1 ||
		snapshot.modulePath != procedure.fixtureModulePath {
		return nil, nil, errors.New("verification snapshot is invalid")
	}
	adapter, err := executionAdapterBinaryCoordinates()
	if err != nil {
		return nil, nil, err
	}
	return adapter, verificationBinary(
		"fixture",
		snapshot.modulePath,
		snapshot.digest,
		snapshot.size,
	), nil
}

func (instance *server) executionBinaryCoordinates(
	procedure verificationProcedureSpec,
) (
	map[string]any,
	map[string]any,
	error,
) {
	fixturePath, err := strictFixtureExecutable(instance.fixtureExecutable)
	if err != nil {
		return nil, nil, err
	}
	fixtureInfo, err := buildinfo.ReadFile(fixturePath)
	if err != nil || !validVerificationBuildInfo(
		fixtureInfo,
		procedure.fixtureModulePath,
	) {
		return nil, nil, errors.New("unsupported fixture build")
	}
	adapter, err := executionAdapterBinaryCoordinates()
	if err != nil {
		return nil, nil, err
	}
	fixtureDigest, fixtureSize, err := digestStableExecutable(fixturePath)
	if err != nil {
		return nil, nil, err
	}
	return adapter,
		verificationBinary(
			"fixture",
			procedure.fixtureModulePath,
			fixtureDigest,
			fixtureSize,
		),
		nil
}

func executionAdapterBinaryCoordinates() (map[string]any, error) {
	if runtime.Version() != "go1.26.5" ||
		runtime.GOOS != "linux" ||
		runtime.GOARCH != "amd64" {
		return nil, errors.New("unsupported adapter runtime")
	}
	selfInfo, ok := runtimedebug.ReadBuildInfo()
	if !ok || !validVerificationBuildInfo(
		selfInfo,
		"ucf/adapters/go-stdlib",
	) {
		return nil, errors.New("unsupported adapter build")
	}
	adapterDigest, adapterSize, err := digestOpenExecutable(
		"/proc/self/exe",
	)
	if err != nil {
		return nil, err
	}
	return verificationBinary(
		"adapter",
		"ucf/adapters/go-stdlib",
		adapterDigest,
		adapterSize,
	), nil
}

func validVerificationBuildInfo(
	info *buildinfo.BuildInfo,
	modulePath string,
) bool {
	if info == nil ||
		info.GoVersion != "go1.26.5" ||
		info.Main.Path != modulePath ||
		len(info.Deps) != 0 {
		return false
	}
	expected := map[string]string{
		"-buildmode":  "exe",
		"-compiler":   "gc",
		"-trimpath":   "true",
		"CGO_ENABLED": "0",
		"GOARCH":      "amd64",
		"GOOS":        "linux",
		"GOAMD64":     "v1",
	}
	actual := map[string]string{}
	for _, setting := range info.Settings {
		if _, duplicate := actual[setting.Key]; duplicate {
			return false
		}
		actual[setting.Key] = setting.Value
	}
	if len(actual) != len(expected) {
		return false
	}
	for name, value := range expected {
		if actual[name] != value {
			return false
		}
	}
	return true
}

func strictFixtureExecutable(path string) (string, error) {
	if path == "" || !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return "", errors.New("fixture executable path is not canonical")
	}
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil || resolved != path {
		return "", errors.New("fixture executable path contains a symlink")
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode()&0111 == 0 {
		return "", errors.New("fixture executable is not a regular executable")
	}
	return path, nil
}

func digestStableExecutable(path string) (string, int, error) {
	before, err := os.Lstat(path)
	if err != nil || !before.Mode().IsRegular() {
		return "", 0, errors.New("executable is unavailable")
	}
	digest, size, err := digestOpenExecutable(path)
	if err != nil {
		return "", 0, err
	}
	after, err := os.Lstat(path)
	if err != nil ||
		!os.SameFile(before, after) ||
		before.Size() != after.Size() ||
		!before.ModTime().Equal(after.ModTime()) {
		return "", 0, errors.New("executable changed while hashing")
	}
	return digest, size, nil
}

func digestOpenExecutable(path string) (string, int, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() ||
		info.Size() < 1 ||
		info.Size() > maxVerificationExecutableBytes {
		return "", 0, errors.New("executable size is outside the profile")
	}
	hasher := sha256.New()
	copied, err := io.Copy(hasher, file)
	if err != nil || copied != info.Size() {
		return "", 0, errors.New("executable cannot be hashed completely")
	}
	return hex.EncodeToString(hasher.Sum(nil)), int(copied), nil
}

func verificationBinary(
	role string,
	modulePath string,
	digest string,
	size int,
) map[string]any {
	return map[string]any{
		"kind":        "go_binary",
		"role":        role,
		"module_path": modulePath,
		"digest":      digestValue(digest),
		"size_bytes":  size,
	}
}

func decodeVerificationEnvelope(
	payload map[string]any,
) (map[string]any, error) {
	if payload["schema_uri"] != verificationRequestSchemaURI ||
		payload["schema_version"] != verificationVersion {
		return nil, errors.New("incompatible verification payload")
	}
	logical, err := decodeProfileValue(payload["value"], 0)
	if err != nil {
		return nil, err
	}
	request, ok := logical.(map[string]any)
	if !ok || !hasExactKeys(
		request,
		"adapter_procedure_uri",
		"base_behavior",
		"capability",
		"check",
		"environment",
		"expected_outputs",
		"implementation_evidence_version",
		"inputs",
		"kind",
		"mapping",
		"profile_procedure_uri",
		"schema_uri",
		"source",
		"subject",
	) ||
		request["kind"] != "execution_verification_request" ||
		request["implementation_evidence_version"] != verificationVersion ||
		request["schema_uri"] != verificationRequestSchemaURI ||
		request["profile_procedure_uri"] != verificationProfileProcedureURI ||
		!sameCanonicalLogicalValue(
			request["capability"],
			verificationCapability(),
		) {
		return nil, errors.New("invalid verification request")
	}
	return request, nil
}

func (instance *server) validateVerificationRequest(
	request map[string]any,
	run *inventoryRun,
	mapping map[string]any,
	environment map[string]any,
	procedure verificationProcedureSpec,
) (verificationValues, error) {
	if request["adapter_procedure_uri"] != procedure.adapterProcedureURI {
		return verificationValues{}, errors.New(
			"verification procedure does not match the active profile",
		)
	}
	contextValues, err := instance.verificationMappingContext(mapping, run)
	if err != nil {
		return verificationValues{}, err
	}
	if !sameCanonicalLogicalValue(
		request["mapping"],
		contextValues["mapping"],
	) ||
		!sameCanonicalLogicalValue(
			request["base_behavior"],
			contextValues["base_behavior"],
		) ||
		!sameCanonicalLogicalValue(
			request["subject"],
			contextValues["subject"],
		) ||
		!sameCanonicalLogicalValue(
			request["source"],
			contextValues["source"],
		) ||
		!sameCanonicalLogicalValue(request["environment"], environment) ||
		!sameCanonicalLogicalValue(
			request["check"],
			verificationCheck(procedure),
		) {
		return verificationValues{}, errors.New("verification context is invalid")
	}
	inputs, ok := request["inputs"].([]any)
	if !ok || len(inputs) != 2 {
		return verificationValues{}, errors.New("verification inputs are invalid")
	}
	quantity, ok := readVerificationInteger(
		inputs[0],
		"input",
		"quantity",
	)
	if !ok || quantity != 2 {
		return verificationValues{}, errors.New("verification quantity is unsupported")
	}
	unitPriceCents, ok := readVerificationInteger(
		inputs[1],
		"input",
		"unit-price-cents",
	)
	if !ok || unitPriceCents != 1250 {
		return verificationValues{}, errors.New("verification unit price is unsupported")
	}
	outputs, ok := request["expected_outputs"].([]any)
	if !ok || len(outputs) != 1 {
		return verificationValues{}, errors.New("verification outputs are invalid")
	}
	expectedTotalCents, ok := readVerificationInteger(
		outputs[0],
		"output",
		"total-cents",
	)
	if !ok || expectedTotalCents < 0 {
		return verificationValues{}, errors.New("verification total is unsupported")
	}
	return verificationValues{
		quantity:           quantity,
		unitPriceCents:     unitPriceCents,
		expectedTotalCents: expectedTotalCents,
	}, nil
}

func (instance *server) verificationMappingContext(
	mapping map[string]any,
	run *inventoryRun,
) (map[string]any, error) {
	if !hasExactKeys(
		mapping,
		"bindings",
		"capability",
		"id",
		"implementation_evidence_version",
		"kind",
		"procedure_uri",
		"producer",
		"request",
		"schema_uri",
		"status",
	) ||
		mapping["kind"] != "implementation_mapping_result" ||
		mapping["implementation_evidence_version"] != mappingVersion ||
		mapping["schema_uri"] != mappingResultSchemaURI ||
		mapping["status"] != "complete" ||
		!sameCanonicalLogicalValue(mapping["producer"], inventoryProducer()) ||
		!sameCanonicalLogicalValue(mapping["capability"], mappingCapability()) ||
		mapping["procedure_uri"] != mappingAdapterProcedureURI {
		return nil, errors.New("verification mapping is invalid")
	}
	mappingRequest, ok := mapping["request"].(map[string]any)
	if !ok || !sameCanonicalLogicalValue(
		mappingRequest["inventory"],
		run.snapshot,
	) {
		return nil, errors.New("verification mapping inventory is stale")
	}
	bindings, ok := mapping["bindings"].([]any)
	if !ok || len(bindings) != 1 {
		return nil, errors.New("verification mapping binding is missing")
	}
	binding, ok := bindings[0].(map[string]any)
	if !ok || !hasExactKeys(
		binding,
		"behavior",
		"kind",
		"source_records",
	) ||
		binding["kind"] != "implementation_binding" {
		return nil, errors.New("verification mapping binding is invalid")
	}
	subject, ok := binding["behavior"].(map[string]any)
	sourceRecords, recordsOK := binding["source_records"].([]any)
	expectedSourceRecords, sourceErr := instance.quoteOrderImplementationEvidence(
		run.records,
	)
	if sourceErr != nil || !ok || !recordsOK ||
		!sameCanonicalLogicalValue(sourceRecords, expectedSourceRecords) ||
		subject["target_kind"] != "use_case" ||
		subject["target_id"] != quoteOrderUseCaseID {
		return nil, errors.New("verification mapping subject is unsupported")
	}
	mappingDigest, err := canonicalLogicalDigest(mapping)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"mapping": map[string]any{
			"kind":             "implementation_mapping_result_ref",
			"schema_uri":       mappingResultSchemaURI,
			"schema_version":   mappingVersion,
			"target_id":        mapping["id"],
			"canonical_digest": digestValue(mappingDigest),
		},
		"base_behavior": map[string]any{
			"kind":             "behavior_document_ref",
			"document_id":      subject["document_id"],
			"ir_version":       subject["ir_version"],
			"canonical_digest": subject["canonical_digest"],
		},
		"subject": subject,
		"source": map[string]any{
			"kind":            "implementation_source",
			"subject_uri":     run.snapshot["subject_uri"],
			"source_revision": run.snapshot["source_revision"],
			"records":         sourceRecords,
		},
	}, nil
}

func readVerificationInteger(
	value any,
	direction string,
	name string,
) (int, bool) {
	entry, ok := value.(map[string]any)
	if !ok || !hasExactKeys(entry, "kind", "port", "value") ||
		entry["kind"] != "execution_port_value" {
		return 0, false
	}
	expectedPort := map[string]any{
		"kind": "port_ref",
		"owner": map[string]any{
			"kind":        "entity_ref",
			"target_kind": "use_case",
			"target_id":   quoteOrderUseCaseID,
		},
		"direction": direction,
		"name":      name,
	}
	integer, ok := entry["value"].(map[string]any)
	if !ok || !sameCanonicalLogicalValue(entry["port"], expectedPort) ||
		!hasExactKeys(integer, "kind", "value") ||
		integer["kind"] != "integer" {
		return 0, false
	}
	result, ok := integer["value"].(int)
	return result, ok
}

func verificationCapability() map[string]any {
	return map[string]any{
		"kind":    "capability",
		"name":    "org.ucf.adapter.verification",
		"version": verificationVersion,
	}
}

func verificationCheck(
	procedure verificationProcedureSpec,
) map[string]any {
	return map[string]any{
		"kind":          "check",
		"id":            procedure.checkID,
		"version":       verificationVersion,
		"procedure_uri": procedure.checkProcedureURI,
	}
}

func (instance *server) executeVerificationProcedure(
	parent context.Context,
	procedure verificationProcedureSpec,
	values verificationValues,
	executable string,
) (string, error) {
	switch procedure.adapterProcedureURI {
	case verificationAdapterProcedureURI:
		return executeQuoteOrderCheck(
			parent,
			executable,
			values,
		)
	case cliVerificationAdapterProcedureURI:
		return executeCLIQuoteOrderCheck(
			parent,
			executable,
			values,
		)
	case eventVerificationAdapterProcedureURI:
		return executeEventQuoteOrderCheck(
			parent,
			executable,
			values,
		)
	default:
		return "error", errors.New("unsupported verification procedure")
	}
}

func executeQuoteOrderCheck(
	parent context.Context,
	executable string,
	values verificationValues,
) (result string, resultErr error) {
	contextValue, cancel := context.WithTimeout(
		parent,
		verificationDeadline,
	)
	defer cancel()
	command := exec.Command(
		executable,
		"--listen",
		"127.0.0.1:0",
	)
	command.Env = []string{}
	command.SysProcAttr = &syscall.SysProcAttr{
		Setpgid:   true,
		Pdeathsig: syscall.SIGKILL,
	}
	pipes, err := openVerificationOutputPipes(command)
	if err != nil {
		return "error", err
	}
	owner, err := startVerificationProcess(command)
	if err != nil {
		return "error", errors.Join(err, pipes.closeAll())
	}
	writerCloseErr := pipes.closeWriters()
	waited := make(chan error, 1)
	go func() {
		waited <- command.Wait()
	}()
	if writerCloseErr != nil {
		cleanupErr := stopOwnedVerificationProcess(
			command,
			waited,
			owner,
		)
		return "error", errors.Join(
			writerCloseErr,
			cleanupErr,
			pipes.closeReaders(),
		)
	}
	defer func() {
		if closeErr := pipes.closeReaders(); closeErr != nil {
			result = "error"
			resultErr = errors.Join(resultErr, closeErr)
		}
	}()
	stdout := pipes.stdoutReader
	stderr := pipes.stderrReader
	stderrResult := make(chan boundedStream, 1)
	go func() {
		stderrResult <- readBoundedStream(stderr)
	}()
	reader := bufio.NewReaderSize(stdout, 4096)
	readinessResult := make(chan boundedStream, 1)
	go func() {
		readinessResult <- readReadinessLine(reader)
	}()

	var readiness boundedStream
	select {
	case readiness = <-readinessResult:
	case <-contextValue.Done():
		cleanupErr := stopOwnedVerificationProcess(
			command,
			waited,
			owner,
		)
		readerCloseErr := error(nil)
		if errors.Is(cleanupErr, errVerificationCleanup) {
			readerCloseErr = pipes.closeReaders()
		}
		readiness = <-readinessResult
		stderrValue := <-stderrResult
		return "error", errors.Join(
			contextValue.Err(),
			cleanupErr,
			readerCloseErr,
			readiness.err,
			stderrValue.err,
		)
	}
	extraOutput := make(chan boundedStream, 1)
	go func() {
		extraOutput <- readBoundedStream(reader)
	}()
	address, readinessOK := verificationAddress(readiness)
	outcome := "error"
	if readinessOK {
		outcome, err = executeVerificationHTTP(
			contextValue,
			address,
			values,
		)
	}
	cleanupErr := stopOwnedVerificationProcess(
		command,
		waited,
		owner,
	)
	readerCloseErr := error(nil)
	if errors.Is(cleanupErr, errVerificationCleanup) {
		readerCloseErr = pipes.closeReaders()
	}
	stderrValue := <-stderrResult
	stdoutValue := <-extraOutput
	if err != nil ||
		cleanupErr != nil ||
		readerCloseErr != nil ||
		readiness.err != nil ||
		readiness.overflow ||
		stderrValue.err != nil ||
		stderrValue.overflow ||
		len(stderrValue.payload) != 0 ||
		stdoutValue.err != nil ||
		stdoutValue.overflow ||
		len(stdoutValue.payload) != 0 {
		return "error", errors.Join(
			errors.New("verification process failed"),
			err,
			cleanupErr,
			readerCloseErr,
			readiness.err,
			stderrValue.err,
			stdoutValue.err,
		)
	}
	return outcome, nil
}

func readReadinessLine(reader *bufio.Reader) boundedStream {
	payload := make([]byte, 0, reader.Size())
	for {
		fragment, err := reader.ReadSlice('\n')
		remaining := maxVerificationOutputBytes + 1 - len(payload)
		if remaining > 0 {
			retained := min(len(fragment), remaining)
			payload = append(payload, fragment[:retained]...)
		}
		if len(payload) > maxVerificationOutputBytes ||
			len(fragment) > remaining {
			return boundedStream{
				payload:  payload[:maxVerificationOutputBytes],
				overflow: true,
				err:      err,
			}
		}
		if err == nil {
			return boundedStream{payload: payload}
		}
		if !errors.Is(err, bufio.ErrBufferFull) {
			return boundedStream{payload: payload, err: err}
		}
	}
}

func readBoundedStream(reader io.Reader) boundedStream {
	limited := io.LimitReader(reader, maxVerificationOutputBytes+1)
	payload, err := io.ReadAll(limited)
	if len(payload) > maxVerificationOutputBytes {
		return boundedStream{
			payload:  payload[:maxVerificationOutputBytes],
			overflow: true,
			err:      err,
		}
	}
	return boundedStream{payload: payload, err: err}
}

func verificationAddress(value boundedStream) (string, bool) {
	if value.err != nil || value.overflow ||
		!bytes.HasPrefix(value.payload, []byte("READY http://127.0.0.1:")) ||
		len(value.payload) < len("READY http://127.0.0.1:1\n") ||
		value.payload[len(value.payload)-1] != '\n' {
		return "", false
	}
	portText := strings.TrimSuffix(
		strings.TrimPrefix(
			string(value.payload),
			"READY http://127.0.0.1:",
		),
		"\n",
	)
	if len(portText) > 5 || strings.HasPrefix(portText, "0") {
		return "", false
	}
	port, err := strconv.Atoi(portText)
	if err != nil || port < 1 || port > 65_535 {
		return "", false
	}
	return net.JoinHostPort("127.0.0.1", portText), true
}

func executeVerificationHTTP(
	parent context.Context,
	address string,
	values verificationValues,
) (string, error) {
	contextValue, cancel := context.WithTimeout(
		parent,
		verificationPhaseDeadline,
	)
	defer cancel()
	body, ok := appendCanonicalJSON(nil, map[string]any{
		"quantity":         values.quantity,
		"unit_price_cents": values.unitPriceCents,
	})
	if !ok {
		return "error", errors.New("verification request cannot be encoded")
	}
	request, err := http.NewRequestWithContext(
		contextValue,
		http.MethodPost,
		"http://"+address+"/quote-order",
		bytes.NewReader(body),
	)
	if err != nil {
		return "error", err
	}
	request.Header.Set("content-type", "application/json")
	transport := &http.Transport{
		Proxy:             nil,
		DisableKeepAlives: true,
		DialContext: (&net.Dialer{
			Timeout: verificationPhaseDeadline,
		}).DialContext,
	}
	client := &http.Client{Transport: transport}
	response, err := client.Do(request)
	if err != nil {
		return "error", err
	}
	defer response.Body.Close()
	payload, err := io.ReadAll(
		io.LimitReader(
			response.Body,
			maxVerificationOutputBytes+1,
		),
	)
	if err != nil || len(payload) > maxVerificationOutputBytes {
		return "error", errors.New("verification response is outside the byte limit")
	}
	decoded, err := parseStrictJSON(payload)
	if err != nil {
		return "error", err
	}
	result, ok := decoded.(map[string]any)
	if !ok {
		return "error", errors.New("verification response is not an object")
	}
	if response.StatusCode != http.StatusOK ||
		response.Header.Get("content-type") != "application/json" ||
		!hasExactKeys(result, "receipt", "total_cents") {
		return "failed", nil
	}
	receipt, receiptOK := result["receipt"].(string)
	total, totalOK := result["total_cents"].(json.Number)
	expectedText := strconv.Itoa(values.expectedTotalCents)
	if !receiptOK || receipt != "Total: 25.00" ||
		!totalOK || total.String() != expectedText {
		return "failed", nil
	}
	return "passed", nil
}

func stopOwnedVerificationProcess(
	command *exec.Cmd,
	waited <-chan error,
	owner *verificationProcessOwner,
) error {
	return stopVerificationProcessWithinOwned(
		command,
		waited,
		owner,
		verificationTerminationGrace,
		verificationCleanupDeadline,
	)
}

func stopVerificationProcessWithinOwned(
	command *exec.Cmd,
	waited <-chan error,
	owner *verificationProcessOwner,
	terminationGrace time.Duration,
	cleanupDeadline time.Duration,
) error {
	if command == nil ||
		command.Process == nil ||
		waited == nil ||
		terminationGrace < 0 ||
		cleanupDeadline <= terminationGrace {
		return errors.Join(
			errVerificationCleanup,
			errors.New("verification cleanup configuration is invalid"),
		)
	}
	processID := command.Process.Pid
	startedAt := time.Now()
	graceDeadline := startedAt.Add(terminationGrace)
	absoluteDeadline := startedAt.Add(cleanupDeadline)
	var waitErr error
	leaderDone := false
	var cleanupErr error
	if err := signalVerificationProcessGroup(
		processID,
		syscall.SIGTERM,
	); err != nil {
		cleanupErr = errors.Join(cleanupErr, err)
	}
	if err := owner.signalDescendants(syscall.SIGTERM); err != nil {
		cleanupErr = errors.Join(cleanupErr, err)
	}
	killSent := false
	for {
		if !leaderDone {
			select {
			case waitErr = <-waited:
				leaderDone = true
			default:
			}
		}
		groupGone, groupErr := verificationProcessGroupGone(processID)
		if groupErr != nil {
			cleanupErr = errors.Join(cleanupErr, groupErr)
		}
		descendantsGone, descendantsErr := owner.descendantsGone()
		if descendantsErr != nil {
			cleanupErr = errors.Join(cleanupErr, descendantsErr)
		}
		if leaderDone && groupGone && descendantsGone {
			if cleanupErr != nil {
				return errors.Join(
					waitErr,
					errVerificationCleanup,
					cleanupErr,
				)
			}
			return waitErr
		}

		now := time.Now()
		if !killSent && !now.Before(graceDeadline) {
			if err := signalVerificationProcessGroup(
				processID,
				syscall.SIGKILL,
			); err != nil {
				cleanupErr = errors.Join(cleanupErr, err)
			}
			if err := owner.signal(syscall.SIGKILL); err != nil {
				cleanupErr = errors.Join(cleanupErr, err)
			}
			killSent = true
		} else if killSent {
			if err := owner.signal(syscall.SIGKILL); err != nil {
				cleanupErr = errors.Join(cleanupErr, err)
			}
		}
		if !now.Before(absoluteDeadline) {
			if !leaderDone {
				cleanupErr = errors.Join(
					cleanupErr,
					errors.New("verification process leader did not exit"),
				)
			}
			if !groupGone {
				cleanupErr = errors.Join(
					cleanupErr,
					errors.New("verification process group did not exit"),
				)
			}
			if !descendantsGone {
				cleanupErr = errors.Join(
					cleanupErr,
					errors.New(
						"verification process descendants did not exit",
					),
				)
			}
			return errors.Join(
				waitErr,
				errVerificationCleanup,
				cleanupErr,
			)
		}

		wakeAfter := verificationCleanupPollInterval
		if !killSent {
			wakeAfter = min(
				wakeAfter,
				time.Until(graceDeadline),
			)
		}
		wakeAfter = min(wakeAfter, time.Until(absoluteDeadline))
		if wakeAfter <= 0 {
			continue
		}
		timer := time.NewTimer(wakeAfter)
		if leaderDone {
			<-timer.C
			continue
		}
		select {
		case waitErr = <-waited:
			leaderDone = true
			if !timer.Stop() {
				<-timer.C
			}
		case <-timer.C:
		}
	}
}

func signalVerificationProcessGroup(
	processID int,
	signal syscall.Signal,
) error {
	err := syscall.Kill(-processID, signal)
	if err == nil || errors.Is(err, syscall.ESRCH) {
		return nil
	}
	return err
}

func verificationProcessGroupGone(processID int) (bool, error) {
	err := syscall.Kill(-processID, 0)
	if errors.Is(err, syscall.ESRCH) {
		return true, nil
	}
	if err != nil {
		return false, err
	}
	return false, nil
}

func buildVerificationResult(
	request map[string]any,
	outcome string,
	executedAt string,
	procedure verificationProcedureSpec,
) (map[string]any, error) {
	if outcome != "passed" && outcome != "failed" && outcome != "error" {
		return nil, errors.New("verification outcome is invalid")
	}
	projection := map[string]any{
		"kind":                            "execution_verification_result",
		"implementation_evidence_version": verificationVersion,
		"schema_uri":                      verificationResultSchemaURI,
		"status":                          "completed",
		"request":                         request,
		"outcome":                         outcome,
		"executed_at":                     executedAt,
		"producer":                        inventoryProducer(),
		"capability":                      verificationCapability(),
		"procedure_uri":                   procedure.adapterProcedureURI,
	}
	digest, err := canonicalLogicalDigest(projection)
	if err != nil {
		return nil, err
	}
	result := make(map[string]any, len(projection)+1)
	for name, value := range projection {
		result[name] = value
	}
	result["id"] = "result." + digest
	return result, nil
}
