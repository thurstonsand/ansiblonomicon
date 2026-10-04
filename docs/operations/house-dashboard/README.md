# House dashboard

Versioned copies of Loch Highland's shipped Home Assistant dashboard, verified against the live instance on 2026-09-16. HA remains managed through HA-MCP; these files are not consumed by mise reconciliation or a push-triggered deployment.

## Files and live locations

| File                         | Live location                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| `dashboard.json`             | Storage dashboard `house-atlas`, view `home`, title **House**                                  |
| `house-atlas.js`             | Inline module resource `b917dcc7055c41c2bbe8167df0727d30`; registers `custom:house-atlas-card` |
| `house-atlas-theme.yaml`     | `themes/house_atlas.yaml`, theme **House Atlas**                                               |
| `trash-pickup-template.yaml` | Value of `template:` in `configuration.yaml`; creates `sensor.trash_pickup_reminder`           |

Open `/house-atlas/home` on the current HA address. House is the system default dashboard. The global theme has Gruvbox-derived light and dark palettes; the user profile must use the backend-selected theme and Auto mode to follow the device appearance.

## Dependencies and behavior

- Tested with HA 2026.9.2 and HACS **ha-floorplan v1.1.5**, registered as a module at `/hacsfiles/ha-floorplan/floorplan.js?hacstag=188323494115` (resource `49c6783e7fb24c1ba63688c9bf2d8f83`).
- Native HA tiles provide controls. Phones use HA's internal `ha-bottom-sheet`; wider layouts dock controls. The sheet and frontend entity/device registry interfaces are not stable public custom-card APIs, so check them after HA upgrades. No Bubble Card or card-mod dependency.
- `dashboard.json` contains the final geometry, door openings, labels, and explicit entity controls. Edit it directly; no generator is required. Room `id` values match HA area IDs, which need not match renamed display names: `primary_bath` is Main Bath, `stair_hall` is Entryway, and `marianne_office` is Yanie Office.
- `room.lights` lists individual bulbs for map counts/status. `room.controls` selects displayed light-group controls. `room.group` is the optional whole-room control. `room.appliances` adds toggleable tiles beside the room's primary entity; Kitchen lists the espresso machine's power switch. `room.scenes` lists curated scene buttons, each calling `<domain>.turn_on`, so scripts work; Living Room lists its combined scripts. Without it, `room.hueScenes` populates Hue scenes dynamically by their entity/device area assignment; those buttons call `scene.turn_on`, not explicit dynamic-animation playback.
- Map taps open room details. Lock and Unlock execute directly without confirmation. Floor and room selection stay local to each browser.
- Room rules use `double_tap_action: false` for immediate selection. An `{ action: "none" }` object still enables Floorplan's 400 ms double-click detection delay.

The desktop map stays in its left-hand column, reserving space for room controls even when none are selected. The controls panel appears only after selection. Floor names appear in the tabs without repeated headings.

Main Bedroom omits the whole-room lighting tile; its Hue group `light.main_bedroom` remains enabled, and its individual lamp and scenes remain available in the dashboard.

`light.main_bedroom_cloud_painting` is temporarily disabled in HA's entity registry and omitted from Main Bedroom's `lights` list while the painting is offline. Its Hue device, identity, and scenes are retained. To restore it, enable that entity, reload its Hue integration if needed, and add the entity ID back to the room's `lights` list in the live dashboard and this copy.

Four HA light-group helpers are prerequisites, not created by these exports:

| Helper                                | Members                                                                                                    |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `light.living_room_ambient_light`     | Living Room Signe Floor Light Left, Floor Right, Wall Wash Right                                           |
| `light.thurston_office_desk_lights`   | Thurston Office Desk Lamp Left and Right                                                                   |
| `light.thurston_office_ambient_light` | Thurston Office Wall Wash Left and Right                                                                   |
| `light.living_room_floor_lamps`       | Living Room Front Right and Rear Center Floor Lamps, Switch-as-X lights over the Eve Energy bottom sockets |

The Living Room scene scripts are also prerequisites. Each runs `hue.activate_scene` with `dynamic: true`, then sets `light.living_room_floor_lamps`: `script.living_room_evening_lights` plays Autumn gold with the lamps on, `script.living_room_late_night` plays November haze with them off, and `script.living_room_tokyo` plays Tokyo with them off. Hue stores brightness per scene, so the scripts leave it to the Hue app.

The individual entity IDs are in the corresponding room's `lights` array. Hue scenes continue to address their original bulbs. These files do not back up integrations, helpers, area assignments, or Hue scenes; retain ordinary HA backups for those.

## House controls

The card's `override` key names an `input_boolean` that pauses the door automations; the card refuses to load without it. `input_boolean.door_automations_override` is a prerequisite helper, not created by these exports. `automation.garage_close_after_departure`, `automation.front_door_auto_lock_after_closed`, and `automation.basement_door_auto_lock_after_closed` each require it off and also trigger when it turns off, so resuming locks and closes anything left open.

A strip of house controls sits above the floor tabs, and below the map on phones:

- **Turn all off** shows while any light in a room's `lights` list is on and turns them all off in one `light.turn_off` call.
- **Secure** shows while a room's `lock.` entity is not locked or its `cover.` entity is not closed. It locks or closes only those.
- **Pause** and **Resume** toggle the override. While paused, an "Auto-lock paused" stamp sits on the map; drag it off to resume.

