# Ghostty SSH Neovim bridge

## Status

Superseded by the daemon-backed `ghostty-nav` bridge.

The implemented path uses the portable Go `ghostty-nav` client on OpenClaw, SSH `RemoteForward` for the daemon Unix socket, and `GHOSTTY_NAV_TTY` propagation through zsh/SSH environment forwarding. It avoids Ghostty AppleScript terminal-id matching entirely, so the deferred `terminal.tty` dependency below is no longer the active implementation plan.

The historical design assumed Ghostty AppleScript `terminal` objects would provide:

- `id`: stable terminal surface id
- `tty`: controlling PTY path or basename for that surface

Do not revive the focus-based fallback. It targets the wrong surface as soon as panes, tabs, or automation are involved.

## Problem Statement

Local Neovim already integrates with Ghostty native splits:

1. Ghostty's default key table maps `Ctrl-h/j/k/l` to `goto_split:*`.
2. Neovim activates Ghostty's `nvim` key table while it is running.
3. In the `nvim` key table, `Ctrl-h/j/k/l` pass raw control bytes to Neovim.
4. At a Neovim window edge, Neovim calls `ghostty-nav move <direction>` to move the surrounding Ghostty split.

Remote Neovim over SSH/OpenClaw should behave the same way. A remote process cannot run the local macOS `ghostty-nav`, and Ghostty does not expose a supported OSC/DCS sequence for arbitrary actions such as `activate_key_table:nvim` or `goto_split:left`.

The bridge must target the local Ghostty terminal surface that owns the SSH session, not the currently focused terminal.

## Design Decisions

### 1. Use SSH-level plumbing, not shpool-level plumbing

The problem is remote process to local terminal control. Shpool is only one consumer. Plain interactive SSH sessions can also start Neovim.

The bridge will be created by a local interactive SSH wrapper named `shp` for OpenClaw sessions. Shpool-specific behavior is limited to stable remote socket names and active-editor markers.

### 2. Wait for Ghostty `terminal.tty`

The primary terminal identity mechanism will be:

1. `shp` asks the local process for its controlling TTY via `/dev/tty`.
2. `ghostty-nav terminal-id` queries Ghostty AppleScript terminals.
3. It matches the process TTY against `terminal.tty`.
4. It returns the matching terminal's stable `id`.

Matching must normalize both full paths and basenames, because Ghostty may expose either `/dev/ttys016` or `ttys016`.

Rejected for primary use:

- **Focused terminal lookup:** wrong for unfocused panes and automation.
- **OSC title probe:** valid as a compatibility fallback, but deliberately deferred. It mutates visible title state and exists only to support older Ghostty builds.
- **PID matching:** foreground process ids change; the PTY is the identity.

### 3. Use the same `ghostty-nav` command name on each platform

Chezmoi can install platform-specific implementations at the same path.

macOS `~/.local/bin/ghostty-nav`:

- real Swift/AppKit/Ghostty AppleScript controller
- supports local layout commands used today
- adds target-aware commands:
  - `terminal-id`
  - `--terminal-id <id> activate nvim`
  - `--terminal-id <id> deactivate`
  - `--terminal-id <id> move left|down|up|right`
  - `serve --socket <path> --terminal-id <id>`

OpenClaw `~/.local/bin/ghostty-nav`:

- Python or shell shim
- resolves the current bridge socket dynamically
- forwards only the remote-safe Neovim navigation contract:
  - `available`
  - `activate nvim`
  - `deactivate`
  - `move left|down|up|right`

The OpenClaw shim must not forward arbitrary Ghostty action strings, split creation, resize, title changes, text input, or shell commands.

### 4. Use OpenSSH `RemoteForward` Unix sockets

No separate reverse SSH connection is needed. `shp` will use the existing SSH connection:

```sh
ssh \
  -tt \
  -o ControlMaster=no \
  -o ControlPath=none \
  -o ExitOnForwardFailure=yes \
  -o StreamLocalBindUnlink=yes \
  -o StreamLocalBindMask=0177 \
  -R "$remote_sock:$local_sock" \
  openclaw
```

Rationale:

- Remote Unix socket forwarding is the supported OpenSSH primitive for remote-to-local side channels.
- `ExitOnForwardFailure=yes` prevents sessions that claim bridge support but have no bridge.
- `ControlMaster` is disabled because multiplexing collapses per-surface identity.
- Unix sockets avoid exposing a TCP listener.

### 5. Add an explicit `shp` wrapper

`shp` is an interactive OpenClaw SSH wrapper, not a full `ssh` replacement.

Initial supported forms:

```sh
shp openclaw
shp openclaw '<interactive command>'
shp --shpool-session edit-ansiblonomicon openclaw '<remote shpool attach command>'
```

For the first implementation, non-OpenClaw hosts should fail clearly rather than silently passing through. Ordinary `ssh` remains ordinary SSH for Ansible, Git, rsync, scp, and scripts.

`shp` flow:

1. Require Ghostty and an interactive local TTY.
2. Capture the local Ghostty terminal id with `ghostty-nav terminal-id`.
3. Start `ghostty-nav serve --socket <local_sock> --terminal-id <id>`.
4. Wait until the local socket exists.
5. Start SSH with remote Unix socket forwarding.
6. Set/prefix remote bridge environment:
   - `GHOSTTY_NAV=1`
   - `GHOSTTY_NAV_SOCKET=<remote_sock>`
   - `GHOSTTY_NAV_SESSION=<uuid>` for plain SSH
   - `GHOSTTY_NAV_SHPOOL_SESSION=<session>` for shpool mode
