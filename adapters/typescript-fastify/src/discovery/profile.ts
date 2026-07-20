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
  "urn:ucf:adapter:discovery-request:1.0.0";
const RESULT_SCHEMA_URI =
  "urn:ucf:adapter:discovery-result:1.0.0";
const INVENTORY_SCHEMA_URI =
  "urn:ucf:schema:inventory:1.0.0";
const INVENTORY_CAPABILITY: JsonObject = {
  kind: "capability",
  name: "org.ucf.adapter.inventory",
  version: VERSION,
};
const PRODUCER: JsonObject = {
  kind: "producer",
  name: "org.ucf.adapter.typescript-fastify",
  version: VERSION,
};
const CAPABILITY: JsonObject = {
  kind: "capability",
  name: "org.ucf.adapter.discovery",
  version: VERSION,
};
const PROCEDURE_URI =
  "urn:ucf:onboarding-procedure:"
  + "typescript-fastify-static-discovery:1.0.0";
const CONFIDENCE_BASIS =
  "urn:ucf:onboarding-confidence:"
  + "typescript-exported-function:1.0.0";
const EXPORTED_FUNCTION_URI =
  "urn:ucf:inventory-interface:"
  + "typescript-exported-function:1.0.0";
const FASTIFY_ROUTE_URI =
  "urn:ucf:inventory-interface:"
  + "fastify-literal-route:1.0.0";
const DIGEST = /^[0-9a-f]{64}$/;
const RECORD_PREFIX = new Map([
  ["build_manifest", "manifest"],
  ["inventory_ignore_match", "ignore"],
  ["inventory_provenance", "provenance"],
  ["public_interface", "interface"],
  ["repository_entry", "entry"],
  ["test_asset", "test"],
]);
const EXPECTED_MANIFEST_DIALECTS = new Map([
  [
    "package-lock.json",
    "urn:ucf:inventory-dialect:npm-lockfile-v3:1.0.0",
  ],
  [
    "package.json",
    "urn:ucf:inventory-dialect:npm-package-json:1.0.0",
  ],
  [
    "tsconfig.json",
    "urn:ucf:inventory-dialect:typescript-config:1.0.0",
  ],
]);

interface PortSpec {
  name: string;
  valueKind: string;
  required: boolean;
}

interface FunctionSpec {
  slug: string;
  confidence: string;
  inputs: readonly PortSpec[];
  outputs: readonly PortSpec[];
}

const FUNCTIONS = new Map<string, FunctionSpec>([
  [
    "formatReceipt",
    {
      slug: "format-receipt",
      confidence: "0.82",
      inputs: [
        { name: "total-cents", valueKind: "integer", required: true },
      ],
      outputs: [
        { name: "receipt", valueKind: "string", required: true },
      ],
    },
  ],
  [
    "legacyDiscountHint",
    {
      slug: "legacy-discount-hint",
      confidence: "0.61",
      inputs: [
        { name: "code", valueKind: "string", required: true },
      ],
      outputs: [
        {
          name: "discount-percent",
          valueKind: "integer",
          required: false,
        },
      ],
    },
  ],
  [
    "normalizeCoupon",
    {
      slug: "normalize-coupon",
      confidence: "0.82",
      inputs: [
        { name: "code", valueKind: "string", required: true },
      ],
      outputs: [
        {
          name: "normalized-code",
          valueKind: "string",
          required: true,
        },
      ],
    },
  ],
  [
    "quoteOrder",
    {
      slug: "quote-order",
      confidence: "0.82",
      inputs: [
        { name: "quantity", valueKind: "integer", required: true },
        {
          name: "unit-price-cents",
          valueKind: "integer",
          required: true,
        },
      ],
      outputs: [
        {
          name: "total-cents",
          valueKind: "integer",
          required: true,
        },
      ],
    },
  ],
]);

export class DiscoveryProfileError extends Error {
  public constructor(
    public readonly code: "invalid_params" | "operation_failed",
    message: string,
  ) {
    super(message);
    this.name = "DiscoveryProfileError";
  }
}

