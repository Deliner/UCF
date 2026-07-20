import {
  type JsonObject,
  type JsonValue,
  hasExactKeys,
  isObject,
} from "./strict-json.js";

const IDENTIFIER = /^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/;
const DECIMAL =
  /^(?:0|[1-9][0-9]*|-[1-9][0-9]*|-?(?:0|[1-9][0-9]*)\.[0-9]*[1-9])$/;
const TIMESTAMP =
  /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$/;
const MAX_DEPTH = 128;

export class TaggedValueError extends Error {}

export function decodeTagged(
  value: JsonValue | undefined,
  depth = 0,
): JsonValue {
  return decodeTaggedValue(value, depth, false);
}

export function decodeProfileTagged(
  value: JsonValue | undefined,
  depth = 0,
): JsonValue {
  return decodeTaggedValue(value, depth, true);
}

function decodeTaggedValue(
  value: JsonValue | undefined,
  depth: number,
  requireSortedRecords: boolean,
): JsonValue {
  checkDepth(depth);
  if (!isObject(value)) {
    throw new TaggedValueError("tagged value must be an object");
  }
  const kind = value["kind"];
  if (kind === "null") {
    requireExact(value, ["kind"]);
    return null;
  }
  if (kind === "boolean") {
    requireExact(value, ["kind", "value"]);
    const decoded = value["value"];
    if (typeof decoded !== "boolean") {
      throw new TaggedValueError("boolean tagged value is invalid");
    }
    return decoded;
  }
  if (kind === "integer") {
    requireExact(value, ["kind", "value"]);
    const decoded = value["value"];
    if (typeof decoded !== "number" || !Number.isSafeInteger(decoded)) {
      throw new TaggedValueError("integer tagged value is invalid");
    }
    return decoded;
  }
  if (kind === "string") {
    requireExact(value, ["kind", "value"]);
    const decoded = value["value"];
    if (typeof decoded !== "string") {
      throw new TaggedValueError("string tagged value is invalid");
    }
    return decoded;
  }
  if (kind === "decimal") {
    requireExact(value, ["kind", "value"]);
    const decoded = value["value"];
    if (
      typeof decoded !== "string"
      || decoded === "-0"
      || !DECIMAL.test(decoded)
    ) {
      throw new TaggedValueError("decimal tagged value is invalid");
    }
    return decoded;
  }
  if (kind === "timestamp") {
    requireExact(value, ["kind", "value"]);
    const decoded = value["value"];
    if (typeof decoded !== "string" || !validTimestamp(decoded)) {
      throw new TaggedValueError("timestamp tagged value is invalid");
    }
    return decoded;
  }
  if (kind === "list") {
    requireExact(value, ["kind", "items"]);
    const items = value["items"];
    if (!Array.isArray(items)) {
      throw new TaggedValueError("list tagged value is invalid");
    }
    return items.map((item) =>
      decodeTaggedValue(item, depth + 1, requireSortedRecords));
  }
  if (kind === "record") {
    requireExact(value, ["kind", "entries"]);
    const entries = value["entries"];
    if (!Array.isArray(entries)) {
      throw new TaggedValueError("record tagged value is invalid");
    }
    const decoded = Object.create(null) as JsonObject;
    const names: string[] = [];
    for (const item of entries) {
      if (
        !hasExactKeys(item, ["kind", "name", "value"])
        || item["kind"] !== "record_entry"
        || typeof item["name"] !== "string"
        || !IDENTIFIER.test(item["name"])
        || Object.hasOwn(decoded, item["name"])
      ) {
        throw new TaggedValueError("record entry is invalid");
      }
      names.push(item["name"]);
      decoded[item["name"]] = decodeTaggedValue(
        item["value"],
        depth + 1,
        requireSortedRecords,
      );
    }
    if (
      requireSortedRecords
      && names.some((name, index) => name !== [...names].sort()[index])
    ) {
      throw new TaggedValueError("profile record entries are not sorted");
    }
    return decoded;
  }
  throw new TaggedValueError("tagged value kind is unsupported");
}

export function encodeTagged(value: JsonValue, depth = 0): JsonObject {
  checkDepth(depth);
  if (value === null) {
    return { kind: "null" };
  }
  if (typeof value === "boolean") {
    return { kind: "boolean", value };
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new TaggedValueError("integer is outside the exact profile");
    }
    return { kind: "integer", value };
  }
  if (typeof value === "string") {
    return { kind: "string", value };
  }
  if (Array.isArray(value)) {
    return {
      kind: "list",
      items: value.map((item) => encodeTagged(item, depth + 1)),
    };
  }
  const names = Object.keys(value).sort();
  if (names.some((name) => !IDENTIFIER.test(name))) {
    throw new TaggedValueError("record name is not an identifier");
  }
  return {
    kind: "record",
    entries: names.map((name) => ({
      kind: "record_entry",
      name,
      value: encodeTagged(value[name] ?? null, depth + 1),
    })),
  };
}

function requireExact(
  value: JsonObject,
  fields: readonly string[],
): void {
  if (!hasExactKeys(value, fields)) {
    throw new TaggedValueError("tagged value fields are not exact");
  }
}

function checkDepth(depth: number): void {
  if (depth > MAX_DEPTH) {
    throw new TaggedValueError("tagged value nesting exceeds the limit");
  }
}

function validTimestamp(value: string): boolean {
  const match = TIMESTAMP.exec(value);
  if (match === null) {
    return false;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  if (
    year < 1
    || month < 1
    || month > 12
    || day < 1
    || hour > 23
    || minute > 59
    || second > 59
  ) {
    return false;
  }
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(hour, minute, second, 0);
  return date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day
    && date.getUTCHours() === hour
    && date.getUTCMinutes() === minute
    && date.getUTCSeconds() === second;
}
