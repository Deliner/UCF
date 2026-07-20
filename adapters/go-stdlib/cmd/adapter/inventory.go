package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

const (
	inventoryVersion            = "1.0.0"
	inventoryRequestSchemaURI   = "urn:ucf:adapter:inventory-request:1.0.0"
	inventoryPageSchemaURI      = "urn:ucf:adapter:inventory-page:1.0.0"
	inventorySchemaURI          = "urn:ucf:schema:inventory:1.0.0"
	httpInventorySubjectURI     = "urn:ucf:repository:go-stdlib-legacy-quote"
	platformInventorySubjectURI = "urn:ucf:repository:go-stdlib-legacy-platforms"
	inventoryPathIdentity       = "unicode-nfc-ascii-casefold-1"
	inventoryProducerName       = "org.ucf.adapter.go-stdlib"
	inventoryEntryProcedure     = "urn:ucf:inventory-procedure:go-stdlib-read-only-scan:1.0.0"
	inventoryFactProcedure      = "urn:ucf:inventory-procedure:go-stdlib-syntax-classification:1.0.0"
	inventoryConfidenceBasis    = "urn:ucf:inventory-procedure:direct-observation:1.0.0"
	maxFrozenFileBytes          = 1_048_576
)

var inventoryFactKinds = []string{
	"api_description",
	"build_manifest",
	"public_interface",
	"repository_entry",
	"test_asset",
}

type decodedInventoryRequest struct {
	subjectURI    string
	appliedPolicy map[string]any
	recordLimit   int
	cursor        map[string]any
	runKey        string
}

type inventoryRun struct {
	key            string
	entries        []scannedInventoryEntry
	snapshot       map[string]any
	snapshotDigest string
	records        []any
	completed      bool
}

type frozenEntrySpec struct {
	path     string
	kind     string
	children []string
}

type scannedInventoryEntry struct {
	path          string
	kind          string
	size          int
	contentDigest string
	content       []byte
}

var httpFrozenFixtureLayout = []frozenEntrySpec{
	{
		path: ".",
		kind: "directory",
		children: []string{
			".gitignore",
			"README.md",
			"cmd",
			"go.mod",
			"quote",
		},
	},
	{path: ".gitignore", kind: "file"},
	{path: "README.md", kind: "file"},
	{path: "cmd", kind: "directory", children: []string{"server"}},
	{path: "cmd/server", kind: "directory", children: []string{"main.go"}},
	{path: "cmd/server/main.go", kind: "file"},
	{path: "go.mod", kind: "file"},
	{
		path:     "quote",
		kind:     "directory",
		children: []string{"service.go", "service_test.go"},
	},
	{path: "quote/service.go", kind: "file"},
	{path: "quote/service_test.go", kind: "file"},
}

var platformFrozenFixtureLayout = []frozenEntrySpec{
	{
		path: ".",
		kind: "directory",
		children: []string{
			".gitignore",
			"README.md",
			"cmd",
			"go.mod",
			"quote",
			"spool",
		},
	},
	{path: ".gitignore", kind: "file"},
	{path: "README.md", kind: "file"},
	{path: "cmd", kind: "directory", children: []string{"platform"}},
	{
		path:     "cmd/platform",
		kind:     "directory",
		children: []string{"main.go", "main_test.go"},
	},
	{path: "cmd/platform/main.go", kind: "file"},
	{path: "cmd/platform/main_test.go", kind: "file"},
	{path: "go.mod", kind: "file"},
	{
		path:     "quote",
		kind:     "directory",
		children: []string{"service.go", "service_test.go"},
	},
	{path: "quote/service.go", kind: "file"},
	{path: "quote/service_test.go", kind: "file"},
	{
		path:     "spool",
		kind:     "directory",
		children: []string{"spool.go", "spool_test.go"},
	},
	{path: "spool/spool.go", kind: "file"},
	{path: "spool/spool_test.go", kind: "file"},
}

