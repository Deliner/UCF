import { createHash } from "node:crypto";
import { Worker } from "node:worker_threads";

import { canonicalJson } from "../canonical-json.js";
import {
  type JsonObject,
  type JsonValue,
  hasExactKeys,
  isObject,
} from "../strict-json.js";
import {
  encodeTagged,
} from "../tagged-values.js";
import {
  type ClassifiedFact,
  InventoryClassificationError,
  classifySupportedFixture,
} from "./classifier.js";
import {
  InventoryTraversalError,
  type ScannedEntry,
  logicalIgnoreRules,
  scanRepository,
} from "./traversal.js";

const VERSION = "1.0.0";
const MAX_PROTOCOL_FRAME_BYTES = 1_048_576;
const REQUEST_SCHEMA_URI =
  "urn:ucf:adapter:inventory-request:1.0.0";
const PAGE_SCHEMA_URI = "urn:ucf:adapter:inventory-page:1.0.0";
const SNAPSHOT_SCHEMA_URI = "urn:ucf:schema:inventory:1.0.0";
const PATH_IDENTITY = "unicode-nfc-ascii-casefold-1";
const FACT_KINDS = [
  "api_description",
  "build_manifest",
  "public_interface",
  "repository_entry",
  "test_asset",
] as const;
const PRODUCER: JsonObject = {
  kind: "producer",
  name: "org.ucf.adapter.typescript-fastify",
  version: VERSION,
};
const CAPABILITY: JsonObject = {
  kind: "capability",
  name: "org.ucf.adapter.inventory",
  version: VERSION,
};
const CONFIDENCE: JsonObject = {
  kind: "confidence",
  scale: "decimal-0-to-1",
  value: "1",
  basis: "urn:ucf:inventory-procedure:direct-observation:1.0.0",
};
const ENTRY_PROCEDURE =
  "urn:ucf:inventory-procedure:typescript-fastify-entry:1.0.0";
const CLASSIFICATION_PROCEDURE =
  "urn:ucf:inventory-procedure:typescript-fastify-token-span-half-open:1.0.0";
const RECORD_PREFIX = new Map([
  ["build_manifest", "manifest"],
  ["inventory_ignore_match", "ignore"],
  ["inventory_provenance", "provenance"],
  ["public_interface", "interface"],
  ["repository_entry", "entry"],
  ["test_asset", "test"],
]);
const IDENTIFIER = /^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/;
const QUALIFIED_NAME =
  /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$/;
