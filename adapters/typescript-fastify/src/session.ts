import {
  type JsonObject,
  type JsonValue,
  hasExactKeys,
  isObject,
  parseStrictJson,
} from "./strict-json.js";
import { canonicalJson } from "./canonical-json.js";
import {
  DiscoveryProfileError,
  buildDiscoveryPayload,
} from "./discovery/profile.js";
import {
  InventoryProfile,
  InventoryProfileError,
} from "./inventory/profile.js";
import {
  MappingProfileError,
  buildMappingPayload,
} from "./mapping/profile.js";
import {
  TaggedValueError,
  decodeProfileTagged,
  decodeTagged,
} from "./tagged-values.js";
import { SessionLimits } from "./session-limits.js";
import {
  VerificationProfileError,
  startVerificationPayload,
} from "./verification/profile.js";

const PROTOCOL_VERSION = "1.0.0";
const CONTROL_SCHEMA_URI =
  "urn:ucf:adapter-conformance:control:1.0.0";
const CONTROL_SCHEMA_VERSION = "1.0.0";
const ADAPTER_NAME = "org.ucf.adapter.typescript-fastify";
const ADAPTER_VERSION = "1.0.0";
const MAX_FRAME_BYTES = 1_048_576;
const REQUEST_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/;
const NORMALIZED_VERSION =
  /^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$/;
const QUALIFIED_NAME =
  /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$/;
const URI = /^[a-z][a-z0-9+.-]*:[^\s]+$/;

const CAPABILITY_BY_METHOD = new Map<string, string>([
  ["ucf.inventory", "org.ucf.adapter.inventory"],
  ["ucf.discover", "org.ucf.adapter.discovery"],
  ["ucf.map", "org.ucf.adapter.mapping"],
  ["ucf.generate", "org.ucf.adapter.generation"],
  ["ucf.verify", "org.ucf.adapter.verification"],
]);
const SUPPORTED_CAPABILITIES = new Map<string, string>(
  Array.from(
    CAPABILITY_BY_METHOD.values(),
    (name): [string, string] => [name, "1.0.0"],
  ),
);
const RESULT_KIND_BY_METHOD = new Map<string, string>([
  ["ucf.inventory", "inventory_result"],
  ["ucf.discover", "discover_result"],
  ["ucf.map", "map_result"],
  ["ucf.generate", "generate_result"],
  ["ucf.verify", "verify_result"],
]);
const KNOWN_REQUEST_METHODS = new Set([
  "ucf.initialize",
  "ucf.shutdown",
  ...CAPABILITY_BY_METHOD.keys(),
]);

type Lifecycle = "new" | "ready" | "closed";
type ProtocolCode =
  | "capability_not_negotiated"
  | "duplicate_capability"
  | "duplicate_request_id"
  | "frame_too_large"
  | "incompatible_version"
  | "internal_error"
  | "invalid_lifecycle"
  | "invalid_message"
  | "invalid_params"
  | "method_not_found"
  | "operation_failed"
  | "parse_error"
  | "request_cancelled"
  | "session_request_limit"
  | "too_many_pending"
  | "truncated_frame"
  | "unsupported_capability";

interface RequestMessage extends JsonObject {
  jsonrpc: "2.0";
  id: string;
  method: string;
  params: JsonObject;
}

interface CapabilityRequest extends JsonObject {
  kind: "capability_request";
  name: string;
  minimum_version: string;
  required: boolean;
}

interface ValidatedAdapterPayload {
  wire: JsonObject;
}

type Control =
  | { operation: "block" }
  | { operation: "echo"; value: JsonObject }
  | { operation: "readiness"; targetRequestId: string };

interface ActiveRequest {
  method: string;
  cancelling: boolean;
  cancel(): Promise<void> | null;
}

let lifecycle: Lifecycle = "new";
const active = new Map<string, ActiveRequest>();
const selectedCapabilities = new Set<string>();
const seenRequestIds = new Set<string>();
const inventoryProfile = new InventoryProfile();
let mappingResult: JsonObject | null = null;
const limits = new SessionLimits();

export function handleFrame(frame: string): boolean {
  let decoded: JsonValue;
  try {
    decoded = parseStrictJson(frame);
  } catch (error: unknown) {
    if (error instanceof SyntaxError) {
      writeError(null, "parse_error", "invalid JSON input");
      return false;
    }
    throw error;
  }
  handleMessage(decoded);
  return lifecycle === "closed";
}

