---
name: operating-home-assistant
description: Operates Home Assistant through the `ha-mcp` MCP. Use before reading or changing anything in Home Assistant, including entities, devices, integrations, automations, dashboards, and its Apple Home and Google bridges.
---

# Operating Home Assistant

Home Assistant runs as an appliance in an Incus VM on pod042. This repo owns only the VM. Everything inside it is live state, reached through the `ha-mcp`. The house dashboard additionally keeps a repo copy, described in `docs/operations/house-dashboard/README.md`.

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

Put the consequences in front of the user before acting. HomeKit identifies an accessory by its entity ID. A new ID makes Apple Home see a new accessory, so its room, scenes and automations there need redoing by hand. Changing a display name only is safe for every consumer.

After the rename, update each consumer you found, rerun the sweep for the old ID, and confirm the new entities report state.

### Config entry sweep

Listing config entries through `ha_get_integration` omits their options. Fetching one by `entry_id`, or filtering by `domain`, returns them in full. Check every entry's options for the old ID; `ha_manage_custom_tool` can run that loop server-side in one call.

To change a bridge filter, pass the complete option set to `ha_set_integration`, which steps through the options flow, then confirm the entry is `loaded`.
