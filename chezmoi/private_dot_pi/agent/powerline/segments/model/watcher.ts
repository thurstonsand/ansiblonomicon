import { existsSync, readFileSync, watch } from "node:fs";
import path from "node:path";

function toFilePathList(filePaths: string | string[] | (() => string | string[])): string[] {
  const resolved = typeof filePaths === "function" ? filePaths() : filePaths;
  return Array.isArray(resolved) ? resolved : [resolved];
}

function readFileContents(filePath: string): string | undefined {
  try {
    if (!existsSync(filePath)) {
      return undefined;
    }

    return readFileSync(filePath, "utf8");
  } catch {
    return undefined;
  }
}

export function createFileWatcher(
  filePaths: string | string[] | (() => string | string[]),
  onChange: (contents: Map<string, string | undefined>) => void,
  debounceMs: number = 50,
): () => void {
  let started = false;
  let reloadTimer: ReturnType<typeof setTimeout> | null = null;

  function emitChange(): void {
    const contents = new Map<string, string | undefined>();
    for (const filePath of toFilePathList(filePaths)) {
      contents.set(filePath, readFileContents(filePath));
    }
    onChange(contents);
  }

  function scheduleReload(): void {
    if (reloadTimer) {
      clearTimeout(reloadTimer);
    }

    reloadTimer = setTimeout(() => {
      reloadTimer = null;
      emitChange();
    }, debounceMs);
  }

  return function ensureWatcher(): void {
    if (started) {
      return;
    }

    started = true;
    emitChange();

    const namesByDir = new Map<string, Set<string>>();
    for (const filePath of toFilePathList(filePaths)) {
      const dir = path.dirname(filePath);
      const fileName = path.basename(filePath);
      const names = namesByDir.get(dir) ?? new Set<string>();
      names.add(fileName);
      namesByDir.set(dir, names);
    }

    for (const [dir, fileNames] of namesByDir.entries()) {
      try {
        watch(dir, (_eventType, fileName) => {
          if (typeof fileName === "string" && !fileNames.has(fileName)) {
            return;
          }
          scheduleReload();
        });
      } catch {
        // Keep the last successfully loaded contents if watching is unavailable.
      }
    }
  };
}
