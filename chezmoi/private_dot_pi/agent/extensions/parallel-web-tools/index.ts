import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createFetchWebTool } from "./fetch.js";
import { createGitHubFetcher } from "./github.js";
import { createGitHubAuth } from "./github-auth.js";
import { createParallelFetcher } from "./parallel.js";
import { searchWebTool } from "./search.js";

export default function parallelWebTools(pi: ExtensionAPI) {
  pi.registerTool(searchWebTool);
  pi.registerTool(
    createFetchWebTool([createGitHubFetcher(createGitHubAuth()), createParallelFetcher()]),
  );
}
