package main

import (
	"bytes"
	"context"
	"errors"
	"sort"
)

const (
	discoveryVersion          = "1.0.0"
	discoveryRequestSchemaURI = "urn:ucf:adapter:discovery-request:1.0.0"
	discoveryResultSchemaURI  = "urn:ucf:adapter:discovery-result:1.0.0"
	discoveryProcedureURI     = "urn:ucf:onboarding-procedure:go-stdlib-static-discovery:1.0.0"
	discoveryConfidenceBasis  = "urn:ucf:onboarding-confidence:go-exported-function:1.0.0"
)

type discoveryPortSpec struct {
	name      string
	valueKind string
	required  bool
}

type discoveryFunctionSpec struct {
	slug       string
	confidence string
	inputs     []discoveryPortSpec
	outputs    []discoveryPortSpec
}

var discoveryFunctions = map[string]discoveryFunctionSpec{
	"FormatReceipt": {
		slug:       "format-receipt",
		confidence: "0.82",
		inputs: []discoveryPortSpec{
			{name: "total-cents", valueKind: "integer", required: true},
		},
		outputs: []discoveryPortSpec{
			{name: "receipt", valueKind: "string", required: true},
		},
	},
	"LegacyDiscountHint": {
		slug:       "legacy-discount-hint",
		confidence: "0.61",
		inputs: []discoveryPortSpec{
			{name: "code", valueKind: "string", required: true},
		},
		outputs: []discoveryPortSpec{
			{name: "discount-percent", valueKind: "integer", required: false},
		},
	},
	"NormalizeCoupon": {
		slug:       "normalize-coupon",
		confidence: "0.82",
		inputs: []discoveryPortSpec{
			{name: "code", valueKind: "string", required: true},
		},
		outputs: []discoveryPortSpec{
			{name: "normalized-code", valueKind: "string", required: true},
		},
	},
	"QuoteOrder": {
		slug:       "quote-order",
		confidence: "0.82",
		inputs: []discoveryPortSpec{
			{name: "quantity", valueKind: "integer", required: true},
			{name: "unit-price-cents", valueKind: "integer", required: true},
		},
		outputs: []discoveryPortSpec{
			{name: "total-cents", valueKind: "integer", required: true},
		},
	},
}

func (instance *server) discovery(
	contextValue context.Context,
	payload map[string]any,
) operationOutcome {
	run := instance.inventoryRun
	if run == nil || !run.completed {
		return failedOperation(
			"operation_failed",
			"discovery requires a completed inventory snapshot",
		)
	}
	request, err := decodeDiscoveryRequest(payload, run)
	if err != nil {
		return failedOperation(
			"invalid_params",
			"discovery request is outside the Go fixture profile",
		)
	}
	if contextValue.Err() != nil {
		return cancelledOperation()
	}
	result, err := instance.buildDiscoveryResult(request, run)
	if err != nil {
		return failedOperation(
			"internal_error",
			"discovery result construction failed",
		)
	}
	tagged, ok := encodeProfileValue(result, 0)
	if !ok {
		return failedOperation(
			"internal_error",
			"discovery result cannot be encoded",
		)
	}
	if contextValue.Err() != nil {
		return cancelledOperation()
	}
	return successfulOperation(map[string]any{
		"kind": "discover_result",
		"payload": map[string]any{
			"kind":           "adapter_payload",
			"schema_uri":     discoveryResultSchemaURI,
			"schema_version": discoveryVersion,
			"value":          tagged,
		},
	})
}

