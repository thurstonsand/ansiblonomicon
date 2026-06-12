import path from "node:path";

// Mirrors pi's autocomplete token boundaries (tui/src/autocomplete.ts), plus
// newlines so line-leading refs in multi-line context files are detected.
const TOKEN_BOUNDARIES = new Set([" ", "\t", "\n", "\r", '"', "'", "="]);

export function isAgentsFile(filePath: string): boolean {
  return path.basename(filePath).toUpperCase() === "AGENTS.MD";
}

/** Extract `@`-reference tokens that begin at a token boundary. */
export function extractRefs(content: string): string[] {
  const refs: string[] = [];
  for (let i = 0; i < content.length; i += 1) {
    if (content[i] !== "@") continue;
    if (i > 0 && !TOKEN_BOUNDARIES.has(content[i - 1] ?? "")) continue;

    let end = i + 1;
    while (end < content.length && !TOKEN_BOUNDARIES.has(content[end] ?? "")) {
      end += 1;
    }

    const ref = content.slice(i + 1, end);
    if (ref.length > 0) refs.push(ref);
    i = end;
  }
  return refs;
}
