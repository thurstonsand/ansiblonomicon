import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { fetchWebTool } from "./fetch.js";
import { searchWebTool } from "./search.js";

export default function parallelWebTools(pi: ExtensionAPI) {
  pi.registerTool(searchWebTool);
  pi.registerTool(fetchWebTool);
}
