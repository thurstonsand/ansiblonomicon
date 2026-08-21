---
status: open
type: research
blocked-by: []
---

# Fiber bypass device stability

## Question

The AT&T fiber bypass device — the one that supplants the required AT&T gateway at the fiber entry point — takes the house offline roughly weekly. Root-cause it and make it stable, since it moves to the new house (also AT&T fiber).

Symptoms: every few days to a week, internet drops entirely. Recovery ritual: reboot the UDMP *and* power-cycle the bypass device for a few seconds. Cause unknown.

Branches to settle:

- Device identified: an **XGS-PON stick** (WAS-110-class, 8311-community bypass). Login creds in 1Password under the item named "XGS PON" (agent vault), mgmt at `https://192.168.11.1`.
- **Firmware upgraded 2026-08-19**: v2.8.0 → v2.8.3 (bank B → A; B keeps v2.8.0 as fallback) via `scripts/upgrade-xgs-pon.sh` + `runbooks/xgs-pon-upgrade.md`. Verified: PON O5.1, internet restored in ~4 min, metrics endpoint live at `/cgi-bin/luci/8311/metrics` (post-upgrade: cpu 78.5/76.0°C, optic 68.9°C — still hot; cooling remains the open action).
- **Cooling decision deferred to the new house (2026-08-20)**: no fan purchase pre-move; the user will evaluate a naturally better-ventilated placement at the new house first. Post-move step: place, let temps settle 24–48h, re-read the metrics endpoint, and only then decide on active cooling. Until then the thermal-lockup hypothesis stands untreated — capture-before-reboot remains the rule on any outage, including during the move window.
- Known instability patterns for that method: DHCP lease renewal against AT&T's network, ONT firmware, heat, auth re-negotiation.
- Diagnostics to capture *before* the move while the failure is reproducible: logs from the device and UDMP WAN state at failure time.
- Mitigations: firmware, config, watchdog automation (detect WAN-down → power-cycle via smart plug?), or replacing the method.

Output: root cause or best hypothesis, plus the stabilization plan for the new house.

## Research log

- 2026-08-19: Read-only inspection confirmed a WAS-110 on 8311 Community Firmware basic v2.8.0 with a healthy current PON state (O5.1), good optical power, and a 10G host link. Its SoC thermal zones were 82.4°C and 79.7°C after 5d 13h uptime, making insufficient cooling the leading hypothesis; no root cause is confirmed because the historical RAM log began at the last physical power cycle. [Research and failure-time capture plan](../research/fiber-bypass-stability.md) are complete. This ticket remains open until the next outage is captured before recovery, which requires the user's device access.
