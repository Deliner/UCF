package main

import (
	"context"
	"errors"
	"os"
	"sort"
)

const (
	mappingVersion             = "1.0.0"
	mappingRequestSchemaURI    = "urn:ucf:adapter:implementation-mapping-request:1.0.0"
	mappingResultSchemaURI     = "urn:ucf:adapter:implementation-mapping-result:1.0.0"
	mappingProfileProcedureURI = "urn:ucf:implementation-evidence:map:1.0.0"
	mappingAdapterProcedureURI = "urn:ucf:adapter:go-stdlib-static-mapping:1.0.0"
	onboardingBundleSchemaURI  = "urn:ucf:onboarding:bundle:1.0.0"
	quoteOrderActionID         = "action.quote-order"
	quoteOrderQuantityBinding  = "binding.quote-order.quantity"
	quoteOrderUnitPriceBinding = "binding.quote-order.unit-price-cents"
	quoteOrderStepID           = "step.quote-order"
	quoteOrderUseCaseID        = "use-case.quote-order"
)

func (instance *server) mapping(
	contextValue context.Context,
	payload map[string]any,
) operationOutcome {
	run := instance.inventoryRun
	if run == nil || !run.completed {
		return failedOperation(
			"operation_failed",
			"mapping requires a completed inventory snapshot",
		)
	}
	if !instance.mappingRunIsCurrent(run) {
		instance.inventoryRun = nil
		instance.mappingResult = nil
		return failedOperation(
			"operation_failed",
			"mapping inventory snapshot is no longer current",
		)
	}
	request, target, err := decodeMappingRequest(payload, run)
	if err != nil {
		return failedOperation(
			"invalid_params",
			"mapping request is outside the Go fixture profile",
		)
	}
	sourceRecords, err := instance.quoteOrderImplementationEvidence(
		run.records,
	)
	if err != nil {
		return failedOperation(
			"operation_failed",
			"mapping implementation evidence is unavailable",
		)
	}
	result, err := buildMappingResult(request, target, sourceRecords)
	if err != nil {
		return failedOperation(
			"internal_error",
			"mapping result construction failed",
		)
	}
	tagged, ok := encodeProfileValue(result, 0)
	if !ok {
		return failedOperation(
			"internal_error",
			"mapping result cannot be encoded",
		)
	}
	if contextValue.Err() != nil {
		return cancelledOperation()
	}
	instance.mappingResult = result
	return successfulOperation(map[string]any{
		"kind": "map_result",
		"payload": map[string]any{
			"kind":           "adapter_payload",
			"schema_uri":     mappingResultSchemaURI,
			"schema_version": mappingVersion,
			"value":          tagged,
		},
	})
}

func (instance *server) mappingRunIsCurrent(run *inventoryRun) bool {
	recomputed, err := canonicalLogicalDigest(run.snapshot)
	if err != nil || recomputed != run.snapshotDigest ||
		!sameCanonicalLogicalValue(run.records, run.snapshot["records"]) ||
		!sameCanonicalLogicalValue(run.snapshot["producer"], inventoryProducer()) {
		return false
	}
	sourceRevision, ok := run.snapshot["source_revision"].(map[string]any)
	if !ok || !validMappingDigest(sourceRevision) {
		return false
	}
	root, err := os.OpenRoot(".")
	if err != nil {
		return false
	}
	defer root.Close()
	layout := instance.frozenFixtureLayout()
	first, err := scanFrozenFixture(root, layout)
	if err != nil {
		return false
	}
	second, err := scanFrozenFixture(root, layout)
	return err == nil &&
		sameInventoryEntries(first, second) &&
		sameInventoryEntries(run.entries, first)
}

