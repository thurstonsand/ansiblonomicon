import { execFileSync } from "node:child_process";
import {
  block,
  gitValueFlags,
  type HighlightSpan,
  isCustomToolInput,
  matchCommand,
  matchTool,
  type PermissionsAPI,
  type PermissionToolInput,
  request,
  type SimpleCommand,
} from "@thurstonsand/pi-permissions";

const GIT_MUTATION_SUBCOMMANDS = [
  "stash",
  "add",
  "commit",
  "push",
  "pull",
  "checkout",
  "switch",
  "restore",
  "reset",
  "clean",
  "rebase",
  "merge",
  "cherry-pick",
  "revert",
  "rm",
  "mv",
  "branch",
  "tag",
  "worktree",
  "submodule",
] as const;
const SQL_DATA_MUTATION_PATTERN =
  /\b(?:insert|update|delete|merge|truncate|vacuum|reindex|cluster)\b/i;
const SQL_ANALYZE_PATTERN = /(?<!\bexplain\s+)\banalyze\b/i;
const SQL_COPY_FROM_PATTERN = /\\?\bcopy\b[\s\S]*?\bfrom\b/i;
const SQL_DDL_PATTERN = /\b(?:create|alter|drop|rename)\b/i;
const SQL_DCL_PATTERN = /\b(?:grant|revoke)\b/i;
const SQL_MUTATION_HIGHLIGHTS = [
  SQL_DATA_MUTATION_PATTERN,
  SQL_ANALYZE_PATTERN,
  SQL_COPY_FROM_PATTERN,
  SQL_DDL_PATTERN,
  SQL_DCL_PATTERN,
] as const;
const WORK_WEB_SEARCH_TOOL = "web_search_web_search";

export default function permissions(api: PermissionsAPI): void {
  api.onToolUse({
    name: "Git interference",
    description: "tampering with repository state or history",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: matchCommand({
          program: "git",
          subcommands: GIT_MUTATION_SUBCOMMANDS,
          valueFlags: gitValueFlags,
          where: allowReadOnly(isReadOnlyAction, isReadOnlyListing, isReadOnlyClean),
          onMatch: ({ commands }) => {
            if (isSubagent()) {
              return block("Subagents may not alter Git state or history.");
            }
            return request({
              highlight: commands.map((command) => command.span),
              approveLabel: "Tamper",
              editLabel: "Amend",
              rejectLabel: "Deny",
            });
          },
        }),
      }),
  });

  api.onToolUse({
    name: "File disposal",
    description: "files targeted for elimination",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) => {
          if (!isRecursiveForcedRemovalCommand(command) && !isFindDeleteCommand(command)) {
            return undefined;
          }
          if (isSubagent()) {
            return undefined;
          }
          return request({
            highlight: fileDisposalSpans,
            approveLabel: "Dispose",
            editLabel: "Retarget",
            rejectLabel: "Prevent",
          });
        },
      }),
  });

  api.onToolUse({
    name: "Database integrity",
    description: "state mutation of data, schema, or privileges",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) => {
          if (!isPostgresMutation(command)) {
            return undefined;
          }
          if (isSubagent()) {
            return block("Subagents may not mutate databases.");
          }
          return request({
            highlight: SQL_MUTATION_HIGHLIGHTS,
            approveLabel: "Mutate",
            editLabel: "Reword",
            rejectLabel: "Deny",
          });
        },
      }),
  });

  api.onToolUse({
    name: "Reconnaissance",
    description: "web search beyond local operational boundaries",
    handler: ({ tool }) =>
      matchTool(tool, {
        custom: {
          mcp: (tool) => requestWebSearch(webSearchTarget(tool)),
        },
        default: (tool) => requestWebSearch(tool.toolName),
      }),
  });
}

interface ReadOnlyActionRule {
  actions: ReadonlySet<string>;
  allowBare?: boolean;
}

const READ_ONLY_ACTION_SUBCOMMANDS: Record<string, ReadOnlyActionRule> = {
  stash: { actions: new Set(["list", "show"]) },
  worktree: { actions: new Set(["list"]) },
  submodule: { actions: new Set(["status", "summary"]), allowBare: true },
};

const LISTING_MUTATING_FLAGS: Record<string, readonly string[]> = {
  branch: [
    "-d",
    "-D",
    "--delete",
    "-m",
    "-M",
    "--move",
    "-c",
    "-C",
    "--copy",
    "-f",
    "--force",
    "-u",
    "--set-upstream-to",
    "--unset-upstream",
    "--edit-description",
  ],
  tag: [
    "-d",
    "--delete",
    "-f",
    "--force",
    "-a",
    "--annotate",
    "-s",
    "--sign",
    "-m",
    "--message",
    "-F",
    "--file",
  ],
};

function allowReadOnly(
  ...predicates: readonly ((command: SimpleCommand) => boolean)[]
): (command: SimpleCommand) => boolean {
  return (command) => !predicates.some((predicate) => predicate(command));
}

function gitPositionals(command: SimpleCommand): readonly string[] {
  return command.positionals({ valueFlags: gitValueFlags }).map((token) => token.text);
}

function isReadOnlyAction(command: SimpleCommand): boolean {
  const [subcommand, action] = gitPositionals(command);
  if (subcommand === undefined) return false;

  const rule = READ_ONLY_ACTION_SUBCOMMANDS[subcommand];
  if (!rule) return false;

  return action === undefined ? rule.allowBare === true : rule.actions.has(action);
}

