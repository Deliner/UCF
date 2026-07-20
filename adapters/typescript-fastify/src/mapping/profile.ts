import { createHash } from "node:crypto";

import { canonicalJson } from "../canonical-json.js";
import type { InventoryRun } from "../inventory/profile.js";
import {
  type JsonObject,
  type JsonValue,
  hasExactKeys,
  isObject,
} from "../strict-json.js";
import { encodeTagged } from "../tagged-values.js";

const VERSION = "1.0.0";
const REQUEST_SCHEMA_URI =
  "urn:ucf:adapter:implementation-mapping-request:1.0.0";
const RESULT_SCHEMA_URI =
  "urn:ucf:adapter:implementation-mapping-result:1.0.0";
const PROFILE_PROCEDURE_URI =
  "urn:ucf:implementation-evidence:map:1.0.0";
const ADAPTER_PROCEDURE_URI =
  "urn:ucf:adapter:typescript-fastify-static-mapping:1.0.0";
const ONBOARDING_SCHEMA_URI = "urn:ucf:onboarding:bundle:1.0.0";
const PRODUCER: JsonObject = {
  kind: "producer",
  name: "org.ucf.adapter.typescript-fastify",
  version: VERSION,
};
const CAPABILITY: JsonObject = {
  kind: "capability",
  name: "org.ucf.adapter.mapping",
  version: VERSION,
};
const DIGEST = /^[0-9a-f]{64}$/;
const IDENTIFIER = /^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/;
const NORMALIZED_VERSION =
  /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/;
const QUALIFIED_NAME =
  /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$/;
const URI = /^[a-z][a-z0-9+.-]*:[^\s]+$/;
const TIMESTAMP =
  /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/;
const ACTION_ID = "action.quote-order";
const QUANTITY_BINDING_ID = "binding.quote-order.quantity";
const UNIT_PRICE_BINDING_ID =
  "binding.quote-order.unit-price-cents";
const STEP_ID = "step.quote-order";
const QUOTE_ORDER_ID = "use-case.quote-order";

export class MappingProfileError extends Error {
  public constructor(
    public readonly code: "invalid_params" | "operation_failed",
    message: string,
  ) {
    super(message);
    this.name = "MappingProfileError";
  }
}

export function buildMappingPayload(
  payload: JsonValue | undefined,
  decodedValue: JsonValue,
  run: Readonly<InventoryRun> | null,
): JsonObject {
  if (run === null) {
    throw new MappingProfileError(
      "operation_failed",
      "mapping requires a completed inventory snapshot",
    );
  }
  validateCompletedRun(run);
  const request = decodeRequest(payload, decodedValue, run.snapshot);
  const target = validateBehaviorTarget(
    request["behavior"],
    request["targets"],
  );
  const sourceRecords = implementationEvidence(run.records);
  const provisional: JsonObject = {
    kind: "implementation_mapping_result",
    implementation_evidence_version: VERSION,
    schema_uri: RESULT_SCHEMA_URI,
    id: `mapping.${"0".repeat(64)}`,
    status: "complete",
    request,
    producer: PRODUCER,
    capability: CAPABILITY,
    procedure_uri: ADAPTER_PROCEDURE_URI,
    bindings: [
      {
        kind: "implementation_binding",
        behavior: target,
        source_records: sourceRecords,
      },
    ],
  };
  const projection = Object.fromEntries(
    Object.entries(provisional).filter(([name]) => name !== "id"),
  ) as JsonObject;
  provisional["id"] = `mapping.${sha256(canonicalJson(projection))}`;
  return {
    kind: "adapter_payload",
    schema_uri: RESULT_SCHEMA_URI,
    schema_version: VERSION,
    value: encodeTagged(provisional),
  };
}

function decodeRequest(
  payload: JsonValue | undefined,
  decoded: JsonValue,
  inventory: JsonObject,
): JsonObject {
  if (
    !hasExactKeys(
      payload,
      ["kind", "schema_uri", "schema_version", "value"],
    )
    || payload["kind"] !== "adapter_payload"
    || payload["schema_uri"] !== REQUEST_SCHEMA_URI
    || payload["schema_version"] !== VERSION
  ) {
    invalid("mapping payload coordinates are incompatible");
  }
  if (!isObject(decoded)) {
    invalid("mapping request root is not a record");
  }
  requireExact(decoded, [
    "kind",
    "implementation_evidence_version",
    "schema_uri",
    "capability",
    "profile_procedure_uri",
    "adapter_procedure_uri",
    "onboarding",
    "behavior",
    "inventory",
    "targets",
  ]);
  if (
    decoded["kind"] !== "implementation_mapping_request"
    || decoded["implementation_evidence_version"] !== VERSION
    || decoded["schema_uri"] !== REQUEST_SCHEMA_URI
    || canonicalJson(decoded["capability"] ?? null)
      !== canonicalJson(CAPABILITY)
    || decoded["profile_procedure_uri"] !== PROFILE_PROCEDURE_URI
    || decoded["adapter_procedure_uri"] !== ADAPTER_PROCEDURE_URI
  ) {
    invalid("mapping request coordinates are incompatible");
  }
  validateOnboardingBinding(decoded["onboarding"]);
  if (
    canonicalJson(decoded["inventory"] ?? null)
    !== canonicalJson(inventory)
  ) {
    invalid("mapping request inventory differs from the completed snapshot");
  }
  return decoded;
}