func (instance *server) inventory(
	contextValue context.Context,
	payload map[string]any,
) operationOutcome {
	request, err := decodeInventoryRequest(
		payload,
		instance.inventorySubjectURI(),
	)
	if err != nil {
		return failedOperation(
			"invalid_params",
			"inventory request is outside the Go fixture profile",
		)
	}
	if request.cursor == nil {
		instance.inventoryRun = nil
		instance.mappingResult = nil
	}
	if contextValue.Err() != nil {
		return cancelledOperation()
	}
	root, err := os.OpenRoot(".")
	if err != nil {
		return failedOperation(
			"operation_failed",
			"inventory root is unavailable",
		)
	}
	defer root.Close()

	layout := instance.frozenFixtureLayout()
	entries, err := scanFrozenFixture(root, layout)
	if err != nil {
		if request.cursor != nil {
			instance.inventoryRun = nil
			instance.mappingResult = nil
		}
		return failedOperation(
			"operation_failed",
			"inventory source does not match the frozen fixture",
		)
	}
	if contextValue.Err() != nil {
		return cancelledOperation()
	}
	recheck, err := scanFrozenFixture(root, layout)
	if err != nil || !sameInventoryEntries(entries, recheck) {
		if request.cursor != nil {
			instance.inventoryRun = nil
			instance.mappingResult = nil
		}
		return failedOperation(
			"operation_failed",
			"inventory source changed while it was observed",
		)
	}

	var run *inventoryRun
	if request.cursor == nil {
		classifications, classificationErr := instance.classifyFrozenFixture(
			entries,
		)
		if classificationErr != nil {
			return failedOperation(
				"operation_failed",
				"inventory source is outside the supported Go syntax profile",
			)
		}
		if contextValue.Err() != nil {
			return cancelledOperation()
		}
		run, err = buildFilesystemInventoryRun(
			request,
			entries,
			classifications,
		)
		if err != nil {
			return failedOperation(
				"internal_error",
				"inventory run construction failed",
			)
		}
	} else {
		run = instance.inventoryRun
		if run == nil || run.key != request.runKey {
			return failedOperation(
				"operation_failed",
				"inventory cursor has no matching active snapshot",
			)
		}
		if !sameInventoryEntries(run.entries, entries) {
			instance.inventoryRun = nil
			instance.mappingResult = nil
			return failedOperation(
				"operation_failed",
				"inventory source changed after the active snapshot",
			)
		}
	}
	page, complete, err := buildInventoryPage(request, run)
	if err != nil {
		return failedOperation(
			"operation_failed",
			"inventory cursor cannot advance the active snapshot",
		)
	}
	tagged, ok := encodeProfileValue(page, 0)
	if !ok {
		return failedOperation(
			"internal_error",
			"inventory page cannot be encoded",
		)
	}
	if contextValue.Err() != nil {
		return cancelledOperation()
	}
	run.completed = run.completed || complete
	if request.cursor == nil {
		instance.inventoryRun = run
	}
	return successfulOperation(map[string]any{
		"kind": "inventory_result",
		"payload": map[string]any{
			"kind":           "adapter_payload",
			"schema_uri":     inventoryPageSchemaURI,
			"schema_version": inventoryVersion,
			"value":          tagged,
		},
	})
}

func decodeInventoryRequest(
	payload map[string]any,
	subjectURI string,
) (decodedInventoryRequest, error) {
	if payload["schema_uri"] != inventoryRequestSchemaURI ||
		payload["schema_version"] != inventoryVersion {
		return decodedInventoryRequest{}, errors.New("incompatible inventory payload")
	}
	logical, err := decodeProfileValue(payload["value"], 0)
	if err != nil {
		return decodedInventoryRequest{}, err
	}
	request, ok := logical.(map[string]any)
	if !ok || !hasExactKeys(
		request,
		"fact_kinds",
		"ignore_policy",
		"inventory_version",
		"kind",
		"page",
		"root_path",
		"schema_uri",
		"subject_uri",
	) ||
		request["kind"] != "inventory_request_profile" ||
		request["inventory_version"] != inventoryVersion ||
		request["schema_uri"] != inventoryRequestSchemaURI ||
		request["subject_uri"] != subjectURI ||
		request["root_path"] != "." {
		return decodedInventoryRequest{}, errors.New("invalid inventory request")
	}
	if !exactStringList(request["fact_kinds"], inventoryFactKinds) {
		return decodedInventoryRequest{}, errors.New("invalid inventory fact kinds")
	}
	policy, ok := request["ignore_policy"].(map[string]any)
	if !ok || !hasExactKeys(policy, "kind", "policy_version", "rules") ||
		policy["kind"] != "ignore_policy" ||
		policy["policy_version"] != inventoryVersion {
		return decodedInventoryRequest{}, errors.New("invalid ignore policy")
	}
	rules, ok := policy["rules"].([]any)
	if !ok || len(rules) != 0 {
		return decodedInventoryRequest{}, errors.New("unsupported ignore policy")
	}
	page, ok := request["page"].(map[string]any)
	if !ok || !hasExactKeys(page, "cursor", "kind", "record_limit") ||
		page["kind"] != "inventory_page_request" {
		return decodedInventoryRequest{}, errors.New("invalid page request")
	}
	limit, ok := page["record_limit"].(int)
	if !ok || limit < 1 || limit > 256 {
		return decodedInventoryRequest{}, errors.New("invalid page record limit")
	}
	var cursor map[string]any
	if page["cursor"] != nil {
		cursor, ok = page["cursor"].(map[string]any)
		if !ok || !validInventoryCursor(cursor) {
			return decodedInventoryRequest{}, errors.New("invalid inventory cursor")
		}
	}
	runKey, err := canonicalLogicalDigest(map[string]any{
		"subject_uri":   request["subject_uri"],
		"root_path":     request["root_path"],
		"fact_kinds":    request["fact_kinds"],
		"ignore_policy": policy,
	})
	if err != nil {
		return decodedInventoryRequest{}, errors.New("invalid inventory identity")
	}
	return decodedInventoryRequest{
		subjectURI:    subjectURI,
		appliedPolicy: policy,
		recordLimit:   limit,
		cursor:        cursor,
		runKey:        runKey,
	}, nil
}

