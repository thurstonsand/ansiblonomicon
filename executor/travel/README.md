# Travel

Pairs Google Maps Essentials lookups with selected scripts from Home Assistant's native MCP server at `https://ha.thurstons.house/api/mcp/assist`. Each caller connects their own Google Maps API key and long-lived HA access token through Executor's account forms. Credentials are restricted to their respective hosts and authentication headers. Maps reads and navigation run without Executor approval; other exported commands require approval by default. The HA account check validates the token through its authenticated REST API without generating failed-login alerts from unauthenticated health probes.

The MCP integration enables only the Assist API, requires an administrator, and permits writes. The broader third-party HA administration MCP is not used. The HA token itself has broader permissions than this app: `EXPORTED_TOOLS` restricts both discovery and invocation through Executor, not direct use of the token.

## Google Maps Essentials

The official MCP at `https://mapstools.googleapis.com/mcp` supplies `maps.search_places`, `maps.resolve_names`, `maps.resolve_maps_urls`, `maps.compute_routes`, and `maps.lookup_weather`. Native input schemas and responses, including attribution links, pass through unchanged. Look up a destination, check its identity and address, then pass the returned bare Google Place ID to `tesla.send_destination`. Clarify ambiguous results rather than guessing a branch, terminal, or entrance.

`terraform/google/maps.tf` owns the billing-enabled `ansiblonomicon-maps` project, enabled APIs, and an API key restricted to `mapstools.googleapis.com`. The Agent vault's **Google Maps Essentials API Key** item stores the key for connection and recovery; `GOOGLE_MAPS_API_KEY` in fnox resolves it, and Executor stores the connected credential. The project is not enrolled in Pro. Keep `includeExtendedDetails` off, `pageSize` at most 5, `routingPreference` traffic-unaware, and `intermediateWaypoints` at most 10. Estimates do not include live traffic. Name and URL resolution are free; other Essentials requests have a monthly free allowance followed by usage billing, as documented in [Google's pricing](https://developers.google.com/maps/ai/maps-experience-agent-tools#billing-and-quotas).

Use a model configured not to train on Google Maps data. Present the returned Google Maps source links immediately after supported facts. Voice clients disclose the use of Google Maps and keep the links in their conversation transcript. Do not cache Maps response content in this app; the router cache holds tool metadata only.

## Publishing a command

1. Create or edit a script in HA with a description, typed fields, and a response where useful. Keep device selection and action sequencing in HA.
2. Add the **Executor** label and expose the script to **Assist**. Labels only organize scripts; they do not grant access. Use **Dashboard** for scripts called by dashboard controls, both labels for shared scripts, and neither for internal helpers.
3. Add its native `script__<entity_suffix>` name and public tool name to `EXPORTED_TOOLS`; Travel groups these under `tesla`. Push to main to deploy through the Deploy Executor Apps workflow. MCP metadata is fresh for five minutes and can be served stale while refreshing; allow it to refresh after editing HA fields or descriptions. Keep unrelated household commands in a separate app rather than adding them to Travel.
4. Verify the published tool's inputs, an accepted call, and that unlisted tools cannot be called. Never export a general service-call or script-dispatch tool as a substitute for individual commands.

## Tesla navigation

`tesla.send_destination` invokes `script.send_destination`, labeled **Executor**, on the sole car, **Nausea**. It requires `place_id`, a bare Google Place ID returned by Maps, not an address, URL, or `refId:` value. The live HA script rejects missing or malformed IDs, trims input, refreshes `binary_sensor.nausea_status`, then calls `tesla_fleet.navigate_to_waypoints` with that single ID. HA encodes it for Tesla and wakes the car if needed. The script resolves the required device ID from the status entity. Queued execution keeps concurrent destination changes ordered. The refresh works around [core#182023](https://github.com/home-assistant/core/issues/182023), where a car sleeping since its last poll can fail to wake for a command.

Its MCP response contains `result.status: command_accepted`; this is not proof of what the car's screen displays. Invalid input returns `result.status: rejected` without contacting Tesla. HA's `stop` with `error: true` aborts but does not propagate an MCP error, so the script returns an explicit rejection instead. Tesla action errors propagate normally. Tesla's destination and route sensors may remain unknown after a successful command. Clarify ambiguous places before sending. Navigation does not unlock, start, or drive the car.

Tesla Fleet's application credentials and vehicle key are in the Agent vault's **Tesla Fleet API Key** item. HA holds the private key at `/config/tesla_fleet.key`; `tesla.thurstons.house` publishes the corresponding public key. Pair that key to the vehicle before using commands.

The existing `living_room_evening_lights`, `living_room_late_night`, and `living_room_tokyo` scripts carry **Dashboard** and are not exposed to Assist. HA owns script configuration and labels as live appliance state; this directory owns only the Executor adapter.
