#!/usr/bin/env bun
/**
 * Test harness for worker.js analytics extraction
 * Run with: bun test worker.test.js
 * Or: bun worker.test.js (for quick summary table)
 */

import { readFileSync } from "fs";
import { describe, test, expect } from "bun:test";

// Extract functions from worker.js without modifying it
const workerCode = readFileSync(new URL("./worker.js", import.meta.url), "utf-8");
const functionsCode = workerCode.replace(/export default \{[\s\S]*\};?\s*$/, "");

const evalFunctions = new Function(`
  ${functionsCode}
  return { classifyRequest, extractProvider, extractModel, extractClient, isAuthorized, extractTokens };
`);
const { classifyRequest, extractProvider, extractModel, extractClient, isAuthorized, extractTokens } = evalFunctions();

// Mock Request class for testing
function mockRequest(method, headers = {}, body = null) {
  const headerMap = new Map(
    Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v])
  );
  return {
    method,
    headers: {
      get: (name) => headerMap.get(name.toLowerCase()) || null,
    },
    clone: function() { return mockRequest(method, headers, body); },
    json: async () => {
      if (!body) throw new Error("No body");
      return typeof body === "string" ? JSON.parse(body) : body;
    },
  };
}

// Full analytics extraction helper (mirrors worker logic)
async function extractAnalytics(path, method, headers = {}, body = null) {
  const headerObj = {
    get: (name) => headers[name] || headers[name.toLowerCase()] || null,
  };
  const request = mockRequest(method, headers, body);
  
  const requestType = classifyRequest(path);
  const provider = extractProvider(path);
  const model = requestType === "provider" ? await extractModel(path, request) : "";
  const client = extractClient(headerObj);
  
  return { requestType, provider, model, client };
}

// ============================================================================
// ANTHROPIC API TESTS
// ============================================================================

describe("Anthropic API", () => {
  const anthropicHeaders = {
    "anthropic-version": "2024-01-01",
    "x-amp-client-application": "VS Code CLI",
  };

  describe("/api/provider/anthropic/v1/messages", () => {
    const path = "/api/provider/anthropic/v1/messages";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", anthropicHeaders, {
        model: "claude-sonnet-4-20250514",
        messages: [{ role: "user", content: "Hello" }],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "anthropic",
        model: "claude-sonnet-4-20250514",
        client: "VS Code CLI",
      });
    });

    test("handles claude-3-opus model", async () => {
      const result = await extractAnalytics(path, "POST", anthropicHeaders, {
        model: "claude-3-opus-20240229",
        messages: [],
      });
      expect(result.model).toBe("claude-3-opus-20240229");
    });

    test("handles claude-3-haiku model", async () => {
      const result = await extractAnalytics(path, "POST", anthropicHeaders, {
        model: "claude-3-haiku-20240307",
        messages: [],
      });
      expect(result.model).toBe("claude-3-haiku-20240307");
    });
  });

  describe("/api/provider/anthropic/v1/messages/count_tokens", () => {
    const path = "/api/provider/anthropic/v1/messages/count_tokens";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", anthropicHeaders, {
        model: "claude-sonnet-4-20250514",
        messages: [{ role: "user", content: "Hello" }],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "anthropic",
        model: "claude-sonnet-4-20250514",
        client: "VS Code CLI",
      });
    });
  });

  describe("/v1/messages (direct Anthropic)", () => {
    const path = "/v1/messages";

    test("extracts provider from anthropic-version header", async () => {
      const result = await extractAnalytics(path, "POST", anthropicHeaders, {
        model: "claude-3-5-sonnet-20241022",
        messages: [],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "anthropic",
        model: "claude-3-5-sonnet-20241022",
        client: "VS Code CLI",
      });
    });

    test("detects anthropic from path pattern (no header needed)", async () => {
      const result = await extractAnalytics(path, "POST", { "x-amp-client-application": "VS Code CLI" }, {
        model: "claude-3-5-sonnet-20241022",
        messages: [],
      });
      expect(result.provider).toBe("anthropic"); // Path-based detection
    });
  });

  describe("/v1/messages/count_tokens (direct Anthropic)", () => {
    const path = "/v1/messages/count_tokens";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", anthropicHeaders, {
        model: "claude-sonnet-4-20250514",
        messages: [],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "anthropic",
        model: "claude-sonnet-4-20250514",
        client: "VS Code CLI",
      });
    });
  });
});