export function writeTransportError(
  code: "frame_too_large" | "invalid_message" | "parse_error" | "truncated_frame",
  message: string,
): void {
  writeError(null, code, message);
}

function handleMessage(message: JsonValue): void {
  if (!isObject(message)) {
    writeError(null, "invalid_message", "request root must be an object");
    return;
  }
  if (!Object.hasOwn(message, "id")) {
    if (message["method"] === "ucf.cancel") {
      cancel(message);
    } else {
      writeError(
        null,
        "invalid_message",
        "only ucf.cancel may be a notification",
      );
    }
    return;
  }
  if (!validRequestEnvelope(message)) {
    writeError(
      recoverRequestId(message),
      "invalid_message",
      "invalid request envelope",
    );
    return;
  }
  if (!KNOWN_REQUEST_METHODS.has(message.method)) {
    writeError(message.id, "method_not_found", "unknown adapter method");
    return;
  }
  if (seenRequestIds.has(message.id)) {
    writeError(
      message.id,
      "duplicate_request_id",
      "request id was already used in this session",
    );
    return;
  }
  if (!limits.acceptRequest(message.method)) {
    writeError(
      message.id,
      "session_request_limit",
      "session request limit was reached",
    );
    return;
  }
  seenRequestIds.add(message.id);
  if (message.method === "ucf.initialize") {
    initialize(message);
    return;
  }
  if (message.method === "ucf.shutdown") {
    shutdown(message);
    return;
  }
  operation(message);
}

function initialize(message: RequestMessage): void {
  if (lifecycle !== "new") {
    writeError(
      message.id,
      "invalid_lifecycle",
      "initialize requires new state",
    );
    return;
  }
  const params = message.params;
  const capabilities = params["capabilities"];
  if (
    !hasExactKeys(
      params,
      ["kind", "protocol_version", "client", "capabilities"],
    )
    || params["kind"] !== "initialize_request"
    || typeof params["protocol_version"] !== "string"
    || !NORMALIZED_VERSION.test(params["protocol_version"])
    || !validProducer(params["client"])
    || !Array.isArray(capabilities)
    || !capabilities.every(validCapabilityRequest)
  ) {
    writeError(
      message.id,
      "invalid_params",
      "invalid initialize parameters",
    );
    return;
  }
  if (params["protocol_version"] !== PROTOCOL_VERSION) {
    writeError(
      message.id,
      "incompatible_version",
      "adapter protocol version is incompatible",
    );
    return;
  }
  const requested = capabilities as CapabilityRequest[];
  const names = requested.map((capability) => capability.name);
  if (new Set(names).size !== names.length) {
    writeError(
      message.id,
      "duplicate_capability",
      "capability requests must be unique",
    );
    return;
  }

  const selections: JsonObject[] = [];
  for (const capability of requested) {
    const supportedVersion = SUPPORTED_CAPABILITIES.get(capability.name);
    const supported = supportedVersion !== undefined
      && compareVersions(
        capability.minimum_version,
        supportedVersion,
      ) <= 0;
    if (!supported && capability.required) {
      writeError(
        message.id,
        "unsupported_capability",
        "required capability is unavailable",
      );
      return;
    }
    if (supported && supportedVersion !== undefined) {
      selections.push({
        kind: "capability",
        name: capability.name,
        version: supportedVersion,
      });
    }
  }
  selections.sort((left, right) => {
    const leftName = String(left["name"]);
    const rightName = String(right["name"]);
    return leftName < rightName ? -1 : leftName > rightName ? 1 : 0;
  });

  for (const selection of selections) {
    selectedCapabilities.add(selection["name"] as string);
  }
  lifecycle = "ready";
  write({
    jsonrpc: "2.0",
    id: message.id,
    result: {
      kind: "initialize_result",
      protocol_version: PROTOCOL_VERSION,
      adapter: {
        kind: "producer",
        name: ADAPTER_NAME,
        version: ADAPTER_VERSION,
      },
      capabilities: selections,
    },
  });
}

