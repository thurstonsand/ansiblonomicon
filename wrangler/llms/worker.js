function classifyRequest(pathname) {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  const second = segments[1];

  switch (first) {
    case "v1":
    case "v1beta":
      return "provider";

    case "v0":
      if (second === "management") return "management";
      break;

    case "threads":
    case "docs":
    case "settings":
    case "auth":
      return "amp-admin";

    case "anthropic":
    case "codex":
    case "google":
    case "iflow":
    case "antigravity":
      if (second === "callback") return "oauth";
      break;

    case "threads.rss":
      return "amp-admin";

    case "api":
      switch (second) {
        case "provider":
          return "provider";
        case "tab":
          return "amp-tab";
        case "otel":
        case "telemetry":
          return "amp-telemetry";
        case "internal":
        case "threads":
        case "user":
        case "auth":
        case "meta":
        case "ads":
          return "amp-admin";
      }
      break;
  }

  return "other";
}

function extractProvider(pathname) {
  const segments = pathname.split("/").filter(Boolean);

  // /api/provider/{provider}/...
  if (segments[0] === "api" && segments[1] === "provider" && segments[2]) {
    return segments[2];
  }

  // /v1beta/... routes are Gemini
  if (segments[0] === "v1beta") {
    return "google";
  }

  // /v1/... routes - determine by endpoint pattern (matches origin routing)
  if (segments[0] === "v1") {
    // /v1/messages or /v1/messages/count_tokens → Anthropic
    if (segments[1] === "messages") return "anthropic";
    // /v1/chat/completions, /v1/completions, /v1/responses, /v1/models → OpenAI
    return "openai";
  }

  return "";
}

async function extractModel(pathname, request) {
  // Gemini: model in URL path
  // /v1beta/models/{model}:generateContent
  // /api/provider/google/v1beta1/publishers/google/models/{model}:generateContent
  const geminiMatch = pathname.match(/\/models\/([^/:]+)/);
  if (geminiMatch) return geminiMatch[1];

  // Anthropic/OpenAI: model in request body
  // Only parse for POST requests to provider endpoints
  if (request.method === "POST") {
    try {
      const clone = request.clone();
      const body = await clone.json();
      if (body.model) return body.model;
    } catch (err) {
      console.warn({ event: "extractModel_failed", pathname, error: err.message });
    }
  }

  return "";
}

function extractClient(headers) {
  // Prefer Amp's custom header
  const ampClient = headers.get("x-amp-client-application");
  if (ampClient) return ampClient;

  // Fall back to User-Agent
  const ua = headers.get("user-agent") || "";

  // Simplify common user agents
  if (ua.startsWith("Bun/")) return "Bun";
  if (ua.startsWith("node")) return "node";
  if (ua.includes("google-genai-sdk")) return "google-sdk";
  if (ua.includes("OTel-OTLP")) return "otel";

  return ua.split("/")[0] || "unknown";
}

function isAuthorized(url, headers, apiKey) {
  // Check Authorization header (Bearer token)
  const authHeader = headers.get("Authorization");
  if (authHeader === `Bearer ${apiKey}`) return true;

  // Check X-Api-Key header
  if (headers.get("x-api-key") === apiKey) return true;

  // Check X-Goog-Api-Key header
  if (headers.get("x-goog-api-key") === apiKey) return true;

  // Check query parameters
  const key = url.searchParams.get("key");
  if (key === apiKey) return true;

  const authToken = url.searchParams.get("auth_token");
  if (authToken === apiKey) return true;

  return false;
}

function extractTokens(body) {
  if (!body) return { input: 0, output: 0 };

  // Anthropic: usage.input_tokens, usage.output_tokens
  if (body.usage?.input_tokens !== undefined) {
    return {
      input: body.usage.input_tokens || 0,
      output: body.usage.output_tokens || 0,
    };
  }

  // OpenAI: usage.prompt_tokens, usage.completion_tokens
  if (body.usage?.prompt_tokens !== undefined) {
    return {
      input: body.usage.prompt_tokens || 0,
      output: body.usage.completion_tokens || 0,
    };
  }

  // Gemini: usageMetadata.promptTokenCount, usageMetadata.candidatesTokenCount
  // For thinking models, thoughtsTokenCount is included in totalTokenCount but not candidatesTokenCount
  if (body.usageMetadata?.promptTokenCount !== undefined) {
    const thoughtsTokens = body.usageMetadata.thoughtsTokenCount || 0;
    return {
      input: body.usageMetadata.promptTokenCount || 0,
      output: (body.usageMetadata.candidatesTokenCount || 0) + thoughtsTokens,
    };
  }

  return { input: 0, output: 0 };
}