## Grounds

A fourth floor, Grounds, maps the lot with the empty `front_yard` and `backyard` areas; the house, rear platforms, driveway, and walk are noninteractive context. The geometry is an abstracted, squared-off reading of the McClung lot 25 block R survey (`plans/site.jpg` in the [Grounds sheet thread](https://ampcode.com/threads/T-01a0a86f-0e76-748e-a00e-6561bf9ef87a)). Side-yard splits are diagrammatic, not fences. Neither area has an HA floor.

## Doorbell polaroids

`room.doorbell` on Foyer names the Nest doorbell's `camera`, its `ring` and `motion` event entities, the `snapshots` media folder, and the `pin` point in map coordinates. The Foyer panel opens with a live `picture-entity` feed.

Each ring or motion event pins a polaroid at the front door on the Main floor, newest three stacked. Rings carry a RING stamp; motion captions name the event type. A polaroid fades with age and expires 15 minutes after its event. Tap one to open its snapshot full screen, with buttons for the Foyer's live feed and for dismissal; or drag it off to dismiss it. Dismissals are stored per browser in `localStorage` under `house-atlas-dismissed`, keyed by `nest_event_id`.

Nest gives HA no event media for this doorbell: it advertises `CameraEventImage`, but SDM rejects `GenerateImage` for WebRTC-only cameras ("camera not supporting RTSP protocol"), and it lacks `CameraClipPreview`. The photo instead comes from Scrypted. On each event the `Front door snapshot` automation calls `shell_command.front_door_snapshot`, declared in HA's `configuration.yaml`, which has ffmpeg save the first frame of a fresh connection to Scrypted's Rebroadcast RTSP stream (`rtsp://10.10.40.43:33159/85272fedf846f071`) as `/media/doorbell/<kind>-<slot>.jpg`, where `<slot>` is the event's epoch second modulo 1000. Nest events reach HA about 3 seconds after they happen, too late for the newest frame to still show a passing person, but a fresh Rebroadcast connection replays Scrypted's prebuffer from its last keyframe, about 2.6 seconds back, so the frame lands near the event moment. Slots bound storage to 2000 files; the card resolves the slot through `media_source/resolve_media` and retries for 10 seconds until the file is no older than its event. Until then, or without one, the polaroid shows a doorbell icon.

## Pickup reminder

The Main-floor garage has a small indicator inside its top-left corner, positioned by `room.pickup.position` in map coordinates. It never changes the map's size or position. Green indicates garbage; blue indicates recycling. Only the bin symbols are visible; the pickup description remains available to screen readers. No dismissal or bin-movement detection is implied.

`sensor.trash_pickup_reminder` owns the schedule: `tomorrow`, `today`, or `hidden`, with `pickup_date` and `pickup_types` attributes. It selects today's pickup before tomorrow's from the provider-backed `sensor.trash_pickup_current_pickup` and `sensor.trash_pickup_next_pickup`. HA's local date determines the two-day window; `now()` makes HA reevaluate at each minute boundary without a browser timer. Unavailable provider data makes the reminder unavailable, which the map hides. `calendar.trash_pickup` remains the provider's calendar, not a visibility switch.

The sensor uses YAML because the Template Helper config flow cannot define custom attributes. Apply the file's list under `template:` through managed YAML editing, preserving any other template entries, and run `homeassistant.check_config`. The first template integration requires an approved Core restart; subsequent edits use `template.reload`. The sensor is active and verified against live provider data.

Run `uv run pytest tests/test_trash_pickup_reminder.py` for local-date, DST, stream selection, and unavailable-data checks. Browser checks should cover both streams, each stream alone, hidden/unavailable states, and a sensor first appearing after the map loads. Inject preview states only into the browser card's `hass` object, never into the live provider entities.

## Maintenance

Before editing, read the live dashboard, resources, and theme through HA-MCP and compare them with these copies so newer live changes are not overwritten. Use `ha_config_get_dashboard`, `ha_config_list_dashboard_resources(include_content=true)`, and `ha_config_get_yaml` for theme key `House Atlas` in `themes/house_atlas.yaml`.

Apply approved changes through HA-MCP: update the existing inline module with `ha_config_set_dashboard_resource`, the storage config with `ha_config_set_dashboard`, and the theme through managed YAML editing with diff confirmation and validation. Refresh the best-practices read-receipt required by gated tools. The instance already includes `themes` through `frontend.themes`; reload themes and select House Atlas for both backend light and dark defaults when restoring it. Refresh the browser after JavaScript changes.

Verify light/dark phone and tablet layouts, all four floors, doorbell polaroids with injected event states and slot files, room-list navigation, scene updates, and sheet dismissal versus scrolling/slider interactions. Intercept service calls when testing lock buttons; do not operate physical locks as a smoke test. Compare the resulting live configuration with these files before committing.

Global controls design: [Global controls for House](../../wayfinding/loch-highland-house/tickets/29-house-global-controls.md). Design and acceptance history: [House dashboard thread](https://ampcode.com/threads/T-01a0a859-11a2-724a-a131-fa9cdd0f2cda).
