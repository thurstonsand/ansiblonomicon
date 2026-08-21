---
status: closed
type: grilling
blocked-by: [11]
---

# Alerting and notifications

## Question

Which alerting stack does the Bunker adopt, and what is the standard pattern every producer (restic, zed, smartd, scrub cron, agent platform, watchtower) uses to report?

Inputs: shortlist from [Alerting platform landscape](11-alerting-platform-landscape.md); Thurston wants a spike proving the chosen pattern before adoption. Consumers: [Cloud backup replacement](04-backup-replacement.md) (failure + staleness alerts) and [Storage services on bare Proxmox](08-storage-services-on-bare-proxmox.md) (scrub/SMART) both defer their alerting shape here.

## Progress

Grilled 2026-08-19. Decided, **contingent on the spike passing**:

- **Stack: Hark + hosted Healthchecks.io.** Healthchecks owns schedules and dead-man state off-host; Hark is the iPhone push channel — chosen over Pushover/ntfy for its approval/prompt surface, which gives pascal (ticket 07) and the storage alerts one pipe to the phone. Fallback if the spike disappoints: Pushover, zero design change (same skeleton).
- **Producer contract (adopted)**: scheduled jobs (restic, scrub, SMART, sanoid, self-reconcile loop) wrap in systemd units pinging Healthchecks `/start` → success or `/<exit-status>`; event producers (zed/smartd via ticket 08's `storage-alert` shim) POST to Hark directly; one host-alive heartbeat check. Rules with teeth: notification failure never masks job failure (wrapper reports the job's exit status regardless, journal keeps diagnostics); secret URLs via systemd credentials from the `op` launcher role, never inline.
- **Spike: now, pre-rebuild.** Scope: HC check lifecycle (`/start` → fail → recovery), HC→Hark down/up webhook payloads, idle-phone delivery quality, one agent approval round-trip. Human prerequisites: Hark app + account, Healthchecks account, credentials into the `agent` vault.
- Open: fate of the Discord webhook (retire / passive copy / pascal's channel) — question went unanswered in round 1.

Ticket stays open until the spike passes; adoption is conditional by design.

## Resolution

**Spike passed 2026-08-20; Hark + hosted Healthchecks.io adopted.** Executed end-to-end against the live services: direct Hark webhook POST → phone; Healthchecks account wired (API key minted, stored in the `agent` vault item `Healthchecks.io` under `api key`; Hark webhook URL in `Hark (Webhooks)`); HC webhook integration "Hark" created with JSON down/up POST payloads (🔴/🟢 + `$NAME`/`$STATUS`/`$NOW` placeholders, Content-Type: application/json); a `spike-restic-sim` check driven through `/start` → `/1` (down) → success (up) via curl. All three notifications delivered to the iPhone promptly. Spike check deleted; the integration and API key are permanent residents — the rebuild's checks get created via the Management API from ansible.

Standing outcomes:

- Producer contract as in Progress above — ticket 08's `storage-alert` shim destination is the Hark webhook; ticket 04's restic alerting uses the HC `/start`→`/<exit>` wrapper.
- **Discord webhook retires.** One channel, one contract.
- Hark avatar image: serve from caddy's static site (`https://thurstons.house/…`) — cosmetic, at leisure.
- **Open follow-up, non-blocking**: approvals confirmed Pro-gated by live test 2026-08-20 (`{"ok":false,"error":"Interactive responses require Hark Pro"}` — the pricing modal omits it, the API enforces it). One-shot notifications cover every rebuild producer on the free tier. The $8/mo decision lands with ticket 07's execution; what it buys pascal: approval/yes-no/text prompts, Live Activity approval layouts, and `harkctl permissions setup` (phone-approval routing for coding-agent permission requests).
