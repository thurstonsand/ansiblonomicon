# pyinfra trial: the alerting + zfs_maintenance segment, both ways

Ticket 19. Prototype: `../prototypes/pyinfra/`. Rig: Lima, arm64 Debian 13, real ZFS, file-backed `ark`/`black-box`, mock Healthchecks/Hark on 127.0.0.1:8099 — the workstream-E gauntlet rig, rebuilt from `rig/prep.sh` in about two minutes.

## Verdict

pyinfra converges this segment to a **byte-identical** result in **3.6x less wall clock on a cold host and 13x less on a converged one**, and its dry run is 11x faster than `--check --diff` while showing the same file diffs plus a column Ansible has no equivalent for. The loop is not incrementally better; it is a different loop. Eleven seconds of no-op is a thing you avoid running, 0.9 seconds is a thing you run after every edit.

The abstraction story is weaker than the speed story but not weak. `@deploy` with `data_defaults` is a genuine role analog — parameterized, composable, with the same defaults-then-host-data precedence. What it does not have is tags. Partial runs become one entrypoint file per part, which is fine for five parts and an open question for the thirty-role laptop playbook.

The cost is concentrated in one place: **the module ecosystem is smaller, and this repo leans on the parts of Ansible's that pyinfra lacks.** `osx_defaults`, `mas`, and the `community.docker` network/compose surface either don't exist or exist in reduced form. Every one is writable as a custom operation, and this trial writes two to prove the shape, but that is work Ansible has already done.

One finding is independent of the decision: **the Ansible `alerting` role silently under-reports check changes.** Verified below. It should be fixed either way.

## 1. The loop, measured

Same VM, same minute, each tool starting from an identical reset state (`rig/reset.sh`: packages purged, files removed, mock registry wiped). Ansible scoped with `--tags alerting,sanoid,scrub,smartd,zed`; pyinfra running `deploy.py`. Both target localhost, so neither pays SSH.

| | Ansible 12 | pyinfra 3.10 | ratio |
|---|---|---|---|
| full converge from bare host | 18.9 s | 5.3 s | 3.6x |
| no-op re-run | 11.5 s | 0.87 s | 13x |
| dry run with diffs | 9.8 s | 0.87 s | 11x |
| partial run (scrub only) | 3.9 s | 0.36 s | 11x |
| units of work | 60 tasks, 31 changed | 41 ops, 39 changed | — |

The gap is not the work; it is the overhead. Ansible re-forks a Python interpreter per task and re-gathers facts per play; pyinfra runs the deploy in one local process and batches its fact reads. The 11.5 s no-op is what a `--tags` cycle costs today on a machine that has nothing to do.

### Dry-run fidelity

Both show real file diffs. Change the zed throttle from 900 to 1200 and each prints a unified diff of all four zedlets before touching anything:

```
# ansible --check --diff
--- before: /etc/zfs/zed.d/statechange-storage-alert.sh
+++ after: /home/thurston/.ansible/tmp/.../zedlet-storage-alert.sh.j2
@@ -34,7 +34,7 @@
-  if (( now - last < 900 )); then
+  if (( now - last < 1200 )); then

# pyinfra --dry --diff
[@local] Will modify /etc/zfs/zed.d/statechange-storage-alert.sh
  @@ -35,5 +35,5 @@
  -   if (( now - last < 900 )); then
  +   if (( now - last < 1200 )); then
```

They diverge on what they claim about systemd. Ansible reports `RUNNING HANDLER [Restart zed] changed`, stating flatly that the handler will fire. pyinfra prints a two-column table and puts the restart in the second column:

```
Operation                                                          Change       Conditional Change
Install the statechange zedlet                                     1 (@local)   -
Restart zed                                                        -            1 (@local)
```

"Conditional Change" means: this operation is gated on `_if`, and the gate is evaluated at execute time. That is more honest than Ansible's claim and, in a plan you are reading to decide whether to apply, more useful — it distinguishes "this will happen" from "this will happen if the thing above it does."

Both share the same structural limit: an operation whose input does not exist yet cannot be diffed. Neither tool can show you the content of a file that a not-yet-run package install would create.

### Error legibility

An undefined template variable, `alerting_bin_dirr`, introduced into `zfs-scrub-pool@.service.j2`:

