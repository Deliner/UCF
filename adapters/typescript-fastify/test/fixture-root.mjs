import { lstatSync, realpathSync } from "node:fs";
import {
  isAbsolute,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";

const defaultFixtureRoot = fileURLToPath(
  new URL(
    "../../../tests/fixtures/brownfield/"
      + "typescript_fastify_legacy_quote/",
    import.meta.url,
  ),
);

export function typescriptFastifyFixtureRoot() {
  const configured = process.env.UCF_TYPESCRIPT_FASTIFY_FIXTURE_ROOT;
  const candidate = configured ?? defaultFixtureRoot;
  if (configured !== undefined && !isAbsolute(configured)) {
    throw new Error(
      "UCF_TYPESCRIPT_FASTIFY_FIXTURE_ROOT must be an absolute path",
    );
  }
  const absolute = resolve(candidate);
  const metadata = lstatSync(absolute);
  if (!metadata.isDirectory()) {
    throw new Error("TypeScript/Fastify fixture root must be a directory");
  }
  if (realpathSync(absolute) !== absolute) {
    throw new Error(
      "TypeScript/Fastify fixture root must not contain symlinks or aliases",
    );
  }
  return absolute;
}

export function typescriptFastifyFixtureRootPath(from = process.cwd()) {
  const relativePath = relative(resolve(from), typescriptFastifyFixtureRoot())
    .split(sep)
    .join("/");
  if (
    relativePath.length === 0
    || isAbsolute(relativePath)
    || relativePath.split("/").includes("")
  ) {
    throw new Error(
      "TypeScript/Fastify fixture must have one portable relative root path",
    );
  }
  return relativePath;
}