func decodeDiscoveryRequest(
	payload map[string]any,
	run *inventoryRun,
) (map[string]any, error) {
	if payload["schema_uri"] != discoveryRequestSchemaURI ||
		payload["schema_version"] != discoveryVersion {
		return nil, errors.New("incompatible discovery payload")
	}
	logical, err := decodeProfileValue(payload["value"], 0)
	if err != nil {
		return nil, err
	}
	request, ok := logical.(map[string]any)
	if !ok || !hasExactKeys(
		request,
		"capability",
		"inventory",
		"inventory_binding",
		"kind",
		"onboarding_version",
		"schema_uri",
	) ||
		request["kind"] != "discovery_request_profile" ||
		request["onboarding_version"] != discoveryVersion ||
		request["schema_uri"] != discoveryRequestSchemaURI ||
		!sameCanonicalLogicalValue(
			request["capability"],
			discoveryCapability(),
		) {
		return nil, errors.New("invalid discovery request")
	}
	embedded, ok := request["inventory"].(map[string]any)
	if !ok || !sameCanonicalLogicalValue(embedded, run.snapshot) {
		return nil, errors.New("discovery inventory does not match active run")
	}
	if !validDiscoveryInventoryBinding(
		request["inventory_binding"],
		run,
	) {
		return nil, errors.New("discovery inventory binding is stale")
	}
	recomputed, err := canonicalLogicalDigest(run.snapshot)
	if err != nil || recomputed != run.snapshotDigest ||
		!sameCanonicalLogicalValue(run.records, run.snapshot["records"]) {
		return nil, errors.New("active inventory run is invalid")
	}
	return request, nil
}

func validDiscoveryInventoryBinding(value any, run *inventoryRun) bool {
	binding, ok := value.(map[string]any)
	if !ok || !hasExactKeys(
		binding,
		"canonical_digest",
		"inventory_version",
		"kind",
		"schema_uri",
		"source_revision",
		"subject_uri",
	) {
		return false
	}
	expected := map[string]any{
		"kind":              "inventory_binding",
		"schema_uri":        inventorySchemaURI,
		"inventory_version": inventoryVersion,
		"subject_uri":       run.snapshot["subject_uri"],
		"source_revision":   run.snapshot["source_revision"],
		"canonical_digest":  digestValue(run.snapshotDigest),
	}
	return sameCanonicalLogicalValue(binding, expected)
}

func (instance *server) buildDiscoveryResult(
	request map[string]any,
	run *inventoryRun,
) (map[string]any, error) {
	interfaces := make([]map[string]any, 0, 12)
	manifests := make([]map[string]any, 0, 1)
	for _, raw := range run.records {
		record, ok := raw.(map[string]any)
		if !ok {
			return nil, errors.New("inventory record is invalid")
		}
		switch record["kind"] {
		case "build_manifest":
			manifests = append(manifests, record)
		case "public_interface":
			interfaces = append(interfaces, record)
		}
	}
	supportedFunctions := discoveryFunctions
	expectedInterfaceCount := 12
	expectedCandidateCount := len(discoveryFunctions)
	if instance.platformMode {
		supportedFunctions = map[string]discoveryFunctionSpec{
			"QuoteOrder": discoveryFunctions["QuoteOrder"],
		}
		expectedInterfaceCount = 9
		expectedCandidateCount = 1
	}
	if len(interfaces) != expectedInterfaceCount || len(manifests) != 1 {
		return nil, errors.New("inventory discovery facts are incomplete")
	}
	sortInventoryRecords(interfaces)
	sortInventoryRecords(manifests)
	if manifests[0]["dialect_uri"] != goModuleDialectURI {
		return nil, errors.New("inventory manifest is unsupported")
	}

	context := map[string]any{
		"inventory_binding": request["inventory_binding"],
		"producer":          inventoryProducer(),
		"capability":        discoveryCapability(),
		"procedure_uri":     discoveryProcedureURI,
	}
	candidates := make([]any, 0, expectedCandidateCount)
	eligible := make([]any, 0, len(interfaces))
	uncovered := make([]any, 0, len(interfaces)-len(discoveryFunctions))
	for _, subject := range interfaces {
		reference, err := inventoryReferenceForDiscovery(subject)
		if err != nil {
			return nil, err
		}
		eligible = append(eligible, reference)
		name, nameOK := subject["name"].(string)
		specification, supported := supportedFunctions[name]
		if !nameOK || !supported ||
			subject["interface_kind_uri"] != goExportedFunctionURI {
			uncovered = append(uncovered, reference)
			continue
		}
		proposal := discoveryProposal(specification)
		semanticDigest, err := canonicalLogicalDigest(proposal)
		if err != nil {
			return nil, err
		}
		evidence := []any{reference}
		if name == "QuoteOrder" {
			evidence, err = instance.quoteOrderImplementationEvidence(
				run.records,
			)
			if err != nil {
				return nil, err
			}
		}
		candidate := map[string]any{
			"kind":            "discovery_candidate",
			"id":              "candidate." + zeroDigest(),
			"semantic_digest": digestValue(semanticDigest),
			"subject":         reference,
			"evidence":        evidence,
			"confidence": map[string]any{
				"kind":  "confidence",
				"scale": "decimal-0-to-1",
				"value": specification.confidence,
				"basis": discoveryConfidenceBasis,
			},
			"proposal": proposal,
		}
		candidateID, err := discoveryCandidateID(candidate, context)
		if err != nil {
			return nil, err
		}
		candidate["id"] = "candidate." + candidateID
		candidates = append(candidates, candidate)
	}
	sortDiscoveryReferences(eligible)
	sortDiscoveryReferences(uncovered)
	sort.Slice(candidates, func(left int, right int) bool {
		return candidates[left].(map[string]any)["id"].(string) <
			candidates[right].(map[string]any)["id"].(string)
	})
	if len(candidates) != expectedCandidateCount ||
		len(uncovered) != len(interfaces)-expectedCandidateCount {
		return nil, errors.New("discovery coverage is inconsistent")
	}
	return map[string]any{
		"kind":               "discovery_result_profile",
		"onboarding_version": discoveryVersion,
		"schema_uri":         discoveryResultSchemaURI,
		"inventory_binding":  context["inventory_binding"],
		"producer":           context["producer"],
		"capability":         context["capability"],
		"procedure_uri":      context["procedure_uri"],
		"coverage": map[string]any{
			"kind":               "discovery_coverage",
			"status":             "partial",
			"eligible_subjects":  eligible,
			"uncovered_subjects": uncovered,
		},
		"diagnostics": []any{},
		"candidates":  candidates,
	}, nil
}

