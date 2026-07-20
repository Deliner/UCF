import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { createInterface } from "node:readline";
import { test } from "node:test";

import { canonicalJson } from "../dist/canonical-json.js";
import { buildRun } from "../dist/inventory/profile.js";
import {
  MappingProfileError,
  buildMappingPayload,
} from "../dist/mapping/profile.js";
import { decodeProfileTagged, encodeTagged } from "../dist/tagged-values.js";
import {
  typescriptFastifyFixtureRoot,
  typescriptFastifyFixtureRootPath,
} from "./fixture-root.mjs";

const fixtureRoot = typescriptFastifyFixtureRoot();
const fixtureRootPath = typescriptFastifyFixtureRootPath();
const adapterEntry = new URL("../dist/main.js", import.meta.url).pathname;
const VERSION = "1.0.0";
const REQUEST_SCHEMA_URI =
  "urn:ucf:adapter:implementation-mapping-request:1.0.0";
const RESULT_SCHEMA_URI =
  "urn:ucf:adapter:implementation-mapping-result:1.0.0";
const PROCEDURE_URI =
  "urn:ucf:adapter:typescript-fastify-static-mapping:1.0.0";

test("maps the reviewed quote-order root to exact live source evidence", () => {
  const run = inventoryRun();
  const request = mappingRequest(run.snapshot);

  const first = buildMappingPayload(
    adapterPayload(request),
    request,
    run,
  );
  const second = buildMappingPayload(
    adapterPayload(request),
    request,
    run,
  );

  assert.equal(first.schema_uri, RESULT_SCHEMA_URI);
  assert.equal(first.schema_version, VERSION);
  assert.equal(canonicalJson(first), canonicalJson(second));
  const result = decodeProfileTagged(first.value);
  assert.equal(canonicalJson(result.request), canonicalJson(request));
  assert.equal(
    canonicalJson(result.producer),
    canonicalJson({
      kind: "producer",
      name: "org.ucf.adapter.typescript-fastify",
      version: VERSION,
    }),
  );
  assert.equal(
    canonicalJson(result.capability),
    canonicalJson({
      kind: "capability",
      name: "org.ucf.adapter.mapping",
      version: VERSION,
    }),
  );
  assert.equal(result.procedure_uri, PROCEDURE_URI);
  assert.equal(result.status, "complete");
  assert.equal(result.bindings.length, 1);
  assert.equal(
    canonicalJson(result.bindings[0].behavior),
    canonicalJson(request.targets[0]),
  );
  assert.equal(
    canonicalJson(result.bindings[0].source_records),
    canonicalJson(expectedEvidence(run.records)),
  );
  assert.equal(result.bindings[0].source_records.length, 5);
  const projection = Object.fromEntries(
    Object.entries(result).filter(([name]) => name !== "id"),
  );
  assert.equal(
    result.id,
    `mapping.${sha256(canonicalJson(projection))}`,
  );
  assert.equal("claims" in result, false);
  assert.equal("mapping_basis" in result, false);
});

test("rejects absent or rebound live mapping context", () => {
  const run = inventoryRun();
  const request = mappingRequest(run.snapshot);
  assertMappingError(
    () => buildMappingPayload(adapterPayload(request), request, null),
    "operation_failed",
  );

  const changed = structuredClone(request);
  changed.inventory.source_revision.value = "f".repeat(64);
  assertMappingError(
    () => buildMappingPayload(adapterPayload(changed), changed, run),
    "invalid_params",
  );
});

test("rejects malformed mapping coordinates, source, behavior, and targets", () => {
  const run = inventoryRun();
  const valid = mappingRequest(run.snapshot);
  for (const [, mutate] of mappingThreats()) {
    const changed = structuredClone(valid);
    mutate(changed);
    assertMappingError(
      () => buildMappingPayload(
        adapterPayload(changed),
        changed,
        run,
      ),
      "invalid_params",
    );
  }

  const wrongOuter = adapterPayload(valid);
  wrongOuter.schema_version = "2.0.0";
  assertMappingError(
    () => buildMappingPayload(wrongOuter, valid, run),
    "invalid_params",
  );
  const wrongOuterSchema = adapterPayload(valid);
  wrongOuterSchema.schema_uri =
    "urn:ucf:adapter:implementation-mapping-request:2.0.0";
  assertMappingError(
    () => buildMappingPayload(wrongOuterSchema, valid, run),
    "invalid_params",
  );
  const unexpectedOuter = adapterPayload(valid);
  unexpectedOuter.future = true;
  assertMappingError(
    () => buildMappingPayload(unexpectedOuter, valid, run),
    "invalid_params",
  );
  const missingOuter = adapterPayload(valid);
  delete missingOuter.schema_version;
  assertMappingError(
    () => buildMappingPayload(missingOuter, valid, run),
    "invalid_params",
  );
});

