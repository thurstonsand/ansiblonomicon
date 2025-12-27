export default {
  async fetch(request, env) {
    const debug = env.DEBUG === "true";
    const url = new URL(request.url);

    if (debug) {
      const headersObj = {};
      for (const [key, value] of request.headers.entries()) {
        headersObj[key] = key.toLowerCase() === "authorization" 
          ? `${value.substring(0, 15)}...` 
          : value;
      }
      console.log(JSON.stringify({ type: "request_debug", headers: headersObj }));
    }

    // Check both Authorization: Bearer and x-api-key headers
    // (amp uses Authorization for internal endpoints, x-api-key for provider endpoints)
    const authHeader = request.headers.get("Authorization");
    const xApiKey = request.headers.get("x-api-key");
    
    const isAuthorized = 
      authHeader === `Bearer ${env.API_KEY}` || 
      xApiKey === env.API_KEY;

    if (!isAuthorized) {
      console.log(JSON.stringify({ type: "auth_error", method: request.method, path: url.pathname }));
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
    
    console.log(JSON.stringify({ 
      type: "request", 
      method: request.method, 
      path: url.pathname, 
      status: response.status 
    }));

    return response;
  },
};
