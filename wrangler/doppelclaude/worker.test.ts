import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "./worker.ts";

const env = {
  API_KEY: "test-api-key",
  CF_ACCESS_CLIENT_ID: "test-access-id",
  CF_ACCESS_CLIENT_SECRET: "test-access-secret",
};
const base = "https://doppelclaude.thurstons.house";

test("SDK catalog uses existing authentication and exact GET route", async (t) => {
  const origin = t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "https://doppelclaude-origin.thurstons.house/v1/sdk-models");
    assert.equal(init.method, "GET");
    assert.equal(new Headers(init.headers).get("Authorization"), `Bearer ${env.API_KEY}`);
    return Response.json({ sdkVersion: "test" });
  });
  for (const headers of [{ "x-api-key": env.API_KEY }, { Authorization: `Bearer ${env.API_KEY}` }]) {
    assert.equal((await worker.fetch(new Request(`${base}/v1/sdk-models`, { headers }), env)).status, 200);
    for (const [method, path] of [["POST", "/v1/sdk-models"], ["HEAD", "/v1/sdk-models"], ["GET", "/v1/sdk-models/"]]) {
      assert.equal((await worker.fetch(new Request(`${base}${path}`, { method, headers }), env)).status, 404);
    }
  }
  for (const headers of [{}, { "x-api-key": "wrong" }]) {
    assert.equal((await worker.fetch(new Request(`${base}/v1/sdk-models`, { headers }), env)).status, 401);
  }
  assert.equal(origin.mock.callCount(), 2);
});

test("rejects missing credentials and unrecognized routes without contacting origin", async (t) => {
  const origin = t.mock.method(globalThis, "fetch", () => {
    throw new Error("Origin must not be contacted");
  });
  for (const headers of [{}, { Authorization: "Bearer incorrect" }]) {
    const response = await worker.fetch(new Request(`${base}/v1/models`, { headers }), env);
    assert.equal(response.status, 401);
  }
  const authorized = { "x-api-key": env.API_KEY };
  for (const [method, path] of [["GET", "/v1/messages"], ["POST", "/v1/models"], ["GET", "/admin"]]) {
    const response = await worker.fetch(new Request(`${base}${path}`, { method, headers: authorized }), env);
    assert.equal(response.status, 404);
  }
  for (const key of Object.keys(env)) {
    const response = await worker.fetch(new Request(`${base}/v1/models`, { headers: authorized }), { ...env, [key]: "" });
    assert.equal(response.status, 503);
  }
  assert.equal(origin.mock.callCount(), 0);
});

test("canonicalizes auth, discards cookies and query secrets, and does not follow redirects", async (t) => {
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "https://doppelclaude-origin.thurstons.house/v1/models");
    assert.equal(init.method, "GET");
    assert.equal(init.redirect, "manual");
    const headers = new Headers(init.headers);
    assert.equal(headers.get("Authorization"), `Bearer ${env.API_KEY}`);
    assert.equal(headers.get("x-api-key"), null);
    assert.equal(headers.get("cookie"), null);
    assert.equal(headers.get("CF-Access-Client-Id"), env.CF_ACCESS_CLIENT_ID);
    assert.equal(headers.get("CF-Access-Client-Secret"), env.CF_ACCESS_CLIENT_SECRET);
    return new Response(null, { status: 302, headers: { Location: "https://example.com" } });
  });
  const response = await worker.fetch(new Request(`${base}/v1/models?key=must-not-forward`, {
    headers: {
      "x-api-key": env.API_KEY,
      Cookie: "CF_Authorization=untrusted",
      "CF-Access-Client-Id": "untrusted",
      "CF-Access-Client-Secret": "untrusted",
    },
  }), env);
  assert.equal(response.status, 302);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
});

test("forwards marker unchanged, streams before EOF, and propagates cancellation signal", async (t) => {
  const payload = JSON.stringify({ system: "Amp Thread URL: https://ampcode.com/threads/T-test", messages: [] });
  const controller = new AbortController();
  const request = new Request(`${base}/v1/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.API_KEY}`, "Content-Type": "application/json" },
    body: payload,
    signal: controller.signal,
  });
  let upstreamSignal: AbortSignal | null | undefined;
  const stream = new ReadableStream({
    start(streamController) {
      streamController.enqueue(new TextEncoder().encode(": keepalive\n\n"));
    },
  });
  t.mock.method(globalThis, "fetch", async (_url: string, init: RequestInit) => {
    assert.equal(await new Response(init.body).text(), payload);
    assert.equal(init.signal, request.signal);
    upstreamSignal = init.signal;
    return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
  });
  const response = await worker.fetch(request, env);
  assert.equal(response.headers.get("Content-Type"), "text/event-stream");
  assert.equal(response.body, stream);
  const reader = response.body!.getReader();
  assert.equal(new TextDecoder().decode((await reader.read()).value), ": keepalive\n\n");
  controller.abort();
  assert.equal(upstreamSignal?.aborted, true);
  await reader.cancel();
});