// ============================================================================
// OPENAI API TESTS
// ============================================================================

describe("OpenAI API", () => {
  const openaiHeaders = {
    "x-amp-client-application": "VS Code Insiders",
  };

  describe("/api/provider/openai/v1/chat/completions", () => {
    const path = "/api/provider/openai/v1/chat/completions";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-4o",
        messages: [{ role: "user", content: "Hello" }],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "gpt-4o",
        client: "VS Code Insiders",
      });
    });

    test("handles gpt-4o-mini model", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-4o-mini",
        messages: [],
      });
      expect(result.model).toBe("gpt-4o-mini");
    });

    test("handles gpt-4-turbo model", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-4-turbo-2024-04-09",
        messages: [],
      });
      expect(result.model).toBe("gpt-4-turbo-2024-04-09");
    });

    test("handles o1 model", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "o1-preview",
        messages: [],
      });
      expect(result.model).toBe("o1-preview");
    });
  });

  describe("/api/provider/openai/v1/completions", () => {
    const path = "/api/provider/openai/v1/completions";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-3.5-turbo-instruct",
        prompt: "Hello",
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "gpt-3.5-turbo-instruct",
        client: "VS Code Insiders",
      });
    });
  });

  describe("/api/provider/openai/v1/responses", () => {
    const path = "/api/provider/openai/v1/responses";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-4o",
        input: "Hello",
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "gpt-4o",
        client: "VS Code Insiders",
      });
    });
  });

  describe("/v1/chat/completions (direct OpenAI)", () => {
    const path = "/v1/chat/completions";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-4o",
        messages: [],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "gpt-4o",
        client: "VS Code Insiders",
      });
    });
  });

  describe("/v1/completions (direct OpenAI)", () => {
    const path = "/v1/completions";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-3.5-turbo-instruct",
        prompt: "Hello",
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "gpt-3.5-turbo-instruct",
        client: "VS Code Insiders",
      });
    });
  });

  describe("/v1/responses (direct OpenAI)", () => {
    const path = "/v1/responses";

    test("extracts all analytics fields", async () => {
      const result = await extractAnalytics(path, "POST", openaiHeaders, {
        model: "gpt-4o-mini",
        input: "test",
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "gpt-4o-mini",
        client: "VS Code Insiders",
      });
    });
  });

  describe("/v1/models (list models)", () => {
    const path = "/v1/models";

    test("GET request has no model", async () => {
      const result = await extractAnalytics(path, "GET", openaiHeaders, null);
      expect(result).toEqual({
        requestType: "provider",
        provider: "openai",
        model: "",
        client: "VS Code Insiders",
      });
    });
  });
});

// ============================================================================
// GOOGLE GEMINI API TESTS
// ============================================================================

