import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { test } from "node:test";

import { SessionLimits } from "../dist/session-limits.js";

const adapter = new URL("../dist/main.js", import.meta.url);
const CONTROL_URI = "urn:ucf:adapter-conformance:control:1.0.0";

test("supports small injected session limits without changing defaults", () => {
  const limits = new SessionLimits(2, 4);
  assert.equal(limits.acceptRequest("ucf.initialize"), true);
  assert.equal(limits.acceptRequest("ucf.inventory"), true);
  assert.equal(limits.acceptRequest("ucf.inventory"), true);
  assert.equal(limits.acceptRequest("ucf.inventory"), false);
  assert.equal(limits.acceptRequest("ucf.shutdown"), true);
  assert.equal(limits.acceptRequest("ucf.shutdown"), false);
  assert.equal(limits.acceptsPending(0), true);
  assert.equal(limits.acceptsPending(1), true);
  assert.equal(limits.acceptsPending(2), false);
  assert.throws(() => new SessionLimits(65, 4), RangeError);
  assert.throws(() => new SessionLimits(2, 65_537), RangeError);
});

test("validates producer and capability names and sorts selections", async () => {
  const invalidProducer = await runAdapter([
    initialize("bad-producer", [], {
      kind: "producer",
      name: "invalid",
      version: "1.0.0",
    }),
    initialize("valid-after-producer", []),
    shutdown(),
  ]);
  assert.equal(invalidProducer.stderr, "");
  assert.equal(errorCode(invalidProducer.frames[0]), "invalid_params");
  assert.equal(
    invalidProducer.frames[1]?.result?.kind,
    "initialize_result",
  );

  const invalidCapability = await runAdapter([
    initialize("bad-capability", [
      capability("INVALID", true),
    ]),
    initialize("valid-after-capability", []),
    shutdown(),
  ]);
  assert.equal(invalidCapability.stderr, "");
  assert.equal(errorCode(invalidCapability.frames[0]), "invalid_params");
  assert.equal(
    invalidCapability.frames[1]?.result?.kind,
    "initialize_result",
  );

  const sorted = await runAdapter([
    initialize("sorted", [
      capability("org.ucf.adapter.verification", true),
      capability("org.ucf.adapter.inventory", true),
    ]),
    shutdown(),
  ]);
  assert.deepEqual(
    sorted.frames[0]?.result?.capabilities.map((item) => item.name),
    [
      "org.ucf.adapter.inventory",
      "org.ucf.adapter.verification",
    ],
  );
});

test("recursively rejects a noncanonical nested IRValue across methods", async () => {
  const duplicateRecord = {
    kind: "record",
    entries: [
      { kind: "record_entry", name: "x", value: { kind: "null" } },
      { kind: "record_entry", name: "x", value: { kind: "null" } },
    ],
  };
  const transcript = await runAdapter([
    initialize("initialize", [
      capability("org.ucf.adapter.inventory", true),
      capability("org.ucf.adapter.verification", true),
    ]),
    request("duplicate", "ucf.inventory", {
      kind: "inventory_request",
      payload: controlPayload("echo", duplicateRecord),
    }),
    request("verify-duplicate", "ucf.verify", {
      kind: "verify_request",
      payload: controlPayload("echo", duplicateRecord),
    }),
    shutdown(),
  ]);
  assert.equal(transcript.stderr, "");
  assert.equal(errorCode(transcript.frames[1]), "invalid_params");
  assert.equal(errorCode(transcript.frames[2]), "invalid_params");
  assert.equal(transcript.frames[3]?.result?.kind, "shutdown_result");
});

