import { bearer, defineApp, defineProvider, object, raw, router, secrets, string, toolAnnotations, withApprovals } from "apps";
import { mcpHealth, mcpRouter } from "apps/mcp";
import { always } from "apps/operations/approval";

const HOST = "fdsnaiutiizykhbtju3uhpmumkqhtmmi.ui.nabu.casa";
const webhookUrl = (webhookId: string) => {
  if (!/^mcp_[0-9a-f]{32}$/.test(webhookId)) throw new Error("Enter the mcp_… ID from the HA-MCP connect URL.");
  return `https://${HOST}/api/webhook/${webhookId}`;
};

const homeAssistant = defineProvider({
  name: "Home Assistant Admin (HA-MCP)",
  hosts: [HOST],
  auth: {
    token: secrets({
      label: "HA-MCP webhook and Home Assistant admin token",
      fields: object({
        webhookId: raw(string({ minLength: 1 })),
        token: string({ minLength: 1 }),
      }),
      request: ({ token }) => bearer(token),
    }),
  },
  health: (check) => mcpHealth(check, {
    url: webhookUrl(check.account.fields.webhookId),
    headers: check.account.headers(),
  }),
});

export default defineApp({ user: { accounts: { homeAssistant } } }, async ({ user, cache, signal }) => {
  if (!user) return { tools: router({}) };
  const account = user.accounts.homeAssistant;
  return {
    tools: withApprovals(
      await mcpRouter({
        url: webhookUrl(account.fields.webhookId),
        account,
        headers: account.headers(),
        cache,
        signal,
      }),
      (tool) => toolAnnotations(tool)?.readOnlyHint === true ? undefined : always(),
    ),
  };
});