describe("Google Gemini API", () => {
  const geminiHeaders = {
    "x-goog-api-key": "AIza...",
    "x-amp-client-application": "VS Code CLI",
  };

  describe("/api/provider/google/v1beta1/publishers/google/models/{model}:generateContent", () => {
    test("extracts gemini-2.0-flash model from path", async () => {
      const path = "/api/provider/google/v1beta1/publishers/google/models/gemini-2.0-flash:generateContent";
      const result = await extractAnalytics(path, "POST", geminiHeaders, {});
      expect(result).toEqual({
        requestType: "provider",
        provider: "google",
        model: "gemini-2.0-flash",
        client: "VS Code CLI",
      });
    });

    test("extracts gemini-3-pro-preview model from path", async () => {
      const path = "/api/provider/google/v1beta1/publishers/google/models/gemini-3-pro-preview:generateContent";
      const result = await extractAnalytics(path, "POST", geminiHeaders, {});
      expect(result.model).toBe("gemini-3-pro-preview");
    });

    test("extracts gemini-2.5-flash-lite model from path", async () => {
      const path = "/api/provider/google/v1beta1/publishers/google/models/gemini-2.5-flash-lite:generateContent";
      const result = await extractAnalytics(path, "POST", geminiHeaders, {});
      expect(result.model).toBe("gemini-2.5-flash-lite");
    });

    test("extracts gemini-1.5-pro model from path", async () => {
      const path = "/api/provider/google/v1beta1/publishers/google/models/gemini-1.5-pro:generateContent";
      const result = await extractAnalytics(path, "POST", geminiHeaders, {});
      expect(result.model).toBe("gemini-1.5-pro");
    });
  });

  describe("/api/provider/google/v1beta1/models/{model}:generateContent (alternate format)", () => {
    test("extracts model from shorter path format", async () => {
      const path = "/api/provider/google/v1beta1/models/gemini-pro:generateContent";
      const result = await extractAnalytics(path, "POST", geminiHeaders, {});
      expect(result).toEqual({
        requestType: "provider",
        provider: "google",
        model: "gemini-pro",
        client: "VS Code CLI",
      });
    });
  });

  describe("/v1beta/models/{model}:generateContent (direct Gemini)", () => {
    test("extracts model from direct path", async () => {
      const path = "/v1beta/models/gemini-2.0-flash:generateContent";
      const result = await extractAnalytics(path, "POST", geminiHeaders, {});
      expect(result).toEqual({
        requestType: "provider",
        provider: "google",
        model: "gemini-2.0-flash",
        client: "VS Code CLI",
      });
    });

    test("detects google from v1beta path (no header needed)", async () => {
      const path = "/v1beta/models/gemini-2.0-flash:generateContent";
      const result = await extractAnalytics(path, "POST", { "x-amp-client-application": "VS Code CLI" }, {});
      expect(result.provider).toBe("google"); // Path-based detection for v1beta
      expect(result.model).toBe("gemini-2.0-flash"); // Model still extracted from path
    });
  });

  describe("/v1beta/models (list Gemini models)", () => {
    test("GET request for model listing", async () => {
      const path = "/v1beta/models";
      const result = await extractAnalytics(path, "GET", geminiHeaders, null);
      expect(result).toEqual({
        requestType: "provider",
        provider: "google",
        model: "",
        client: "VS Code CLI",
      });
    });
  });
});

// ============================================================================
// OTHER PROVIDER TESTS (Groq, Cerebras, etc.)
// ============================================================================

describe("Other Providers", () => {
  describe("/api/provider/groq/v1/chat/completions", () => {
    test("extracts groq provider", async () => {
      const path = "/api/provider/groq/v1/chat/completions";
      const result = await extractAnalytics(path, "POST", { "x-amp-client-application": "VS Code CLI" }, {
        model: "llama-3.1-70b-versatile",
        messages: [],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "groq",
        model: "llama-3.1-70b-versatile",
        client: "VS Code CLI",
      });
    });
  });

  describe("/api/provider/cerebras/v1/chat/completions", () => {
    test("extracts cerebras provider", async () => {
      const path = "/api/provider/cerebras/v1/chat/completions";
      const result = await extractAnalytics(path, "POST", { "x-amp-client-application": "VS Code CLI" }, {
        model: "llama3.1-8b",
        messages: [],
      });
      expect(result).toEqual({
        requestType: "provider",
        provider: "cerebras",
        model: "llama3.1-8b",
        client: "VS Code CLI",
      });
    });
  });
});

// ============================================================================
// AMP ADMIN ROUTES
// ============================================================================

