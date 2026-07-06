import path from "node:path";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { FetchWarning, RoutedFetchResult, UrlOutcome, WebFetcher } from "./contract.js";
import { TMP_DIR } from "./shared.js";

export async function fetchDocuments(
  fetchers: WebFetcher[],
  urls: string[],
  objective: string | undefined,
  signal: AbortSignal | undefined,
  ctx: ExtensionContext,
): Promise<RoutedFetchResult> {
  const artifactRoot = path.join(TMP_DIR, new Date().toISOString().replace(/[:.]/g, "-"));
  const outcomesByUrl = new Map<string, UrlOutcome>(
    urls.map((url) => [url, { url, attempts: [] }]),
  );
  const warnings: FetchWarning[] = [];

  for (const fetcher of fetchers) {
    const remainingUrls = [...outcomesByUrl.values()]
      .filter((outcome) => !outcome.document)
      .map((outcome) => outcome.url);
    if (remainingUrls.length === 0) break;
    if (signal?.aborted) throw new Error("Fetch cancelled.");

    const matchingUrls = remainingUrls.filter((url) => fetcher.canFetch(url));
    if (matchingUrls.length === 0) continue;

    const result = await fetcher.fetch({
      urls: matchingUrls,
      artifactDir: artifactRoot,
      objective,
      signal,
      ctx,
    });
    warnings.push(...result.warnings);
    for (const document of result.documents) {
      const outcome = outcomesByUrl.get(document.url);
      if (outcome) outcome.document = document;
    }
    for (const failure of result.failures) {
      outcomesByUrl.get(failure.url)?.attempts.push({ source: fetcher.source, ...failure });
    }
  }

  const outcomes = urls.flatMap((url) => {
    const outcome = outcomesByUrl.get(url);
    return outcome ? [outcome] : [];
  });

  return { outcomes, warnings, artifactRoot };
}
