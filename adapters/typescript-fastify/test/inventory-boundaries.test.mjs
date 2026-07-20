import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  cpSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  truncateSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  decodeTagged,
  encodeTagged,
} from "../dist/tagged-values.js";
import { typescriptFastifyFixtureRoot } from "./fixture-root.mjs";

const adapter = new URL("../dist/main.js", import.meta.url);
const fixture = typescriptFastifyFixtureRoot();
const INVENTORY_CAPABILITY = "org.ucf.adapter.inventory";
const REQUEST_URI = "urn:ucf:adapter:inventory-request:1.0.0";
const SOURCE_REVISION =
  "3edbe720c9cc3f47b2dfdd2283c94c13a954931c6d3cde7fdb95ec48b0646e9e";
const MAX_FRAME_BYTES = 1_048_576;

test("ignores generated trees without changing the source revision", async () => {
  const temporary = fixtureCopy();
  mkdirSync(join(temporary.root, "dist"), { recursive: true });
  mkdirSync(join(temporary.root, "node_modules", "dependency"), {
    recursive: true,
  });
  writeFileSync(join(temporary.root, "dist", "generated.js"), "ignored");
  writeFileSync(
    join(temporary.root, "node_modules", "dependency", "index.js"),
    "ignored",
  );
  const session = await initializedSession(temporary.root);
  try {
    const page = await inventoryPage(session, "generated");
    assert.equal(page.source_revision.value, SOURCE_REVISION);
    assert.deepEqual(
      page.records
        .filter((record) => record.kind === "inventory_ignore_match")
        .map((record) => [record.rule_id, record.path])
        .sort(),
      [
        ["ignore.dist", "dist"],
        ["ignore.node-modules", "node_modules"],
      ],
    );
    const observedPaths = page.records
      .filter((record) => record.kind === "repository_entry")
      .map((record) => record.path);
    assert.equal(observedPaths.some((path) => path.startsWith("dist/")), false);
    assert.equal(
      observedPaths.some((path) => path.startsWith("node_modules/")),
      false,
    );
    await session.shutdown();
    assert.equal(session.stderr, "");
  } finally {
    await session.forceClose();
    temporary.remove();
  }
});

test("records a leaf symlink without following its target", async () => {
  const temporary = fixtureCopy();
  const outside = join(temporary.parent, "outside");
  mkdirSync(outside);
  writeFileSync(join(outside, "secret.txt"), "must not be inventoried");
  const target = "../outside";
  symlinkSync(target, join(temporary.root, "linked-target"));
  const session = await initializedSession(temporary.root);
  try {
    const page = await inventoryPage(session, "symlink");
    const link = page.records.find(
      (record) => record.kind === "repository_entry"
        && record.path === "linked-target",
    );
    assert.equal(link?.entry_kind, "symlink");
    assert.equal(
      link?.symlink_target_digest?.value,
      createHash("sha256").update(target).digest("hex"),
    );
    assert.equal(
      page.records.some(
        (record) => record.path?.includes("secret.txt") === true,
      ),
      false,
    );
    await session.shutdown();
    assert.equal(session.stderr, "");
  } finally {
    await session.forceClose();
    temporary.remove();
  }
});