describe("Amp Admin Routes", () => {
  const ampHeaders = { "x-amp-client-application": "VS Code CLI" };

  describe("/api/internal", () => {
    test("classifies as amp-admin with no provider/model", async () => {
      const result = await extractAnalytics("/api/internal", "POST", ampHeaders, {});
      expect(result).toEqual({
        requestType: "amp-admin",
        provider: "",
        model: "",
        client: "VS Code CLI",
      });
    });
  });

  describe("/api/threads/*", () => {
    test("/api/threads", async () => {
      const result = await extractAnalytics("/api/threads", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/api/threads/sync", async () => {
      const result = await extractAnalytics("/api/threads/sync", "POST", ampHeaders, {});
      expect(result.requestType).toBe("amp-admin");
    });

    test("/api/threads/T-123-456", async () => {
      const result = await extractAnalytics("/api/threads/T-123-456", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });
  });

  describe("/api/user/*", () => {
    test("/api/user", async () => {
      const result = await extractAnalytics("/api/user", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });
  });

  describe("/api/auth/*", () => {
    test("/api/auth", async () => {
      const result = await extractAnalytics("/api/auth", "POST", ampHeaders, {});
      expect(result.requestType).toBe("amp-admin");
    });
  });

  describe("/api/meta/*", () => {
    test("/api/meta", async () => {
      const result = await extractAnalytics("/api/meta", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });
  });

  describe("/api/ads/*", () => {
    test("/api/ads", async () => {
      const result = await extractAnalytics("/api/ads", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });
  });

  describe("Root-level amp routes", () => {
    test("/threads", async () => {
      const result = await extractAnalytics("/threads", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/threads/T-abc-123", async () => {
      const result = await extractAnalytics("/threads/T-abc-123", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/docs", async () => {
      const result = await extractAnalytics("/docs", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/docs/something", async () => {
      const result = await extractAnalytics("/docs/something", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/settings", async () => {
      const result = await extractAnalytics("/settings", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/auth", async () => {
      const result = await extractAnalytics("/auth", "POST", ampHeaders, {});
      expect(result.requestType).toBe("amp-admin");
    });

    test("/auth/callback", async () => {
      const result = await extractAnalytics("/auth/callback", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });

    test("/threads.rss", async () => {
      const result = await extractAnalytics("/threads.rss", "GET", ampHeaders, null);
      expect(result.requestType).toBe("amp-admin");
    });
  });
});

// ============================================================================
// AMP TAB ROUTES
// ============================================================================

describe("Amp Tab Routes", () => {
  const ampHeaders = { "x-amp-client-application": "VS Code CLI" };

  test("/api/tab", async () => {
    const result = await extractAnalytics("/api/tab", "POST", ampHeaders, {});
    expect(result).toEqual({
      requestType: "amp-tab",
      provider: "",
      model: "",
      client: "VS Code CLI",
    });
  });

  test("/api/tab/llm-proxy", async () => {
    const result = await extractAnalytics("/api/tab/llm-proxy", "POST", ampHeaders, {});
    expect(result.requestType).toBe("amp-tab");
  });
});

// ============================================================================
// AMP TELEMETRY ROUTES
// ============================================================================

describe("Amp Telemetry Routes", () => {
  describe("/api/telemetry/*", () => {
    test("/api/telemetry", async () => {
      const result = await extractAnalytics("/api/telemetry", "POST", { "user-agent": "node" }, {});
      expect(result).toEqual({
        requestType: "amp-telemetry",
        provider: "",
        model: "",
        client: "node",
      });
    });

    test("/api/telemetry/events", async () => {
      const result = await extractAnalytics("/api/telemetry/events", "POST", {}, {});
      expect(result.requestType).toBe("amp-telemetry");
    });
  });

  describe("/api/otel/*", () => {
    test("/api/otel", async () => {
      const result = await extractAnalytics("/api/otel", "POST", { "user-agent": "OTel-OTLP-Exporter/1.0" }, {});
      expect(result).toEqual({
        requestType: "amp-telemetry",
        provider: "",
        model: "",
        client: "otel",
      });
    });

    test("/api/otel/v1/metrics", async () => {
      const result = await extractAnalytics("/api/otel/v1/metrics", "POST", {}, {});
      expect(result.requestType).toBe("amp-telemetry");
    });

    test("/api/otel/v1/traces", async () => {
      const result = await extractAnalytics("/api/otel/v1/traces", "POST", {}, {});
      expect(result.requestType).toBe("amp-telemetry");
    });
  });
});

// ============================================================================
// MANAGEMENT ROUTES
// ============================================================================

describe("Management Routes", () => {
  test("/v0/management/config", async () => {
    const result = await extractAnalytics("/v0/management/config", "GET", {}, null);
    expect(result.requestType).toBe("management");
  });

  test("/v0/management/usage", async () => {
    const result = await extractAnalytics("/v0/management/usage", "GET", {}, null);
    expect(result.requestType).toBe("management");
  });

  test("/v0/management/api-keys", async () => {
    const result = await extractAnalytics("/v0/management/api-keys", "GET", {}, null);
    expect(result.requestType).toBe("management");
  });
});

// ============================================================================
// OAUTH CALLBACK ROUTES
// ============================================================================

describe("OAuth Callback Routes", () => {
  test("/anthropic/callback", async () => {
    const result = await extractAnalytics("/anthropic/callback", "GET", {}, null);
    expect(result.requestType).toBe("oauth");
  });

  test("/google/callback", async () => {
    const result = await extractAnalytics("/google/callback", "GET", {}, null);
    expect(result.requestType).toBe("oauth");
  });

  test("/codex/callback", async () => {
    const result = await extractAnalytics("/codex/callback", "GET", {}, null);
    expect(result.requestType).toBe("oauth");
  });

  test("/iflow/callback", async () => {
    const result = await extractAnalytics("/iflow/callback", "GET", {}, null);
    expect(result.requestType).toBe("oauth");
  });

  test("/antigravity/callback", async () => {
    const result = await extractAnalytics("/antigravity/callback", "GET", {}, null);
    expect(result.requestType).toBe("oauth");
  });

  test("/anthropic (without callback) is other", async () => {
    const result = await extractAnalytics("/anthropic", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });
});

// ============================================================================
// BOT/OTHER TRAFFIC
// ============================================================================

describe("Bot/Other Traffic", () => {
  test("/ root", async () => {
    const result = await extractAnalytics("/", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });

  test("/favicon.ico", async () => {
    const result = await extractAnalytics("/favicon.ico", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });

  test("/robots.txt", async () => {
    const result = await extractAnalytics("/robots.txt", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });

  test("/news.rss (bot traffic)", async () => {
    const result = await extractAnalytics("/news.rss", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });

  test("/swagger-ui.html", async () => {
    const result = await extractAnalytics("/swagger-ui.html", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });

  test("/graphql", async () => {
    const result = await extractAnalytics("/graphql", "POST", {}, {});
    expect(result.requestType).toBe("other");
  });

  test("/.env", async () => {
    const result = await extractAnalytics("/.env", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });

  test("/wp-admin", async () => {
    const result = await extractAnalytics("/wp-admin", "GET", {}, null);
    expect(result.requestType).toBe("other");
  });
});

// ============================================================================
// CLIENT EXTRACTION
// ============================================================================

describe("Client Extraction", () => {
  test("x-amp-client-application takes priority", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "x-amp-client-application": "VS Code CLI",
      "user-agent": "Bun/1.3.0",
    }, {});
    expect(result.client).toBe("VS Code CLI");
  });

  test("VS Code Insiders", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "x-amp-client-application": "VS Code Insiders",
    }, {});
    expect(result.client).toBe("VS Code Insiders");
  });

  test("Bun user-agent", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "user-agent": "Bun/1.3.0",
    }, {});
    expect(result.client).toBe("Bun");
  });

  test("node user-agent", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "user-agent": "node",
    }, {});
    expect(result.client).toBe("node");
  });

  test("google-genai-sdk user-agent", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "user-agent": "google-genai-sdk/1.30.0 gl-node/v22.21.1",
    }, {});
    expect(result.client).toBe("google-sdk");
  });

  test("OTel exporter user-agent", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "user-agent": "OTel-OTLP-Exporter-JavaScript/0.208.0",
    }, {});
    expect(result.client).toBe("otel");
  });

  test("unknown user-agent extracts first segment", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {
      "user-agent": "CustomClient/2.0.0",
    }, {});
    expect(result.client).toBe("CustomClient");
  });

  test("no headers returns unknown", async () => {
    const result = await extractAnalytics("/api/internal", "POST", {}, {});
    expect(result.client).toBe("unknown");
  });
});

