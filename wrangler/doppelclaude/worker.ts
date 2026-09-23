interface Env {
  API_KEY: string;
  CF_ACCESS_CLIENT_ID: string;
  CF_ACCESS_CLIENT_SECRET: string;
}

const ORIGIN = "https://doppelclaude-origin.thurstons.house";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (
      !env.API_KEY ||
      !env.CF_ACCESS_CLIENT_ID ||
      !env.CF_ACCESS_CLIENT_SECRET
    ) {
      return new Response("Service unavailable", { status: 503 });
    }

    if (
      request.headers.get("Authorization") !== `Bearer ${env.API_KEY}` &&
      request.headers.get("x-api-key") !== env.API_KEY
    ) {
      return new Response("Unauthorized", { status: 401 });
    }

    const url = new URL(request.url);
    if (
      !(request.method === "POST" && url.pathname === "/v1/messages") &&
      !(request.method === "GET" && url.pathname === "/v1/models") &&
      !(request.method === "GET" && url.pathname === "/v1/sdk-models")
    ) {
      return new Response("Not found", { status: 404 });
    }

    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${env.API_KEY}`);
    headers.delete("x-api-key");
    headers.delete("cookie");
    headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
    headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
    const response = await fetch(`${ORIGIN}${url.pathname}`, {
      method: request.method,
      headers,
      body: request.body,
      redirect: "manual",
      signal: request.signal,
    });
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Cache-Control", "no-store");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  },
};
