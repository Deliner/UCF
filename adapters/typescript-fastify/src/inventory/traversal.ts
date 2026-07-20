import { createHash } from "node:crypto";
import {
  closeSync,
  constants,
  fstatSync,
  lstatSync,
  openSync,
  readSync,
  readdirSync,
  readlinkSync,
} from "node:fs";
import type { BigIntStats } from "node:fs";
import { join } from "node:path";

import type { JsonObject } from "../strict-json.js";

const HASH_CHUNK_BYTES = 65_536;
const MAX_CLASSIFICATION_BYTES = 1_048_576;
const MAX_DEPTH = 64;
const MAX_FILESYSTEM_ENTRIES = 20_000;
const MAX_FILE_BYTES = 268_435_456n;
const MAX_TOTAL_FILE_BYTES = 2_147_483_648n;
const MAX_PATH_BYTES = 1_024;
const pathDecoder = new TextDecoder("utf-8", { fatal: true });
const WINDOWS_RESERVED = new Set([
  "AUX",
  "CON",
  "NUL",
  "PRN",
  ...Array.from({ length: 9 }, (_, index) => `COM${index + 1}`),
  ...Array.from({ length: 9 }, (_, index) => `LPT${index + 1}`),
]);

export interface IgnoreRule {
  id: string;
  matcher:
    | { kind: "path_prefix"; path: string }
    | { kind: "path_segment"; segment: string };
}

export interface ScannedEntry {
  path: string;
  entryKind: "directory" | "file" | "symlink";
  sizeBytes: number | null;
  contentDigest: string | null;
  symlinkTargetDigest: string | null;
}

export interface ScannedIgnore {
  ruleId: string;
  path: string;
}

export interface ScanResult {
  entries: ScannedEntry[];
  ignores: ScannedIgnore[];
  filePrefixes: Map<string, Buffer>;
}

export class InventoryTraversalError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "InventoryTraversalError";
  }
}

export function scanRepository(
  rootPath: string,
  ignoreRules: readonly IgnoreRule[],
): ScanResult {
  try {
    const root = resolveRoot(rootPath);
    const rootStat = lstatSync(root, { bigint: true });
    if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) {
      throw new InventoryTraversalError(
        "inventory root is not a direct directory",
      );
    }
    const state: TraversalState = {
      entryCount: 1,
      totalFileBytes: 0n,
      portablePaths: new Set(["."]),
      entries: [
        {
          path: ".",
          entryKind: "directory",
          sizeBytes: null,
          contentDigest: null,
          symlinkTargetDigest: null,
        },
      ],
      ignores: [],
      filePrefixes: new Map(),
    };
    scanDirectory(root, ".", 0, rootStat, ignoreRules, state);
    return {
      entries: state.entries,
      ignores: state.ignores,
      filePrefixes: state.filePrefixes,
    };
  } catch (error: unknown) {
    if (error instanceof InventoryTraversalError) {
      throw error;
    }
    if (isFilesystemError(error)) {
      throw new InventoryTraversalError(
        "inventory source could not be read safely",
      );
    }
    throw error;
  }
}

interface TraversalState extends ScanResult {
  entryCount: number;
  totalFileBytes: bigint;
  portablePaths: Set<string>;
}

