---
name: browsing
description: Automates browsers with Browse on personal hosts and agent-browser in Amp orbs. Use for navigating websites, filling forms, authenticated workflows, screenshots, browser testing, and recording browser behavior.
---

# Browsing

Choose by where the browser runs, not by which agent harness is calling it:

- **Personal hosts:** use the Browse CLI. Run `browse skill` and follow that installed version's guide before the first browser command. `browse doctor` diagnoses an unavailable relay or extension. Mise owns CLI installation and upgrades (`mise upgrade npm:@opencode/browse`); the browser owns extension updates. Use CLI-only setup rather than adding MCP servers to harness-managed configuration.
- **Amp orbs:** use their preinstalled agent-browser. Run `agent-browser skills get core` before the first browser command, then load specialized guides with `agent-browser skills get <name>` when needed. No Browse extension or personal browser pairing is required in an orb.
- **Work:** neither tool is configured. Keep its browser workflow separate.

Browse requires a running Chromium-family browser with its extension installed and paired. If setup is incomplete, report that boundary rather than silently switching tools. On pod042, load `using-pod042-desktop` for the shared browser and native desktop controls.

Give each task its own named session. At completion, delete only that session; Browse's `tabs cleanup` affects other agents' sessions too.

Browse cannot drive browser chrome or other extensions, including 1Password's passkey UI. Use separately authorized native desktop controls or hand those interactions to the user; do not weaken Browse's guardrails or assume a page click completed authentication. Verify the resulting page state.