func validInventoryCursor(cursor map[string]any) bool {
	if !hasExactKeys(
		cursor,
		"after_id",
		"after_kind",
		"kind",
		"snapshot_digest",
	) || cursor["kind"] != "inventory_cursor" {
		return false
	}
	digest, ok := cursor["snapshot_digest"].(map[string]any)
	if !ok || !hasExactKeys(digest, "algorithm", "kind", "value") ||
		digest["kind"] != "digest" || digest["algorithm"] != "sha-256" {
		return false
	}
	digestText, digestOK := digest["value"].(string)
	kind, kindOK := cursor["after_kind"].(string)
	identifier, identifierOK := cursor["after_id"].(string)
	prefix, prefixOK := inventoryCursorPrefix(kind)
	return digestOK && validSHA256(digestText) &&
		kindOK && identifierOK && prefixOK &&
		strings.HasPrefix(identifier, prefix+".") &&
		validSHA256(strings.TrimPrefix(identifier, prefix+"."))
}

func validSHA256(value string) bool {
	if len(value) != 64 {
		return false
	}
	for _, character := range value {
		if !('0' <= character && character <= '9') &&
			!('a' <= character && character <= 'f') {
			return false
		}
	}
	return true
}

func inventoryCursorPrefix(kind string) (string, bool) {
	switch kind {
	case "api_description":
		return "api", true
	case "build_manifest":
		return "manifest", true
	case "inventory_diagnostic":
		return "diagnostic", true
	case "inventory_ignore_match":
		return "ignore", true
	case "inventory_provenance":
		return "provenance", true
	case "public_interface":
		return "interface", true
	case "repository_entry":
		return "entry", true
	case "test_asset":
		return "test", true
	default:
		return "", false
	}
}

