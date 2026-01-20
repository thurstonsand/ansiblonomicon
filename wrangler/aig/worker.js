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

// Categorizes requests for analytics tracking
// Returns: "provider", "amp_metadata", or "other"
function getRequestCategory(pathname) {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  const second = segments[1];

  // Provider routes (go through AI Gateway)
  if (first === "v1" || first === "v1beta") return "provider";
  if (first === "api" && second === "provider") return "provider";

  // Amp metadata routes (go direct to origin)
  const ampMetadataPaths = [
    "internal",
    "user",
    "auth",
    "meta",
    "telemetry",
    "threads",
    "ads",
    "otel",
    "tab",
  ];
  if (first === "api" && ampMetadataPaths.includes(second)) return "amp_metadata";

  return "other";
}

// For reference, these paths go DIRECT to origin (not through AI Gateway):
// /v0/management/*     - CLIProxyAPI management API
// /v1internal:*        - Internal Gemini CLI (localhost-only proxy)
// /api/internal/*      - Amp internal management
// /api/user/*          - Amp user management
// /api/auth/*          - Amp auth
// /api/meta/*          - Amp metadata
// /api/telemetry/*     - Telemetry
// /api/threads/*       - Conversation threads
// /api/ads/*           - Ads
// /api/otel/*          - OpenTelemetry
// /api/tab/*           - Tab management
// /anthropic/callback  - OAuth callbacks
// /codex/callback
// /google/callback
// /iflow/callback
// /antigravity/callback
// /auth/*              - Root auth
// /threads/*           - Root threads
// /docs/*              - Docs
// /settings/*          - Settings
// /keep-alive          - Health check

function isAuthorized(url, headers, apiKey) {
  const authHeader = headers.get("Authorization");
  if (authHeader === `Bearer ${apiKey}`) return true;
  if (headers.get("x-api-key") === apiKey) return true;
  if (headers.get("x-goog-api-key") === apiKey) return true;

  const key = url.searchParams.get("key");
  if (key === apiKey) return true;

  const authToken = url.searchParams.get("auth_token");
  if (authToken === apiKey) return true;

  return false;
}

// Fixes empty text content blocks in the messages array.
// Some clients (Amp 👀) have a bug where tool results sometimes have empty
// text content, which Anthropic rejects with "text content blocks must be non-empty".
// This function replaces empty text with an error message so the request can proceed.
// Returns true if any fixes were made.
// If analytics binding is provided, writes a data point for each fix.
function fixEmptyTextBlocks(messages, analytics) {
  if (!Array.isArray(messages)) return false;

  let fixed = false;

  for (const msg of messages) {
    if (!msg.content || !Array.isArray(msg.content)) continue;

    for (const block of msg.content) {
      // Check tool_result content blocks for empty text
      if (block.type === "tool_result" && Array.isArray(block.content)) {
        for (const inner of block.content) {
          if (inner.type === "text" && inner.text === "") {
            console.warn("EMPTY_CONTENT_FIX", {
              tool_use_id: block.tool_use_id,
              message_role: msg.role,
            });
            if (analytics) {
              analytics.writeDataPoint({
                blobs: [block.tool_use_id || "unknown", msg.role || "unknown"],
                indexes: ["empty_content_fix"],
              });
            }
            inner.text = `<error>EMPTY_CONTENT_ERROR (tool_use_id=${block.tool_use_id}): The tool returned empty content due to a client bug. Please retry this exact tool call.</error>`;
            fixed = true;
          }
        }
      }
    }
  }

  return fixed;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!isAuthorized(url, request.headers, env.API_KEY)) {
      return new Response("Unauthorized: Invalid or missing API key", {
        status: 401,
        headers: { "Content-Type": "text/plain" },
      });
    }

    const category = getRequestCategory(url.pathname);

    env.ANALYTICS.writeDataPoint({
      blobs: [category, request.method, url.pathname],
      indexes: ["request"],
    });

    // Clone headers and add Access service token for origin auth
    const headers = new Headers(request.headers);
    headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
    headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);

    let targetUrl;
    let body = request.body;

    if (category === "provider") {
      // Route LLM requests through AI Gateway
      // https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/custom-{provider_slug}/{path}
      targetUrl = `${GATEWAY_BASE}/${env.ACCOUNT_ID}/${env.GATEWAY_ID}/custom-cli-proxy-api${url.pathname}${url.search}`;
      headers.set("cf-aig-authorization", `Bearer ${env.AIG_TOKEN}`);

      // Fix empty text blocks in Amp's Anthropic requests (workaround for Amp client bug)
      // Only Amp uses /api/provider/... paths; other clients use /v1/messages directly
      if (
        request.method === "POST" &&
        url.pathname.startsWith("/api/provider/anthropic/") &&
        url.pathname.endsWith("/messages")
      ) {
        body = await request.text();
        try {
          const parsed = JSON.parse(body);
          if (fixEmptyTextBlocks(parsed.messages, env.ANALYTICS)) {
            body = JSON.stringify(parsed);
          }
        } catch {
          // If JSON parsing fails, body already has the raw text - upstream will handle the error
        }
      }
    } else {
      // Route non-LLM requests directly to origin
      targetUrl = `${ORIGIN}${url.pathname}${url.search}`;
    }

    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      redirect: "follow",
    });

    return response;
  },
};
