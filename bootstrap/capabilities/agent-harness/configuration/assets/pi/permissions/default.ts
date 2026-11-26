import { execFileSync } from "node:child_process";
import {
  block,
  gitValueFlags,
  matchCommand,
  matchTool,
  type PermissionsAPI,
  request,
  type SimpleCommand,
} from "@thurstonsand/pi-permissions";

const GIT_GATED_SUBCOMMANDS = [
  "commit",
  "merge",
  "rebase",
  "cherry-pick",
  "revert",
  "am",
  // Plumbing that writes commits or moves refs without going through `commit`.
  "commit-tree",
  "update-ref",
  "push",
  "reset",
  "clean",
  "restore",
  "checkout",
  "switch",
  "rm",
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
const WORK_WEB_SEARCH_TOOL = "mcp__web_search__web_search";

export default function permissions(api: PermissionsAPI): void {
  api.onToolUse({
    name: "Git interference",
    description: "committing history, modifying remotes, or discarding uncommitted work",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: matchCommand({
          program: "git",
          subcommands: GIT_GATED_SUBCOMMANDS,
          valueFlags: gitValueFlags,
          where: isGatedGitCommand,
          onMatch: ({ commands }) => {
            if (isSubagent()) {
              return undefined;
            }
            return request({
              highlight: commands.map((command) => command.span),
              approveLabel: "Tamper",
              rejectLabel: "Deny",
            });
          },
        }),
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
          [WORK_WEB_SEARCH_TOOL]: requestWebSearch,
        },
      }),
  });
}

type GitGatedSubcommand = (typeof GIT_GATED_SUBCOMMANDS)[number];

const DISCARDS_UNCOMMITTED_WORK: Partial<
  Record<GitGatedSubcommand, (command: SimpleCommand) => boolean>
> = {
  reset: (command) => command.hasFlag("--hard"),
  clean: (command) => !command.hasFlag("-n", "--dry-run"),
  restore: (command) => !command.hasFlag("-S", "--staged") || command.hasFlag("-W", "--worktree"),
  checkout: (command) => command.hasFlag("-f", "--force") || checksOutPaths(command),
  switch: (command) => command.hasFlag("-f", "--force", "--discard-changes"),
  rm: (command) => command.hasFlag("-f", "--force"),
};

function isGatedGitCommand(command: SimpleCommand): boolean {
  const subcommand = gitPositionals(command)[0] as GitGatedSubcommand;
  const discardsWork = DISCARDS_UNCOMMITTED_WORK[subcommand];
  return discardsWork ? discardsWork(command) : true;
}

function checksOutPaths(command: SimpleCommand): boolean {
  return (
    command.args.some((token) => token.text === "--") ||
    gitPositionals(command).slice(1).includes(".")
  );
}

function gitPositionals(command: SimpleCommand): readonly string[] {
  return command.positionals({ valueFlags: gitValueFlags }).map((token) => token.text);
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

function stripOuterQuotes(token: string): string {
  if (token.length < 2) return token;

  const first = token[0];
  const last = token[token.length - 1];

  return first === last && (first === '"' || first === "'") ? token.slice(1, -1) : token;
}

function tokenizeShellWords(command: string): string[] {
  return [...command.matchAll(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\S+/g)].map((match) =>
    stripOuterQuotes(match[0]),
  );
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

function requestWebSearch() {
  if (isSubagent()) {
    return undefined;
  }
  return request({ approveLabel: "Commence", rejectLabel: "Reconsider" });
}