function operation(message: RequestMessage): void {
  if (lifecycle !== "ready") {
    writeError(
      message.id,
      "invalid_lifecycle",
      "operation requires ready state",
    );
    return;
  }
  const capability = CAPABILITY_BY_METHOD.get(message.method);
  if (capability === undefined || !selectedCapabilities.has(capability)) {
    writeError(
      message.id,
      "capability_not_negotiated",
      "operation capability was not negotiated",
    );
    return;
  }
  const requestKind = `${message.method.slice("ucf.".length)}_request`;
  if (
    !hasExactKeys(message.params, ["kind", "payload"])
    || message.params["kind"] !== requestKind
  ) {
    writeError(
      message.id,
      "invalid_params",
      "operation parameters do not match method",
    );
    return;
  }
  const payload = decodeAdapterPayload(message.params["payload"]);
  if (payload === null) {
    writeError(
      message.id,
      "invalid_params",
      "operation payload is invalid",
    );
    return;
  }
  const control = parseControl(payload.wire);
  if (control === null) {
    if (message.method === "ucf.inventory") {
      startInventory(message, payload);
      return;
    }
    if (message.method === "ucf.discover") {
      discover(message, payload);
      return;
    }
    if (message.method === "ucf.map") {
      mapImplementation(message, payload);
      return;
    }
    if (message.method === "ucf.verify") {
      startVerification(message, payload);
      return;
    }
    writeError(
      message.id,
      "operation_failed",
      "unsupported conformance control payload",
    );
    return;
  }
  if (control.operation === "block") {
    if (!limits.acceptsPending(active.size)) {
      writeError(
        message.id,
        "too_many_pending",
        "adapter pending request limit was reached",
      );
      return;
    }
    active.set(message.id, {
      method: message.method,
      cancelling: false,
      cancel(): null {
        return null;
      },
    });
    return;
  }

  const entries: JsonObject[] = control.operation === "readiness"
    ? [
        recordEntry("operation", stringValue("readiness_result")),
        recordEntry(
          "target_request_id",
          stringValue(control.targetRequestId),
        ),
        recordEntry(
          "active",
          { kind: "boolean", value: active.has(control.targetRequestId) },
        ),
      ]
    : [
        recordEntry("operation", stringValue("echo_result")),
        recordEntry("value", control.value),
      ];
  const resultKind = RESULT_KIND_BY_METHOD.get(message.method);
  if (resultKind === undefined) {
    writeError(
      message.id,
      "internal_error",
      "operation result kind is unavailable",
    );
    return;
  }
  write({
    jsonrpc: "2.0",
    id: message.id,
    result: {
      kind: resultKind,
      payload: {
        kind: "adapter_payload",
        schema_uri: CONTROL_SCHEMA_URI,
        schema_version: CONTROL_SCHEMA_VERSION,
        value: { kind: "record", entries },
      },
    },
  });
}

function mapImplementation(
  message: RequestMessage,
  payload: ValidatedAdapterPayload,
): void {
  try {
    const result = buildMappingPayload(
      payload.wire,
      decodeProfileTagged(payload.wire["value"]),
      inventoryProfile.completedRun(),
    );
    const decodedResult = decodeProfileTagged(result["value"]);
    if (!isObject(decodedResult)) {
      throw new Error("mapping result root is unavailable");
    }
    mappingResult = decodedResult;
    write({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        kind: "map_result",
        payload: result,
      },
    });
  } catch (error: unknown) {
    if (error instanceof TaggedValueError) {
      writeError(
        message.id,
        "invalid_params",
        "mapping profile value is noncanonical",
      );
    } else if (error instanceof MappingProfileError) {
      writeError(message.id, error.code, error.message);
    } else {
      writeError(
        message.id,
        "internal_error",
        "mapping operation failed internally",
      );
    }
  }
}

