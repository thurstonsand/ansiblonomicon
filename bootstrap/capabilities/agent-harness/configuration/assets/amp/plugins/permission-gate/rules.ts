import type { PermissionSubject } from "./subjects.ts";

const GIT_MUTATION_SUBCOMMANDS = new Set([
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
]);
const SQL_DATA_MUTATION_PATTERN =
  /\b(?:insert|update|delete|merge|truncate|vacuum|reindex|cluster)\b/i;
const SQL_ANALYZE_PATTERN = /(?<!\bexplain\s+)\banalyze\b/i;
const SQL_COPY_FROM_PATTERN = /\\?\bcopy\b[\s\S]*?\bfrom\b/i;
const SQL_DDL_PATTERN = /\b(?:create|alter|drop|rename)\b/i;
const SQL_DCL_PATTERN = /\b(?:grant|revoke)\b/i;
const WORK_WEB_SEARCH_TOOL = "web_search_web_search";
const GIT_VALUE_FLAGS = new Set([
  "-C",
  "-c",
  "--git-dir",
  "--work-tree",
  "--namespace",
  "--exec-path",
]);

export type RuleKey =
  | "git-interference"
  | "file-disposal"
  | "database-integrity"
  | "reconnaissance";

export type PermissionRule = {
  key: RuleKey;
  name: string;
  description: string;
  approveLabel: string;
  editLabel?: string;
  rejectLabel: string;
  subagent: "allow" | { blockReason: string };
  matches: (subject: PermissionSubject) => boolean;
};

export type PermissionMatch = {
  subject: PermissionSubject;
  rule: PermissionRule;
};

export const PERMISSION_RULES: readonly PermissionRule[] = [
  {
    key: "git-interference",
    name: "Git interference",
    description: "tampering with repository state or history",
    approveLabel: "Tamper",
    editLabel: "Amend",
    rejectLabel: "Deny",
    subagent: { blockReason: "Child threads may not alter Git state or history." },
    matches: (subject) => subject.kind === "shell-command" && isGitMutationCommand(subject.command),
  },
  {
    key: "file-disposal",
    name: "File disposal",
    description: "files targeted for elimination",
    approveLabel: "Dispose",
    editLabel: "Retarget",
    rejectLabel: "Prevent",
    subagent: "allow",
    matches: (subject) =>
      subject.kind === "shell-command" &&
      (isRecursiveForcedRemovalCommand(subject.command) || isFindDeleteCommand(subject.command)),
  },
  {
    key: "database-integrity",
    name: "Database integrity",
    description: "state mutation of data, schema, or privileges",
    approveLabel: "Mutate",
    editLabel: "Reword",
    rejectLabel: "Deny",
    subagent: { blockReason: "Child threads may not mutate databases." },
    matches: (subject) => subject.kind === "shell-command" && isPostgresMutation(subject.command),
  },
  {
    key: "reconnaissance",
    name: "Reconnaissance",
    description: "web search beyond local operational boundaries",
    approveLabel: "Commence",
    rejectLabel: "Reconsider",
    subagent: "allow",
    matches: (subject) => subject.toolName === WORK_WEB_SEARCH_TOOL,
  },
];

export function findMatchingRule(subject: PermissionSubject): PermissionMatch | undefined {
  for (const rule of PERMISSION_RULES) {
    if (rule.matches(subject)) return { subject, rule };
  }
  return undefined;
}

function isGitMutationCommand(command: string): boolean {
  return shellSegments(command).some((segment) => {
    const tokens = tokenizeShellWords(segment).map(stripOuterQuotes);
    const gitIndex = tokens.findIndex((token) => token === "git" || token.endsWith("/git"));
    if (gitIndex === -1) return false;

    const candidate = new GitCommand(tokens.slice(gitIndex + 1));
    const subcommand = candidate.positionals()[0];
    if (!subcommand || !GIT_MUTATION_SUBCOMMANDS.has(subcommand)) return false;

    return (
      !isReadOnlyAction(candidate) && !isReadOnlyListing(candidate) && !isReadOnlyClean(candidate)
    );
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

class GitCommand {
  constructor(private readonly args: readonly string[]) {}

  positionals(): readonly string[] {
    const positionals: string[] = [];

    for (let index = 0; index < this.args.length; index++) {
      const token = this.args[index];
      if (token === "--") {
        positionals.push(...this.args.slice(index + 1));
        break;
      }
      if (GIT_VALUE_FLAGS.has(token)) {
        index += 1;
        continue;
      }
      if (token.startsWith("--") && token.includes("=")) continue;
      if (token.startsWith("-") && token !== "-") continue;
      positionals.push(token);
    }

    return positionals;
  }

  hasFlag(...spellings: readonly string[]): boolean {
    return this.args.some((token) => spellings.includes(token));
  }
}

function isReadOnlyAction(command: GitCommand): boolean {
  const [subcommand, action] = command.positionals();
  if (subcommand === undefined) return false;

  const rule = READ_ONLY_ACTION_SUBCOMMANDS[subcommand];
  if (!rule) return false;

  return action === undefined ? rule.allowBare === true : rule.actions.has(action);
}

function isReadOnlyListing(command: GitCommand): boolean {
  const positionals = command.positionals();
  const subcommand = positionals[0];
  if (subcommand === undefined) return false;

  const mutatingFlags = LISTING_MUTATING_FLAGS[subcommand];
  if (!mutatingFlags) return false;

  return positionals.length === 1 && !command.hasFlag(...mutatingFlags);
}

function isReadOnlyClean(command: GitCommand): boolean {
  return command.positionals()[0] === "clean" && command.hasFlag("-n", "--dry-run");
}

function tokenizeShellWords(command: string): string[] {
  return command.match(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\S+/g) ?? [];
}

function stripOuterQuotes(token: string): string {
  if (token.length < 2) return token;

  const first = token[0];
  const last = token[token.length - 1];

  return first === last && (first === '"' || first === "'") ? token.slice(1, -1) : token;
}

function shellSegments(command: string): string[] {
  return command.split(/&&|\|\||[;|\n]/);
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

function isFindDeleteCommand(command: string): boolean {
  return /find\s+.*-delete/i.test(command);
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