func decodeProfileValue(value any, depth int) (any, error) {
	if depth > 128 {
		return nil, errors.New("profile nesting exceeds 128")
	}
	tagged, ok := value.(map[string]any)
	if !ok {
		return nil, errors.New("profile value is not tagged")
	}
	kind, ok := tagged["kind"].(string)
	if !ok {
		return nil, errors.New("profile value kind is missing")
	}
	switch kind {
	case "null":
		if !hasExactKeys(tagged, "kind") {
			return nil, errors.New("invalid null profile value")
		}
		return nil, nil
	case "boolean":
		item, ok := tagged["value"].(bool)
		if !hasExactKeys(tagged, "kind", "value") || !ok {
			return nil, errors.New("invalid boolean profile value")
		}
		return item, nil
	case "integer":
		number, ok := tagged["value"].(json.Number)
		if !hasExactKeys(tagged, "kind", "value") || !ok ||
			!validSafeInteger(number) {
			return nil, errors.New("invalid integer profile value")
		}
		item, err := strconv.ParseInt(number.String(), 10, 64)
		if err != nil {
			return nil, errors.New("invalid integer profile value")
		}
		return int(item), nil
	case "string":
		item, ok := tagged["value"].(string)
		if !hasExactKeys(tagged, "kind", "value") || !ok {
			return nil, errors.New("invalid string profile value")
		}
		return item, nil
	case "list":
		rawItems, ok := tagged["items"].([]any)
		if !hasExactKeys(tagged, "items", "kind") || !ok {
			return nil, errors.New("invalid list profile value")
		}
		items := make([]any, 0, len(rawItems))
		for _, raw := range rawItems {
			item, err := decodeProfileValue(raw, depth+1)
			if err != nil {
				return nil, err
			}
			items = append(items, item)
		}
		return items, nil
	case "record":
		rawEntries, ok := tagged["entries"].([]any)
		if !hasExactKeys(tagged, "entries", "kind") || !ok {
			return nil, errors.New("invalid record profile value")
		}
		result := map[string]any{}
		previous := ""
		for index, raw := range rawEntries {
			entry, ok := raw.(map[string]any)
			if !ok || !hasExactKeys(entry, "kind", "name", "value") ||
				entry["kind"] != "record_entry" {
				return nil, errors.New("invalid profile record entry")
			}
			name, ok := entry["name"].(string)
			if !ok || !identifierPattern.MatchString(name) ||
				(index != 0 && name <= previous) {
				return nil, errors.New("profile record names are not canonical")
			}
			item, err := decodeProfileValue(entry["value"], depth+1)
			if err != nil {
				return nil, err
			}
			result[name] = item
			previous = name
		}
		return result, nil
	default:
		return nil, errors.New("unsupported profile value kind")
	}
}

func encodeProfileValue(value any, depth int) (any, bool) {
	if depth > 128 {
		return nil, false
	}
	switch item := value.(type) {
	case nil:
		return map[string]any{"kind": "null"}, true
	case bool:
		return map[string]any{"kind": "boolean", "value": item}, true
	case int:
		return map[string]any{"kind": "integer", "value": item}, true
	case string:
		return map[string]any{"kind": "string", "value": item}, true
	case []any:
		encoded := make([]any, 0, len(item))
		for _, value := range item {
			child, ok := encodeProfileValue(value, depth+1)
			if !ok {
				return nil, false
			}
			encoded = append(encoded, child)
		}
		return map[string]any{"kind": "list", "items": encoded}, true
	case map[string]any:
		names := make([]string, 0, len(item))
		for name := range item {
			if !identifierPattern.MatchString(name) {
				return nil, false
			}
			names = append(names, name)
		}
		sort.Strings(names)
		entries := make([]any, 0, len(names))
		for _, name := range names {
			child, ok := encodeProfileValue(item[name], depth+1)
			if !ok {
				return nil, false
			}
			entries = append(entries, recordEntry(name, child))
		}
		return map[string]any{"kind": "record", "entries": entries}, true
	default:
		return nil, false
	}
}

func scanFrozenFixture(
	root *os.Root,
	layout []frozenEntrySpec,
) ([]scannedInventoryEntry, error) {
	entries := make([]scannedInventoryEntry, 0, len(layout))
	for _, spec := range layout {
		switch spec.kind {
		case "directory":
			names, err := verifiedDirectoryNames(root, spec.path)
			if err != nil || !sameStrings(names, spec.children) {
				return nil, fmt.Errorf("invalid directory %s", spec.path)
			}
			entries = append(entries, scannedInventoryEntry{
				path: spec.path,
				kind: "directory",
			})
		case "file":
			payload, err := readVerifiedRegularFile(root, spec.path)
			if err != nil {
				return nil, err
			}
			digest := sha256.Sum256(payload)
			entries = append(entries, scannedInventoryEntry{
				path:          spec.path,
				kind:          "file",
				size:          len(payload),
				contentDigest: hex.EncodeToString(digest[:]),
				content:       bytes.Clone(payload),
			})
		default:
			return nil, errors.New("unsupported frozen entry kind")
		}
	}
	sort.Slice(entries, func(left int, right int) bool {
		return entries[left].path < entries[right].path
	})
	return entries, nil
}

