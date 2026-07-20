import { createHash } from "node:crypto";
import { lstatSync, realpathSync } from "node:fs";
import { isAbsolute, join, relative } from "node:path";
import { Worker } from "node:worker_threads";

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
  "urn:ucf:adapter:execution-verification-request:1.0.0";
const RESULT_SCHEMA_URI =
  "urn:ucf:adapter:execution-verification-result:1.0.0";
const MAPPING_RESULT_SCHEMA_URI =
  "urn:ucf:adapter:implementation-mapping-result:1.0.0";
const PROFILE_PROCEDURE_URI =
  "urn:ucf:implementation-evidence:verify:1.0.0";
const ADAPTER_PROCEDURE_URI =
  "urn:ucf:adapter:typescript-fastify-real-http-verification:1.0.0";
const ENVIRONMENT_IDENTITY_URI =
  "urn:ucf:fixture-environment:node22-linux-loopback:1.0.0";
const ENVIRONMENT_REVISION =
  "5c1cb86c391a5942088462fa2fe4e8a4deec768f6b37fd69027e37729555ce02";
const CHECK_PROCEDURE_URI =
  "urn:ucf:fixture-check:quote-order-http-contract:1.0.0";
const SUBJECT_ID = "use-case.quote-order";
const SUPPORTED_NODE_VERSION = "22.22.3";
const SUPPORTED_PLATFORM = "linux";
const SUPPORTED_ARCHITECTURE = "x64";
const WORKER_DEADLINE_MS = 5_000;
const PRODUCER: JsonObject = {
  kind: "producer",
  name: "org.ucf.adapter.typescript-fastify",
  version: VERSION,
};
const CAPABILITY: JsonObject = {
  kind: "capability",
  name: "org.ucf.adapter.verification",
  version: VERSION,
};

type VerificationOutcome = "passed" | "failed" | "error";

interface VerificationValues {
  quantity: number;
  unitPriceCents: number;
  expectedTotalCents: number;
}

interface WorkerResult {
  outcome: VerificationOutcome;
  executedAt: string;
}

export interface VerificationJob {
  promise: Promise<JsonObject>;
  cancel(): Promise<void>;
}

export class VerificationProfileError extends Error {
  public constructor(
    public readonly code: "invalid_params" | "operation_failed",
    message: string,
  ) {
    super(message);
    this.name = "VerificationProfileError";
  }
}

export function startVerificationPayload(
  payload: JsonValue | undefined,
  decodedValue: JsonValue,
  run: Readonly<InventoryRun> | null,
  mapping: JsonObject | null,
): VerificationJob {
  if (run === null || mapping === null) {
    throw new VerificationProfileError(
      "operation_failed",
      "verification requires current inventory and mapping context",
    );
  }
  const values = decodeRequest(
    payload,
    decodedValue,
    run,
    mapping,
  );
  requireSupportedRuntime();
  preflightServiceModule();
  const workerJob = startVerificationWorker(values);
  return {
    promise: workerJob.promise.then((workerResult) =>
      buildResultPayload(decodedValue as JsonObject, workerResult)
    ),
    cancel: workerJob.cancel,
  };
}

function decodeRequest(
  payload: JsonValue | undefined,
  decoded: JsonValue,
  run: Readonly<InventoryRun>,
  mapping: JsonObject,
): VerificationValues {
  if (
    !hasExactKeys(
      payload,
      ["kind", "schema_uri", "schema_version", "value"],
    )
    || payload["kind"] !== "adapter_payload"
    || payload["schema_uri"] !== REQUEST_SCHEMA_URI
    || payload["schema_version"] !== VERSION
  ) {
    invalid("verification payload coordinates are incompatible");
  }
  if (!isObject(decoded)) {
    invalid("verification request root is not a record");
  }
  requireExact(decoded, [
    "kind",
    "implementation_evidence_version",
    "schema_uri",
    "capability",
    "profile_procedure_uri",
    "adapter_procedure_uri",
    "mapping",
    "base_behavior",
    "subject",
    "inputs",
    "expected_outputs",
    "source",
    "environment",
    "check",
  ]);
  if (
    decoded["kind"] !== "execution_verification_request"
    || decoded["implementation_evidence_version"] !== VERSION
    || decoded["schema_uri"] !== REQUEST_SCHEMA_URI
    || !sameJson(decoded["capability"], CAPABILITY)
    || decoded["profile_procedure_uri"] !== PROFILE_PROCEDURE_URI
    || decoded["adapter_procedure_uri"] !== ADAPTER_PROCEDURE_URI
  ) {
    invalid("verification request coordinates are incompatible");
  }
  const context = validateMappingContext(mapping, run);
  if (
    !sameJson(decoded["mapping"], mappingReference(mapping))
    || !sameJson(decoded["base_behavior"], context.baseBehavior)
    || !sameJson(decoded["subject"], context.subject)
    || !sameJson(decoded["source"], context.source)
    || !sameJson(decoded["environment"], supportedEnvironment())
    || !sameJson(decoded["check"], supportedCheck())
  ) {
    invalid("verification request differs from current execution context");
  }
  const quantity = readPortInteger(
    decoded["inputs"],
    0,
    "input",
    "quantity",
  );
  const unitPriceCents = readPortInteger(
    decoded["inputs"],
    1,
    "input",
    "unit-price-cents",
  );
  if (
    !Array.isArray(decoded["inputs"])
    || decoded["inputs"].length !== 2
    || quantity !== 2
    || unitPriceCents !== 1_250
    || !Number.isSafeInteger(quantity * unitPriceCents)
  ) {
    invalid("verification input values are outside the supported procedure");
  }
  const expectedTotalCents = readPortInteger(
    decoded["expected_outputs"],
    0,
    "output",
    "total-cents",
  );
  if (
    !Array.isArray(decoded["expected_outputs"])
    || decoded["expected_outputs"].length !== 1
    || expectedTotalCents < 0
  ) {
    invalid("verification expected output is outside the supported procedure");
  }
  return { quantity, unitPriceCents, expectedTotalCents };
}

