---
status: closed
claimed: 2B (charting session)
type: grilling
blocked-by: [2, 5]
---

# Comms channel and remote access

## Question

How does pod042 reach Thurston, and how does Thurston reach it? Two halves: (1) push notifications for converge failures and repair reports — candidates include Amp's own surfaces, the existing Cloudflare hooks worker, or a push service; (2) remote conversational access to the resident agent from anywhere — possibly free via Amp's thread model, possibly needing Zero Trust plumbing. Decide the channel(s) with the Amp capabilities research in hand, favoring what the harness already provides over new infrastructure. Includes deciding the fate of a web surface: does anything replace `openclaw.thurstons.house`?

## Resolution

Grilled 2026-07-24.

- **Alerts (push)**: **Discord webhook, outbound-only** — the converge wrapper sends failure/repair reports via one HTTPS call; webhook URL lands in the agent vault (the Discord setup lives outside this repo — locate/create the webhook at build time). Deliberately independent of Amp so the failure path holds when the harness is the casualty. Secondary: experiment with Amp-side reporting for agent-run work; if it proves sufficient the Discord path stays as the dead-man's channel.
- **Conversation**: **Amp web/mobile threads are the surface.** Runners make pod042 threads startable and steerable from ampcode.com; alerts include thread links. No custom gateway, ever again — the OpenClaw gateway was the pain being escaped.
- **Remote terminal**: **Amp's `--remote-control-terminal`** on the resident runner, not a Cloudflare SSH tunnel app — `openclaw-ssh` dies without a successor. Recorded caveat: this couples remote terminal access to the runner being alive; the fallback when pod042 is sick is `truenas-ssh` (existing tunnel app) → LAN hop to pod042.
- **Web surface**: reserve **`pod042.thurstons.house`** as a placeholder — no service behind it yet, but the option stays open for static hosting or safely exposing local dev servers via Cloudflare Access. Terraform swap happens at sunset phase 2.
