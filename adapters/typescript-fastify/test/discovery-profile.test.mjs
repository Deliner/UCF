import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { createInterface } from "node:readline";
import { test } from "node:test";

import { canonicalJson } from "../dist/canonical-json.js";
import {
  DiscoveryProfileError,
  buildDiscoveryPayload,
} from "../dist/discovery/profile.js";
import { buildRun } from "../dist/inventory/profile.js";
import {
  TaggedValueError,
  decodeProfileTagged,
  encodeTagged,
} from "../dist/tagged-values.js";
import {
  typescriptFastifyFixtureRoot,
  typescriptFastifyFixtureRootPath,
} from "./fixture-root.mjs";

const fixtureRoot = typescriptFastifyFixtureRoot();
const fixtureRootPath = typescriptFastifyFixtureRootPath();
const adapterEntry = new URL("../dist/main.js", import.meta.url).pathname;
const VERSION = "1.0.0";
const REQUEST_SCHEMA_URI =
  "urn:ucf:adapter:discovery-request:1.0.0";
const RESULT_SCHEMA_URI =
  "urn:ucf:adapter:discovery-result:1.0.0";
const INVENTORY_SCHEMA_URI =
  "urn:ucf:schema:inventory:1.0.0";
const CAPABILITY = {
  kind: "capability",
  name: "org.ucf.adapter.discovery",
  version: VERSION,
};
const EXPECTED_SEMANTIC_DIGESTS = new Map([
  [
    "use-case.format-receipt",
    "ba7d915efbc19bff087cee325125b801f64d3d3f932db3df96a87d9dadf4569c",
  ],
  [
    "use-case.legacy-discount-hint",
    "d0182d40ad306dd41fef8090a3caca94ba491f30a5a1dc83a702dbd5f207f8b8",
  ],
  [
    "use-case.normalize-coupon",
    "d44419a028758d14eb1dfc5edc5d1c2b8d6fc1f1744fa6b17f063117d409261f",
  ],
  [
    "use-case.quote-order",
    "cd09cf6ac27457ddbd62715ad903b4b3e0217c6b580cbde1d75c8d2c1b17153a",
  ],
]);

test("derives exact contextual TypeScript discovery evidence", () => {
  const run = inventoryRun();
  const request = discoveryRequest(run.snapshot);
  const payload = buildDiscoveryPayload(
    adapterPayload(request),
    request,
    run,
  );
  assert.equal(payload.schema_uri, RESULT_SCHEMA_URI);
  assert.equal(payload.schema_version, VERSION);

  const result = decodeProfileTagged(payload.value);
  const recordsById = new Map(
    run.records.map((record) => [record.id, record]),
  );
  assert.deepEqual(result.diagnostics, []);
  assert.equal(result.coverage.status, "partial");
  assert.deepEqual(
    result.coverage.eligible_subjects.map(
      (reference) => recordsById.get(reference.target_id).name,
    ).sort(),
    [
      "POST /quote-order",
      "buildApp",
      "formatReceipt",
      "legacyDiscountHint",
      "normalizeCoupon",
      "quoteOrder",
    ],
  );
  assert.deepEqual(
    result.coverage.uncovered_subjects.map(
      (reference) => recordsById.get(reference.target_id).name,
    ).sort(),
    ["POST /quote-order", "buildApp"],
  );
  assert.deepEqual(
    new Map(
      result.candidates.map((candidate) => [
        candidate.proposal.root.target_id,
        candidate.semantic_digest.value,
      ]),
    ),
    EXPECTED_SEMANTIC_DIGESTS,
  );
  assert.equal(result.candidates.length, 4);

  for (const candidate of result.candidates) {
    const projection = {
      candidate: Object.fromEntries(
        Object.entries(candidate).filter(
          ([name]) => !["id", "semantic_digest"].includes(name),
        ),
      ),
      capability: result.capability,
      inventory_binding: result.inventory_binding,
      procedure_uri: result.procedure_uri,
      producer: result.producer,
    };
    assert.equal(
      candidate.id,
      `candidate.${sha256(canonicalJson(projection))}`,
    );
  }

  const quote = result.candidates.find(
    (candidate) =>
      candidate.proposal.root.target_id === "use-case.quote-order",
  );
  assert.ok(quote);
  assert.deepEqual(
    quote.evidence.map((reference) => {
      const record = recordsById.get(reference.target_id);
      if (record.kind === "public_interface") {
        return [record.kind, record.name];
      }
      const entry = recordsById.get(record.entry.target_id);
      return [record.kind, entry.path];
    }).sort(),
    [
      ["build_manifest", "package-lock.json"],
      ["build_manifest", "package.json"],
      ["build_manifest", "tsconfig.json"],
      ["public_interface", "POST /quote-order"],
      ["public_interface", "quoteOrder"],
    ],
  );
});