function startVerification(
  message: RequestMessage,
  payload: ValidatedAdapterPayload,
): void {
  if (!limits.acceptsPending(active.size)) {
    writeError(
      message.id,
      "too_many_pending",
      "adapter pending request limit was reached",
    );
    return;
  }
  let job;
  try {
    job = startVerificationPayload(
      payload.wire,
      decodeProfileTagged(payload.wire["value"]),
      inventoryProfile.completedRun(),
      mappingResult,
    );
  } catch (error: unknown) {
    if (error instanceof TaggedValueError) {
      writeError(
        message.id,
        "invalid_params",
        "verification profile value is noncanonical",
      );
    } else if (error instanceof VerificationProfileError) {
      writeError(message.id, error.code, error.message);
    } else {
      writeError(
        message.id,
        "internal_error",
        "verification operation could not be started",
      );
    }
    return;
  }
  const activeRequest: ActiveRequest = {
    method: message.method,
    cancelling: false,
    cancel: job.cancel,
  };
  active.set(message.id, activeRequest);
  void job.promise.then(
    (result) => {
      if (
        active.get(message.id) !== activeRequest
        || activeRequest.cancelling
      ) {
        return;
      }
      active.delete(message.id);
      write({
        jsonrpc: "2.0",
        id: message.id,
        result: {
          kind: "verify_result",
          payload: result,
        },
      });
    },
    (error: unknown) => {
      if (
        active.get(message.id) !== activeRequest
        || activeRequest.cancelling
      ) {
        return;
      }
      active.delete(message.id);
      if (error instanceof VerificationProfileError) {
        writeError(message.id, error.code, error.message);
      } else {
        writeError(
          message.id,
          "internal_error",
          "verification operation failed internally",
        );
      }
    },
  );
}

function discover(
  message: RequestMessage,
  payload: ValidatedAdapterPayload,
): void {
  try {
    const result = buildDiscoveryPayload(
      payload.wire,
      decodeProfileTagged(payload.wire["value"]),
      inventoryProfile.completedRun(),
    );
    write({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        kind: "discover_result",
        payload: result,
      },
    });
  } catch (error: unknown) {
    if (error instanceof TaggedValueError) {
      writeError(
        message.id,
        "invalid_params",
        "discovery profile value is noncanonical",
      );
    } else if (error instanceof DiscoveryProfileError) {
      writeError(message.id, error.code, error.message);
    } else {
      writeError(
        message.id,
        "internal_error",
        "discovery operation failed internally",
      );
    }
  }
}

function startInventory(
  message: RequestMessage,
  payload: ValidatedAdapterPayload,
): void {
  if (!limits.acceptsPending(active.size)) {
    writeError(
      message.id,
      "too_many_pending",
      "adapter pending request limit was reached",
    );
    return;
  }
  let job;
  try {
    const decodedValue = decodeProfileTagged(payload.wire["value"]);
    job = inventoryProfile.start(
      payload.wire,
      decodedValue,
      message.id,
    );
    if (
      isObject(decodedValue)
      && isObject(decodedValue["page"])
      && decodedValue["page"]["cursor"] === null
    ) {
      mappingResult = null;
    }
  } catch (error: unknown) {
    if (error instanceof TaggedValueError) {
      writeError(
        message.id,
        "invalid_params",
        "inventory profile value is noncanonical",
      );
    } else if (error instanceof InventoryProfileError) {
      writeError(message.id, error.code, error.message);
    } else {
      writeError(
        message.id,
        "internal_error",
        "inventory operation could not be started",
      );
    }
    return;
  }
  const activeRequest: ActiveRequest = {
    method: message.method,
    cancelling: false,
    cancel: job.cancel,
  };
  active.set(message.id, activeRequest);
  void job.promise.then(
    (payload) => {
      if (active.get(message.id) !== activeRequest) {
        return;
      }
      if (activeRequest.cancelling) {
        return;
      }
      active.delete(message.id);
      write({
        jsonrpc: "2.0",
        id: message.id,
        result: {
          kind: "inventory_result",
          payload,
        },
      });
    },
    (error: unknown) => {
      if (active.get(message.id) !== activeRequest) {
        return;
      }
      if (activeRequest.cancelling) {
        return;
      }
      active.delete(message.id);
      if (error instanceof InventoryProfileError) {
        writeError(message.id, error.code, error.message);
      } else {
        writeError(
          message.id,
          "internal_error",
          "inventory operation failed internally",
        );
      }
    },
  );
}

