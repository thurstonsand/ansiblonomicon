// Webhook Gateway Worker
// Validates inbound webhooks at the edge before forwarding to Clawdbot via Cloudflare Tunnel
//
// Routes:
//   /gmail/*  → Validate Google OIDC JWT → Forward to gog via internal tunnel
//   /github/* → Validate HMAC-SHA256    → Forward to Clawdbot (future)
//   /health/* → Validate CF Access Token → Forward to Clawdbot agent hook
//
// Global variables (cachedKeys, cacheExpiry) persist within a single isolate but
// are NOT guaranteed to persist across requests. Cloudflare may spin up multiple
// isolates, and any isolate can be evicted at any time. The caching is opportunistic
// and reduces latency when hitting the same isolate.

const GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs";

// Opportunistic cache for Google's public keys
let cachedKeys: GoogleJWKS | null = null;
let cacheExpiry = 0;

// --- Google JWKS types ---

interface GoogleJWK {
  kid: string;
  kty: string;
  alg: string;
  use: string;
  n: string;
  e: string;
}

interface GoogleJWKS {
  keys: GoogleJWK[];
}

interface GoogleJWTHeader {
  alg: string;
  kid: string;
  typ: string;
}

interface GoogleJWTPayload {
  iss: string;
  aud: string;
  email: string;
  email_verified: boolean;
  exp: number;
  iat: number;
  sub?: string;
}

// --- JWT Verification ---

async function getGooglePublicKeys(): Promise<GoogleJWKS> {
  const now = Date.now();
  if (cachedKeys && now < cacheExpiry) {
    return cachedKeys;
  }

  const response = await fetch(GOOGLE_CERTS_URL);
  if (!response.ok) {
    throw new Error(`Failed to fetch Google public keys: ${response.status}`);
  }

  cachedKeys = (await response.json()) as GoogleJWKS;

  const cacheControl = response.headers.get("cache-control");
  const maxAgeMatch = cacheControl?.match(/max-age=(\d+)/);
  const maxAge = maxAgeMatch ? parseInt(maxAgeMatch[1], 10) : 3600;
  cacheExpiry = now + maxAge * 1000;

  return cachedKeys;
}

function base64UrlDecode(str: string): Uint8Array {
  const base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function base64UrlDecodeToString(str: string): string {
  return new TextDecoder().decode(base64UrlDecode(str));
}

async function importRsaKey(jwk: GoogleJWK): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "jwk",
    {
      kty: jwk.kty,
      n: jwk.n,
      e: jwk.e,
      alg: jwk.alg,
      use: jwk.use,
    },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"]
  );
}

type JWTResult =
  | { valid: true; payload: GoogleJWTPayload }
  | { valid: false; error: string };

async function verifyGoogleJWT(
  token: string,
  expectedAudience: string,
  expectedEmail: string
): Promise<JWTResult> {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return { valid: false, error: "Invalid JWT format" };
  }

  const [headerB64, payloadB64, signatureB64] = parts;

  let header: GoogleJWTHeader;
  let payload: GoogleJWTPayload;
  try {
    header = JSON.parse(base64UrlDecodeToString(headerB64)) as GoogleJWTHeader;
    payload = JSON.parse(base64UrlDecodeToString(payloadB64)) as GoogleJWTPayload;
  } catch {
    return { valid: false, error: "Failed to decode JWT" };
  }

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp < now) {
    return { valid: false, error: "Token expired" };
  }

  if (payload.aud !== expectedAudience) {
    return { valid: false, error: `Invalid audience: ${payload.aud}` };
  }

  if (payload.email !== expectedEmail) {
    return { valid: false, error: `Invalid email: ${payload.email}` };
  }

  if (payload.iss !== "https://accounts.google.com") {
    return { valid: false, error: `Invalid issuer: ${payload.iss}` };
  }

  const keys = await getGooglePublicKeys();
  const key = keys.keys.find((k) => k.kid === header.kid);
  if (!key) {
    return { valid: false, error: `Unknown key ID: ${header.kid}` };
  }

  const cryptoKey = await importRsaKey(key);
  const signedData = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = base64UrlDecode(signatureB64);

  const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", cryptoKey, signature, signedData);

  if (!valid) {
    return { valid: false, error: "Invalid signature" };
  }

  return { valid: true, payload };
}

