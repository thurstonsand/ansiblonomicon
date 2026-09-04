// AI Gateway Proxy Worker
// Routes LLM requests through Cloudflare AI Gateway for observability, caching, rate limiting
// Non-LLM requests go directly to origin
//
// Request flow (LLM):
//   aig.thurstons.house/{path} → AI Gateway → custom-cli-proxy-api/{path} → cli-proxy-api.thurstons.house/{path}
// Request flow (other):
//   aig.thurstons.house/{path} → cli-proxy-api.thurstons.house/{path}

const GATEWAY_BASE = "https://gateway.ai.cloudflare.com/v1";
const ORIGIN = "https://cli-proxy-api.thurstons.house";

type RequestCategory = "provider" | "other";

type AnalyticsIndex = "response" | "empty_content_fix";

interface Analytics {
  track(index: AnalyticsIndex, ...blobs: string[]): void;
}

function createAnalytics(dataset?: AnalyticsEngineDataset): Analytics {
  return {
    track(index, ...blobs) {
      dataset?.writeDataPoint({ blobs, indexes: [index] });
    },
  };
}

interface MessageContent {
  type: string;
  text?: string;
  content?: MessageContent[];
  tool_use_id?: string;
}

interface Message {
  role?: string;
  content?: MessageContent[];
}

interface AnthropicRequestBody {
  messages?: Message[];
}

function getRequestCategory(pathname: string): RequestCategory {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  const second = segments[1];
  if (first === "v1" || first === "v1beta") return "provider";
  if (first === "api" && second === "provider") return "provider";

  return "other";
}

// For reference, these paths go DIRECT to origin (not through AI Gateway):
// /v0/management/*     - CLIProxyAPI management API
// /v1internal:*        - Internal Gemini CLI (localhost-only proxy)
// /anthropic/callback  - OAuth callbacks
// /codex/callback
// /google/callback
// /iflow/callback
// /antigravity/callback
// /auth/*              - Root auth
// /docs/*              - Docs
// /settings/*          - Settings
// /keep-alive          - Health check

function isAuthorized(url: URL, headers: Headers, apiKey: string): boolean {
  if (headers.get("Authorization") === `Bearer ${apiKey}`) return true;
  if (headers.get("x-api-key") === apiKey) return true;
  if (headers.get("x-goog-api-key") === apiKey) return true;
  if (url.searchParams.get("key") === apiKey) return true;
  if (url.searchParams.get("auth_token") === apiKey) return true;
  return false;
}

function fixEmptyTextBlocks(messages: Message[] | undefined, analytics: Analytics): boolean {
  if (!messages) return false;

  let fixed = false;

  for (const msg of messages) {
    if (!msg.content || !Array.isArray(msg.content)) continue;

    for (const block of msg.content) {
      if (block.type === "tool_result" && Array.isArray(block.content)) {
        for (const inner of block.content) {
          if (inner.type === "text" && inner.text === "") {
            console.warn("EMPTY_CONTENT_FIX", {
              tool_use_id: block.tool_use_id,
              message_role: msg.role,
            });
            analytics.track("empty_content_fix", block.tool_use_id ?? "unknown", msg.role ?? "unknown");
            inner.text = `<error>EMPTY_CONTENT_ERROR (tool_use_id=${block.tool_use_id}): The tool returned empty content due to a client bug. Please retry this exact tool call.</error>`;
            fixed = true;
          }
        }
      }
    }
  }

  return fixed;
}

function getStatusBucket(status: number): string {
  if (status >= 200 && status < 300) return "2xx";
  if (status >= 400 && status < 500) return "4xx";
  if (status >= 500) return "5xx";
  return "other";
}

function getConversationId(headers: Headers): string | undefined {
  return headers.get("x-opencode-session-id") ?? undefined;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const analytics = createAnalytics(env.ANALYTICS);
    const category = getRequestCategory(url.pathname);
    const conversationId = getConversationId(request.headers);

    if (!isAuthorized(url, request.headers, env.API_KEY)) {
      analytics.track("response", category, "4xx", "401", conversationId ?? "unknown");
      return new Response("Unauthorized: Invalid or missing API key", {
        status: 401,
        headers: { "Content-Type": "text/plain" },
      });
    }

    const headers = new Headers(request.headers);
    headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
    headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);

    let targetUrl: string;
    let body: BodyInit | null = request.body;

    if (category === "provider") {
      targetUrl = `${GATEWAY_BASE}/${env.ACCOUNT_ID}/${env.GATEWAY_ID}/custom-cli-proxy-api${url.pathname}${url.search}`;
      headers.set("cf-aig-authorization", `Bearer ${env.AIG_TOKEN}`);

      if (conversationId) {
        headers.set("cf-aig-metadata", JSON.stringify({ "conversation-id": conversationId }));
      }

      if (
        request.method === "POST" &&
        url.pathname.startsWith("/api/provider/anthropic/") &&
        url.pathname.endsWith("/messages")
      ) {
        const rawBody = await request.text();
        try {
          const parsed = JSON.parse(rawBody) as AnthropicRequestBody;
          if (fixEmptyTextBlocks(parsed.messages, analytics)) {
            body = JSON.stringify(parsed);
          } else {
            body = rawBody;
          }
        } catch {
          body = rawBody;
        }
      }
    } else {
      targetUrl = `${ORIGIN}${url.pathname}${url.search}`;
    }

    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      redirect: "follow",
    });

    analytics.track("response", category, getStatusBucket(response.status), String(response.status), conversationId ?? "unknown");

    return response;
  },
} satisfies ExportedHandler<Env>;