test("raw session rejects pre-inventory and noncanonical map then recovers", async () => {
  const child = spawn(process.execPath, [adapterEntry], {
    cwd: fixtureRoot,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = createInterface({ input: child.stdout });
  const responses = lines[Symbol.asyncIterator]();
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => {
    stderr += chunk;
  });
  const exchange = async (message) => {
    child.stdin.write(`${JSON.stringify(message)}\n`);
    const response = await responses.next();
    assert.equal(response.done, false);
    return JSON.parse(response.value);
  };

  const initialized = await exchange(request(
    "initialize",
    "ucf.initialize",
    {
      kind: "initialize_request",
      protocol_version: VERSION,
      client: {
        kind: "producer",
        name: "org.ucf.adapter.mapping-test",
        version: VERSION,
      },
      capabilities: [
        capabilityRequest("org.ucf.adapter.inventory"),
        capabilityRequest("org.ucf.adapter.mapping"),
      ],
    },
  ));
  assert.equal(initialized.result.kind, "initialize_result");

  const expectedRun = inventoryRun();
  const unavailable = mappingRequest(expectedRun.snapshot);
  assertProtocolError(
    await exchange(operation(
      "unavailable",
      "ucf.map",
      adapterPayload(unavailable),
    )),
    "operation_failed",
    "unavailable",
  );

  const inventory = await collectRawInventory(exchange, 7);
  const valid = mappingRequest(inventory);
  const first = await exchange(operation(
    "valid-a",
    "ucf.map",
    adapterPayload(valid),
  ));
  assert.equal(first.result.kind, "map_result");
  const decoded = decodeProfileTagged(first.result.payload.value);
  assert.equal(decoded.bindings.length, 1);
  assert.equal(decoded.bindings[0].source_records.length, 5);

  for (const [id, mutate] of mappingThreats()) {
    const changed = structuredClone(valid);
    mutate(changed);
    assertProtocolError(
      await exchange(operation(
        id,
        "ucf.map",
        adapterPayload(changed),
      )),
      "invalid_params",
      id,
    );
  }
  const wrongOuter = adapterPayload(valid);
  wrongOuter.schema_version = "2.0.0";
  assertProtocolError(
    await exchange(operation(
      "outer-version",
      "ucf.map",
      wrongOuter,
    )),
    "invalid_params",
    "outer-version",
  );
  const wrongOuterSchema = adapterPayload(valid);
  wrongOuterSchema.schema_uri =
    "urn:ucf:adapter:implementation-mapping-request:2.0.0";
  assertProtocolError(
    await exchange(operation(
      "outer-schema",
      "ucf.map",
      wrongOuterSchema,
    )),
    "invalid_params",
    "outer-schema",
  );
  const unexpectedOuter = adapterPayload(valid);
  unexpectedOuter.future = true;
  assertProtocolError(
    await exchange(operation(
      "outer-unknown",
      "ucf.map",
      unexpectedOuter,
    )),
    "invalid_params",
    "outer-unknown",
  );
  const missingOuter = adapterPayload(valid);
  delete missingOuter.schema_version;
  assertProtocolError(
    await exchange(operation(
      "outer-missing",
      "ucf.map",
      missingOuter,
    )),
    "invalid_params",
    "outer-missing",
  );

  const noncanonical = adapterPayload(valid);
  const onboarding = noncanonical.value.entries.find(
    (entry) => entry.name === "onboarding",
  ).value;
  [
    onboarding.entries[0],
    onboarding.entries[1],
  ] = [
    onboarding.entries[1],
    onboarding.entries[0],
  ];
  assertProtocolError(
    await exchange(operation(
      "noncanonical",
      "ucf.map",
      noncanonical,
    )),
    "invalid_params",
    "noncanonical",
  );

  const recovered = await exchange(operation(
    "valid-b",
    "ucf.map",
    adapterPayload(valid),
  ));
  assert.equal(recovered.result.kind, "map_result");
  assert.equal(
    canonicalJson(recovered.result.payload),
    canonicalJson(first.result.payload),
  );
  const shutdown = await exchange(request(
    "shutdown",
    "ucf.shutdown",
    { kind: "shutdown_request" },
  ));
  assert.equal(shutdown.result.kind, "shutdown_result");
  child.stdin.end();
  const exitCode = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", resolve);
  });
  assert.equal(exitCode, 0);
  assert.equal(stderr, "");
});