const URI = /^[a-z][a-z0-9+.-]*:[^\s]+$/;
const DIGEST = /^[0-9a-f]{64}$/;
const VERSIONED = /(?:[:/])(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$/;

export class InventoryProfileError extends Error {
  public constructor(
    public readonly code: "invalid_params" | "operation_failed",
    message: string,
  ) {
    super(message);
    this.name = "InventoryProfileError";
  }
}

export interface InventoryRequest {
  logical: JsonObject;
  subjectUri: string;
  rootPath: string;
  ignorePolicy: JsonObject;
  ignoreRules: JsonObject[];
  recordLimit: number;
  cursor: JsonObject | null;
}

export interface InventoryRun {
  key: string;
  snapshot: JsonObject;
  snapshotDigest: string;
  records: JsonObject[];
}

export interface InventoryJob {
  promise: Promise<JsonObject>;
  cancel(): Promise<void>;
}

export class InventoryProfile {
  private run: InventoryRun | null = null;

  public completedRun(): Readonly<InventoryRun> | null {
    return this.run;
  }

  public start(
    payload: JsonValue | undefined,
    decodedValue: JsonValue,
    requestId: string,
  ): InventoryJob {
    const request = decodeRequest(payload, decodedValue);
    const key = runKey(request.logical);
    if (request.cursor === null) {
      this.run = null;
      const workerJob = startInventoryWorker(request, key);
      return {
        promise: workerJob.promise.then((run) => {
          this.run = run;
          return buildBoundedPayload(request, run, requestId);
        }),
        cancel: workerJob.cancel,
      };
    }
    const run = this.run;
    if (run === null || run.key !== key) {
      throw new InventoryProfileError(
        "operation_failed",
        "inventory cursor has no matching active snapshot",
      );
    }
    return {
      promise: Promise.resolve(
        buildBoundedPayload(request, run, requestId),
      ),
      async cancel(): Promise<void> {},
    };
  }
}

function decodeRequest(
  payload: JsonValue | undefined,
  decoded: JsonValue,
): InventoryRequest {
  if (
    !hasExactKeys(
      payload,
      ["kind", "schema_uri", "schema_version", "value"],
    )
    || payload["kind"] !== "adapter_payload"
    || payload["schema_uri"] !== REQUEST_SCHEMA_URI
    || payload["schema_version"] !== VERSION
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory payload coordinates are incompatible",
    );
  }
  if (!isObject(decoded)) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory request root is not a record",
    );
  }
  requireExact(decoded, [
    "kind",
    "inventory_version",
    "schema_uri",
    "subject_uri",
    "root_path",
    "fact_kinds",
    "ignore_policy",
    "page",
  ]);
  if (
    decoded["kind"] !== "inventory_request_profile"
    || decoded["inventory_version"] !== VERSION
    || decoded["schema_uri"] !== REQUEST_SCHEMA_URI
    || typeof decoded["subject_uri"] !== "string"
    || !URI.test(decoded["subject_uri"])
    || decoded["subject_uri"].startsWith("file:")
    || typeof decoded["root_path"] !== "string"
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory request coordinates are invalid",
    );
  }
  validateRepositoryPath(decoded["root_path"]);
  const factKinds = decoded["fact_kinds"];
  if (
    !Array.isArray(factKinds)
    || factKinds.length !== FACT_KINDS.length
    || FACT_KINDS.some(
      (kind, index) => factKinds[index] !== kind,
    )
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory fact kinds are not canonical",
    );
  }
  const policy = validateIgnorePolicy(decoded["ignore_policy"]);
  const page = validatePage(decoded["page"]);
  return {
    logical: decoded,
    subjectUri: decoded["subject_uri"],
    rootPath: decoded["root_path"],
    ignorePolicy: policy.policy,
    ignoreRules: policy.rules,
    recordLimit: page.recordLimit,
    cursor: page.cursor,
  };
}

function validateIgnorePolicy(
  value: JsonValue | undefined,
): { policy: JsonObject; rules: JsonObject[] } {
  if (!hasExactKeys(value, ["kind", "policy_version", "rules"])
      || value["kind"] !== "ignore_policy"
      || value["policy_version"] !== VERSION
      || !Array.isArray(value["rules"])
      || value["rules"].length > 256) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory ignore policy is invalid",
    );
  }
  const rules: JsonObject[] = [];
  const ids: string[] = [];
  const matchers = new Set<string>();
  for (const item of value["rules"]) {
    if (
      !hasExactKeys(item, ["kind", "id", "reason", "matcher"])
      || item["kind"] !== "ignore_rule"
      || typeof item["id"] !== "string"
      || !IDENTIFIER.test(item["id"])
      || typeof item["reason"] !== "string"
      || !QUALIFIED_NAME.test(item["reason"])
      || !isObject(item["matcher"])
    ) {
      throw new InventoryProfileError(
        "invalid_params",
        "inventory ignore rule is invalid",
      );
    }
    const matcher = item["matcher"];
    let identity: string;
    if (
      hasExactKeys(matcher, ["kind", "segment"])
      && matcher["kind"] === "path_segment"
      && typeof matcher["segment"] === "string"
    ) {
      validatePathSegment(matcher["segment"]);
      identity = `path_segment:${matcher["segment"]}`;
    } else if (
      hasExactKeys(matcher, ["kind", "path"])
      && matcher["kind"] === "path_prefix"
      && typeof matcher["path"] === "string"
      && matcher["path"] !== "."
    ) {
      validateRepositoryPath(matcher["path"]);
      identity = `path_prefix:${matcher["path"]}`;
    } else {
      throw new InventoryProfileError(
        "invalid_params",
        "inventory ignore matcher is invalid",
      );
    }
    if (matchers.has(identity)) {
      throw new InventoryProfileError(
        "invalid_params",
        "inventory ignore matcher is duplicated",
      );
    }
    matchers.add(identity);
    ids.push(item["id"]);
    rules.push(item);
  }
  if (
    ids.some((id, index) => id !== [...ids].sort()[index])
    || new Set(ids).size !== ids.length
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory ignore rule IDs are not canonical",
    );
  }
  return { policy: value, rules };
}

