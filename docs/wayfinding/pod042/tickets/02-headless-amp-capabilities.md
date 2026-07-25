---
status: closed
claimed: subagent-amp-research
type: research
blocked-by: []
---

# Headless Amp capabilities

## Question

What can Amp actually do as a resident, headless harness on an always-on Linux box? Establish from docs/changelogs/source: headless & CLI execution modes; the new scheduling feature (what triggers, what runs, where output goes); remote conversational access (are threads reachable from amp web/mobile such that "talk to the box from anywhere" comes free?); notification surfaces (can a thread ping the user?); auth model for an unattended machine (API key vs subscription session, expiry behavior); and how Amp itself stays updated non-interactively. Deliver a capability summary as a linked markdown asset — the self-management loop and comms tickets both hang on this.

## Resolution

[Headless Amp capabilities](../assets/amp-capabilities.md) establishes Amp as a viable headless runner: `--execute`/JSON streaming and the public `--no-tui` runner are supported, and live CLI threads are controllable from Amp web/mobile. The separately hidden `--headless [thread]` is an unsupported, entitlement-gated single-thread actor executor, not the resident-runner mode, and does not establish Automation dispatch to pod042. Scheduling can wake a saved thread or create a fresh one, but its ability to target a specific self-hosted runner remains unverified; use a local systemd timer until tested. Amp has no documented generic push/email/webhook notification for that runner, and unattended use requires a managed static `AMP_API_KEY` plus external alerting, token rotation, spend bounds, and supervised updates.
