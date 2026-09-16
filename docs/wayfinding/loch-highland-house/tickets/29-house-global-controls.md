---
status: open
type: grilling
blocked-by: []
---

# Global controls for House

## Question

Where should whole-house actions live in the House dashboard, and what should they target and report? Start with **Turn off all lights** and **Lock all doors**.

Decide placement on the phone-first layout and tablet dock, whether membership is explicit or follows HA areas/entities, and how to show progress, unavailable devices, and partial failures without claiming the whole house is off or locked prematurely. Light groups and their individual members must not receive duplicate commands.

## Context

Deferred by Thurston after accepting the live dashboard in [the House dashboard thread](https://ampcode.com/threads/T-01a0a859-11a2-724a-a131-fa9cdd0f2cda). Capture only; do not begin implementation until this ticket is picked up.

The existing dashboard has explicit room controls, HA light groups, dynamically discovered Hue scenes, system-following light/dark themes, phone room sheets, and tablet docked controls. Existing room actions execute directly; Thurston explicitly rejected confirmation dialogs and hold gestures for unlocking. Global unlock is not requested.

Manage HA through the connected HA-MCP tools, not a parallel Ansible-owned configuration tree.