func discoveryProposal(specification discoveryFunctionSpec) map[string]any {
	slug := specification.slug
	actionID := "action." + slug
	stepID := "step." + slug
	useCaseID := "use-case." + slug
	actionReference := discoveryEntityReference("proposed_action", actionID)
	stepReference := discoveryEntityReference("proposed_step", stepID)
	useCaseReference := discoveryEntityReference("proposed_use_case", useCaseID)
	inputs := discoveryPorts(specification.inputs)
	outputs := discoveryPorts(specification.outputs)
	bindings := make([]any, 0, len(inputs))
	bindingReferences := make([]any, 0, len(inputs))
	for _, raw := range inputs {
		input := raw.(map[string]any)
		name := input["name"].(string)
		bindingID := "binding." + slug + "." + name
		bindingReference := discoveryEntityReference(
			"proposed_binding",
			bindingID,
		)
		bindingReferences = append(bindingReferences, bindingReference)
		bindings = append(bindings, map[string]any{
			"kind": "proposed_binding",
			"id":   bindingID,
			"target": map[string]any{
				"kind":      "proposal_port_ref",
				"owner":     stepReference,
				"direction": "input",
				"name":      name,
			},
			"source": map[string]any{
				"kind":      "proposal_port_ref",
				"owner":     useCaseReference,
				"direction": "input",
				"name":      name,
			},
		})
	}
	entities := []any{
		map[string]any{
			"kind":         "proposed_action",
			"id":           actionID,
			"input_ports":  inputs,
			"output_ports": outputs,
		},
	}
	entities = append(entities, bindings...)
	entities = append(
		entities,
		map[string]any{
			"kind":     "proposed_step",
			"id":       stepID,
			"action":   actionReference,
			"bindings": bindingReferences,
		},
		map[string]any{
			"kind":         "proposed_use_case",
			"id":           useCaseID,
			"input_ports":  inputs,
			"output_ports": outputs,
			"steps":        []any{stepReference},
		},
	)
	sort.Slice(entities, func(left int, right int) bool {
		leftEntity := entities[left].(map[string]any)
		rightEntity := entities[right].(map[string]any)
		leftKind := leftEntity["kind"].(string)
		rightKind := rightEntity["kind"].(string)
		if leftKind != rightKind {
			return leftKind < rightKind
		}
		return leftEntity["id"].(string) < rightEntity["id"].(string)
	})
	return map[string]any{
		"kind":     "candidate_proposal",
		"root":     useCaseReference,
		"entities": entities,
	}
}