function validatePage(
  value: JsonValue | undefined,
): { recordLimit: number; cursor: JsonObject | null } {
  if (
    !hasExactKeys(value, ["kind", "record_limit", "cursor"])
    || value["kind"] !== "inventory_page_request"
    || typeof value["record_limit"] !== "number"
    || !Number.isInteger(value["record_limit"])
    || value["record_limit"] < 1
    || value["record_limit"] > 256
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory page request is invalid",
    );
  }
  if (value["cursor"] === null) {
    return { recordLimit: value["record_limit"], cursor: null };
  }
  const cursor = value["cursor"];
  if (
    !hasExactKeys(
      cursor,
      ["kind", "snapshot_digest", "after_kind", "after_id"],
    )
    || cursor["kind"] !== "inventory_cursor"
    || !validDigest(cursor["snapshot_digest"])
    || typeof cursor["after_kind"] !== "string"
    || typeof cursor["after_id"] !== "string"
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory cursor is invalid",
    );
  }
  const prefix = RECORD_PREFIX.get(cursor["after_kind"]);
  if (
    prefix === undefined
    || !cursor["after_id"].startsWith(`${prefix}.`)
    || !DIGEST.test(cursor["after_id"].slice(prefix.length + 1))
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory cursor coordinate is invalid",
    );
  }
  return { recordLimit: value["record_limit"], cursor };
}