function isReadOnlyListing(command: SimpleCommand): boolean {
  const positionals = gitPositionals(command);
  const subcommand = positionals[0];
  if (subcommand === undefined) return false;

  const mutatingFlags = LISTING_MUTATING_FLAGS[subcommand];
  if (!mutatingFlags) return false;

  return positionals.length === 1 && !command.hasFlag(...mutatingFlags);
}

function isReadOnlyClean(command: SimpleCommand): boolean {
  return gitPositionals(command)[0] === "clean" && command.hasFlag("-n", "--dry-run");
}

let subagentDetected: boolean | undefined;

function isSubagent(): boolean {
  if (subagentDetected !== undefined) return subagentDetected;

  const tmuxPane = process.env.TMUX_PANE;
  if (!tmuxPane) {
    subagentDetected = false;
    return subagentDetected;
  }

  try {
    // Temporary integration hack: pi-sessions identifies managed subagents with a window stamp.
    subagentDetected = Boolean(
      execFileSync("tmux", ["show-options", "-wqv", "-t", tmuxPane, "@pi_session_id"], {
        encoding: "utf8",
      }).trim(),
    );
  } catch {
    subagentDetected = false;
  }

  return subagentDetected;
}

function isFindDeleteCommand(command: string): boolean {
  return /find\s+.*-delete/i.test(command);
}

function fileDisposalSpans(command: string): HighlightSpan[] {
  return [...recursiveForcedRemovalSpans(command), ...findDeleteSpans(command)];
}

function recursiveForcedRemovalSpans(command: string): HighlightSpan[] {
  const spans: HighlightSpan[] = [];

  for (const segment of shellSegments(command)) {
    const tokens = tokenizeShellWordsWithSpans(segment.text, segment.start);

    for (let index = 0; index < tokens.length; index++) {
      if (tokens[index]?.text !== "rm") continue;

      let hasRecursive = false;
      let hasForce = false;
      let end = tokens[index]?.end ?? segment.start;

      for (let optionIndex = index + 1; optionIndex < tokens.length; optionIndex++) {
        const token = tokens[optionIndex];
        if (!token) continue;

        if (token.text === "--") break;
        if (!token.text.startsWith("-") || token.text === "-") break;

        if (token.text.startsWith("--")) {
          hasRecursive ||= token.text === "--recursive";
          hasForce ||= token.text === "--force";
        } else {
          const flags = token.text.slice(1);
          hasRecursive ||= flags.includes("r");
          hasForce ||= flags.includes("f");
        }

        end = token.end;
      }

      if (hasRecursive && hasForce && tokens[index]) {
        spans.push({ start: tokens[index].start, end });
      }
    }
  }

  return spans;
}

function findDeleteSpans(command: string): HighlightSpan[] {
  return [...command.matchAll(/find\s+.*?-delete\b/gi)].map((match) => ({
    start: match.index ?? 0,
    end: (match.index ?? 0) + match[0].length,
  }));
}

function stripOuterQuotes(token: string): string {
  if (token.length < 2) return token;

  const first = token[0];
  const last = token[token.length - 1];

  return first === last && (first === '"' || first === "'") ? token.slice(1, -1) : token;
}

interface ShellToken {
  text: string;
  start: number;
  end: number;
}

interface ShellSegment {
  text: string;
  start: number;
}

function tokenizeShellWords(command: string): string[] {
  return tokenizeShellWordsWithSpans(command).map((token) => token.text);
}

function tokenizeShellWordsWithSpans(command: string, offset = 0): ShellToken[] {
  return [...command.matchAll(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\S+/g)].map((match) => ({
    text: stripOuterQuotes(match[0]),
    start: offset + (match.index ?? 0),
    end: offset + (match.index ?? 0) + match[0].length,
  }));
}

function shellSegments(command: string): ShellSegment[] {
  const segments: ShellSegment[] = [];
  let start = 0;

  for (const match of command.matchAll(/&&|\|\||;|\n/g)) {
    const end = match.index ?? 0;
    segments.push({ text: command.slice(start, end), start });
    start = end + match[0].length;
  }

  segments.push({ text: command.slice(start), start });
  return segments;
}

function isRecursiveForcedRemovalCommand(command: string): boolean {
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

function isPostgresMutation(command: string): boolean {
  return isPsqlInvocation(command) && isPostgresMutationStatement(command);
}

function isPsqlInvocation(command: string): boolean {
  return tokenizeShellWords(command)
    .map(stripOuterQuotes)
    .some((token) => token === "psql" || token.endsWith("/psql"));
}

function isPostgresMutationStatement(command: string): boolean {
  return (
    SQL_DATA_MUTATION_PATTERN.test(command) ||
    SQL_ANALYZE_PATTERN.test(command) ||
    SQL_COPY_FROM_PATTERN.test(command) ||
    SQL_DDL_PATTERN.test(command) ||
    SQL_DCL_PATTERN.test(command)
  );
}

function requestWebSearch(target: string | undefined) {
  if (target !== WORK_WEB_SEARCH_TOOL || isSubagent()) {
    return undefined;
  }
  return request({ approveLabel: "Commence", rejectLabel: "Reconsider" });
}

function webSearchTarget(tool: PermissionToolInput): string | undefined {
  return isCustomToolInput(tool, "mcp") && typeof tool.input.tool === "string"
    ? tool.input.tool
    : undefined;
}