```
# ansible
[ERROR]: Task failed: 'alerting_bin_dirr' is undefined
Origin: .../roles/zfs_maintenance/tasks/scrub.yml:23:3
23 - name: Install the scrub service template unit
     ^ column 3
<<< caused by >>>
'alerting_bin_dirr' is undefined
Origin: .../templates/zfs-scrub-pool@.service.j2

# pyinfra
pyinfra.api.exceptions.OperationError: Error in template:
  .../templates/zfs-scrub-pool@.service.j2 (L9): 'alerting_bin_dirr' is undefined
...
ExecStart={{ alerting_bin_dirr }}/hc-run {{ hostname }}-zfs-scrub-%i -- ...
...
```

pyinfra gives the line number and the offending line; Ansible names the template but not where in it, and instead names the task that called it. Ansible 12's error format is better than its reputation. The catch is that pyinfra buries its message under a fifteen-frame traceback that ends in `src/gevent/greenlet.py line 912` — the message is good, the framing is noise.

A task-level failure (`sanoid` → `sanoid-typo`) inverts the result:

```
# ansible
[ERROR]: Task failed: Module failed: No package matching 'sanoid-typo' is available
Origin: .../roles/zfs_maintenance/tasks/sanoid.yml:2:3

# pyinfra
--> Starting operation: Configure sanoid snapshots | Install sanoid
    [@local] E: Unable to locate package sanoid-typo
    [@local] Error: executed 0 commands
```

pyinfra shows the tool's own output and the operation's label, but no source location. Ansible points at the file and line. Neither is confusing; Ansible is more precise about *where*, pyinfra more direct about *what*.

The nicest failure in the trial is pyinfra's `DeployError` — the `assert` analog guarding the alerting credentials — because it is a plain Python exception raised in deploy code:

```
--> pyinfra error in .../bunker/alerting.py line 64: alerting_hark_webhook_url and
    alerting_healthchecks_api_key must be resolved before configuring alerting.
    Run `uv run poe init-secrets`.
```

File, line, message, no traceback, nothing about greenlets.

## 2. Idempotency

Both tools reach steady state and both report exactly **one** residual change, and it is the same one: `Enable smartd`. Debian's `smartmontools.service` carries `ConditionVirtualization=no`, so it can never be active in the rig, and both tools dutifully try to start it every run. Known rig artifact from the original gauntlet, not a tool difference.

Functional equivalence is not an argument, it is a diff. `rig/fingerprint.sh` records mode, owner, and SHA-256 for 21 managed files, the mode/owner of 4 directories, enabled/active state for 6 units, 5 package states, both pools' `autoreplace`, and the mock's registered checks. Ansible converges, fingerprint taken; reset; pyinfra converges, fingerprint taken:

```
== fingerprint diff (ansible vs pyinfra)
IDENTICAL
```

Every script, unit, drop-in and credential file is byte-for-byte the same, including the four zedlets and the `0600 root:root` ping-URL files. Behavior, hammered on the pyinfra-built state:

- heartbeat unit pings its check (`/start` + success, 2 pings)
- sanoid cut 9 snapshots on `black-box` and **0** on `ark`, per policy
- `sanoid.service` ExecStart is wrapped in `hc-run pod042-sanoid`
- `zfs-scrub-pool@black-box.service` ran a real scrub, result `success`, one `/start` ping and one success ping
- `zpool offline -f` on a `black-box` leg reached the mock Hark inside 6 seconds: `pod042: ZFS vdev FAULTED in black-box`

### Ops that resist idempotency, and the pattern that fixes them

pyinfra ships operations that are honestly labeled non-idempotent: `systemd.daemon_reload` is declared `@operation(is_idempotent=False)`, and `docker.compose`'s docstring says outright that it always shells out. Anything you write with `server.shell` is in the same category.

The pattern is to gate the shell on a fact so the operation yields no commands when converged. `zpool set autoreplace=on` is the segment's example, and the pyinfra version is shorter than the Ansible one because the gate lives in the operation rather than in two tasks:

```yaml
# ansible: read, then conditionally write, with the state passed between tasks
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
# pyinfra: one custom operation, the gate inside it
@operation()
def zpool_property(pool: str, prop: str, value: str):
    current = host.get_fact(ZfsPoolProperty, pool=pool, prop=prop)
    if current != value:
        yield StringCommand(
            "zpool", "set", QuoteString(f"{prop}={value}"), QuoteString(pool)
        )
```

`changed_when: false` / `check_mode: false` / `failed_when: false` — the three annotations Ansible needs to stop a read from lying about itself — have no counterpart because a fact is not a task.

## 3. Abstraction: is there a role?

Yes, with one hole.

