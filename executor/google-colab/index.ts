import { array, bearer, boolean, decodeJson, defineApp, defineProvider, json, mutation, object, oauth2, query, renameTools, router, string, toolAnnotations, withApprovals, type QueryContext } from "apps";
import { mcpRouter } from "apps/mcp";
import { always } from "apps/operations/approval";

const HOST = "colaboratory.googleapis.com";
const URL = `https://${HOST}/mcp`;

const colab = defineProvider({
  name: "Google Colab",
  hosts: [HOST],
  auth: {
    oauth: oauth2({
      discover: "https://accounts.google.com",
      scopes: ["https://www.googleapis.com/auth/colaboratory"],
      authorizationParams: { access_type: "offline", prompt: "consent" },
      request: ({ access_token }) => bearer(access_token),
      clientGuide: "In a Google Cloud project, enable the [Colab API](https://console.cloud.google.com/apis/library/colaboratory.googleapis.com) and its [remote MCP server](https://docs.cloud.google.com/mcp/enable-disable-mcp-servers). In [Google Auth Platform](https://console.cloud.google.com/auth/clients), create a **Web application** client, select **Use this client for an AI-powered agent**, and add the redirect URI shown above. Sign in with the Google account whose Colab quota you want to use.",
    }),
  },
  // MCP discovery is anonymous; a subscription lookup actually checks the grant.
  async health({ account, fetch, signal }) {
    await decodeJson(
      await fetch(`https://${HOST}/v1beta/subscription`, { headers: account.headers(), signal }),
      object({ name: string(), tier: string() }),
    );
  },
});

const requirements = { user: { accounts: { colab } } };
type Context = QueryContext<typeof requirements>;
const runtimeSpec = object({ variant: string(), accelerator: string(), shape: string() });
const runtime = object({ name: string(), runtimeSpec, version: string().optional() });
const runtimeResult = object({ result: object({
  isError: boolean().optional(),
  structuredContent: json().optional(),
  content: array(object({ text: string().optional() })).optional(),
}) });
const privateRuntimeTools = new Set(["create_runtime", "get_runtime", "list_runtimes"]);

// These upstream calls include writable proxy credentials. Decode only public runtime fields.
async function runtimeCall<T>(ctx: Context, name: string, args: object, output: Parameters<typeof decodeJson<T>>[1]) {
  const signal = AbortSignal.any([ctx.signal, AbortSignal.timeout(300_000)]);
  const { result } = await decodeJson(await ctx.fetch(URL, {
    method: "POST",
    headers: { ...ctx.user.accounts.colab.headers(), "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
    signal,
  }), runtimeResult);
  if (result.isError) throw new Error(`Colab ${name} failed. Check runtime availability before retrying.`);
  const text = result.content?.[0]?.text;
  return decodeJson(new Response(result.structuredContent === undefined ? text : JSON.stringify(result.structuredContent)), output);
}

export default defineApp(requirements, async ({ user, cache, signal }) => {
  if (!user) return { tools: router({}) };
  const account = user.accounts.colab;
  const upstream = await mcpRouter({ url: URL, account, headers: account.headers(), cache, signal, timeoutMs: 300_000 });
  return {
    tools: withApprovals(router({
      colab: renameTools(upstream, (name) => privateRuntimeTools.has(name) ? undefined : name),
      list_runtimes: query({ description: "List your active Colab runtimes and their accelerator specs. Reuse a suitable runtime before creating one.", input: object({}) },
        (ctx: Context, input) => runtimeCall(ctx, "list_runtimes", input, object({ runtimes: array(runtime).optional() }))),
      create_runtime: mutation({
        description: "Provision a Colab runtime using an eligible spec from colab.list_runtime_specs. Reuse the same requestId after a timeout; do not allocate a second runtime blindly.",
        input: object({ runtime: object({ runtimeSpec, version: string().optional() }), requestId: string(), runtimeId: string().optional() }),
      }, (ctx: Context, input) => runtimeCall(ctx, "create_runtime", input, runtime)),
    }, {
      title: "Google Colab",
      description: "Provision Colab GPU/TPU runtimes and execute Python in their Jupyter sessions.",
      instructions: "Check list_runtimes and colab.list_runtime_specs before allocating. Reuse a suitable runtime or choose an eligible accelerator. Generate a UUID v4 for create_runtime.requestId and retain it for a retry. Reuse a kernel session for related calls. Release sessions and runtimes you created when done. A timeout does not confirm completion; check state before retrying.",
    }), (tool) => toolAnnotations(tool)?.readOnlyHint === true ? undefined : always()),
  };
});