func decodeMappingRequest(
	payload map[string]any,
	run *inventoryRun,
) (map[string]any, map[string]any, error) {
	if payload["schema_uri"] != mappingRequestSchemaURI ||
		payload["schema_version"] != mappingVersion {
		return nil, nil, errors.New("incompatible mapping payload")
	}
	logical, err := decodeProfileValue(payload["value"], 0)
	if err != nil {
		return nil, nil, err
	}
	request, ok := logical.(map[string]any)
	if !ok || !hasExactKeys(
		request,
		"adapter_procedure_uri",
		"behavior",
		"capability",
		"implementation_evidence_version",
		"inventory",
		"kind",
		"onboarding",
		"profile_procedure_uri",
		"schema_uri",
		"targets",
	) ||
		request["kind"] != "implementation_mapping_request" ||
		request["implementation_evidence_version"] != mappingVersion ||
		request["schema_uri"] != mappingRequestSchemaURI ||
		request["profile_procedure_uri"] != mappingProfileProcedureURI ||
		request["adapter_procedure_uri"] != mappingAdapterProcedureURI ||
		!sameCanonicalLogicalValue(request["capability"], mappingCapability()) ||
		!validOnboardingBinding(request["onboarding"]) ||
		!sameCanonicalLogicalValue(request["inventory"], run.snapshot) {
		return nil, nil, errors.New("invalid mapping request")
	}
	target, err := validateQuoteOrderTarget(
		request["behavior"],
		request["targets"],
	)
	if err != nil {
		return nil, nil, err
	}
	return request, target, nil
}

func validOnboardingBinding(value any) bool {
	binding, ok := value.(map[string]any)
	if !ok || !hasExactKeys(
		binding,
		"canonical_digest",
		"kind",
		"schema_uri",
		"schema_version",
	) ||
		binding["kind"] != "onboarding_bundle_binding" ||
		binding["schema_uri"] != onboardingBundleSchemaURI ||
		binding["schema_version"] != mappingVersion {
		return false
	}
	digest, ok := binding["canonical_digest"].(map[string]any)
	return ok && validMappingDigest(digest)
}

func validateQuoteOrderTarget(
	behaviorValue any,
	targetsValue any,
) (map[string]any, error) {
	behavior, ok := behaviorValue.(map[string]any)
	if !ok || !hasExactKeys(
		behavior,
		"document_id",
		"entities",
		"ir_version",
		"kind",
		"roots",
	) ||
		behavior["kind"] != "behavior_ir" ||
		behavior["ir_version"] != mappingVersion {
		return nil, errors.New("mapping Behavior IR is incompatible")
	}
	documentID, ok := behavior["document_id"].(string)
	if !ok || len(documentID) > 255 || !identifierPattern.MatchString(documentID) {
		return nil, errors.New("mapping Behavior document identity is invalid")
	}
	roots, ok := mappingObjectList(behavior["roots"])
	if !ok {
		return nil, errors.New("mapping Behavior roots are invalid")
	}
	entities, ok := mappingObjectList(behavior["entities"])
	if !ok || !validQuoteOrderGraph(roots, entities) {
		return nil, errors.New("mapping Behavior graph is unsupported")
	}
	targets, ok := mappingObjectList(targetsValue)
	if !ok || len(targets) != 1 {
		return nil, errors.New("mapping request requires one supported target")
	}
	digest, err := canonicalLogicalDigest(behavior)
	if err != nil {
		return nil, errors.New("mapping Behavior digest cannot be derived")
	}
	expected := map[string]any{
		"kind":             "behavior_entity_ref",
		"document_id":      documentID,
		"ir_version":       mappingVersion,
		"canonical_digest": digestValue(digest),
		"target_kind":      "use_case",
		"target_id":        quoteOrderUseCaseID,
	}
	if !sameCanonicalLogicalValue(targets[0], expected) {
		return nil, errors.New("mapping target does not bind QuoteOrder")
	}
	return targets[0], nil
}

