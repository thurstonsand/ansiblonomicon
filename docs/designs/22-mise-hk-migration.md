# mise + hk migration

## Status

Accepted, implemented

## Decision Summary

Replace direnv, poethepoet, and pre-commit with mise and hk, matching the model already used in `wt` and `ghosttykit`. This cuts the per-shell repo tax from ~150 ms to ~60 ms and the common commit from 12.9 s to roughly 2 s, and it regroups a 38-task poe surface that had accumulated three different naming conventions. The tradeoff accepted deliberately: commit-time linting becomes scoped to staged files, and with no CI, this repo gives up automatic whole-tree verification entirely.

## Problem Statement / Background

Three separate tools currently sit between a fresh terminal and useful work here, and each is slower than it looks.

**Shell entry.** direnv has no on-disk cache, so every new terminal re-executes `.envrc` in a freshly forked Homebrew bash. Measured in a directory with identical contents and the same 85-variable `.env`:

| configuration | shell startup | over baseline |
| --- | --- | --- |
| neither tool | 135 ms | — |
| mise: env, tools, gated bootstrap hook | 195 ms | +60 ms |
| direnv: env only, no `uv sync` | 225 ms | +90 ms |
| direnv: this repo's actual `.envrc` | ~285 ms | ~+150 ms |

direnv loses on the stripped-down configuration that does no work at all, because forking bash costs more than reading TOML. Inside `.envrc`, the work splits as `uv sync --dev` 40 ms, two `hostname -s` subshells 16 ms, `git config --local` 8 ms, and stat guards 3 ms. Only the first is avoidable, and mise's `sources`/`outputs` task caching avoids it for free.

**The commit hook.** This is where the real time goes, and it was not what prompted the investigation. `pre-commit run --all-files` takes 12.9 s, essentially all of it `ansible-lint` over 115 files with `pass_filenames: false`. Its hook is `types: [yaml]`, and this is an Ansible repo, so most commits pay it. For scale, the direnv problem is 0.09 s.

**The full graph.** `uv run poe lint` is 27.3 s: ansible-lint, ruff, basedpyright, stylua, two `wrangler deploy --dry-run` calls, three TypeScript lint scripts, and `go test` in two subprojects.

Underneath the timings is a coherence problem. `wt` and `ghosttykit` both run mise for tools, env, and tasks, with a small `hk.pkl` for the commit hook. This repo runs direnv for env, poe for tasks, Homebrew for tools, and pre-commit for hooks, so moving between repos means switching muscle memory. The poe surface has drifted too: host names used as verbs (`poe truenas`), unguessable abbreviations (`cz-re-add`, `tfa`), and a `lint:*` namespace mixing languages, components, and deploy targets on the same axis.

One scenario motivates the scoping design specifically. Today, staging a role task that references a module which does not exist gets caught, because the whole-tree lint runs a syntax check across every playbook and role. Under a naive `ansible-lint {{files}}` hook it would not be, because ansible-lint only syntax-checks lintables of kind playbook, role, or pattern, and a bare task file is kind `tasks`. That regression is the thing this design has to avoid while still getting the speed.

## Goals

- A new terminal in this repo costs roughly what a new terminal anywhere else costs.
- A commit that touches one role is verified in about two seconds, without losing syntax-check coverage.
- One tool provides the toolchain, the environment, and the task runner, as in the sibling repos.
- The task surface is discoverable by tab completion rather than by memory.
- A command that rewrites files never wears a name that reads as read-only.

## Non-Goals

- Continuous integration. Considered twice and declined; see Alternatives.
- Committing a `mise.lock`. The work laptop deliberately runs older versions and that flexibility is wanted.
- Changing what any linter actually checks. This migration moves and scopes existing checks; it does not add or remove rules.
- Replacing Homebrew as the source of host tools.

## Exposed Shape

### Task surface

Canonical names carry a namespace; aliases restore terseness. `mise run` is optional, so `mise truenas -t chezmoi` is the everyday form, six characters shorter than today's `uv run poe truenas -t chezmoi`. `mise tasks` lists canonical names only, so discovery stays clean. It also lists the root hierarchy only — the two Go config roots need `mise tasks --all`.