function mappingThreats() {
  return [
    [
      "unknown",
      (request) => {
        request.unexpected = true;
      },
    ],
    [
      "request-kind",
      (request) => {
        request.kind = "implementation_mapping_request_v2";
      },
    ],
    [
      "request-version",
      (request) => {
        request.implementation_evidence_version = "2.0.0";
      },
    ],
    [
      "capability",
      (request) => {
        request.capability.name = "org.ucf.adapter.verification";
      },
    ],
    [
      "procedure",
      (request) => {
        request.adapter_procedure_uri =
          "urn:ucf:adapter:typescript-fastify-other-mapping:1.0.0";
      },
    ],
    [
      "profile-procedure",
      (request) => {
        request.profile_procedure_uri =
          "urn:ucf:implementation-evidence:map:2.0.0";
      },
    ],
    [
      "request-schema",
      (request) => {
        request.schema_uri =
          "urn:ucf:adapter:implementation-mapping-request:2.0.0";
      },
    ],
    [
      "source-revision",
      (request) => {
        request.inventory.source_revision.value = "f".repeat(64);
      },
    ],
    [
      "inventory-producer",
      (request) => {
        request.inventory.producer.version = "1.0.1";
      },
    ],
    [
      "inventory-records",
      (request) => {
        request.inventory.records.pop();
      },
    ],
    [
      "inventory-record-name",
      (request) => {
        const record = request.inventory.records.find(
          (candidate) =>
            candidate.kind === "public_interface"
            && candidate.name === "quoteOrder",
        );
        record.name = "quoteOrders";
      },
    ],
    [
      "inventory-record-order",
      (request) => {
        request.inventory.records.reverse();
      },
    ],
    [
      "missing-target",
      (request) => {
        request.behavior.entities = request.behavior.entities.filter(
          (entity) => entity.id !== "use-case.quote-order",
        );
        rebindBehavior(request);
      },
    ],
    [
      "broken-step-action",
      (request) => {
        const step = request.behavior.entities.find(
          (entity) => entity.kind === "step",
        );
        step.action.target_id = "action.missing";
        rebindBehavior(request);
      },
    ],
    [
      "broken-binding-owner",
      (request) => {
        const binding = request.behavior.entities.find(
          (entity) =>
            entity.kind === "binding"
            && entity.id === "binding.quote-order.quantity",
        );
        binding.source.owner.target_id = "use-case.missing";
        rebindBehavior(request);
      },
    ],
    [
      "unknown-action-field",
      (request) => {
        const action = request.behavior.entities.find(
          (entity) => entity.kind === "action",
        );
        action.unexpected = true;
        rebindBehavior(request);
      },
    ],
    [
      "duplicate-entity",
      (request) => {
        request.behavior.entities.push(
          structuredClone(request.behavior.entities[0]),
        );
        rebindBehavior(request);
      },
    ],
    [
      "noncanonical-entities",
      (request) => {
        request.behavior.entities.reverse();
        rebindBehavior(request);
      },
    ],
    [
      "noncanonical-ports",
      (request) => {
        const useCase = request.behavior.entities.find(
          (entity) => entity.kind === "use_case",
        );
        useCase.input_ports.reverse();
        rebindBehavior(request);
      },
    ],
    [
      "extra-root",
      (request) => {
        request.behavior.roots.push(
          structuredClone(request.behavior.roots[0]),
        );
        rebindBehavior(request);
      },
    ],
    [
      "wrong-target-kind",
      (request) => {
        request.targets[0].target_kind = "action";
      },
    ],
    [
      "wrong-target-document",
      (request) => {
        request.targets[0].document_id = "behavior.changed";
      },
    ],
    [
      "wrong-target-version",
      (request) => {
        request.targets[0].ir_version = "2.0.0";
      },
    ],
    [
      "wrong-target-digest",
      (request) => {
        request.targets[0].canonical_digest.value = "f".repeat(64);
      },
    ],
    [
      "empty-targets",
      (request) => {
        request.targets = [];
      },
    ],
    [
      "duplicate-target",
      (request) => {
        request.targets.push(structuredClone(request.targets[0]));
      },
    ],
    [
      "noncanonical-target",
      (request) => {
        request.targets = [
          {
            ...structuredClone(request.targets[0]),
            target_id: "use-case.zzz",
          },
          structuredClone(request.targets[0]),
        ];
      },
    ],
  ];
}