function validateMappingContext(
  mapping: JsonObject,
  run: Readonly<InventoryRun>,
): {
  baseBehavior: JsonObject;
  subject: JsonObject;
  source: JsonObject;
} {
  requireExact(mapping, [
    "kind",
    "implementation_evidence_version",
    "schema_uri",
    "id",
    "status",
    "request",
    "producer",
    "capability",
    "procedure_uri",
    "bindings",
  ]);
  const request = mapping["request"];
  const bindings = mapping["bindings"];
  if (
    mapping["kind"] !== "implementation_mapping_result"
    || mapping["implementation_evidence_version"] !== VERSION
    || mapping["schema_uri"] !== MAPPING_RESULT_SCHEMA_URI
    || mapping["status"] !== "complete"
    || !sameJson(mapping["producer"], PRODUCER)
    || !isObject(request)
    || !Array.isArray(bindings)
    || bindings.length !== 1
    || !isObject(bindings[0])
    || !sameJson(request["inventory"], run.snapshot)
  ) {
    invalid("current mapping context is incompatible");
  }
  const binding = bindings[0];
  requireExact(binding, ["kind", "behavior", "source_records"]);
  const subject = binding["behavior"];
  const sourceRecords = binding["source_records"];
  const inventory = request["inventory"];
  if (
    binding["kind"] !== "implementation_binding"
    || !hasExactKeys(subject, [
      "kind",
      "document_id",
      "ir_version",
      "canonical_digest",
      "target_kind",
      "target_id",
    ])
    || subject["kind"] !== "behavior_entity_ref"
    || subject["target_kind"] !== "use_case"
    || subject["target_id"] !== SUBJECT_ID
    || !Array.isArray(sourceRecords)
    || sourceRecords.length !== 5
    || !isObject(inventory)
  ) {
    invalid("current mapping binding is incompatible");
  }
  return {
    baseBehavior: {
      kind: "behavior_document_ref",
      document_id: subject["document_id"] ?? null,
      ir_version: subject["ir_version"] ?? null,
      canonical_digest: subject["canonical_digest"] ?? null,
    },
    subject,
    source: {
      kind: "implementation_source",
      subject_uri: inventory["subject_uri"] ?? null,
      source_revision: inventory["source_revision"] ?? null,
      records: sourceRecords,
    },
  };
}

function mappingReference(mapping: JsonObject): JsonObject {
  return {
    kind: "implementation_mapping_result_ref",
    schema_uri: MAPPING_RESULT_SCHEMA_URI,
    schema_version: VERSION,
    target_id: mapping["id"] ?? null,
    canonical_digest: digest(sha256(canonicalJson(mapping))),
  };
}

function supportedEnvironment(): JsonObject {
  return {
    kind: "execution_environment",
    identity_uri: ENVIRONMENT_IDENTITY_URI,
    revision: digest(ENVIRONMENT_REVISION),
  };
}

function supportedCheck(): JsonObject {
  return {
    kind: "check",
    id: "check.quote-order.real-http",
    version: VERSION,
    procedure_uri: CHECK_PROCEDURE_URI,
  };
}

function readPortInteger(
  values: JsonValue | undefined,
  index: number,
  direction: "input" | "output",
  name: string,
): number {
  if (!Array.isArray(values)) {
    invalid("verification port values are not a list");
  }
  const value = values[index];
  if (
    !hasExactKeys(value, ["kind", "port", "value"])
    || value["kind"] !== "execution_port_value"
    || !sameJson(
      value["port"],
      {
        kind: "port_ref",
        owner: {
          kind: "entity_ref",
          target_kind: "use_case",
          target_id: SUBJECT_ID,
        },
        direction,
        name,
      },
    )
    || !hasExactKeys(value["value"], ["kind", "value"])
    || value["value"]["kind"] !== "integer"
    || typeof value["value"]["value"] !== "number"
    || !Number.isSafeInteger(value["value"]["value"])
    || Object.is(value["value"]["value"], -0)
  ) {
    invalid("verification port value is incompatible");
  }
  return value["value"]["value"];
}

