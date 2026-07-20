import { lstat, realpath } from "node:fs/promises";
import { isAbsolute, join, relative } from "node:path";
import { pathToFileURL } from "node:url";
import { parentPort, workerData } from "node:worker_threads";

import {
  type JsonObject,
  hasExactKeys,
  isObject,
  parseStrictJson,
} from "../strict-json.js";

const PHASE_DEADLINE_MS = 1_500;
const MAX_RESPONSE_BYTES = 65_536;

type Outcome = "passed" | "failed" | "error";

interface VerificationValues {
  quantity: number;
  unitPriceCents: number;
  expectedTotalCents: number;
}

interface SupportedApp {
  listen(options: {
    host: "127.0.0.1";
    port: 0;
  }): Promise<string>;
  close(): Promise<void>;
}

async function run(): Promise<Outcome> {
  let app: SupportedApp | null = null;
  let outcome: Outcome = "error";
  try {
    const values = validateWorkerData(workerData);
    const service = await supportedServicePath();
    const loaded: unknown = await withDeadline(
      import(pathToFileURL(service).href),
    );
    if (loaded === null || typeof loaded !== "object") {
      throw new Error("unsupported service module");
    }
    const buildApp = (loaded as Record<string, unknown>)["buildApp"];
    if (typeof buildApp !== "function") {
      throw new Error("unsupported service module");
    }
    const candidate: unknown = buildApp();
    if (!supportedApp(candidate)) {
      throw new Error("unsupported application instance");
    }
    app = candidate;
    const baseUrl = await withDeadline(
      app.listen({ host: "127.0.0.1", port: 0 }),
    );
    const endpoint = loopbackEndpoint(baseUrl);
    outcome = await executeCheck(endpoint, values);
  } catch {
    outcome = "error";
  } finally {
    if (app !== null) {
      try {
        await withDeadline(app.close());
      } catch {
        outcome = "error";
      }
    }
  }
  return outcome;
}

async function executeCheck(
  endpoint: URL,
  values: VerificationValues,
): Promise<Outcome> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    PHASE_DEADLINE_MS,
  );
  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        quantity: values.quantity,
        unit_price_cents: values.unitPriceCents,
      }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
  let body: JsonObject;
  try {
    const encoded = await readBounded(response);
    const decoded = parseStrictJson(encoded);
    if (!isObject(decoded)) {
      return "failed";
    }
    body = decoded;
  } catch {
    return "error";
  }
  return response.status === 200
    && typeof body["total_cents"] === "number"
    && Number.isSafeInteger(body["total_cents"])
    && body["total_cents"] === values.expectedTotalCents
    ? "passed"
    : "failed";
}

async function readBounded(response: Response): Promise<string> {
  if (response.body === null) {
    return "";
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const next = await withDeadline(reader.read());
      if (next.done) {
        break;
      }
      size += next.value.byteLength;
      if (size > MAX_RESPONSE_BYTES) {
        throw new Error("response exceeds bound");
      }
      chunks.push(next.value);
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
  const merged = Buffer.alloc(size);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(merged);
}

async function supportedServicePath(): Promise<string> {
  const requestedRoot = process.cwd();
  const root = await realpath(requestedRoot);
  if (root !== requestedRoot) {
    throw new Error("unsupported working directory");
  }
  const distribution = join(root, "dist");
  const distributionMetadata = await lstat(distribution);
  if (
    distributionMetadata.isSymbolicLink()
    || !distributionMetadata.isDirectory()
  ) {
    throw new Error("unsupported distribution directory");
  }
  const service = join(distribution, "service.js");
  const serviceMetadata = await lstat(service);
  const resolved = await realpath(service);
  const within = relative(root, resolved);
  if (
    serviceMetadata.isSymbolicLink()
    || !serviceMetadata.isFile()
    || resolved !== service
    || within === ""
    || within.startsWith("..")
    || isAbsolute(within)
  ) {
    throw new Error("unsupported service module");
  }
  return service;
}

function loopbackEndpoint(value: string): URL {
  const url = new URL(value);
  if (
    url.protocol !== "http:"
    || url.hostname !== "127.0.0.1"
    || !/^[1-9][0-9]{0,4}$/u.test(url.port)
    || Number(url.port) > 65_535
    || url.username !== ""
    || url.password !== ""
    || url.pathname !== "/"
    || url.search !== ""
    || url.hash !== ""
  ) {
    throw new Error("application did not bind the supported endpoint");
  }
  url.pathname = "/quote-order";
  return url;
}

function validateWorkerData(value: unknown): VerificationValues {
  if (
    !hasExactKeys(
      value,
      ["quantity", "unitPriceCents", "expectedTotalCents"],
    )
    || !supportedInteger(value["quantity"])
    || !supportedInteger(value["unitPriceCents"])
    || !supportedInteger(value["expectedTotalCents"])
  ) {
    throw new Error("verification values are invalid");
  }
  return {
    quantity: value["quantity"],
    unitPriceCents: value["unitPriceCents"],
    expectedTotalCents: value["expectedTotalCents"],
  };
}

function supportedInteger(value: unknown): value is number {
  return typeof value === "number"
    && Number.isSafeInteger(value)
    && !Object.is(value, -0);
}

function supportedApp(value: unknown): value is SupportedApp {
  return isObject(value)
    && typeof value["listen"] === "function"
    && typeof value["close"] === "function";
}

async function withDeadline<T>(operation: Promise<T>): Promise<T> {
  let timeout: NodeJS.Timeout | undefined;
  const expired = new Promise<never>((_resolve, reject) => {
    timeout = setTimeout(
      () => reject(new Error("verification phase timed out")),
      PHASE_DEADLINE_MS,
    );
  });
  try {
    return await Promise.race([operation, expired]);
  } finally {
    if (timeout !== undefined) {
      clearTimeout(timeout);
    }
  }
}

void run().then(
  (outcome) => {
    parentPort?.postMessage({
      outcome,
      executedAt: wholeSecondNow(),
    });
  },
  () => {
    parentPort?.postMessage({
      outcome: "error",
      executedAt: wholeSecondNow(),
    });
  },
);

function wholeSecondNow(): string {
  return new Date(
    Math.floor(Date.now() / 1_000) * 1_000,
  ).toISOString().replace(".000Z", "Z");
}
