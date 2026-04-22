import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import Parallel from "parallel-web";

export const API_KEY_ENV = "PARALLEL_API_KEY";
export const DEFAULT_SEARCH_MODE: "basic" | "advanced" = "advanced";
export const DEFAULT_MAX_RESULTS = 5;
export const MAX_MAX_RESULTS = 8;
export const TMP_DIR = "/tmp/pi-parallel-fetch";

export function getParallelClient(): Parallel {
  const apiKey = process.env[API_KEY_ENV];
  if (!apiKey) {
    throw new Error(`${API_KEY_ENV} is not set`);
  }
  return new Parallel({ apiKey });
}

export function asJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function normalizeSearchQueries(
  searchQueries: string[] | undefined,
  objective: string,
): string[] {
  const cleaned = (searchQueries ?? []).map((query) => query.trim()).filter(Boolean);
  return cleaned.length > 0 ? cleaned : [objective];
}

export function clampMaxResults(maxResults: number | undefined): number {
  if (maxResults === undefined) return DEFAULT_MAX_RESULTS;
  return Math.min(Math.max(maxResults, 1), MAX_MAX_RESULTS);
}

export function validateAfterDate(afterDate: string | undefined): string | undefined {
  if (!afterDate) return undefined;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(afterDate)) {
    throw new Error(`Invalid after_date: ${afterDate}. Expected YYYY-MM-DD.`);
  }

  const date = new Date(`${afterDate}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== afterDate) {
    throw new Error(
      `Invalid after_date: ${afterDate}. Expected a real calendar date in YYYY-MM-DD format.`,
    );
  }
  return afterDate;
}

export function summarizeExcerpt(text: string | undefined, maxLength = 220): string {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

export function formatWarnings(
  warnings: Array<{ message?: string | null; type?: string | null }> | undefined | null,
): string[] {
  if (!warnings?.length) return [];
  return warnings
    .map((warning) => {
      const type = warning.type ? `[${warning.type}] ` : "";
      const message = warning.message?.trim();
      return message ? `${type}${message}` : undefined;
    })
    .filter((warning): warning is string => Boolean(warning));
}

export function formatExtractErrors(
  errors:
    | Array<{
        url: string;
        error_type?: string | null;
        http_status_code?: number | null;
        content?: string | null;
      }>
    | undefined
    | null,
): string[] {
  if (!errors?.length) return [];
  return errors.map((error) => {
    const bits = [error.url];
    if (error.error_type) bits.push(`type=${error.error_type}`);
    if (error.http_status_code != null) bits.push(`status=${error.http_status_code}`);
    if (error.content?.trim()) bits.push(`content=${error.content.trim()}`);
    return bits.join(" | ");
  });
}

export function buildSearchSummary(
  results: Array<{
    title?: string | null;
    url: string;
    publish_date?: string | null;
    excerpts?: string[] | null;
  }>,
  warnings?: Array<{ message?: string | null; type?: string | null }> | null,
): string {
  const warningLines = formatWarnings(warnings);
  const resultText =
    results.length === 0
      ? "No results."
      : results
          .map((result, index) => {
            const title = result.title?.trim() || result.url;
            const publishDate = result.publish_date ? ` (${result.publish_date})` : "";
            const excerpts = (result.excerpts ?? []).map((excerpt, excerptIndex) => {
              const prefix =
                result.excerpts && result.excerpts.length > 1
                  ? `   Excerpt ${excerptIndex + 1}: `
                  : "   ";
              return `${prefix}${excerpt}`;
            });
            return [`${index + 1}. ${title}${publishDate}`, `   ${result.url}`, ...excerpts].join(
              "\n",
            );
          })
          .join("\n\n");

  if (warningLines.length === 0) return resultText;
  return [`Warnings:`, ...warningLines.map((warning) => `- ${warning}`), "", resultText].join("\n");
}

export function formatFetchSummaryLine(item: {
  url: string;
  title?: string | null;
  publish_date?: string | null;
  path: string;
  excerpts?: string[] | null;
}): string {
  const title = item.title?.trim();
  const publishDate = item.publish_date ? ` (${item.publish_date})` : "";
  const lines: string[] = [];
  if (title && title !== item.url) {
    lines.push(`${title}${publishDate}`);
  }
  lines.push(item.url);
  lines.push(`Saved: ${item.path}`);
  for (const [index, excerpt] of (item.excerpts ?? []).entries()) {
    const prefix = (item.excerpts?.length ?? 0) > 1 ? `Excerpt ${index + 1}: ` : "Excerpt: ";
    lines.push(`${prefix}${excerpt}`);
  }
  return lines.join("\n");
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/https?:\/\//g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export async function writeFetchResultFile(url: string, payload: unknown): Promise<string> {
  await mkdir(TMP_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filePath = path.join(TMP_DIR, `${stamp}-${slugify(url) || "result"}.json`);
  await writeFile(filePath, asJson(payload), "utf8");
  return filePath;
}
