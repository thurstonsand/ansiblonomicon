import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { fileNotification, pasteEditorText, runGhosttyPaste } from "./ghostty-nav.js";
import { loadSettings } from "./settings.js";

export default function piPasteFile(pi: ExtensionAPI): void {
  const settings = loadSettings();

  async function paste(ctx: ExtensionContext): Promise<void> {
    try {
      const result = await runGhosttyPaste(async (command, args) => {
        const execResult = await pi.exec(command, args, { timeout: 30_000 });
        return {
          stdout: execResult.stdout,
          stderr: execResult.stderr,
          code: execResult.code,
        };
      }, settings.outputDir);

      ctx.ui.pasteToEditor(pasteEditorText(result));
      const notification = fileNotification(result);
      if (notification) {
        ctx.ui.notify(notification, "info");
      }
    } catch (error) {
      ctx.ui.notify(`Paste failed: ${errorMessage(error)}`, "error");
    }
  }

  pi.registerShortcut(settings.shortcut, {
    description: "Paste clipboard text or files, even over ssh",
    handler: paste,
  });

  pi.registerCommand("paste", {
    description: "Paste clipboard text or files, even over ssh",
    handler: async (_args, ctx) => {
      await paste(ctx);
    },
  });
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
