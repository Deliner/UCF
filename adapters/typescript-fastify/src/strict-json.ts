export type JsonObject = { [name: string]: JsonValue };
export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | JsonObject;

const MAX_SAFE_INTEGER = 9_007_199_254_740_991;
const MAX_DEPTH = 128;

export function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function hasExactKeys(
  value: unknown,
  expected: readonly string[],
): value is JsonObject {
  if (!isObject(value)) {
    return false;
  }
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return actual.length === wanted.length
    && actual.every((key, index) => key === wanted[index]);
}

export function parseStrictJson(text: string): JsonValue {
  return new Parser(text).parse();
}

class Parser {
  private position = 0;

  public constructor(private readonly text: string) {}

  public parse(): JsonValue {
    if (this.text.startsWith("\uFEFF")) {
      throw new SyntaxError("UTF-8 BOM is not permitted");
    }
    const decoded = this.parseValue(0);
    this.skipWhitespace();
    if (this.position !== this.text.length) {
      throw new SyntaxError("trailing JSON content");
    }
    return decoded;
  }

  private parseValue(depth: number): JsonValue {
    if (depth > MAX_DEPTH) {
      throw new SyntaxError(`JSON nesting exceeds ${MAX_DEPTH}`);
    }
    this.skipWhitespace();
    const character = this.text[this.position];
    if (character === "\"") {
      return this.parseString();
    }
    if (character === "[") {
      return this.parseArray(depth);
    }
    if (character === "{") {
      return this.parseObject(depth);
    }
    return this.parseScalar();
  }

  private parseArray(depth: number): JsonValue[] {
    this.position += 1;
    const result: JsonValue[] = [];
    this.skipWhitespace();
    if (this.text[this.position] === "]") {
      this.position += 1;
      return result;
    }
    while (true) {
      result.push(this.parseValue(depth + 1));
      this.skipWhitespace();
      if (this.text[this.position] === "]") {
        this.position += 1;
        return result;
      }
      if (this.text[this.position] !== ",") {
        throw new SyntaxError("invalid JSON array");
      }
      this.position += 1;
    }
  }

  private parseObject(depth: number): JsonObject {
    this.position += 1;
    const result = Object.create(null) as JsonObject;
    const names = new Set<string>();
    this.skipWhitespace();
    if (this.text[this.position] === "}") {
      this.position += 1;
      return result;
    }
    while (true) {
      this.skipWhitespace();
      if (this.text[this.position] !== "\"") {
        throw new SyntaxError("object member must be a string");
      }
      const name = this.parseString();
      if (names.has(name)) {
        throw new SyntaxError("duplicate object member");
      }
      names.add(name);
      this.skipWhitespace();
      if (this.text[this.position] !== ":") {
        throw new SyntaxError("object member requires a colon");
      }
      this.position += 1;
      result[name] = this.parseValue(depth + 1);
      this.skipWhitespace();
      if (this.text[this.position] === "}") {
        this.position += 1;
        return result;
      }
      if (this.text[this.position] !== ",") {
        throw new SyntaxError("invalid JSON object");
      }
      this.position += 1;
    }
  }

  private parseString(): string {
    const start = this.position;
    this.position += 1;
    let escaped = false;
    while (this.position < this.text.length) {
      const character = this.text[this.position];
      this.position += 1;
      if (character === undefined) {
        break;
      }
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === "\"") {
        const decoded: unknown = JSON.parse(
          this.text.slice(start, this.position),
        );
        if (typeof decoded !== "string") {
          throw new SyntaxError("invalid JSON string");
        }
        return decoded;
      } else if (character < " ") {
        break;
      }
    }
    throw new SyntaxError("invalid JSON string");
  }

  private parseScalar(): null | boolean | number {
    const remainder = this.text.slice(this.position);
    for (const [token, value] of [
      ["true", true],
      ["false", false],
      ["null", null],
    ] as const) {
      if (remainder.startsWith(token)) {
        this.position += token.length;
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
    if (!Number.isSafeInteger(value) || Math.abs(value) > MAX_SAFE_INTEGER) {
      throw new SyntaxError("integer is outside the exact range");
    }
    this.position += token.length;
    return value;
  }

  private skipWhitespace(): void {
    while (
      this.position < this.text.length
      && " \t\n\r".includes(this.text[this.position] ?? "")
    ) {
      this.position += 1;
    }
  }
}