func validQuoteOrderGraph(
	roots []map[string]any,
	entities []map[string]any,
) bool {
	if len(roots) != 1 ||
		!sameCanonicalLogicalValue(
			roots[0],
			mappingEntityReference("use_case", quoteOrderUseCaseID),
		) ||
		len(entities) != 6 ||
		!mappingEntitiesAreCanonical(entities) {
		return false
	}
	action := mappingEntity(entities, "action", quoteOrderActionID)
	quantity := mappingEntity(
		entities,
		"binding",
		quoteOrderQuantityBinding,
	)
	unitPrice := mappingEntity(
		entities,
		"binding",
		quoteOrderUnitPriceBinding,
	)
	step := mappingEntity(entities, "step", quoteOrderStepID)
	useCase := mappingEntity(entities, "use_case", quoteOrderUseCaseID)
	var provenance map[string]any
	provenanceCount := 0
	for _, entity := range entities {
		if entity["kind"] == "provenance" {
			provenance = entity
			provenanceCount++
		}
	}
	if action == nil || quantity == nil || unitPrice == nil ||
		step == nil || useCase == nil || provenanceCount != 1 ||
		!validMappingProvenance(provenance) {
		return false
	}
	provenanceID := provenance["id"].(string)
	provenanceReference := mappingEntityReference("provenance", provenanceID)
	expected := []map[string]any{
		{
			"kind":         "action",
			"id":           quoteOrderActionID,
			"input_ports":  quoteOrderInputPorts(),
			"output_ports": quoteOrderOutputPorts(),
			"effects":      []any{},
			"requires":     []any{},
			"provenance":   provenanceReference,
		},
		{
			"kind": "binding",
			"id":   quoteOrderQuantityBinding,
			"target": mappingPortReference(
				"step",
				quoteOrderStepID,
				"quantity",
			),
			"source": mappingPortReference(
				"use_case",
				quoteOrderUseCaseID,
				"quantity",
			),
			"provenance": provenanceReference,
		},
		{
			"kind": "binding",
			"id":   quoteOrderUnitPriceBinding,
			"target": mappingPortReference(
				"step",
				quoteOrderStepID,
				"unit-price-cents",
			),
			"source": mappingPortReference(
				"use_case",
				quoteOrderUseCaseID,
				"unit-price-cents",
			),
			"provenance": provenanceReference,
		},
		{
			"kind":   "step",
			"id":     quoteOrderStepID,
			"action": mappingEntityReference("action", quoteOrderActionID),
			"bindings": []any{
				mappingEntityReference("binding", quoteOrderQuantityBinding),
				mappingEntityReference("binding", quoteOrderUnitPriceBinding),
			},
			"effects":      []any{},
			"observations": []any{},
			"requires":     []any{},
			"provenance":   provenanceReference,
		},
		{
			"kind":         "use_case",
			"id":           quoteOrderUseCaseID,
			"input_ports":  quoteOrderInputPorts(),
			"output_ports": quoteOrderOutputPorts(),
			"steps": []any{
				mappingEntityReference("step", quoteOrderStepID),
			},
			"invariants": []any{},
			"requires":   []any{},
			"provenance": provenanceReference,
		},
	}
	actual := []map[string]any{action, quantity, unitPrice, step, useCase}
	for index := range expected {
		if !sameCanonicalLogicalValue(actual[index], expected[index]) {
			return false
		}
	}
	return true
}

func mappingEntitiesAreCanonical(entities []map[string]any) bool {
	identities := make([]string, 0, len(entities))
	for _, entity := range entities {
		kind, kindOK := entity["kind"].(string)
		identifier, identifierOK := entity["id"].(string)
		if !kindOK || !identifierOK || len(identifier) > 255 ||
			!identifierPattern.MatchString(identifier) {
			return false
		}
		identities = append(identities, kind+"\x00"+identifier)
	}
	sorted := append([]string(nil), identities...)
	sort.Strings(sorted)
	for index, identity := range identities {
		if identity != sorted[index] ||
			(index != 0 && identity == identities[index-1]) {
			return false
		}
	}
	return true
}