async function prepareStreamingRequest(request, provider) {
  if (request.method !== "POST") return { request, modified: false };

  // Only modify OpenAI requests to inject stream_options
  if (provider !== "openai") return { request, modified: false };

  try {
    const clone = request.clone();
    const body = await clone.json();

    // Only modify if streaming is enabled
    if (!body.stream) return { request, modified: false };

    // Don't override if explicitly set to false
    if (body.stream_options?.include_usage === false) {
      return { request, modified: false };
    }

    body.stream_options = { ...body.stream_options, include_usage: true };

    // Create new request with modified body
    const newRequest = new Request(request.url, {
      method: request.method,
      headers: request.headers,
      body: JSON.stringify(body),
    });

    return { request: newRequest, modified: true };
  } catch (err) {
    console.warn({ event: "prepareStreamingRequest_failed", error: err.message });
    return { request, modified: false };
  }
}

function createTokenTrackingStream(response) {
  let tokens = { input: 0, output: 0 };
  let buffer = "";
  let resolveUsage;
  const usagePromise = new Promise((resolve) => { resolveUsage = resolve; });

  const transform = new TransformStream({
    transform(chunk, controller) {
      controller.enqueue(chunk);

      // Decode chunk and add to buffer for SSE parsing
      const text = new TextDecoder().decode(chunk);
      buffer += text;

      // Parse complete SSE events (lines ending with \n\n)
      const events = buffer.split("\n\n");
      buffer = events.pop() || ""; // Keep incomplete event in buffer

      for (const event of events) {
        const dataMatch = event.match(/^data:\s*(.+)$/m);
        if (!dataMatch) continue;

        const data = dataMatch[1].trim();
        if (data === "[DONE]") continue;

        try {
          const parsed = JSON.parse(data);
          const extracted = extractTokens(parsed);
          if (extracted.input > 0 || extracted.output > 0) {
            tokens = extracted;
          }
        } catch (err) {
          console.debug({ event: "sse_parse_failed", data: data.slice(0, 100), error: err.message });
        }
      }
    },

    flush() {
      // Process any remaining buffer
      if (buffer.trim()) {
        const dataMatch = buffer.match(/^data:\s*(.+)$/m);
        if (dataMatch) {
          try {
            const parsed = JSON.parse(dataMatch[1].trim());
            const extracted = extractTokens(parsed);
            if (extracted.input > 0 || extracted.output > 0) {
              tokens = extracted;
            }
          } catch {}
        }
      }
      resolveUsage(tokens);
    },
  });

  const newBody = response.body.pipeThrough(transform);
  const newResponse = new Response(newBody, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });

  return { response: newResponse, usagePromise };
}

export default {
  async fetch(request, env, ctx) {
    const start = Date.now();
    const url = new URL(request.url);
    const headers = request.headers;

    const requestType = classifyRequest(url.pathname);
    const provider = extractProvider(url.pathname);
    const client = extractClient(headers);

    // Only parse body for provider requests (to extract model)
    const model = requestType === "provider"
      ? await extractModel(url.pathname, request)
      : "";

    if (!isAuthorized(url, headers, env.API_KEY)) {
      env.ANALYTICS?.writeDataPoint({
        blobs: [url.pathname, "401", requestType, provider, model, client],
        doubles: [Date.now() - start, 0, 0],
        indexes: ["unauthorized"],
      });
      return new Response("Unauthorized: Invalid or missing API key", {
        status: 401,
        headers: { "Content-Type": "text/plain" },
      });
    }

    url.hostname = env.ORIGIN_HOSTNAME;

    // For provider requests, prepare for streaming (may modify request)
    let finalRequest = request;
    if (requestType === "provider") {
      const prepared = await prepareStreamingRequest(request, provider);
      finalRequest = prepared.request;
    }

    const response = await fetch(new Request(url.toString(), {
      method: finalRequest.method,
      headers: finalRequest.headers,
      body: finalRequest.body,
      redirect: "follow",
    }));

    // Determine if response is streaming
    const contentType = response.headers.get("content-type") || "";
    const isStreaming = contentType.includes("stream") || contentType.includes("event-stream");

    if (requestType === "provider" && isStreaming && response.ok) {
      // Streaming response: track tokens via TransformStream
      const { response: trackedResponse, usagePromise } = createTokenTrackingStream(response);

      ctx.waitUntil(
        usagePromise.then((tokens) => {
          env.ANALYTICS?.writeDataPoint({
            blobs: [url.pathname, String(response.status), requestType, provider, model, client],
            doubles: [Date.now() - start, tokens.input, tokens.output],
            indexes: [request.method],
          });
        })
      );

      return trackedResponse;
    }

    // Non-streaming response
    let inputTokens = 0;
    let outputTokens = 0;

    if (requestType === "provider" && response.ok) {
      try {
        const clone = response.clone();
        const body = await clone.json();
        const tokens = extractTokens(body);
        inputTokens = tokens.input;
        outputTokens = tokens.output;
      } catch (err) {
        console.warn({ event: "token_extraction_failed", pathname: url.pathname, error: err.message });
      }
    }

    env.ANALYTICS?.writeDataPoint({
      blobs: [url.pathname, String(response.status), requestType, provider, model, client],
      doubles: [Date.now() - start, inputTokens, outputTokens],
      indexes: [request.method],
    });

    return response;
  },
};
