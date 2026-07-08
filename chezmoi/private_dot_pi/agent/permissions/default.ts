import {
  type HighlightSpan,
  isCustomToolInput,
  matchTool,
  type PermissionsAPI,
  type PermissionToolInput,
  request,
} from "@thurstonsand/pi-permissions";

const GIT_MUTATION_PATTERN =
  /\bgit\s+(\S+\s+)*?(stash|add|commit|push|checkout|reset|clean|rebase)\b/i;
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
const WEB_SEARCH_TOOL_PATTERN = /web[_-]?search$/i;

export default function permissions(api: PermissionsAPI): void {
  api.onToolUse({
    name: "Git interference",
    description: "tampering with repository state or history",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) =>
          isGitMutation(command)
            ? request({
                highlight: GIT_MUTATION_PATTERN,
                approveLabel: "Tamper",
                rejectLabel: "Deny",
              })
            : undefined,
      }),
  });

  api.onToolUse({
    name: "File disposal",
    description: "files targeted for elimination",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) =>
          isRecursiveForcedRemovalCommand(command) || isFindDeleteCommand(command)
            ? request({
                highlight: fileDisposalSpans,
                approveLabel: "Dispose",
                rejectLabel: "Prevent",
              })
            : undefined,
      }),
  });

  api.onToolUse({
    name: "Database integrity",
    description: "state mutation of data, schema, or privileges",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) =>
          isPostgresMutation(command)
            ? request({
                highlight: SQL_MUTATION_HIGHLIGHTS,
                approveLabel: "Mutate",
                rejectLabel: "Deny",
              })
            : undefined,
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

function isGitMutation(command: string): boolean {
  return GIT_MUTATION_PATTERN.test(command);
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
  return target && WEB_SEARCH_TOOL_PATTERN.test(target)
    ? request({ approveLabel: "Commence", rejectLabel: "Reconsider" })
    : undefined;
}

function webSearchTarget(tool: PermissionToolInput): string | undefined {
  return isCustomToolInput(tool, "mcp") && typeof tool.input.tool === "string"
    ? tool.input.tool
    : undefined;
}