function validateCompletedRun(run: Readonly<InventoryRun>): void {
  const snapshot = run.snapshot;
  const records = snapshot["records"];
  if (
    run.snapshotDigest !== sha256(canonicalJson(snapshot))
    || !Array.isArray(records)
    || !records.every(isObject)
    || canonicalJson(records) !== canonicalJson(run.records)
    || canonicalJson(snapshot["producer"] ?? null)
      !== canonicalJson(PRODUCER)
    || !validDigest(snapshot["source_revision"])
  ) {
    invalid("completed inventory snapshot is incompatible");
  }
}

function validateOnboardingBinding(value: JsonValue | undefined): void {
  if (
    !hasExactKeys(value, [
      "kind",
      "schema_uri",
      "schema_version",
      "canonical_digest",
    ])
    || value["kind"] !== "onboarding_bundle_binding"
    || value["schema_uri"] !== ONBOARDING_SCHEMA_URI
    || value["schema_version"] !== VERSION
    || !validDigest(value["canonical_digest"])
  ) {
    invalid("mapping onboarding binding is incompatible");
  }
}

function validateBehaviorTarget(
  behaviorValue: JsonValue | undefined,
  targetsValue: JsonValue | undefined,
): JsonObject {
  if (
    !hasExactKeys(
      behaviorValue,
      ["kind", "ir_version", "document_id", "roots", "entities"],
    )
    || behaviorValue["kind"] !== "behavior_ir"
    || behaviorValue["ir_version"] !== VERSION
    || typeof behaviorValue["document_id"] !== "string"
    || !IDENTIFIER.test(behaviorValue["document_id"])
  ) {
    invalid("mapping Behavior IR is incompatible");
  }
  const behavior = behaviorValue;
  const roots = objectArray(behavior["roots"]);
  const entities = objectArray(behavior["entities"]);
  validateQuoteOrderGraph(roots, entities);
  if (!Array.isArray(targetsValue) || targetsValue.length !== 1) {
    invalid("mapping request requires exactly one supported target");
  }
  const target = targetsValue[0];
  if (
    !hasExactKeys(target, [
      "kind",
      "document_id",
      "ir_version",
      "canonical_digest",
      "target_kind",
      "target_id",
    ])
    || target["kind"] !== "behavior_entity_ref"
    || target["document_id"] !== behavior["document_id"]
    || target["ir_version"] !== behavior["ir_version"]
    || target["target_kind"] !== "use_case"
    || target["target_id"] !== QUOTE_ORDER_ID
    || canonicalJson(target["canonical_digest"] ?? null)
      !== canonicalJson(digest(sha256(canonicalJson(behavior))))
  ) {
    invalid("mapping target does not bind the supported Behavior root");
  }
  return target;
}

function validateQuoteOrderGraph(
  roots: readonly JsonObject[],
  entities: readonly JsonObject[],
): void {
  validateCanonicalEntities(entities);
  if (
    roots.length !== 1
    || !sameJson(
      roots[0],
      entityReference("use_case", QUOTE_ORDER_ID),
    )
    || entities.length !== 6
  ) {
    invalid("mapping Behavior graph shape is unsupported");
  }
  const action = findEntity(entities, "action", ACTION_ID);
  const quantity = findEntity(
    entities,
    "binding",
    QUANTITY_BINDING_ID,
  );
  const unitPrice = findEntity(
    entities,
    "binding",
    UNIT_PRICE_BINDING_ID,
  );
  const step = findEntity(entities, "step", STEP_ID);
  const useCase = findEntity(entities, "use_case", QUOTE_ORDER_ID);
  const provenances = entities.filter(
    (entity) => entity["kind"] === "provenance",
  );
  if (
    action === undefined
    || quantity === undefined
    || unitPrice === undefined
    || step === undefined
    || useCase === undefined
    || provenances.length !== 1
  ) {
    invalid("mapping Behavior graph identities are unsupported");
  }
  const provenance = provenances[0];
  if (provenance === undefined || !validProvenance(provenance)) {
    invalid("mapping Behavior provenance is invalid");
  }
  const provenanceReference = entityReference(
    "provenance",
    requireString(provenance["id"]),
  );
  if (
    !validQuoteOrderAction(action, provenanceReference)
    || !validQuoteOrderBinding(
      quantity,
      "quantity",
      provenanceReference,
    )
    || !validQuoteOrderBinding(
      unitPrice,
      "unit-price-cents",
      provenanceReference,
    )
    || !validQuoteOrderStep(step, provenanceReference)
    || !validQuoteOrderUseCase(useCase, provenanceReference)
  ) {
    invalid("mapping Behavior graph does not resolve canonically");
  }
}