test("accepts unique generic record entries without imposing profile order", async () => {
  const unsortedRecord = {
    kind: "record",
    entries: [
      {
        kind: "record_entry",
        name: "z",
        value: { kind: "string", value: "last-by-name" },
      },
      {
        kind: "record_entry",
        name: "a",
        value: { kind: "string", value: "first-by-name" },
      },
    ],
  };
  const transcript = await runAdapter([
    initialize("initialize", [
      capability("org.ucf.adapter.inventory", true),
      capability("org.ucf.adapter.verification", true),
    ]),
    request("inventory-unsorted", "ucf.inventory", {
      kind: "inventory_request",
      payload: controlPayload("echo", unsortedRecord),
    }),
    request("verify-unsorted", "ucf.verify", {
      kind: "verify_request",
      payload: controlPayload("echo", unsortedRecord),
    }),
    shutdown(),
  ]);

  assert.equal(transcript.stderr, "");
  assert.deepEqual(
    transcript.frames.slice(1, 3).map(errorCode),
    [undefined, undefined],
  );
  assert.deepEqual(
    transcript.frames.slice(1, 3).map((frame) => [
      frame.result?.kind,
      echoedValue(frame).entries.map((entry) => entry.name),
    ]),
    [
      ["inventory_result", ["z", "a"]],
      ["verify_result", ["z", "a"]],
    ],
  );
  assert.equal(transcript.frames[3]?.result?.kind, "shutdown_result");
});

test("canonical server frames ASCII-escape non-ASCII values", async () => {
  const transcript = await runAdapter([
    initialize("initialize", [
      capability("org.ucf.adapter.inventory", true),
    ]),
    request("unicode", "ucf.inventory", {
      kind: "inventory_request",
      payload: controlPayload("echo", {
        kind: "string",
        value: "é😀",
      }),
    }),
    shutdown(),
  ]);
  assert.equal(transcript.stderr, "");
  assert.equal(transcript.stdout.includes("é"), false);
  assert.equal(transcript.stdout.includes("😀"), false);
  assert.equal(transcript.stdout.includes("\\u00e9"), true);
  assert.equal(
    transcript.stdout.includes("\\ud83d\\ude00"),
    true,
  );
});

test("enforces the default 64-active-request boundary", async () => {
  const blocks = Array.from({ length: 65 }, (_, index) =>
    request(`block-${index}`, "ucf.inventory", {
      kind: "inventory_request",
      payload: controlPayload("block"),
    }));
  const cancellations = Array.from({ length: 64 }, (_, index) => ({
    jsonrpc: "2.0",
    method: "ucf.cancel",
    params: { kind: "cancel_request", request_id: `block-${index}` },
  }));
  const transcript = await runAdapter([
    initialize("initialize", [
      capability("org.ucf.adapter.inventory", true),
    ]),
    ...blocks,
    ...cancellations,
    shutdown(),
  ]);
  assert.equal(transcript.stderr, "");
  assert.equal(
    transcript.frames.filter(
      (frame) => errorCode(frame) === "too_many_pending",
    ).length,
    1,
  );
  assert.equal(
    transcript.frames.filter(
      (frame) => errorCode(frame) === "request_cancelled",
    ).length,
    64,
  );
  assert.equal(
    transcript.frames.at(-1)?.result?.kind,
    "shutdown_result",
  );
});

test("reserves the final 65,536th accepted request for shutdown", async () => {
  const rejected = Array.from({ length: 65_534 }, (_, index) =>
    request(`rejected-${index}`, "ucf.verify", {
      kind: "verify_request",
      payload: controlPayload("echo", { kind: "null" }),
    }));
  const transcript = await runAdapter([
    initialize("initialize", []),
    ...rejected,
    request("over-budget", "ucf.verify", {
      kind: "verify_request",
      payload: controlPayload("echo", { kind: "null" }),
    }),
    shutdown(),
  ]);
  assert.equal(transcript.stderr, "");
  assert.equal(transcript.frames.length, 65_537);
  assert.equal(
    errorCode(transcript.frames.at(-2)),
    "session_request_limit",
  );
  assert.equal(
    transcript.frames.at(-1)?.result?.kind,
    "shutdown_result",
  );
});

