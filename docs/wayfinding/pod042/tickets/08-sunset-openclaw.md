---
status: open
claimed: subagent-vm-shutdown
type: task
blocked-by: []
---

# Sunset OpenClaw

## Question

Retire OpenClaw completely: stop and delete the VM (via the `truenas_vms.openclaw` entry and TrueNAS, including the `performance/openclaw` zvol); remove the playbook, `openclaw.config.yml`, inventory target, `poe openclaw` tasks, and openclaw-specific roles/monitors from this repo; tear down `openclaw.thurstons.house` DNS/Zero Trust in terraform; scrub AGENTS.md's OpenClaw section; add retired paths to `.ansibleremove` where applicable. Decide in passing whether the 1Password service account is revoked or inherited (coordinate with the secrets ticket if it lands first). Everything is in git; deletion is safe. May run before or in parallel with pod042 design — but if pod042 reuses the IP or zvol name, this must land first.

Execution is split: **phase 1** (shut the VM down, stop it consuming resources) runs now; **phase 2** (deleting config, repo state, DNS/Zero Trust) is deferred while the old setup remains available as reference for pod042 design.

### Phase 1 log

On 2026-07-24, VM 12 (`OpenClaw`) was gracefully shut down through TrueNAS middleware and its runtime autostart was disabled. It changed from `RUNNING` with `autostart: true` to `STOPPED`/`SHUTOFF` with `autostart: false`; the Ansible inventory now preserves that state. No VM, zvol, repository configuration, DNS, or Zero Trust resources were deleted.