function inventoryRun() {
  const ignoreRules = [
    {
      kind: "ignore_rule",
      id: "ignore.dist",
      reason: "org.ucf.inventory.generated",
      matcher: { kind: "path_segment", segment: "dist" },
    },
    {
      kind: "ignore_rule",
      id: "ignore.node-modules",
      reason: "org.ucf.inventory.generated",
      matcher: { kind: "path_segment", segment: "node_modules" },
    },
  ];
  return buildRun(
    {
      logical: {
        subject_uri:
          "urn:ucf:repository:typescript-fastify-legacy-quote",
        root_path: ".",
        fact_kinds: [
          "api_description",
          "build_manifest",
          "public_interface",
          "repository_entry",
          "test_asset",
        ],
        ignore_policy: {
          kind: "ignore_policy",
          policy_version: VERSION,
          rules: ignoreRules,
        },
      },
      subjectUri:
        "urn:ucf:repository:typescript-fastify-legacy-quote",
      rootPath: fixtureRootPath,
      ignorePolicy: {
        kind: "ignore_policy",
        policy_version: VERSION,
        rules: ignoreRules,
      },
      ignoreRules,
      recordLimit: 7,
      cursor: null,
    },
    "mapping-test",
  );
}

function mappingRequest(inventory) {
  const behavior = quoteBehavior();
  const target = {
    kind: "behavior_entity_ref",
    document_id: behavior.document_id,
    ir_version: behavior.ir_version,
    canonical_digest: digest(sha256(canonicalJson(behavior))),
    target_kind: "use_case",
    target_id: "use-case.quote-order",
  };
  return {
    kind: "implementation_mapping_request",
    implementation_evidence_version: VERSION,
    schema_uri: REQUEST_SCHEMA_URI,
    capability: {
      kind: "capability",
      name: "org.ucf.adapter.mapping",
      version: VERSION,
    },
    profile_procedure_uri:
      "urn:ucf:implementation-evidence:map:1.0.0",
    adapter_procedure_uri: PROCEDURE_URI,
    onboarding: {
      kind: "onboarding_bundle_binding",
      schema_uri: "urn:ucf:onboarding:bundle:1.0.0",
      schema_version: VERSION,
      canonical_digest: digest("a".repeat(64)),
    },
    behavior,
    inventory,
    targets: [target],
  };
}

function rebindBehavior(request) {
  request.targets[0].canonical_digest =
    digest(sha256(canonicalJson(request.behavior)));
}

function quoteBehavior() {
  const provenanceId = `provenance.${"b".repeat(64)}`;
  const provenance = entityReference("provenance", provenanceId);
  const useCase = entityReference("use_case", "use-case.quote-order");
  const step = entityReference("step", "step.quote-order");
  const action = entityReference("action", "action.quote-order");
  const quantity = binding(
    "quantity",
    useCase,
    step,
    provenance,
  );
  const unitPrice = binding(
    "unit-price-cents",
    useCase,
    step,
    provenance,
  );
  const inputs = [
    port("quantity", "integer"),
    port("unit-price-cents", "integer"),
  ];
  const outputs = [port("total-cents", "integer")];
  return {
    kind: "behavior_ir",
    ir_version: VERSION,
    document_id: `behavior.${"b".repeat(64)}`,
    roots: [useCase],
    entities: [
      {
        kind: "action",
        id: action.target_id,
        input_ports: inputs,
        output_ports: outputs,
        effects: [],
        requires: [],
        provenance,
      },
      quantity,
      unitPrice,
      {
        kind: "provenance",
        id: provenanceId,
        source: {
          kind: "artifact_source",
          uri: `urn:ucf:onboarding:decision-set:${"b".repeat(64)}`,
          revision: digest("b".repeat(64)),
        },
        producer: {
          kind: "producer",
          name: "org.ucf.ecosystem-reviewer",
          version: VERSION,
        },
        captured_at: "2026-07-19T12:00:00Z",
      },
      {
        kind: "step",
        id: step.target_id,
        action,
        bindings: [
          entityReference("binding", quantity.id),
          entityReference("binding", unitPrice.id),
        ],
        effects: [],
        observations: [],
        requires: [],
        provenance,
      },
      {
        kind: "use_case",
        id: useCase.target_id,
        input_ports: inputs,
        output_ports: outputs,
        steps: [step],
        invariants: [],
        requires: [],
        provenance,
      },
    ],
  };
}

function binding(name, sourceOwner, targetOwner, provenance) {
  return {
    kind: "binding",
    id: `binding.quote-order.${name}`,
    target: {
      kind: "port_ref",
      owner: targetOwner,
      direction: "input",
      name,
    },
    source: {
      kind: "port_ref",
      owner: sourceOwner,
      direction: "input",
      name,
    },
    provenance,
  };
}

function port(name, valueKind) {
  return {
    kind: "port",
    name,
    value_kind: valueKind,
    required: true,
  };
}

