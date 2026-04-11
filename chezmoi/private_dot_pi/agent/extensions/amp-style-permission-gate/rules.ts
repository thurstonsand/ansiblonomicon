import {
  type BashToolCallEvent,
  type EditToolCallEvent,
  type FindToolCallEvent,
  type GrepToolCallEvent,
  isToolCallEventType,
  type LsToolCallEvent,
  type ReadToolCallEvent,
  type ToolCallEvent,
  type WriteToolCallEvent,
} from "@mariozechner/pi-coding-agent";

export type BuiltInToolName =
  | BashToolCallEvent["toolName"]
  | ReadToolCallEvent["toolName"]
  | EditToolCallEvent["toolName"]
  | WriteToolCallEvent["toolName"]
  | GrepToolCallEvent["toolName"]
  | FindToolCallEvent["toolName"]
  | LsToolCallEvent["toolName"];

export const BASH_TOOL_NAME: BashToolCallEvent["toolName"] = "bash";

export type PermissionRule = {
  toolName: BuiltInToolName;
  label: string;
  matcher: RegExp | string;
  matches?: (text: string) => boolean;
};

function stripOuterQuotes(token: string): string {
  if (token.length < 2) return token;

  const first = token[0];
  const last = token[token.length - 1];

  return first === last && (first === '"' || first === "'") ? token.slice(1, -1) : token;
}

function tokenizeShellWords(command: string): string[] {
  return command.match(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\S+/g) ?? [];
}

export function isRecursiveForcedRemovalCommand(command: string): boolean {
  const segments = command.split(/&&|\|\||;|\n/);

  for (const segment of segments) {
    const tokens = tokenizeShellWords(segment).map(stripOuterQuotes);

    for (let index = 0; index < tokens.length; index++) {
      if (tokens[index] !== "rm") continue;

      let hasRecursive = false;
      let hasForce = false;

      for (let optionIndex = index + 1; optionIndex < tokens.length; optionIndex++) {
        const token = tokens[optionIndex];

        if (token === "--") break;
        if (!token.startsWith("-") || token === "-") break;

        if (token.startsWith("--")) {
          hasRecursive ||= token === "--recursive";
          hasForce ||= token === "--force";
          continue;
        }

        const flags = token.slice(1);
        hasRecursive ||= flags.includes("r");
        hasForce ||= flags.includes("f");
      }

      if (hasRecursive && hasForce) return true;
    }
  }

  return false;
}

export const PERMISSION_RULES: PermissionRule[] = [
  {
    toolName: BASH_TOOL_NAME,
    label: "git mutation",
    matcher: /\bgit\s+(\S+\s+)*?(stash|add|commit|push|checkout|reset|clean|rebase)\b/i,
  },
  {
    toolName: BASH_TOOL_NAME,
    label: "recursive forced removal",
    matcher: "rm with both recursive (-r/--recursive) and force (-f/--force) flags",
    matches: isRecursiveForcedRemovalCommand,
  },
  {
    toolName: BASH_TOOL_NAME,
    label: "destructive find",
    matcher: /find\s+.*(-delete|-exec|-execdir)/i,
  },
];

function getMatchableInput(
  event: ToolCallEvent,
): { toolName: BuiltInToolName; text: string } | undefined {
  if (isToolCallEventType(BASH_TOOL_NAME, event)) {
    return { toolName: BASH_TOOL_NAME, text: String(event.input.command ?? "") };
  }
  return undefined;
}

export function findMatchingRule(event: ToolCallEvent): PermissionRule | undefined {
  const input = getMatchableInput(event);
  if (!input) return undefined;

  return PERMISSION_RULES.find((rule) => {
    if (rule.toolName !== input.toolName) return false;
    if (rule.matches) return rule.matches(input.text);
    return rule.matcher instanceof RegExp && rule.matcher.test(input.text);
  });
}