func discoveryPorts(specifications []discoveryPortSpec) []any {
	ports := make([]any, 0, len(specifications))
	for _, specification := range specifications {
		ports = append(ports, map[string]any{
			"kind":       "port",
			"name":       specification.name,
			"value_kind": specification.valueKind,
			"required":   specification.required,
		})
	}
	return ports
}

func discoveryCandidateID(
	candidate map[string]any,
	context map[string]any,
) (string, error) {
	return canonicalLogicalDigest(map[string]any{
		"candidate": map[string]any{
			"kind":       candidate["kind"],
			"subject":    candidate["subject"],
			"evidence":   candidate["evidence"],
			"confidence": candidate["confidence"],
			"proposal":   candidate["proposal"],
		},
		"capability":        context["capability"],
		"inventory_binding": context["inventory_binding"],
		"procedure_uri":     context["procedure_uri"],
		"producer":          context["producer"],
	})
}

func inventoryReferenceForDiscovery(record map[string]any) (map[string]any, error) {
	kind, kindOK := record["kind"].(string)
	identifier, identifierOK := record["id"].(string)
	if !kindOK || !identifierOK {
		return nil, errors.New("inventory reference target is invalid")
	}
	return map[string]any{
		"kind":        "inventory_record_ref",
		"target_kind": kind,
		"target_id":   identifier,
	}, nil
}

func (instance *server) quoteOrderImplementationEvidence(
	records []any,
) ([]any, error) {
	references := make([]any, 0, 10)
	manifestCount := 0
	interfaceCount := 0
	for _, raw := range records {
		record, ok := raw.(map[string]any)
		if !ok {
			return nil, errors.New("quote-order inventory record is invalid")
		}
		switch record["kind"] {
		case "build_manifest":
			if record["dialect_uri"] != goModuleDialectURI {
				return nil, errors.New("quote-order build manifest is unsupported")
			}
			manifestCount++
			references = append(references, inventoryRecordReference(record))
		case "public_interface":
			name, nameOK := record["name"].(string)
			if !nameOK {
				return nil, errors.New("quote-order public interface is invalid")
			}
			if !instance.platformMode {
				_, isOtherFunction := discoveryFunctions[name]
				if isOtherFunction &&
					name != "QuoteOrder" {
					continue
				}
			}
			interfaceCount++
			references = append(references, inventoryRecordReference(record))
		}
	}
	if manifestCount != 1 || interfaceCount != 9 || len(references) != 10 {
		return nil, errors.New("quote-order implementation evidence is incomplete")
	}
	sortDiscoveryReferences(references)
	return references, nil
}

func discoveryEntityReference(kind string, identifier string) map[string]any {
	return map[string]any{
		"kind":        "proposal_entity_ref",
		"target_kind": kind,
		"target_id":   identifier,
	}
}

func discoveryCapability() map[string]any {
	return map[string]any{
		"kind":    "capability",
		"name":    "org.ucf.adapter.discovery",
		"version": discoveryVersion,
	}
}

func sortInventoryRecords(records []map[string]any) {
	sort.Slice(records, func(left int, right int) bool {
		return records[left]["id"].(string) < records[right]["id"].(string)
	})
}

func sortDiscoveryReferences(references []any) {
	sort.Slice(references, func(left int, right int) bool {
		leftReference := references[left].(map[string]any)
		rightReference := references[right].(map[string]any)
		leftKind := leftReference["target_kind"].(string)
		rightKind := rightReference["target_kind"].(string)
		if leftKind != rightKind {
			return leftKind < rightKind
		}
		return leftReference["target_id"].(string) <
			rightReference["target_id"].(string)
	})
}

func sameCanonicalLogicalValue(left any, right any) bool {
	leftEncoded, leftOK := appendCanonicalJSON(nil, left)
	rightEncoded, rightOK := appendCanonicalJSON(nil, right)
	return leftOK && rightOK && bytes.Equal(leftEncoded, rightEncoded)
}

func zeroDigest() string {
	return "0000000000000000000000000000000000000000000000000000000000000000"
}