export function buildDiscoveryPayload(
  payload: JsonValue | undefined,
  decodedValue: JsonValue,
  run: Readonly<InventoryRun> | null,
): JsonObject {
  if (run === null) {
    throw new DiscoveryProfileError(
      "operation_failed",
      "discovery requires a completed inventory snapshot",
    );
  }
  validateCachedRun(run);
  const request = decodeRequest(payload, decodedValue, run.snapshot);
  const result = buildResult(request);
  return {
    kind: "adapter_payload",
    schema_uri: RESULT_SCHEMA_URI,
    schema_version: VERSION,
    value: encodeTagged(result),
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
    invalid("discovery payload coordinates are incompatible");
  }
  if (!isObject(decoded)) {
    invalid("discovery request root is not a record");
  }
  requireExact(decoded, [
    "kind",
    "onboarding_version",
    "schema_uri",
    "capability",
    "inventory_binding",
    "inventory",
  ]);
  if (
    decoded["kind"] !== "discovery_request_profile"
    || decoded["onboarding_version"] !== VERSION
    || decoded["schema_uri"] !== REQUEST_SCHEMA_URI
    || canonicalJson(decoded["capability"] ?? null)
      !== canonicalJson(CAPABILITY)
  ) {
    invalid("discovery request coordinates are incompatible");
  }
  const embedded = decoded["inventory"];
  if (
    !isObject(embedded)
    || canonicalJson(embedded) !== canonicalJson(inventory)
  ) {
    invalid(
      "discovery request does not embed the completed inventory snapshot",
    );
  }
  validateInventoryBinding(decoded["inventory_binding"], inventory);
  return decoded;
}

function validateCachedRun(run: Readonly<InventoryRun>): void {
  const snapshot = run.snapshot;
  requireExact(snapshot, [
    "kind",
    "inventory_version",
    "schema_uri",
    "subject_uri",
    "path_identity",
    "source_revision",
    "producer",
    "capability",
    "applied_policy",
    "coverage",
    "records",
  ]);
  if (
    snapshot["kind"] !== "inventory_snapshot"
    || snapshot["inventory_version"] !== VERSION
    || snapshot["schema_uri"] !== INVENTORY_SCHEMA_URI
    || typeof snapshot["subject_uri"] !== "string"
    || snapshot["path_identity"] !== "unicode-nfc-ascii-casefold-1"
    || !validDigest(snapshot["source_revision"])
    || canonicalJson(snapshot["producer"] ?? null)
      !== canonicalJson(PRODUCER)
    || canonicalJson(snapshot["capability"] ?? null)
      !== canonicalJson(INVENTORY_CAPABILITY)
    || run.snapshotDigest !== sha256(canonicalJson(snapshot))
    || canonicalJson(run.records)
      !== canonicalJson(snapshot["records"] ?? null)
  ) {
    invalid("completed inventory snapshot is incompatible");
  }
  const records = objectArray(snapshot["records"]);
  const identities: string[] = [];
  for (const record of records) {
    const kind = record["kind"];
    const id = record["id"];
    const prefix = typeof kind === "string"
      ? RECORD_PREFIX.get(kind)
      : undefined;
    if (
      prefix === undefined
      || typeof id !== "string"
      || id !== `${prefix}.${recordDigest(record)}`
    ) {
      invalid("completed inventory record identity is invalid");
    }
    identities.push(`${kind}\0${id}`);
  }
  const sortedIdentities = [...identities].sort();
  if (
    identities.some(
      (identity, index) => identity !== sortedIdentities[index],
    )
    || new Set(identities).size !== identities.length
  ) {
    invalid("completed inventory records are not canonical");
  }
  validateSupportedFacts(records);
}

function validateSupportedFacts(records: readonly JsonObject[]): void {
  const byId = new Map<string, JsonObject>();
  for (const record of records) {
    const id = record["id"];
    if (typeof id !== "string" || byId.has(id)) {
      invalid("completed inventory record IDs are duplicated");
    }
    byId.set(id, record);
  }

  const interfaces = records.filter(
    (record) => record["kind"] === "public_interface",
  );
  const names = interfaces.map((record) => record["name"]);
  const expectedNames = [
    "POST /quote-order",
    "buildApp",
    "formatReceipt",
    "legacyDiscountHint",
    "normalizeCoupon",
    "quoteOrder",
  ];
  if (
    names.some((name) => typeof name !== "string")
    || names.length !== expectedNames.length
    || [...names].sort().some(
      (name, index) => name !== expectedNames[index],
    )
    || new Set(names).size !== names.length
  ) {
    invalid("completed inventory public interfaces are incompatible");
  }
  for (const record of interfaces) {
    const name = String(record["name"]);
    const expectedDialect = name === "POST /quote-order"
      ? FASTIFY_ROUTE_URI
      : EXPORTED_FUNCTION_URI;
    if (
      record["interface_kind_uri"] !== expectedDialect
      || entryPath(record, byId) !== "src/service.ts"
    ) {
      invalid("completed inventory interface fact is incompatible");
    }
  }

  const manifests = records.filter(
    (record) => record["kind"] === "build_manifest",
  );
  if (manifests.length !== EXPECTED_MANIFEST_DIALECTS.size) {
    invalid("completed inventory build manifests are incompatible");
  }
  const seenPaths = new Set<string>();
  for (const manifest of manifests) {
    const path = entryPath(manifest, byId);
    if (
      seenPaths.has(path)
      || manifest["dialect_uri"] !== EXPECTED_MANIFEST_DIALECTS.get(path)
    ) {
      invalid("completed inventory build manifest is incompatible");
    }
    seenPaths.add(path);
  }
}

