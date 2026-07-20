import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  access,
  mkdir,
  mkdtemp,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { canonicalJson } from "../dist/canonical-json.js";
import { decodeProfileTagged, encodeTagged } from "../dist/tagged-values.js";
import {
  VerificationProfileError,
  startVerificationPayload,
} from "../dist/verification/profile.js";

const VERSION = "1.0.0";
const REQUEST_SCHEMA_URI =
  "urn:ucf:adapter:execution-verification-request:1.0.0";
const RESULT_SCHEMA_URI =
  "urn:ucf:adapter:execution-verification-result:1.0.0";

test("runs only the bounded loopback procedure and closes before result", async () => {
  await withRepository(serviceSource("normal"), async (repository) => {
    const context = verificationContext();
    const first = startVerificationPayload(
      adapterPayload(context.request),
      context.request,
      context.run,
      context.mapping,
    );
    const passedPayload = await first.promise;
    const passed = decodeProfileTagged(passedPayload.value);
    assert.equal(passedPayload.schema_uri, RESULT_SCHEMA_URI);
    assert.equal(passed.outcome, "passed");
    assert.equal(
      canonicalJson(passed.request),
      canonicalJson(context.request),
    );
    assert.deepEqual(Object.keys(passed).sort(), [
      "capability",
      "executed_at",
      "id",
      "implementation_evidence_version",
      "kind",
      "outcome",
      "procedure_uri",
      "producer",
      "request",
      "schema_uri",
      "status",
    ]);
    assert.equal(
      passed.id,
      `result.${sha256(canonicalJson(withoutId(passed)))}`,
    );
    await access(join(repository, "closed.marker"));

    const failedRequest = structuredClone(context.request);
    failedRequest.expected_outputs[0].value.value = 2501;
    const second = startVerificationPayload(
      adapterPayload(failedRequest),
      failedRequest,
      context.run,
      context.mapping,
    );
    const failed = decodeProfileTagged((await second.promise).value);
    assert.equal(failed.outcome, "failed");
    assert.equal(
      canonicalJson(failed.request),
      canonicalJson(failedRequest),
    );
  });
});

test("returns a minimal error result for bounded runtime failures", async (t) => {
  for (const mode of ["invalid-module", "hanging", "oversized"]) {
    await t.test(mode, async () => {
      await withRepository(serviceSource(mode), async (repository) => {
        const context = verificationContext();
        const job = startVerificationPayload(
          adapterPayload(context.request),
          context.request,
          context.run,
          context.mapping,
        );
        const result = decodeProfileTagged((await job.promise).value);
        assert.equal(result.outcome, "error");
        assert.deepEqual(Object.keys(result).sort(), [
          "capability",
          "executed_at",
          "id",
          "implementation_evidence_version",
          "kind",
          "outcome",
          "procedure_uri",
          "producer",
          "request",
          "schema_uri",
          "status",
        ]);
        for (const forbidden of [
          "body",
          "error",
          "headers",
          "host",
          "message",
          "path",
          "port",
          "stack",
          "stderr",
          "stdout",
        ]) {
          assert.equal(forbidden in result, false);
        }
        if (mode !== "invalid-module") {
          await access(join(repository, "closed.marker"));
        }
      });
    });
  }
});

test("rejects malformed or rebound requests before runtime", () => {
  const context = verificationContext();
  const threats = [
    (value) => {
      value.kind = "implementation_mapping_request";
    },
    (value) => {
      value.implementation_evidence_version = "2.0.0";
    },
    (value) => {
      value.schema_uri =
        "urn:ucf:adapter:execution-verification-request:2.0.0";
    },
    (value) => {
      value.capability.name = "org.ucf.adapter.mapping";
    },
    (value) => {
      value.profile_procedure_uri =
        "urn:ucf:implementation-evidence:verify:2.0.0";
    },
    (value) => {
      value.adapter_procedure_uri =
        "urn:ucf:adapter:typescript-fastify-other:1.0.0";
    },
    (value) => {
      value.mapping.canonical_digest.value = "f".repeat(64);
    },
    (value) => {
      value.subject.target_id = "use-case.other";
    },
    (value) => {
      value.source.source_revision.value = "f".repeat(64);
    },
    (value) => {
      value.environment.revision.value = "f".repeat(64);
    },
    (value) => {
      value.check.id = "check.other";
    },
    (value) => {
      value.inputs.reverse();
    },
    (value) => {
      value.inputs[0].port.direction = "output";
    },
    (value) => {
      value.inputs[0].value.kind = "string";
    },
    (value) => {
      value.inputs[0].value.value = 3;
    },
    (value) => {
      value.expected_outputs.push(
        structuredClone(value.expected_outputs[0]),
      );
    },
    (value) => {
      value.future = true;
    },
  ];
  for (const mutate of threats) {
    const changed = structuredClone(context.request);
    mutate(changed);
    assertProfileError(
      () => startVerificationPayload(
        adapterPayload(changed),
        changed,
        context.run,
        context.mapping,
      ),
      "invalid_params",
    );
  }

  const wrongOuter = adapterPayload(context.request);
  wrongOuter.schema_version = "2.0.0";
  assertProfileError(
    () => startVerificationPayload(
      wrongOuter,
      context.request,
      context.run,
      context.mapping,
    ),
    "invalid_params",
  );
  assertProfileError(
    () => startVerificationPayload(
      adapterPayload(context.request),
      context.request,
      null,
      context.mapping,
    ),
    "operation_failed",
  );
  assertProfileError(
    () => startVerificationPayload(
      adapterPayload(context.request),
      context.request,
      context.run,
      null,
    ),
    "operation_failed",
  );
});