// ============================================================================
// EDGE CASES
// ============================================================================

describe("Edge Cases", () => {
  test("invalid JSON body returns empty model", async () => {
    const request = mockRequest("POST", {}, "not valid json");
    const model = await extractModel("/v1/messages", request);
    expect(model).toBe("");
  });

  test("body without model field returns empty", async () => {
    const result = await extractAnalytics("/v1/messages", "POST", {}, {
      messages: [{ role: "user", content: "Hello" }],
      // no model field
    });
    expect(result.model).toBe("");
  });

  test("empty path segments handled", async () => {
    const result = await extractAnalytics("//api//internal//", "POST", {}, {});
    // Should still work despite double slashes
    expect(result.requestType).toBe("amp-admin");
  });
});

// ============================================================================
// AUTHORIZATION TESTS
// ============================================================================

describe("Authorization", () => {
  const API_KEY = "test-api-key-12345";

  function mockUrl(path, queryParams = {}) {
    const url = new URL(`https://example.com${path}`);
    for (const [k, v] of Object.entries(queryParams)) {
      url.searchParams.set(k, v);
    }
    return url;
  }

  function mockHeaders(headers = {}) {
    const headerMap = new Map(
      Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v])
    );
    return {
      get: (name) => headerMap.get(name.toLowerCase()) || null,
    };
  }

  test("Authorization Bearer header", () => {
    const url = mockUrl("/v1/messages");
    const headers = mockHeaders({ "Authorization": `Bearer ${API_KEY}` });
    expect(isAuthorized(url, headers, API_KEY)).toBe(true);
  });

  test("x-api-key header", () => {
    const url = mockUrl("/v1/messages");
    const headers = mockHeaders({ "x-api-key": API_KEY });
    expect(isAuthorized(url, headers, API_KEY)).toBe(true);
  });

  test("x-goog-api-key header", () => {
    const url = mockUrl("/v1beta/models/gemini:generateContent");
    const headers = mockHeaders({ "x-goog-api-key": API_KEY });
    expect(isAuthorized(url, headers, API_KEY)).toBe(true);
  });

  test("query param key", () => {
    const url = mockUrl("/v1beta/models/gemini:generateContent", { key: API_KEY });
    const headers = mockHeaders({});
    expect(isAuthorized(url, headers, API_KEY)).toBe(true);
  });

  test("query param auth_token", () => {
    const url = mockUrl("/v1/messages", { auth_token: API_KEY });
    const headers = mockHeaders({});
    expect(isAuthorized(url, headers, API_KEY)).toBe(true);
  });

  test("wrong key returns false", () => {
    const url = mockUrl("/v1/messages");
    const headers = mockHeaders({ "Authorization": "Bearer wrong-key" });
    expect(isAuthorized(url, headers, API_KEY)).toBe(false);
  });

  test("no credentials returns false", () => {
    const url = mockUrl("/v1/messages");
    const headers = mockHeaders({});
    expect(isAuthorized(url, headers, API_KEY)).toBe(false);
  });
});

