# Home Assistant

Imports selected scripts from Home Assistant's native MCP server at `https://ha.thurstons.house/api/mcp/assist`. Each caller connects their own long-lived HA access token through Executor's account form. Credentials are restricted to that host and the bearer header. Every exported command asks for approval. The account check validates the token through HA's authenticated REST API; MCP discovery checks the actual command endpoint without generating failed-login alerts from unauthenticated health probes.

The MCP integration enables only the Assist API, requires an administrator, and permits writes. The broader third-party HA administration MCP is not used. The HA token itself has broader permissions than this app: `EXPORTED_TOOLS` restricts both discovery and invocation through Executor, not direct use of the token.

## Publishing a command

1. Create or edit a script in HA with a description, typed fields, and a response where useful. Keep device selection and action sequencing in HA.
2. Add the **Executor** label and expose the script to **Assist**. Labels only organize scripts; they do not grant access. Use **Dashboard** for scripts called by dashboard controls, both labels for shared scripts, and neither for internal helpers.
3. Add its native `script__<entity_suffix>` name and public tool name to `EXPORTED_TOOLS`. Push to main to deploy through the Deploy Executor Apps workflow. MCP metadata is cached for five minutes fresh plus five minutes stale; allow it to refresh after editing HA fields or descriptions.
4. Verify the published tool's inputs, an accepted call, and that unlisted tools cannot be called. Never export a general service-call or script-dispatch tool as a substitute for individual commands.

## Tesla navigation

`send_destination` invokes `script.send_destination`, labeled **Executor**, on the sole car, **Nausea**. The live HA script rejects missing or blank destinations, trims input, refreshes `binary_sensor.nausea_status`, then calls `tesla_fleet.navigate_to_destination`. It resolves the required device ID from that entity. Queued execution keeps concurrent destination changes ordered. The refresh works around [core#182023](https://github.com/home-assistant/core/issues/182023), where a car sleeping since its last poll can fail to wake for a command.

Its MCP response contains `result.status: command_accepted`; this is not proof of what the car's screen displays. Invalid input returns `result.status: rejected` without contacting Tesla. HA's `stop` with `error: true` aborts but does not propagate an MCP error, so the script returns an explicit rejection instead. Tesla action errors propagate normally. Tesla's destination and route sensors may remain unknown after a successful command. Clarify ambiguous places before sending. Navigation does not unlock, start, or drive the car.

Tesla Fleet's application credentials and vehicle key are in the Agent vault's **Tesla Fleet API Key** item. HA holds the private key at `/config/tesla_fleet.key`; `tesla.thurstons.house` publishes the corresponding public key. Pair that key to the vehicle before using commands.

The existing `living_room_evening_lights`, `living_room_late_night`, and `living_room_tokyo` scripts carry **Dashboard** and are not exposed to Assist. HA owns script configuration and labels as live appliance state; this directory owns only the Executor adapter.
