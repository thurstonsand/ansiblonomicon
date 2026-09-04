# mise trial: the same segment, a third time

Ticket 20. Prototype: `../prototypes/mise/`. Rig: the ticket-19 rig, rebuilt unchanged from `../prototypes/pyinfra/rig/prep.sh` — Lima, arm64 Debian 13, real ZFS, file-backed `ark`/`black-box`, mock Healthchecks/Hark on 127.0.0.1:8099. All three tools were measured in the same VM inside the same three minutes, so the Ansible and pyinfra columns here are fresh measurements rather than quotes from the last report.

## Verdict

mise is a sufficient skeleton, and the modularity answer is better than the ticket assumed. **Monorepo mode is a role system.** `monorepo_root = true` plus `[monorepo].config_roots` gives every unit its own config root with its own `[env]`, `[vars]`, `[tools]` and tasks, namespaced `//units/alerting:heartbeat`, with a real dependency graph across units and no monolithic file anywhere. No config file in the prototype exceeds 63 lines, and the two unit configs are 29 and 39.

It converges the segment **byte-identically** and it is the fastest of the three: 4.5 s cold, 0.74 s converged, against pyinfra's 5.3/0.85 and Ansible's 19.0/12.1.

The cost is concentrated in one place and it is large: **mise has no reconciliation model, so you write one.** The runtime is 343 lines of shell that implement idempotency, change accounting, check mode, unified diffs and handlers, because none of those exist in a task runner. Once written, per-resource cost is at or below Ansible's — the four zedlets plus their conditional restart are six lines against Ansible's sixteen. But those 343 lines are a load-bearing piece of infrastructure with no tests, no upstream, and no one else maintaining it, and every bug in it is a bug in every host.

Two findings are worth reading even if the trial goes nowhere. mise runs the dependency graph **in parallel by default**, and the first converge in this trial had four tasks fighting over the dpkg lock and three Healthchecks registrations racing through the same read-modify-write. And minijinja's otherwise excellent template errors **print the entire process environment** as "referenced variables", which on a host holding real credentials is an unacceptable failure mode without a wrapper.

## 1. The loop, measured

Same VM, same minute, each tool starting from an identical reset (`rig/reset.sh`). Ansible scoped with `--tags alerting,sanoid,scrub,smartd,zed`; pyinfra running `deploy.py`; mise running `mise run converge`. All three target localhost.

| | Ansible 12 | pyinfra 3.10 | mise 2026.8.14 |
|---|---|---|---|
| full converge from bare host | 19.0 s | 5.3 s | **4.5 s** |
| no-op re-run | 12.1 s | 0.85 s | **0.74 s** |
| check/dry run with file diffs | 10.2 s | 0.86 s | **0.45 s** |
| partial run (scrub only) | 4.2 s | 0.35 s | **0.25 s** |
| plan-only (no state read at all) | — | — | 0.03 s |
| units of work | 68 tasks, 32 changed | 41 ops, 39 changed | 42 resources, 41 changed |

The Ansible numbers are higher than ticket 19's because `alerting/tasks/check.yml` grew a GET and a `set_fact` per check when the drift bug was fixed — eight more tasks, and Ansible pays a forked interpreter for each.

mise beats pyinfra because it does less: no Python interpreter start, no fact gathering pass, no operation graph. `mise run converge` is thirteen `bash` processes and a scheduler. That is also the reason for the gap in the check column, where mise's 0.45 s is doing exactly the same reads pyinfra's 0.86 s dry run does.

The 0.03 s row is `mise run --dry-run`, and it is not a plan. It prints the tasks in the order they would run and the command line of each, and evaluates nothing:

```
$ mise run --dry-run converge
[//:ledger-begin] $ sudo install -m 0644 -o "$(id -un)" /dev/null "$RECONCILE_L…
[//units/base:retire] $ ~/…/units/base/mise-tasks/retire
[//units/alerting:scripts] $ ~/…/units/alerting/mise-tasks/scripts
[//units/base:converge] $ true
[//units/alerting:heartbeat] $ ~/…/units/alerting/mise-tasks/heartbeat
…
```