test("rejects unsupported and unsafe filesystem inputs without stderr", async (t) => {
  await t.test("unsupported layout and same-session recovery", async () => {
    const temporary = fixtureCopy();
    const packagePath = join(temporary.root, "package.json");
    const original = readFileSync(packagePath, "utf8");
    writeFileSync(
      packagePath,
      original.replace('"fastify": "5.10.0"', '"fastify": "5.9.0"'),
    );
    const session = await initializedSession(temporary.root);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "unsupported"),
      );
      writeFileSync(packagePath, original);
      const recovered = await inventoryPage(session, "recovered");
      assert.equal(recovered.records.length, 42);
      assert.equal(recovered.complete, true);
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      await session.forceClose();
      temporary.remove();
    }
  });

  await t.test("unavailable root", async () => {
    const temporary = fixtureCopy();
    const session = await initializedSession(temporary.root);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "missing", {
          rootPath: "missing",
        }),
      );
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      await session.forceClose();
      temporary.remove();
    }
  });

  await t.test("ancestor symlink", async () => {
    const parent = mkdtempSync(join(tmpdir(), "ucf-ts-inventory-"));
    const outside = join(parent, "outside");
    mkdirSync(outside);
    cpSync(fixture, join(outside, "project"), { recursive: true });
    symlinkSync("outside", join(parent, "bridge"));
    const temporary = {
      parent,
      remove() {
        rmSync(parent, { force: true, recursive: true });
      },
    };
    const session = await initializedSession(temporary.parent);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "ancestor", {
          rootPath: "bridge/project",
        }),
      );
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      await session.forceClose();
      temporary.remove();
    }
  });

  await t.test("unreadable file", async () => {
    const temporary = fixtureCopy();
    const packagePath = join(temporary.root, "package.json");
    chmodSync(packagePath, 0);
    const session = await initializedSession(temporary.root);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "unreadable"),
      );
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      chmodSync(packagePath, 0o600);
      await session.forceClose();
      temporary.remove();
    }
  });

  await t.test("invalid raw-byte filename", async () => {
    const temporary = fixtureCopy();
    const encodedPath = Buffer.concat([
      Buffer.from(temporary.root),
      Buffer.from("/invalid-"),
      Buffer.from([0xff]),
    ]);
    writeFileSync(encodedPath, "invalid");
    const session = await initializedSession(temporary.root);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "raw-name"),
      );
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      await session.forceClose();
      temporary.remove();
    }
  });

  await t.test("portable path collision", async () => {
    const temporary = fixtureCopy();
    writeFileSync(join(temporary.root, "Case.ts"), "");
    writeFileSync(join(temporary.root, "case.ts"), "");
    const session = await initializedSession(temporary.root);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "collision"),
      );
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      await session.forceClose();
      temporary.remove();
    }
  });

  await t.test("depth bound", async () => {
    const temporary = fixtureCopy();
    let current = temporary.root;
    for (let index = 0; index < 66; index += 1) {
      current = join(current, `d${index}`);
      mkdirSync(current);
    }
    const session = await initializedSession(temporary.root);
    try {
      assertOperationFailed(
        await inventoryResponse(session, "depth"),
      );
      await session.shutdown();
      assert.equal(session.stderr, "");
    } finally {
      await session.forceClose();
      temporary.remove();
    }
  });
});

test("rejects a stale cursor and retains a usable session", async () => {
  const temporary = fixtureCopy();
  const session = await initializedSession(temporary.root);
  try {
    const first = await inventoryPage(session, "first", { recordLimit: 1 });
    assert.notEqual(first.next_cursor, null);
    const stale = structuredClone(first.next_cursor);
    stale.snapshot_digest.value = "0".repeat(64);
    assertOperationFailed(
      await inventoryResponse(session, "stale", {
        cursor: stale,
        recordLimit: 1,
      }),
    );
    await session.shutdown();
    assert.equal(session.stderr, "");
  } finally {
    await session.forceClose();
    temporary.remove();
  }
});

test("rejects noncanonical tagged record order at the inventory profile boundary", async () => {
  const temporary = fixtureCopy();
  const session = await initializedSession(temporary.root);
  try {
    const message = inventoryMessage("unsorted-profile");
    message.params.payload.value.entries.reverse();
    session.send(message);
    const response = await session.nextFrame();
    assert.equal(errorCode(response), "invalid_params");
    await session.shutdown();
    assert.equal(session.stderr, "");
  } finally {
    await session.forceClose();
    temporary.remove();
  }
});