```
RECONCILE                                    alias
  reconcile                 this machine, by hostname
  reconcile:laptop          poe laptop       laptop
  reconcile:truenas         poe truenas      truenas
  reconcile:udmp            poe udmp         udmp
  reconcile:pod042          poe pod042       pod042
  reconcile:tags <pb>       poe list-tags

EDGE — Cloudflare, grouped by resource rather than by tool
  edge:init                 poe tfi
  edge:plan                 poe tfp
  edge:apply                poe tfa
  edge:deploy               poe wrangler
  edge:deploy:aig           poe wrangler:aig
  edge:deploy:hooks         poe wrangler:hooks
  edge:deploy:tesla         poe pages-deploy

CHECKS — component first, verb second
  check                     every non-mutating task
  fix                       every mutating task
  ansible:lint              poe lint:ansible
  python:lint               poe lint:ruff          (check only)
  python:lint:fix                                  (--fix --unsafe-fixes)
  python:fmt                poe lint:format        (now mutating)
  python:fmt:check
  python:typecheck          poe lint:types
  nvim:fmt                  poe lint:nvim          (now mutating)
  nvim:fmt:check
  workers:typecheck         poe lint:workers
  pi:check                  poe lint:pi
  amp:check                 poe lint:amp
  session-recovery:check    poe lint:session-recovery
  //ansible/roles/shp/files/shp:check          poe lint:shp
  //ansible/roles/sessions/files/sessions:check  poe lint:sessions

UPKEEP
  secrets:init              poe init-secrets
  deps:update               poe update-deps
  deps:update:uv            poe update-deps:uv
  deps:update:ts            poe update-deps:ts
  pull                      poe pull
  chezmoi:diff              poe cz-diff
  chezmoi:re-add            poe cz-re-add

DELETED — aliases for commands already on PATH
  poe cz-status  ->  chezmoi status
  poe cz-managed ->  chezmoi managed
  poe cz-edit    ->  chezmoi edit
```

`poe openclaw` has no successor. OpenClaw is sunset, the host is not running, and porting a reconcile task for a machine that will never be reconciled again would be carrying it forward for no reason. Its remaining footprint is 65 files, a role, a playbook, inventory, chezmoi templates, and three terraform files, which is a removal of its own and not this migration's business.

Reconcile tasks keep their flags exactly: `-c/--check` and `-t/--tags`, expressed as mise usage specs. Verified that usage flags resolve through an alias.

### Environment contract

mise owns the Python interpreter; uv owns Python packages. The seam between them is a single variable that fails loudly.

```toml
[tools]
python = "3.14"

[env]
_.python.venv = { path = ".venv", create = true }
UV_PYTHON = "..."            # mise's interpreter, explicitly
_.file = ".env"              # secrets, generated by secrets:init
ANSIBLE_CONFIG = "{{config_root}}/ansible/ansible.cfg"
SUDO_ASKPASS = "{{config_root}}/ansible/sudo-askpass.sh"

[hooks]
enter = "mise run --quiet bootstrap"
```

`UV_PYTHON_PREFERENCE=only-managed` is deleted. Under mise it means "prefer uv's Python over mise's", the opposite of its documented intent.

### hk boundary

hk steps invoke binaries on mise's PATH directly. They do not dispatch to mise tasks, which is where this design diverges from both sibling repos and is the subject of Design Decision 5. Each step declares `glob`, a non-mutating `check`, and where applicable a `fix` plus `stage`.

| step | glob | commit-time cost |
| --- | --- | --- |
| ansible | `ansible/**/*.{yml,yaml}` | ~1.4 s per role |
| ruff-check | `**/*.py` | 0.05 s |
| ruff-format | `**/*.py` | fast |
| stylua | `**/*.lua` | fast |
| basedpyright | none, project-wide | 1.1 s |
| pi / amp / session-recovery | their subtrees | only when touched |
| go | the two subprojects | ~0.5 s each |

