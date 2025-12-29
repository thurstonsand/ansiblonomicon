export default {
  async fetch(request, env) {
    const start = Date.now();
    const url = new URL(request.url);

    const authHeader = request.headers.get("Authorization");
    const xApiKey = request.headers.get("x-api-key");
    
    const isAuthorized = 
      authHeader === `Bearer ${env.API_KEY}` || 
      xApiKey === env.API_KEY;

    if (!isAuthorized) {
      env.ANALYTICS?.writeDataPoint({
        blobs: [url.pathname, "401"],
        doubles: [Date.now() - start],
        indexes: ["unauthorized"],
      });
      return new Response("Unauthorized: Invalid or missing API key", {
        status: 401,
        headers: { "Content-Type": "text/plain" },
      });
    }

    url.hostname = env.ORIGIN_HOSTNAME;

    const response = await fetch(new Request(url.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: "follow",
    }));

    env.ANALYTICS?.writeDataPoint({
      blobs: [url.pathname, String(response.status)],
      doubles: [Date.now() - start],
      indexes: [request.method],
    });

    return response;
  },
};
