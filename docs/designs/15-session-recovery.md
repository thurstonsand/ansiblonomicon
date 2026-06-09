# 15 — Session Recovery (Claude Code + Pi)

## Problem

A hard restart (power loss, forced reboot, kernel panic) kills every active
agent session with no warning. Claude Code and Pi each keep durable transcripts
on disk, but after a crash there is no list of *which* sessions were live or how
to resume them. We want a recoverable record: at minimum a list of session ids
and their working directories, written continuously so the last pre-crash state
survives.

## Design

Each tool writes **one file per live session** into a shared, XDG-standard state
tree. A session only ever touches its own file; there is no shared index and no
cross-session scanning, so the two tools — and concurrent sessions within a tool
— never contend for the same file.

```
${XDG_STATE_HOME:-~/.local/state}/session-recovery/
  claude/<sessionId>.json     # owned by Claude Code
  pi/<sessionId>.json         # owned by Pi
```

Directories are mode `0700`. Each tool owns its subdir exclusively.

### Record schema

Both tools write the same shape so a single restore reader can consume both
halves:

```jsonc
{
  "sessionId": "string",        // resume key for the owning tool
  "name": "string|null",        // human label for completion, if the tool has one
  "cwd": "string",              // working dir to resume from
  "transcript": "string|null",  // absolute path to the transcript, if known
  "pid": 12345,                 // the agent process that owns the session
  "bootId": "string",           // boot identity at write time (see below)
  "updatedAt": 1780679882949,   // epoch milliseconds, last refresh
  "tool": "claude" | "pi"
}
```