export function buildRun(
  request: InventoryRequest,
  key: string,
): InventoryRun {
  let scan;
  let classifications: ClassifiedFact[];
  try {
    const rules = logicalIgnoreRules(request.ignoreRules);
    scan = scanRepository(request.rootPath, rules);
    classifications = classifySupportedFixture(scan);
  } catch (error: unknown) {
    if (
      error instanceof InventoryTraversalError
      || error instanceof InventoryClassificationError
    ) {
      throw new InventoryProfileError(
        "operation_failed",
        "inventory source is outside the supported TypeScript/Fastify profile",
      );
    }
    throw error;
  }

  const records: JsonObject[] = [];
  const entries = new Map<string, JsonObject>();
  for (const scanned of scan.entries) {
    const evidenceDigest = scanned.entryKind === "file"
      ? scanned.contentDigest
      : scanned.entryKind === "symlink"
        ? scanned.symlinkTargetDigest
        : null;
    const provenance = identified({
      kind: "inventory_provenance",
      source_path: scanned.path,
      content_digest: evidenceDigest === null
        ? null
        : digest(evidenceDigest),
      source_span: null,
      producer: PRODUCER,
      procedure_uri: ENTRY_PROCEDURE,
    });
    records.push(provenance);
    const entry = identified({
      kind: "repository_entry",
      level: "observed",
      provenance: reference(provenance),
      confidence: CONFIDENCE,
      path: scanned.path,
      entry_kind: scanned.entryKind,
      size_bytes: scanned.sizeBytes,
      content_digest: scanned.contentDigest === null
        ? null
        : digest(scanned.contentDigest),
      symlink_target_digest: scanned.symlinkTargetDigest === null
        ? null
        : digest(scanned.symlinkTargetDigest),
    });
    records.push(entry);
    entries.set(scanned.path, entry);
  }

  for (const classified of classifications) {
    const scanned = scan.entries.find(
      (item) => item.path === classified.path,
    );
    const entry = entries.get(classified.path);
    if (
      scanned === undefined
      || scanned.contentDigest === null
      || entry === undefined
    ) {
      throw new InventoryProfileError(
        "operation_failed",
        "classified source entry is unavailable",
      );
    }
    const provenance = identified({
      kind: "inventory_provenance",
      source_path: classified.path,
      content_digest: digest(scanned.contentDigest),
      source_span: {
        kind: "source_span",
        start_line: classified.span.startLine,
        start_column: classified.span.startColumn,
        end_line: classified.span.endLine,
        end_column: classified.span.endColumn,
      },
      producer: PRODUCER,
      procedure_uri: CLASSIFICATION_PROCEDURE,
    });
    records.push(provenance);
    records.push(identified({
      kind: classified.kind,
      level: "observed",
      provenance: reference(provenance),
      confidence: CONFIDENCE,
      entry: reference(entry),
      ...classified.attributes,
    }));
  }

  for (const ignored of scan.ignores) {
    records.push(identified({
      kind: "inventory_ignore_match",
      rule_id: ignored.ruleId,
      path: ignored.path,
    }));
  }
  records.sort(recordOrder);
  const sourceRevision = deriveSourceRevision(scan.entries);
  const coverage = FACT_KINDS.map((factKind) => ({
    kind: "inventory_coverage",
    fact_kind: factKind,
    status: "complete",
    record_count: records.filter(
      (record) => record["kind"] === factKind,
    ).length,
  }));
  const snapshot: JsonObject = {
    kind: "inventory_snapshot",
    inventory_version: VERSION,
    schema_uri: SNAPSHOT_SCHEMA_URI,
    subject_uri: request.subjectUri,
    path_identity: PATH_IDENTITY,
    source_revision: digest(sourceRevision),
    producer: PRODUCER,
    capability: CAPABILITY,
    applied_policy: request.ignorePolicy,
    coverage,
    records,
  };
  const snapshotDigest = sha256(canonicalJson(snapshot));
  return { key, snapshot, snapshotDigest, records };
}

function buildPage(
  request: InventoryRequest,
  run: InventoryRun,
  recordLimit = request.recordLimit,
): JsonObject {
  let start = 0;
  if (request.cursor !== null) {
    const cursorDigest = request.cursor["snapshot_digest"];
    if (
      !isObject(cursorDigest)
      || cursorDigest["value"] !== run.snapshotDigest
    ) {
      throw new InventoryProfileError(
        "operation_failed",
        "inventory cursor snapshot is stale",
      );
    }
    const coordinate = [
      request.cursor["after_kind"],
      request.cursor["after_id"],
    ];
    const index = run.records.findIndex(
      (record) => record["kind"] === coordinate[0]
        && record["id"] === coordinate[1],
    );
    if (index < 0 || index + 1 >= run.records.length) {
      throw new InventoryProfileError(
        "operation_failed",
        "inventory cursor coordinate is unavailable",
      );
    }
    start = index + 1;
  }
  const selected = run.records.slice(
    start,
    start + recordLimit,
  );
  if (selected.length === 0) {
    throw new InventoryProfileError(
      "operation_failed",
      "inventory page would be empty",
    );
  }
  const complete = start + selected.length === run.records.length;
  const last = selected[selected.length - 1];
  if (last === undefined) {
    throw new InventoryProfileError(
      "operation_failed",
      "inventory page has no terminal coordinate",
    );
  }
  const nextCursor: JsonObject | null = complete
    ? null
    : {
        kind: "inventory_cursor",
        snapshot_digest: digest(run.snapshotDigest),
        after_kind: last["kind"] ?? "",
        after_id: last["id"] ?? "",
      };
  return {
    kind: "inventory_page",
    inventory_version: VERSION,
    schema_uri: PAGE_SCHEMA_URI,
    subject_uri: run.snapshot["subject_uri"] ?? "",
    path_identity: PATH_IDENTITY,
    source_revision: run.snapshot["source_revision"] ?? null,
    snapshot_digest: digest(run.snapshotDigest),
    producer: PRODUCER,
    capability: CAPABILITY,
    applied_policy: run.snapshot["applied_policy"] ?? null,
    coverage: run.snapshot["coverage"] ?? [],
    request_cursor: request.cursor,
    records: selected,
    next_cursor: nextCursor,
    complete,
  };
}

