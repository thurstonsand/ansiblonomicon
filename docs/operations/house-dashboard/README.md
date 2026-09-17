# House dashboard

Versioned copies of Loch Highland's shipped Home Assistant dashboard, verified against the live instance on 2026-09-16. HA remains managed through HA-MCP; these files are not consumed by Ansible, mise reconciliation, or a push-triggered deployment.

## Files and live locations

| File | Live location |
| --- | --- |
| `dashboard.json` | Storage dashboard `house-atlas`, view `home`, title **House** |
| `house-atlas.js` | Inline module resource `b917dcc7055c41c2bbe8167df0727d30`; registers `custom:house-atlas-card` |
| `house-atlas-theme.yaml` | `themes/house_atlas.yaml`, theme **House Atlas** |
| `trash-pickup-template.yaml` | Value of `template:` in `configuration.yaml`; creates `sensor.trash_pickup_reminder` |

Open `/house-atlas/home` on the current HA address. House is the system default dashboard. The global theme has Gruvbox-derived light and dark palettes; the user profile must use the backend-selected theme and Auto mode to follow the device appearance.

## Dependencies and behavior

- Tested with HA 2026.9.2 and HACS **ha-floorplan v1.1.5**, registered as a module at `/hacsfiles/ha-floorplan/floorplan.js?hacstag=188323494115` (resource `49c6783e7fb24c1ba63688c9bf2d8f83`).
- Native HA tiles provide controls. Phones use HA's internal `ha-bottom-sheet`; wider layouts dock controls. The sheet and frontend entity/device registry interfaces are not stable public custom-card APIs, so check them after HA upgrades. No Bubble Card or card-mod dependency.
- `dashboard.json` contains the final geometry, door openings, labels, and explicit entity controls. Edit it directly; no generator is required. Room `id` values match HA area IDs, which need not match renamed display names: `primary_bath` is Main Bath, `stair_hall` is Entryway, and `marianne_office` is Yanie Office.
- `room.lights` lists individual bulbs for map counts/status. `room.controls` selects displayed light-group controls. `room.group` is the optional whole-room control. Hue scenes populate dynamically by their entity/device area assignment; buttons call `scene.turn_on`, not explicit dynamic-animation playback.
- Map taps open room details. Lock and Unlock execute directly without confirmation. Floor and room selection stay local to each browser.
- Room rules use `double_tap_action: false` for immediate selection. An `{ action: "none" }` object still enables Floorplan's 400 ms double-click detection delay.

The desktop map stays in its left-hand column, reserving space for room controls even when none are selected. The controls panel appears only after selection. Floor names appear in the tabs without repeated headings.

Main Bedroom omits the whole-room lighting tile; its Hue group `light.main_bedroom` remains enabled, and its individual lamp and scenes remain available in the dashboard.

`light.main_bedroom_cloud_painting` is temporarily disabled in HA's entity registry and omitted from Main Bedroom's `lights` list while the painting is offline. Its Hue device, identity, and scenes are retained. To restore it, enable that entity, reload its Hue integration if needed, and add the entity ID back to the room's `lights` list in the live dashboard and this copy.

Three HA light-group helpers are prerequisites, not created by these exports:

| Helper | Members |
| --- | --- |
| `light.living_room_ambient_light` | Living Room Signe Floor Light Left, Floor Right, Wall Wash Right |
| `light.thurston_office_desk_lights` | Thurston Office Desk Lamp Left and Right |
| `light.thurston_office_ambient_light` | Thurston Office Wall Wash Left and Right |

The individual entity IDs are in the corresponding room's `lights` array. Hue scenes continue to address their original bulbs. These files do not back up integrations, helpers, area assignments, or Hue scenes; retain ordinary HA backups for those.

## Pickup reminder

The Main-floor garage has a small indicator inside its top-left corner, positioned by `room.pickup.position` in map coordinates. It never changes the map's size or position. Green indicates garbage; blue indicates recycling. Only the bin symbols are visible; the pickup description remains available to screen readers. No dismissal or bin-movement detection is implied.

`sensor.trash_pickup_reminder` owns the schedule: `tomorrow`, `today`, or `hidden`, with `pickup_date` and `pickup_types` attributes. It selects today's pickup before tomorrow's from the provider-backed `sensor.trash_pickup_current_pickup` and `sensor.trash_pickup_next_pickup`. HA's local date determines the two-day window; `now()` makes HA reevaluate at each minute boundary without a browser timer. Unavailable provider data makes the reminder unavailable, which the map hides. `calendar.trash_pickup` remains the provider's calendar, not a visibility switch.

The sensor uses YAML because the Template Helper config flow cannot define custom attributes. Apply the file's list under `template:` through managed YAML editing, preserving any other template entries, and run `homeassistant.check_config`. The first template integration requires an approved Core restart; subsequent edits use `template.reload`. The sensor is active and verified against live provider data.

Run `uv run pytest tests/test_trash_pickup_reminder.py` for local-date, DST, stream selection, and unavailable-data checks. Browser checks should cover both streams, each stream alone, hidden/unavailable states, and a sensor first appearing after the map loads. Inject preview states only into the browser card's `hass` object, never into the live provider entities.

## Maintenance

Before editing, read the live dashboard, resources, and theme through HA-MCP and compare them with these copies so newer live changes are not overwritten. Use `ha_config_get_dashboard`, `ha_config_list_dashboard_resources(include_content=true)`, and `ha_config_get_yaml` for theme key `House Atlas` in `themes/house_atlas.yaml`.

Apply approved changes through HA-MCP: update the existing inline module with `ha_config_set_dashboard_resource`, the storage config with `ha_config_set_dashboard`, and the theme through managed YAML editing with diff confirmation and validation. Refresh the best-practices read-receipt required by gated tools. The instance already includes `themes` through `frontend.themes`; reload themes and select House Atlas for both backend light and dark defaults when restoring it. Refresh the browser after JavaScript changes.

Verify light/dark phone and tablet layouts, all three floors, room-list navigation, scene updates, and sheet dismissal versus scrolling/slider interactions. Intercept service calls when testing lock buttons; do not operate physical locks as a smoke test. Compare the resulting live configuration with these files before committing.

Future work: [Global controls for House](../../wayfinding/loch-highland-house/tickets/29-house-global-controls.md). Design and acceptance history: [House dashboard thread](https://ampcode.com/threads/T-01a0a859-11a2-724a-a131-fa9cdd0f2cda).
