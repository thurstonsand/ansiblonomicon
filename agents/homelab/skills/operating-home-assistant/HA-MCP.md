# ha-mcp quirks

## Finding tools

- Import only names that `tool_search` returned
- `ha_get_entity` takes `entity_id` or `unique_id` and returns registry metadata. Live state and attributes come from `ha_get_state`.
- `ha_get_history` takes `entity_ids`, a list.

## Logs

`ha_get_logs` reads the logbook unless you pass `source`. For diagnostics, pass `source: "error_log"`; its time window is `hours_back`.

## Writes

- Dashboard, automation and helper writes require `BestPracticeKey`. Fetch the guide once, extract the full `I-HAVE-READ-THE-BEST-PRACTICES-GUIDE-<hex>` key, and pass it on every gated write. Tools without that parameter reject it, so pass it only where the signature lists it.
- `Error: MCP tool failed: fetch failed` leaves the outcome unknown. Read back before retrying a write.
- Registry writes go through `ha_set_entity`, `ha_set_device` and the area tools; raw `config/*_registry/*` WebSocket commands are blocked in the sandbox.
- `ha_set_integration` with `enabled: false` disables the integration. Reload through `ha_reload_core` with `entry_id` alone.

## Sandbox

`code_exec` and `ha_manage_custom_tool` have no timers and no imports: no `setTimeout`, `asyncio.sleep` or `import time`. Wait with a shell `sleep` between calls. Each execution allows 50 tool calls, so batch bulk edits in chunks below that and track which items landed.

## Response shapes

- Dashboard resource bodies live in `_content`, alongside `_inline` and `_size`; `content` is absent.
- Compare dashboard configs structurally, not by serialized length: numbers round-trip as `95` or `95.0` and key order varies.
- `ha_read_file` and `ha_list_files` allow only limited paths. Read anything else through `incus exec home-assistant`.