function entityReference(targetKind, targetId) {
  return {
    kind: "entity_ref",
    target_kind: targetKind,
    target_id: targetId,
  };
}

function expectedEvidence(records) {
  return records
    .filter(
      (record) =>
        record.kind === "build_manifest"
        || record.kind === "public_interface"
        && ["POST /quote-order", "quoteOrder"].includes(record.name),
    )
    .map((record) => ({
      kind: "inventory_record_ref",
      target_kind: record.kind,
      target_id: record.id,
    }))
    .sort(referenceOrder);
}

function adapterPayload(request) {
  return {
    kind: "adapter_payload",
    schema_uri: REQUEST_SCHEMA_URI,
    schema_version: VERSION,
    value: encodeTagged(request),
  };
}

async function collectRawInventory(exchange, recordLimit) {
  const records = [];
  let cursor = null;
  let page;
  let pageNumber = 0;
  do {
    pageNumber += 1;
    const response = await exchange(operation(
      `inventory-${pageNumber}`,
      "ucf.inventory",
      inventoryPayload(inventoryRequest(recordLimit, cursor)),
    ));
    assert.equal(response.result.kind, "inventory_result");
    page = decodeProfileTagged(response.result.payload.value);
    records.push(...page.records);
    cursor = page.next_cursor;
  } while (cursor !== null);
  return {
    kind: "inventory_snapshot",
    inventory_version: page.inventory_version,
    schema_uri: "urn:ucf:schema:inventory:1.0.0",
    subject_uri: page.subject_uri,
    path_identity: page.path_identity,
    source_revision: page.source_revision,
    producer: page.producer,
    capability: page.capability,
    applied_policy: page.applied_policy,
    coverage: page.coverage,
    records,
  };
}

function inventoryRequest(recordLimit, cursor) {
  return {
    kind: "inventory_request_profile",
    inventory_version: VERSION,
    schema_uri: "urn:ucf:adapter:inventory-request:1.0.0",
    subject_uri:
      "urn:ucf:repository:typescript-fastify-legacy-quote",
    root_path: ".",
    fact_kinds: [
      "api_description",
      "build_manifest",
      "public_interface",
      "repository_entry",
      "test_asset",
    ],
    ignore_policy: {
      kind: "ignore_policy",
      policy_version: VERSION,
      rules: [
        {
          kind: "ignore_rule",
          id: "ignore.dist",
          reason: "org.ucf.inventory.generated",
          matcher: { kind: "path_segment", segment: "dist" },
        },
        {
          kind: "ignore_rule",
          id: "ignore.node-modules",
          reason: "org.ucf.inventory.generated",
          matcher: { kind: "path_segment", segment: "node_modules" },
        },
      ],
    },
    page: {
      kind: "inventory_page_request",
      record_limit: recordLimit,
      cursor,
    },
  };
}

function inventoryPayload(profile) {
  return {
    kind: "adapter_payload",
    schema_uri: "urn:ucf:adapter:inventory-request:1.0.0",
    schema_version: VERSION,
    value: encodeTagged(profile),
  };
}

function request(id, method, params) {
  return { jsonrpc: "2.0", id, method, params };
}

function operation(id, method, payload) {
  return request(id, method, {
    kind: `${method.slice("ucf.".length)}_request`,
    payload,
  });
}

function capabilityRequest(name) {
  return {
    kind: "capability_request",
    name,
    minimum_version: VERSION,
    required: true,
  };
}

function digest(value) {
  return { kind: "digest", algorithm: "sha-256", value };
}

function referenceOrder(left, right) {
  const kind = compareStrings(left.target_kind, right.target_kind);
  return kind === 0
    ? compareStrings(left.target_id, right.target_id)
    : kind;
}

function compareStrings(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function assertMappingError(callback, code) {
  assert.throws(
    callback,
    (error) =>
      error instanceof MappingProfileError
      && error.code === code,
  );
}

function assertProtocolError(response, code, id) {
  assert.deepEqual(
    Object.keys(response).sort(),
    ["error", "id", "jsonrpc"],
  );
  assert.equal(response.jsonrpc, "2.0");
  assert.equal(response.id, id);
  assert.deepEqual(
    Object.keys(response.error).sort(),
    ["code", "data", "message"],
  );
  assert.deepEqual(
    Object.keys(response.error.data).sort(),
    ["category", "ucf_code"],
  );
  assert.equal(response.error.data.ucf_code, code);
  assert.equal(
    response.error.data.category,
    code === "operation_failed"
      ? "adapter_failure"
      : "protocol_failure",
  );
}
