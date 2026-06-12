import { readFileSync, realpathSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { extractRefs } from "./detect.js";

export interface LoadedReference {
  resolvedPath: string;
  ref: string;
  from: string;
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

/**
 * Walk the `@`-references found in each root file, loading every resolvable
 * target. Recurses into loaded files up to maxDepth, guarding against cycles
 * and re-loading files already present in the prompt via `preloaded`.
 */
export function collectReferences(
  roots: Array<{ path: string; content: string }>,
  preloaded: Array<{ path: string }>,
  maxDepth: number,
  ui: ReferenceNotifier,
): LoadedReference[] {
  const loaded: LoadedReference[] = [];
  const seen = new Set(preloaded.map((file) => canonicalize(file.path)));

  const walk = (fromPath: string, content: string, depth: number): void => {
    if (depth > maxDepth) return;
    const baseDir = path.dirname(fromPath);

    for (const ref of extractRefs(content)) {
      const resolvedPath = resolveRef(ref, baseDir);
      const canonical = canonicalize(resolvedPath);
      if (seen.has(canonical)) continue;
      seen.add(canonical);

      let fileContent: string;
      try {
        fileContent = readFileSync(resolvedPath, "utf-8");
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ui.notify(`Could not load @${ref} referenced from ${fromPath}: ${message}`, "error");
        continue;
      }

      loaded.push({ resolvedPath, ref, from: fromPath, content: fileContent });
      walk(resolvedPath, fileContent, depth + 1);
    }
  };

  for (const root of roots) {
    walk(root.path, root.content, 1);
  }

  return loaded;
}