function cancel(message: JsonObject): void {
  if (
    !hasExactKeys(message, ["jsonrpc", "method", "params"])
    || message["jsonrpc"] !== "2.0"
    || message["method"] !== "ucf.cancel"
    || !hasExactKeys(message["params"], ["kind", "request_id"])
    || message["params"]["kind"] !== "cancel_request"
    || !validRequestId(message["params"]["request_id"])
  ) {
    writeError(
      null,
      "invalid_message",
      "invalid cancellation notification",
    );
    return;
  }
  const target = message["params"]["request_id"];
  const activeRequest = active.get(target);
  if (activeRequest === undefined) {
    return;
  }
  if (activeRequest.cancelling) {
    return;
  }
  activeRequest.cancelling = true;
  const stopping = activeRequest.cancel();
  if (stopping === null) {
    finishCancellation(target, activeRequest);
    return;
  }
  void stopping.then(
    () => finishCancellation(target, activeRequest),
    () => {
      if (active.get(target) === activeRequest) {
        active.delete(target);
        writeError(
          target,
          "internal_error",
          "adapter request cancellation failed",
        );
      }
    },
  );
}

function finishCancellation(
  target: string,
  activeRequest: ActiveRequest,
): void {
  if (active.get(target) !== activeRequest) {
    return;
  }
  active.delete(target);
  writeError(
    target,
    "request_cancelled",
    "adapter request was cancelled",
  );
}

function shutdown(message: RequestMessage): void {
  if (
    !hasExactKeys(message.params, ["kind"])
    || message.params["kind"] !== "shutdown_request"
  ) {
    writeError(
      message.id,
      "invalid_params",
      "invalid shutdown parameters",
    );
    return;
  }
  if (lifecycle !== "ready" || active.size !== 0) {
    writeError(
      message.id,
      "invalid_lifecycle",
      "shutdown requires ready state with no pending operations",
    );
    return;
  }
  lifecycle = "closed";
  write(
    {
      jsonrpc: "2.0",
      id: message.id,
      result: { kind: "shutdown_result" },
    },
    true,
  );
}

function parseControl(payload: JsonValue | undefined): Control | null {
  if (
    !hasExactKeys(
      payload,
      ["kind", "schema_uri", "schema_version", "value"],
    )
    || payload["kind"] !== "adapter_payload"
    || payload["schema_uri"] !== CONTROL_SCHEMA_URI
    || payload["schema_version"] !== CONTROL_SCHEMA_VERSION
  ) {
    return null;
  }
  const entries = recordEntries(payload["value"]);
  if (entries === null) {
    return null;
  }
  const operation = readStringValue(entries.get("operation"));
  if (
    operation === "echo"
    && entries.size === 2
    && entries.has("value")
  ) {
    const value = entries.get("value");
    return value === undefined ? null : { operation, value };
  }
  if (operation === "block" && entries.size === 1) {
    return { operation };
  }
  if (
    operation === "readiness"
    && entries.size === 2
    && entries.has("target_request_id")
  ) {
    const targetRequestId = readStringValue(
      entries.get("target_request_id"),
    );
    if (
      targetRequestId !== null
      && validRequestId(targetRequestId)
    ) {
      return { operation, targetRequestId };
    }
  }
  return null;
}

function decodeAdapterPayload(
  payload: JsonValue | undefined,
): ValidatedAdapterPayload | null {
  if (
    !hasExactKeys(
      payload,
      ["kind", "schema_uri", "schema_version", "value"],
    )
    || payload["kind"] !== "adapter_payload"
    || typeof payload["schema_uri"] !== "string"
    || payload["schema_uri"].length < 3
    || payload["schema_uri"].length > 2_048
    || !URI.test(payload["schema_uri"])
    || typeof payload["schema_version"] !== "string"
    || !NORMALIZED_VERSION.test(payload["schema_version"])
  ) {
    return null;
  }
  try {
    decodeTagged(payload["value"]);
    return { wire: payload };
  } catch (error: unknown) {
    if (error instanceof TaggedValueError) {
      return null;
    }
    throw error;
  }
}

function recordEntries(
  value: JsonValue | undefined,
): Map<string, JsonObject> | null {
  if (
    !hasExactKeys(value, ["kind", "entries"])
    || value["kind"] !== "record"
    || !Array.isArray(value["entries"])
  ) {
    return null;
  }
  const entries = new Map<string, JsonObject>();
  for (const entry of value["entries"]) {
    if (
      !hasExactKeys(entry, ["kind", "name", "value"])
      || entry["kind"] !== "record_entry"
      || typeof entry["name"] !== "string"
      || entries.has(entry["name"])
      || !isObject(entry["value"])
    ) {
      return null;
    }
    entries.set(entry["name"], entry["value"]);
  }
  return entries;
}