**The role analog is `@deploy(name, data_defaults=...)`.** It is a Python function whose body calls operations; the decorator merges its defaults into the host's data at the bottom of the precedence chain (`override → host → group → all → deploy defaults`, `api/host.py`), applies its global arguments to every operation inside, and prefixes nested deploy names for output. `Configure ZFS maintenance | Configure pool scrubs | Install the scrub timer for ark` is what a three-deep composition prints, which beats reading Ansible's flat task names and inferring the role from the prefix.

**Composition is a function call**, so `zfs_maintenance()` calling `sanoid()`, `scrub()`, `smartd()`, `zed()` is exactly what it looks like. No `include_role`, no `apply:` block, no tags to thread through the include.

**The `meta/main.yml` dependency becomes a dict merge.** `zfs_maintenance` needs alerting's `alerting_bin_dir` and `alerting_state_dir` in scope even on a run that never configures alerting itself. In Ansible that is a declared role dependency whose side effect is bringing defaults into scope. In pyinfra:

```python
DEFAULTS = {
    **alerting.DEFAULTS,
    "zfs_maintenance_bin_dir": "/usr/local/bin",
    ...
}
```

Blunter, more explicit, and it makes the dependency's actual nature visible: it was never about ordering, only about defaults. `parts/scrub.py` runs standalone with correct paths and no alerting operations, which is the property the Ansible dependency exists to provide.

**Handlers become `_if` on a normal operation.** The trap the docs warn about is real: deploy code runs in a *prepare* pass before anything is executed, so `if op.changed:` in the deploy body reads pre-deploy state and is wrong. The correct form defers the check to execute time:

```yaml
# ansible: notify a named handler, then force it to run before the next task needs it
- name: Install the storage-alert zedlets
  ansible.builtin.template: {...}
  loop: "{{ zfs_maintenance_zed_events }}"
  notify: Restart zed
```

```python
# pyinfra: the operation is ordinary, the condition is a callable evaluated at execute time
zedlets = [files.template(...) for event in host.data.zfs_maintenance_zed_events]

systemd.service(
    name="Restart zed",
    service="zfs-zed",
    restarted=True,
    _if=lambda: any(zedlet.did_change() for zedlet in zedlets),
)
```

This is better than handlers in two ways and worse in one. Better: the restart appears in the operation order where you wrote it, so `meta: flush_handlers` — which this segment needs three times — has no analog and no need for one. Better: `_if` takes any callable, so "restart if any of these four changed" is `any(...)`, where Ansible's notify has no OR beyond notifying the same handler from each task. Worse: handlers de-duplicate. Notify the same handler from six tasks and it runs once; write six `_if` restarts and you get six restarts unless you collect the conditions yourself.

**Tags have no analog.** There is no tag selector in the CLI (`src/pyinfra_cli/cli.py` offers `--limit` and `--exclude`, both host selectors) and no mention of tags anywhere in the docs. Partial runs are expressed by choosing which deploy files to run:

```sh
uv run poe pod042 -t scrub                       # ansible
uv run pyinfra inventory.py parts/scrub.py       # pyinfra
```

For five parts, five three-line files under `parts/` is arguably clearer than tag lists that must be kept in sync across `include_role` and `apply:` blocks. For a playbook with thirty roles and cross-cutting tags (`-t apt` hitting tasks in six places), the entrypoint-file model would need thought. That is the one place where the Ansible model has a capability with no replacement, only a rearrangement.

**Custom fact and custom operation.** Healthchecks registration is the right stress test: an idempotent, API-backed resource with no on-disk representation. The fact reads the Management API's list endpoint:

```python
class HealthchecksChecks(FactBase):
    default = dict

    def requires_command(self, api_url: str, api_key: str) -> str:
        return "curl"

    def command(self, api_url: str, api_key: str) -> str:
        return f"curl -fsS --max-time 10 -H 'X-Api-Key: {api_key}' '{api_url}'"

    def process(self, output) -> dict[str, dict]:
        payload = json.loads("\n".join(output) or "{}")
        return {c["slug"]: c for c in payload.get("checks", []) if c.get("slug")}
```

and the operation diffs desired against actual, emitting a POST only when the check is missing or a field drifted, and rewriting the credential file only when its contents disagree with the known ping URL. Sixty lines for both, including the docstrings.

### The bug this turned up

Ansible's `alerting/tasks/check.yml` POSTs on every run and keys changed-state off `status == 201`. The Healthchecks docs are explicit that a `unique` POST matching an existing check **updates it** and returns 200. So editing a check's schedule or grace in `defaults/main.yml` applies the change and reports `ok`. Demonstrated in the rig:

```
--- ansible, -e alerting_heartbeat_grace=4321
PLAY RECAP: ok=18  changed=0
mock state after: "grace": 4321        # changed, reported as unchanged
```