function scanDirectory(
  directory: string,
  parentPath: string,
  depth: number,
  before: BigIntStats,
  ignoreRules: readonly IgnoreRule[],
  state: TraversalState,
): void {
  if (depth > MAX_DEPTH) {
    throw new InventoryTraversalError("inventory depth limit was reached");
  }
  const encodedNames = readdirSync(directory, { encoding: "buffer" })
    .sort(Buffer.compare);
  for (const encodedName of encodedNames) {
    const name = decodePathName(encodedName);
    state.entryCount += 1;
    if (state.entryCount > MAX_FILESYSTEM_ENTRIES) {
      throw new InventoryTraversalError(
        "inventory entry limit was reached",
      );
    }
    const relative = parentPath === "." ? name : `${parentPath}/${name}`;
    if (!validName(name) || Buffer.byteLength(relative) > MAX_PATH_BYTES) {
      throw new InventoryTraversalError(
        "inventory encountered a non-portable path",
      );
    }
    const matching = matchingRuleIds(ignoreRules, relative);
    if (matching.length > 0) {
      state.ignores.push({ ruleId: matching[0] ?? "", path: relative });
      continue;
    }
    const portable = asciiCasefold(relative);
    if (state.portablePaths.has(portable)) {
      throw new InventoryTraversalError(
        "inventory encountered a path identity collision",
      );
    }
    state.portablePaths.add(portable);
    const absolute = join(directory, name);
    const entryBefore = lstatSync(absolute, { bigint: true });
    if (entryBefore.isSymbolicLink()) {
      scanSymlink(absolute, relative, entryBefore, state);
    } else if (entryBefore.isDirectory()) {
      state.entries.push({
        path: relative,
        entryKind: "directory",
        sizeBytes: null,
        contentDigest: null,
        symlinkTargetDigest: null,
      });
      scanDirectory(
        absolute,
        relative,
        depth + 1,
        entryBefore,
        ignoreRules,
        state,
      );
    } else if (entryBefore.isFile()) {
      scanFile(absolute, relative, entryBefore, state);
    } else {
      throw new InventoryTraversalError(
        "inventory encountered an unsupported entry type",
      );
    }
  }
  const after = lstatSync(directory, { bigint: true });
  if (!sameIdentity(before, after, true)) {
    throw new InventoryTraversalError(
      "inventory source changed during traversal",
    );
  }
}

function scanFile(
  absolute: string,
  relative: string,
  before: BigIntStats,
  state: TraversalState,
): void {
  if (before.size > MAX_FILE_BYTES) {
    throw new InventoryTraversalError("inventory file limit was reached");
  }
  state.totalFileBytes += before.size;
  if (state.totalFileBytes > MAX_TOTAL_FILE_BYTES) {
    throw new InventoryTraversalError(
      "inventory total byte limit was reached",
    );
  }
  const noFollow = constants.O_NOFOLLOW;
  const descriptor = openSync(absolute, constants.O_RDONLY | noFollow);
  let opened: BigIntStats;
  let afterOpen: BigIntStats;
  const digest = createHash("sha256");
  const chunks: Buffer[] = [];
  let prefixBytes = 0;
  let byteCount = 0;
  try {
    opened = fstatSync(descriptor, { bigint: true });
    if (!opened.isFile() || !sameIdentity(before, opened, false)) {
      throw new InventoryTraversalError(
        "inventory source changed before read",
      );
    }
    const buffer = Buffer.allocUnsafe(HASH_CHUNK_BYTES);
    while (true) {
      const count = readSync(
        descriptor,
        buffer,
        0,
        buffer.length,
        null,
      );
      if (count === 0) {
        break;
      }
      byteCount += count;
      if (BigInt(byteCount) > MAX_FILE_BYTES) {
        throw new InventoryTraversalError(
          "inventory file limit was reached",
        );
      }
      const chunk = buffer.subarray(0, count);
      digest.update(chunk);
      const remaining = MAX_CLASSIFICATION_BYTES - prefixBytes;
      if (remaining > 0) {
        const retained = Buffer.from(chunk.subarray(0, remaining));
        chunks.push(retained);
        prefixBytes += retained.length;
      }
    }
    afterOpen = fstatSync(descriptor, { bigint: true });
  } finally {
    closeSync(descriptor);
  }
  const afterPath = lstatSync(absolute, { bigint: true });
  if (
    BigInt(byteCount) !== opened.size
    || !sameIdentity(opened, afterOpen, false)
    || !sameIdentity(opened, afterPath, false)
  ) {
    throw new InventoryTraversalError(
      "inventory source changed during read",
    );
  }
  state.entries.push({
    path: relative,
    entryKind: "file",
    sizeBytes: byteCount,
    contentDigest: digest.digest("hex"),
    symlinkTargetDigest: null,
  });
  state.filePrefixes.set(relative, Buffer.concat(chunks));
}

