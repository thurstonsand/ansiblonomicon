---
status: closed
type: research
claimed: subagent
blocked-by: []
---

# Alerting platform landscape

## Question

What should carry the Bunker's alerts — backup failures/staleness, ZFS scrub and SMART results, service health, agent-platform reports? Thurston has seen interesting patterns worth evaluating: https://hark.ryan.ceo, ntfy, and the broader open-source alerting space.

Survey against primary sources (project docs/repos, pricing pages):

- Push-notification platforms: ntfy (self-hosted + hosted), Gotify, Pushover, hark.
- Dead-man's-switch / heartbeat monitoring: Healthchecks.io (hosted + self-hosted), Uptime Kuma push monitors — the pattern where *silence* alerts, which backup jobs need.
- Aggregation/routing layers: Apprise as a many-backend fan-out.
- The incumbent pattern: plain Discord webhook (pod042's choice) — what it lacks vs the above.
- Weigh: self-hosted on the very machine being monitored (conflict of interest for host-down alerts), phone delivery quality, systemd/cron integration ergonomics (curl-ability), maintenance burden.

Deliver a shortlist (2–3) with tradeoffs and a recommended pairing of push channel + dead-man's monitor; the decision belongs to [Alerting and notifications](12-alerting-decision.md).

## Resolution

Research completed in [Alerting platform landscape](../research/alerting-platform-landscape.md). It shortlists Hark + hosted Healthchecks.io (recommended to spike), Pushover + hosted Healthchecks.io, and hosted ntfy + hosted Healthchecks.io; ticket 12 retains the final decision.
