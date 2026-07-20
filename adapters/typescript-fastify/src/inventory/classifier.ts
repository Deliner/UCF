import { createHash } from "node:crypto";

import { canonicalJson } from "../canonical-json.js";
import {
  type JsonObject,
  type JsonValue,
  isObject,
  parseStrictJson,
} from "../strict-json.js";
import type { ScanResult } from "./traversal.js";

const decoder = new TextDecoder("utf-8", { fatal: true });
const MANIFEST_DIALECTS = new Map([
  [
    "package-lock.json",
    "urn:ucf:inventory-dialect:npm-lockfile-v3:1.0.0",
  ],
  [
    "package.json",
    "urn:ucf:inventory-dialect:npm-package-json:1.0.0",
  ],
  [
    "tsconfig.json",
    "urn:ucf:inventory-dialect:typescript-config:1.0.0",
  ],
]);
const EXPORTED_FUNCTION_URI =
  "urn:ucf:inventory-interface:typescript-exported-function:1.0.0";
const FASTIFY_ROUTE_URI =
  "urn:ucf:inventory-interface:fastify-literal-route:1.0.0";
const NODE_TEST_URI =
  "urn:ucf:inventory-test:node-test-call:1.0.0";

export interface SourceSpan {
  startLine: number;
  startColumn: number;
  endLine: number;
  endColumn: number;
}

export interface ClassifiedFact {
  kind: "build_manifest" | "public_interface" | "test_asset";
  path: string;
  span: SourceSpan;
  attributes: JsonObject;
}

export class InventoryClassificationError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "InventoryClassificationError";
  }
}

export function classifySupportedFixture(
  scan: ScanResult,
): ClassifiedFact[] {
  const packageText = fileText(scan, "package.json");
  const lockText = fileText(scan, "package-lock.json");
  const configText = fileText(scan, "tsconfig.json");
  validateManifestProfile(packageText, lockText, configText);

  const facts: ClassifiedFact[] = [];
  for (const [path, dialect] of MANIFEST_DIALECTS) {
    const text = fileText(scan, path);
    facts.push({
      kind: "build_manifest",
      path,
      span: fullDocumentSpan(text),
      attributes: { dialect_uri: dialect },
    });
  }

  const serviceText = fileText(scan, "src/service.ts");
  const serviceTokens = tokenize(serviceText);
  const functions = exportedFunctions(serviceTokens);
  const expectedFunctions = [
    "quoteOrder",
    "formatReceipt",
    "normalizeCoupon",
    "legacyDiscountHint",
    "buildApp",
  ];
  if (
    functions.length !== expectedFunctions.length
    || functions.some(
      (item, index) => item.name !== expectedFunctions[index],
    )
  ) {
    throw new InventoryClassificationError(
      "supported exported-function layout does not match",
    );
  }
  for (const declaration of functions) {
    facts.push({
      kind: "public_interface",
      path: "src/service.ts",
      span: declaration.span,
      attributes: {
        interface_kind_uri: EXPORTED_FUNCTION_URI,
        name: declaration.name,
        container: null,
        declaration_digest: digestObject(
          tokenProjection(
            serviceTokens.slice(
              declaration.startToken,
              declaration.endToken + 1,
            ),
          ),
        ),
      },
    });
  }
  const buildApp = functions.find((item) => item.name === "buildApp");
  if (buildApp === undefined) {
    throw new InventoryClassificationError("buildApp is unavailable");
  }
  const route = literalFastifyRoute(serviceTokens, buildApp);
  facts.push({
    kind: "public_interface",
    path: "src/service.ts",
    span: route.span,
    attributes: {
      interface_kind_uri: FASTIFY_ROUTE_URI,
      name: `POST ${route.path}`,
      container: "buildApp",
      declaration_digest: digestObject(
        tokenProjection(
          serviceTokens.slice(route.startToken, route.endToken + 1),
        ),
      ),
    },
  });

  const testText = fileText(scan, "src/service.test.ts");
  const testTokens = tokenize(testText);
  const tests = directNodeTests(testTokens);
  const expectedTests = [
    "real HTTP quote-order path returns the legacy quote result",
    "real HTTP quote-order path rejects zero quantity",
    "legacy business functions retain their standalone semantics",
  ];
  if (
    tests.length !== expectedTests.length
    || tests.some((item, index) => item.name !== expectedTests[index])
  ) {
    throw new InventoryClassificationError(
      "supported node:test layout does not match",
    );
  }
  for (const test of tests) {
    facts.push({
      kind: "test_asset",
      path: "src/service.test.ts",
      span: test.span,
      attributes: {
        test_kind_uri: NODE_TEST_URI,
        name: test.name,
      },
    });
  }
  return facts;
}