Useful for checking the graph, useless for deciding whether to apply. The real check mode is the one the runtime implements, and it is measured in the row above.

## 2. Modularity

### Every mechanism mise offers

Bounded from the docs and verified against 2026.8.12/2026.8.14 in the rig.

**Config file hierarchy.** Nine filenames per directory, searched from the cwd upward, top overriding bottom: `mise.local.toml`, `mise.toml`, `mise/config.toml`, `mise/conf.d/*.toml`, `.mise/config.toml`, `.mise/conf.d/*.toml`, `.config/mise.toml`, `.config/mise/config.toml`, `.config/mise/conf.d/*.toml`. Merge behaviour differs per section: `[tools]`, `[env]` and `[settings]` merge additively with override; **`[tasks]` are replaced whole per task name**, so a higher-precedence definition of `converge` does not merge with a lower one.

**conf.d fragments.** Real, and the closest thing to a drop-in directory: every non-hidden `.toml` in `mise/conf.d`, `.mise/conf.d` or `.config/mise/conf.d` loads alphabetically. They share one config root, so they split a file without creating a namespace. Note the live migration: dotted fragment names like `node.tools.toml` are deprecated and will select an environment after mise 2027.8.10; `env_conf_d = true` opts in early.

**Config environments.** `mise.<MISE_ENV>.toml`, set with `-E`, `MISE_ENV`, or `env = [...]` in `.miserc.toml`. Multiple environments compose, last wins. With `auto_env`, platform names (`unix`, `linux`, `macos-arm64`) become environments automatically. This is a `dev`/`prod` axis, not a role axis — useful here for the laptop/pod042 split, not for compartmentalizing units.

**`task_config.includes`.** Names the toml task files and file-task directories a config scope searches. It **replaces** the defaults rather than adding to them, entries render as Tera templates, last entry wins on a name collision, and `git::` URLs pull task directories or files from other repositories with a `?ref=`. The remote form is the closest mise has to `ansible-galaxy`, and it is worth remembering for the day a role wants to live in its own repo.

**File tasks and directory namespacing.** Executable files in `mise-tasks/`, `.mise-tasks/`, `mise/tasks/`, `.mise/tasks/` or `.config/mise/tasks/` are tasks. Subdirectories prefix the name: `mise-tasks/test/units` is `test:units`. Configuration rides in `#MISE` comments, argument parsing in `#USAGE`. The file must be executable, which is a trap: two of this prototype's tasks were invisible until `chmod +x`, with no warning of any kind.

**Monorepo mode.** `monorepo_root = true` plus an explicit `[monorepo].config_roots` list. Each listed directory is a config root with its own configuration; its tasks are addressed `//units/alerting:heartbeat` from anywhere, `:heartbeat` from inside it, and `./...:x` relative to the declaring task. Tools, env and vars layer from ancestors down. Wildcards select across projects (`//...:converge`, `'//units/alerting:*'`). `[task_templates]` at the root plus `extends` in a project deduplicates task shapes.

**`[vars]` and `env._` directives.** `[vars]` are template-only values that follow the config hierarchy and can be overridden per task. `env._.file` loads dotenv, JSON, YAML or TOML **relative to the config file that declares it**, which is the mechanism this prototype uses for cross-unit imports. `env._.source` runs a shell script; `env._.path` appends to PATH.

**`ceiling_paths`.** In `.miserc.toml`, stops config discovery above a directory. Required here: the prototype sits inside the ansiblonomicon checkout, and without a ceiling the repo's own root `mise.toml` layers over it and drags in python, node, stylua, opentofu and hk. It is also the only way to guarantee a monorepo root is actually the root.

### The prototype

