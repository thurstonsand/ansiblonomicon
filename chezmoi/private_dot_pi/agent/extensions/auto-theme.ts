import { type FSWatcher, watch } from "node:fs";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

const themeFile = join(homedir(), ".terminal-bg");

type PiTheme = "gruvbox-dark-hard" | "gruvbox-light-hard";

async function readTheme(): Promise<PiTheme | null> {
  try {
    const value = (await readFile(themeFile, "utf8")).trim();
    return value === "light" ? "gruvbox-light-hard" : "gruvbox-dark-hard";
  } catch {
    return null;
  }
}

export default function (pi: ExtensionAPI) {
  let watcher: FSWatcher | null = null;

  pi.on("session_start", async (_event, ctx) => {
    const applyTheme = async (): Promise<PiTheme | null> => {
      const theme = await readTheme();
      const nextTheme = theme ?? "gruvbox-dark-hard";
      if (ctx.ui.theme.name !== nextTheme) {
        ctx.ui.setTheme(nextTheme);
      }
      return theme;
    };

    if ((await applyTheme()) === null) return;

    watcher = watch(themeFile, async () => {
      await applyTheme();
    });

    watcher.on("error", () => {
      watcher?.close();
      watcher = null;
    });
  });

  pi.on("session_shutdown", () => {
    watcher?.close();
    watcher = null;
  });
}
