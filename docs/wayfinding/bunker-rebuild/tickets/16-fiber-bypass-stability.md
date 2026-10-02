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
- Mitigations: firmware, config, or replacing the method. If instability returns, UniFi's **Power Cycle on Internet Loss** is a candidate remediation: place the WAS-110 on a controllable PDU outlet and permit one delayed cycle per outage, after proving the trigger cannot remove its own control path or turn a provider outage into a reboot loop.

Output: root cause or best hypothesis, plus the stabilization plan for the new house.

## Research log

- 2026-09-19: The direct-service WAS-110 has produced no user-visible recurrence for roughly two to three weeks. Current metrics remain clean at PLOAM O5.1, Rx -15.56 dBm, Tx 5.67 dBm, CPU 73.7/71.6°C, and optic 62.2°C. The new placement is still warm but materially cooler than the pre-move 82.4/79.7°C reading. Continue observation for two more weeks; if no real outage recurs, close this as stabilized by firmware plus placement rather than adding active cooling.

  The monitor recorded six capture events between August 28 and September 13, plus one isolated failed sample on September 18. Five events lasted roughly one to three minutes; the September 8 event overlaps 10 hours of rebuild work. In every event, both WAN probes and the stick management endpoint disappeared together, which does not resemble the earlier degraded-but-reachable failure. None produced stick diagnostics: OpenSSH exited with `No user exists for uid 1000` because the container ran as numeric `1000:3000` without a matching passwd entry. The repaired image now declares that user and group; it was deployed on September 19, returned healthy, sampled both the WAN and stick successfully, and completed the same read-only SSH command the next capture will use. Separately, repeated Healthchecks delivery failures on September 19 were DNS failures from the container, not proof of a PON outage; direct-IP WAN probes and current stick metrics remained healthy.

- 2026-08-27: **First outage since the firmware upgrade, and the UDMP captured it even though the stick did not.** 13:35:52 the WAN failover monitors went to 100% DNS loss; 13:36:06 dpinger reported 57% ICMP loss with 24,003 ms latency to 1.1.1.1 and 3,793 ms to 8.8.8.8. The user power-cycled the stick at 13:36:41 (`dmesg` on the UDMP: `AL_ETH_LM_MODE_10G_OPTIC -> DISCONNECTED`), it booted at 13:37:17, and WAN was declared up at 13:38:54 on the same lease, 108.207.130.230, with no DHCP renewal. The UDMP was not rebooted; its uptime is unbroken since 2026-08-21.

  What this rules out: **the host-link wedge**. `dmesg` shows zero eth9 link events between boot on 08-21 and the manual unplug, so the 10G SFP+ link stayed up through the whole failure. `ip -s link` shows 0 RX/TX errors. And this was the *only* WAN transition in 6d10h of uptime, so the weekly cadence has not obviously held since the upgrade.

  What it points at instead: degradation, not a lockup. 57% loss with 24-second latency is a path that is passing some traffic badly, which is not what a wedged SoC or a dead PON looks like. Because the stick was pulled inside 50 seconds, we do not know whether it would have recovered on its own, and its RAM log now starts at the replug. Post-recovery state is clean: O5.1, no alarms, 0 BIP / 0 corrected / 0 uncorrected FEC codewords over 3.7e9, 0 HEC errors, Rx -19.5 dBm (in range; no earlier Rx figure was recorded to compare against), Tx 5.7 dBm, cpu 75.8/73.5 °C, optic 65.7 °C — cooler than the 2026-08-19 post-upgrade 78.5/76.0, but still above the 60 °C guidance, and cooling is still undone.

  The standing capture rule keeps losing to reflex: a human under an internet outage power-cycles before collecting anything. So the rule is now a program. The `pon-monitor` stack samples `/cgi-bin/luci/8311/metrics` every 15 s into `{{ docker.config_base }}/pon-monitor/pon-monitor/data/samples.jsonl`, and after two consecutive failed HTTPS probes it SSHes the stick for the full read-only capture — uptime, reset cause, thermal zones, PLOAM, optics, alarms, FEC, GTC, host link, `dmesg`, `logread` — into `data/captures/<utc>.log`. The Hark alert spools to `data/spool/` rather than posting inline: it is raised exactly when the path to Hark is down, so delivery waits for the first successful probe after recovery. Deployed on truenas 2026-08-27 and wired into the pod042 playbook for the cutover; liveness rides on the `truenas-pon-monitor` Healthchecks check. The next event should arrive with its own evidence attached.

- 2026-08-19: Read-only inspection confirmed a WAS-110 on 8311 Community Firmware basic v2.8.0 with a healthy current PON state (O5.1), good optical power, and a 10G host link. Its SoC thermal zones were 82.4°C and 79.7°C after 5d 13h uptime, making insufficient cooling the leading hypothesis; no root cause is confirmed because the historical RAM log began at the last physical power cycle. [Research and failure-time capture plan](../research/fiber-bypass-stability.md) are complete. This ticket remains open until the next outage is captured before recovery, which requires the user's device access.