The fact-gated pyinfra operation gets this right, because it compares before it writes:

```
grace before: 900
--- apply with grace=4321
Register Healthchecks check pod042-heartbeat   1 host   1 success
grace after: 4321
--- same command again
Register Healthchecks check pod042-heartbeat   1 host   -         1 no change
```

Detected, applied once, silent thereafter. The Ansible role can be fixed the same way — a `uri` GET before the POST — and should be, regardless of what happens to this trial.

### Sharp edges found by building it

Four, all cheap once known, all discovered the hard way:

- **`name` is reserved** for operations *and* for `@deploy` functions — it is the global argument that labels them. A check's own name has to travel as `check=`.
- **`requires_command()` receives the fact's arguments**, so its signature must mirror `command()`'s or you get a `TypeError` from inside pyinfra's fact machinery.
- **Jinja defaults differ.** Ansible sets `trim_blocks`; pyinfra does not. `sanoid.conf.j2` needs `jinja_env_kwargs={"trim_blocks": True}` to render identically. pyinfra uses `StrictUndefined`, which is the better default and the reason the undefined-variable failure above is a hard error.
- **`systemctl enable smartd` fails on Debian** — it is an `Alias=` of `smartmontools.service`, and systemd refuses to operate on a linked unit. Ansible's `systemd_service` module resolves the alias; pyinfra passes the name to systemctl unchanged. The prototype uses the canonical name.

The `no_log` analog is `HiddenValue`, and it is partial. Operation commands mask correctly:

```
sh -c 'umask 077; curl -fsS --max-time 10 -X POST -H '"'"'*MASKED*'"'"' ...
```

Fact commands do not — they are plain strings, and at `-vv` the API key appears in both the fact command and pyinfra's fact-argument logging (8 occurrences in a full verbose run). Anything secret that a fact needs is visible at high verbosity.

## 4. Migration cost, by surface

Line count is not the story and does not favor either tool: 443 lines of role YAML against 420 lines of deploy Python, plus 166 lines of custom fact and operation that replace `uri` + `set_fact` + `copy`.

**Ports directly.** `files.template`, `files.directory`, `files.link`, `apt.packages`, `systemd.service`, `server.user`, `server.shell`, `git.repo` — everything the storage and base-system roles use. `sshd`, `samba`, `restic_backup`, `op_service_account`, `host_network` are all templates plus units plus packages, which is the segment proven here. `files.sync` and `files.rsync` exist, which is what `docker_stack` uses to place stack trees.

**Ports with effort.** `docker_stack` is the biggest single item: `docker.compose` exists but is explicitly non-idempotent (always shells out to compose, relying on compose to skip unchanged services), and the role's change detection — the `_docker_stack_changed` fact that drives Ghost's restart — would have to be rebuilt on top of the file operations' `did_change()`. That is arguably cleaner than what the role does today. `community.docker.docker_network` with macvlan `driver_options` and `ipam_config` has a thinner analog in `docker.network`; the four macvlan networks want checking against it. The 1Password `lookup('env')` pattern is the easiest of the lot: deploy code is Python running locally, so it is `os.environ` (`group_data/pod042.py` in the prototype), and the `.env` from `poe init-secrets` works unchanged.

**No equivalent.** `osx_defaults` and `mas` do not exist — pyinfra has `brew.packages`, `brew.casks`, `brew.tap`, and `launchd` facts and operations, but nothing for macOS preference domains or the App Store. `macos_defaults` is roughly 30 domains of `osx_defaults` calls, and porting it means writing the operation and the fact that reads `defaults read` back, per type. The `chezmoi` role is `server.shell` either way, so it is not a loss. There is no `ansible-lint` counterpart, though `basedpyright` over deploy code is a strictly better check than linting YAML, and pyinfra ships type annotations and runtime `typeguard` checking of operation arguments.

The honest summary of cost: the storage/service half of this repo ports mechanically, the macOS half needs new operations written, and `docker_stack` needs a design pass. Four hosts, roughly thirty roles.

## Rig disposition

The Lima VM `pod042test` and Homebrew's `lima` were **removed** after the trial. Nothing in the VM was worth keeping: `rig/prep.sh` rebuilds it from scratch in about two minutes now that Debian 13 ships a prebuilt ZFS module (the original gauntlet's DKMS build and kernel-flavour dance are no longer needed), and every measurement in this document comes from `rig/bench.sh`, `rig/fingerprint.sh` and `rig/hammer.sh`, which are all committed with the prototype.

No real Hark, Healthchecks or B2 endpoint was contacted; the mock served both APIs, and no 1Password credential was needed.
