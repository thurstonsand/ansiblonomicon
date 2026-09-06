---
status: closed
type: research
blocked-by: []
---

# mise trial: the same segment, solely mise

## Question

Ticket 19 proved pyinfra reproduces the `alerting` + `zfs_maintenance` segment byte-identically with a ~13× faster loop. Third contender, user-preferred at this time: **mise alone** — tools, env, and tasks as the entire reconciliation driver, no ansible, no pyinfra. Mise is already on every host as a host tool, which makes "the config manager is just the tool manager" an attractive collapse of the stack.

Reproduce the same segment solely with mise. Two questions carry extra weight:

1. **Modularity**: the config must not be one massive `mise.toml`. Bound, from primary sources, every mechanism mise offers for compartmentalizing: config file hierarchy and precedence, `task_config.includes`, file tasks in task directories (subdirectory namespacing), per-environment configs, and whatever else exists. Produce an actual folder structure that reads like roles — an `alerting/` and a `zfs-maintenance/` unit, each owning its tasks, templates, and defaults, composable the way the ansible dependency worked.
2. **Earned properties**: idempotency, dry-run, diff, and change reporting are not native to imperative tasks. What do disciplined patterns recover (guard commands, `sources`/`outputs` freshness, wrapper conventions), what stays lost, and at what authoring cost per task?

Same rig, same fingerprint comparison, same hammer battery, same measured loop numbers against the ansible and pyinfra baselines.

Output: `research/mise-trial.md` + prototype under `prototypes/mise/`. Decision rests with the user.

## Resolution

Trial executed 2026-08-30 ([mise trial](../research/mise-trial.md), prototype in `prototypes/mise/`). Byte-identical fingerprint vs ansible; fastest of the three: 4.5s cold / 0.74s no-op / 0.45s check, vs pyinfra 5.3/0.85/0.86 and ansible 19.0/12.1/10.2. Modularity answered by **monorepo mode** (`monorepo_root = true` + `config_roots`): each unit owns its config root, env, vars, tools, and `//units/<name>:task` namespace; largest config file 63 lines; the meta-dependency splits into an `env._.file` defaults import plus a `depends` ordering edge. The price: a 343-line hand-written reconciliation runtime (`lib/reconcile.sh` + `report.sh`) supplying ensure-primitives, check mode with unified diffs, handlers, change ledger, and recap — everything ansible gives free. Recovered: check, diff, handlers, change reporting, API drift detection, `.miseremove` retirement (demonstrated). Lost or hazardous: `sources`/`outputs` freshness is wrong for reconciliation; `--dry-run` evaluates nothing; **parallel-by-default breaks convergence** (dpkg-lock and API races — must pin ordering); a failed resource does not fail the run unless the primitive exits; recap vanishes on failure (`depends_post` skipped); no `tags: [always]` analog, so partial runs skip retirement; minijinja strict-mode errors print the full process environment **including secrets**; env precedence is inverted vs role defaults (unit default clobbers host fact without a `default()` wrapper). Adopt-vs-stay decision rests with the user, three measured columns on the table.
