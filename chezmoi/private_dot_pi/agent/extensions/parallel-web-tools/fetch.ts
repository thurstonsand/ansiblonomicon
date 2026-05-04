import type { ToolDefinition } from "@mariozechner/pi-coding-agent";
import { Text } from "@mariozechner/pi-tui";
import { Type } from "typebox";
import {
  formatExtractErrors,
  formatFetchSummaryLine,
  formatWarnings,
  getErrorMessage,
  getParallelClient,
  summarizeExcerpt,
  writeFetchResultFile,
} from "./parallel.js";

type FetchResultItem = {
  url: string;
  title?: string | null;
  publish_date?: string | null;
  excerpts?: string[] | null;
  full_content?: string | null;
};

type FetchWarning = {
  message?: string | null;
  type?: string | null;
};

type FetchError = {
  url: string;
  error_type?: string | null;
  http_status_code?: number | null;
  content?: string | null;
};

type FetchWebDetails = {
  count?: number;
  files?: Array<{
    url: string;
    path: string;
    title?: string | null;
    excerpt?: string;
  }>;
  results?: FetchResultItem[];
  warnings?: FetchWarning[] | null;
  errors?: FetchError[] | null;
};

type RenderableToolResult<TDetails> = {
  content: Array<{ type: string; text?: string }>;
  details?: TDetails;
  isError?: boolean;
};

const fetchWebParameters = Type.Object({
  urls: Type.Array(Type.String({ description: "A URL to extract." }), {
    description: "One or more URLs to extract.",
    minItems: 1,
    maxItems: 10,
  }),
  objective: Type.Optional(
    Type.String({
      description:
        "Optional extraction goal. When provided, prioritize excerpts relevant to that objective.",
    }),
  ),
});

export const fetchWebTool: ToolDefinition<typeof fetchWebParameters, FetchWebDetails> = {
  name: "fetch_web",
  label: "Fetch Web",
  description:
    "Fetch and extract content from one or more specific web pages, saving the extracted payload to temp files.",
  promptSnippet:
    "Use when you already have a specific public URL and need the page contents or targeted excerpts.",
  promptGuidelines: [
    "Use fetch_web after search_web or when the user already provided URLs.",
    "Omit objective when you want broad page extraction; provide it when you want excerpts tailored to a specific question.",
    "Read or search/filter through the saved temp file if you need the full extracted content for deeper follow-up.",
  ],
  parameters: fetchWebParameters,
  execute: async (_toolCallId, params, _signal, onUpdate) => {
    onUpdate?.({
      content: [
        {
          type: "text",
          text: `Fetching ${params.urls.length} URL(s) from the web...`,
        },
      ],
      details: {},
    });

    try {
      const client = getParallelClient();
      const result = await client.extract({
        urls: params.urls,
        objective: params.objective,
        advanced_settings: { full_content: true },
      });

      const results = Array.isArray(result.results) ? (result.results as FetchResultItem[]) : [];
      const warnings = Array.isArray(result.warnings) ? (result.warnings as FetchWarning[]) : null;
      const errors = Array.isArray(result.errors) ? (result.errors as FetchError[]) : null;
      const files = [] as Array<{
        url: string;
        path: string;
        title?: string | null;
        excerpt?: string;
      }>;
      const summaryLines: string[] = [];

      for (const item of results) {
        const filePath = await writeFetchResultFile(item.url, item);
        const excerptPreview = summarizeExcerpt(item.excerpts?.[0], 280);
        files.push({
          url: item.url,
          path: filePath,
          title: item.title,
          excerpt: excerptPreview,
        });
        summaryLines.push(
          formatFetchSummaryLine({
            url: item.url,
            title: item.title,
            publish_date: item.publish_date,
            path: filePath,
            excerpts: item.excerpts,
          }),
        );
      }

      const warningLines = formatWarnings(warnings);
      const errorLines = formatExtractErrors(errors);
      const sections: string[] = [];
      if (warningLines.length > 0) {
        sections.push("Warnings:");
        sections.push(...warningLines.map((warning) => `- ${warning}`));
      }
      if (errorLines.length > 0) {
        if (sections.length > 0) sections.push("");
        sections.push("Errors:");
        sections.push(...errorLines.map((error) => `- ${error}`));
      }
      if (sections.length > 0 && summaryLines.length > 0) sections.push("");
      sections.push(...summaryLines);

      return {
        content: [
          {
            type: "text",
            text: sections.join("\n") || "No extracted results.",
          },
        ],
        details: { count: results.length, files, results, warnings, errors },
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: `Parallel fetch failed: ${getErrorMessage(error)}`,
          },
        ],
        isError: true,
        details: {},
      };
    }
  },
  renderCall(args, theme, context) {
    let text = theme.fg("toolTitle", theme.bold("fetch_web"));

    if (context.isPartial) {
      const primaryUrl = args.urls.find((url: string) => url.trim())?.trim() ?? "";
      const extraUrls = Math.max(args.urls.filter((url: string) => url.trim()).length - 1, 0);
      if (primaryUrl) {
        text += theme.fg("toolTitle", " ");
        text += theme.fg("muted", primaryUrl);
      }
      if (extraUrls > 0) {
        text += theme.fg("dim", ` +${extraUrls} more`);
      }
    }

    return new Text(text, 0, 0);
  },
  renderResult(result, { expanded, isPartial }, theme) {
    const renderedResult = result as RenderableToolResult<FetchWebDetails>;
    if (isPartial) return new Text(theme.fg("warning", "Fetching..."), 0, 0);
    if (renderedResult.isError) {
      const text =
        renderedResult.content[0]?.type === "text"
          ? (renderedResult.content[0].text ?? "Fetch failed")
          : "Fetch failed";
      return new Text(theme.fg("error", text), 0, 0);
    }

    const details = (renderedResult.details ?? {}) as FetchWebDetails;
    const count = details.count ?? details.files?.length ?? 0;
    let text = theme.fg("success", `${count} file${count === 1 ? "" : "s"} saved`);
    const warningLines = formatWarnings(details.warnings);
    const errorLines = formatExtractErrors(details.errors);
    if (warningLines.length > 0) {
      text += `\n${theme.fg("warning", expanded ? "Warnings:" : `Warnings: ${warningLines.length}`)}`;
      if (expanded) {
        for (const warning of warningLines) {
          text += `\n${theme.fg("warning", `- ${warning}`)}`;
        }
      }
    }
    if (errorLines.length > 0) {
      text += `\n${theme.fg("error", `${errorLines.length} URL${errorLines.length === 1 ? "" : "s"} failed`)}`;
      if (expanded) {
        for (const error of errorLines) {
          text += `\n${theme.fg("error", `- ${error}`)}`;
        }
      }
    }

    if (details.files?.length) {
      for (const [index, file] of details.files.entries()) {
        const title = file.title?.trim();
        if (title && title !== file.url) {
          text += `\n${theme.fg("accent", `${index + 1}. ${title}`)}${theme.fg("muted", ` (${file.url})`)}`;
        } else {
          text += `\n${theme.fg("accent", `${index + 1}. ${file.url}`)}`;
        }
        text += `\n${theme.fg("dim", file.path)}`;
        if (file.excerpt) {
          text += `\n${theme.fg("muted", expanded ? file.excerpt : summarizeExcerpt(file.excerpt, 120))}`;
        }
      }
    }

    return new Text(text, 0, 0);
  },
};
