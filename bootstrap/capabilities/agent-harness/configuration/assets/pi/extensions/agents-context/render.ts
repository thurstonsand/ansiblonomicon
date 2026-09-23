import type { LoadedContextFile } from "./load.js";

function renderLocalContext(loaded: LoadedContextFile[]): string {
  const localFiles = loaded.filter((file) => file.source.type === "local");
  if (localFiles.length === 0) return "";

  let block = "\n\n<project_context>\n\nProject-specific instructions and guidelines:\n\n";
  for (const { resolvedPath, content } of localFiles) {
    block += `<project_instructions path="${resolvedPath}">\n${content}\n</project_instructions>\n\n`;
  }
  block += "</project_context>\n";
  return block;
}

function renderReferencedContext(loaded: LoadedContextFile[]): string {
  if (!loaded.some((file) => file.source.type === "reference")) return "";

  let block = "\n\n<referenced_context>\n\n";
  for (const { resolvedPath, source, content } of loaded) {
    if (source.type !== "reference") continue;
    block += `File pulled in via @-reference from ${source.from}:\n\n`;
    block += `<project_instructions path="${resolvedPath}" referenced-as="@${source.ref}" referenced-from="${source.from}">\n${content}\n</project_instructions>\n\n`;
  }
  block += "</referenced_context>\n";
  return block;
}

export function renderBlocks(loaded: LoadedContextFile[]): string {
  return renderLocalContext(loaded) + renderReferencedContext(loaded);
}
