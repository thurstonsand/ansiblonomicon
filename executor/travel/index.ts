import { bearer, decodeJson, defineApp, defineProvider, header, object, renameTools, router, secrets, string, withApprovals } from "apps";
import { mcpRouter } from "apps/mcp";
import { always, never } from "apps/operations/approval";

const URL = "https://ha.thurstons.house/api/mcp/assist";
const MAPS_URL = "https://mapstools.googleapis.com/mcp";

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

const googleMaps = defineProvider({
  name: "Google Maps Essentials",
  hosts: ["mapstools.googleapis.com"],
  auth: {
    apiKey: secrets({
      label: "Google Maps API key",
      fields: object({ key: string({ minLength: 1 }) }),
      request: ({ key }) => header("X-Goog-Api-Key", key),
    }),
  },
});

const EXPORTED_TOOLS = new Map([
  ["script__send_destination", "send_destination"],
]);

const MAPS_TOOLS = {
  search_places: "query",
  resolve_names: "query",
  resolve_maps_urls: "query",
  compute_routes: "query",
  lookup_weather: "query",
} as const;

export default defineApp({ user: { accounts: { homeAssistant, googleMaps } } }, async ({ user, cache, signal }) => {
  if (!user) return { tools: router({}) };
  return {
    tools: withApprovals(
      router({
        tesla: renameTools(
          await mcpRouter({
            url: URL,
            account: user.accounts.homeAssistant,
            headers: user.accounts.homeAssistant.headers(),
            cache,
            signal,
          }),
          (name) => EXPORTED_TOOLS.get(name),
        ),
        maps: renameTools(
          await mcpRouter({
            url: MAPS_URL,
            account: user.accounts.googleMaps,
            headers: user.accounts.googleMaps.headers(),
            cache,
            signal,
          }, MAPS_TOOLS),
          (name) => Object.hasOwn(MAPS_TOOLS, name) ? name : undefined,
        ),
      }, {
        title: "Travel",
        description: "Find places with Google Maps Essentials and send an exact Google Place ID to Nausea's navigation.",
        instructions: "Resolve destinations with maps.search_places, maps.resolve_names, or maps.resolve_maps_urls before tesla.send_destination. Use the returned bare Google Place ID, never an invented ID or free-text address. If a resolver returns a places/ resource name, remove that prefix. Check the place name and address; clarify genuinely ambiguous results. Send only when the user asks to send a destination. Command acceptance does not confirm the car's screen or an active route. Use Essentials only: includeExtendedDetails must be false or omitted, pageSize at most 5, routingPreference must not be ROUTING_PREFERENCE_TRAFFIC_AWARE_OPTIMAL, and intermediateWaypoints at most 10. Route estimates exclude live traffic. For lookup_weather, omit capabilities, weatherOptions, and airQualityOptions; use location, unitsSystem, date, and hour for weather only. The advertised environmental capabilities are not authorized for this project. Preserve Google Maps attribution and source links immediately after the facts they support. In voice, disclose that results use Google Maps and that sources are in the conversation transcript. Use only with models configured not to train on this data.",
      }),
      (_, name) => name === "tesla.send_destination" || name.startsWith("maps.") ? never() : always(),
    ),
  };
});