interface Token {
  kind: "identifier" | "number" | "punctuation" | "string";
  value: string;
  start: number;
  end: number;
  startLine: number;
  startColumn: number;
  endLine: number;
  endColumn: number;
}

interface Declaration {
  name: string;
  startToken: number;
  endToken: number;
  span: SourceSpan;
}

interface RouteDeclaration extends Declaration {
  path: string;
}

function fileText(scan: ScanResult, path: string): string {
  const content = scan.filePrefixes.get(path);
  const entry = scan.entries.find((item) => item.path === path);
  if (
    content === undefined
    || entry === undefined
    || entry.entryKind !== "file"
    || entry.sizeBytes !== content.length
  ) {
    throw new InventoryClassificationError(
      "supported fixture input is unavailable or exceeds the lexer bound",
    );
  }
  try {
    return decoder.decode(content);
  } catch (error: unknown) {
    if (error instanceof TypeError) {
      throw new InventoryClassificationError(
        "supported fixture input is not UTF-8",
      );
    }
    throw error;
  }
}

function validateManifestProfile(
  packageText: string,
  lockText: string,
  configText: string,
): void {
  const packageJson = parseObject(packageText);
  const dependencies = objectField(packageJson, "dependencies");
  const devDependencies = objectField(packageJson, "devDependencies");
  const engines = objectField(packageJson, "engines");
  if (
    dependencies["fastify"] !== "5.10.0"
    || devDependencies["@types/node"] !== "22.20.1"
    || devDependencies["typescript"] !== "7.0.2"
    || engines["node"] !== "22.x"
    || engines["npm"] !== "10.x"
    || packageJson["type"] !== "module"
  ) {
    throw new InventoryClassificationError(
      "package profile is unsupported",
    );
  }

  const lockJson = parseObject(lockText);
  const packages = objectField(lockJson, "packages");
  const lockRoot = objectField(packages, "");
  const lockDependencies = objectField(lockRoot, "dependencies");
  const lockDevDependencies = objectField(lockRoot, "devDependencies");
  if (
    lockJson["lockfileVersion"] !== 3
    || lockDependencies["fastify"] !== "5.10.0"
    || lockDevDependencies["@types/node"] !== "22.20.1"
    || lockDevDependencies["typescript"] !== "7.0.2"
  ) {
    throw new InventoryClassificationError(
      "npm lock profile is unsupported",
    );
  }

  const config = parseObject(configText);
  const options = objectField(config, "compilerOptions");
  if (
    options["module"] !== "NodeNext"
    || options["moduleResolution"] !== "NodeNext"
    || options["strict"] !== true
    || options["skipLibCheck"] !== false
    || options["noEmitOnError"] !== true
  ) {
    throw new InventoryClassificationError(
      "TypeScript compiler profile is unsupported",
    );
  }
}

function parseObject(text: string): JsonObject {
  let value: JsonValue;
  try {
    value = parseStrictJson(text);
  } catch (error: unknown) {
    if (error instanceof SyntaxError) {
      throw new InventoryClassificationError(
        "manifest JSON is invalid",
      );
    }
    throw error;
  }
  if (!isObject(value)) {
    throw new InventoryClassificationError(
      "manifest root is not an object",
    );
  }
  return value;
}

function objectField(value: JsonObject, name: string): JsonObject {
  const field = value[name];
  if (!isObject(field)) {
    throw new InventoryClassificationError(
      "manifest object field is unavailable",
    );
  }
  return field;
}

function fullDocumentSpan(text: string): SourceSpan {
  const end = text.trimEnd().length;
  const coordinate = positionAt(text, end);
  return {
    startLine: 1,
    startColumn: 1,
    endLine: coordinate.line,
    endColumn: coordinate.column,
  };
}

