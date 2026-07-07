import path from "node:path";
import { Octokit, type RestEndpointMethodTypes } from "@octokit/rest";
import type { FetchedDocument, FetcherResult, FetchFailure, WebFetcher } from "./contract.ts";
import type { GitHubAuth } from "./github-auth.ts";
import { getErrorMessage, writeDocumentBody } from "./shared.ts";

type ResolverResult =
  | { status: "resolved"; document: FetchedDocument }
  | { status: "unsupported"; reason?: string }
  | { status: "failed"; reason: string };

interface GitHubDirectoryEntry {
  type: string;
  name: string;
  path: string;
  size?: number;
  sha?: string;
  html_url?: string;
  download_url?: string | null;
}

interface GitHubIssueComment {
  id: number;
  author?: string;
  author_association?: string;
  body?: string | null;
  html_url?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

interface GitHubRefSummary {
  label?: string;
  ref?: string;
  sha?: string;
  repo?: string;
  owner?: string;
}

interface GitHubReview {
  id: number;
  author?: string;
  author_association?: string;
  body?: string | null;
  state?: string;
  html_url?: string;
  submitted_at?: string | null;
  commit_id?: string;
}

interface GitHubReviewComment {
  id: number;
  pull_request_review_id?: number | null;
  author?: string;
  author_association?: string;
  body?: string | null;
  path?: string;
  diff_hunk?: string;
  line?: number | null;
  original_line?: number | null;
  html_url?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

interface GitHubPullRequestFile {
  sha?: string;
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  blob_url?: string;
  raw_url?: string;
  contents_url?: string;
  previous_filename?: string;
  patch_truncated?: boolean;
  patch?: string;
}

type GitHubIssueRenderModel = {
  title: string;
  url: string;
  html_url?: string;
  state: string;
  state_reason?: string | null;
  author?: string;
  created_at: string;
  updated_at: string;
  body?: string | null;
  comments: GitHubIssueComment[];
  comments_truncated: boolean;
};

type GitHubPullRequestRenderModel = {
  issue_comments_truncated: boolean;
  reviews_truncated: boolean;
  review_comments_truncated: boolean;
  files_truncated: boolean;
  title: string;
  url: string;
  html_url?: string;
  state: string;
  author?: string;
  draft: boolean;
  merged?: boolean;
  base: GitHubRefSummary;
  head: GitHubRefSummary;
  additions: number;
  deletions: number;
  changed_files: number;
  commits: number;
  body?: string | null;
  issue_comments: GitHubIssueComment[];
  reviews: GitHubReview[];
  review_comments: GitHubReviewComment[];
  files: GitHubPullRequestFile[];
};

const GITHUB_HOST = "github.com";
const RAW_GITHUB_HOST = "raw.githubusercontent.com";
const API_GITHUB_HOST = "api.github.com";
const DIRECTORY_LIMIT = 1000;
const ISSUE_COMMENT_LIMIT = 200;
const PR_REVIEW_LIMIT = 100;
const PR_REVIEW_COMMENT_LIMIT = 200;
const PR_FILE_LIMIT = 300;
const PATCH_TEXT_LIMIT = 400_000;
const RAW_CONTENT_LIMIT = 100 * 1024 * 1024;

type GitHubRepo = {
  owner: string;
  repo: string;
};

type FileTarget = GitHubRepo & {
  url: string;
  ref?: string;
  path: string;
};

type DirectoryTarget = GitHubRepo & {
  url: string;
  ref?: string;
  path: string;
};

type IssueTarget = GitHubRepo & {
  url: string;
  number: number;
};

type PullRequestTarget = GitHubRepo & {
  url: string;
  number: number;
};

type RefPathTarget = GitHubRepo & {
  marker: "blob" | "tree" | "raw";
  parts: string[];
  url: string;
};

type GetContentData = RestEndpointMethodTypes["repos"]["getContent"]["response"]["data"];
type ContentFile = {
  type?: string;
  size?: number;
  name?: string;
  path?: string;
  sha?: string;
  content?: string;
  encoding?: string;
  url?: string;
  html_url?: string | null;
  download_url?: string | null;
};

type DirectoryEntryResponse = Extract<GetContentData, unknown[]>[number];
type DirectoryResponse = {
  type?: string;
  size?: number;
  name?: string;
  path?: string;
  sha?: string;
  entries?: DirectoryEntryResponse[];
  url?: string;
  html_url?: string | null;
};

type OctokitRequestOptions = { request?: { signal?: AbortSignal } };

// Any console output corrupts pi's interactive TUI (its differential renderer
// cannot recover from writes it did not make), so octokit must never log.
// The top-level `log` alone is not enough: @octokit/request resolves its logger
// from the per-request options (`request.log || console`) when emitting API
// deprecation warnings, so the silent logger has to be passed at both levels.
const SILENT_OCTOKIT_LOG = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
};

export function createGitHubFetcher(auth: GitHubAuth): WebFetcher {
  let clientPromise: Promise<Octokit> | undefined;

  async function getClient(): Promise<Octokit> {
    clientPromise ??= createClient();
    return await clientPromise;
  }

  async function createClient(): Promise<Octokit> {
    const token = await auth.getToken();
    return new Octokit({
      ...(token ? { auth: token } : {}),
      userAgent: "pi-parallel-web-tools",
      log: SILENT_OCTOKIT_LOG,
      request: { log: SILENT_OCTOKIT_LOG },
    });
  }

  async function fetchOne(
    url: string,
    octokit: Octokit,
    signal: AbortSignal | undefined,
    artifactDir: string,
  ): Promise<ResolverResult> {
    try {
      return await fetchGitHubUrl(octokit, url, signal, artifactDir);
    } catch (error) {
      return {
        status: "failed",
        reason: getErrorMessage(error),
      };
    }
  }

  return {
    source: "github",
    canFetch: isGitHubUrl,
    async fetch({ urls, signal, artifactDir }): Promise<FetcherResult> {
      if (signal?.aborted) throw new Error("Fetch cancelled.");
      const octokit = await getClient();
      const results = await Promise.all(
        urls.map(async (url) => ({
          url,
          result: await fetchOne(url, octokit, signal, artifactDir),
        })),
      );
      const documents: FetchedDocument[] = [];
      const failures: FetchFailure[] = [];

      for (const { url, result } of results) {
        if (result.status === "resolved") {
          documents.push(result.document);
        } else if (result.status === "failed") {
          failures.push({ url, reason: result.reason });
        }
      }

      return { documents, failures, warnings: [] };
    },
  };
}

async function fetchGitHubUrl(
  octokit: Octokit,
  url: string,
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<ResolverResult> {
  const parsed = parseGitHubUrl(url);
  if (!parsed) return { status: "unsupported", reason: "Unsupported GitHub URL." };

  switch (parsed.type) {
    case "file":
      return {
        status: "resolved",
        document: await fetchFile(octokit, parsed.target, signal, artifactDir),
      };
    case "readme":
      return {
        status: "resolved",
        document: await fetchReadme(octokit, parsed.target, signal, artifactDir),
      };
    case "directory":
      return {
        status: "resolved",
        document: await fetchDirectory(octokit, parsed.target, signal, artifactDir),
      };
    case "issue":
      return {
        status: "resolved",
        document: await fetchIssue(octokit, parsed.target, signal, artifactDir),
      };
    case "pull_request":
      return {
        status: "resolved",
        document: await fetchPullRequest(octokit, parsed.target, signal, artifactDir),
      };
    case "ambiguous_file": {
      const resolved = await resolveRefPath(octokit, parsed.target, "file", signal);
      return {
        status: "resolved",
        document: await fetchFile(octokit, { ...resolved, url }, signal, artifactDir),
      };
    }
    case "ambiguous_directory": {
      const resolved = await resolveRefPath(octokit, parsed.target, "directory", signal);
      return {
        status: "resolved",
        document: await fetchDirectory(octokit, { ...resolved, url }, signal, artifactDir),
      };
    }
  }
}

function parseGitHubUrl(
  url: string,
):
  | { type: "file"; target: FileTarget }
  | { type: "readme"; target: GitHubRepo & { url: string } }
  | { type: "directory"; target: DirectoryTarget }
  | { type: "issue"; target: IssueTarget }
  | { type: "pull_request"; target: PullRequestTarget }
  | { type: "ambiguous_file"; target: RefPathTarget }
  | { type: "ambiguous_directory"; target: RefPathTarget }
  | undefined {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return undefined;
  }

  const host = parsed.hostname.toLowerCase();
  const parts = parsed.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  if (host === RAW_GITHUB_HOST) {
    const [owner, repo, ...rest] = parts;
    if (!owner || !repo || rest.length < 2) return undefined;
    return { type: "ambiguous_file", target: { owner, repo, marker: "raw", parts: rest, url } };
  }

  if (host === API_GITHUB_HOST) {
    const [reposMarker, owner, repo, contentsMarker, ...pathParts] = parts;
    if (reposMarker !== "repos" || !owner || !repo || contentsMarker !== "contents") {
      return undefined;
    }
    const ref = parsed.searchParams.get("ref") ?? undefined;
    const contentPath = pathParts.join("/");
    if (!contentPath) return undefined;
    return {
      type: "file",
      target: { owner, repo, ref, path: contentPath, url },
    };
  }

  if (host !== GITHUB_HOST) return undefined;

  const [owner, repo, marker, numberOrRef, ...rest] = parts;
  if (!owner || !repo) return undefined;

  if (!marker) {
    return { type: "readme", target: { owner, repo, url } };
  }

  if ((marker === "issues" || marker === "pull") && numberOrRef) {
    const number = Number.parseInt(numberOrRef, 10);
    if (!Number.isInteger(number) || number <= 0) return undefined;
    return marker === "issues"
      ? { type: "issue", target: { owner, repo, number, url } }
      : { type: "pull_request", target: { owner, repo, number, url } };
  }

  if ((marker === "blob" || marker === "raw") && numberOrRef && rest.length > 0) {
    return {
      type: "ambiguous_file",
      target: { owner, repo, marker, parts: [numberOrRef, ...rest], url },
    };
  }

  if (marker === "tree" && numberOrRef) {
    return {
      type: "ambiguous_directory",
      target: { owner, repo, marker, parts: [numberOrRef, ...rest], url },
    };
  }

  return undefined;
}

async function fetchFile(
  octokit: Octokit,
  target: FileTarget,
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<FetchedDocument> {
  return buildFileDocument(
    "github.file",
    target,
    await getContentFile(octokit, target, signal),
    signal,
    artifactDir,
  );
}

async function fetchReadme(
  octokit: Octokit,
  target: GitHubRepo & { url: string },
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<FetchedDocument> {
  const response = await octokit.rest.repos.getReadme({
    owner: target.owner,
    repo: target.repo,
    mediaType: { format: "object" },
    ...requestOptions(signal),
  });
  return buildFileDocument(
    "github.readme",
    target,
    response.data as ContentFile,
    signal,
    artifactDir,
  );
}

async function buildFileDocument(
  kind: "github.file" | "github.readme",
  target: GitHubRepo & { url: string; ref?: string; path?: string },
  item: ContentFile,
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<FetchedDocument> {
  const sourcePath = item.path ?? target.path ?? item.name ?? "README";
  const content = await readContentFile(item, signal);
  const body = await writeDocumentBody(
    artifactDir,
    target.url,
    item.name ?? path.basename(sourcePath),
    content,
  );
  return {
    kind,
    source: "github",
    url: target.url,
    link: item.html_url ?? undefined,
    title:
      kind === "github.readme"
        ? `${target.owner}/${target.repo} README`
        : `${target.owner}/${target.repo}:${sourcePath}`,
    facts: [
      `repo ${target.owner}/${target.repo}`,
      ...(target.ref ? [`ref ${target.ref}`] : []),
      `path ${sourcePath}`,
      ...(Buffer.isBuffer(content) ? ["binary"] : []),
      ...(kind === "github.readme"
        ? [`whole repository: git clone https://github.com/${target.owner}/${target.repo}.git`]
        : []),
    ],
    excerpt: Buffer.isBuffer(content) ? undefined : content,
    bodies: [body],
  };
}

async function fetchDirectory(
  octokit: Octokit,
  target: DirectoryTarget,
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<FetchedDocument> {
  const response = await octokit.rest.repos.getContent({
    owner: target.owner,
    repo: target.repo,
    path: target.path,
    ...(target.ref ? { ref: target.ref } : {}),
    mediaType: { format: "object" },
    ...requestOptions(signal),
  });
  const directory = normalizeDirectoryResponse(response.data);
  const entries = (directory.entries ?? []).map(normalizeDirectoryEntry);
  const likelyIncomplete = entries.length >= DIRECTORY_LIMIT;
  const title = `${target.owner}/${target.repo}:${target.path || "/"}`;
  return {
    kind: "github.directory",
    source: "github",
    url: target.url,
    title,
    link: directory.html_url ?? undefined,
    facts: [
      `${entries.length} entr${entries.length === 1 ? "y" : "ies"}`,
      ...(likelyIncomplete ? ["listing may be incomplete"] : []),
    ],
    excerpt: entries
      .map((entry) => (entry.type === "dir" ? `${entry.name}/` : entry.name))
      .join(", "),
    bodies: [
      await writeDocumentBody(
        artifactDir,
        target.url,
        "listing.md",
        renderDirectoryMarkdown(title, entries, likelyIncomplete),
      ),
    ],
  };
}

async function fetchIssue(
  octokit: Octokit,
  target: IssueTarget,
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<FetchedDocument> {
  const response = await octokit.rest.issues.get({
    owner: target.owner,
    repo: target.repo,
    issue_number: target.number,
    mediaType: { format: "full" },
    ...requestOptions(signal),
  });
  const issue = response.data;
  const comments = await listIssueComments(octokit, target, ISSUE_COMMENT_LIMIT, signal);
  const labels = issue.labels
    .map((label) => (typeof label === "string" ? label : label.name))
    .filter(isString);
  const model: GitHubIssueRenderModel = {
    title: `${target.owner}/${target.repo}#${target.number}: ${issue.title}`,
    url: target.url,
    html_url: issue.html_url,
    state: issue.state,
    state_reason: issue.state_reason,
    author: issue.user?.login,
    created_at: issue.created_at,
    updated_at: issue.updated_at,
    body: issue.body,
    comments: comments.items,
    comments_truncated: comments.truncated,
  };
  return {
    kind: "github.issue",
    source: "github",
    url: target.url,
    link: issue.html_url,
    title: model.title,
    facts: [
      `${issue.state}${issue.state_reason ? ` (${issue.state_reason})` : ""}`,
      ...(issue.user?.login ? [`by ${issue.user.login}`] : []),
      `${issue.comments} comment${issue.comments === 1 ? "" : "s"}`,
      ...(comments.truncated ? [`comments capped at ${ISSUE_COMMENT_LIMIT}`] : []),
      ...(labels.length > 0 ? [`labels ${labels.join(", ")}`] : []),
    ],
    excerpt: issue.body ?? comments.items[0]?.body ?? undefined,
    bodies: [
      await writeDocumentBody(
        artifactDir,
        target.url,
        "conversation.md",
        renderIssueMarkdown(model),
      ),
    ],
  };
}

async function fetchPullRequest(
  octokit: Octokit,
  target: PullRequestTarget,
  signal: AbortSignal | undefined,
  artifactDir: string,
): Promise<FetchedDocument> {
  const response = await octokit.rest.pulls.get({
    owner: target.owner,
    repo: target.repo,
    pull_number: target.number,
    mediaType: { format: "full" },
    ...requestOptions(signal),
  });
  const pr = response.data;
  const [issueComments, reviews, reviewComments, files] = await Promise.all([
    listIssueComments(octokit, target, ISSUE_COMMENT_LIMIT, signal),
    listPullRequestReviews(octokit, target, PR_REVIEW_LIMIT, signal),
    listPullRequestReviewComments(octokit, target, PR_REVIEW_COMMENT_LIMIT, signal),
    listPullRequestFiles(octokit, target, PR_FILE_LIMIT, signal),
  ]);
  const model: GitHubPullRequestRenderModel = {
    issue_comments_truncated: issueComments.truncated,
    reviews_truncated: reviews.truncated,
    review_comments_truncated: reviewComments.truncated,
    files_truncated: files.truncated,
    title: `${target.owner}/${target.repo}#${target.number}: ${pr.title}`,
    url: target.url,
    html_url: pr.html_url,
    state: pr.state,
    author: pr.user?.login,
    draft: pr.draft ?? false,
    merged: pr.merged ?? undefined,
    base: normalizeRefSummary(pr.base),
    head: normalizeRefSummary(pr.head),
    additions: pr.additions ?? 0,
    deletions: pr.deletions ?? 0,
    changed_files: pr.changed_files ?? 0,
    commits: pr.commits ?? 0,
    body: pr.body,
    issue_comments: issueComments.items,
    reviews: reviews.items,
    review_comments: reviewComments.items,
    files: files.items,
  };
  return {
    kind: "github.pull_request",
    source: "github",
    url: target.url,
    link: pr.html_url,
    title: model.title,
    facts: [
      `${pr.state}${pr.draft ? " draft" : ""}${pr.merged ? " merged" : ""}`,
      ...(pr.user?.login ? [`by ${pr.user.login}`] : []),
      `+${pr.additions ?? 0} -${pr.deletions ?? 0}`,
      `${pr.changed_files ?? 0} file${(pr.changed_files ?? 0) === 1 ? "" : "s"}`,
      `${issueComments.items.length} issue comment${issueComments.items.length === 1 ? "" : "s"}`,
      `${reviews.items.length} review${reviews.items.length === 1 ? "" : "s"}`,
      ...(issueComments.truncated ||
      reviews.truncated ||
      reviewComments.truncated ||
      files.truncated
        ? ["some lists capped; see conversation.md markers"]
        : []),
    ],
    excerpt: pr.body ?? issueComments.items[0]?.body ?? undefined,
    bodies: [
      await writeDocumentBody(
        artifactDir,
        target.url,
        "conversation.md",
        renderPullRequestMarkdown(model),
      ),
      await writeDocumentBody(
        artifactDir,
        target.url,
        "diff.patch",
        renderPullRequestPatch(files.items),
      ),
    ],
  };
}

async function getContentFile(
  octokit: Octokit,
  target: FileTarget,
  signal: AbortSignal | undefined,
): Promise<ContentFile> {
  const response = await octokit.rest.repos.getContent({
    owner: target.owner,
    repo: target.repo,
    path: target.path,
    ...(target.ref ? { ref: target.ref } : {}),
    mediaType: { format: "object" },
    ...requestOptions(signal),
  });
  if (Array.isArray(response.data)) {
    throw new Error(`Expected file but GitHub returned a directory: ${target.path}`);
  }
  const item = response.data as ContentFile;
  if (item.type === "dir") {
    throw new Error(`Expected file but GitHub returned a directory: ${target.path}`);
  }
  return item;
}

function normalizeDirectoryResponse(value: unknown): DirectoryResponse {
  if (Array.isArray(value)) {
    return { type: "dir", entries: value as DirectoryEntryResponse[] };
  }
  if (!isRecord(value)) throw new Error("GitHub returned an invalid directory response.");
  const directory = value as DirectoryResponse;
  if (Array.isArray(directory.entries)) return directory;
  throw new Error("GitHub returned a file where a directory was expected.");
}

function normalizeDirectoryEntry(entry: DirectoryEntryResponse): GitHubDirectoryEntry {
  return {
    type: entry.type ?? "unknown",
    name: entry.name ?? path.basename(entry.path ?? ""),
    path: entry.path ?? entry.name ?? "",
    size: entry.size,
    sha: entry.sha,
    html_url: entry.html_url ?? undefined,
    download_url: entry.download_url,
  };
}

async function readContentFile(
  item: ContentFile,
  signal: AbortSignal | undefined,
): Promise<string | Buffer> {
  if (item.encoding === "base64" && item.content) {
    return decodeTextOrBuffer(Buffer.from(item.content.replace(/\n/g, ""), "base64"));
  }
  if (item.content) return item.content;
  if (item.download_url) return await fetchRawContent(item.download_url, signal);

  throw new Error(
    `GitHub did not return inline content for ${item.path ?? item.name ?? "file"}; the file may be too large.`,
  );
}

async function fetchRawContent(
  url: string,
  signal: AbortSignal | undefined,
): Promise<string | Buffer> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`GitHub raw download failed with HTTP ${response.status}.`);
  }

  const contentLength = response.headers.get("content-length");
  if (contentLength && Number(contentLength) > RAW_CONTENT_LIMIT) {
    throw new Error(`GitHub raw file exceeds ${RAW_CONTENT_LIMIT} byte limit.`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  if (buffer.byteLength > RAW_CONTENT_LIMIT) {
    throw new Error(`GitHub raw file exceeds ${RAW_CONTENT_LIMIT} byte limit.`);
  }
  return decodeTextOrBuffer(buffer);
}

function decodeTextOrBuffer(buffer: Buffer): string | Buffer {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    return buffer;
  }
}

async function resolveRefPath(
  octokit: Octokit,
  target: RefPathTarget,
  expected: "file" | "directory",
  signal: AbortSignal | undefined,
): Promise<GitHubRepo & { ref: string; path: string }> {
  for (let index = 1; index < target.parts.length; index += 1) {
    const ref = target.parts.slice(0, index).join("/");
    const contentPath = target.parts.slice(index).join("/");
    try {
      const response = await octokit.rest.repos.getContent({
        owner: target.owner,
        repo: target.repo,
        path: contentPath,
        ref,
        mediaType: { format: "object" },
        ...requestOptions(signal),
      });
      const contentData = response.data as unknown;
      const isDirectory =
        Array.isArray(contentData) || (isRecord(contentData) && contentData.type === "dir");
      if ((expected === "directory" && isDirectory) || (expected === "file" && !isDirectory)) {
        return { owner: target.owner, repo: target.repo, ref, path: contentPath };
      }
    } catch {
      // Try the next possible ref/path split.
    }
  }
  throw new Error(`Could not resolve GitHub ${target.marker} URL ref/path split.`);
}

async function listIssueComments(
  octokit: Octokit,
  target: IssueTarget | PullRequestTarget,
  limit: number,
  signal: AbortSignal | undefined,
): Promise<CappedResult<GitHubIssueComment>> {
  const result = await listWithCap(limit, async (page, perPage) => {
    const response = await octokit.rest.issues.listComments({
      owner: target.owner,
      repo: target.repo,
      issue_number: target.number,
      page,
      per_page: perPage,
      mediaType: { format: "full" },
      ...requestOptions(signal),
    });
    return response.data.map((comment) => ({
      id: comment.id,
      author: comment.user?.login,
      author_association: comment.author_association,
      body: comment.body,
      html_url: comment.html_url,
      created_at: comment.created_at,
      updated_at: comment.updated_at,
    }));
  });
  return result;
}

async function listPullRequestReviews(
  octokit: Octokit,
  target: PullRequestTarget,
  limit: number,
  signal: AbortSignal | undefined,
): Promise<CappedResult<GitHubReview>> {
  return listWithCap(limit, async (page, perPage) => {
    const response = await octokit.rest.pulls.listReviews({
      owner: target.owner,
      repo: target.repo,
      pull_number: target.number,
      page,
      per_page: perPage,
      mediaType: { format: "full" },
      ...requestOptions(signal),
    });
    return response.data.map((review) => ({
      id: review.id,
      author: review.user?.login,
      author_association: review.author_association,
      body: review.body,
      state: review.state,
      html_url: review.html_url,
      submitted_at: review.submitted_at,
      commit_id: review.commit_id ?? undefined,
    }));
  });
}

async function listPullRequestReviewComments(
  octokit: Octokit,
  target: PullRequestTarget,
  limit: number,
  signal: AbortSignal | undefined,
): Promise<CappedResult<GitHubReviewComment>> {
  return listWithCap(limit, async (page, perPage) => {
    const response = await octokit.rest.pulls.listReviewComments({
      owner: target.owner,
      repo: target.repo,
      pull_number: target.number,
      page,
      per_page: perPage,
      mediaType: { format: "full" },
      ...requestOptions(signal),
    });
    return response.data.map((comment) => ({
      id: comment.id,
      pull_request_review_id: comment.pull_request_review_id,
      author: comment.user?.login,
      author_association: comment.author_association,
      body: comment.body,
      path: comment.path,
      diff_hunk: comment.diff_hunk,
      line: comment.line,
      original_line: comment.original_line,
      html_url: comment.html_url,
      created_at: comment.created_at,
      updated_at: comment.updated_at,
    }));
  });
}

async function listPullRequestFiles(
  octokit: Octokit,
  target: PullRequestTarget,
  limit: number,
  signal: AbortSignal | undefined,
): Promise<CappedResult<GitHubPullRequestFile>> {
  let patchBytes = 0;
  return listWithCap(limit, async (page, perPage) => {
    const response = await octokit.rest.pulls.listFiles({
      owner: target.owner,
      repo: target.repo,
      pull_number: target.number,
      page,
      per_page: perPage,
      ...requestOptions(signal),
    });
    return response.data.map((file) => {
      const patch = file.patch;
      let patch_truncated = false;
      let cappedPatch = patch;
      if (patch) {
        const remaining = PATCH_TEXT_LIMIT - patchBytes;
        if (remaining <= 0) {
          cappedPatch = undefined;
          patch_truncated = true;
        } else if (Buffer.byteLength(patch, "utf8") > remaining) {
          cappedPatch = truncateUtf8Bytes(patch, remaining);
          patch_truncated = true;
          patchBytes = PATCH_TEXT_LIMIT;
        } else {
          patchBytes += Buffer.byteLength(patch, "utf8");
        }
      }
      return {
        sha: file.sha ?? undefined,
        filename: file.filename,
        status: file.status,
        additions: file.additions,
        deletions: file.deletions,
        changes: file.changes,
        blob_url: file.blob_url,
        raw_url: file.raw_url,
        contents_url: file.contents_url,
        previous_filename: file.previous_filename,
        patch_truncated,
        patch: cappedPatch,
      };
    });
  });
}

type CappedResult<T> = {
  items: T[];
  truncated: boolean;
};

async function listWithCap<T>(
  limit: number,
  fetchPage: (page: number, perPage: number) => Promise<T[]>,
): Promise<CappedResult<T>> {
  const items: T[] = [];
  let page = 1;
  while (items.length <= limit) {
    const perPage = Math.min(100, limit + 1 - items.length);
    const pageItems = await fetchPage(page, perPage);
    items.push(...pageItems);
    if (pageItems.length < perPage) break;
    page += 1;
  }
  const truncated = items.length > limit;
  return {
    items: items.slice(0, limit),
    truncated,
  };
}

function normalizeRefSummary(ref: {
  label?: string;
  ref?: string;
  sha?: string;
  repo?: { name?: string; owner?: { login?: string } } | null;
}): GitHubRefSummary {
  return {
    label: ref.label,
    ref: ref.ref,
    sha: ref.sha,
    repo: ref.repo?.name,
    owner: ref.repo?.owner?.login,
  };
}

function renderDirectoryMarkdown(
  title: string,
  entries: GitHubDirectoryEntry[],
  incomplete: boolean,
): string {
  const lines = [`# ${title}`, "", "| Type | Path | Size |", "| --- | --- | --- |"];
  for (const entry of entries) {
    lines.push(`| ${entry.type} | ${entry.path} | ${entry.size ?? ""} |`);
  }
  if (incomplete) lines.push("", "[listing may be incomplete: GitHub returned 1,000 entries]");
  return lines.join("\n");
}

function renderIssueMarkdown(issue: GitHubIssueRenderModel): string {
  const lines = [
    `# ${issue.title}`,
    "",
    `- State: ${issue.state}${issue.state_reason ? ` (${issue.state_reason})` : ""}`,
    `- Author: ${issue.author ?? "unknown"}`,
    `- Created: ${issue.created_at}`,
    `- Updated: ${issue.updated_at}`,
    `- URL: ${issue.html_url ?? issue.url}`,
    "",
    "## Body",
    "",
    issue.body ?? "(no body)",
  ];
  appendIssueComments(lines, issue.comments, issue.comments_truncated);
  return lines.join("\n");
}

function renderPullRequestMarkdown(pr: GitHubPullRequestRenderModel): string {
  const lines = [
    `# ${pr.title}`,
    "",
    `- State: ${pr.state}${pr.draft ? " (draft)" : ""}${pr.merged ? " (merged)" : ""}`,
    `- Author: ${pr.author ?? "unknown"}`,
    `- Base: ${pr.base.label ?? pr.base.ref ?? "unknown"}`,
    `- Head: ${pr.head.label ?? pr.head.ref ?? "unknown"}`,
    `- Changes: +${pr.additions} -${pr.deletions} across ${pr.changed_files} file(s)`,
    `- Commits: ${pr.commits}`,
    `- URL: ${pr.html_url ?? pr.url}`,
    "",
    "## Body",
    "",
    pr.body ?? "(no body)",
  ];

  appendIssueComments(lines, pr.issue_comments, pr.issue_comments_truncated, "Issue comments");
  appendReviews(lines, pr.reviews, pr.reviews_truncated);
  appendReviewComments(lines, pr.review_comments, pr.review_comments_truncated);
  appendPullRequestFiles(lines, pr.files, pr.files_truncated);
  return lines.join("\n");
}

function appendIssueComments(
  lines: string[],
  comments: GitHubIssueComment[],
  truncated: boolean,
  title = "Comments",
): void {
  lines.push("", `## ${title}`);
  if (comments.length === 0) {
    lines.push("", "(none)");
  }
  for (const comment of comments) {
    lines.push(
      "",
      `### ${comment.author ?? "unknown"} at ${comment.created_at ?? "unknown time"}`,
      "",
      comment.body ?? "",
    );
  }
  if (truncated) lines.push("", "[comments truncated]");
}

function appendReviews(lines: string[], reviews: GitHubReview[], truncated: boolean): void {
  lines.push("", "## Reviews");
  if (reviews.length === 0) lines.push("", "(none)");
  for (const review of reviews) {
    lines.push(
      "",
      `### ${review.state ?? "review"} by ${review.author ?? "unknown"}`,
      "",
      review.body ?? "",
    );
  }
  if (truncated) lines.push("", "[reviews truncated]");
}

function appendReviewComments(
  lines: string[],
  comments: GitHubReviewComment[],
  truncated: boolean,
): void {
  lines.push("", "## Review comments");
  if (comments.length === 0) lines.push("", "(none)");
  for (const comment of comments) {
    lines.push(
      "",
      `### ${comment.path ?? "unknown path"} by ${comment.author ?? "unknown"}`,
      "",
      comment.diff_hunk ? `\`\`\`diff\n${comment.diff_hunk}\n\`\`\`\n` : "",
      comment.body ?? "",
    );
  }
  if (truncated) lines.push("", "[review comments truncated]");
}

function renderPullRequestPatch(files: GitHubPullRequestFile[]): string {
  return files
    .flatMap((file) => {
      if (!file.patch) return [];
      const oldPath = file.previous_filename ?? file.filename;
      return [
        `diff --git a/${oldPath} b/${file.filename}`,
        `--- a/${oldPath}`,
        `+++ b/${file.filename}`,
        file.patch,
        file.patch_truncated ? "[patch truncated]" : "",
      ];
    })
    .filter(Boolean)
    .join("\n");
}

function appendPullRequestFiles(
  lines: string[],
  files: GitHubPullRequestFile[],
  truncated: boolean,
): void {
  lines.push("", "## Files", "", "| Status | File | + | - |", "| --- | --- | ---: | ---: |");
  for (const file of files) {
    lines.push(`| ${file.status} | ${file.filename} | ${file.additions} | ${file.deletions} |`);
  }
  if (truncated) lines.push("", "[files truncated]");
}

function requestOptions(signal: AbortSignal | undefined): OctokitRequestOptions {
  return signal ? { request: { signal } } : {};
}

function truncateUtf8Bytes(value: string, maxBytes: number): string {
  const buffer = Buffer.from(value, "utf8");
  if (buffer.byteLength <= maxBytes) return value;

  const decoder = new TextDecoder("utf-8", { fatal: true });
  for (let end = maxBytes; end >= 0; end -= 1) {
    try {
      return decoder.decode(buffer.subarray(0, end));
    } catch {
      // Drop the partial code point and try again.
    }
  }
  return "";
}

function isGitHubUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === GITHUB_HOST || host === RAW_GITHUB_HOST || host === API_GITHUB_HOST;
  } catch {
    return false;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: string | null | undefined): value is string {
  return typeof value === "string" && value.length > 0;
}