function buildResult(request: JsonObject): JsonObject {
  const inventory = requireObject(request["inventory"]);
  const records = objectArray(inventory["records"]);
  const interfaces = records
    .filter((record) => record["kind"] === "public_interface")
    .sort(recordIdOrder);
  const manifests = records
    .filter((record) => record["kind"] === "build_manifest")
    .sort(recordIdOrder);
  const route = interfaces.find(
    (record) => record["name"] === "POST /quote-order",
  );
  if (route === undefined) {
    invalid("completed inventory route fact is unavailable");
  }

  const context: JsonObject = {
    inventory_binding: request["inventory_binding"] ?? null,
    producer: PRODUCER,
    capability: CAPABILITY,
    procedure_uri: PROCEDURE_URI,
  };
  const candidates: JsonObject[] = [];
  const eligible: JsonObject[] = [];
  const uncovered: JsonObject[] = [];
  for (const subject of interfaces) {
    const reference = inventoryReference(subject);
    eligible.push(reference);
    const name = requireString(subject["name"]);
    const specification = FUNCTIONS.get(name);
    if (
      specification === undefined
      || subject["interface_kind_uri"] !== EXPORTED_FUNCTION_URI
    ) {
      uncovered.push(reference);
      continue;
    }
    const proposal = proposalFor(specification);
    const evidence = name === "quoteOrder"
      ? [
          ...manifests.map(inventoryReference),
          inventoryReference(route),
          reference,
        ].sort(referenceOrder)
      : [reference];
    const candidate: JsonObject = {
      kind: "discovery_candidate",
      id: `candidate.${"0".repeat(64)}`,
      semantic_digest: digest(sha256(canonicalJson(proposal))),
      subject: reference,
      evidence,
      confidence: {
        kind: "confidence",
        scale: "decimal-0-to-1",
        value: specification.confidence,
        basis: CONFIDENCE_BASIS,
      },
      proposal,
    };
    candidate["id"] = candidateId(candidate, context);
    candidates.push(candidate);
  }
  eligible.sort(referenceOrder);
  uncovered.sort(referenceOrder);
  candidates.sort((left, right) =>
    compareStrings(
      requireString(left["id"]),
      requireString(right["id"]),
    ));
  return {
    kind: "discovery_result_profile",
    onboarding_version: VERSION,
    schema_uri: RESULT_SCHEMA_URI,
    ...context,
    coverage: {
      kind: "discovery_coverage",
      status: uncovered.length === 0 ? "complete" : "partial",
      eligible_subjects: eligible,
      uncovered_subjects: uncovered,
    },
    diagnostics: [],
    candidates,
  };
}

function proposalFor(specification: FunctionSpec): JsonObject {
  const slug = specification.slug;
  const actionId = `action.${slug}`;
  const stepId = `step.${slug}`;
  const useCaseId = `use-case.${slug}`;
  const actionReference = entityReference("proposed_action", actionId);
  const stepReference = entityReference("proposed_step", stepId);
  const useCaseReference = entityReference(
    "proposed_use_case",
    useCaseId,
  );
  const inputs = specification.inputs.map(port);
  const outputs = specification.outputs.map(port);
  const bindings: JsonObject[] = [];
  const bindingReferences: JsonObject[] = [];
  for (const input of inputs) {
    const name = requireString(input["name"]);
    const bindingId = `binding.${slug}.${name}`;
    const bindingReference = entityReference(
      "proposed_binding",
      bindingId,
    );
    bindingReferences.push(bindingReference);
    bindings.push({
      kind: "proposed_binding",
      id: bindingId,
      target: {
        kind: "proposal_port_ref",
        owner: stepReference,
        direction: "input",
        name,
      },
      source: {
        kind: "proposal_port_ref",
        owner: useCaseReference,
        direction: "input",
        name,
      },
    });
  }
  const entities: JsonObject[] = [
    {
      kind: "proposed_action",
      id: actionId,
      input_ports: inputs,
      output_ports: outputs,
    },
    ...bindings,
    {
      kind: "proposed_step",
      id: stepId,
      action: actionReference,
      bindings: bindingReferences,
    },
    {
      kind: "proposed_use_case",
      id: useCaseId,
      input_ports: inputs,
      output_ports: outputs,
      steps: [stepReference],
    },
  ];
  entities.sort((left, right) => {
    const kind = compareStrings(
      requireString(left["kind"]),
      requireString(right["kind"]),
    );
    return kind === 0
      ? compareStrings(
          requireString(left["id"]),
          requireString(right["id"]),
        )
      : kind;
  });
  return {
    kind: "candidate_proposal",
    root: useCaseReference,
    entities,
  };
}