// ============================================================================
// TOKEN EXTRACTION TESTS
// ============================================================================

describe("Token Extraction", () => {
  describe("Anthropic format", () => {
    test("extracts input_tokens and output_tokens", () => {
      const body = {
        usage: {
          input_tokens: 23,
          cache_creation_input_tokens: 0,
          cache_read_input_tokens: 0,
          output_tokens: 10,
        },
      };
      expect(extractTokens(body)).toEqual({ input: 23, output: 10 });
    });

    test("handles zero tokens", () => {
      const body = { usage: { input_tokens: 0, output_tokens: 0 } };
      expect(extractTokens(body)).toEqual({ input: 0, output: 0 });
    });
  });

  describe("OpenAI format", () => {
    test("extracts prompt_tokens and completion_tokens", () => {
      const body = {
        usage: {
          prompt_tokens: 9,
          completion_tokens: 10,
          total_tokens: 19,
        },
      };
      expect(extractTokens(body)).toEqual({ input: 9, output: 10 });
    });
  });

  describe("Gemini format", () => {
    test("extracts promptTokenCount and candidatesTokenCount", () => {
      const body = {
        usageMetadata: {
          promptTokenCount: 2,
          candidatesTokenCount: 10,
          totalTokenCount: 35,
        },
      };
      expect(extractTokens(body)).toEqual({ input: 2, output: 10 });
    });
  });

  describe("Edge cases", () => {
    test("null body returns zeros", () => {
      expect(extractTokens(null)).toEqual({ input: 0, output: 0 });
    });

    test("undefined body returns zeros", () => {
      expect(extractTokens(undefined)).toEqual({ input: 0, output: 0 });
    });

    test("empty object returns zeros", () => {
      expect(extractTokens({})).toEqual({ input: 0, output: 0 });
    });

    test("missing usage field returns zeros", () => {
      expect(extractTokens({ model: "gpt-4o" })).toEqual({ input: 0, output: 0 });
    });
  });
});

