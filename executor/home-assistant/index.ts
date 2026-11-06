import { bearer, decodeJson, defineApp, defineProvider, object, renameTools, router, secrets, string, withApprovals } from "apps";
import { mcpRouter } from "apps/mcp";
import { always } from "apps/operations/approval";

const URL = "https://ha.thurstons.house/api/mcp/assist";

const homeAssistant = defineProvider({
  name: "Home Assistant",
  hosts: ["ha.thurstons.house"],
  auth: {
    token: secrets({
      label: "Home Assistant long-lived access token",
      fields: object({ token: string({ minLength: 1 }) }),
      request: ({ token }) => bearer(token),
    }),
  },
  // HA's long-lived token covers REST and MCP; mcpHealth's unauthenticated probe raises a login alert.
  async health({ account, fetch, signal }) {
    await decodeJson(
      await fetch("https://ha.thurstons.house/api/", { headers: account.headers(), signal }),
      object({ message: string() }),
    );
  },
});

const EXPORTED_TOOLS = new Map([
  ["script__send_destination", "send_destination"],
]);

export default defineApp({ user: { accounts: { homeAssistant } } }, async ({ user, cache, signal }) => {
  if (!user) return { tools: router({}) };
  return {
    tools: withApprovals(
      renameTools(
        await mcpRouter({
          url: URL,
          account: user.accounts.homeAssistant,
          headers: user.accounts.homeAssistant.headers(),
          cache,
          signal,
        }),
        (name) => EXPORTED_TOOLS.get(name),
      ),
      () => always(),
    ),
  };
});
