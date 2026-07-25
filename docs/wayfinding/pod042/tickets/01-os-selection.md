---
status: closed
claimed: subagent-os-research
type: research
blocked-by: []
---

# OS selection for pod042

## Question

Which OS should the pod042 VM run? Requirements: lean, dev-focused, headless, stable under unattended operation, easy to keep current, and manageable by this repo's ansible-converge approach (a strong prior toward apt-family, but the field is genuinely open — weigh immutable/atomic options like Fedora CoreOS, openSUSE MicroOS, and NixOS honestly, including what each would do to the existing role library). Consider: package freshness for dev tooling (the old OpenClaw resorted to Debian sid pinning for tmux — a smell worth eliminating), unattended-upgrade story, KVM/VirtIO guest fitness on TrueNAS, and cloud-image availability for clean provisioning. Deliver a recommendation with runner-up, as a linked markdown summary.

## Resolution

Use Debian 13 stable with its official generic cloud image and cloud-init. Keep the base stable, move fast developer tools to their native managers, and permit only explicit, single-package `trixie-backports` exceptions—never sid pinning. Ubuntu Server 26.04 LTS minimal is the runner-up, but its benefits do not justify auditing the Debian-specific apt/repository contract now. Arch was assessed: its official cloud image, cloud-init, KVM/VirtIO support, and package freshness are strong, but Arch requires reviewed full-system upgrades, can require manual News interventions, and shifts the AUR’s rebuild/review responsibility onto the operator; so it does not meet this ticket’s fully unattended requirement. The atomic and RPM options impose a platform rewrite or an unsuitable lifecycle. Full comparison and current sources: [OS selection research](../assets/os-selection.md).
