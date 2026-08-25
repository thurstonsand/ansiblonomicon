---
status: open
type: research
blocked-by: []
---

# pyinfra trial: reproduce one ansible segment, judge the loop

## Question

Ansible fills the reconciliation role well but reads poorly: YAML verbosity, jinja-inside-YAML debugging, minutes-long feedback cycles, `| bool` landmines. pyinfra is the one credible same-shape alternative — agentless, inventory, idempotent operations, dry-run — written as plain Python. The decision criterion is not line count: it is **loop quality** (dry-run/diff fidelity, iteration speed, error legibility, idempotency as a testable property) and **abstraction quality** (whether pyinfra has a real analog to a role: something that hides complexity behind a high-level, parameterized behavior with defaults, composable and dependency-capable the way `zfs_maintenance` leans on `alerting`).

Reproduce the `alerting` + `zfs_maintenance` pair in pyinfra — the segment is small, freshly gauntlet-proven, and exercises templates, systemd units, handlers-on-change, role-on-role dependency, and per-tag partial runs. Compare head-to-head in a rig against the ansible original. Bound extensibility with primary sources: `@deploy` composition, operation authoring, facts authoring, defaults/data layering, what replaces tags and handlers.

Output: `research/pyinfra-trial.md` — working prototype, measured comparison, extensibility verdict, migration-cost sketch. Decision (adopt for Phase 4 greenfield vs stay) rests with the map's writer.

## Resolution

Trial executed 2026-08-25 ([pyinfra trial](../research/pyinfra-trial.md), prototype in `prototypes/pyinfra/`). pyinfra reproduced the segment to a byte-identical fingerprint (21 files, 6 units, 5 packages, 4 checks) and passed the same hammer battery. Loop: 5.3s full / 0.87s no-op / 0.87s dry vs ansible's 18.9 / 11.5 / 9.8. Abstraction: `@deploy(data_defaults=...)` is a real role analog — composition is a function call, the meta-dependency collapses to importing the dependee's defaults; handlers become `_if=did_change` lambdas; **tags have no analog** (partial runs = one entrypoint per part). Custom fact + two custom ops (healthchecks_check, zpool_property) bound authoring cost as low. Unresolved migration surfaces: docker_stack change detection over non-idempotent compose, and no osx_defaults/mas equivalent for the laptops. Side find: the ansible check.yml drift-underreporting bug (unique-POST 200), fixed in-role. Adopt-vs-stay decision remains with the user; recommended shape if adopted: pyinfra for Phase 4 greenfield (workstream F), ansible retained where its module depth pays.
