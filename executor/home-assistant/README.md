# Home Assistant

Exposes the full catalog from the [HA-MCP HACS integration](https://github.com/homeassistant-ai/ha-mcp) over its Nabu Casa webhook, including administration of automations, dashboards, and helpers. [Travel](../travel/) still uses Home Assistant's native Assist MCP for Tesla navigation.

Before the first deploy, register the hosted app with slug `home-assistant`. The deploy workflow updates existing apps; it does not create them.

In the app's **Accounts** tab, enter the `mcp_…` ID from the HA-MCP connect URL and a Home Assistant administrator's long-lived access token. This is a separate account from Travel's. Executor sends the token only to the configured Nabu Casa host. The health check verifies that the endpoint lists tools with the token and rejects discovery without it.

Use a scoped connection to choose which agents can reach this app and which tools they can call. Even read-only admin tools may reveal private configuration; select only the tools the client needs. The app requests approval for tools HA-MCP doesn't mark as read-only. Use **Browser** approval mode for admin writes: Executor's **Automatic** mode approves them on the client's behalf.
