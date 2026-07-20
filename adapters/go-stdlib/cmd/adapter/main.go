package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

const (
	protocolVersion              = "1.0.0"
	controlSchemaURI             = "urn:ucf:adapter-conformance:control:1.0.0"
	httpLoopbackCapabilityName   = "org.ucf.platform.http-loopback"
	cliProcessCapabilityName     = "org.ucf.platform.cli-process"
	fileSpoolEventCapabilityName = "org.ucf.platform.file-spool-event"
	maxFrameBytes                = 1_048_576
	maxPending                   = 64
	maxRequests                  = 65_536
)

var (
	requestIDPattern     = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$`)
	versionPattern       = regexp.MustCompile(`^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$`)
	qualifiedNamePattern = regexp.MustCompile(
		`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$`,
	)
	identifierPattern = regexp.MustCompile(
		`^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$`,
	)
	integerPattern = regexp.MustCompile(`^(?:0|-[1-9][0-9]*|[1-9][0-9]*)$`)
	decimalPattern = regexp.MustCompile(
		`^(?:0|[1-9][0-9]*|-[1-9][0-9]*|-?(?:0|[1-9][0-9]*)\.[0-9]*[1-9])$`,
	)
	timestampPattern = regexp.MustCompile(
		`^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$`,
	)
	uriPattern         = regexp.MustCompile(`^[a-z][a-z0-9+.-]*:[^\s]+$`)
	capabilityByMethod = map[string]string{
		"ucf.inventory": "org.ucf.adapter.inventory",
		"ucf.discover":  "org.ucf.adapter.discovery",
		"ucf.map":       "org.ucf.adapter.mapping",
		"ucf.generate":  "org.ucf.adapter.generation",
		"ucf.verify":    "org.ucf.adapter.verification",
	}
	resultKindByMethod = map[string]string{
		"ucf.inventory": "inventory_result",
		"ucf.discover":  "discover_result",
		"ucf.map":       "map_result",
		"ucf.generate":  "generate_result",
		"ucf.verify":    "verify_result",
	}
)

type server struct {
	writer               *bufio.Writer
	lifecycle            string
	conformanceMode      bool
	platformMode         bool
	fixtureExecutable    string
	selectedCapabilities map[string]bool
	seenRequestIDs       map[string]bool
	inventoryRun         *inventoryRun
	mappingResult        map[string]any
	operationMu          sync.Mutex
	operationCond        *sync.Cond
	operationJobs        map[string]*operationJob
	operationQueue       []*operationJob
	operationDone        chan struct{}
	operationStopping    bool
	writeMu              sync.Mutex
	acceptedRequests     int
	closed               bool
}

func main() {
	conformanceMode, platformMode, fixtureExecutable, validArguments := adapterMode(
		os.Args[1:],
	)
	if !validArguments {
		os.Exit(2)
	}
	instance := &server{
		writer:               bufio.NewWriter(os.Stdout),
		lifecycle:            "new",
		conformanceMode:      conformanceMode,
		platformMode:         platformMode,
		fixtureExecutable:    fixtureExecutable,
		selectedCapabilities: map[string]bool{},
		seenRequestIDs:       map[string]bool{},
	}
	instance.startOperationRunner()
	serveInput(instance, os.Stdin)
	instance.stopOperationRunner()
}

func serveInput(instance *server, input io.Reader) {
	reader := bufio.NewReaderSize(input, 64*1024)
	frame := make([]byte, 0, 64*1024)
	discardingOversizedFrame := false
	for {
		fragment, err := reader.ReadSlice('\n')
		switch {
		case discardingOversizedFrame:
			if err == nil {
				discardingOversizedFrame = false
			}
		case len(frame)+len(fragment) > maxFrameBytes:
			frame = frame[:0]
			instance.writeError(nil, "frame_too_large", "protocol frame exceeds the byte limit")
			discardingOversizedFrame = errors.Is(err, bufio.ErrBufferFull)
		default:
			frame = append(frame, fragment...)
			if err == nil {
				handleFrame(instance, frame[:len(frame)-1])
				frame = frame[:0]
				if instance.closed {
					return
				}
			}
		}

		if err == nil || errors.Is(err, bufio.ErrBufferFull) {
			continue
		}
		if errors.Is(err, io.EOF) {
			if !discardingOversizedFrame && len(frame) != 0 {
				instance.writeError(nil, "truncated_frame", "protocol frame is not terminated by LF")
			}
			return
		}
		instance.writeError(nil, "invalid_message", "protocol input failed")
		return
	}
}

func handleFrame(instance *server, frame []byte) {
	if len(frame) == 0 {
		instance.writeError(nil, "invalid_message", "empty protocol frame")
		return
	}
	decoded, err := parseStrictJSON(bytes.Clone(frame))
	if err != nil {
		instance.writeError(nil, "parse_error", "invalid JSON input")
		return
	}
	instance.handle(decoded)
}

func parseStrictJSON(raw []byte) (any, error) {
	if !utf8.Valid(raw) || bytes.HasPrefix(raw, []byte{0xef, 0xbb, 0xbf}) {
		return nil, errors.New("invalid UTF-8")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	value, err := parseJSONValue(decoder, 0)
	if err != nil {
		return nil, err
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		if err == nil {
			return nil, errors.New("trailing JSON content")
		}
		return nil, err
	}
	return value, nil
}

func parseJSONValue(decoder *json.Decoder, depth int) (any, error) {
	if depth > 128 {
		return nil, errors.New("JSON nesting exceeds 128")
	}
	token, err := decoder.Token()
	if err != nil {
		return nil, err
	}
	delimiter, isDelimiter := token.(json.Delim)
	if !isDelimiter {
		if number, ok := token.(json.Number); ok {
			text := number.String()
			if !integerPattern.MatchString(text) || text == "-0" {
				return nil, errors.New("number is outside the integer profile")
			}
			value, err := strconv.ParseInt(text, 10, 64)
			if err != nil || value < -9_007_199_254_740_991 || value > 9_007_199_254_740_991 {
				return nil, errors.New("integer is outside the safe range")
			}
		}
		return token, nil
	}
	switch delimiter {
	case '{':
		result := map[string]any{}
		for decoder.More() {
			nameToken, err := decoder.Token()
			if err != nil {
				return nil, err
			}
			name, ok := nameToken.(string)
			if !ok {
				return nil, errors.New("object member must be a string")
			}
			if _, duplicate := result[name]; duplicate {
				return nil, errors.New("duplicate object member")
			}
			value, err := parseJSONValue(decoder, depth+1)
			if err != nil {
				return nil, err
			}
			result[name] = value
		}
		if token, err := decoder.Token(); err != nil || token != json.Delim('}') {
			return nil, errors.New("invalid object end")
		}
		return result, nil
	case '[':
		result := []any{}
		for decoder.More() {
			value, err := parseJSONValue(decoder, depth+1)
			if err != nil {
				return nil, err
			}
			result = append(result, value)
		}
		if token, err := decoder.Token(); err != nil || token != json.Delim(']') {
			return nil, errors.New("invalid array end")
		}
		return result, nil
	default:
		return nil, errors.New("unexpected closing delimiter")
	}
}

func (instance *server) handle(value any) {
	message, ok := value.(map[string]any)
	if !ok {
		instance.writeError(nil, "invalid_message", "request root must be an object")
		return
	}
	if _, hasID := message["id"]; !hasID {
		if method, _ := message["method"].(string); method == "ucf.cancel" {
			instance.cancel(message)
		} else {
			instance.writeError(nil, "invalid_message", "only ucf.cancel may be a notification")
		}
		return
	}
	id, validID := message["id"].(string)
	method, validMethod := message["method"].(string)
	params, validParams := message["params"].(map[string]any)
	if !hasExactKeys(message, "id", "jsonrpc", "method", "params") ||
		message["jsonrpc"] != "2.0" || !validID || !requestIDPattern.MatchString(id) ||
		!validMethod || !validParams {
		instance.writeError(recoverRequestID(message), "invalid_message", "invalid request envelope")
		return
	}
	if !knownMethod(method) {
		instance.writeError(id, "method_not_found", "unknown adapter method")
		return
	}
	if instance.seenRequestIDs[id] {
		instance.writeError(id, "duplicate_request_id", "request id was already used in this session")
		return
	}
	if !instance.acceptRequest(method) {
		instance.writeError(id, "session_request_limit", "session request limit was reached")
		return
	}
	instance.seenRequestIDs[id] = true
	switch method {
	case "ucf.initialize":
		instance.initialize(id, params)
	case "ucf.shutdown":
		instance.shutdown(id, params)
	default:
		instance.operation(id, method, params)
	}
}

func (instance *server) acceptRequest(method string) bool {
	if instance.acceptedRequests >= maxRequests ||
		(instance.acceptedRequests == maxRequests-1 &&
			method != "ucf.shutdown") {
		return false
	}
	instance.acceptedRequests++
	return true
}

func (instance *server) initialize(id string, params map[string]any) {
	if instance.lifecycle != "new" {
		instance.writeError(id, "invalid_lifecycle", "initialize requires new state")
		return
	}
	capabilities, capabilitiesOK := params["capabilities"].([]any)
	client, clientOK := params["client"].(map[string]any)
	version, versionOK := params["protocol_version"].(string)
	if !hasExactKeys(params, "capabilities", "client", "kind", "protocol_version") ||
		params["kind"] != "initialize_request" || !versionOK || !versionPattern.MatchString(version) ||
		!clientOK || !validProducer(client) || !capabilitiesOK {
		instance.writeError(id, "invalid_params", "invalid initialize parameters")
		return
	}
	if version != protocolVersion {
		instance.writeError(id, "incompatible_version", "adapter protocol version is incompatible")
		return
	}
	seenCapabilities := map[string]bool{}
	selectedCapabilities := map[string]bool{}
	selections := []any{}
	for _, item := range capabilities {
		request, ok := item.(map[string]any)
		if !ok || !validCapabilityRequest(request) {
			instance.writeError(id, "invalid_params", "invalid initialize parameters")
			return
		}
		name := request["name"].(string)
		if seenCapabilities[name] {
			instance.writeError(id, "duplicate_capability", "capability requests must be unique")
			return
		}
		seenCapabilities[name] = true
		minimumVersion := request["minimum_version"].(string)
		supported := instance.supportsCapability(name) &&
			compareNormalizedVersions(minimumVersion, "1.0.0") <= 0
		if !supported && request["required"].(bool) {
			instance.writeError(id, "unsupported_capability", "required capability is unavailable")
			return
		}
		if supported {
			selectedCapabilities[name] = true
			selections = append(selections, map[string]any{
				"kind":    "capability",
				"name":    name,
				"version": "1.0.0",
			})
		}
	}
	sort.Slice(selections, func(left int, right int) bool {
		leftName := selections[left].(map[string]any)["name"].(string)
		rightName := selections[right].(map[string]any)["name"].(string)
		return leftName < rightName
	})
	instance.selectedCapabilities = selectedCapabilities
	instance.lifecycle = "ready"
	instance.write(map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"result": map[string]any{
			"kind":             "initialize_result",
			"protocol_version": protocolVersion,
			"adapter": map[string]any{
				"kind":    "producer",
				"name":    "org.ucf.adapter.go-stdlib",
				"version": "1.0.0",
			},
			"capabilities": selections,
		},
	})
}

func (instance *server) operation(id string, method string, params map[string]any) {
	if instance.lifecycle != "ready" {
		instance.writeError(id, "invalid_lifecycle", "operation requires ready state")
		return
	}
	capability := capabilityByMethod[method]
	if !instance.selectedCapabilities[capability] {
		instance.writeError(id, "capability_not_negotiated", "operation capability was not negotiated")
		return
	}
	expectedKind := strings.TrimPrefix(method, "ucf.") + "_request"
	payload, payloadOK := params["payload"].(map[string]any)
	if !hasExactKeys(params, "kind", "payload") || params["kind"] != expectedKind || !payloadOK {
		instance.writeError(id, "invalid_params", "operation parameters do not match method")
		return
	}
	if !validAdapterPayload(payload) {
		instance.writeError(id, "invalid_params", "operation payload is invalid")
		return
	}
	control, ok := parseControl(payload)
	if !ok {
		switch method {
		case "ucf.inventory", "ucf.discover", "ucf.map", "ucf.verify":
			if !instance.enqueueOperation(
				id,
				method,
				payload,
				false,
			) {
				instance.writeError(id, "too_many_pending", "adapter pending request limit was reached")
			}
			return
		default:
			instance.writeError(id, "operation_failed", "unsupported conformance control payload")
			return
		}
	}
	if control.operation == "block" {
		if !instance.enqueueOperation(
			id,
			method,
			payload,
			true,
		) {
			instance.writeError(id, "too_many_pending", "adapter pending request limit was reached")
		}
		return
	}
	var entries []any
	if control.operation == "readiness" {
		entries = []any{
			recordEntry("operation", stringValue("readiness_result")),
			recordEntry("target_request_id", stringValue(control.targetRequestID)),
			recordEntry("active", map[string]any{"kind": "boolean", "value": instance.operationActive(control.targetRequestID)}),
		}
	} else {
		entries = []any{
			recordEntry("operation", stringValue("echo_result")),
			recordEntry("value", control.value),
		}
	}
	instance.write(map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"result": map[string]any{
			"kind": resultKindByMethod[method],
			"payload": map[string]any{
				"kind":           "adapter_payload",
				"schema_uri":     controlSchemaURI,
				"schema_version": "1.0.0",
				"value": map[string]any{
					"kind":    "record",
					"entries": entries,
				},
			},
		},
	})
}

type controlRequest struct {
	operation       string
	targetRequestID string
	value           any
}

func validAdapterPayload(payload map[string]any) bool {
	schemaURI, uriOK := payload["schema_uri"].(string)
	schemaVersion, versionOK := payload["schema_version"].(string)
	return hasExactKeys(
		payload,
		"kind",
		"schema_uri",
		"schema_version",
		"value",
	) &&
		payload["kind"] == "adapter_payload" &&
		uriOK && len(schemaURI) <= 2048 && uriPattern.MatchString(schemaURI) &&
		versionOK && versionPattern.MatchString(schemaVersion) &&
		validTaggedValue(payload["value"], 0)
}

func parseControl(payload map[string]any) (controlRequest, bool) {
	if !hasExactKeys(payload, "kind", "schema_uri", "schema_version", "value") ||
		payload["kind"] != "adapter_payload" || payload["schema_uri"] != controlSchemaURI ||
		payload["schema_version"] != "1.0.0" {
		return controlRequest{}, false
	}
	record, ok := payload["value"].(map[string]any)
	if !ok || !validTaggedValue(record, 0) ||
		!hasExactKeys(record, "entries", "kind") ||
		record["kind"] != "record" {
		return controlRequest{}, false
	}
	rawEntries, ok := record["entries"].([]any)
	if !ok {
		return controlRequest{}, false
	}
	entries := map[string]any{}
	for _, raw := range rawEntries {
		entry, ok := raw.(map[string]any)
		if !ok || !hasExactKeys(entry, "kind", "name", "value") || entry["kind"] != "record_entry" {
			return controlRequest{}, false
		}
		name, ok := entry["name"].(string)
		if !ok {
			return controlRequest{}, false
		}
		if _, duplicate := entries[name]; duplicate {
			return controlRequest{}, false
		}
		entries[name] = entry["value"]
	}
	operation, ok := taggedString(entries["operation"])
	if !ok {
		return controlRequest{}, false
	}
	switch operation {
	case "echo":
		value, present := entries["value"]
		if len(entries) != 2 || !present {
			return controlRequest{}, false
		}
		return controlRequest{operation: operation, value: value}, true
	case "block":
		if len(entries) != 1 {
			return controlRequest{}, false
		}
		return controlRequest{operation: operation}, true
	case "readiness":
		target, ok := taggedString(entries["target_request_id"])
		if len(entries) != 2 || !ok || !requestIDPattern.MatchString(target) {
			return controlRequest{}, false
		}
		return controlRequest{operation: operation, targetRequestID: target}, true
	default:
		return controlRequest{}, false
	}
}

func validTaggedValue(value any, depth int) bool {
	if depth > 128 {
		return false
	}
	tagged, ok := value.(map[string]any)
	if !ok {
		return false
	}
	kind, ok := tagged["kind"].(string)
	if !ok {
		return false
	}
	switch kind {
	case "null":
		return hasExactKeys(tagged, "kind")
	case "boolean":
		_, valueOK := tagged["value"].(bool)
		return hasExactKeys(tagged, "kind", "value") && valueOK
	case "integer":
		number, valueOK := tagged["value"].(json.Number)
		return hasExactKeys(tagged, "kind", "value") && valueOK &&
			validSafeInteger(number)
	case "string":
		_, valueOK := tagged["value"].(string)
		return hasExactKeys(tagged, "kind", "value") && valueOK
	case "decimal":
		text, valueOK := tagged["value"].(string)
		return hasExactKeys(tagged, "kind", "value") && valueOK &&
			text != "-0" && decimalPattern.MatchString(text)
	case "timestamp":
		text, valueOK := tagged["value"].(string)
		return hasExactKeys(tagged, "kind", "value") && valueOK &&
			validTimestamp(text)
	case "list":
		items, itemsOK := tagged["items"].([]any)
		if !hasExactKeys(tagged, "items", "kind") || !itemsOK {
			return false
		}
		for _, item := range items {
			if !validTaggedValue(item, depth+1) {
				return false
			}
		}
		return true
	case "record":
		entries, entriesOK := tagged["entries"].([]any)
		if !hasExactKeys(tagged, "entries", "kind") || !entriesOK {
			return false
		}
		seen := map[string]bool{}
		for _, rawEntry := range entries {
			entry, entryOK := rawEntry.(map[string]any)
			if !entryOK ||
				!hasExactKeys(entry, "kind", "name", "value") ||
				entry["kind"] != "record_entry" {
				return false
			}
			name, nameOK := entry["name"].(string)
			if !nameOK || len(name) > 255 ||
				!identifierPattern.MatchString(name) || seen[name] ||
				!validTaggedValue(entry["value"], depth+1) {
				return false
			}
			seen[name] = true
		}
		return true
	default:
		return false
	}
}

func validSafeInteger(number json.Number) bool {
	text := number.String()
	if !integerPattern.MatchString(text) || text == "-0" {
		return false
	}
	value, err := strconv.ParseInt(text, 10, 64)
	return err == nil &&
		value >= -9_007_199_254_740_991 &&
		value <= 9_007_199_254_740_991
}

func validTimestamp(value string) bool {
	if !timestampPattern.MatchString(value) {
		return false
	}
	parsed, err := time.Parse("2006-01-02T15:04:05Z", value)
	return err == nil && parsed.Year() >= 1
}

func (instance *server) cancel(message map[string]any) {
	params, ok := message["params"].(map[string]any)
	if !hasExactKeys(message, "jsonrpc", "method", "params") || message["jsonrpc"] != "2.0" ||
		message["method"] != "ucf.cancel" || !ok || !hasExactKeys(params, "kind", "request_id") ||
		params["kind"] != "cancel_request" {
		instance.writeError(nil, "invalid_message", "invalid cancellation notification")
		return
	}
	target, ok := params["request_id"].(string)
	if !ok || !requestIDPattern.MatchString(target) {
		instance.writeError(nil, "invalid_message", "invalid cancellation notification")
		return
	}
	instance.cancelOperation(target)
}

func (instance *server) shutdown(id string, params map[string]any) {
	if !hasExactKeys(params, "kind") || params["kind"] != "shutdown_request" {
		instance.writeError(id, "invalid_params", "invalid shutdown parameters")
		return
	}
	if instance.lifecycle != "ready" || instance.operationCount() != 0 {
		instance.writeError(id, "invalid_lifecycle", "shutdown requires ready state with no pending operations")
		return
	}
	instance.lifecycle = "closed"
	instance.closed = true
	instance.write(map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"result":  map[string]any{"kind": "shutdown_result"},
	})
}

func (instance *server) writeError(id any, code string, message string) {
	instance.write(map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"error": map[string]any{
			"code":    jsonRPCCode(code),
			"message": message,
			"data": map[string]any{
				"category": categoryFor(code),
				"ucf_code": code,
			},
		},
	})
}

func (instance *server) write(message map[string]any) {
	instance.writeMu.Lock()
	defer instance.writeMu.Unlock()
	encoded, ok := appendCanonicalJSON(nil, message)
	if !ok {
		panic("adapter attempted to encode an unsupported JSON value")
	}
	if len(encoded)+1 > maxFrameBytes {
		var requestID any
		if candidate, valid := message["id"].(string); valid &&
			requestIDPattern.MatchString(candidate) {
			requestID = candidate
		}
		encoded, ok = appendCanonicalJSON(nil, map[string]any{
			"jsonrpc": "2.0",
			"id":      requestID,
			"error": map[string]any{
				"code":    jsonRPCCode("operation_failed"),
				"message": "adapter response exceeds the protocol frame bound",
				"data": map[string]any{
					"category": categoryFor("operation_failed"),
					"ucf_code": "operation_failed",
				},
			},
		})
		if !ok || len(encoded)+1 > maxFrameBytes {
			panic("adapter could not encode a bounded error response")
		}
	}
	if _, err := instance.writer.Write(encoded); err != nil {
		panic(err)
	}
	if err := instance.writer.WriteByte('\n'); err != nil {
		panic(err)
	}
	if err := instance.writer.Flush(); err != nil {
		panic(err)
	}
}

func appendCanonicalJSON(destination []byte, value any) ([]byte, bool) {
	switch typed := value.(type) {
	case nil:
		return append(destination, "null"...), true
	case bool:
		if typed {
			return append(destination, "true"...), true
		}
		return append(destination, "false"...), true
	case int:
		return strconv.AppendInt(destination, int64(typed), 10), true
	case json.Number:
		if !validSafeInteger(typed) {
			return destination, false
		}
		return append(destination, typed.String()...), true
	case string:
		return appendJSONString(destination, typed), true
	case []any:
		destination = append(destination, '[')
		for index, item := range typed {
			if index != 0 {
				destination = append(destination, ',')
			}
			var ok bool
			destination, ok = appendCanonicalJSON(destination, item)
			if !ok {
				return destination, false
			}
		}
		return append(destination, ']'), true
	case map[string]any:
		names := make([]string, 0, len(typed))
		for name := range typed {
			names = append(names, name)
		}
		sort.Strings(names)
		destination = append(destination, '{')
		for index, name := range names {
			if index != 0 {
				destination = append(destination, ',')
			}
			destination = appendJSONString(destination, name)
			destination = append(destination, ':')
			var ok bool
			destination, ok = appendCanonicalJSON(destination, typed[name])
			if !ok {
				return destination, false
			}
		}
		return append(destination, '}'), true
	default:
		return destination, false
	}
}

func appendJSONString(destination []byte, value string) []byte {
	destination = append(destination, '"')
	for _, character := range value {
		switch character {
		case '"', '\\':
			destination = append(destination, '\\', byte(character))
		case '\b':
			destination = append(destination, '\\', 'b')
		case '\f':
			destination = append(destination, '\\', 'f')
		case '\n':
			destination = append(destination, '\\', 'n')
		case '\r':
			destination = append(destination, '\\', 'r')
		case '\t':
			destination = append(destination, '\\', 't')
		default:
			switch {
			case character < 0x20:
				destination = appendUnicodeEscape(
					destination,
					uint16(character),
				)
			case character <= 0x7f:
				destination = append(destination, byte(character))
			case character <= 0xffff:
				destination = appendUnicodeEscape(
					destination,
					uint16(character),
				)
			default:
				scalar := character - 0x10000
				destination = appendUnicodeEscape(
					destination,
					uint16(0xd800+(scalar>>10)),
				)
				destination = appendUnicodeEscape(
					destination,
					uint16(0xdc00+(scalar&0x3ff)),
				)
			}
		}
	}
	return append(destination, '"')
}

func appendUnicodeEscape(destination []byte, value uint16) []byte {
	const hexadecimal = "0123456789abcdef"
	return append(
		destination,
		'\\',
		'u',
		hexadecimal[(value>>12)&0xf],
		hexadecimal[(value>>8)&0xf],
		hexadecimal[(value>>4)&0xf],
		hexadecimal[value&0xf],
	)
}

func hasExactKeys(value map[string]any, expected ...string) bool {
	if len(value) != len(expected) {
		return false
	}
	actual := make([]string, 0, len(value))
	for key := range value {
		actual = append(actual, key)
	}
	sort.Strings(actual)
	wanted := append([]string(nil), expected...)
	sort.Strings(wanted)
	for index := range actual {
		if actual[index] != wanted[index] {
			return false
		}
	}
	return true
}

func validProducer(value map[string]any) bool {
	name, nameOK := value["name"].(string)
	version, versionOK := value["version"].(string)
	return hasExactKeys(value, "kind", "name", "version") && value["kind"] == "producer" &&
		nameOK && len(name) <= 255 && qualifiedNamePattern.MatchString(name) &&
		versionOK && versionPattern.MatchString(version)
}

func validCapabilityRequest(value map[string]any) bool {
	name, nameOK := value["name"].(string)
	version, versionOK := value["minimum_version"].(string)
	_, requiredOK := value["required"].(bool)
	return hasExactKeys(value, "kind", "minimum_version", "name", "required") &&
		value["kind"] == "capability_request" && nameOK && len(name) <= 255 &&
		qualifiedNamePattern.MatchString(name) &&
		versionOK && versionPattern.MatchString(version) && requiredOK
}

func (instance *server) supportsCapability(name string) bool {
	if !instance.conformanceMode {
		switch name {
		case "org.ucf.adapter.inventory",
			"org.ucf.adapter.discovery",
			"org.ucf.adapter.mapping":
			return true
		case "org.ucf.adapter.verification":
			return instance.verificationExecutableAvailable()
		case httpLoopbackCapabilityName:
			return !instance.platformMode &&
				instance.verificationExecutableAvailable()
		case cliProcessCapabilityName, fileSpoolEventCapabilityName:
			return instance.platformMode &&
				instance.verificationExecutableAvailable()
		default:
			return false
		}
	}
	for _, capability := range capabilityByMethod {
		if name == capability {
			return true
		}
	}
	return false
}

func adapterMode(arguments []string) (bool, bool, string, bool) {
	switch {
	case len(arguments) == 0:
		return false, false, "", true
	case len(arguments) == 1 && arguments[0] == "--conformance":
		return true, false, "", true
	case len(arguments) == 2 &&
		arguments[0] == "--fixture-executable" &&
		arguments[1] != "":
		return false, false, arguments[1], true
	case len(arguments) == 2 &&
		arguments[0] == "--platform-fixture-executable" &&
		arguments[1] != "":
		return false, true, arguments[1], true
	default:
		return false, false, "", false
	}
}

func syncNewCond(lock *sync.Mutex) *sync.Cond {
	return sync.NewCond(lock)
}

func compareNormalizedVersions(left string, right string) int {
	leftParts := strings.Split(left, ".")
	rightParts := strings.Split(right, ".")
	for index := range leftParts {
		switch {
		case len(leftParts[index]) < len(rightParts[index]):
			return -1
		case len(leftParts[index]) > len(rightParts[index]):
			return 1
		case leftParts[index] < rightParts[index]:
			return -1
		case leftParts[index] > rightParts[index]:
			return 1
		}
	}
	return 0
}

func knownMethod(method string) bool {
	return method == "ucf.initialize" || method == "ucf.shutdown" || capabilityByMethod[method] != ""
}

func recoverRequestID(message map[string]any) any {
	if id, ok := message["id"].(string); ok && requestIDPattern.MatchString(id) {
		return id
	}
	return nil
}

func taggedString(value any) (string, bool) {
	tagged, ok := value.(map[string]any)
	if !ok || !hasExactKeys(tagged, "kind", "value") || tagged["kind"] != "string" {
		return "", false
	}
	text, ok := tagged["value"].(string)
	return text, ok
}

func recordEntry(name string, value any) map[string]any {
	return map[string]any{"kind": "record_entry", "name": name, "value": value}
}

func stringValue(value string) map[string]any {
	return map[string]any{"kind": "string", "value": value}
}

func jsonRPCCode(code string) int {
	switch code {
	case "parse_error":
		return -32700
	case "invalid_message":
		return -32600
	case "method_not_found":
		return -32601
	case "invalid_params":
		return -32602
	case "internal_error":
		return -32603
	default:
		return -32000
	}
}

func categoryFor(code string) string {
	if code == "request_cancelled" {
		return "cancelled"
	}
	if code == "operation_failed" || code == "internal_error" {
		return "adapter_failure"
	}
	return "protocol_failure"
}

func init() {
	if strconv.IntSize != 64 {
		panic("unsupported integer width")
	}
}
