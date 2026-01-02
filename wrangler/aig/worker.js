// AI Gateway Proxy Worker
// Routes LLM requests through Cloudflare AI Gateway for observability, caching, rate limiting
// Non-LLM requests go directly to origin
//
// Request flow (LLM):
//   aig.thurstons.house/{path} → AI Gateway → custom-cli-proxy-api/{path} → cli-proxy-api.thurstons.house/{path}
// Request flow (OpenAI-only, e.g. /v1/responses/compact):
//   aig.thurstons.house/v1/responses/compact
//     → AI Gateway → custom-cli-proxy-api/v0/management/api-call
//     → cli-proxy-api management API (with OAuth token refresh)
//     → api.openai.com/v1/responses/compact
//   See COMPACT_FALLBACK.md if AI Gateway has issues with this flow.
// Request flow (other):
//   aig.thurstons.house/{path} → cli-proxy-api.thurstons.house/{path}

const GATEWAY_BASE = "https://gateway.ai.cloudflare.com/v1";
const ORIGIN = "https://cli-proxy-api.thurstons.house";
const OPENAI_BASE = "https://api.openai.com";

// Paths that need special handling via cli-proxy-api's management API
// These endpoints aren't natively supported by cli-proxy-api but can be proxied
// to OpenAI using stored OAuth credentials
function isProxiedOpenAIPath(pathname) {
  // /v1/responses/compact - Codex CLI compaction endpoint (not in cli-proxy-api)
  if (pathname === "/v1/responses/compact") return true;
  return false;
}

// Proxy a request to OpenAI via cli-proxy-api's management API
// This allows using stored OAuth tokens with automatic refresh
async function proxyViaManagementAPI(request, env, pathname, search) {
  const requestBody = await request.text();

  const apiCallBody = JSON.stringify({
    auth_index: env.CODEX_AUTH_INDEX,
    method: request.method,
    url: `${OPENAI_BASE}${pathname}${search}`,
    header: {
      Authorization: "Bearer $TOKEN$",
      "Content-Type": "application/json",
    },
    data: requestBody,
  });

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${env.CLI_PROXY_API_ADMIN_KEY}`);
  headers.set("Content-Type", "application/json");
  headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
  headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);

  // Route through AI Gateway for observability
  // If this causes issues, see COMPACT_FALLBACK.md for direct routing
  const targetUrl = `${GATEWAY_BASE}/${env.ACCOUNT_ID}/${env.GATEWAY_ID}/custom-cli-proxy-api/v0/management/api-call`;
  headers.set("cf-aig-authorization", `Bearer ${env.AIG_TOKEN}`);

  const response = await fetch(targetUrl, {
    method: "POST",
    headers,
    body: apiCallBody,
  });

  if (!response.ok) {
    // Pass through errors from the management API
    return response;
  }

  // The management API returns {status_code, header, body}
  // We need to reconstruct the actual HTTP response
  const result = await response.json();

  // Build response headers from the proxied response
  const responseHeaders = new Headers();
  if (result.header) {
    for (const [key, values] of Object.entries(result.header)) {
      // Skip hop-by-hop headers
      if (
        ["transfer-encoding", "connection", "keep-alive"].includes(
          key.toLowerCase()
        )
      )
        continue;
      for (const value of values) {
        responseHeaders.append(key, value);
      }
    }
  }

  return new Response(result.body, {
    status: result.status_code,
    headers: responseHeaders,
  });
}

function isProviderPath(pathname) {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  const second = segments[1];

  // /v1/... - OpenAI-compatible routes (chat/completions, messages, models, etc.)
  // /v1beta/... - Gemini-compatible routes
  if (first === "v1" || first === "v1beta") return true;

  // /api/provider/... - Amp CLI provider aliases (LLM calls to various providers)
  if (first === "api" && second === "provider") return true;

  return false;
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!isAuthorized(url, request.headers, env.API_KEY)) {
      return new Response("Unauthorized: Invalid or missing API key", {
        status: 401,
        headers: { "Content-Type": "text/plain" },
      });
    }

    // Check for paths that need proxying via cli-proxy-api's management API
    // These are OpenAI endpoints not natively supported by cli-proxy-api
    if (isProxiedOpenAIPath(url.pathname)) {
      return proxyViaManagementAPI(request, env, url.pathname, url.search);
    }

    // Clone headers and add Access service token for origin auth
    const headers = new Headers(request.headers);
    headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
    headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);

    let targetUrl;
    if (isProviderPath(url.pathname)) {
      // Route LLM requests through AI Gateway
      // https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/custom-{provider_slug}/{path}
      targetUrl = `${GATEWAY_BASE}/${env.ACCOUNT_ID}/${env.GATEWAY_ID}/custom-cli-proxy-api${url.pathname}${url.search}`;
      headers.set("cf-aig-authorization", `Bearer ${env.AIG_TOKEN}`);
    } else {
      // Route non-LLM requests directly to origin
      targetUrl = `${ORIGIN}${url.pathname}${url.search}`;
    }

    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: request.body,
      redirect: "follow",
    });

    return response;
  },
};