function requireSupportedRuntime(): void {
  if (
    process.versions.node !== SUPPORTED_NODE_VERSION
    || process.platform !== SUPPORTED_PLATFORM
    || process.arch !== SUPPORTED_ARCHITECTURE
  ) {
    throw new VerificationProfileError(
      "operation_failed",
      "verification runtime does not match the declared environment",
    );
  }
}

function preflightServiceModule(): void {
  try {
    const requestedRoot = process.cwd();
    const root = realpathSync(requestedRoot);
    if (root !== requestedRoot || !lstatSync(root).isDirectory()) {
      unavailable();
    }
    const distribution = join(root, "dist");
    const distributionMetadata = lstatSync(distribution);
    if (
      distributionMetadata.isSymbolicLink()
      || !distributionMetadata.isDirectory()
    ) {
      unavailable();
    }
    const service = join(distribution, "service.js");
    const serviceMetadata = lstatSync(service);
    const resolved = realpathSync(service);
    const within = relative(root, resolved);
    if (
      serviceMetadata.isSymbolicLink()
      || !serviceMetadata.isFile()
      || resolved !== service
      || within === ""
      || within.startsWith("..")
      || isAbsolute(within)
    ) {
      unavailable();
    }
  } catch (error: unknown) {
    if (error instanceof VerificationProfileError) {
      throw error;
    }
    unavailable();
  }
}

function startVerificationWorker(
  values: VerificationValues,
): {
  promise: Promise<WorkerResult>;
  cancel(): Promise<void>;
} {
  const worker = new Worker(
    new URL("./worker.js", import.meta.url),
    { workerData: values },
  );
  let settled = false;
  let rejectPromise: (reason: VerificationProfileError) => void = () => {};
  let deadline: NodeJS.Timeout;
  const promise = new Promise<WorkerResult>((resolve, reject) => {
    rejectPromise = reject;
    const finish = (result: WorkerResult): void => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(deadline);
      void worker.terminate().then(
        () => resolve(result),
        () => resolve(errorWorkerResult()),
      );
    };
    worker.once("message", (message: unknown) => {
      finish(validWorkerResult(message) ? message : errorWorkerResult());
    });
    worker.once("error", () => {
      finish(errorWorkerResult());
    });
    worker.once("exit", () => {
      if (!settled) {
        finish(errorWorkerResult());
      }
    });
    deadline = setTimeout(() => {
      finish(errorWorkerResult());
    }, WORKER_DEADLINE_MS);
  });
  return {
    promise,
    async cancel(): Promise<void> {
      if (!settled) {
        settled = true;
        clearTimeout(deadline);
        rejectPromise(new VerificationProfileError(
          "operation_failed",
          "verification operation was cancelled",
        ));
      }
      await worker.terminate();
    },
  };
}

function buildResultPayload(
  request: JsonObject,
  workerResult: WorkerResult,
): JsonObject {
  const provisional: JsonObject = {
    kind: "execution_verification_result",
    implementation_evidence_version: VERSION,
    schema_uri: RESULT_SCHEMA_URI,
    id: `result.${"0".repeat(64)}`,
    status: "completed",
    request,
    outcome: workerResult.outcome,
    executed_at: workerResult.executedAt,
    producer: PRODUCER,
    capability: CAPABILITY,
    procedure_uri: ADAPTER_PROCEDURE_URI,
  };
  const projection = Object.fromEntries(
    Object.entries(provisional).filter(([name]) => name !== "id"),
  ) as JsonObject;
  provisional["id"] = `result.${sha256(canonicalJson(projection))}`;
  return {
    kind: "adapter_payload",
    schema_uri: RESULT_SCHEMA_URI,
    schema_version: VERSION,
    value: encodeTagged(provisional),
  };
}

function validWorkerResult(value: unknown): value is WorkerResult {
  return hasExactKeys(value, ["outcome", "executedAt"])
    && (
      value["outcome"] === "passed"
      || value["outcome"] === "failed"
      || value["outcome"] === "error"
    )
    && validTimestamp(value["executedAt"]);
}

function errorWorkerResult(): WorkerResult {
  return { outcome: "error", executedAt: wholeSecondNow() };
}

function wholeSecondNow(): string {
  return new Date(
    Math.floor(Date.now() / 1_000) * 1_000,
  ).toISOString().replace(".000Z", "Z");
}

function validTimestamp(value: JsonValue | undefined): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/u.test(value)
    && new Date(value).toISOString() === value.replace("Z", ".000Z");
}

function digest(value: string): JsonObject {
  return { kind: "digest", algorithm: "sha-256", value };
}

function sameJson(
  value: JsonValue | undefined,
  expected: JsonValue,
): boolean {
  return canonicalJson(value ?? null) === canonicalJson(expected);
}

function requireExact(
  value: JsonObject,
  fields: readonly string[],
): void {
  if (!hasExactKeys(value, fields)) {
    invalid("verification profile fields are not exact");
  }
}

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function unavailable(): never {
  throw new VerificationProfileError(
    "operation_failed",
    "verification executable layout is unavailable",
  );
}

function invalid(message: string): never {
  throw new VerificationProfileError("invalid_params", message);
}