function buildBoundedPayload(
  request: InventoryRequest,
  run: InventoryRun,
  requestId: string,
): JsonObject {
  for (
    let recordLimit = request.recordLimit;
    recordLimit >= 1;
    recordLimit -= 1
  ) {
    const page = buildPage(request, run, recordLimit);
    const payload: JsonObject = {
      kind: "adapter_payload",
      schema_uri: PAGE_SCHEMA_URI,
      schema_version: VERSION,
      value: encodeTagged(page),
    };
    const response: JsonObject = {
      jsonrpc: "2.0",
      id: requestId,
      result: {
        kind: "inventory_result",
        payload,
      },
    };
    if (
      Buffer.byteLength(canonicalJson(response), "utf8")
      <= MAX_PROTOCOL_FRAME_BYTES
    ) {
      return payload;
    }
  }
  throw new InventoryProfileError(
    "operation_failed",
    "inventory page cannot fit the protocol frame bound",
  );
}

function startInventoryWorker(
  request: InventoryRequest,
  key: string,
): { promise: Promise<InventoryRun>; cancel(): Promise<void> } {
  const worker = new Worker(
    new URL("./worker.js", import.meta.url),
    { workerData: { request, key } },
  );
  let settled = false;
  let rejectPromise: (reason: InventoryProfileError) => void = () => {};
  const promise = new Promise<InventoryRun>((resolve, reject) => {
    rejectPromise = reject;
    worker.once("message", (message: unknown) => {
      if (settled) {
        return;
      }
      settled = true;
      if (
        hasExactKeys(message, ["kind", "run"])
        && message["kind"] === "success"
        && validInventoryRun(message["run"])
      ) {
        resolve(message["run"]);
        return;
      }
      reject(new InventoryProfileError(
        "operation_failed",
        "inventory worker could not complete the operation",
      ));
    });
    worker.once("error", () => {
      if (!settled) {
        settled = true;
        reject(new InventoryProfileError(
          "operation_failed",
          "inventory worker could not complete the operation",
        ));
      }
    });
    worker.once("exit", (code) => {
      if (!settled) {
        settled = true;
        reject(new InventoryProfileError(
          "operation_failed",
          code === 0
            ? "inventory worker produced no result"
            : "inventory worker could not complete the operation",
        ));
      }
    });
  });
  return {
    promise,
    async cancel(): Promise<void> {
      if (settled) {
        await worker.terminate();
        return;
      }
      settled = true;
      rejectPromise(new InventoryProfileError(
        "operation_failed",
        "inventory operation was cancelled",
      ));
      await worker.terminate();
    },
  };
}

function validInventoryRun(value: unknown): value is InventoryRun {
  return hasExactKeys(
    value,
    ["key", "snapshot", "snapshotDigest", "records"],
  )
    && typeof value["key"] === "string"
    && isObject(value["snapshot"])
    && typeof value["snapshotDigest"] === "string"
    && DIGEST.test(value["snapshotDigest"])
    && Array.isArray(value["records"])
    && value["records"].every(isObject);
}