test("terminates cancelled inventory before acknowledgement and reuses the session", async () => {
  const temporary = fixtureCopy();
  const largePath = join(temporary.root, "large.bin");
  writeFileSync(largePath, "");
  truncateSync(largePath, 192 * 1024 * 1024);
  const session = await initializedSession(temporary.root);
  try {
    session.send(
      inventoryMessage("cancelled"),
      readinessMessage("cancelled-readiness", "cancelled"),
    );
    const readiness = await session.nextFrame();
    assert.equal(readiness.id, "cancelled-readiness");
    const activeEntry = readiness.result.payload.value.entries.find(
      (entry) => entry.name === "active",
    );
    assert.equal(activeEntry?.value?.value, true);
    await delay(30);
    session.send(cancelMessage("cancelled"));
    const cancelled = await session.nextFrame();
    assert.equal(cancelled.id, "cancelled");
    assert.equal(errorCode(cancelled), "request_cancelled");

    rmSync(largePath);
    const recovered = await inventoryPage(session, "after-cancel");
    assert.equal(
      recovered.records.some((record) => record.path === "large.bin"),
      false,
    );
    assert.equal(recovered.records.length, 42);
    await session.shutdown();
    assert.equal(
      session.frames.filter((frame) => frame.id === "cancelled").length,
      1,
    );
    assert.equal(session.stderr, "");
  } finally {
    await session.forceClose();
    temporary.remove();
  }
});

test("shrinks inventory pages so every complete response frame is bounded", async () => {
  const temporary = fixtureCopy();
  const segments = ["é", "ê", "ë", "è"].map(
    (character) => character.repeat(120),
  );
  const deep = join(temporary.root, ...segments);
  mkdirSync(deep, { recursive: true });
  for (let index = 0; index < 700; index += 1) {
    writeFileSync(join(deep, `f${String(index).padStart(4, "0")}`), "");
  }
  const session = await initializedSession(temporary.root);
  try {
    let cursor = null;
    let complete = false;
    let totalRecords = 0;
    let observedShrink = false;
    let pageNumber = 0;
    while (!complete) {
      const page = await inventoryPage(
        session,
        `page-${pageNumber}`,
        { cursor, recordLimit: 256 },
      );
      totalRecords += page.records.length;
      observedShrink ||= !page.complete && page.records.length < 256;
      complete = page.complete;
      cursor = page.next_cursor;
      pageNumber += 1;
    }
    assert.equal(totalRecords, 1_450);
    assert.equal(observedShrink, true);
    assert.equal(
      session.frameBytes.every((size) => size <= MAX_FRAME_BYTES),
      true,
    );
    await session.shutdown();
    assert.equal(session.stderr, "");
  } finally {
    await session.forceClose();
    temporary.remove();
  }
});

function fixtureCopy(name = "repository") {
  const parent = mkdtempSync(join(tmpdir(), "ucf-ts-inventory-"));
  const root = join(parent, name);
  cpSync(fixture, root, { recursive: true });
  return {
    parent,
    root,
    remove() {
      rmSync(parent, { force: true, recursive: true });
    },
  };
}

async function initializedSession(cwd) {
  const session = new AdapterSession(cwd);
  session.send(initializeMessage());
  const initialized = await session.nextFrame();
  assert.equal(initialized.result?.kind, "initialize_result");
  return session;
}

async function inventoryResponse(session, id, options = {}) {
  session.send(inventoryMessage(id, options));
  return session.nextFrame();
}

async function inventoryPage(session, id, options = {}) {
  const response = await inventoryResponse(session, id, options);
  assert.equal(response.result?.kind, "inventory_result");
  const page = decodeTagged(response.result.payload.value);
  assert.equal(page.kind, "inventory_page");
  return page;
}