The two `wrangler deploy --dry-run` calls are excluded: they need the network, and a hook that fails because Cloudflare is having a bad afternoon is a hook that gets disabled.

The pre-commit hook stashes, overriding hk's default of `none`. hk offers `git` and `patch-file`; the choice between them turns on which leaves the working tree recoverable when a hook is interrupted, and belongs to whoever implements it. This matters more here than in most repos. Staged and unstaged are load-bearing in this workflow — unstaged means not yet reviewed — and several steps carry `fix` plus `stage`. Without stashing, `ruff format` would rewrite a file containing unreviewed unstaged edits and then stage the whole thing, quietly folding unreviewed work into the commit. Stashing costs a little time per commit and buys the guarantee that the hook only ever sees, and only ever stages, what is actually being committed.

`go test` runs at commit time even though pre-commit never ran it. It is glob'd to the Go subtrees, so it fires only when Go changes, and it is near-free warm. `just check` ran it, and dropping it during a migration whose whole point is a faster hook would be taking the win in the wrong currency.

### New component: staged-path normalizer

`scripts/ansible-lint-staged.sh` takes the paths hk passes, collapses anything under `roles/<name>/` to `roles/<name>`, dedupes, and passes playbooks and other YAML through unchanged. It owns exactly that transformation; hk owns file selection, ansible-lint owns the verdict.

```txt
git staged paths
  -> hk glob filter (ansible/**/*.yml)
  -> {{files}}
  -> normalizer: roles/foo/tasks/main.yml -> roles/foo
                 roles/foo/meta/main.yml  -> roles/foo
                 playbooks/truenas.yml    -> unchanged
                 group_vars/all.yml       -> unchanged
  -> dedupe
  -> ansible-lint --offline <paths>
```

## Call Stacks and Data Flow

Shell entry:

```diff
 new terminal in repo
-  direnv precmd hook
-    fork /opt/homebrew/opt/bash/bin/bash
-    source .envrc
-      uv sync --dev                        (40 ms, unconditional)
-      hostname -s  x2                      (16 ms)
-      git config --local core.hooksPath    (8 ms, writes .git/config)
-      stat guards for pre-commit, npm deps
-      dotenv .env
-    export diff back to zsh
+  mise hook-env
+    read mise.toml, resolve tools and env
+    _.file .env
+    hooks.enter -> mise run bootstrap
+      sources/outputs cache hit -> no-op
```

Commit:

```diff
 git commit
-  pre-commit
-    uv-lock
-    ansible-lint, whole tree, pass_filenames: false     13.5 s
-    ruff format / ruff check --fix, on staged py
-    basedpyright, project-wide
+  hk (installed via `hk install --mise`, entered through `mise x`)
+    steps run in parallel, each filtered by glob
+      ansible   -> scripts/ansible-lint-staged.sh -> ansible-lint --offline
+      ruff      -> check, then fix + stage on failure
+      stylua, pi, amp, session-recovery, go — only if their globs match
+      basedpyright — no glob, always
```

The `uv-lock` pre-commit hook has no hk equivalent and is dropped; `deps:update:uv` owns lockfile refresh.

`hk install --mise` registers `hook.hk-pre-commit.command` in `.git/config` rather than writing a shim into `.git/hooks`, using the config-based hooks Git 2.54 introduced. That kills the `core.hooksPath` pin outright, along with the unset-install-restore dance `.envrc` performed around it, since a config hook cannot be shadowed by a global hooksPath and the pin defended against nothing else.

The reach was the only argument against. `hook.<name>.command` needs Git 2.54 and Debian 13 ships 2.47.3 from apt, which would have meant pod042 committing with no hook and no message saying so. That is settled by keeping Debian's git current rather than by carrying `--legacy` everywhere else. `bootstrap:git` verifies nothing about the version, but `scripts/verify-migration.sh` asserts `git --version >= 2.54`, so a host that cannot honour the hook fails an explicit check instead of committing in silence.

## Design Decisions

### 1. mise owns the Python interpreter, uv owns the packages

The seam had to land somewhere, and the evidence decided it. Running `uv sync` under a mise-provided Python, varying only the preference variable:

| `UV_PYTHON_PREFERENCE` | interpreter the venv ends up on |
| --- | --- |
| unset | mise's |
| `only-system` | mise's |
| `only-managed` (today's) | **uv's own download** |
| `UV_PYTHON` pinned | mise's |

The third row is the one that mattered. mise creates `.venv` on its interpreter, announces it, and `uv sync` then silently rebuilds the venv on a Python it downloaded itself. The variable exists to keep the venv off Homebrew's Python, because a `brew upgrade` relinks the interpreter and breaks ansible-core's module loader mid-run. mise owning the interpreter achieves that goal directly, which leaves the variable doing nothing but introducing a second authority.

`UV_PYTHON` is pinned rather than using `only-system`, because `only-system` degrades to Homebrew's Python if mise's is ever missing, which is the original failure. A pinned path errors instead: `error: No interpreter found at path ...`. Given the failure mode is a reconcile dying partway through on a machine nobody is watching, loud beats convenient.

Consequence for future work: `python = "3.14"` in `mise.toml` and `requires-python = ">=3.14"` in `pyproject.toml` can drift, and nothing enforces agreement.

### 2. Dev tools in mise.toml, host tools in the Brewfile

This repo writes the Brewfile that provisions its own machines, so the split needed a principle. A **dev tool** is needed to work on this repo and belongs in `mise.toml`. A **host tool** is something reconciliation installs for its own sake and belongs in the Brewfile, even when development also happens to need it.

So `go`, `golangci-lint`, `node`, `stylua`, `opentofu`, and `hk` move to `mise.toml`; `mise`, `uv`, `chezmoi`, and `wrangler` stay in the Brewfile. Pinning everything in mise was rejected because `scripts/bootstrap.sh` installs Homebrew before anything else exists, and pod042 reconciles itself from this repo's venv.

`just` leaves the dev-tool list entirely, since the two justfiles become mise configs under Decision 3.

`go` is the exception, and implementation is what surfaced it. The `shp` and `sessions` roles run `go build` and `go get` through Ansible during reconcile, which sources no shell profile and sits inside no mise context. That makes go something reconciliation needs for its own sake, which is the definition of a host tool, so `brew "go"` stays in both Brewfiles and go is pinned in the two subprojects as well. The two do not conflict: the roles append mise's shim directory to the inherited PATH rather than prepending it, so brew's go wins wherever it exists and the shim is the fallback on pod042, which is Debian and has no Homebrew at all.

That fallback carries one live fragility. pod042 installs `go@latest` while the subprojects pin `go = "1.27"`. They agree today because latest resolves to 1.27.0. The day it becomes 1.28, the shim fails with "No version is set for shim" rather than falling back, and it fails during a reconcile on a machine nobody is watching. pod042 should pin the same version the subprojects do.

### 3. The Go subprojects become monorepo config roots

`ansible/roles/shp/files/shp` and `.../sessions/files/sessions` are Go projects with their own justfiles. Ansible builds them in place with `chdir: {{ role_path }}/files/shp`, so nothing is copied wholesale to a host and an extra `mise.toml` there is never deployed. That makes them structurally identical to ghosttykit's `cli/gty`.

The cost is honest: `config_roots` will contain two paths that read as Ansible role internals, and `mise run //ansible/roles/shp/files/shp:check` is the one place this design is worse to type than poe was. Accepted because root `check` fans out and the full path is rare. The fan-out is spelled `//ansible/...:check`, not `//...:check`: `...` matches the monorepo root itself, so the shorter form makes root `check` depend on itself.

### 4. Commit-time ansible-lint normalizes to the role directory

A sub-agent investigation established that ansible-lint runs `ansible-playbook --syntax-check` only on lintables of kind playbook, role, or pattern. Proven by planting `scope_probe.invalid_module:` in a role task: passing the task file exits clean, passing the role directory reports `syntax-check[unknown-module]`.

| invocation | time | syntax check |
| --- | --- | --- |
| `roles/foo/tasks/main.yml` | 1.5 s | no |
| `roles/foo` | 1.8 s | yes, plus defaults, handlers, meta, vars |
| `playbooks/truenas.yml` | 1.9 s | yes, follows imports and role refs |
| whole tree | 11.3 s | everything |

Normalizing to the role directory costs about 0.3 s and restores the coverage. `meta/main.yml` normalizes too, since direct meta linting also lacks role syntax-check. The largest role here, `agent_harness` at 12 YAML files, lints in 2.3 s.

Worth recording because it is the obvious thing to get wrong: there is no cross-file coverage being lost. ansible-lint has no undefined-variable rule at all, and `no-handler` only reads the current task's `when:`, never resolving `notify` targets. The whole-tree run was never providing that.

### 5. hk uses real glob'd steps, diverging from both sibling repos

Both sibling `hk.pkl` files are twelve lines and use exactly two step fields, `check` and `exclusive`. A step with no `glob` always runs, so every commit in `wt` runs the entire `lint` graph. That is fine when the graph is three seconds.

Here the graph is 27.3 s, so adopting the sibling shape verbatim would have doubled the current commit cost rather than reducing it. A hook that gets routed around with `--no-verify` is worse than a slow one. This is the single place where "match the other repos" was overruled, and it is overruled by a number rather than by taste.

### 6. `check` never mutates; `fix` does

Today's `poe lint` runs `ruff check --fix --unsafe-fixes`, so it can serve as neither. hk's model needs a clean non-mutating command for `check` and a separate mutating one for `fix`, which then gets `stage`d.

The failure this avoids is live in ghosttykit right now: its pre-commit step is named `check`, depends on `docs:fmt`, and that task runs `prettier --write` and `markdownlint-cli2 --fix`. With no `fix` field to stage them, the rewrites land unstaged and the commit completes carrying the unfixed content.

`--unsafe-fixes` stays out of the commit path and remains in the manual `fix` task, where a human is present to read the diff.

That exclusion is also what settles the staging question. hk offers `stage = false` with `fail_on_fix = true`, which applies fixes, stages nothing, and rejects the commit so you stage the result yourself. It was considered and declined. The argument for it is that auto-staging puts content in the index nobody reviewed, and in this repo the index is a review ledger. The argument against won: what reaches the commit path is `ruff format` and safe `ruff check --fix` only, both deterministic, and paying a second `git commit` on every formatting change to review output that is never surprising is a bad trade. `fix` keeps its name rather than becoming `fmt`, because it runs lint fixes alongside formatters and `fmt` would undersell it.

This design originally claimed no `fmt:check` tasks were needed, on the grounds that their only consumers would have been CI, which was declined, and the commit hook, which declares both forms itself inside the step. Implementation disproved that in every corner of the repo at once.

The consumer nobody accounted for is root `check` itself. `poe lint` already ran `ruff format --check` and `stylua --check`, and it fans out into the two Go subprojects whose `just check` ran `gofmt -w`. So splitting the mutating and non-mutating halves is not optional anywhere: `python:fmt:check`, `nvim:fmt:check`, and a `fmt:check` in each Go subproject all exist, with the mutating twins feeding `fix`.

`lint:ruff` needed the same surgery for the same reason. It ran `ruff check --fix --unsafe-fixes`, so it could serve as neither half. `python:lint` now checks and `python:lint:fix` carries both flags, which is where Decision 6 wanted `--unsafe-fixes` in the first place.

### 7. `--offline` at commit time only

`.ansible-lint` sets `offline: false`, so every invocation first runs `ansible-galaxy collection install -r requirements.yml`. Measured: role directory 1.83 s to 1.36 s, whole tree 11.34 s to 10.57 s. A 26% cut on the hook's dominant cost.

The full `ansible:lint` task stays online, which is also where a newly added collection requirement would first surface. Offline everywhere was rejected because a missing collection would then produce a confusing lint failure instead of being fetched.

### 8. zsh completion gets installed, and caching it is safe

mise ships zsh completion that this machine has never had. The generated script is byte-identical across three directories with entirely different task sets, because it is a static shim that calls `mise __complete_word__` at completion time. Directory-dependence lives in the callback, not the script, so `_evalcache mise completion zsh` is correct.

This is what makes the namespaced task names pay for themselves: `mise re<TAB>` enumerates the fleet.

## Edge Cases & Failure Modes

- **Fresh clone, no `.env`:** mise does not error on a missing `_.file` and the enter hook generates it, but it resolves `_.file` before the hook runs, so the process that caused the write does not see the secrets. First prompt of the generating shell: empty. Second prompt of that same shell: present. Any shell or process started once `.env` exists: present. `mise run bootstrap` first, then start the shell: present. direnv had no such gap, because `.envrc` ran init-secrets and `dotenv .env` in one evaluation. A human loses one command to this and moves on; a non-interactive reconcile gets a single shot and half-configures a host on empty `lookup('env', ...)` values, which is why `bootstrap:secrets` shouts to stderr whenever it generates.
- **`mise run reconcile` typed by accident:** verified harmless. Errors with `no task reconcile found` and lists the candidates. Under this design a bare `reconcile` is defined anyway, dispatching by hostname.
- **`mise run 'reconcile:*'`:** does fan out and run every host in parallel. Requires deliberately typing a quoted glob.
- **mise's Python missing:** `UV_PYTHON` points at a path that does not exist, uv errors immediately rather than falling back.
- **Staged file references a nonexistent module:** caught, via role-directory normalization. This is the regression the design exists to prevent.
- **A staged change breaks an unstaged file:** not caught by anything. No CI, no reconcile gate. Surfaces at the next deliberate `mise run check` or at reconcile time.
- **Work laptop:** mise already provides `node` and `golangci-lint` there, and Python via mise is confirmed working. No fallback path needed.

## Alternatives

### Sibling model verbatim: one no-glob hk dispatcher into `mise run lint`

- **Status:** Rejected
- **Decision:** doubles commit cost from 12.9 s to 27.3 s.
- **Discussion:** This was the stated preference at the start of the design session and lost to measurement. It remains right for `wt` and `ghosttykit`, whose whole graphs are seconds.

### uv keeps the Python interpreter

- **Status:** Rejected
- **Decision:** leaves the toolchain split across two owners for no gain once mise is present.
- **Discussion:** Argued for initially on the grounds that `only-managed` exists for a documented reason. The experiment in Design Decision 1 inverted the argument: keeping that variable under mise creates the split brain rather than preventing one.

### Commit a `mise.lock`

- **Status:** Rejected
- **Decision:** the work laptop deliberately runs older tool versions and that flexibility is wanted.
- **Discussion:** `wt` commits one, `ghosttykit` does not. The sibling repos disagree, so precedent decided nothing.

### CI workflow running the full `check`

- **Status:** Open
- **Open Issue:** with no CI and no reconcile gate, nothing verifies the whole tree automatically. A staged change that breaks an unstaged file surfaces only at reconcile time, potentially mid-run on a remote host.
- **Discussion:** Declined twice, deliberately, on the grounds that this is a solo repo reconciled by hand. Neither sibling runs hk in CI either, though both run mise tasks there. `hk check --all` offers a cheaper partial net covering every hk step against the whole repo.
- **Next step:** if a broken reconcile is ever traced to an unstaged file that a full check would have caught, revisit. Roughly fifteen lines of workflow.

### Gating `reconcile:*` on `check`

- **Status:** Rejected
- **Decision:** 27 seconds before every `-t chezmoi` iteration is the same trap as the slow commit hook.
- **Discussion:** Deploying is the moment being wrong costs something, so it is the theoretically right place for a gate. Rejected on the practical grounds that a bypass flag would get used by reflex within a week.

## Implementation Plan

- [x] Phase 1: mise owns the environment
  - Goal: a new shell in the repo is configured by mise alone; direnv is gone.
  - Files: `mise.toml` (new), `.envrc` (deleted), `.gitignore`, `scripts/bootstrap.sh`
  - Work: `[tools]` with python, node, go, golangci-lint, stylua, opentofu, hk. `[env]` with `UV_PYTHON`, `_.python.venv`, `_.file = ".env"`, `ANSIBLE_CONFIG`, `SUDO_ASKPASS`. Delete `UV_PYTHON_PREFERENCE`. `bootstrap` task with `sources`/`outputs` covering `uv sync --dev`, the pi-extension npm install, and the work-machine `skip-worktree` calls. `hooks.enter` calls it. Update bootstrap.sh to stop mentioning `direnv allow`.
  - Validation: `rm -rf .venv && exec zsh` in the repo rebuilds it on mise's interpreter — confirm with `grep ^home .venv/pyvenv.cfg`. Confirm the 85 secrets variables are present. Time a fresh shell against the 195 ms target. `uv run poe lint` must still pass, since poe is untouched this phase.

- [x] Phase 2: Go subprojects become config roots
  - Goal: `shp` and `sessions` own their toolchains; `just` leaves the dev-tool list.
  - Files: `ansible/roles/{shp,sessions}/files/*/mise.toml` (new), the two justfiles (deleted), root `mise.toml`
  - Work: `monorepo_root` and `[monorepo] config_roots`, both verified against mise's live JSON schema and neither needing `MISE_EXPERIMENTAL`. `task_config.cascade` is real but cascades task *configuration* rather than tasks, and root has no `[task_config]` to cascade, so it is omitted as inert. Each subproject gets `fmt`, `fmt:check`, `lint`, `test`, `build`, `install`, `deps:update`, and `check`, pinning its own `go` and `golangci-lint`. `install` and `deps:update` exist because Ansible calls them: the `shp` and `sessions` roles were themselves `just` callers, which this plan missed.
  - Validation: `mise run //ansible/roles/shp/files/shp:check` and the sessions equivalent both pass. The Ansible build path still works: `uv run poe laptop -t shp --check`.

- [x] Phase 3: task surface
  - Goal: poe is deleted; every task has its new name.
  - Files: root `mise.toml`, `pyproject.toml`, `scripts/aig_deploy.py`, `scripts/hooks_deploy.py`
  - Work: port all reconcile, edge, check, and upkeep tasks with usage specs and aliases. Give the two deploy scripts argparse CLIs, since poe's `script = "module:main(arg)"` has no mise equivalent. Add bare `reconcile` dispatching by hostname. Drop `cz-status`, `cz-managed`, `cz-edit`. Remove `poethepoet` from dev dependencies.
  - Validation: `mise run check` reproduces the current clean `poe lint` result. Every reconcile task runs with `--check`. `mise tasks` lists the intended surface and nothing else.

- [x] Phase 4: hk replaces pre-commit
  - Goal: a commit touching one role is verified in about two seconds.
  - Files: `hk.pkl` (new), `scripts/ansible-lint-staged.sh` (new), `.pre-commit-config.yaml` (deleted), `pyproject.toml`
  - Work: steps per the table in Exposed Shape, each with `glob`, non-mutating `check`, and `fix` + `stage` where applicable. Normalizer script. `hk install --mise` wired into the bootstrap task. Remove `pre-commit` from dev dependencies and drop the `uv-lock` hook.
  - Validation: normalizer table test over representative paths. Stage a role task containing `scope_probe.invalid_module:` and confirm the commit is rejected — this is the regression that justifies the whole scoping design. Stage an unformatted Python file and confirm the fix is applied and staged. Time a single-role commit.

- [x] Phase 5: documentation and completion
  - Goal: nothing in the repo still tells you to run poe or `direnv allow`.
  - Files: `DEV.md`, `AGENTS.md`, `README.md`, `README.work.md`, `chezmoi/dot_zshrc.tmpl`, `ansible/Brewfile`
  - Work: rewrite every `uv run poe X` reference. Add `_evalcache mise completion zsh` to the zshrc template. Drop `just` from the Brewfile. `CONTEXT.md` already carries Dev tool, Host tool, Check, and Fix.
  - Validation: `rg 'poe |direnv allow' --glob '!docs/designs/'` returns nothing. `mise re<TAB>` completes in a fresh shell after `chezmoi apply`.
