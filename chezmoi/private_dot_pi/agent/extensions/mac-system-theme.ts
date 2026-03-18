import { watch, type FSWatcher } from "node:fs";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

const themeFile = join(homedir(), ".terminal-bg");

type PiTheme = "gruvbox-dark-hard" | "gruvbox-light-hard";

async function readTheme(): Promise<PiTheme> {
  try {
    const value = (await readFile(themeFile, "utf8")).trim();
    return value === "light" ? "gruvbox-light-hard" : "gruvbox-dark-hard";
  } catch {
    return "gruvbox-dark-hard";
  }
}

export default function (pi: ExtensionAPI) {
  let watcher: FSWatcher | null = null;
  let currentTheme: PiTheme | null = null;

  pi.on("session_start", async (_event, ctx) => {
    const applyTheme = async () => {
      const nextTheme = await readTheme();
      if (nextTheme === currentTheme) return;
      currentTheme = nextTheme;
      ctx.ui.setTheme(nextTheme);
    };

    await applyTheme();

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