func verifiedDirectoryNames(root *os.Root, path string) ([]string, error) {
	before, err := root.Lstat(path)
	if err != nil || !before.IsDir() || before.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("inventory directory is not real")
	}
	directory, err := root.Open(path)
	if err != nil {
		return nil, err
	}
	defer directory.Close()
	opened, err := directory.Stat()
	if err != nil || !sameFileState(before, opened) {
		return nil, errors.New("inventory directory changed while opening")
	}
	rawEntries, err := directory.ReadDir(-1)
	if err != nil {
		return nil, err
	}
	names := make([]string, 0, len(rawEntries))
	for _, entry := range rawEntries {
		names = append(names, entry.Name())
	}
	sort.Strings(names)
	openedAfter, openedErr := directory.Stat()
	after, pathErr := root.Lstat(path)
	if openedErr != nil || pathErr != nil ||
		!sameFileState(opened, openedAfter) ||
		!sameFileState(before, after) {
		return nil, errors.New("inventory directory changed while reading")
	}
	return names, nil
}

func readVerifiedRegularFile(root *os.Root, path string) ([]byte, error) {
	before, err := root.Lstat(path)
	if err != nil || !before.Mode().IsRegular() ||
		before.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("inventory input is not a regular file")
	}
	file, err := root.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	opened, err := file.Stat()
	if err != nil || !opened.Mode().IsRegular() ||
		!sameFileState(before, opened) {
		return nil, errors.New("inventory input changed while opening")
	}
	payload, err := io.ReadAll(io.LimitReader(file, maxFrozenFileBytes+1))
	if err != nil || len(payload) > maxFrozenFileBytes {
		return nil, errors.New("inventory input cannot be read within its bound")
	}
	openedAfter, openedErr := file.Stat()
	after, pathErr := root.Lstat(path)
	if openedErr != nil || pathErr != nil ||
		len(payload) != int(openedAfter.Size()) ||
		!sameFileState(opened, openedAfter) ||
		!sameFileState(before, after) {
		return nil, errors.New("inventory input changed while reading")
	}
	return payload, nil
}

func sameFileState(left os.FileInfo, right os.FileInfo) bool {
	return os.SameFile(left, right) &&
		left.Mode() == right.Mode() &&
		left.Size() == right.Size() &&
		left.ModTime().Equal(right.ModTime())
}

func sameStrings(left []string, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func sameInventoryEntries(
	left []scannedInventoryEntry,
	right []scannedInventoryEntry,
) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index].path != right[index].path ||
			left[index].kind != right[index].kind ||
			left[index].size != right[index].size ||
			left[index].contentDigest != right[index].contentDigest ||
			!bytes.Equal(left[index].content, right[index].content) {
			return false
		}
	}
	return true
}

