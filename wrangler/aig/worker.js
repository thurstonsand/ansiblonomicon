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
