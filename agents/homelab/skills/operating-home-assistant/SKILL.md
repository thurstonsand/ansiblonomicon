---
name: operating-home-assistant
description: Operates Home Assistant through the `ha-mcp` MCP. Use before reading or changing anything in Home Assistant, including entities, devices, integrations, automations, dashboards, and its Apple Home and Google bridges.
---

# Operating Home Assistant

Home Assistant runs as an appliance in an Incus VM on pod042. This repo owns only the VM. Everything inside it is live state, reached through the `ha-mcp`. The house dashboard additionally keeps a repo copy, described in `docs/operations/house-dashboard/README.md`.

Before your first `ha-mcp` call, read [HA-MCP.md](HA-MCP.md): it lists the tool quirks that cost earlier sessions their time.

## Reaching Home Assistant outside the `ha-mcp`

Home Assistant serves plain HTTP on port 80 at `10.10.40.42`, and remotely at `https://ha.thurstons.house` through Nabu Casa. Every request carries the token from `scripts/fnox-host get HOMEASSISTANT_API_KEY`, because Home Assistant notifies the user of each unauthenticated request as a failed login.

pod042's host namespace cannot reach the VM over its macvlan. Pick the vantage by what you need:

- HTTP or WebSocket from the LAN: `sudo -n net-probe curl -m 10 -H "Authorization: Bearer $T" http://10.10.40.42/api/` through the Scanners leg; see the `surveying-the-network` skill.
- Files, logs or the `ha` CLI: `incus exec home-assistant -- ...`. The appliance shell is BusyBox, and the Core container has no `python3`.
- A quick authenticated check from anywhere: the Nabu Casa URL.

## Naming

Follow [Home Assistant's contextual naming](https://www.home-assistant.io/docs/configuration/customizing-entities/): name the device for the object, the entity for its function, and supply location through area and floor assignments. `Desk Lamp Left` belongs to `Thurston Office`; its entities need names such as `Connectivity`, not copies of the device or room name. Mark the primary control **Main entity of the device** rather than copying the device name into it.

Keep meaningful distinctions: `Under Kitchen` identifies a position within Basement, and a robot's or thermostat's service floor need not be its physical room. Preserve distinct area names where multiple rooms share a function. Leave mobile and whole-house objects without a fixed area when that reflects their use.

Use HA-specific display overrides when a vendor's room or device name serves a different context. For a separately named load on a multi-output device, give its entity an explicit area so its name stands alone; use integration-provided child devices when supported, rather than inventing them. Keep existing entity IDs when tidying names, and retain old voice names as aliases for exposed entities.

Dashboard-only wording belongs on the card. Custom cards use `hass.formatEntityName(state)`; pass `{ type: "entity" }` when the surrounding UI already supplies the device context. Templates compose the needed parts with `entity_name()`, `device_name()`, and `area_name()`. Audit `friendly_name` consumers before bulk renames: display changes can affect text and name-based matching even though entity-ID references keep working.

## Renaming or removing entities and devices

An entity ID belongs to every system that stores it, not only to Home Assistant. `ha_set_entity` and `ha_set_device` rewrite the registry and nothing else. Their docstrings list a few of the consumers they leave alone, not all of them.

Before changing an ID, find every consumer:

| Consumer | How to find it |
| --- | --- |
| Automations, scripts, scenes, helpers | `ha_search` over each type |
| Dashboards, including custom card config | cross-dashboard search, then the repo copy under `docs/operations/house-dashboard/` |
| Integration options: HomeKit Bridge include filter, other bridges and exposure filters | the config entry sweep below, because no search tool reads options |
| Google Assistant and Assist exposure | entity registry options from `ha_get_entity` |
| YAML configuration, templates and themes | `ha_read_file` over `configuration.yaml`, `automations.yaml`, `scripts.yaml`, `scenes.yaml`, and every file `ha_list_files` finds under `packages/`, `custom_templates/`, `themes/` and `dashboards/` |
| Apple Home and Google Home | invisible from here; see below |

Put the consequences in front of the user before acting. HomeKit identifies an accessory by its entity ID. A new ID makes Apple Home see a new accessory, so its room, scenes and automations there need redoing by hand. Display-name changes preserve identity; check name-dependent consumers as described above.

After the rename, update each consumer you found, rerun the sweep for the old ID, and confirm the new entities report state.

### Config entry sweep

Listing config entries through `ha_get_integration` omits their options. Fetching one by `entry_id`, or filtering by `domain`, returns them in full. Check every entry's options for the old ID; `ha_manage_custom_tool` can run that loop server-side in one call.

To change a bridge filter, pass the complete option set to `ha_set_integration`, which steps through the options flow, then confirm the entry is `loaded`.