func buildFilesystemInventoryRun(
	request decodedInventoryRequest,
	entries []scannedInventoryEntry,
	classifications []classifiedInventoryFact,
) (*inventoryRun, error) {
	records := make([]any, 0, len(entries)*2+len(classifications)*2)
	entryByPath := map[string]map[string]any{}
	sourceByPath := map[string]scannedInventoryEntry{}
	confidence := map[string]any{
		"kind":  "confidence",
		"scale": "decimal-0-to-1",
		"value": "1",
		"basis": inventoryConfidenceBasis,
	}
	for _, scanned := range entries {
		sourceByPath[scanned.path] = scanned
		var contentDigest any
		var size any
		if scanned.kind == "file" {
			contentDigest = digestValue(scanned.contentDigest)
			size = scanned.size
		}
		provenance, err := identifiedInventoryRecord(
			"provenance",
			map[string]any{
				"kind":           "inventory_provenance",
				"source_path":    scanned.path,
				"content_digest": contentDigest,
				"source_span":    nil,
				"producer":       inventoryProducer(),
				"procedure_uri":  inventoryEntryProcedure,
			},
		)
		if err != nil {
			return nil, err
		}
		records = append(records, provenance)
		entry, err := identifiedInventoryRecord(
			"entry",
			map[string]any{
				"kind":                  "repository_entry",
				"level":                 "observed",
				"provenance":            inventoryRecordReference(provenance),
				"confidence":            confidence,
				"path":                  scanned.path,
				"entry_kind":            scanned.kind,
				"size_bytes":            size,
				"content_digest":        contentDigest,
				"symlink_target_digest": nil,
			},
		)
		if err != nil {
			return nil, err
		}
		entryByPath[scanned.path] = entry
		records = append(records, entry)
	}
	provenanceByCoordinate := map[string]map[string]any{}
	for _, classified := range classifications {
		source, sourceOK := sourceByPath[classified.path]
		entry, entryOK := entryByPath[classified.path]
		if !sourceOK || !entryOK || source.kind != "file" {
			return nil, errors.New("classification source is unavailable")
		}
		coordinate := classified.provenanceCoordinate()
		provenance := provenanceByCoordinate[coordinate]
		if provenance == nil {
			var err error
			provenance, err = identifiedInventoryRecord(
				"provenance",
				map[string]any{
					"kind":           "inventory_provenance",
					"source_path":    source.path,
					"content_digest": digestValue(source.contentDigest),
					"source_span":    classified.span.logicalValue(),
					"producer":       inventoryProducer(),
					"procedure_uri":  inventoryFactProcedure,
				},
			)
			if err != nil {
				return nil, err
			}
			provenanceByCoordinate[coordinate] = provenance
			records = append(records, provenance)
		}
		fact := map[string]any{
			"kind":       classified.kind,
			"level":      "observed",
			"provenance": inventoryRecordReference(provenance),
			"confidence": confidence,
			"entry":      inventoryRecordReference(entry),
		}
		for name, value := range classified.attributes {
			fact[name] = value
		}
		prefix, ok := inventoryRecordPrefix(classified.kind)
		if !ok {
			return nil, errors.New("unsupported classification kind")
		}
		identified, err := identifiedInventoryRecord(prefix, fact)
		if err != nil {
			return nil, err
		}
		records = append(records, identified)
	}
	sort.Slice(records, func(left int, right int) bool {
		leftRecord := records[left].(map[string]any)
		rightRecord := records[right].(map[string]any)
		leftKind := leftRecord["kind"].(string)
		rightKind := rightRecord["kind"].(string)
		if leftKind != rightKind {
			return leftKind < rightKind
		}
		return leftRecord["id"].(string) < rightRecord["id"].(string)
	})
	counts := map[string]int{"repository_entry": len(entries)}
	for _, classified := range classifications {
		counts[classified.kind]++
	}
	coverage := make([]any, 0, len(inventoryFactKinds))
	for _, factKind := range inventoryFactKinds {
		coverage = append(coverage, map[string]any{
			"kind":         "inventory_coverage",
			"fact_kind":    factKind,
			"status":       "complete",
			"record_count": counts[factKind],
		})
	}
	sourceRevision, err := inventorySourceRevision(records)
	if err != nil {
		return nil, err
	}
	snapshot := map[string]any{
		"kind":              "inventory_snapshot",
		"inventory_version": inventoryVersion,
		"schema_uri":        inventorySchemaURI,
		"subject_uri":       request.subjectURI,
		"path_identity":     inventoryPathIdentity,
		"source_revision":   digestValue(sourceRevision),
		"producer":          inventoryProducer(),
		"capability":        inventoryCapability(),
		"applied_policy":    request.appliedPolicy,
		"coverage":          coverage,
		"records":           records,
	}
	snapshotDigest, err := canonicalLogicalDigest(snapshot)
	if err != nil {
		return nil, err
	}
	return &inventoryRun{
		key:            request.runKey,
		entries:        entries,
		snapshot:       snapshot,
		snapshotDigest: snapshotDigest,
		records:        records,
	}, nil
}

func buildInventoryPage(
	request decodedInventoryRequest,
	run *inventoryRun,
) (map[string]any, bool, error) {
	if run == nil || len(run.records) == 0 {
		return nil, false, errors.New("inventory run is unavailable")
	}
	start := 0
	if request.cursor != nil {
		digest := request.cursor["snapshot_digest"].(map[string]any)
		if digest["value"] != run.snapshotDigest {
			return nil, false, errors.New("inventory cursor snapshot is stale")
		}
		afterKind := request.cursor["after_kind"].(string)
		afterID := request.cursor["after_id"].(string)
		found := false
		for index, raw := range run.records {
			record := raw.(map[string]any)
			if record["kind"] == afterKind && record["id"] == afterID {
				start = index + 1
				found = true
				break
			}
		}
		if !found || start >= len(run.records) {
			return nil, false, errors.New("inventory cursor coordinate is unavailable")
		}
	}
	end := start + request.recordLimit
	if end > len(run.records) {
		end = len(run.records)
	}
	selected := append([]any(nil), run.records[start:end]...)
	if len(selected) == 0 {
		return nil, false, errors.New("inventory page would be empty")
	}
	complete := end == len(run.records)
	var nextCursor any
	if !complete {
		last := selected[len(selected)-1].(map[string]any)
		nextCursor = map[string]any{
			"kind":            "inventory_cursor",
			"snapshot_digest": digestValue(run.snapshotDigest),
			"after_kind":      last["kind"],
			"after_id":        last["id"],
		}
	}
	var requestCursor any
	if request.cursor != nil {
		requestCursor = request.cursor
	}
	page := map[string]any{
		"kind":              "inventory_page",
		"inventory_version": inventoryVersion,
		"schema_uri":        inventoryPageSchemaURI,
		"subject_uri":       run.snapshot["subject_uri"],
		"path_identity":     inventoryPathIdentity,
		"source_revision":   run.snapshot["source_revision"],
		"snapshot_digest":   digestValue(run.snapshotDigest),
		"producer":          inventoryProducer(),
		"capability":        inventoryCapability(),
		"applied_policy":    run.snapshot["applied_policy"],
		"coverage":          run.snapshot["coverage"],
		"request_cursor":    requestCursor,
		"records":           selected,
		"next_cursor":       nextCursor,
		"complete":          complete,
	}
	return page, complete, nil
}