// --- Analytics ---

interface Analytics {
  track(index: string, ...blobs: string[]): void;
}

function createAnalytics(dataset?: AnalyticsEngineDataset): Analytics {
  return {
    track(index, ...blobs) {
      dataset?.writeDataPoint({ blobs, indexes: [index] });
    },
  };
}

function getStatusBucket(status: number): string {
  if (status >= 200 && status < 300) return "2xx";
  if (status >= 400 && status < 500) return "4xx";
  if (status >= 500) return "5xx";
  return "other";
}

// --- Route Handlers ---

async function handleGmailPubSub(request: Request, env: Env, analytics: Analytics): Promise<Response> {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    console.error("gmail: missing Authorization header");
    analytics.track("gmail", "auth_fail", "401");
    return new Response("Unauthorized", { status: 401 });
  }

  const token = authHeader.slice(7);
  const result = await verifyGoogleJWT(token, env.GOOGLE_PUBSUB_AUDIENCE, env.GOOGLE_PUBSUB_SERVICE_ACCOUNT);

  if (!result.valid) {
    console.error(`gmail: JWT invalid: ${result.error}`);
    analytics.track("gmail", "auth_fail", "401");
    return new Response(`Unauthorized: ${result.error}`, { status: 401 });
  }

  const gogUrl = `${env.GOG_GMAIL_URL}?token=${env.GOG_GMAIL_TOKEN}`;

  try {
    const forwardResponse = await env.GOG_SERVICE.fetch(gogUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });

    const statusBucket = getStatusBucket(forwardResponse.status);
    if (forwardResponse.ok) {
      console.log(`gmail: forwarded ok status=${forwardResponse.status}`);
    } else {
      console.error(`gmail: forward failed status=${forwardResponse.status}`);
    }
    analytics.track("gmail", "forward", statusBucket, String(forwardResponse.status));

    return new Response(forwardResponse.body, {
      status: forwardResponse.status,
      headers: forwardResponse.headers,
    });
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err);
    console.error(`gmail: forward error: ${error}`);
    analytics.track("gmail", "forward", "5xx", "502");
    return new Response(`Forward failed: ${error}`, { status: 502 });
  }
}