function exportedFunctions(tokens: readonly Token[]): Declaration[] {
  const declarations: Declaration[] = [];
  let braceDepth = 0;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === undefined) {
      break;
    }
    if (
      braceDepth === 0
      && token.value === "export"
      && tokens[index + 1]?.value === "function"
      && tokens[index + 2]?.kind === "identifier"
    ) {
      const bodyStart = findToken(tokens, index + 3, "{");
      const bodyEnd = matchingToken(tokens, bodyStart, "{", "}");
      const name = tokens[index + 2]?.value;
      if (name === undefined) {
        throw new InventoryClassificationError(
          "exported function name is unavailable",
        );
      }
      declarations.push({
        name,
        startToken: index,
        endToken: bodyEnd,
        span: span(tokens[index], tokens[bodyEnd]),
      });
      index = bodyEnd;
      continue;
    }
    if (token.value === "{") {
      braceDepth += 1;
    } else if (token.value === "}") {
      braceDepth -= 1;
      if (braceDepth < 0) {
        throw new InventoryClassificationError(
          "TypeScript braces are unbalanced",
        );
      }
    }
  }
  if (braceDepth !== 0) {
    throw new InventoryClassificationError(
      "TypeScript braces are unbalanced",
    );
  }
  return declarations;
}

function literalFastifyRoute(
  tokens: readonly Token[],
  buildApp: Declaration,
): RouteDeclaration {
  const body = tokens.slice(buildApp.startToken, buildApp.endToken + 1);
  const hasDirectApp = body.some((token, index) =>
    token.value === "const"
    && body[index + 1]?.value === "app"
    && body[index + 2]?.value === "="
    && body[index + 3]?.value === "Fastify"
    && body[index + 4]?.value === "(");
  if (!hasDirectApp) {
    throw new InventoryClassificationError(
      "direct Fastify construction is unavailable",
    );
  }
  const matches: RouteDeclaration[] = [];
  for (
    let index = buildApp.startToken;
    index <= buildApp.endToken;
    index += 1
  ) {
    if (
      tokens[index]?.value !== "app"
      || tokens[index + 1]?.value !== "."
      || tokens[index + 2]?.value !== "post"
    ) {
      continue;
    }
    let callStart = index + 3;
    if (tokens[callStart]?.value === "<") {
      callStart = matchingToken(tokens, callStart, "<", ">") + 1;
    }
    if (
      tokens[callStart]?.value !== "("
      || tokens[callStart + 1]?.kind !== "string"
    ) {
      throw new InventoryClassificationError(
        "Fastify route path is not a direct literal",
      );
    }
    const callEnd = matchingToken(tokens, callStart, "(", ")");
    const endToken = tokens[callEnd + 1]?.value === ";"
      ? callEnd + 1
      : callEnd;
    const path = tokens[callStart + 1]?.value;
    if (path === undefined || !path.startsWith("/")) {
      throw new InventoryClassificationError(
        "Fastify route path is invalid",
      );
    }
    matches.push({
      name: `POST ${path}`,
      path,
      startToken: index,
      endToken,
      span: span(tokens[index], tokens[endToken]),
    });
    index = endToken;
  }
  if (matches.length !== 1 || matches[0]?.path !== "/quote-order") {
    throw new InventoryClassificationError(
      "supported Fastify route layout does not match",
    );
  }
  return matches[0];
}