func validMappingProvenance(value map[string]any) bool {
	if value == nil || !hasExactKeys(
		value,
		"captured_at",
		"id",
		"kind",
		"producer",
		"source",
	) ||
		value["kind"] != "provenance" {
		return false
	}
	identifier, identifierOK := value["id"].(string)
	capturedAt, capturedAtOK := value["captured_at"].(string)
	source, sourceOK := value["source"].(map[string]any)
	producer, producerOK := value["producer"].(map[string]any)
	if !identifierOK || len(identifier) > 255 ||
		!identifierPattern.MatchString(identifier) ||
		!capturedAtOK || !validTimestamp(capturedAt) ||
		!sourceOK || !producerOK || !validProducer(producer) ||
		!hasExactKeys(source, "kind", "revision", "uri") ||
		source["kind"] != "artifact_source" {
		return false
	}
	uri, uriOK := source["uri"].(string)
	revision, revisionOK := source["revision"].(map[string]any)
	return uriOK && len(uri) >= 3 && len(uri) <= 2048 &&
		uriPattern.MatchString(uri) &&
		revisionOK && validMappingDigest(revision)
}

func mappingObjectList(value any) ([]map[string]any, bool) {
	items, ok := value.([]any)
	if !ok {
		return nil, false
	}
	result := make([]map[string]any, 0, len(items))
	for _, item := range items {
		object, ok := item.(map[string]any)
		if !ok {
			return nil, false
		}
		result = append(result, object)
	}
	return result, true
}

func mappingEntity(
	entities []map[string]any,
	kind string,
	identifier string,
) map[string]any {
	for _, entity := range entities {
		if entity["kind"] == kind && entity["id"] == identifier {
			return entity
		}
	}
	return nil
}

func quoteOrderInputPorts() []any {
	return []any{
		mappingPort("quantity"),
		mappingPort("unit-price-cents"),
	}
}

func quoteOrderOutputPorts() []any {
	return []any{mappingPort("total-cents")}
}

func mappingPort(name string) map[string]any {
	return map[string]any{
		"kind":       "port",
		"name":       name,
		"value_kind": "integer",
		"required":   true,
	}
}

func mappingEntityReference(kind string, identifier string) map[string]any {
	return map[string]any{
		"kind":        "entity_ref",
		"target_kind": kind,
		"target_id":   identifier,
	}
}

func mappingPortReference(
	ownerKind string,
	ownerID string,
	name string,
) map[string]any {
	return map[string]any{
		"kind":      "port_ref",
		"owner":     mappingEntityReference(ownerKind, ownerID),
		"direction": "input",
		"name":      name,
	}
}

func validMappingDigest(value map[string]any) bool {
	text, ok := value["value"].(string)
	return hasExactKeys(value, "algorithm", "kind", "value") &&
		value["kind"] == "digest" &&
		value["algorithm"] == "sha-256" &&
		ok && validSHA256(text)
}

func buildMappingResult(
	request map[string]any,
	target map[string]any,
	sourceRecords []any,
) (map[string]any, error) {
	projection := map[string]any{
		"kind":                            "implementation_mapping_result",
		"implementation_evidence_version": mappingVersion,
		"schema_uri":                      mappingResultSchemaURI,
		"status":                          "complete",
		"request":                         request,
		"producer":                        inventoryProducer(),
		"capability":                      mappingCapability(),
		"procedure_uri":                   mappingAdapterProcedureURI,
		"bindings": []any{
			map[string]any{
				"kind":           "implementation_binding",
				"behavior":       target,
				"source_records": sourceRecords,
			},
		},
	}
	digest, err := canonicalLogicalDigest(projection)
	if err != nil {
		return nil, err
	}
	result := make(map[string]any, len(projection)+1)
	for name, value := range projection {
		result[name] = value
	}
	result["id"] = "mapping." + digest
	return result, nil
}

func mappingCapability() map[string]any {
	return map[string]any{
		"kind":    "capability",
		"name":    "org.ucf.adapter.mapping",
		"version": mappingVersion,
	}
}
