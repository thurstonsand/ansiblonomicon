---
status: open
type: task
blocked-by: [9]
---

# Purge legacy references: openclaw and old-pod042

## Task

After cutover, sweep the repo for dead identities and retire them declaratively:

- **openclaw**: playbook (`ansible/playbooks/openclaw.yml`), inventory (`inventory/targets/openclaw.yml`), the `openclaw-vm` declaration in `truenas_vms`, its DNS record and `*-ssh` tunnel hostname (terraform), the retained reference image on `capacity`, poe task, ssh config entries, and any CONTEXT.md mention (already flagged legacy there).
- **old pod042 (the VM)**: the `truenas_vms` entry, VM-era provisioning in its playbook (the playbook itself is reborn as the *host* reconcile — pod042 is the Debian server now, per ticket 07), the NFS symmetric-path dataset wiring (`/mnt/performance/pod042`), docker-over-ssh context, and stale wayfinding cross-references outside the closed pod042 map.

Use `.ansibleremove`/`.chezmoiremove` where a removal must propagate to a live host; most of this dies with TrueNAS at cutover and needs only repo deletion.

Verification: `rg -i 'openclaw'` returns only historical wayfinding/design records; `rg 'pod042'` returns only the host identity and closed-map history.