test("rejects absent, rebound, or structurally changed inventory", () => {
  const run = inventoryRun();
  const valid = discoveryRequest(run.snapshot);
  assertDiscoveryError(
    () => buildDiscoveryPayload(adapterPayload(valid), valid, null),
    "operation_failed",
  );

  const rebound = structuredClone(valid);
  rebound.inventory_binding.canonical_digest.value = "0".repeat(64);
  assertDiscoveryError(
    () => buildDiscoveryPayload(adapterPayload(rebound), rebound, run),
    "invalid_params",
  );

  for (const mutate of [
    (request) => request.inventory.records.push(
      structuredClone(request.inventory.records[0]),
    ),
    (request) => request.inventory.records.pop(),
    (request) => {
      const fact = request.inventory.records.find(
        (record) => record.kind === "public_interface",
      );
      fact.kind = "test_asset";
    },
  ]) {
    const changed = structuredClone(valid);
    mutate(changed);
    assertDiscoveryError(
      () => buildDiscoveryPayload(adapterPayload(changed), changed, run),
      "invalid_params",
    );
  }
});

test("requires canonical tagged-record order recursively for discovery profiles", () => {
  const request = discoveryRequest(inventoryRun().snapshot);
  const tagged = encodeTagged(request);
  [tagged.entries[0], tagged.entries[1]] = [
    tagged.entries[1],
    tagged.entries[0],
  ];
  assert.throws(
    () => decodeProfileTagged(tagged),
    TaggedValueError,
  );

  const nestedTagged = encodeTagged(request);
  const binding = nestedTagged.entries.find(
    (entry) => entry.name === "inventory_binding",
  ).value;
  [binding.entries[0], binding.entries[1]] = [
    binding.entries[1],
    binding.entries[0],
  ];
  assert.throws(
    () => decodeProfileTagged(nestedTagged),
    TaggedValueError,
  );
});

