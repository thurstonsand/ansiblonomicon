# mise reproduction of the alerting + zfs_maintenance segment

Ticket 20's prototype. It reproduces `ansible/roles/alerting` and `ansible/roles/zfs_maintenance` as wired into `ansible/playbooks/pod042.yml`, using mise alone as the driver, and converges pod042 to a byte-identical result. Findings live in `../../research/mise-trial.md`.

Nothing outside this directory depends on it, and `.miserc.toml` stops config discovery here so the repo's own root `mise.toml` does not layer over it.

## Layout

```
mise.toml                          # monorepo root: host facts, entrypoints  (playbooks/pod042.yml)
.miserc.toml                       # ceiling_paths, so this really is the root
.miseremove                        # retired paths                            (.ansibleremove)
host/pod042.json                   # structured host facts                    (group_vars/pod042.yml)
lib/reconcile.sh                   # the reconciliation runtime mise lacks
lib/report.sh                      # PLAY RECAP
units/base/
  mise.toml
  mise-tasks/retire                #                                          (tasks/remove_retired_paths.yml)
units/alerting/
  mise.toml                        # unit defaults                            (roles/alerting/defaults/main.yml)
  interface.env                    # the exported contract                    (roles/zfs_maintenance/meta/main.yml)
  lib/check.sh                     # reusable check registration              (roles/alerting/tasks/check.yml)
  mise-tasks/{scripts,heartbeat}   #                                          (roles/alerting/tasks/main.yml)
  templates/*.j2
units/zfs-maintenance/
  mise.toml                        # unit defaults + the contract import
  defaults.json                    # unit defaults that are not scalars
  mise-tasks/{sanoid,scrub,smartd,zed}
  templates/*.j2
rig/{mise.sh,bench.sh}             # the wrapper and the three-way benchmark
```

Tasks are namespaced by their directory: `//units/alerting:heartbeat`, `//units/zfs-maintenance:scrub`. `mise tasks deps` draws the graph.

## Running it

```sh
mise run converge                     # reconcile everything
mise run plan                         # check mode: report drift, change nothing
mise run //units/zfs-maintenance:scrub  # one part
mise run --dry-run converge           # print the task order; evaluates nothing
mise tasks deps                       # the dependency graph
```

The three alerting endpoints come from the process environment. In the rig `rig/mise.sh` points them at the mock on 127.0.0.1:8099.

## Rebuilding the rig

The rig is the pyinfra prototype's: `../pyinfra/rig/prep.sh` builds the Lima VM, `reset.sh` returns it to a pre-converge state, `fingerprint.sh` records the 21-file managed surface, `hammer.sh` exercises it.

```sh
brew install lima
limactl start --name=pod042test --tty=false ../pyinfra/rig/pod042test.yaml
cp ../pyinfra/rig/mockapi.py /tmp/rig/ && (cd ../pyinfra/rig && ./prep.sh)
limactl shell pod042test sudo -u thurston -i bash rig/bench.sh   # all three tools, same minute
limactl delete -f pod042test && brew uninstall lima
```

`rig/bench.sh` needs the pyinfra prototype's `converge.sh`/`converge-tags.sh` in `/home/thurston` and `reset.sh`/`fingerprint.sh` in `/usr/local/sbin`.

## Deviations from the Ansible original

- Templates take `{{ ENV.ALERTING_STATE_DIR }}` where the role takes `{{ alerting_state_dir }}`, and the per-pool timers take `pool`/`calendar` rather than `item.pool`/`item.calendar`. Rendered output is identical.
- Rendering is minijinja-cli, pinned in `[tools]`, run with `--strict --trim-blocks --py-compat`. `--py-compat` is what makes `.items()` work; `--trim-blocks` matches Ansible's Jinja default.
- The smartd unit is enabled under its canonical name `smartmontools.service`, for the same reason the pyinfra prototype does it.
- `jobs = 1`. mise runs the dependency graph in parallel; convergence is serial work.