function validateCanonicalEntities(entities: readonly JsonObject[]): void {
  const identities: string[] = [];
  for (const entity of entities) {
    if (
      typeof entity["kind"] !== "string"
      || !validIdentifier(entity["id"])
    ) {
      invalid("mapping Behavior entity identity is invalid");
    }
    identities.push(`${entity["kind"]}\0${entity["id"]}`);
  }
  const sorted = [...identities].sort();
  if (
    identities.some((identity, index) => identity !== sorted[index])
    || new Set(identities).size !== identities.length
  ) {
    invalid("mapping Behavior entities are not canonical");
  }
}

function validQuoteOrderAction(
  value: JsonObject,
  provenance: JsonObject,
): boolean {
  return hasExactKeys(value, [
    "kind",
    "id",
    "input_ports",
    "output_ports",
    "effects",
    "requires",
    "provenance",
  ])
    && value["kind"] === "action"
    && value["id"] === ACTION_ID
    && sameJson(value["input_ports"], quoteOrderInputs())
    && sameJson(value["output_ports"], quoteOrderOutputs())
    && sameJson(value["effects"], [])
    && sameJson(value["requires"], [])
    && sameJson(value["provenance"], provenance);
}

function validQuoteOrderBinding(
  value: JsonObject,
  name: "quantity" | "unit-price-cents",
  provenance: JsonObject,
): boolean {
  const id = name === "quantity"
    ? QUANTITY_BINDING_ID
    : UNIT_PRICE_BINDING_ID;
  return hasExactKeys(value, [
    "kind",
    "id",
    "target",
    "source",
    "provenance",
  ])
    && value["kind"] === "binding"
    && value["id"] === id
    && sameJson(
      value["target"],
      portReference("step", STEP_ID, name),
    )
    && sameJson(
      value["source"],
      portReference("use_case", QUOTE_ORDER_ID, name),
    )
    && sameJson(value["provenance"], provenance);
}

function validQuoteOrderStep(
  value: JsonObject,
  provenance: JsonObject,
): boolean {
  return hasExactKeys(value, [
    "kind",
    "id",
    "action",
    "bindings",
    "effects",
    "observations",
    "requires",
    "provenance",
  ])
    && value["kind"] === "step"
    && value["id"] === STEP_ID
    && sameJson(
      value["action"],
      entityReference("action", ACTION_ID),
    )
    && sameJson(value["bindings"], [
      entityReference("binding", QUANTITY_BINDING_ID),
      entityReference("binding", UNIT_PRICE_BINDING_ID),
    ])
    && sameJson(value["effects"], [])
    && sameJson(value["observations"], [])
    && sameJson(value["requires"], [])
    && sameJson(value["provenance"], provenance);
}

function validQuoteOrderUseCase(
  value: JsonObject,
  provenance: JsonObject,
): boolean {
  return hasExactKeys(value, [
    "kind",
    "id",
    "input_ports",
    "output_ports",
    "steps",
    "invariants",
    "requires",
    "provenance",
  ])
    && value["kind"] === "use_case"
    && value["id"] === QUOTE_ORDER_ID
    && sameJson(value["input_ports"], quoteOrderInputs())
    && sameJson(value["output_ports"], quoteOrderOutputs())
    && sameJson(
      value["steps"],
      [entityReference("step", STEP_ID)],
    )
    && sameJson(value["invariants"], [])
    && sameJson(value["requires"], [])
    && sameJson(value["provenance"], provenance);
}

function validProvenance(value: JsonObject): boolean {
  const source = value["source"];
  const producer = value["producer"];
  return hasExactKeys(value, [
    "kind",
    "id",
    "source",
    "producer",
    "captured_at",
  ])
    && value["kind"] === "provenance"
    && validIdentifier(value["id"])
    && hasExactKeys(source, ["kind", "uri", "revision"])
    && source["kind"] === "artifact_source"
    && validUri(source["uri"])
    && validDigest(source["revision"])
    && hasExactKeys(producer, ["kind", "name", "version"])
    && producer["kind"] === "producer"
    && validQualifiedName(producer["name"])
    && validNormalizedVersion(producer["version"])
    && validTimestamp(value["captured_at"]);
}

