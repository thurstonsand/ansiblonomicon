import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createFetchWebTool } from "./fetch.ts";
import { createGitHubFetcher } from "./github.ts";
import { createGitHubAuth } from "./github-auth.ts";
import { createLocalFetcher } from "./local.ts";
import { createTrafilaturaExtractor } from "./local-extractor.ts";
import { createParallelFetcher, hasParallelApiKey } from "./parallel.ts";
import { searchWebTool } from "./search.ts";
import { loadWebToolsSettings } from "./settings.ts";
import { getErrorMessage } from "./shared.ts";
import { createFetchWorkerClient } from "./worker-connection.ts";

export default function parallelWebTools(pi: ExtensionAPI) {
  // Without a Parallel key there is no search backend; an unregistered tool is
  // more honest than a permanently erroring one.
  if (hasParallelApiKey()) pi.registerTool(searchWebTool);
  const settings = loadWebToolsSettings();
  const workerClient = createFetchWorkerClient(settings.fetch.browser);
  pi.registerTool(
    createFetchWebTool([
      createGitHubFetcher(createGitHubAuth()),
      createParallelFetcher(),
      createLocalFetcher(workerClient, createTrafilaturaExtractor()),
    ]),
  );
  pi.registerCommand("open-browser", {
    description: "Open the fetch browser to log into sites for authenticated fetching",
    handler: async (_args, ctx) => {
      try {
        await workerClient.openBrowser();
        ctx.ui.notify(
          "Interactive browser open — log in as needed, then quit Chrome to resume fetching",
          "info",
        );
      } catch (error) {
        ctx.ui.notify(`open-browser failed: ${getErrorMessage(error)}`, "error");
      }
    },
  });
}