test("rejects missing, non-file, and symlinked executable layouts", async (t) => {
  const context = verificationContext();
  const cases = [
    {
      name: "missing",
      prepare: async (root) => {
        await mkdir(join(root, "dist"));
      },
    },
    {
      name: "directory",
      prepare: async (root) => {
        await mkdir(join(root, "dist", "service.js"), { recursive: true });
      },
    },
    {
      name: "file-symlink",
      prepare: async (root) => {
        await mkdir(join(root, "dist"));
        await writeFile(join(root, "outside.js"), serviceSource("normal"));
        await symlink(
          join(root, "outside.js"),
          join(root, "dist", "service.js"),
        );
      },
    },
    {
      name: "dist-symlink",
      prepare: async (root) => {
        await mkdir(join(root, "outside"));
        await writeFile(
          join(root, "outside", "service.js"),
          serviceSource("normal"),
        );
        await symlink(join(root, "outside"), join(root, "dist"));
      },
    },
  ];
  for (const item of cases) {
    await t.test(item.name, async () => {
      await withTemporaryRoot(async (root) => {
        await item.prepare(root);
        assertProfileError(
          () => startVerificationPayload(
            adapterPayload(context.request),
            context.request,
            context.run,
            context.mapping,
          ),
          "operation_failed",
        );
      });
    });
  }
});

test("cancellation waits for Worker termination and rejects its result", async () => {
  await withRepository(serviceSource("hanging"), async (repository) => {
    const context = verificationContext();
    const job = startVerificationPayload(
      adapterPayload(context.request),
      context.request,
      context.run,
      context.mapping,
    );
    await waitFor(join(repository, "listening.marker"));
    const rejected = job.promise.catch((error) => error);
    await job.cancel();
    const error = await rejected;
    assert.equal(error instanceof VerificationProfileError, true);
    assert.equal(error.code, "operation_failed");
  });
});

function verificationContext() {
  const snapshot = {
    kind: "inventory_snapshot",
    inventory_version: VERSION,
    schema_uri: "urn:ucf:schema:inventory:1.0.0",
    subject_uri: "urn:ucf:fixture:typescript-fastify-legacy-quote:1.0.0",
    source_revision: digest("a".repeat(64)),
    path_identity: "unicode-nfc-ascii-casefold-1",
    producer: {
      kind: "producer",
      name: "org.ucf.adapter.typescript-fastify",
      version: VERSION,
    },
    records: [],
  };
  const run = {
    key: "synthetic-verification-profile",
    snapshot,
    snapshotDigest: sha256(canonicalJson(snapshot)),
    records: [],
  };
  const subject = {
    kind: "behavior_entity_ref",
    document_id: "document.typescript-fastify.quote-order",
    ir_version: VERSION,
    canonical_digest: digest("b".repeat(64)),
    target_kind: "use_case",
    target_id: "use-case.quote-order",
  };
  const sourceRecords = [
    ["build_manifest", "manifest.a"],
    ["build_manifest", "manifest.b"],
    ["build_manifest", "manifest.c"],
    ["public_interface", "interface.a"],
    ["public_interface", "interface.b"],
  ].map(([target_kind, target_id]) => ({
    kind: "inventory_record_ref",
    target_kind,
    target_id,
  }));
  const mapping = {
    kind: "implementation_mapping_result",
    implementation_evidence_version: VERSION,
    schema_uri:
      "urn:ucf:adapter:implementation-mapping-result:1.0.0",
    id: `mapping.${"c".repeat(64)}`,
    status: "complete",
    request: { inventory: snapshot },
    producer: {
      kind: "producer",
      name: "org.ucf.adapter.typescript-fastify",
      version: VERSION,
    },
    capability: {
      kind: "capability",
      name: "org.ucf.adapter.mapping",
      version: VERSION,
    },
    procedure_uri:
      "urn:ucf:adapter:typescript-fastify-static-mapping:1.0.0",
    bindings: [
      {
        kind: "implementation_binding",
        behavior: subject,
        source_records: sourceRecords,
      },
    ],
  };
  const owner = {
    kind: "entity_ref",
    target_kind: "use_case",
    target_id: "use-case.quote-order",
  };
  const request = {
    kind: "execution_verification_request",
    implementation_evidence_version: VERSION,
    schema_uri: REQUEST_SCHEMA_URI,
    capability: {
      kind: "capability",
      name: "org.ucf.adapter.verification",
      version: VERSION,
    },
    profile_procedure_uri:
      "urn:ucf:implementation-evidence:verify:1.0.0",
    adapter_procedure_uri:
      "urn:ucf:adapter:typescript-fastify-real-http-verification:1.0.0",
    mapping: {
      kind: "implementation_mapping_result_ref",
      schema_uri:
        "urn:ucf:adapter:implementation-mapping-result:1.0.0",
      schema_version: VERSION,
      target_id: mapping.id,
      canonical_digest: digest(sha256(canonicalJson(mapping))),
    },
    base_behavior: {
      kind: "behavior_document_ref",
      document_id: subject.document_id,
      ir_version: subject.ir_version,
      canonical_digest: subject.canonical_digest,
    },
    subject,
    inputs: [
      portValue(owner, "input", "quantity", 2),
      portValue(owner, "input", "unit-price-cents", 1250),
    ],
    expected_outputs: [
      portValue(owner, "output", "total-cents", 2500),
    ],
    source: {
      kind: "implementation_source",
      subject_uri: snapshot.subject_uri,
      source_revision: snapshot.source_revision,
      records: sourceRecords,
    },
    environment: {
      kind: "execution_environment",
      identity_uri:
        "urn:ucf:fixture-environment:node22-linux-loopback:1.0.0",
      revision: digest(
        "5c1cb86c391a5942088462fa2fe4e8a4deec768f6b37fd69027e37729555ce02",
      ),
    },
    check: {
      kind: "check",
      id: "check.quote-order.real-http",
      version: VERSION,
      procedure_uri:
        "urn:ucf:fixture-check:quote-order-http-contract:1.0.0",
    },
  };
  return { mapping, request, run };
}

