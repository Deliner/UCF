import type { JsonValue } from "./strict-json.js";

export function canonicalJson(value: JsonValue): string {
  return `${encode(value)}\n`;
}

function encode(value: JsonValue): string {
  if (value === null) {
    return "null";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new TypeError("canonical JSON accepts exact integers only");
    }
    return String(value);
  }
  if (typeof value === "string") {
    return encodeString(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(encode).join(",")}]`;
  }
  return `{${Object.keys(value)
    .sort()
    .map((name) => `${encodeString(name)}:${encode(value[name] ?? null)}`)
    .join(",")}}`;
}

function encodeString(value: string): string {
  let encoded = "\"";
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    switch (code) {
      case 0x08:
        encoded += "\\b";
        break;
      case 0x09:
        encoded += "\\t";
        break;
      case 0x0a:
        encoded += "\\n";
        break;
      case 0x0c:
        encoded += "\\f";
        break;
      case 0x0d:
        encoded += "\\r";
        break;
      case 0x22:
        encoded += "\\\"";
        break;
      case 0x5c:
        encoded += "\\\\";
        break;
      default:
        if (code < 0x20 || code > 0x7e) {
          encoded += `\\u${code.toString(16).padStart(4, "0")}`;
        } else {
          encoded += String.fromCharCode(code);
        }
    }
  }
  return `${encoded}\"`;
}