test("discards an oversized unterminated frame through its next LF", async () => {
  const child = spawn(process.execPath, [adapter.pathname], {
    stdio: ["pipe", "pipe", "pipe"],
  });
  const output = collect(child.stdout);
  const stderr = collect(child.stderr);
  child.stdin.write("x".repeat(1_048_577));
  await waitForOutput(child.stdout);
  child.stdin.write(`${JSON.stringify(initialize("discarded", []))}\n`);
  child.stdin.write(`${JSON.stringify(initialize("accepted", []))}\n`);
  child.stdin.end(`${JSON.stringify(shutdown())}\n`);
  const code = await closeCode(child);
  const stdout = await output;
  const frames = framesFrom(stdout);
  assert.equal(code, 0);
  assert.equal(await stderr, "");
  assert.deepEqual(
    frames.map((frame) => [
      frame.id,
      frame.result?.kind ?? errorCode(frame),
    ]),
    [
      [null, "frame_too_large"],
      ["accepted", "initialize_result"],
      ["shutdown", "shutdown_result"],
    ],
  );
});

test("emits no frame after the shutdown acknowledgement", async () => {
  const transcript = await runAdapter([
    initialize("initialize", []),
    shutdown(),
    request("after-shutdown", "ucf.inventory", {
      kind: "inventory_request",
      payload: controlPayload("echo", { kind: "null" }),
    }),
  ]);
  assert.equal(transcript.stderr, "");
  assert.deepEqual(
    transcript.frames.map((frame) => frame.id),
    ["initialize", "shutdown"],
  );
});

function initialize(id, capabilities, producer = {
  kind: "producer",
  name: "org.ucf.adapter.boundary-test",
  version: "1.0.0",
}) {
  return request(id, "ucf.initialize", {
    kind: "initialize_request",
    protocol_version: "1.0.0",
    client: producer,
    capabilities,
  });
}

function shutdown() {
  return request(
    "shutdown",
    "ucf.shutdown",
    { kind: "shutdown_request" },
  );
}

function capability(name, required) {
  return {
    kind: "capability_request",
    name,
    minimum_version: "1.0.0",
    required,
  };
}

function request(id, method, params) {
  return { jsonrpc: "2.0", id, method, params };
}

function controlPayload(operation, value) {
  const entries = [
    {
      kind: "record_entry",
      name: "operation",
      value: { kind: "string", value: operation },
    },
  ];
  if (value !== undefined) {
    entries.push({ kind: "record_entry", name: "value", value });
  }
  return {
    kind: "adapter_payload",
    schema_uri: CONTROL_URI,
    schema_version: "1.0.0",
    value: { kind: "record", entries },
  };
}

function errorCode(frame) {
  return frame?.error?.data?.ucf_code;
}

function echoedValue(frame) {
  const entries = frame.result?.payload?.value?.entries;
  assert.ok(Array.isArray(entries));
  const value = entries.find((entry) => entry.name === "value")?.value;
  assert.ok(value);
  return value;
}

async function runAdapter(messages) {
  const child = spawn(process.execPath, [adapter.pathname], {
    stdio: ["pipe", "pipe", "pipe"],
  });
  const output = collect(child.stdout);
  const stderr = collect(child.stderr);
  child.stdin.end(`${messages.map(JSON.stringify).join("\n")}\n`);
  const code = await closeCode(child);
  const stdout = await output;
  return {
    code,
    stdout,
    stderr: await stderr,
    frames: framesFrom(stdout),
  };
}

function framesFrom(output) {
  return output.trim().split("\n").filter(Boolean).map(JSON.parse);
}

async function collect(stream) {
  let output = "";
  stream.setEncoding("utf8");
  for await (const chunk of stream) {
    output += chunk;
  }
  return output;
}

function closeCode(child) {
  return new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", resolve);
  });
}

function waitForOutput(stream) {
  return new Promise((resolve) => {
    stream.once("data", resolve);
  });
}