// ============================================================================
// SUMMARY TABLE (run with: bun worker.test.js)
// ============================================================================

if (import.meta.main) {
  console.log("\n📊 Worker Analytics Extraction Test Summary\n");
  console.log("=" .repeat(120));
  
  const testCases = [
    // Anthropic
    { path: "/api/provider/anthropic/v1/messages", method: "POST", headers: { "anthropic-version": "2024", "x-amp-client-application": "VS Code CLI" }, body: { model: "claude-sonnet-4-20250514" } },
    { path: "/v1/messages", method: "POST", headers: { "anthropic-version": "2024", "x-amp-client-application": "VS Code CLI" }, body: { model: "claude-3-opus-20240229" } },
    
    // OpenAI
    { path: "/api/provider/openai/v1/chat/completions", method: "POST", headers: { "x-amp-client-application": "VS Code Insiders" }, body: { model: "gpt-4o" } },
    { path: "/v1/chat/completions", method: "POST", headers: { "x-amp-client-application": "VS Code Insiders" }, body: { model: "gpt-4o-mini" } },
    { path: "/v1/responses", method: "POST", headers: { "x-amp-client-application": "VS Code CLI" }, body: { model: "gpt-4o" } },
    
    // Gemini
    { path: "/api/provider/google/v1beta1/publishers/google/models/gemini-2.0-flash:generateContent", method: "POST", headers: { "x-goog-api-key": "key", "x-amp-client-application": "VS Code CLI" }, body: {} },
    { path: "/v1beta/models/gemini-3-pro-preview:generateContent", method: "POST", headers: { "x-goog-api-key": "key", "x-amp-client-application": "VS Code CLI" }, body: {} },
    
    // Other providers
    { path: "/api/provider/groq/v1/chat/completions", method: "POST", headers: { "x-amp-client-application": "VS Code CLI" }, body: { model: "llama-3.1-70b" } },
    
    // Amp routes
    { path: "/api/internal", method: "POST", headers: { "x-amp-client-application": "VS Code CLI" }, body: {} },
    { path: "/api/threads/sync", method: "POST", headers: { "x-amp-client-application": "VS Code CLI" }, body: {} },
    { path: "/api/tab/llm-proxy", method: "POST", headers: { "x-amp-client-application": "VS Code CLI" }, body: {} },
    { path: "/api/otel/v1/metrics", method: "POST", headers: { "user-agent": "OTel-OTLP-Exporter/1.0" }, body: {} },
    { path: "/api/telemetry", method: "POST", headers: { "user-agent": "node" }, body: {} },
    
    // Management & OAuth
    { path: "/v0/management/config", method: "GET", headers: {}, body: null },
    { path: "/anthropic/callback", method: "GET", headers: {}, body: null },
    
    // Bot traffic
    { path: "/robots.txt", method: "GET", headers: { "user-agent": "Googlebot/2.1" }, body: null },
    { path: "/news.rss", method: "GET", headers: {}, body: null },
  ];

  console.log("| Path | Method | Type | Provider | Model | Client |");
  console.log("|" + "-".repeat(60) + "|--------|---------------|----------|" + "-".repeat(25) + "|" + "-".repeat(18) + "|");
  
  for (const tc of testCases) {
    const result = await extractAnalytics(tc.path, tc.method, tc.headers || {}, tc.body);
    const path = tc.path.length > 58 ? tc.path.substring(0, 55) + "..." : tc.path;
    console.log(
      `| ${path.padEnd(58)} | ${tc.method.padEnd(6)} | ${result.requestType.padEnd(13)} | ${(result.provider || "-").padEnd(8)} | ${(result.model || "-").padEnd(23)} | ${(result.client || "-").padEnd(16)} |`
    );
  }
  
  console.log("=" .repeat(120));
  console.log("\n✅ Run 'bun test worker.test.js' for full test suite\n");
}