function findEntity(
  entities: readonly JsonObject[],
  kind: string,
  id: string,
): JsonObject | undefined {
  return entities.find(
    (entity) => entity["kind"] === kind && entity["id"] === id,
  );
}

function quoteOrderInputs(): JsonObject[] {
  return [port("quantity"), port("unit-price-cents")];
}

function quoteOrderOutputs(): JsonObject[] {
  return [port("total-cents")];
}

function entityReference(
  targetKind: string,
  targetId: string,
): JsonObject {
  return {
    kind: "entity_ref",
    target_kind: targetKind,
    target_id: targetId,
  };
}

function portReference(
  ownerKind: string,
  ownerId: string,
  name: string,
): JsonObject {
  return {
    kind: "port_ref",
    owner: entityReference(ownerKind, ownerId),
    direction: "input",
    name,
  };
}

function sameJson(
  value: JsonValue | undefined,
  expected: JsonValue,
): boolean {
  return canonicalJson(value ?? null) === canonicalJson(expected);
}

function validIdentifier(value: JsonValue | undefined): boolean {
  return typeof value === "string"
    && value.length <= 255
    && IDENTIFIER.test(value);
}

function validQualifiedName(value: JsonValue | undefined): boolean {
  return typeof value === "string"
    && value.length >= 3
    && value.length <= 255
    && QUALIFIED_NAME.test(value);
}

function validNormalizedVersion(value: JsonValue | undefined): boolean {
  return typeof value === "string"
    && NORMALIZED_VERSION.test(value);
}

function validUri(value: JsonValue | undefined): boolean {
  return typeof value === "string"
    && value.length >= 3
    && value.length <= 2048
    && URI.test(value);
}

function validTimestamp(value: JsonValue | undefined): boolean {
  if (
    typeof value !== "string"
    || !TIMESTAMP.test(value)
    || Number(value.slice(0, 4)) < 1
  ) {
    return false;
  }
  const parsed = new Date(value);
  return !Number.isNaN(parsed.valueOf())
    && parsed.toISOString() === `${value.slice(0, -1)}.000Z`;
}

function implementationEvidence(
  records: readonly JsonObject[],
): JsonObject[] {
  const manifests = records.filter(
    (record) => record["kind"] === "build_manifest",
  );
  const interfaces = records.filter(
    (record) =>
      record["kind"] === "public_interface"
      && (
        record["name"] === "POST /quote-order"
        || record["name"] === "quoteOrder"
      ),
  );
  if (manifests.length !== 3 || interfaces.length !== 2) {
    invalid("quote-order implementation evidence is unavailable");
  }
  return [...manifests, ...interfaces]
    .map((record) => {
      const kind = requireString(record["kind"]);
      const id = requireString(record["id"]);
      return {
        kind: "inventory_record_ref",
        target_kind: kind,
        target_id: id,
      };
    })
    .sort(referenceOrder);
}

function validDigest(value: JsonValue | undefined): boolean {
  return hasExactKeys(value, ["kind", "algorithm", "value"])
    && value["kind"] === "digest"
    && value["algorithm"] === "sha-256"
    && typeof value["value"] === "string"
    && DIGEST.test(value["value"]);
}

function digest(value: string): JsonObject {
  return { kind: "digest", algorithm: "sha-256", value };
}

function port(name: string): JsonObject {
  return {
    kind: "port",
    name,
    value_kind: "integer",
    required: true,
  };
}

function objectArray(value: JsonValue | undefined): JsonObject[] {
  if (!Array.isArray(value) || !value.every(isObject)) {
    invalid("mapping profile value is not a record list");
  }
  return value;
}

function requireString(value: JsonValue | undefined): string {
  if (typeof value !== "string") {
    invalid("mapping profile string is invalid");
  }
  return value;
}

function requireExact(
  value: JsonObject,
  fields: readonly string[],
): void {
  if (!hasExactKeys(value, fields)) {
    invalid("mapping profile fields are not exact");
  }
}

function referenceOrder(left: JsonObject, right: JsonObject): number {
  const kind = compareStrings(
    requireString(left["target_kind"]),
    requireString(right["target_kind"]),
  );
  return kind === 0
    ? compareStrings(
      requireString(left["target_id"]),
      requireString(right["target_id"]),
    )
    : kind;
}

function compareStrings(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function invalid(message: string): never {
  throw new MappingProfileError("invalid_params", message);
}
