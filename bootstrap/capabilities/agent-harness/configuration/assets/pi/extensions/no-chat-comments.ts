import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { type ExtensionAPI, isToolCallEventType } from "@earendil-works/pi-coding-agent";

const pattern =
  /^\s*(?:\/\/|#|\/\*|\*|<!--).*\b(?:changed from|used to be|previously (?:this|it)|as (?:you )?requested)\b/i;

export default function noChatComments(pi: ExtensionAPI): void {
  pi.on("tool_call", async (event, ctx) => {
    let lines: string[];
    if (isToolCallEventType("edit", event)) {
      lines = event.input.edits.flatMap((edit) => {
        const previous = new Set(edit.oldText.split(/\r?\n/));
        return edit.newText.split(/\r?\n/).filter((line) => !previous.has(line));
      });
    } else if (isToolCallEventType("write", event)) {
      let before: string;
      try {
        before = await readFile(resolve(ctx.cwd, event.input.path), "utf8");
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
        before = "";
      }
      const previous = new Set(before.split(/\r?\n/));
      lines = event.input.content.split(/\r?\n/).filter((line) => !previous.has(line));
    } else {
      return;
    }
    if (lines.some((line) => pattern.test(line))) {
      return {
        block: true,
        reason:
          "Write comments for the code, not the chat. Explain current behavior and rationale; remove conversation or edit-history narration from the new comment.",
      };
    }
  });
}