function candidateId(
  candidate: JsonObject,
  context: JsonObject,
): string {
  const projection: JsonObject = {
    candidate: {
      kind: candidate["kind"] ?? null,
      subject: candidate["subject"] ?? null,
      evidence: candidate["evidence"] ?? null,
      confidence: candidate["confidence"] ?? null,
      proposal: candidate["proposal"] ?? null,
    },
    capability: context["capability"] ?? null,
    inventory_binding: context["inventory_binding"] ?? null,
    procedure_uri: context["procedure_uri"] ?? null,
    producer: context["producer"] ?? null,
  };
  return `candidate.${sha256(canonicalJson(projection))}`;
}

function validateInventoryBinding(
  value: JsonValue | undefined,
  inventory: JsonObject,
): void {
  if (
    !hasExactKeys(value, [
      "kind",
      "schema_uri",
      "inventory_version",
      "subject_uri",
      "source_revision",
      "canonical_digest",
    ])
  ) {
    invalid("inventory binding fields are not exact");
  }
  const expected: JsonObject = {
    kind: "inventory_binding",
    schema_uri: INVENTORY_SCHEMA_URI,
    inventory_version: VERSION,
    subject_uri: inventory["subject_uri"] ?? null,
    source_revision: inventory["source_revision"] ?? null,
    canonical_digest: digest(sha256(canonicalJson(inventory))),
  };
  if (canonicalJson(value) !== canonicalJson(expected)) {
    invalid("inventory binding does not name the completed snapshot");
  }
}

function entryPath(
  record: JsonObject,
  byId: ReadonlyMap<string, JsonObject>,
): string {
  const reference = record["entry"];
  if (
    !hasExactKeys(reference, ["kind", "target_kind", "target_id"])
    || reference["kind"] !== "inventory_record_ref"
    || reference["target_kind"] !== "repository_entry"
    || typeof reference["target_id"] !== "string"
  ) {
    invalid("inventory fact entry reference is invalid");
  }
  const entry = byId.get(reference["target_id"]);
  if (
    entry === undefined
    || entry["kind"] !== "repository_entry"
    || typeof entry["path"] !== "string"
  ) {
    invalid("inventory fact entry reference is broken");
  }
  return entry["path"];
}

function inventoryReference(record: JsonObject): JsonObject {
  return {
    kind: "inventory_record_ref",
    target_kind: requireString(record["kind"]),
    target_id: requireString(record["id"]),
  };
}

function entityReference(kind: string, id: string): JsonObject {
  return {
    kind: "proposal_entity_ref",
    target_kind: kind,
    target_id: id,
  };
}

function port(specification: PortSpec): JsonObject {
  return {
    kind: "port",
    name: specification.name,
    value_kind: specification.valueKind,
    required: specification.required,
  };
}

function digest(value: string): JsonObject {
  if (!DIGEST.test(value)) {
    invalid("discovery digest is not canonical");
  }
  return { kind: "digest", algorithm: "sha-256", value };
}

function validDigest(value: JsonValue | undefined): boolean {
  return hasExactKeys(value, ["kind", "algorithm", "value"])
    && value["kind"] === "digest"
    && value["algorithm"] === "sha-256"
    && typeof value["value"] === "string"
    && DIGEST.test(value["value"]);
}

function recordDigest(record: JsonObject): string {
  const projection = Object.fromEntries(
    Object.entries(record).filter(([name]) => name !== "id"),
  ) as JsonObject;
  return sha256(canonicalJson(projection));
}

function objectArray(value: JsonValue | undefined): JsonObject[] {
  if (!Array.isArray(value) || !value.every(isObject)) {
    invalid("inventory records are not a record list");
  }
  return value;
}

function requireObject(value: JsonValue | undefined): JsonObject {
  if (!isObject(value)) {
    invalid("discovery value is not a record");
  }
  return value;
}

function requireString(value: JsonValue | undefined): string {
  if (typeof value !== "string") {
    invalid("discovery string value is invalid");
  }
  return value;
}

function requireExact(
  value: JsonObject,
  fields: readonly string[],
): void {
  if (!hasExactKeys(value, fields)) {
    invalid("discovery profile fields are not exact");
  }
}

function recordIdOrder(left: JsonObject, right: JsonObject): number {
  return compareStrings(
    requireString(left["id"]),
    requireString(right["id"]),
  );
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
  throw new DiscoveryProfileError("invalid_params", message);
}