test("rejects discovery boundary threats without stderr or partial state", async () => {
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

  const initialized = await exchange(request("initialize", "ucf.initialize", {
    kind: "initialize_request",
    protocol_version: VERSION,
    client: {
      kind: "producer",
      name: "org.ucf.adapter.discovery-test",
      version: VERSION,
    },
    capabilities: [
      capabilityRequest("org.ucf.adapter.discovery"),
      capabilityRequest("org.ucf.adapter.inventory"),
    ],
  }));
  assert.equal(initialized.result.kind, "initialize_result");

  const unavailable = discoveryRequest(emptyInventory());
  assertProtocolError(
    await exchange(operation("unavailable", "ucf.discover", adapterPayload(
      unavailable,
    ))),
    "operation_failed",
    "unavailable",
  );

  const records = [];
  let cursor = null;
  let page;
  let pageNumber = 0;
  do {
    pageNumber += 1;
    const response = await exchange(operation(
      `inventory-${pageNumber}`,
      "ucf.inventory",
      inventoryPayload(inventoryRequest(7, cursor)),
    ));
    assert.equal(response.result.kind, "inventory_result");
    page = decodeProfileTagged(response.result.payload.value);
    records.push(...page.records);
    cursor = page.next_cursor;
  } while (cursor !== null);
  const inventory = {
    kind: "inventory_snapshot",
    inventory_version: page.inventory_version,
    schema_uri: INVENTORY_SCHEMA_URI,
    subject_uri: page.subject_uri,
    path_identity: page.path_identity,
    source_revision: page.source_revision,
    producer: page.producer,
    capability: page.capability,
    applied_policy: page.applied_policy,
    coverage: page.coverage,
    records,
  };
  const valid = discoveryRequest(inventory);

  const rebound = structuredClone(valid);
  rebound.inventory_binding.canonical_digest.value = "f".repeat(64);
  assertProtocolError(
    await exchange(operation(
      "rebound",
      "ucf.discover",
      adapterPayload(rebound),
    )),
    "invalid_params",
    "rebound",
  );
  const malformed = structuredClone(valid);
  malformed.unexpected = true;
  assertProtocolError(
    await exchange(operation(
      "malformed",
      "ucf.discover",
      adapterPayload(malformed),
    )),
    "invalid_params",
    "malformed",
  );
  for (const [id, mutate] of [
    [
      "source-revision",
      (profile) => {
        profile.inventory.source_revision.value = "e".repeat(64);
        rebindInventory(profile);
      },
    ],
    [
      "producer",
      (profile) => {
        profile.inventory.producer.version = "1.0.1";
        rebindInventory(profile);
      },
    ],
    [
      "duplicate",
      (profile) => profile.inventory.records.push(
        structuredClone(profile.inventory.records[0]),
      ),
    ],
    ["missing", (profile) => profile.inventory.records.pop()],
    [
      "wrong-kind",
      (profile) => {
        const fact = profile.inventory.records.find(
          (record) => record.kind === "public_interface",
        );
        fact.kind = "test_asset";
      },
    ],
    [
      "renamed-interface",
      (profile) => {
        const fact = profile.inventory.records.find(
          (record) =>
            record.kind === "public_interface"
            && record.name === "quoteOrder",
        );
        fact.name = "quoteOrders";
        rebindInventory(profile);
      },
    ],
  ]) {
    const changed = structuredClone(valid);
    mutate(changed);
    assertProtocolError(
      await exchange(operation(
        id,
        "ucf.discover",
        adapterPayload(changed),
      )),
      "invalid_params",
      id,
    );
  }

  const noncanonical = adapterPayload(valid);
  const binding = noncanonical.value.entries.find(
    (entry) => entry.name === "inventory_binding",
  ).value;
  [
    binding.entries[0],
    binding.entries[1],
  ] = [
    binding.entries[1],
    binding.entries[0],
  ];
  assertProtocolError(
    await exchange(operation(
      "noncanonical",
      "ucf.discover",
      noncanonical,
    )),
    "invalid_params",
    "noncanonical",
  );

  const discovered = await exchange(operation(
    "valid",
    "ucf.discover",
    adapterPayload(valid),
  ));
  assert.equal(discovered.result.kind, "discover_result");
  const recovered = decodeProfileTagged(discovered.result.payload.value);
  const expected = decodeProfileTagged(
    buildDiscoveryPayload(
      adapterPayload(valid),
      valid,
      {
        key: "boundary-recovery",
        snapshot: inventory,
        snapshotDigest: sha256(canonicalJson(inventory)),
        records,
      },
    ).value,
  );
  assert.deepEqual(recovered, expected);
  assert.equal(recovered.candidates.length, 4);
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
    "discovery-test",
  );
}

function discoveryRequest(inventory) {
  return {
    kind: "discovery_request_profile",
    onboarding_version: VERSION,
    schema_uri: REQUEST_SCHEMA_URI,
    capability: CAPABILITY,
    inventory_binding: {
      kind: "inventory_binding",
      schema_uri: INVENTORY_SCHEMA_URI,
      inventory_version: VERSION,
      subject_uri: inventory.subject_uri,
      source_revision: inventory.source_revision,
      canonical_digest: digest(canonicalJson(inventory)),
    },
    inventory,
  };
}

function adapterPayload(request) {
  return {
    kind: "adapter_payload",
    schema_uri: REQUEST_SCHEMA_URI,
    schema_version: VERSION,
    value: encodeTagged(request),
  };
}

function rebindInventory(profile) {
  profile.inventory_binding.source_revision =
    structuredClone(profile.inventory.source_revision);
  profile.inventory_binding.canonical_digest =
    digest(canonicalJson(profile.inventory));
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

function emptyInventory() {
  return {
    kind: "inventory_snapshot",
    inventory_version: VERSION,
    schema_uri: INVENTORY_SCHEMA_URI,
    subject_uri: "urn:ucf:repository:unavailable",
    path_identity: "unicode-nfc-ascii-casefold-1",
    source_revision: digest("empty source"),
    producer: {
      kind: "producer",
      name: "org.ucf.adapter.typescript-fastify",
      version: VERSION,
    },
    capability: {
      kind: "capability",
      name: "org.ucf.adapter.inventory",
      version: VERSION,
    },
    applied_policy: {
      kind: "ignore_policy",
      policy_version: VERSION,
      rules: [],
    },
    coverage: [],
    records: [],
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
  return {
    kind: "digest",
    algorithm: "sha-256",
    value: sha256(value),
  };
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function assertDiscoveryError(callback, code) {
  assert.throws(
    callback,
    (error) =>
      error instanceof DiscoveryProfileError
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