function portValue(owner, direction, name, value) {
  return {
    kind: "execution_port_value",
    port: {
      kind: "port_ref",
      owner,
      direction,
      name,
    },
    value: { kind: "integer", value },
  };
}

function adapterPayload(value) {
  return {
    kind: "adapter_payload",
    schema_uri: REQUEST_SCHEMA_URI,
    schema_version: VERSION,
    value: encodeTagged(value),
  };
}

function digest(value) {
  return { kind: "digest", algorithm: "sha-256", value };
}

function withoutId(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([name]) => name !== "id"),
  );
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function assertProfileError(action, code) {
  assert.throws(
    action,
    (error) =>
      error instanceof VerificationProfileError
      && error.code === code,
  );
}

async function withRepository(source, action) {
  await withTemporaryRoot(async (root) => {
    await mkdir(join(root, "dist"));
    await writeFile(
      join(root, "package.json"),
      '{"private":true,"type":"module"}\n',
    );
    await writeFile(join(root, "dist", "service.js"), source);
    await action(root);
  });
}

async function withTemporaryRoot(action) {
  const root = await mkdtemp(join(tmpdir(), "ucf-verification-profile-"));
  const original = process.cwd();
  process.chdir(root);
  try {
    await action(root);
  } finally {
    process.chdir(original);
    await rm(root, { recursive: true, force: true });
  }
}

async function waitFor(path) {
  const deadline = Date.now() + 2_000;
  while (true) {
    try {
      await access(path);
      return;
    } catch {
      if (Date.now() >= deadline) {
        throw new Error("worker did not reach the expected phase");
      }
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  }
}

function serviceSource(mode) {
  if (mode === "invalid-module") {
    return "export const unsupported = true;\n";
  }
  return `
import { createServer } from "node:http";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

let server;

export function buildApp() {
  return {
    async listen({ host, port }) {
      server = createServer(async (request, response) => {
        if (${JSON.stringify(mode)} === "hanging") {
          return;
        }
        let encoded = "";
        for await (const chunk of request) {
          encoded += chunk;
        }
        const values = JSON.parse(encoded);
        response.statusCode = 200;
        response.setHeader("content-type", "application/json");
        if (${JSON.stringify(mode)} === "oversized") {
          response.end(JSON.stringify({
            total_cents: values.quantity * values.unit_price_cents,
            padding: "x".repeat(70_000),
          }));
          return;
        }
        response.end(JSON.stringify({
          total_cents: values.quantity * values.unit_price_cents,
          receipt: "undeclared transport detail",
        }));
      });
      await new Promise((resolve, reject) => {
        server.once("error", reject);
        server.listen(port, host, resolve);
      });
      await writeFile(join(process.cwd(), "listening.marker"), "ready");
      const address = server.address();
      return \`http://127.0.0.1:\${address.port}\`;
    },
    async close() {
      if (server?.listening) {
        await new Promise((resolve, reject) => {
          server.close((error) => error ? reject(error) : resolve());
        });
      }
      await writeFile(join(process.cwd(), "closed.marker"), "closed");
    },
  };
}
`;
}
