import type { LoadedReference } from "./load.js";

/** Wrap loaded files to match pi's native context format, tagged with origin. */
export function renderBlock(loaded: LoadedReference[]): string {
  let block = "\n\n<referenced_context>\n\nFiles pulled in via @-references from AGENTS.md:\n\n";
  for (const { resolvedPath, ref, from, content } of loaded) {
    block += `<project_instructions path="${resolvedPath}" referenced-as="@${ref}" referenced-from="${from}">\n${content}\n</project_instructions>\n\n`;
  }
  block += "</referenced_context>\n";
  return block;
}