```
prototypes/mise/
├── mise.toml                          63 lines — host facts, entrypoints   (playbooks/pod042.yml)
├── .miserc.toml                        5 lines — ceiling_paths
├── .miseremove                                 — retired paths             (.ansibleremove)
├── host/pod042.json                            — host facts that are lists (group_vars/pod042.yml)
├── lib/
│   ├── reconcile.sh                  255 lines — the reconciliation runtime
│   └── report.sh                      27 lines — PLAY RECAP
└── units/
    ├── base/
    │   ├── mise.toml                   8 lines
    │   └── mise-tasks/retire          29 lines                        (tasks/remove_retired_paths.yml)
    ├── alerting/
    │   ├── mise.toml                  29 lines — defaults              (roles/alerting/defaults/main.yml)
    │   ├── interface.env              3 values — the exported contract  (roles/zfs_maintenance/meta/main.yml)
    │   ├── lib/check.sh               61 lines                         (roles/alerting/tasks/check.yml)
    │   ├── mise-tasks/scripts         23 lines ┐
    │   ├── mise-tasks/heartbeat       24 lines ┘                       (roles/alerting/tasks/main.yml)
    │   └── templates/*.j2              5 files — unchanged from the role
    └── zfs-maintenance/
        ├── mise.toml                  39 lines — defaults + the import
        ├── defaults.json                       — defaults that are not scalars
        ├── mise-tasks/sanoid          26 lines
        ├── mise-tasks/scrub           38 lines
        ├── mise-tasks/smartd          19 lines
        ├── mise-tasks/zed             25 lines
        └── templates/*.j2              8 files — unchanged from the role
```

`mise tasks deps` draws the whole thing, which no other tool in this bakeoff does:

```
//:converge
├── //units/zfs-maintenance:converge
│   ├── //units/zfs-maintenance:zed
│   │   └── //units/alerting:converge
│   │       ├── //units/alerting:heartbeat
│   │       │   └── //units/alerting:scripts
│   │       │       └── //:ledger-begin
…
└── //units/base:converge
    └── //units/base:retire
```

### The meta-dependency, both halves

`meta/main.yml: dependencies: [alerting]` does two things at once, and mise needs a different mechanism for each.

**Defaults in scope** is `env._.file`. `units/alerting/interface.env` is the exported contract; `units/zfs-maintenance/mise.toml` imports it:

```toml
[env]
_.file = "../alerting/interface.env"
```

`mise run //units/zfs-maintenance:scrub` on its own then has `ALERTING_BIN_DIR`, `ALERTING_STATE_DIR` and `ALERTING_HEALTHCHECKS_TIMEZONE` in scope with no alerting task in the run, which is exactly the property the Ansible dependency exists to provide. It is more honest than Ansible's version, because the file makes the interface a thing you can read.

**Ordering** is a separate edge, and it has to be declared on every leaf. `depends` is a DAG that mise schedules in parallel, so listing `//units/alerting:converge` alongside `:sanoid` in zfs-maintenance's `converge` orders nothing. Each part carries the edge instead:

```bash
#MISE depends=["//units/alerting:converge"]
```

Four repetitions of one line. Ansible's linear play order gives this away.

### Where it is least-bad rather than good

Three seams, all found by building it.

**Precedence runs the wrong way for roles.** In Ansible, `defaults/main.yml` is the lowest layer and `group_vars` overrides it. In mise, a unit's config is *deeper* than the root's and therefore *higher* precedence, so a bare default in a unit clobbers the host fact. Measured:

```toml
# root mise.toml            [env] ZED_THROTTLE_SECONDS = "1200"   ← host fact
# units/zfs/mise.toml       [env] ZED_THROTTLE_SECONDS = "900"    ← unit default
$ mise run //units/zfs:show
throttle=900
```

The fix is one wrapper per default, and it works:

```toml
SMART_SCHEDULE = "{{ env.SMART_SCHEDULE | default(value='(S/../.././02|L/../01/./03)') }}"
```

With the host silent, the default applies; with the host setting it, the host wins. Every default in both units is written this way. It is noisy and it is easy to forget, and forgetting it fails silently in the direction of ignoring the host.