async function handleGitHubWebhook(request: Request, env: Env): Promise<Response> {
  if (!env.GITHUB_WEBHOOK_SECRET) {
    console.error("GitHub webhook: Secret not configured");
    return new Response("Not configured", { status: 501 });
  }

  const signature = request.headers.get("X-Hub-Signature-256");
  if (!signature) {
    console.error("GitHub webhook: Missing signature header");
    return new Response("Unauthorized", { status: 401 });
  }

  const body = await request.text();
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(env.GITHUB_WEBHOOK_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const expectedSig = "sha256=" + Array.from(new Uint8Array(mac), (b) => b.toString(16).padStart(2, "0")).join("");

  if (signature !== expectedSig) {
    console.error("GitHub webhook: Invalid signature");
    return new Response("Unauthorized", { status: 401 });
  }

  const url = new URL(request.url);
  const pathAfterGithub = url.pathname.replace(/^\/github\/?/, "");
  const forwardUrl = `${env.CLAWDBOT_HOOKS_URL}/github${pathAfterGithub ? "/" + pathAfterGithub : ""}`;

  const forwardResponse = await fetch(forwardUrl, {
    method: request.method,
    headers: request.headers,
    body,
  });

  return new Response(forwardResponse.body, {
    status: forwardResponse.status,
    headers: forwardResponse.headers,
  });
}

// --- Health Data Handler ---
// Auth handled by Cloudflare Access at edge (service token validation)
// Worker just parses payload and forwards to Clawdbot agent hook
// Used by iOS Shortcuts to push Apple Health data

interface HealthPayload {
  sleep?: {
    duration_hours?: number;
    quality?: string;
    bed_time?: string;
    wake_time?: string;
  };
  heart_rate?: {
    resting?: number;
    current?: number;
  };
  activity?: {
    steps?: number;
    active_energy?: number;
    exercise_minutes?: number;
  };
  hrv?: number;
  timestamp?: string;
}

async function handleHealth(request: Request, env: Env, analytics: Analytics): Promise<Response> {
  // Auth already validated by Cloudflare Access at edge

  // Validate OPENCLAW_HOOKS_TOKEN is configured
  if (!env.OPENCLAW_HOOKS_TOKEN) {
    console.error("health: OPENCLAW_HOOKS_TOKEN not configured");
    analytics.track("health", "config_error", "501");
    return new Response("Not configured", { status: 501 });
  }

  // Parse health data payload
  let healthData: HealthPayload;
  try {
    healthData = (await request.json()) as HealthPayload;
  } catch {
    console.error("health: invalid JSON payload");
    analytics.track("health", "parse_error", "400");
    return new Response("Bad Request: Invalid JSON", { status: 400 });
  }

  // Validate at least some health data is present
  const hasData = healthData.sleep || healthData.heart_rate || healthData.activity || healthData.hrv !== undefined;
  if (!hasData) {
    console.error("health: empty payload");
    analytics.track("health", "parse_error", "400");
    return new Response("Bad Request: No health data provided", { status: 400 });
  }

  // Format health data as a readable message for the agent
  const parts: string[] = ["Apple Health update received:"];

  if (healthData.sleep) {
    const s = healthData.sleep;
    if (s.duration_hours !== undefined) parts.push(`• Sleep: ${s.duration_hours.toFixed(1)}h`);
    if (s.quality) parts.push(`  Quality: ${s.quality}`);
    if (s.bed_time && s.wake_time) parts.push(`  ${s.bed_time} → ${s.wake_time}`);
  }

  if (healthData.heart_rate) {
    const hr = healthData.heart_rate;
    if (hr.resting !== undefined) parts.push(`• Resting HR: ${hr.resting} bpm`);
    if (hr.current !== undefined) parts.push(`• Current HR: ${hr.current} bpm`);
  }

  if (healthData.activity) {
    const a = healthData.activity;
    if (a.steps !== undefined) parts.push(`• Steps: ${a.steps.toLocaleString()}`);
    if (a.active_energy !== undefined) parts.push(`• Active energy: ${a.active_energy} kcal`);
    if (a.exercise_minutes !== undefined) parts.push(`• Exercise: ${a.exercise_minutes} min`);
  }

  if (healthData.hrv !== undefined) {
    parts.push(`• HRV: ${healthData.hrv} ms`);
  }

  if (healthData.timestamp) {
    parts.push(`\nTimestamp: ${healthData.timestamp}`);
  }

  const message = parts.join("\n");

  // Forward to Clawdbot health hook
  // Clawdbot config handles routing, session isolation, and delivery
  const healthPayload = {
    message,
    raw: healthData,
  };

  try {
    // Forward via VPC service binding
    const forwardResponse = await env.CLAWDBOT_SERVICE.fetch("http://clawdbot/hooks/health", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.OPENCLAW_HOOKS_TOKEN}`,
      },
      body: JSON.stringify(healthPayload),
    });

    const statusBucket = getStatusBucket(forwardResponse.status);
    if (forwardResponse.ok) {
      console.log(`health: forwarded ok status=${forwardResponse.status}`);
    } else {
      const errorText = await forwardResponse.text();
      console.error(`health: forward failed status=${forwardResponse.status} body=${errorText}`);
    }
    analytics.track("health", "forward", statusBucket, String(forwardResponse.status));

    return new Response(forwardResponse.ok ? "Accepted" : "Forward failed", {
      status: forwardResponse.ok ? 202 : 502,
    });
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err);
    console.error(`health: forward error: ${error}`);
    analytics.track("health", "forward", "5xx", "502");
    return new Response(`Forward failed: ${error}`, { status: 502 });
  }
}

// --- Main Handler ---

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const analytics = createAnalytics(env.ANALYTICS);

    if (url.pathname.startsWith("/gmail")) {
      return handleGmailPubSub(request, env, analytics);
    }

    if (url.pathname.startsWith("/github")) {
      return handleGitHubWebhook(request, env);
    }

    if (url.pathname.startsWith("/health")) {
      return handleHealth(request, env, analytics);
    }

    return new Response("Not Found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
