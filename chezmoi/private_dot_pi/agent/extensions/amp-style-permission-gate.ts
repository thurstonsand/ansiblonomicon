import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

type BashRule = {
  label: string;
  pattern: RegExp;
};

// Mirrors the Bash ask-rules from Amp settings.
const ASK_RULES: BashRule[] = [
  {
    label: "git mutation",
    pattern: /\bgit\s+(\S+\s+)*?(stash|add|commit|push|checkout|reset|clean|rebase)\b/i,
  },
  {
    label: "recursive forced removal",
    pattern: /rm\s+.*(-[rf].*-[rf]|-[rf]{2,}|--recursive.*--force|--force.*--recursive)/i,
  },
  {
    label: "destructive find",
    pattern: /find\s+.*(-delete|-exec|-execdir)/i,
  },
];

function matchingRule(command: string): BashRule | undefined {
  return ASK_RULES.find((rule) => rule.pattern.test(command));
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;

    const command = String((event.input as { command?: unknown }).command ?? "");

    const rule = matchingRule(command);
    if (!rule) return undefined;

    if (!ctx.hasUI) {
      return {
        block: true,
        reason: `Blocked ${rule.label} command (confirmation unavailable)`,
      };
    }

    const allowed = await ctx.ui.confirm(
      "Permission check",
      `Matched policy: ${rule.label}\n\nAllow this bash command?\n\n${command}`,
    );

    if (!allowed) {
      return {
        block: true,
        reason: `Blocked by user (${rule.label})`,
      };
    }

    return undefined;
  });
}