`name` lets `sessions r` complete by a readable label instead of a raw id. It is
refreshed alongside `updatedAt` so a late-assigned title (e.g. Pi's auto-title)
lands in the record. The CLI reads only these records — never the transcripts —
so every field it needs to list and resume must live here.

### Boot identity

`bootId` distinguishes a live session in the current boot from a leftover record
of a prior boot. Without it, PID reuse across reboots could make a stale record
look alive (or a fresh post-crash session look like a leftover).

- **macOS**: `sysctl -n kern.bootsessionuuid`
- **Linux**: contents of `/proc/sys/kernel/random/boot_id`
- **Fallback**: empty string (degrades to mtime-based reasoning)

Both tools must read these **identical** sources so the same boot yields a
byte-identical `bootId`. The unified reader's `(bootId, pid)` dedup and the
prior-boot recovery check both depend on this. Pi reads them from the extension
process directly — `node:child_process` for `sysctl` on macOS, `node:fs` for
`/proc/sys/kernel/random/boot_id` on Linux. A wall-clock or `os.uptime()`-derived
boot epoch would *not* be comparable with Claude's UUID and must not be used.

### Lifecycle

| Event (Claude hook) | Action |
|---|---|
| `SessionStart` (startup/resume/clear/compact) | Write/refresh own file. |
| `Stop` | Refresh own file (keeps `cwd` + `updatedAt` current). |
| `SessionEnd` | Delete own file. `SessionEnd` is the single delete authority and is terminal; a clean exit leaves nothing to recover. |

`SessionEnd` fires on **every** terminal transition, `/clear` included. A
`/clear` emits `SessionEnd(reason=clear)` on the outgoing session — which
deletes its file — immediately followed by `SessionStart(source=clear)` on the
new session in the same process, which writes the new file. There is no special
clear-handling: the ordinary delete-on-`SessionEnd` covers it.

A hard restart fires **no** `SessionEnd`, so the file survives. That surviving
file, with a `bootId` from a prior boot, is the recovery signal.

Pi maps onto the same write/refresh/delete semantics through its extension
lifecycle events. Pi's events are **symmetric**: `session_shutdown` fires for
every transition (quit, reload, new, resume, fork, clone) and `session_start`
fires for every (re)entry (startup, new, resume, fork, reload). The recorder
exploits this symmetry:

| Event (Pi extension) | Action |
|---|---|
| `session_start` (any reason) | Write/refresh own file for the current `getSessionId()`. |
| `agent_end` | Refresh own file (Pi's analog of Claude's `Stop` — once per user prompt). |
| `session_shutdown` (any reason) | Delete the file for the **current** `getSessionId()`. |

Why delete on *every* shutdown, not just on quit: `/new`, `/resume`, `/fork`,
and `/clone` mint a **new** `sessionId` in the same process. If the old file
weren't deleted, it would linger forever and — after the next reboot — falsely
appear as a crash survivor. At `session_shutdown` the context is still bound to
the outgoing session, so `getSessionId()` returns the id to delete; the
following `session_start` writes the new id. For `quit` (terminal) the delete is
the final act and nothing recovers — exactly the clean-exit contract.

Pi-specific bindings:

- **`pid`** is `process.pid`. The recorder runs *inside* the Pi process, so —
  unlike Claude's hook subprocess — there is no `os.getppid()` indirection.
- **`sessionId`** is `ctx.sessionManager.getSessionId()`; **`transcript`** is
  `ctx.sessionManager.getSessionFile()`; **`cwd`** is `ctx.cwd`.
- **`name`** is `pi.getSessionName()` (often `null` until Pi's auto-title runs);
  re-read on each `agent_end` refresh so a late title reaches the record.
- **Guards**: only record real, resumable, interactive sessions. Skip when
  `getSessionFile()` is undefined (ephemeral / `--no-session`) and when
  `!ctx.hasUI` (print/RPC runs exit on completion and have nothing worth
  resuming after a crash).
- Pi compaction fires `session_compact`, **not** `session_start`, so the
  "refresh on compact" behavior from Claude's table is covered by `agent_end`
  instead.

Pi does **not** need any predecessor-delete logic because its shutdown/start
pair already removes the outgoing session deterministically. Both tools' records
share the `(bootId, pid)` shape so a unified reader can reason about lineage
uniformly if needed.

### `/clear` and same-process identity changes

`/clear` (verified empirically on Claude Code 2.1.165) fires
`SessionEnd(reason=clear)` on the outgoing session, then
`SessionStart(source=clear)` on a new session in the *same* process under a new
`sessionId`. Because `SessionEnd` deletes the outgoing file, the discarded
conversation is gone before the successor writes its own — no sibling-scanning
or lineage bookkeeping is needed. The writer keeps a verbose debug log at
`/tmp/claude-session-recovery.log` for retuning if these semantics change.

## The `sessions` CLI

The single user surface is one Go/Cobra binary, `sessions`, that reads both
tools' data and dispatches the correct resume verb per `tool`. It replaces the
earlier split plan (`claude-restore` + a Pi-native `/recover-sessions`). Cobra is
chosen for its zero-effort, dynamic shell completion (`ValidArgsFunction`).

### Single source: the recovery tree

The CLI reads **only** `session-recovery/{claude,pi}/` — never the transcripts
or the native session stores. Those records hold exactly the sessions that
opened and have not cleanly shut down: the currently-live ones and the
crash/orphan survivors. Cleanly-closed historical sessions deleted their own
record and are intentionally out of scope. Every field the CLI needs (`name`,
`cwd`, `sessionId`, `tool`, `pid`, `bootId`) lives in the record, so the reader
stays fully tool-agnostic.

A record is classified by liveness:

- **live** — `bootId == currentBoot` **and** `pid` is alive. Open in some window
  right now.
- **orphaned** — anything else: prior-boot survivors, or a current-boot record
  whose process died without firing its shutdown hook. These are the crashed
  sessions worth resuming.

### Commands

- `sessions ls` — list every record, each labeled `live` or `orphaned`. Default
  scope is the **current directory** (records whose `cwd` matches `$PWD`).
  `-a`/`--all` lists across **all** directories, grouped by `cwd`. De-duped by
  `(bootId, pid)`, newest per lineage.
- `sessions r|resume [name|id]` — resume an **orphaned** session. Completion and
  argument matching are scoped to the current directory and to orphaned records
  only: historical sessions aren't tracked, and `live` sessions are excluded
  (already open elsewhere). The CLI resolves `name|id` to a record, then execs
  that tool's resume verb from the record's `cwd`.
  - `sessions r -a|--all [name|id]` widens completion and matching to orphaned
    records across **all** directories. Resume still `cd`s into the record's
    `cwd` first, so a cross-repo resume lands in the right tree.
- `sessions prune` — delete records whose `bootId` differs from the current boot
  (genuine prior-boot leftovers); live records untouched.
- `sessions shell {bash,zsh}` — emit shell integration (the Cobra completion
  script) for `eval "$(sessions shell zsh)"`. `sessions completion ...` (Cobra's
  built-in) also remains available.

### Resume verbs

- `pi` → `(cd <cwd> && pi --session <sessionId>)`
- `claude` → `(cd <cwd> && claude --resume <sessionId>)`

### Completion

`r`'s `ValidArgsFunction` filters the recovery tree to orphaned records — current
directory by default, all directories under `--all` — newest-first. It offers
each record's `sessionId` and, when
present, its `name` as alternate candidates; the completion *description* carries
`<tool> · <name> · <relative-age>` (and `· <cwd>` under `--all`) so the picker is
legible. An argument that uniquely matches a `name` resolves to that record;
otherwise it is treated as a `sessionId`.

## Files

Shared library (a local package, referenced by bare specifier):

- `chezmoi/dot_local/lib/session-recovery/` → `~/.local/lib/session-recovery/`,
  the package `@thurstons/session-recovery`. Single on-disk home of the shared
  code; a small TS package (`package.json` with an `exports` map, `tsconfig.json`,
  dev-only `node_modules` like `amp-plugins`), linted by
  `scripts/session-recovery-lint.sh` (`lint:session-recovery`) and tracked by
  `scripts/ts-package-deps.sh`.
  - `core.ts` — the shared writer: `SessionRecord` schema, `bootId()`,
    `stateDir()`, `writeRecord()`, `deleteRecord()`. Node builtins only, zero
    runtime deps; `exports` `.` → `./core.ts`.

- **How agents consume it — idiomatic bare specifier.** Each agent declares a
  dependency on the package and imports it by name
  (`import { writeRecord } from "@thurstons/session-recovery"`). On the live
  machine the dependency is materialized into the agent's `node_modules` by
  chezmoi's existing installer, `run_onchange_after_install-ts-package-deps.sh`,
  which runs `npm install` per package under each agent root (`~/.pi/agent/...`
  and `~/.claude/scripts`) whenever a `package.json` changes (its
  `# Dependency trigger:` hash). A directory `file:`
  dep installs as a symlink, so edits to `core.ts` flow through with no
  reinstall, and the install touches no registry (the link is local).

- **Pi consumer:** `chezmoi/private_dot_pi/agent/extensions/session-recovery/`
  — `index.ts` (wires `session_start`/`agent_end` → `writeRecord`,
  `session_shutdown` → `deleteRecord`) plus a `package.json` whose only entry is
  `"@thurstons/session-recovery": "file:../../../../.local/lib/session-recovery"`
  (a **live-layout** path) and `pi.extensions: ["./index.ts"]`. It carries **no
  devDependencies** so the live `npm install` only links the local path and
  never hits the registry (this is what keeps it working on the work network,
  where the registry is blocked).

- **Two consequences of the live-layout `file:` path, and how each is handled:**
  - It does **not** resolve in the source checkout. For **type-checking**, the
    consumer carries a **lint-only `tsconfig.json`** with a `paths` mapping
    (`@thurstons/session-recovery` → the repo-source `core.ts`) that `tsc`
    honors but the runtime ignores. That tsconfig is in `.chezmoiignore`, so it
    never deploys — its repo-relative path would be wrong on the live machine,
    and jiti could otherwise honor it and override the `node_modules`
    resolution. The consumer needs no devDependencies: `tsc`/biome resolve
    `@earendil` and `@types/node` from the parent extensions `node_modules`.
  - For **dep management**, `scripts/ts-package-deps.sh` still skips the
    consumer: `npm install` in the source checkout would fail on the unresolved
    `file:` path, and the consumer has no registry deps to pin anyway.
  - The shared package is **never installed** on the live machine (it has
    dev-only deps); only its source files deploy, and consumers symlink to them.
    So it is kept out of the installer's roots — adding it would try to fetch its
    devDeps and fail on work.

Claude Code recorder:

- `chezmoi/dot_claude/scripts/session-recovery/` — the Claude consumer, a
  `bun`-run TS recorder that mirrors the Pi consumer. `index.ts` reads the hook
  payload from stdin and maps `SessionStart`/`Stop` → `writeRecord`, `SessionEnd`
  → `deleteRecord` (pid via `process.ppid` — Claude injects none; `tool:
  "claude"`). `name` is read from the transcript (the latest `custom-title`
  line's `customTitle`), since Claude's `Stop` payload carries no title; it
  refreshes on every write so a late title lands. It imports
  `@thurstons/session-recovery` by bare specifier, resolved on the live machine
  via a `node_modules` symlink from its `package.json` `file:` dep
  (`../../../.local/lib/session-recovery` — three `../`, vs the Pi consumer's
  four). Its lint-only `tsconfig.json` (`paths` + `typeRoots` → the repo-source
  lib) is in `.chezmoiignore`. Linted by `scripts/session-recovery-lint.sh`
  (under `lint:session-recovery`), which borrows the shared lib's biome/tsc
  toolchain so the consumer needs no devDeps.
- The dependency symlink is materialized by the same installer as Pi's,
  `run_onchange_after_install-ts-package-deps.sh.tmpl`, generalized to also walk
  `~/.claude/scripts`. The consumer carries only the local `file:` dep (no
  devDeps), so the work-host `npm install --omit=dev` links it with zero registry
  access.
- Hook wiring: `SessionStart`, `Stop`, `SessionEnd` (command
  `bun ~/.claude/scripts/session-recovery/index.ts`) in
  `chezmoi/.chezmoitemplates/claude-settings.json` (base) and the work overlay
  `chezmoi/.chezmoitemplates/local/claude-settings-overlay.json`, which replaces
  `SessionStart` and `Stop` wholesale and so carries the recorder too; the
  overlay defines no `SessionEnd`, so the base `SessionEnd` survives the merge.
- The superseded Python recorder (`session-record.py`) and the original
  `claude-restore` CLI are removed by `state: absent` tasks in
  `ansible/roles/sessions/tasks/main.yml`.

Shared CLI:

- `ansible/roles/sessions/files/sessions/` — the `sessions` Go/Cobra source,
  structured like the in-repo `ghostty-nav`/`shp` tools: own `go.mod`,
  `justfile` (`fmt`/`lint`/`test`/`check`/`build`/`install`/`update-deps`),
  `.golangci.yml`, and an `internal/cmd` Cobra tree, with a `lint:sessions` poe
  task under `lint:cli-tools`.
- `ansible/roles/sessions/` — deploy role (mirrors `shp`): checksum-gated
  rebuild that runs `just install` to build the binary into `~/.local/bin`.
  Invoked under the `sessions` tag from `macos.yml`, `work.yml`, and
  `openclaw.yml`. Go comes from Homebrew (`brew "go"`); only `golangci-lint` is
  mise-managed and is needed for `lint:sessions`, not for the deploy build.
- Shell completion is loaded via `_evalcache sessions shell zsh` in
  `chezmoi/dot_zshrc.tmpl`, guarded by
  `(( $+commands[sessions] ))` so a machine
  without the binary yet does not error. Reading only the recovery tree, the CLI
  is the single user surface; neither tool ships its own restore command.

## Notes / limitations

- If **zero** sessions are ever active, nothing refreshes the tree — fine for
  crash recovery, since the goal is to capture the last-live state.
- `pid` for the Claude recorder is `process.ppid` (the `bun` hook is a child of
  the Claude process; Claude injects no PID into the payload or environment). The
  Pi recorder runs in-process and uses `process.pid` directly.
- Atomic writes (temp file + rename within the same subdir) keep a record from
  being observed half-written if power is lost mid-write.
