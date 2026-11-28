import { accountRouter, defineApp, defineProvider, object, router, secrets, string, toolAnnotations, withApprovals } from "apps";
import { mcpRouter } from "apps/mcp";
import { always } from "apps/operations/approval";

const BASE = "https://pod153-mcp.thurstons.house";

// The retired imsgbus_token still contributes to the provider identity of the linked Reminders account.
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

// Keep the paused Notes and Mail fields so Photos keeps its linked account.
const library = defineProvider({
  name: "Apple Library on pod153",
  hosts: ["pod153-mcp.thurstons.house"],
  auth: {
    serviceToken: secrets({
      label: "Cloudflare Access and the three Apple Library MCP tokens",
      fields: object({
        cf_access_client_id: string({ minLength: 1 }),
        cf_access_client_secret: string({ minLength: 1 }),
        notes_token: string({ minLength: 1 }),
        mail_token: string({ minLength: 1 }),
        photos_token: string({ minLength: 1 }),
      }),
    }),
  },
});

const GUARDED = new Set(["delete_reminder", "run"]);

export default defineApp({ app: { accounts: { pod153 } }, user: { accounts: { library: library.many() } } }, async ({ app, user, signal }) => {
  const account = app.accounts.pod153;
  const access = {
    "CF-Access-Client-Id": account.fields.cf_access_client_id,
    "CF-Access-Client-Secret": account.fields.cf_access_client_secret,
  };
  const guard = (_: unknown, name: string) => (GUARDED.has(name) ? always() : undefined);
  const photosTools =
    accountRouter(user?.accounts.library ?? [], async (account) =>
      withApprovals(
        await mcpRouter({
          url: `${BASE}/photos`,
          account,
          headers: {
            "CF-Access-Client-Id": account.fields.cf_access_client_id,
            "CF-Access-Client-Secret": account.fields.cf_access_client_secret,
            Authorization: `Bearer ${account.fields.photos_token}`,
          },
          signal,
        }),
        (tool, name) => {
          if (name.endsWith("_run") || toolAnnotations(tool)?.readOnlyHint !== true) return always();
          return ({ toolInput }) =>
            toolInput && typeof toolInput === "object" && "icloud" in toolInput && toolInput.icloud === true
              ? "user-approval"
              : "approved";
        },
      ), { signal });

  const [reminders, photos] = await Promise.all([
    mcpRouter({
      url: `${BASE}/reminders`,
      account,
      headers: { ...access, Authorization: `Bearer ${account.fields.remctl_token}` },
      signal,
    }),
    photosTools,
  ]);
  return { tools: router({
    reminders: router(withApprovals(reminders, guard), {
      title: "Reminders",
      description:
        "Thurston's Apple Reminders: read, search, create, update, complete, delete and restore reminders and lists.",
    }),
    photos,
  }) };
});