function inventoryMessage(
  id,
  {
    cursor = null,
    recordLimit = 256,
    rootPath = ".",
  } = {},
) {
  const logical = {
    kind: "inventory_request_profile",
    inventory_version: "1.0.0",
    schema_uri: REQUEST_URI,
    subject_uri: "urn:ucf:repository:typescript-fastify-boundary",
    root_path: rootPath,
    fact_kinds: [
      "api_description",
      "build_manifest",
      "public_interface",
      "repository_entry",
      "test_asset",
    ],
    ignore_policy: {
      kind: "ignore_policy",
      policy_version: "1.0.0",
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
  return request(id, "ucf.inventory", {
    kind: "inventory_request",
    payload: {
      kind: "adapter_payload",
      schema_uri: REQUEST_URI,
      schema_version: "1.0.0",
      value: encodeTagged(logical),
    },
  });
}

function initializeMessage() {
  return request("initialize", "ucf.initialize", {
    kind: "initialize_request",
    protocol_version: "1.0.0",
    client: {
      kind: "producer",
      name: "org.ucf.adapter.inventory-boundary-test",
      version: "1.0.0",
    },
    capabilities: [
      {
        kind: "capability_request",
        name: INVENTORY_CAPABILITY,
        minimum_version: "1.0.0",
        required: true,
      },
    ],
  });
}

function cancelMessage(requestId) {
  return {
    jsonrpc: "2.0",
    method: "ucf.cancel",
    params: { kind: "cancel_request", request_id: requestId },
  };
}

function readinessMessage(id, targetRequestId) {
  return request(id, "ucf.inventory", {
    kind: "inventory_request",
    payload: {
      kind: "adapter_payload",
      schema_uri: "urn:ucf:adapter-conformance:control:1.0.0",
      schema_version: "1.0.0",
      value: {
        kind: "record",
        entries: [
          {
            kind: "record_entry",
            name: "operation",
            value: { kind: "string", value: "readiness" },
          },
          {
            kind: "record_entry",
            name: "target_request_id",
            value: { kind: "string", value: targetRequestId },
          },
        ],
      },
    },
  });
}

function request(id, method, params) {
  return { jsonrpc: "2.0", id, method, params };
}

function assertOperationFailed(frame) {
  assert.equal(errorCode(frame), "operation_failed");
}

function errorCode(frame) {
  return frame?.error?.data?.ucf_code;
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

class AdapterSession {
  frames = [];
  frameBytes = [];
  stderr = "";
  #buffer = "";
  #queue = [];
  #waiters = [];
  #closed = false;

  constructor(cwd) {
    this.child = spawn(process.execPath, [adapter.pathname], {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.child.stdout.setEncoding("utf8");
    this.child.stderr.setEncoding("utf8");
    this.child.stdout.on("data", (chunk) => this.#receive(chunk));
    this.child.stderr.on("data", (chunk) => {
      this.stderr += chunk;
    });
    this.exit = new Promise((resolve, reject) => {
      this.child.once("error", reject);
      this.child.once("close", (code) => {
        this.#closed = true;
        resolve(code);
      });
    });
  }

  send(...messages) {
    this.child.stdin.write(
      `${messages.map((message) => JSON.stringify(message)).join("\n")}\n`,
    );
  }

  nextFrame(timeout = 5_000) {
    const queued = this.#queue.shift();
    if (queued !== undefined) {
      return Promise.resolve(queued);
    }
    return new Promise((resolve, reject) => {
      const waiter = {
        resolve,
        reject,
        timer: setTimeout(() => {
          const index = this.#waiters.indexOf(waiter);
          if (index >= 0) {
            this.#waiters.splice(index, 1);
          }
          reject(new Error("adapter response timed out"));
        }, timeout),
      };
      this.#waiters.push(waiter);
    });
  }

  async shutdown() {
    this.send(request(
      "shutdown",
      "ucf.shutdown",
      { kind: "shutdown_request" },
    ));
    const response = await this.nextFrame();
    assert.equal(response.result?.kind, "shutdown_result");
    const code = await this.exit;
    assert.equal(code, 0);
  }

  async forceClose() {
    if (!this.#closed) {
      this.child.kill("SIGKILL");
    }
    await this.exit;
  }

  #receive(chunk) {
    this.#buffer += chunk;
    let delimiter = this.#buffer.indexOf("\n");
    while (delimiter >= 0) {
      const line = this.#buffer.slice(0, delimiter);
      this.#buffer = this.#buffer.slice(delimiter + 1);
      if (line.length > 0) {
        this.frameBytes.push(Buffer.byteLength(`${line}\n`, "utf8"));
        const frame = JSON.parse(line);
        this.frames.push(frame);
        const waiter = this.#waiters.shift();
        if (waiter === undefined) {
          this.#queue.push(frame);
        } else {
          clearTimeout(waiter.timer);
          waiter.resolve(frame);
        }
      }
      delimiter = this.#buffer.indexOf("\n");
    }
  }
}