7. On exit, deactivate the captured terminal id, kill the bridge, and remove the local socket.

Use short local socket paths to avoid macOS Unix socket path length limits:

```text
/tmp/gnav.<uid>/<uuid>.sock
```

### 6. Use different socket identity for plain SSH and shpool

Plain SSH uses a random per-connection path:

```text
~/.local/run/ghostty-nav/ssh/<uuid>.sock
```

Shpool uses a stable per-session path:

```text
~/.local/run/ghostty-nav/shpool/<safe-shpool-session>.sock
```

Reason: a shpool session can outlive the SSH transport. A remote Neovim process may keep running while the local bridge disconnects and later reconnects from a different Ghostty pane. The remote shim must resolve the current socket dynamically instead of trusting stale process environment.

OpenClaw shim resolution order:

1. `~/.local/run/ghostty-nav/shpool/<safe-$SHPOOL_SESSION_NAME>.sock`
2. `~/.local/run/ghostty-nav/shpool/<safe-$GHOSTTY_NAV_SHPOOL_SESSION>.sock`
3. `$GHOSTTY_NAV_SOCKET`

### 7. Track active Neovim state separately from local key-table state

For shpool sessions, remote Neovim should write an active marker when running:

```text
~/.local/state/ghostty-nav/shpool/<safe-session>.active
```

It should remove the marker on `VimLeavePre` and `VimSuspend`.

The marker means "the persistent remote Neovim is active." It does not mean "the currently attached local Ghostty surface is in the `nvim` key table."

On shpool attach, `shp` or the remote attach prelude should activate the local `nvim` key table if the active marker exists. On SSH detach/exit, local cleanup should deactivate only the captured local terminal id and must not delete the remote active marker.

## Security Model

No token is planned. OpenClaw is trusted, and the socket directories are user-private.

Required mitigations:

- Remote socket parent directories mode `0700`.
- Unix sockets only, not TCP.
- `StreamLocalBindMask=0177`.
- `StreamLocalBindUnlink=yes` for stable shpool sockets.
- Strict command whitelist in both OpenClaw shim and local bridge.
- No arbitrary Ghostty action forwarding.
- No text input forwarding.
- No ControlMaster for bridged sessions.
- Do not forward `GHOSTTY_NAV_*` through nested SSH by default.

The effective remote capability is limited to:

```text
activate nvim
deactivate
move left|down|up|right
```

That is acceptable for the trusted OpenClaw user.

## Neovim Changes

The existing command contract should remain:

```text
ghostty-nav activate nvim
ghostty-nav deactivate
ghostty-nav move left|down|up|right
```

Detection should allow either local Ghostty or bridge mode:

```lua
local function bridge_possible()
  return vim.env.TERM_PROGRAM == "ghostty"
    or vim.env.GHOSTTY_NAV == "1"
    or (vim.env.SHPOOL_SESSION_NAME ~= nil and vim.env.SHPOOL_SESSION_NAME ~= "")
end
```

Remote bridge availability should be probed with:

```sh
ghostty-nav available
```

Do not cache failed availability forever; a later shpool reattach may create a working bridge.

## Failure Handling

- **SSH disconnect while Neovim is active:** local `shp` cleanup deactivates the captured terminal id. Remote active marker remains for shpool.
- **Shpool reattach from another Ghostty pane:** stable remote socket path is rebound to the new local bridge; old cleanup only affects its captured old terminal id.
- **Remote shim called without a bridge:** `available` returns nonzero; `deactivate` exits successfully and quietly; `move` fails quietly unless debug is enabled.
- **Stale shpool active marker:** a remote shell prompt hook may later clear the marker when the prompt returns outside Neovim.
- **Missing remote socket directory:** SSH must fail closed via `ExitOnForwardFailure=yes`; do not start a bridge-advertised session without forwarding.
- **Ghostty release lacks `terminal.tty`:** implementation should fail closed with a message saying the installed Ghostty does not expose terminal TTY identity yet.

## Rejected Alternatives

- **Ghostty OSC action control:** Ghostty does not expose supported OSC/DCS sequences for arbitrary actions like `activate_key_table` or `goto_split`. Terminal output is the wrong trust boundary for local UI actions.
- **Per-host bridge:** breaks when two Ghostty panes SSH to the same host and only one runs Neovim. The real identity is the local terminal surface.
- **Focus-based terminal id:** wrong for unfocused panes, split automation, and cleanup after focus changes.
- **Global `ssh` shell wrapper:** too easy to surprise Ansible, Git, rsync, scp, and one-off commands. Start explicit with `shp`.
- **Agent forwarding piggyback:** wrong capability and worse security profile.
- **Stdout sideband parser:** reimplements a private OSC with binary transparency and accidental-trigger problems.

## Deferred Implementation Plan

Wait for a Ghostty stable release whose AppleScript `terminal` objects expose `tty`.

Then:

- [ ] Extend macOS `ghostty-nav.swift` with target-aware terminal id support.
- [ ] Add `ghostty-nav terminal-id` using `/dev/tty` to `terminal.tty` matching.
- [ ] Add `ghostty-nav serve --socket <path> --terminal-id <id>`.
- [ ] Add OpenClaw `ghostty-nav` shim.
- [ ] Add OpenClaw runtime/state directories.
- [ ] Add `shp` wrapper for interactive OpenClaw SSH.
- [ ] Update `ideo` to call `shp --shpool-session <session> openclaw ...`.
- [ ] Update Neovim Ghostty navigator detection and active marker paths.
- [ ] Add shpool attach prelude/cleanup for active marker reactivation.
- [ ] Validate multiple Ghostty panes connected to OpenClaw simultaneously.
