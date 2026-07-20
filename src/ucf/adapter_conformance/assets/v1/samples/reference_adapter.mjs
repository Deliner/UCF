const PROTOCOL_VERSION = "1.0.0";
const CONTROL_SCHEMA_URI = "urn:ucf:adapter-conformance:control:1.0.0";
const CONTROL_SCHEMA_VERSION = "1.0.0";
const ADAPTER_NAME = "org.ucf.adapter-conformance.reference";
const REQUEST_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/;
const NORMALIZED_VERSION = /^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$/;
const FAULT_MODES = new Set([
  "accepts-unnegotiated",
  "error-coordinates",
  "malformed-output",
  "response-timeout",
  "shutdown-nonzero",
  "unknown-response-id",
  "unsolicited-cancel",
]);
const faultMode = process.argv.length === 2
  ? null
  : process.argv.length === 4 && process.argv[2] === "--fault"
    && FAULT_MODES.has(process.argv[3])
    ? process.argv[3]
    : undefined;

if (faultMode === undefined) {
  process.stderr.write(
    `usage: reference_adapter.mjs [--fault ${
      Array.from(FAULT_MODES).join("|")
    }]\n`,
  );
  process.exit(2);
}

const CAPABILITY_BY_METHOD = new Map([
  ["ucf.inventory", "org.ucf.adapter.inventory"],
  ["ucf.discover", "org.ucf.adapter.discovery"],
  ["ucf.map", "org.ucf.adapter.mapping"],
  ["ucf.generate", "org.ucf.adapter.generation"],
  ["ucf.verify", "org.ucf.adapter.verification"],
]);
const SUPPORTED_CAPABILITIES = new Map(
  Array.from(CAPABILITY_BY_METHOD.values(), (name) => [name, "1.0.0"]),
);
const RESULT_KIND_BY_METHOD = new Map([
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

let lifecycle = "new";
let input = "";
let receivedMessageCount = 0;
let initializedByFirstBareRequest = false;
const active = new Map();
const selectedCapabilities = new Set();
const seenRequestIds = new Set();

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value, expected) {
  if (!isObject(value)) {
    return false;
  }
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return actual.length === wanted.length
    && actual.every((key, index) => key === wanted[index]);
}

function parseStrictJson(text) {
  if (text.startsWith("\uFEFF")) {
    throw new SyntaxError("UTF-8 BOM is not permitted");
  }
  let position = 0;

  function whitespace() {
    while (
      position < text.length
      && " \t\n\r".includes(text[position])
    ) {
      position += 1;
    }
  }

  function string() {
    const start = position;
    position += 1;
    let escaped = false;
    while (position < text.length) {
      const character = text[position];
      position += 1;
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === "\"") {
        return JSON.parse(text.slice(start, position));
      } else if (character < " ") {
        break;
      }
    }
    throw new SyntaxError("invalid JSON string");
  }

  function scalar() {
    const remainder = text.slice(position);
    for (const [token, value] of [
      ["true", true],
      ["false", false],
      ["null", null],
    ]) {
      if (remainder.startsWith(token)) {
        position += token.length;
        return value;
      }
    }
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(
      remainder,
    );
    if (match === null) {
      throw new SyntaxError("invalid JSON token");
    }
    const token = match[0];
    if (token === "-0" || token.includes(".") || /[eE]/.test(token)) {
      throw new SyntaxError("number is outside the exact integer profile");
    }
    const value = Number(token);
    if (!Number.isSafeInteger(value)) {
      throw new SyntaxError("integer is outside the exact range");
    }
    position += token.length;
    return value;
  }

  function value(depth) {
    if (depth > 128) {
      throw new SyntaxError("JSON nesting exceeds 128");
    }
    whitespace();
    if (text[position] === "\"") {
      return string();
    }
    if (text[position] === "[") {
      position += 1;
      const result = [];
      whitespace();
      if (text[position] === "]") {
        position += 1;
        return result;
      }
      while (true) {
        result.push(value(depth + 1));
        whitespace();
        if (text[position] === "]") {
          position += 1;
          return result;
        }
        if (text[position] !== ",") {
          throw new SyntaxError("invalid JSON array");
        }
        position += 1;
      }
    }
    if (text[position] === "{") {
      position += 1;
      const result = {};
      const names = new Set();
      whitespace();
      if (text[position] === "}") {
        position += 1;
        return result;
      }
      while (true) {
        whitespace();
        if (text[position] !== "\"") {
          throw new SyntaxError("object member must be a string");
        }
        const name = string();
        if (names.has(name)) {
          throw new SyntaxError("duplicate object member");
        }
        names.add(name);
        whitespace();
        if (text[position] !== ":") {
          throw new SyntaxError("object member requires a colon");
        }
        position += 1;
        result[name] = value(depth + 1);
        whitespace();
        if (text[position] === "}") {
          position += 1;
          return result;
        }
        if (text[position] !== ",") {
          throw new SyntaxError("invalid JSON object");
        }
        position += 1;
      }
    }
    return scalar();
  }

  const decoded = value(0);
  whitespace();
  if (position !== text.length) {
    throw new SyntaxError("trailing JSON content");
  }
  return decoded;
}

