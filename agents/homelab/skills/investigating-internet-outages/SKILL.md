---
name: investigating-internet-outages
description: Lists the data sources for an internet outage or a degraded connection. Use when the internet dropped, is down, or is flaky.
---

# Investigating internet outages

On pod042, from the repository root, `mise run outage:report -- SINCE UNTIL` (ISO 8601 with a zone, such as `2026-11-08T05:40Z`) collects the window into one directory and prints its path:

- `pod042-journal.log`: `tailscaled` DERP and netcheck failures, and `dockerd` resolver timeouts against `10.10.10.1`, bracket the window as pod042 saw it.
- `pon-samples.jsonl`: pon-monitor's row every 15 seconds with `wan_up`, `stick_reachable`, stick and optic temperatures, `ploam_state`, and optical power.
- `pon-captures/`: the stick's snapshots taken as the WAN failed, with its uptime, reset cause, `pontop` pages, and kernel log. The stick's own clock is wrong.
- `unifi-events.json`: the controller's event log, including `ISP_PACKET_LOSS`, `NETWORK_WAN_FAILED`, and `NETWORK_WAN_RESTORED`.
- `unifi-devices.json` and `unifi-system.json`: each device's `uptime`, the UDM's WAN monitors, its `startupTime`, and its firmware update state and schedule.
- `stick-live.log` and `unifi-smoke.txt` are taken now, not for the window.

**The UDM's own logs**, which survive its reboots, through the support file with the same controller login: `POST /api/support/file/generate` with `{"recreate": true}`, give it a few minutes, then `GET /api/support/file/download` for a tarball of about 120 MB. Look in `system/var/log/` for `kern.log` (SFP link), `daemon.log` and `messages` (`udhcpc`, `wan-failover`, `sfp-handler`), and `reboot-time.log`, and in `unifi-core/`. Over SSH as `root@10.10.20.1` reads the same logs live, but pod042 holds no key for it.
