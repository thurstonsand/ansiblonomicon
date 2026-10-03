---
status: closed
type: grilling
blocked-by: []
---

# Global controls for House

## Question

Where should whole-house actions live in the House dashboard, and what should they target and report? Start with **Turn off all lights** and **Lock all doors**.

Decide placement on the phone-first layout and tablet dock, whether membership is explicit or follows HA areas/entities, and how to show progress, unavailable devices, and partial failures without claiming the whole house is off or locked prematurely. Light groups and their individual members must not receive duplicate commands.

## Resolution

Shipped on 2026-10-02 in [the global controls thread](https://ampcode.com/threads/T-01a0fce9-bd64-75a4-9040-7f68d7938e55); see the [House dashboard README](../../../operations/house-dashboard/README.md#house-controls).

- A strip of house controls sits above the floor tabs on wide layouts and below the map on phones, so the map stays first.
- **Turn all off** appears only while a light is on. It targets the union of every room's `lights`, which lists individual bulbs only, so groups never receive duplicate commands. Move to an explicit list if a stray entity needs excluding.
- **Secure** appears only while a door is unlocked or the garage is open. It locks every unlocked lock and closes an open cover; global unlock is not offered.
- **Pause** sets `input_boolean.door_automations_override`, which gates the garage auto-close and both door auto-locks. While paused, a stamp sits on the map; drag it off, or press Resume, to restore the automations.
- Actions execute directly. Progress and partial failures come from the entities' own states updating the strip.

## Context

Deferred by Thurston after accepting the live dashboard in [the House dashboard thread](https://ampcode.com/threads/T-01a0a859-11a2-724a-a131-fa9cdd0f2cda). Capture only; do not begin implementation until this ticket is picked up.

The existing dashboard has explicit room controls, HA light groups, dynamically discovered Hue scenes, system-following light/dark themes, phone room sheets, and tablet docked controls. Existing room actions execute directly; Thurston explicitly rejected confirmation dialogs and hold gestures for unlocking. Global unlock is not requested.

Manage HA through the connected HA-MCP tools, not a parallel Ansible-owned configuration tree.