function validRequestEnvelope(
  message: JsonObject,
): message is RequestMessage {
  return hasExactKeys(message, ["jsonrpc", "id", "method", "params"])
    && message["jsonrpc"] === "2.0"
    && validRequestId(message["id"])
    && typeof message["method"] === "string"
    && isObject(message["params"]);
}

function recoverRequestId(message: JsonObject): string | null {
  const value = message["id"];
  return validRequestId(value) ? value : null;
}

function validRequestId(value: JsonValue | undefined): value is string {
  return typeof value === "string" && REQUEST_ID.test(value);
}

function validProducer(value: JsonValue | undefined): boolean {
  return hasExactKeys(value, ["kind", "name", "version"])
    && value["kind"] === "producer"
    && typeof value["name"] === "string"
    && value["name"].length <= 255
    && QUALIFIED_NAME.test(value["name"])
    && typeof value["version"] === "string"
    && NORMALIZED_VERSION.test(value["version"]);
}

function validCapabilityRequest(
  value: JsonValue,
): value is CapabilityRequest {
  return hasExactKeys(
    value,
    ["kind", "name", "minimum_version", "required"],
  )
    && value["kind"] === "capability_request"
    && typeof value["name"] === "string"
    && value["name"].length <= 255
    && QUALIFIED_NAME.test(value["name"])
    && typeof value["minimum_version"] === "string"
    && NORMALIZED_VERSION.test(value["minimum_version"])
    && typeof value["required"] === "boolean";
}

function compareVersions(left: string, right: string): number {
  const leftParts = left.split(".");
  const rightParts = right.split(".");
  const width = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < width; index += 1) {
    const comparison = compareDecimal(
      leftParts[index] ?? "0",
      rightParts[index] ?? "0",
    );
    if (comparison !== 0) {
      return comparison;
    }
  }
  return 0;
}

function compareDecimal(left: string, right: string): number {
  if (left.length !== right.length) {
    return left.length < right.length ? -1 : 1;
  }
  if (left === right) {
    return 0;
  }
  return left < right ? -1 : 1;
}

function readStringValue(value: JsonObject | undefined): string | null {
  return hasExactKeys(value, ["kind", "value"])
    && value["kind"] === "string"
    && typeof value["value"] === "string"
    ? value["value"]
    : null;
}

function stringValue(value: string): JsonObject {
  return { kind: "string", value };
}

function recordEntry(name: string, value: JsonObject): JsonObject {
  return { kind: "record_entry", name, value };
}

function writeError(
  id: string | null,
  code: ProtocolCode,
  message: string,
): void {
  write({
    jsonrpc: "2.0",
    id,
    error: {
      code: jsonRpcCode(code),
      message,
      data: {
        category: errorCategory(code),
        ucf_code: code,
      },
    },
  });
}

function jsonRpcCode(code: ProtocolCode): number {
  const standard: Partial<Record<ProtocolCode, number>> = {
    parse_error: -32700,
    invalid_message: -32600,
    method_not_found: -32601,
    invalid_params: -32602,
    internal_error: -32603,
  };
  return standard[code] ?? -32000;
}

function errorCategory(
  code: ProtocolCode,
): "adapter_failure" | "cancelled" | "protocol_failure" {
  if (code === "request_cancelled") {
    return "cancelled";
  }
  if (code === "operation_failed" || code === "internal_error") {
    return "adapter_failure";
  }
  return "protocol_failure";
}

function write(message: JsonObject, close = false): void {
  let encoded = canonicalJson(message);
  if (Buffer.byteLength(encoded, "utf8") > MAX_FRAME_BYTES) {
    const id = validRequestId(message["id"]) ? message["id"] : null;
    encoded = canonicalJson({
      jsonrpc: "2.0",
      id,
      error: {
        code: jsonRpcCode("operation_failed"),
        message: "adapter response exceeds the protocol frame bound",
        data: {
          category: errorCategory("operation_failed"),
          ucf_code: "operation_failed",
        },
      },
    });
  }
  process.stdout.write(encoded, () => {
    if (close) {
      process.exit(0);
    }
  });
}
