import { defineApp, defineProvider, object, secrets, string, withApprovals } from "apps";
import { mcpRouter } from "apps/mcp";
import { always } from "apps/operations/approval";

// imsgbus's own MCP server, for debugging the bridge against chat.db. Agents read and send messages
// through the Beeper app, which covers iMessage along with every other network.

// The pod153 app's provider, field for field, so both apps share its one connected account.
const pod153 = defineProvider({
  name: "pod153",
  hosts: ["pod153-mcp.thurstons.house"],
  auth: {
    serviceToken: secrets({
      label: "Cloudflare Access service token, RemCTL token, and imsgbus MCP token",
      fields: object({
        cf_access_client_id: string({ minLength: 1 }),
        cf_access_client_secret: string({ minLength: 1 }),
        remctl_token: string({ minLength: 1 }),
        imsgbus_token: string({ minLength: 1 }),
      }),
    }),
  },
});

// Anything that sends or changes what others see asks a person first.
const GUARDED = new Set(["send_message", "tapback", "edit_message", "unsend_message", "mark_read"]);

export default defineApp({ app: { accounts: { pod153 } } }, async ({ app, signal }) => {
  const account = app.accounts.pod153;
  return {
    tools: withApprovals(
      await mcpRouter({
        url: "https://pod153-mcp.thurstons.house/imessage",
        account,
        headers: {
          "CF-Access-Client-Id": account.fields.cf_access_client_id,
          "CF-Access-Client-Secret": account.fields.cf_access_client_secret,
          Authorization: `Bearer ${account.fields.imsgbus_token}`,
        },
        signal,
      }),
      (_, name) => (GUARDED.has(name) ? always() : undefined),
    ),
  };
});
