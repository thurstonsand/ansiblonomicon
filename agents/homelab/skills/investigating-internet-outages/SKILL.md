---
name: investigating-internet-outages
description: Lists the data sources for an internet outage or a degraded connection. Use when the internet dropped, is down, or is flaky.
---

# Investigating internet outages

Run everything on pod042 from the repository root. Pass `journalctl` absolute timestamps; a bare `23:58` means today.

1. **pod042's journal**: `sudo -n journalctl --since "YYYY-MM-DD HH:MM" --until "..."`. `tailscaled` DERP and netcheck failures, and `dockerd` resolver timeouts against `10.10.10.1`, bracket the window as pod042 saw it.
2. **pon-monitor**: `docker logs pon-monitor-pon-monitor-1`, and its data in `/mnt/black-box/docker/pon-monitor/pon-monitor/data/`. All of its timestamps are UTC.
   - `samples.jsonl`: one row every 15 seconds with `wan_up`, `stick_reachable`, stick and optic temperatures, `ploam_state`, and optical power.
   - `captures/<UTC>.log`: a snapshot of the stick taken as the WAN fails, with its uptime, reset cause, `pontop` pages, and kernel log. The stick's own clock is wrong.
   - The live stick: `docker exec pon-monitor-pon-monitor-1 sh -c 'sshpass -p "$PON_STICK_PASSWORD" ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@192.168.11.1 "uptime; logread"'`.
3. **The UniFi controller**: log in with `login()` from `scripts/unifi_api.py`, under `./scripts/fnox-host exec --secret UNIFI_USERNAME --secret UNIFI_PASSWORD -- uv run python`.
   - `POST /proxy/network/v2/api/site/default/system-log/all` with `timestampFrom`, `timestampTo` (epoch milliseconds), `pageSize`, and `pageNumber`: the event log, including `ISP_PACKET_LOSS`, `NETWORK_WAN_FAILED`, and `NETWORK_WAN_RESTORED`. The `admin-activity` log sits beside it.
   - `GET /proxy/network/api/s/default/stat/device`: each device's `uptime`, plus the UDM's `wan1`, `wan2`, and per-WAN `uptime_stats` monitors.
   - `GET /api/system`: the UDM's `startupTime`, WAN ports plugged, and the firmware and application update state and schedule.
4. **`mise run unifi:smoke`**: read-only checks of the WAN, the stick's management route, DNS, and the SFP link.
5. **The UDM's own logs**, which survive its reboots, through the support file with the same controller login: `POST /api/support/file/generate` with `{"recreate": true}`, give it a few minutes, then `GET /api/support/file/download` for a tarball of about 120 MB. Look in `system/var/log/` for `kern.log` (SFP link), `daemon.log` and `messages` (`udhcpc`, `wan-failover`, `sfp-handler`), and `reboot-time.log`, and in `unifi-core/`. Over SSH as `root@10.10.20.1` reads the same logs live, but pod042 holds no key for it.
