import {
  type PermissionSubject,
  SHELL_TOOL_NAMES,
  WEB_SEARCH_SUBJECT_TOOL,
} from "./permission-subject.js";

export type PermissionRule = {
  toolNames: readonly string[];
  label: string;
  description: string;
  matches: (subject: PermissionSubject) => boolean;
};

export type PermissionMatch = {
  subject: PermissionSubject;
  rule: PermissionRule;
};

function commandRule(
  label: string,
  description: string,
  matches: (command: string) => boolean,
): PermissionRule {
  return {
    toolNames: SHELL_TOOL_NAMES,
    label,
    description,
    matches: (subject) => subject.kind === "shell-command" && matches(subject.command),
  };
}

function commandPatternRule(label: string, description: string, pattern: RegExp): PermissionRule {
  return commandRule(label, description, (command) => pattern.test(command));
}

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

function isPsqlInvocation(command: string): boolean {
  return tokenizeShellWords(command)
    .map(stripOuterQuotes)
    .some((token) => token === "psql" || token.endsWith("/psql"));
}

function psqlRule(
  label: string,
  description: string,
  matchesSql: (command: string) => boolean,
): PermissionRule {
  return commandRule(
    label,
    description,
    (command) => isPsqlInvocation(command) && matchesSql(command),
  );
}

const SQL_DATA_MUTATION_PATTERN =
  /\b(?:insert|update|delete|merge|truncate|vacuum|reindex|cluster)\b/i;
// ANALYZE is a maintenance statement, but EXPLAIN ANALYZE is read-only — exclude that form.
const SQL_ANALYZE_PATTERN = /(?<!\bexplain\s+)\banalyze\b/i;
// COPY ... FROM (and the psql \copy meta-command) ingest data; COPY ... TO only exports.
const SQL_COPY_FROM_PATTERN = /\\?\bcopy\b[\s\S]*?\bfrom\b/i;
const SQL_DDL_PATTERN = /\b(?:create|alter|drop|rename)\b/i;
const SQL_DCL_PATTERN = /\b(?:grant|revoke)\b/i;

function isPostgresDataMutation(command: string): boolean {
  return (
    SQL_DATA_MUTATION_PATTERN.test(command) ||
    SQL_ANALYZE_PATTERN.test(command) ||
    SQL_COPY_FROM_PATTERN.test(command)
  );
}

export const PERMISSION_RULES: PermissionRule[] = [
  commandPatternRule(
    "git mutation",
    "git stash/add/commit/push/checkout/reset/clean/rebase",
    /\bgit\s+(\S+\s+)*?(stash|add|commit|push|checkout|reset|clean|rebase)\b/i,
  ),
  commandRule(
    "recursive forced removal",
    "rm with both recursive (-r/--recursive) and force (-f/--force) flags",
    isRecursiveForcedRemovalCommand,
  ),
  commandPatternRule("destructive find", "find with -delete", /find\s+.*-delete/i),
  psqlRule(
    "SQL data mutation",
    "psql running INSERT/UPDATE/DELETE/MERGE/TRUNCATE, COPY…FROM, or VACUUM/REINDEX/ANALYZE/CLUSTER",
    isPostgresDataMutation,
  ),
  psqlRule("SQL schema change", "psql running DDL: CREATE/ALTER/DROP/RENAME", (command) =>
    SQL_DDL_PATTERN.test(command),
  ),
  psqlRule("SQL privilege change", "psql running DCL: GRANT/REVOKE", (command) =>
    SQL_DCL_PATTERN.test(command),
  ),
  {
    toolNames: [WEB_SEARCH_SUBJECT_TOOL],
    label: "web search",
    description: "web search tools (data leaves the machine on every query)",
    matches: (subject) => subject.kind === "tool-invocation",
  },
];

export function findMatchingRule(subject: PermissionSubject): PermissionMatch | undefined {
  const rule = PERMISSION_RULES.find(
    (candidate) => candidate.toolNames.includes(subject.toolName) && candidate.matches(subject),
  );
  return rule ? { subject, rule } : undefined;
}
