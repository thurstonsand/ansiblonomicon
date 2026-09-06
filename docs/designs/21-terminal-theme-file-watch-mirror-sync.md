# Terminal Theme File-Watch Mirror Sync

## Status

Draft

## Decision Summary

Terminal theme mirroring should move toward a file-based active-session sync model: the macOS source writes `~/.terminal-bg` to active remote GhosttyKit sessions, and each mirror host applies side effects by watching that state file. GhosttyKit provides only generic remote file push, described in [ghosttykit docs/designs/02-remote-agent-file-push.md](https://github.com/thurstonsand/ghosttykit/blob/main/docs/designs/02-remote-agent-file-push.md); ansiblonomicon owns theme semantics.

## Problem Statement

The current terminal theme role has a macOS detector profile and a remote mirror profile. On theme change, the source host updates local tool config and shells out over direct SSH to each active mirror host:

```text
~/.local/bin/terminal-theme-switch.py --no-mirror-sync <light|dark>
```

Active hosts are tracked through OpenSSH `LocalCommand` leases. This works, but it is tied to raw SSH config and does not use the emerging GhosttyKit SSH bridge, which already models active remote sessions.

A tempting integration would be to put theme-specific commands into GhosttyKit. That is the wrong boundary. GhosttyKit should provide generic file push over active bridged sessions; terminal theme state and application remain ansiblonomicon concerns.

## Goals

- Preserve active-session-only mirror updates.
- Keep terminal theme behavior out of GhosttyKit.
- Split terminal theme state writing from side-effect application.
- Use a Debian-native, low-idle-cost file watcher on mirror hosts.
- Keep the current direct SSH sync path during migration.

## Non-Goals

- Do not require a persistent GhosttyKit remote daemon.
- Do not add terminal theme commands to GhosttyKit.
- Do not add a GhosttyKit hook or plugin system for this use case.
- Do not require direct remote command execution for theme sync once file push exists.
- Do not remove raw SSH mirror sync until the GhosttyKit path is proven.

## Design Decisions

### 1. Split switch and apply scripts

`terminal-theme-switch.py` currently writes `~/.terminal-bg`, updates local application config, and optionally syncs mirrors. That is too much responsibility for file-watch sync because a watcher reacting to `~/.terminal-bg` would risk recursion if it calls the same script.

Split the behavior:

```text
terminal-theme-switch.py <mode>
  writes ~/.terminal-bg
  calls terminal-theme-apply.py <mode>
  syncs active mirrors unless --no-mirror-sync

terminal-theme-apply.py <mode|--read-state>
  updates Codex, Hunk, and other local app config
  never writes ~/.terminal-bg
  never syncs mirrors
```

This keeps local detector behavior intact while giving mirror hosts a safe idempotent apply entrypoint.

### 2. Watch the state file on mirror hosts

Mirror hosts should install a user-level file watcher for `~/.terminal-bg`. On Debian/OpenClaw, use `systemd --user` path activation:

```text
terminal-theme.path
  PathChanged=%h/.terminal-bg

terminal-theme.service
  ExecStart=%h/.local/bin/terminal-theme-apply.py --read-state
```

This is efficient because systemd uses inotify. Idle CPU cost is effectively zero; no polling loop is needed. If user lingering is enabled, the watcher may operate while logged out. If lingering is not enabled, an active SSH login should still have a user manager, which is enough for active-session behavior.

### 3. Use GhosttyKit only for generic file push

When GhosttyKit remote-agent file push exists, the macOS source can mirror state by writing this file to active remote sessions:

```text
~/.terminal-bg = "dark\n" or "light\n"
```

The remote watcher then runs `terminal-theme-apply.py --read-state`. This gives the same result as direct SSH execution without making GhosttyKit aware of terminal themes.

### 4. Keep direct SSH mirror sync during migration

The current lease/direct-SSH path should remain until the GhosttyKit path is implemented and reliable:

```text
source terminal-theme-switch.py
  -> current direct SSH sync for raw SSH leases
  -> future GhosttyKit file push for active gty sessions
```

During migration, duplicate application is acceptable if `terminal-theme-apply.py` is idempotent. The source should eventually prefer GhosttyKit active remote agents and use direct SSH only as a compatibility fallback for raw `ssh` sessions.

### 5. Rename profile terms later, not inside this refactor

The existing profiles are:

- `detector`
- `mirror`

The clearer long-term language is:

- `source`
- `mirror`

Do not combine the rename with the script split and watcher changes unless the implementation phase is explicitly scoped for it. If renamed later, keep `detector` as a compatibility alias for one deployment cycle.

## Edge Cases & Failure Modes

- **No active SSH session:** no GhosttyKit remote agent is available, so no file push occurs. This preserves the current active-session-only intent.
- **No systemd user manager:** the watcher will not run until a user session starts. With active SSH, the user manager should normally be available.
- **Lingering enabled:** the watcher may apply theme state even while no interactive session is active. This is acceptable and cheap.
- **Direct SSH and GhosttyKit both update the same mirror:** `terminal-theme-apply.py` must be idempotent so duplicate application is harmless.
- **State file contains invalid mode:** `terminal-theme-apply.py --read-state` should fail clearly and avoid modifying tool config.
- **GhosttyKit file push fails:** log the failure and keep direct SSH fallback during migration.
- **Watcher sees partial write:** GhosttyKit and local switch logic should write `~/.terminal-bg` atomically where practical.

## Rejected Alternatives

### Put theme sync commands in GhosttyKit

Rejected because terminal theme state is personal environment policy, not a GhosttyKit domain concept.

### Add a GhosttyKit hook/plugin system

Rejected for this use case because file push plus a platform-native file watcher is simpler and more explicit.

### Add remote execution to GhosttyKit

Rejected because arbitrary command execution reintroduces shell quoting, environment, and security policy problems. SSH already provides remote execution.

### Run a session-scoped theme watcher under `gty ssh remote-run`

Rejected for now because it adds another lifecycle branch inside GhosttyKit or its wrapper. A systemd user path unit is simpler, efficient, and works for both raw SSH and bridged sessions.

### Keep only direct SSH sync

Rejected as the long-term model because GhosttyKit will already know about active bridged sessions and can provide a cleaner active-session transport once remote-agent file push exists.

## Integration Points

- `ansible/roles/terminal_theme/files/terminal-theme-switch.py`: split state writing from side-effect application.
- `ansible/roles/terminal_theme/files/terminal-theme-apply.py`: new apply-only helper.
- `ansible/roles/terminal_theme/tasks/main.yml`: install the apply helper and mirror watcher units.
- `ansible/roles/terminal_theme/templates/`: add systemd user path/service units for mirror hosts.
- `ansible/roles/terminal_theme/files/terminal_theme_common.py`: eventually add GhosttyKit file-push sync alongside or instead of direct SSH sync.
- `ansible/openclaw.config.yml`: remains a mirror host.
- `ansible/darwin.config.yml`: remains the source host and active mirror list owner during migration.
- GhosttyKit remote agent design: provides the generic active-session file push primitive.

## Implementation Plan

Deferred to Gate 3.