function directNodeTests(tokens: readonly Token[]): Declaration[] {
  const declarations: Declaration[] = [];
  let braceDepth = 0;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === undefined) {
      break;
    }
    if (
      braceDepth === 0
      && token.value === "test"
      && tokens[index + 1]?.value === "("
      && tokens[index + 2]?.kind === "string"
    ) {
      const callEnd = matchingToken(tokens, index + 1, "(", ")");
      const endToken = tokens[callEnd + 1]?.value === ";"
        ? callEnd + 1
        : callEnd;
      const name = tokens[index + 2]?.value;
      if (name === undefined) {
        throw new InventoryClassificationError(
          "node:test name is unavailable",
        );
      }
      declarations.push({
        name,
        startToken: index,
        endToken,
        span: span(token, tokens[endToken]),
      });
      index = endToken;
      continue;
    }
    if (token.value === "{") {
      braceDepth += 1;
    } else if (token.value === "}") {
      braceDepth -= 1;
    }
  }
  if (braceDepth !== 0) {
    throw new InventoryClassificationError(
      "test source braces are unbalanced",
    );
  }
  return declarations;
}

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  let index = 0;
  while (index < text.length) {
    const character = text[index];
    if (character === undefined) {
      break;
    }
    if (/\s/u.test(character)) {
      index += 1;
      continue;
    }
    if (text.startsWith("//", index)) {
      const end = text.indexOf("\n", index + 2);
      index = end < 0 ? text.length : end + 1;
      continue;
    }
    if (text.startsWith("/*", index)) {
      const end = text.indexOf("*/", index + 2);
      if (end < 0) {
        throw new InventoryClassificationError(
          "TypeScript block comment is unterminated",
        );
      }
      index = end + 2;
      continue;
    }
    const start = index;
    let kind: Token["kind"];
    let value: string;
    if (/[A-Za-z_$]/u.test(character)) {
      index += 1;
      while (/[A-Za-z0-9_$]/u.test(text[index] ?? "")) {
        index += 1;
      }
      kind = "identifier";
      value = text.slice(start, index);
    } else if (/[0-9]/u.test(character)) {
      index += 1;
      while (/[A-Za-z0-9._]/u.test(text[index] ?? "")) {
        index += 1;
      }
      kind = "number";
      value = text.slice(start, index);
    } else if (character === "\"" || character === "'"
        || character === "`") {
      index = scanString(text, index, character);
      kind = "string";
      value = decodeStringToken(text.slice(start, index), character);
    } else {
      const operator = [
        "===",
        "!==",
        "=>",
        "<=",
        ">=",
        "==",
        "!=",
        "&&",
        "||",
        "??",
        "?.",
      ].find((candidate) => text.startsWith(candidate, index));
      value = operator ?? character;
      index += value.length;
      kind = "punctuation";
    }
    const startCoordinate = positionAt(text, start);
    const endCoordinate = positionAt(text, index);
    tokens.push({
      kind,
      value,
      start,
      end: index,
      startLine: startCoordinate.line,
      startColumn: startCoordinate.column,
      endLine: endCoordinate.line,
      endColumn: endCoordinate.column,
    });
  }
  return tokens;
}

function scanString(text: string, start: number, quote: string): number {
  let index = start + 1;
  while (index < text.length) {
    const character = text[index];
    if (character === "\\") {
      index += 2;
      continue;
    }
    if (character === quote) {
      return index + 1;
    }
    if (
      quote !== "`"
      && (character === "\n" || character === "\r")
    ) {
      break;
    }
    index += 1;
  }
  throw new InventoryClassificationError(
    "TypeScript string is unterminated",
  );
}

function decodeStringToken(raw: string, quote: string): string {
  if (quote === "\"") {
    const decoded: unknown = JSON.parse(raw);
    if (typeof decoded !== "string") {
      throw new InventoryClassificationError(
        "TypeScript string is invalid",
      );
    }
    return decoded;
  }
  return raw;
}

function findToken(
  tokens: readonly Token[],
  start: number,
  value: string,
): number {
  const index = tokens.findIndex(
    (token, tokenIndex) => tokenIndex >= start && token.value === value,
  );
  if (index < 0) {
    throw new InventoryClassificationError(
      "required TypeScript delimiter is unavailable",
    );
  }
  return index;
}

function matchingToken(
  tokens: readonly Token[],
  start: number,
  open: string,
  close: string,
): number {
  if (tokens[start]?.value !== open) {
    throw new InventoryClassificationError(
      "TypeScript delimiter start does not match",
    );
  }
  let depth = 0;
  for (let index = start; index < tokens.length; index += 1) {
    if (tokens[index]?.value === open) {
      depth += 1;
    } else if (tokens[index]?.value === close) {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }
  throw new InventoryClassificationError(
    "TypeScript delimiters are unbalanced",
  );
}

function span(
  first: Token | undefined,
  last: Token | undefined,
): SourceSpan {
  if (first === undefined || last === undefined) {
    throw new InventoryClassificationError(
      "source span token is unavailable",
    );
  }
  return {
    startLine: first.startLine,
    startColumn: first.startColumn,
    endLine: last.endLine,
    endColumn: last.endColumn,
  };
}

function positionAt(
  text: string,
  offset: number,
): { line: number; column: number } {
  let line = 1;
  let column = 1;
  for (let index = 0; index < offset; index += 1) {
    if (text[index] === "\n") {
      line += 1;
      column = 1;
    } else {
      column += 1;
    }
  }
  return { line, column };
}

function tokenProjection(tokens: readonly Token[]): JsonObject {
  return {
    kind: "typescript_token_projection",
    version: "1.0.0",
    tokens: tokens.map((token) => ({
      kind: token.kind,
      value: token.value,
    })),
  };
}

function digestObject(value: JsonValue): JsonObject {
  return {
    kind: "digest",
    algorithm: "sha-256",
    value: createHash("sha256").update(canonicalJson(value)).digest("hex"),
  };
}