**An exported default cannot keep that property.** `interface.env` is a dotenv file, so no templating, so no `default()` wrapper. Anything alerting exports to its consumers is a fixed value that only a process-environment variable can override. The alternative is duplicating the wrapper in every consuming unit, which is the duplication `meta/main.yml` exists to prevent.

**A dotenv file cannot carry a path relative to its exporter.** The sourceable half of alerting's contract — `lib/check.sh`, the `check.yml` analog — has to be rebuilt from `{{ config_root }}` in each consumer:

```toml
ALERTING_CHECK_LIB = "{{ config_root }}/../alerting/lib/check.sh"
```

That line hardcodes the sibling layout into the consumer. It is the worst line in the prototype and I do not have a better one.

**`[env]` and `[vars]` hold scalars only.** Anything shaped — the two scrub entries, the sanoid dataset list, the retention table — leaves the config entirely. Host facts live in `host/pod042.json`, unit defaults that are not scalars live in `units/zfs-maintenance/defaults.json`, and the renderer layers the second under the first because mise cannot merge them:

```bash
minijinja-cli --strict --trim-blocks --py-compat --env \
  "$template" "$RECONCILE_DEFAULTS" "$RECONCILE_FACTS" "$@"
```

Ansible carries `zfs_maintenance_scrubs` as a native list in `group_vars` and merges it with the role default for free. This is the single largest expressive gap, and it is not fixable from the outside.

## 3. Earned properties

### What discipline recovers

Everything, at the price of a runtime. `lib/reconcile.sh` gives each primitive the same shape: read actual, compare to desired, record `ok` or `changed`, and under `RECONCILE_CHECK=1` report instead of write. Same resource, three ways:

```yaml
# ansible: read, then conditionally write, with the state passed between tasks — 24 lines
- name: Read pool autoreplace settings
  ansible.builtin.command:
    argv: [zpool, get, -H, -o, value, autoreplace, "{{ item }}"]
  loop: "{{ zfs_maintenance_pools_autoreplace }}"
  register: zfs_maintenance_autoreplace_state
  changed_when: false
  failed_when: false
  check_mode: false

- name: Enable autoreplace so the hot spare can take over
  ansible.builtin.command:
    argv: [zpool, set, autoreplace=on, "{{ item.item }}"]
  loop: "{{ zfs_maintenance_autoreplace_state.results }}"
  when:
    - item.rc == 0
    - item.stdout | trim != "on"
  changed_when: true
```

```python
# pyinfra: a custom operation, the gate inside it — 8 lines plus a 12-line fact
@operation()
def zpool_property(pool: str, prop: str, value: str):
    current = host.get_fact(ZfsPoolProperty, pool=pool, prop=prop)
    if current != value:
        yield StringCommand("zpool", "set", QuoteString(f"{prop}={value}"), QuoteString(pool))
```

```bash
# mise: three lines at the call site, on top of a 15-line primitive
while read -r pool; do
  reconcile::zpool_property "$pool" autoreplace on
done < <(jq -r '.pools_autoreplace[]' "$RECONCILE_FACTS")
```

Handlers, likewise. Ansible needs a `notify`, a named handler in `handlers/main.yml`, and `meta: flush_handlers` where ordering matters; pyinfra needs a list comprehension and an `_if` callable; mise needs a call after each resource and one flush:

```bash
for event in $ZFS_ZED_EVENTS; do
  reconcile::template "$templates/zedlet-storage-alert.sh.j2" \
    "/etc/zfs/zed.d/${event}-storage-alert.sh" 0755 root root
  reconcile::notify_if_changed zfs-zed
done
reconcile::unit zfs-zed
reconcile::flush
```

Notifications collapse by name, so four changed zedlets restart zed once — the de-duplication pyinfra's `_if` gives up. `flush` is explicit, which turns Ansible's invisible end-of-play flush into something you can see.

Check mode produces real unified diffs, at half the cost of pyinfra's dry run:

```
$ ZFS_ZED_THROTTLE_SECONDS=1200 RECONCILE_CHECK=1 mise run //units/zfs-maintenance:zed
  would change: /etc/zfs/zed.d/statechange-storage-alert.sh (content)
    @@ -34,7 +34,7 @@
     now="$(date +%s)"
     if [[ -f "$stamp" ]]; then
       last="$(< "$stamp")"
    -  if (( now - last < 900 )); then
    +  if (( now - last < 1200 )); then
```

Change reporting is a shared ledger file plus a `depends_post` task, which is the one mise feature that fits reconciliation exactly: it runs after the parent *and its whole dependency subtree*, which is where a recap belongs.

```
UNIT                     ok  changed   failed
alerting                 11        0        0
base                      2        0        0
zfs-maintenance          28        1        0
TOTAL                    41        1        0

changed resources:
  [zfs-maintenance] unit smartmontools (enable+start)
```

The one residual change is the same one both other tools report: Debian's `smartmontools.service` carries `ConditionVirtualization=no` and can never be active in the rig. Known rig artifact, not a tool difference.

Drift on an API-backed resource works, and reports better than either alternative because the ledger carries the reason:

```
-- grace before: 900
  changed: check pod042-heartbeat (grace 900 -> 4321)
-- grace after: 4321
-- same command again: 0 changes
```

### What stays lost

**`sources`/`outputs` freshness is not merely unhelpful here, it is wrong.** It compares repository inputs against declared outputs and skips the task when the outputs are newer. Point `outputs` at a deployed file and hand-editing that file makes it *more* fresh, so the drift is preserved rather than corrected:

```
$ echo "corrupted by hand" > out.txt
$ mise run //units/zfs:b
[//units/zfs:b] sources up-to-date, skipping
$ cat out.txt
corrupted by hand
```

Any reconciliation built on `sources` would be a system that stops fixing things as soon as someone breaks them. The prototype uses it nowhere.

**`--dry-run` is a task-order printer.** It evaluates no state, so it cannot say what would change. Check mode has to be built, and because task `env` is not passed to `depends`, it cannot even travel through the dependency graph — `mise run plan` is a nested `RECONCILE_CHECK=1 mise run converge`.

**The graph runs in parallel and reconciliation does not.** The first converge of this prototype produced five failures: two `apt install` calls deadlocked on the dpkg lock, and three Healthchecks registrations raced each other through the mock's read-modify-write. Neither Ansible nor pyinfra can produce this class of bug. The fix is one line, `jobs = 1`, and the fact that it is one line is not the point — the default is wrong for this use and nothing warns you.

**A failed resource does not fail the run unless you make it.** A shell function returning non-zero leaves the script running and the task exiting 0, and mise calls that a success. `set -e` is not available, because every primitive returns non-zero for "this differs" as well as for "this broke". `reconcile::failed` therefore calls `exit 1`, which does abort the graph and does return rc=1. Nothing about the design pushes you toward that; the naive version silently succeeds.

**The recap disappears exactly when it matters.** `depends_post` runs the subtree when the parent started, and skips it when a regular dependency failed before the parent could start. So a unit failure aborts the run with no summary of what had already changed. Ansible always prints its PLAY RECAP.

**No `become`.** Every primitive carries its own `sudo`, and the change ledger has to be created with the invoking user as owner so a dozen unprivileged task processes can append to it.

**No tags, and unlike pyinfra, no rearrangement needed.** `mise run '//units/zfs-maintenance:*'` and `mise run '//...:converge'` cover most of what tags did, and the namespace is the tag. Cross-cutting selection (`-t apt` hitting six roles) still has no analog.

### Authoring cost, honestly

| | Ansible | pyinfra | mise |
|---|---|---|---|
| role/unit definitions | 468 lines YAML | 513 lines Python | 260 lines (unit configs + tasks) |
| reusable machinery you maintain | 0 | 184 lines (facts + operations) | 343 lines (runtime + check lib) |
| templates | 13 files | 13 files, 3 renamed | 13 files, renamed variables |
| retirement | 34 lines | not implemented | 29 lines |