function validRequestId(value) {
  return typeof value === "string" && REQUEST_ID.test(value);
}

function recoverRequestId(value) {
  return isObject(value) && validRequestId(value.id) ? value.id : null;
}

function compareDecimal(left, right) {
  if (left.length !== right.length) {
    return left.length < right.length ? -1 : 1;
  }
  if (left === right) {
    return 0;
  }
  return left < right ? -1 : 1;
}

function compareVersions(left, right) {
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

function jsonRpcCode(ucfCode) {
  const standard = {
    parse_error: -32700,
    invalid_message: -32600,
    method_not_found: -32601,
    invalid_params: -32602,
    internal_error: -32603,
  };
  return standard[ucfCode] ?? -32000;
}

function categoryFor(ucfCode) {
  if (ucfCode === "request_cancelled") {
    return "cancelled";
  }
  if (ucfCode === "operation_failed" || ucfCode === "internal_error") {
    return "adapter_failure";
  }
  return "protocol_failure";
}

function write(message, close = false, exitCode = 0) {
  process.stdout.write(`${JSON.stringify(message)}\n`, () => {
    if (close) {
      process.exit(exitCode);
    }
  });
}

function writeError(id, ucfCode, message) {
  write({
    jsonrpc: "2.0",
    id,
    error: {
      code: jsonRpcCode(ucfCode),
      message,
      data: {
        category: categoryFor(ucfCode),
        ucf_code: ucfCode,
      },
    },
  });
}

function writeFaultyErrorCoordinates(id) {
  write({
    jsonrpc: "2.0",
    id,
    error: {
      code: -32000,
      message: "deliberately mismatched conformance coordinates",
      data: {
        category: "adapter_failure",
        ucf_code: "incompatible_version",
      },
    },
  });
}

function validProducer(value) {
  return hasExactKeys(value, ["kind", "name", "version"])
    && value.kind === "producer"
    && typeof value.name === "string"
    && value.name.length > 0
    && typeof value.version === "string"
    && NORMALIZED_VERSION.test(value.version);
}

function validCapabilityRequest(value) {
  return hasExactKeys(
    value,
    ["kind", "name", "minimum_version", "required"],
  )
    && value.kind === "capability_request"
    && typeof value.name === "string"
    && value.name.length > 0
    && typeof value.minimum_version === "string"
    && NORMALIZED_VERSION.test(value.minimum_version)
    && typeof value.required === "boolean";
}

function validateRequestEnvelope(message) {
  if (!hasExactKeys(message, ["jsonrpc", "id", "method", "params"])
      || message.jsonrpc !== "2.0"
      || !validRequestId(message.id)
      || typeof message.method !== "string"
      || !isObject(message.params)) {
    return false;
  }
  return true;
}

function initialize(message) {
  if (lifecycle !== "new") {
    writeError(message.id, "invalid_lifecycle", "initialize requires new state");
    return;
  }
  const params = message.params;
  if (!hasExactKeys(
    params,
    ["kind", "protocol_version", "client", "capabilities"],
  )
      || params.kind !== "initialize_request"
      || typeof params.protocol_version !== "string"
      || !NORMALIZED_VERSION.test(params.protocol_version)
      || !validProducer(params.client)
      || !Array.isArray(params.capabilities)
      || !params.capabilities.every(validCapabilityRequest)) {
    writeError(message.id, "invalid_params", "invalid initialize parameters");
    return;
  }
  if (params.protocol_version !== PROTOCOL_VERSION) {
    if (faultMode === "error-coordinates" && message.id === "incompatible") {
      writeFaultyErrorCoordinates(message.id);
      return;
    }
    writeError(
      message.id,
      "incompatible_version",
      "adapter protocol version is incompatible",
    );
    return;
  }
  const names = params.capabilities.map((capability) => capability.name);
  if (new Set(names).size !== names.length) {
    writeError(
      message.id,
      "duplicate_capability",
      "capability requests must be unique",
    );
    return;
  }

  const selections = [];
  for (const requested of params.capabilities) {
    const supportedVersion = SUPPORTED_CAPABILITIES.get(requested.name);
    const supported = supportedVersion !== undefined
      && compareVersions(requested.minimum_version, supportedVersion) <= 0;
    if (!supported && requested.required) {
      writeError(
        message.id,
        "unsupported_capability",
        "required capability is unavailable",
      );
      return;
    }
    if (supported) {
      selections.push({
        kind: "capability",
        name: requested.name,
        version: supportedVersion,
      });
    }
  }

  for (const selection of selections) {
    selectedCapabilities.add(selection.name);
  }
  const targetedFault = message.id === "initialize"
    && receivedMessageCount === 1
    && params.capabilities.length === 0;
  initializedByFirstBareRequest = targetedFault;
  lifecycle = "ready";
  if (targetedFault && faultMode === "response-timeout") {
    return;
  }
  const response = {
    jsonrpc: "2.0",
    id: message.id,
    result: {
      kind: "initialize_result",
      protocol_version: PROTOCOL_VERSION,
      adapter: {
        kind: "producer",
        name: ADAPTER_NAME,
        version: "1.0.0",
      },
      capabilities: selections,
    },
  };
  if (targetedFault && faultMode === "malformed-output") {
    response.forbidden_extra_field = true;
  }
  if (targetedFault && faultMode === "unknown-response-id") {
    response.id = "unknown-response";
  }
  write(response);
}

function recordEntries(value) {
  if (!hasExactKeys(value, ["kind", "entries"])
      || value.kind !== "record"
      || !Array.isArray(value.entries)) {
    return null;
  }
  const entries = new Map();
  for (const entry of value.entries) {
    if (!hasExactKeys(entry, ["kind", "name", "value"])
        || entry.kind !== "record_entry"
        || typeof entry.name !== "string"
        || entries.has(entry.name)
        || !isObject(entry.value)) {
      return null;
    }
    entries.set(entry.name, entry.value);
  }
  return entries;
}

function stringValue(value) {
  return hasExactKeys(value, ["kind", "value"]) && value.kind === "string"
    && typeof value.value === "string"
    ? value.value
    : null;
}

function parseControl(payload) {
  if (!hasExactKeys(
    payload,
    ["kind", "schema_uri", "schema_version", "value"],
  )
      || payload.kind !== "adapter_payload"
      || payload.schema_uri !== CONTROL_SCHEMA_URI
      || payload.schema_version !== CONTROL_SCHEMA_VERSION) {
    return null;
  }
  const entries = recordEntries(payload.value);
  if (entries === null) {
    return null;
  }
  const operation = stringValue(entries.get("operation"));
  if (operation === "echo"
      && entries.size === 2
      && entries.has("value")) {
    return {operation, value: entries.get("value")};
  }
  if (operation === "block" && entries.size === 1) {
    return {operation};
  }
  if (operation === "readiness"
      && entries.size === 2
      && entries.has("target_request_id")) {
    const targetRequestId = stringValue(entries.get("target_request_id"));
    if (targetRequestId !== null && validRequestId(targetRequestId)) {
      return {operation, targetRequestId};
    }
  }
  return null;
}

function operation(message) {
  if (lifecycle !== "ready") {
    writeError(message.id, "invalid_lifecycle", "operation requires ready state");
    return;
  }
  const capability = CAPABILITY_BY_METHOD.get(message.method);
  const deliberatelyAccept = faultMode === "accepts-unnegotiated"
    && message.id === "verify"
    && message.method === "ucf.verify";
  if (!selectedCapabilities.has(capability) && !deliberatelyAccept) {
    writeError(
      message.id,
      "capability_not_negotiated",
      "operation capability was not negotiated",
    );
    return;
  }
  const requestKind = `${message.method.slice("ucf.".length)}_request`;
  if (!hasExactKeys(message.params, ["kind", "payload"])
      || message.params.kind !== requestKind) {
    writeError(message.id, "invalid_params", "operation parameters do not match method");
    return;
  }
  const control = parseControl(message.params.payload);
  if (control === null) {
    writeError(
      message.id,
      "operation_failed",
      "unsupported conformance control payload",
    );
    return;
  }
  if (control.operation === "block") {
    active.set(message.id, message.method);
    return;
  }
  if (faultMode === "unsolicited-cancel" && message.id === "readiness") {
    writeError(
      message.id,
      "request_cancelled",
      "deliberately unsolicited cancellation",
    );
    return;
  }
  const resultEntries = control.operation === "readiness"
    ? [
        {
          kind: "record_entry",
          name: "operation",
          value: {kind: "string", value: "readiness_result"},
        },
        {
          kind: "record_entry",
          name: "target_request_id",
          value: {kind: "string", value: control.targetRequestId},
        },
        {
          kind: "record_entry",
          name: "active",
          value: {
            kind: "boolean",
            value: active.has(control.targetRequestId),
          },
        },
      ]
    : [
        {
          kind: "record_entry",
          name: "operation",
          value: {kind: "string", value: "echo_result"},
        },
        {kind: "record_entry", name: "value", value: control.value},
      ];
  const payload = {
    kind: "adapter_payload",
    schema_uri: CONTROL_SCHEMA_URI,
    schema_version: CONTROL_SCHEMA_VERSION,
    value: {
      kind: "record",
      entries: resultEntries,
    },
  };
  write({
    jsonrpc: "2.0",
    id: message.id,
    result: {
      kind: RESULT_KIND_BY_METHOD.get(message.method),
      payload,
    },
  });
}

function cancel(message) {
  if (!hasExactKeys(message, ["jsonrpc", "method", "params"])
      || message.jsonrpc !== "2.0"
      || message.method !== "ucf.cancel"
      || !hasExactKeys(message.params, ["kind", "request_id"])
      || message.params.kind !== "cancel_request"
      || !validRequestId(message.params.request_id)) {
    writeError(null, "invalid_message", "invalid cancellation notification");
    return;
  }
  const target = message.params.request_id;
  if (!active.has(target)) {
    return;
  }
  active.delete(target);
  writeError(target, "request_cancelled", "adapter request was cancelled");
}

function shutdown(message) {
  if (!hasExactKeys(message.params, ["kind"])
      || message.params.kind !== "shutdown_request") {
    writeError(message.id, "invalid_params", "invalid shutdown parameters");
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
  write({
    jsonrpc: "2.0",
    id: message.id,
    result: {kind: "shutdown_result"},
  }, true, faultMode === "shutdown-nonzero"
    && initializedByFirstBareRequest ? 17 : 0);
}

function handle(message) {
  receivedMessageCount += 1;
  if (!isObject(message)) {
    writeError(null, "invalid_message", "request root must be an object");
    return;
  }
  if (!Object.hasOwn(message, "id")) {
    if (message.method === "ucf.cancel") {
      cancel(message);
    } else {
      writeError(null, "invalid_message", "only ucf.cancel may be a notification");
    }
    return;
  }
  if (!validateRequestEnvelope(message)) {
    writeError(recoverRequestId(message), "invalid_message", "invalid request envelope");
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
  seenRequestIds.add(message.id);
  if (message.method === "ucf.initialize") {
    initialize(message);
    return;
  }
  if (message.method === "ucf.shutdown") {
    shutdown(message);
    return;
  }
  if (CAPABILITY_BY_METHOD.has(message.method)) {
    operation(message);
    return;
  }
  throw new Error("unreachable request method");
}

process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
  while (input.includes("\n")) {
    const delimiter = input.indexOf("\n");
    const frame = input.slice(0, delimiter);
    input = input.slice(delimiter + 1);
    if (frame.length === 0) {
      writeError(null, "invalid_message", "empty protocol frame");
      continue;
    }
    let message;
    try {
      message = parseStrictJson(frame);
    } catch {
      writeError(null, "parse_error", "invalid JSON input");
      continue;
    }
    handle(message);
  }
});