function scanSymlink(
  absolute: string,
  relative: string,
  before: BigIntStats,
  state: TraversalState,
): void {
  const target = readlinkSync(absolute, { encoding: "buffer" });
  const after = lstatSync(absolute, { bigint: true });
  if (!sameIdentity(before, after, false)) {
    throw new InventoryTraversalError(
      "inventory symlink changed during read",
    );
  }
  state.entries.push({
    path: relative,
    entryKind: "symlink",
    sizeBytes: null,
    contentDigest: null,
    symlinkTargetDigest: createHash("sha256").update(target).digest("hex"),
  });
}

function resolveRoot(rootPath: string): string {
  if (rootPath === ".") {
    return process.cwd();
  }
  let resolved = process.cwd();
  const parts = rootPath.split("/");
  for (const [index, part] of parts.entries()) {
    resolved = join(resolved, part);
    const status = lstatSync(resolved, { bigint: true });
    if (status.isSymbolicLink()) {
      throw new InventoryTraversalError(
        "inventory root has a symbolic-link ancestor",
      );
    }
    if (index < parts.length - 1 && !status.isDirectory()) {
      throw new InventoryTraversalError(
        "inventory root ancestor is not a directory",
      );
    }
  }
  return resolved;
}

function sameIdentity(
  left: BigIntStats,
  right: BigIntStats,
  directory: boolean,
): boolean {
  return left.dev === right.dev
    && left.ino === right.ino
    && left.mode === right.mode
    && left.mtimeNs === right.mtimeNs
    && left.ctimeNs === right.ctimeNs
    && (directory || left.size === right.size);
}

function matchingRuleIds(
  rules: readonly IgnoreRule[],
  path: string,
): string[] {
  const parts = path.split("/");
  return rules
    .filter((rule) => rule.matcher.kind === "path_segment"
      ? parts.includes(rule.matcher.segment)
      : path === rule.matcher.path
        || path.startsWith(`${rule.matcher.path}/`))
    .map((rule) => rule.id)
    .sort();
}

function validName(name: string): boolean {
  const normalized = name.normalize("NFC");
  const basename = name.split(".", 1)[0]?.toUpperCase() ?? "";
  return name.length > 0
    && name !== "."
    && name !== ".."
    && normalized === name
    && Buffer.from(name, "utf8").toString("utf8") === name
    && Buffer.byteLength(name) <= 255
    && !/[\\/:<>"|?*\u0000-\u001f\u007f]/u.test(name)
    && !name.endsWith(" ")
    && !name.endsWith(".")
    && !WINDOWS_RESERVED.has(basename);
}

function decodePathName(value: Buffer): string {
  try {
    return pathDecoder.decode(value);
  } catch (error: unknown) {
    if (error instanceof TypeError) {
      throw new InventoryTraversalError(
        "inventory encountered a non-UTF-8 path",
      );
    }
    throw error;
  }
}

function isFilesystemError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error
    && typeof (error as NodeJS.ErrnoException).code === "string";
}

function asciiCasefold(value: string): string {
  return value.replace(/[A-Z]/g, (character) => character.toLowerCase());
}

export function logicalIgnoreRules(
  rules: readonly JsonObject[],
): IgnoreRule[] {
  return rules.map((rule) => {
    const matcher = rule["matcher"];
    if (typeof rule["id"] !== "string" || typeof matcher !== "object"
        || matcher === null || Array.isArray(matcher)) {
      throw new InventoryTraversalError("ignore rule is invalid");
    }
    if (
      matcher["kind"] === "path_segment"
      && typeof matcher["segment"] === "string"
    ) {
      return {
        id: rule["id"],
        matcher: {
          kind: "path_segment",
          segment: matcher["segment"],
        },
      };
    }
    if (
      matcher["kind"] === "path_prefix"
      && typeof matcher["path"] === "string"
    ) {
      return {
        id: rule["id"],
        matcher: {
          kind: "path_prefix",
          path: matcher["path"],
        },
      };
    }
    throw new InventoryTraversalError("ignore matcher is invalid");
  });
}