Per reconciled resource, mise is the tersest of the three at the call site and the only one with a fixed cost you pay up front. 343 lines is roughly two days of careful work plus whatever the third host teaches you. Ansible's equivalent is maintained by Red Hat.

## 4. Declarative retirement

`.miseremove`, consumed by `//units/base:retire`, wired into the standard graph as a dependency of `//:converge`. Same manifest format as `.ansibleremove` — comments, blank lines, `~/`-relative, home-relative and absolute paths, the same four rejected forms (`/`, `.`, `~`, anything containing `..`).

```
### 1. check mode: reports, changes nothing
  would change: remove /usr/local/bin/retired-storage-probe
  would change: remove /home/thurston/.cache/retired-alerting-scratch
still present after check: yes
### 2. apply
  changed: remove /usr/local/bin/retired-storage-probe
  changed: remove /home/thurston/.cache/retired-alerting-scratch
### 3. second run
Finished in 23.1ms
```

The burden differs from Ansible's in two places, one better and one worse.

Better: Ansible's version is three tasks — a `set_fact` with a five-filter Jinja chain to read and strip the file, an `assert` loop to validate, and a `file: state=absent` loop — and the `assert` loop runs and reports on every path every run. The mise version reads the file with `while read`, validates in a `case`, and says nothing about paths that are already gone. 29 lines against 34, and the shell version is the one I would rather debug.

Worse: Ansible's runs on every host that includes the play, automatically, because `import_tasks` with `tags: [always]` cannot be skipped. mise's runs because `//:converge` lists it, and a partial run — `mise run //units/zfs-maintenance:scrub` — does not retire anything. There is no `always` tag. Whether that matters depends on how often partial runs happen; on this repo they happen constantly.

## 5. Equivalence

`rig/fingerprint.sh` records mode, owner and SHA-256 for 21 managed files, mode/owner for 4 directories, enabled/active for 6 units, 5 package states, both pools' `autoreplace`, and the mock's registered checks. Reset, Ansible converge, fingerprint; reset, pyinfra converge, fingerprint; reset, mise converge, fingerprint:

```
== fingerprint diff (ansible vs pyinfra)
IDENTICAL
== fingerprint diff (ansible vs mise)
IDENTICAL
```

Byte-identical on the first attempt, which surprised me — Jinja whitespace usually costs at least one round. minijinja with `--trim-blocks --py-compat` renders the role's templates unchanged apart from variable names, including `sanoid.conf`'s nested loops and the tab indentation.

Hammered on the mise-built state:

- heartbeat unit pings its check (`/start` + success, 2 pings)
- sanoid cut 9 snapshots on `black-box` and **0** on `ark`, per policy; `sanoid.service` ExecStart wrapped in `hc-run pod042-sanoid`, 2 pings
- `zfs-scrub-pool@black-box.service` ran a real scrub, `Result=success`, one `/start` and one success ping, `zpool status` reports the scrub
- `zpool offline -f` on a `black-box` leg reached the mock Hark in **1 second**: `pod042: ZFS vdev FAULTED in black-box`
- a second fault inside the throttle window stayed silent — 1 Hark event before, 1 after

Two rig artifacts, neither attributable to mise: a `zfs-zed` instance restarted repeatedly during the benchmark stopped processing events until restarted once more, and `hammer.sh`'s fixed 6-second wait in step 4 does not clear `/run/zed-storage-alert`, so a second run inside 15 minutes is throttled and reports no event. The deployed files are byte-identical to the Ansible ones; behaviour cannot differ.

## 6. Error legibility

Three failure modes, three different qualities.

**A template variable that does not exist.** `alerting_bin_dirr` in `zfs-scrub-pool@.service.j2`, the same break as the last two trials:

```
error: undefined value (in …/units/zfs-maintenance/../templates/zfs-scrub-pool@.service.j2:9)

------------------------- zfs-scrub-pool@.service.j2 --------------------------
   6 | Type=oneshot
   7 | LoadCredential=hark-webhook-url:{{ ENV.ALERTING_STATE_DIR }}/hark-webhook-url
   8 | LoadCredential=hc-ping:{{ ENV.ALERTING_STATE_DIR }}/checks/{{ ENV.RECONCILE_HOST }}-…
   9 > ExecStart={{ ENV.ALERTING_BIN_DIRR }}/hc-run {{ ENV.RECONCILE_HOST }}-zfs-scrub-%i …
     i              ^^^^^^^^^^^^^^^^^^^^^ undefined value
```

The best of the three by a distance: file, line, three lines of context, a caret under the name. Ansible names the template but not the position; pyinfra gives file and line but buries them under fifteen greenlet frames.

Then it prints "Referenced variables" — **the entire process environment**, every name and every value. In the rig that is a mock API key. On pod042 it would be the 1Password service account token and everything downstream of it. `HiddenValue` had a partial version of this problem in pyinfra; this is the complete version, and any adoption needs the renderer wrapped to suppress it.

**A variable mise itself cannot resolve**, in a unit's `mise.toml`:

```
[//units/zfs-maintenance:smartd] ERROR failed to parse template: '{{ env.ZFS_BIN_DIRR }}'
[//units/zfs-maintenance:smartd] ERROR error: Field `ZFS_BIN_DIRR` is not defined.
  Available fields: ALERTING_BIN_DIR, ALERTING_CHECK_LIB, ALERTING_HARK_WEBHOOK_URL, …
```

Names the field and lists what was available, which is genuinely useful, and names the task whose config was being rendered rather than the config file and line. Contrary to the docs' claim that a failed template "will log a warning and fall back to the raw content", this is a hard error — verified on both 2026.8.12 and 2026.8.14. On a workstation the "available fields" list is the whole environment again, roughly 130 names including every credential the shell carries. Names only, not values.

**A tool failure**, `sanoid` → `sanoid-typo`:

```
E: Unable to locate package sanoid-typo
  FAILED: apt install sanoid-typo
[//units/zfs-maintenance:sanoid] ERROR task failed
```

The tool's own message and the resource, no source location — the same shape as pyinfra's, less precise than Ansible's file-and-line.

## 7. Sharp edges

Five, all cheap once known.

- **A file task must be executable, and an unexecutable one is invisible.** No warning, no listing, no error — `mise tasks ls` simply does not mention it. Two tasks in this prototype were missing for one debugging round.
- **`jobs = 1` or nothing.** Covered above; it is the first line to write.
- **`ceiling_paths` is needed for any monorepo root inside another mise project**, and `{{ config_root }}` excludes the config itself, so the value is `{{ config_root | dirname }}`.
- **`--py-compat` for `.items()`.** minijinja is not Jinja2; the role's `dict.items()` loops need the compatibility flag, and `--trim-blocks` is needed because Ansible sets it and minijinja does not.
- **`ubi:` is deprecated** in favour of `github:` for GitHub-release backends, removal scheduled for 2027.1.0. The prototype pins `github:mitsuhiko/minijinja`.

The template engine being a pinned tool is the one place where "the config manager is just the tool manager" pays a real dividend: `[tools]` guarantees every host renders with byte-identical minijinja 2.24.0, which is a stronger reproducibility claim than either Ansible or pyinfra makes about its Jinja.

## Rig disposition

The Lima VM `pod042test` and Homebrew's `lima` were **removed** after the trial, along with the local minijinja install used for the config-semantics experiments. `../prototypes/pyinfra/rig/prep.sh` rebuilds the VM in about two minutes and is unchanged; `../prototypes/mise/rig/bench.sh` is new and measures all three tools in one pass, so every number above is reproducible from a bare host.

No real Hark, Healthchecks or B2 endpoint was contacted; the mock served both APIs, and no 1Password credential was needed.
