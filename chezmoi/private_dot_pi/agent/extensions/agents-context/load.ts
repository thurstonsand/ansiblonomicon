import { readdirSync, readFileSync, realpathSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { extractRefs, localCompanionBasename } from "./detect.js";

export type LoadedContextSource =
  | { type: "reference"; ref: string; from: string }
  | { type: "local"; from: string };

export interface LoadedContextFile {
  resolvedPath: string;
  source: LoadedContextSource;
  content: string;
}

export interface ReferenceNotifier {
  notify(message: string, type?: "info" | "warning" | "error"): void;
}

function canonicalize(filePath: string): string {
  try {
    return realpathSync(filePath);
  } catch {
    return path.resolve(filePath);
  }
}

function expandHome(value: string): string {
  if (value === "~") return os.homedir();
  if (value.startsWith("~/")) return path.join(os.homedir(), value.slice(2));
  return value;
}

function resolveRef(ref: string, baseDir: string): string {
  const expanded = expandHome(ref);
  return path.isAbsolute(expanded) ? expanded : path.resolve(baseDir, expanded);
}

function isMissingFile(error: unknown): boolean {
  return (
    error instanceof Error && "code" in error && (error as NodeJS.ErrnoException).code === "ENOENT"
  );
}

function findLocalCompanion(contextPath: string): string | undefined {
  const expectedBasename = localCompanionBasename(contextPath);
  if (!expectedBasename) return undefined;

  const directory = path.dirname(contextPath);
  const matchingBasenames = readdirSync(directory)
    .filter((basename) => basename.toUpperCase() === expectedBasename.toUpperCase())
    .sort((left, right) => {
      if (left === expectedBasename) return -1;
      if (right === expectedBasename) return 1;
      return left.localeCompare(right);
    });
  const basename = matchingBasenames[0];
  return basename ? path.join(directory, basename) : undefined;
}

/**
 * Walk the `@`-references found in each root context file and its optional
 * matching local companion. Recurses up to maxDepth, guarding against
 * cycles and files already present in the prompt via `preloaded`.
 */
export function collectContextFiles(
  roots: Array<{ path: string; content: string }>,
  preloaded: Array<{ path: string }>,
  maxDepth: number,
  ui: ReferenceNotifier,
): LoadedContextFile[] {
  const loaded: LoadedContextFile[] = [];
  const seen = new Set(preloaded.map((file) => canonicalize(file.path)));

  const load = (
    resolvedPath: string,
    source: LoadedContextSource,
    depth: number,
    optional: boolean,
  ): void => {
    if (depth > maxDepth) return;

    const canonical = canonicalize(resolvedPath);
    if (seen.has(canonical)) return;
    seen.add(canonical);

    let content: string;
    try {
      content = readFileSync(resolvedPath, "utf-8");
    } catch (error) {
      if (optional && isMissingFile(error)) return;
      const message = error instanceof Error ? error.message : String(error);
      const origin =
        source.type === "reference"
          ? `@${source.ref} referenced from ${source.from}`
          : `${resolvedPath} alongside ${source.from}`;
      ui.notify(`Could not load ${origin}: ${message}`, "error");
      return;
    }

    loaded.push({ resolvedPath, source, content });
    walk(resolvedPath, content, depth + 1);
  };

  const walk = (fromPath: string, content: string, depth: number): void => {
    if (depth > maxDepth) return;

    const companionPath = findLocalCompanion(fromPath);
    if (companionPath) {
      load(companionPath, { type: "local", from: fromPath }, depth, true);
    }

    const baseDir = path.dirname(fromPath);
    for (const ref of extractRefs(content)) {
      load(resolveRef(ref, baseDir), { type: "reference", ref, from: fromPath }, depth, false);
    }
  };

  for (const root of roots) {
    walk(root.path, root.content, 1);
  }

  return loaded;
}
