---
status: closed
type: task
blocked-by: []
---

# Dell laptop: eGPU and Windows/Omarchy dual boot

## Question

Stub. New Dell XPS 14 with a Sonnet eGPU, dual-booting Windows and Omarchy. The enclosure decision is already charted in Bunker Rebuild's [eGPU enclosure qualification](../../bunker-rebuild/tickets/22-egpu-enclosure-qualification.md); the Omarchy dual-boot setup itself (repo-declared, laptop playbook) has no map yet — chart it as its own effort when the hardware is qualified.

## Resolution

The laptop is acquired and Windows/Omarchy dual boot is configured. Onboarding the Omarchy side into this repo remains separate work and now depends on migrating the dotfiles fully from chezmoi to mise; chart that migration and onboarding as their own effort.
