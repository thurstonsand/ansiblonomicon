import {
  isCustomToolInput,
  matchTool,
  type PermissionInput,
  type PermissionsAPI,
  type PermissionToolInput,
  request,
} from "@thurstonsand/pi-permissions";

const SQL_DATA_MUTATION_PATTERN =
  /\b(?:insert|update|delete|merge|truncate|vacuum|reindex|cluster)\b/i;
const SQL_ANALYZE_PATTERN = /(?<!\bexplain\s+)\banalyze\b/i;
const SQL_COPY_FROM_PATTERN = /\\?\bcopy\b[\s\S]*?\bfrom\b/i;
const SQL_DDL_PATTERN = /\b(?:create|alter|drop|rename)\b/i;
const SQL_DCL_PATTERN = /\b(?:grant|revoke)\b/i;
const WEB_SEARCH_TOOL_PATTERN = /web[_-]?search$/i;

export default function permissions(api: PermissionsAPI): void {
  api.onToolUse({
    name: "Git interference",
    description: "tampering with repository state or history",
    matcher: "bash",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) =>
          isGitMutation(command)
            ? request({ approveLabel: "Tamper", rejectLabel: "Deny" })
            : undefined,
      }),
  });

  api.onToolUse({
    name: "File disposal",
    description: "files targeted for elimination",
    matcher: "bash",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) =>
          isRecursiveForcedRemovalCommand(command) || isFindDeleteCommand(command)
            ? request({ approveLabel: "Dispose", rejectLabel: "Prevent" })
            : undefined,
      }),
  });

  api.onToolUse({
    name: "Database integrity",
    description: "state mutation of data, schema, or privileges",
    matcher: "bash",
    handler: ({ tool }) =>
      matchTool(tool, {
        bash: ({ command }) =>
          isPostgresMutation(command)
            ? request({ approveLabel: "Mutate", rejectLabel: "Deny" })
            : undefined,
      }),
  });

  api.onToolUse({
    name: "Reconnaissance",
    description: "web search beyond local operational boundaries",
    matcher: isWebSearchToolCall,
    handler: () => request({ approveLabel: "Commence", rejectLabel: "Reconsider" }),
  });
}

function isGitMutation(command: string): boolean {
  return /\bgit\s+(\S+\s+)*?(stash|add|commit|push|checkout|reset|clean|rebase)\b/i.test(command);
}

function isFindDeleteCommand(command: string): boolean {
  return /find\s+.*-delete/i.test(command);
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

function isWebSearchToolCall(input: PermissionInput): boolean {
  const target = webSearchTarget(input.tool);
  return target ? WEB_SEARCH_TOOL_PATTERN.test(target) : false;
}

function webSearchTarget(tool: PermissionToolInput): string | undefined {
  if (isCustomToolInput(tool, "mcp")) {
    return typeof tool.input.tool === "string" ? tool.input.tool : undefined;
  }

  return tool.toolName;
}