function deriveSourceRevision(entries: readonly ScannedEntry[]): string {
  const projected = [...entries]
    .sort((left, right) => Buffer.compare(
      Buffer.from(left.path, "utf8"),
      Buffer.from(right.path, "utf8"),
    ))
    .map((entry) => ({
      content_digest: entry.contentDigest === null
        ? null
        : digest(entry.contentDigest),
      entry_kind: entry.entryKind,
      path: entry.path,
      read_status: "observed",
      size_bytes: entry.sizeBytes,
      symlink_target_digest: entry.symlinkTargetDigest === null
        ? null
        : digest(entry.symlinkTargetDigest),
    }));
  return sha256(canonicalJson({ entries: projected, failures: [] }));
}

function identified(record: JsonObject): JsonObject {
  const prefix = RECORD_PREFIX.get(String(record["kind"]));
  if (prefix === undefined) {
    throw new InventoryProfileError(
      "operation_failed",
      "inventory record kind is unsupported",
    );
  }
  return {
    ...record,
    id: `${prefix}.${sha256(canonicalJson(record))}`,
  };
}

function reference(record: JsonObject): JsonObject {
  return {
    kind: "inventory_record_ref",
    target_kind: record["kind"] ?? "",
    target_id: record["id"] ?? "",
  };
}

function digest(value: string): JsonObject {
  if (!DIGEST.test(value)) {
    throw new InventoryProfileError(
      "operation_failed",
      "inventory digest is not canonical",
    );
  }
  return { kind: "digest", algorithm: "sha-256", value };
}

function runKey(request: JsonObject): string {
  return canonicalJson({
    subject_uri: request["subject_uri"] ?? null,
    root_path: request["root_path"] ?? null,
    fact_kinds: request["fact_kinds"] ?? null,
    ignore_policy: request["ignore_policy"] ?? null,
  });
}

function recordOrder(left: JsonObject, right: JsonObject): number {
  const leftKey = `${String(left["kind"])}\0${String(left["id"])}`;
  const rightKey = `${String(right["kind"])}\0${String(right["id"])}`;
  return leftKey < rightKey ? -1 : leftKey > rightKey ? 1 : 0;
}

function sha256(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

function validDigest(value: JsonValue | undefined): boolean {
  return hasExactKeys(value, ["kind", "algorithm", "value"])
    && value["kind"] === "digest"
    && value["algorithm"] === "sha-256"
    && typeof value["value"] === "string"
    && DIGEST.test(value["value"]);
}

function requireExact(
  value: JsonObject,
  fields: readonly string[],
): void {
  if (!hasExactKeys(value, fields)) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory request fields are not exact",
    );
  }
}

function validateRepositoryPath(value: string): void {
  if (value === ".") {
    return;
  }
  if (
    value.length === 0
    || value.startsWith("/")
    || value.includes("\\")
    || value.includes("//")
    || value.normalize("NFC") !== value
    || Buffer.byteLength(value) > 1_024
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory repository path is invalid",
    );
  }
  const parts = value.split("/");
  if (parts.some((part) => part === "" || part === "." || part === "..")) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory repository path is invalid",
    );
  }
  parts.forEach(validatePathSegment);
}

function validatePathSegment(value: string): void {
  const basename = value.split(".", 1)[0]?.toUpperCase();
  if (
    value.length === 0
    || value === "."
    || value === ".."
    || value.normalize("NFC") !== value
    || Buffer.byteLength(value) > 255
    || /[\\/:<>"|?*\u0000-\u001f\u007f]/u.test(value)
    || value.endsWith(" ")
    || value.endsWith(".")
    || basename === "AUX"
    || basename === "CON"
    || basename === "NUL"
    || basename === "PRN"
    || /^COM[1-9]$/u.test(basename ?? "")
    || /^LPT[1-9]$/u.test(basename ?? "")
  ) {
    throw new InventoryProfileError(
      "invalid_params",
      "inventory path segment is invalid",
    );
  }
}