func inventoryRecordPrefix(kind string) (string, bool) {
	switch kind {
	case "api_description":
		return "api", true
	case "build_manifest":
		return "manifest", true
	case "public_interface":
		return "interface", true
	case "test_asset":
		return "test", true
	default:
		return "", false
	}
}

func inventorySourceRevision(records []any) (string, error) {
	entries := make([]any, 0, len(records))
	for _, raw := range records {
		record := raw.(map[string]any)
		if record["kind"] != "repository_entry" {
			continue
		}
		entries = append(entries, map[string]any{
			"content_digest":        record["content_digest"],
			"entry_kind":            record["entry_kind"],
			"path":                  record["path"],
			"read_status":           record["level"],
			"size_bytes":            record["size_bytes"],
			"symlink_target_digest": record["symlink_target_digest"],
		})
	}
	sort.Slice(entries, func(left int, right int) bool {
		return entries[left].(map[string]any)["path"].(string) <
			entries[right].(map[string]any)["path"].(string)
	})
	return canonicalLogicalDigest(map[string]any{
		"entries":  entries,
		"failures": []any{},
	})
}

func (instance *server) inventorySubjectURI() string {
	if instance.platformMode {
		return platformInventorySubjectURI
	}
	return httpInventorySubjectURI
}

func (instance *server) frozenFixtureLayout() []frozenEntrySpec {
	if instance.platformMode {
		return platformFrozenFixtureLayout
	}
	return httpFrozenFixtureLayout
}

func (instance *server) classifyFrozenFixture(
	entries []scannedInventoryEntry,
) ([]classifiedInventoryFact, error) {
	if instance.platformMode {
		return classifyFrozenGoPlatformFixture(entries)
	}
	return classifyFrozenGoFixture(entries)
}

func identifiedInventoryRecord(
	prefix string,
	record map[string]any,
) (map[string]any, error) {
	digest, err := canonicalLogicalDigest(record)
	if err != nil {
		return nil, err
	}
	record["id"] = prefix + "." + digest
	return record, nil
}

func canonicalLogicalDigest(value any) (string, error) {
	encoded, ok := appendCanonicalJSON(nil, value)
	if !ok {
		return "", errors.New("logical document is outside canonical JSON")
	}
	encoded = append(encoded, '\n')
	digest := sha256.Sum256(encoded)
	return hex.EncodeToString(digest[:]), nil
}

func inventoryRecordReference(record map[string]any) map[string]any {
	return map[string]any{
		"kind":        "inventory_record_ref",
		"target_kind": record["kind"],
		"target_id":   record["id"],
	}
}

func digestValue(value string) map[string]any {
	return map[string]any{
		"kind":      "digest",
		"algorithm": "sha-256",
		"value":     value,
	}
}

func inventoryProducer() map[string]any {
	return map[string]any{
		"kind":    "producer",
		"name":    inventoryProducerName,
		"version": inventoryVersion,
	}
}

func inventoryCapability() map[string]any {
	return map[string]any{
		"kind":    "capability",
		"name":    "org.ucf.adapter.inventory",
		"version": inventoryVersion,
	}
}

func exactStringList(value any, expected []string) bool {
	items, ok := value.([]any)
	if !ok || len(items) != len(expected) {
		return false
	}
	for index, item := range items {
		if item != expected[index] {
			return false
		}
	}
	return true
}
