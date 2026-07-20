import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const adapter = new URL("../dist/main.js", import.meta.url);
const manifest = new URL("../package.json", import.meta.url);

test("initializes and shuts down with zero stderr", async () => {
  const transcript = await runAdapter([
    request("initialize", "ucf.initialize", {
      kind: "initialize_request",
      protocol_version: "1.0.0",
      client: {
        kind: "producer",
        name: "org.ucf.adapter.control-test",
        version: "1.0.0",
      },
      capabilities: [],
    }),
    request("shutdown", "ucf.shutdown", { kind: "shutdown_request" }),
  ]);

  assert.equal(transcript.code, 0);
  assert.equal(transcript.stderr, "");
  assert.deepEqual(transcript.frames, [
    {
      jsonrpc: "2.0",
      id: "initialize",
      result: {
        kind: "initialize_result",
        protocol_version: "1.0.0",
        adapter: {
          kind: "producer",
          name: "org.ucf.adapter.typescript-fastify",
          version: "1.0.0",
        },
        capabilities: [],
      },
    },
    {
      jsonrpc: "2.0",
      id: "shutdown",
      result: { kind: "shutdown_result" },
    },
  ]);
});

test("rejects non-control generation without a domain claim", async () => {
  const generation = {
    kind: "capability_request",
    name: "org.ucf.adapter.generation",
    minimum_version: "1.0.0",
    required: true,
  };
  const transcript = await runAdapter([
    request("initialize", "ucf.initialize", {
      kind: "initialize_request",
      protocol_version: "1.0.0",
      client: {
        kind: "producer",
        name: "org.ucf.adapter.control-test",
        version: "1.0.0",
      },
      capabilities: [generation],
    }),
    request("generate", "ucf.generate", {
      kind: "generate_request",
      payload: {
        kind: "adapter_payload",
        schema_uri: "urn:example:domain-generation:1.0.0",
        schema_version: "1.0.0",
        value: { kind: "null" },
      },
    }),
    request("shutdown", "ucf.shutdown", { kind: "shutdown_request" }),
  ]);

  assert.equal(transcript.code, 0);
  assert.equal(transcript.stderr, "");
  assert.deepEqual(transcript.frames[1], {
    jsonrpc: "2.0",
    id: "generate",
    error: {
      code: -32000,
      message: "unsupported conformance control payload",
      data: {
        category: "adapter_failure",
        ucf_code: "operation_failed",
      },
    },
  });
});

test("declares build-only dependencies", async () => {
  const packageJson = JSON.parse(await readFile(manifest, "utf8"));
  assert.equal(Object.hasOwn(packageJson, "dependencies"), false);
  assert.equal(Object.hasOwn(packageJson, "optionalDependencies"), false);
  assert.deepEqual(packageJson.devDependencies, {
    "@types/node": "22.20.1",
    typescript: "7.0.2",
  });
});

function request(id, method, params) {
  return { jsonrpc: "2.0", id, method, params };
}

async function runAdapter(messages) {
  const child = spawn(process.execPath, [adapter.pathname], {
    stdio: ["pipe", "pipe", "pipe"],
  });
  child.stdin.end(`${messages.map(JSON.stringify).join("\n")}\n`);

  const stdout = collect(child.stdout);
  const stderr = collect(child.stderr);
  const code = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", resolve);
  });
  const output = await stdout;
  return {
    code,
    stderr: await stderr,
    frames: output.trim().split("\n").filter(Boolean).map(JSON.parse),
  };
}

async function collect(stream) {
  let output = "";
  stream.setEncoding("utf8");
  for await (const chunk of stream) {
    output += chunk;
  }
  return output;
}
