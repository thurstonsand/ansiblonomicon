import { defineApp, defineProvider, object, router, secrets, string, withApprovals } from "apps";
import { mcpRouter } from "apps/mcp";
import { always } from "apps/operations/approval";

const BASE = "https://pod153-mcp.thurstons.house";

// The iMessage app declares this provider too, field for field, so both share its one account;
// the imsgbus token is that app's.
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

// Anything that deletes or runs an arbitrary command asks a person first.
const GUARDED = new Set(["delete_reminder", "run"]);

export default defineApp({ app: { accounts: { pod153 } } }, async ({ app, signal }) => {
  const account = app.accounts.pod153;
  const access = {
    "CF-Access-Client-Id": account.fields.cf_access_client_id,
    "CF-Access-Client-Secret": account.fields.cf_access_client_secret,
  };
  const guard = (_: unknown, name: string) => (GUARDED.has(name) ? always() : undefined);
  return {
    tools: router({
      // RemCTL's own instructions stay; its description, "RemCTL Reminders", is all agents see in a skills listing.
      reminders: router(
        withApprovals(
          await mcpRouter({
            url: `${BASE}/reminders`,
            account,
            headers: { ...access, Authorization: `Bearer ${account.fields.remctl_token}` },
            signal,
          }),
          guard,
        ),
        {
          title: "Reminders",
          description:
            "Thurston's Apple Reminders: read, search, create, update, complete, delete and restore reminders and lists.",
        },
      ),
    }),
  };
});
