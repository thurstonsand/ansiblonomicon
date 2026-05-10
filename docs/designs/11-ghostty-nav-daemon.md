# Ghostty Nav Daemon

## Status

Accepted

## Decision Summary

Replace the hot-path `ghostty-nav` AppleScript-per-command binary with a launchd-managed macOS Swift daemon and a portable Go client. The daemon keeps Ghostty control warm and caches caller TTY to Ghostty terminal id mappings, while the Go client preserves the CLI contract locally and can later run on OpenClaw over an SSH-forwarded Unix socket.

## Problem Statement

Local Neovim uses Ghostty key tables to reproduce `vim-tmux-navigator`-style `Ctrl-h/j/k/l` movement across Neovim windows and Ghostty splits. At a Neovim edge, `ghostty-nav move <direction>` currently spawns a Swift binary, compiles/evaluates AppleScript, and waits for Ghostty on every keypress.

That path is reliable enough for occasional commands but too expensive for an editor navigation hot path. The keypress should feel like an immediate focus transition, not a subprocess and AppleScript round trip.

## Goals

- Reduce latency for `ghostty-nav move <direction>` from Neovim edge navigation.
- Preserve the existing `ghostty-nav` CLI contract for shell helpers and Neovim config.
- Keep deployment owned by the existing Ansible `ghostty_nav` role.
- Make the client portable enough to reuse later from OpenClaw/Linux.
- Allow a manual, pre-deploy copy of the current installed binary as `ghostty-nav-oneshot` for quick comparison.
- Do not reference, build, or maintain the one-shot binary in Ansible.
- Keep the design compatible with future Ghostty AppleScript `terminal.tty` support.

## Non-Goals

- Do not switch Ghostty to tip/nightly as part of this work.
- Do not implement the remote SSH/OpenClaw bridge from `docs/designs/12-ghostty-ssh-nvim-bridge.md`.
- Do not make `title` daemon-backed; it writes OSC title bytes to the caller's TTY and remains client-local.
- Do not build a formal benchmark harness in the first version; use ad hoc shell comparisons.
- Do not introduce SwiftPM for the daemon unless Network.framework proves insufficient.

## Design Decisions

### 1. Use a launchd-managed Swift daemon

Ansible will build and install `ghostty-navd` and a user LaunchAgent. The LaunchAgent uses `RunAtLoad=true` and `KeepAlive=true`; the daemon creates and owns its Unix socket.

The daemon must be Swift/macOS-native because it controls Ghostty through AppleScript/AppKit. It should be built from a dedicated source folder with a `justfile`, but without SwiftPM packages.

Launchd socket activation is deferred because it adds plist and inherited-file-descriptor complexity without much value when the daemon is already kept alive.

### 2. Use Network.framework for the daemon socket server

The daemon will listen on a Unix domain socket using Network.framework rather than raw BSD sockets. This removes direct `socket`, `bind`, `listen`, `accept`, `send`, `recv`, `sockaddr_un`, and `setsockopt` handling from the code.

The verified setup shape is:

```swift
let params = NWParameters()
params.defaultProtocolStack.transportProtocol = NWProtocolTCP.Options()
params.requiredLocalEndpoint = NWEndpoint.unix(path: socketPath)
params.allowLocalEndpointReuse = true

let listener = try NWListener(using: params)
listener.newConnectionHandler = { connection in
  connection.start(queue: queue)
}
listener.start(queue: queue)
```

Apple Developer Forums examples use the same `NWEndpoint.unix(path:)` shape. They note that noisy Network.framework logs for Unix sockets can be benign, and that Unix socket paths must remain short enough for platform limits. The chosen path is short and home-local:

```text
~/.local/run/ghostty-nav/ghostty-navd.sock
```

### 3. Keep `ghostty-nav` as a portable Go client

The user-facing command remains `ghostty-nav`, but it becomes a Go client. The daemon remains macOS-only; the client should be portable to Linux for future OpenClaw use.

The Go client will use the same structure as the existing `shp` tool:

- `go.mod`
- `go.sum`
- `.golangci.yml`
- `justfile`
- dependency upgrade stamp and checksum-driven Ansible rebuild

The client should use Cobra for CLI parsing and the Go standard library for Unix sockets, JSON, environment variables, TTY discovery, and OSC title output. Do not add Viper; there is no config file.

Before this migration is deployed, the current installed binary may be manually copied once to `~/.local/bin/ghostty-nav-oneshot` for local performance comparison. That copy is an operator action, not an Ansible-managed artifact.

### 4. Use an explicit cross-language JSON protocol

The client and daemon are no longer written in the same language, so the wire format should be a boring, explicit JSON object rather than Swift's synthesized enum `Codable` shape.

Each request is newline-delimited JSON with a discriminator plus command-specific fields. The implementation still uses one concrete type per command: the decoder reads the small envelope first, switches on `command`, then decodes the payload into the matching request type.

```json
{"command":"move","reply":false,"tty":"/dev/ttys016","direction":"right"}
```

Examples:

```json
{"command":"ping","reply":true}
{"command":"activate","reply":false,"tty":"/dev/ttys016","table":"nvim"}
{"command":"clear-cache","reply":true,"tty":"/dev/ttys016"}
{"command":"clear-cache","reply":true}
{"command":"resize","reply":true,"tty":"/dev/ttys016","direction":"right","amount":{"percent":15}}
{"command":"resize","reply":true,"tty":"/dev/ttys016","direction":"right","amount":{"pixels":120}}
```

Responses use the presence of `error` to indicate failure:

```json
{"value":"pong"}
{"error":"..."}
```

This keeps the wire format readable for shell tools and future SSH shims while preserving typed per-command request handling in Go and Swift. `amount` is a one-key sum type: exactly one of `pixels` or `percent` should be present.

### 5. Use a TTY-first command identity

The Go client discovers its own controlling TTY for terminal-scoped commands. Most callers continue using the current shape:

```sh
ghostty-nav move right
ghostty-nav activate nvim
ghostty-nav deactivate
```

The client sends the caller TTY to the daemon. `--tty <path>` remains available for tests and debugging, but normal interactive callers do not need it.

The daemon owns an in-memory cache:

```text
TTY path -> Ghostty terminal id
```

On cache hit, the daemon targets Ghostty directly by terminal id:

```applescript
tell application "Ghostty"
  set t to terminal id "..."
  perform action "goto_split:right" on t
end tell
```

Ghostty supports direct `terminal id "..."` lookup through its AppleScript unique-id object lookup, so no terminal enumeration is required on cache hits.

### 6. Allow focused-terminal bootstrap on cache miss

Until stable Ghostty exposes `terminal.tty`, the daemon cannot independently map a caller TTY to a Ghostty terminal. The first implementation assumes usage is interactive: the terminal that calls `ghostty-nav` is also the focused Ghostty terminal.

On cache miss, the daemon asks Ghostty for the focused terminal id, caches it for the caller TTY, then executes the command against that id.

This is intentionally a compatibility bootstrap. It is not correct for delayed/background automation. That tradeoff is accepted because this tool is for interactive Ghostty/Neovim navigation.

When stable Ghostty exposes `terminal.tty`, the cache-miss path should change to query Ghostty for the terminal whose `tty` matches the caller TTY. The public command semantics do not need to change.

### 7. Keep remote compatibility at the protocol boundary

The local client currently relies on `/dev/tty` to identify the terminal that invoked `ghostty-nav`. Over SSH, `/dev/tty` would refer to the remote PTY, not the local Ghostty surface. That is a bridge problem for `docs/designs/12-ghostty-ssh-nvim-bridge.md`, not a reason to make the local daemon remote-aware now.

The client should support `GHOSTTY_NAV_SOCKET` as the socket path override. It should also support `GHOSTTY_NAV_TTY` as a first-class TTY override after `--tty` and before probing `/dev/tty`. A future SSH wrapper can set the socket variable to a remote-forwarded Unix socket and set the TTY variable when the caller cannot expose a useful controlling terminal directly.

No glaring daemon protocol change is needed for this future path: the protocol already accepts explicit TTY strings and talks over a Unix socket.

### 8. Add `clear-cache` as the operator escape hatch

The client will expose:

```sh
ghostty-nav clear-cache
ghostty-nav --tty /dev/ttys016 clear-cache
ghostty-nav clear-cache --all
```

Without arguments, `clear-cache` removes the mapping for the caller TTY. In the wire protocol, `clear-cache` without a `tty` clears all entries; the CLI exposes that as `clear-cache --all`. This handles misbinding after unusual focus behavior or long-lived stale daemon state.

Cache entries expire after 12 hours. Independently, if a Ghostty action fails because the cached terminal id is no longer valid, the daemon deletes that mapping immediately.

### 9. Let the client choose response behavior within command constraints

Commands that return values must wait for a response:

- `terminal-id`
- `tab-terminal-count`
- `ping`

Commands that do not return values may be sent fire-and-forget by default to minimize latency:

- `move`
- `activate`
- `deactivate`
- `split`
- `resize`
- `toggle-zoom`
- `clear-cache`

The client may request an acknowledgement for non-returning commands when a shell workflow needs certainty, for example `split` during `ide` setup. The public CLI supports this with `--wait`. The wait policy is encoded as `reply: true|false` in the JSON request; the daemon writes a response only when `reply` is true.

### 10. Keep `title` client-local

`ghostty-nav title <text>` continues to write OSC 2 to the caller's controlling TTY. The daemon does not own the caller terminal, so daemon-backed title changes would be semantically different.

## Edge Cases & Failure Modes

- **Cache miss while another Ghostty surface is focused:** The daemon may bind the caller TTY to the wrong terminal id. This is accepted for interactive use but can be corrected with `ghostty-nav clear-cache`.
- **Ghostty terminal id no longer exists:** The daemon logs the command, TTY, relevant arguments, and error; then it deletes the stale TTY mapping. If `reply` was true, the daemon returns an error response.
- **Daemon crashes:** Launchd restarts it. The in-memory cache is lost; the next interactive command repopulates from the focused terminal.
- **Socket file remains after crash:** On startup, the daemon removes the stale socket path before binding/listening.
- **Socket path too long:** Unix domain sockets have platform path length limits. Keep the socket under `~/.local/run/ghostty-nav/`; do not move it under a long sandbox/container path.
- **Concurrent clients:** Each connection carries exactly one request. The daemon handles accepted connections independently, so a waiting client receives only its own response.
- **Nvim exits badly:** Manual recovery remains available with `ghostty-nav deactivate`. The simplified Neovim integration does not keep sentinel state.
- **Caller has no controlling TTY:** Terminal-scoped commands fail unless `--tty` is supplied. This is acceptable because the supported local use is interactive.

## Rejected Alternatives

### Keep single-shot AppleScript binary only

This preserves simplicity but keeps process startup and AppleScript evaluation in the keypress hot path.

### One daemon per Ghostty terminal

This avoids a TTY cache but creates unnecessary process/socket proliferation. A single stateless command executor with a TTY mapping is more useful for shell helpers such as `ide` and `ideo`.

### Daemon accepts omitted identity and always uses focused terminal

This repeats the original wrong-surface failure mode inside a long-lived process. The daemon protocol should receive a caller TTY, even if the current stable implementation must use focused terminal only to populate the cache.

### Swift client

A Swift client works locally, but it cannot be reused on OpenClaw/Linux without bringing Swift to the remote host. A Go client is a better portability boundary while the daemon remains macOS Swift.

### SwiftNIO for the daemon

SwiftNIO is cross-platform and powerful, but it would introduce SwiftPM and a larger dependency stack to solve a local macOS Unix socket listener. Network.framework is native and sufficient for the daemon.

### Launchd socket activation

Launchd-owned sockets would avoid stale socket files and support on-demand startup, but require more complex plist and daemon fd handling. `RunAtLoad` plus `KeepAlive` is simpler and matches the goal of a warm hot-path daemon.

### Direct Lua socket writes as the first implementation

Writing to the daemon socket directly from Neovim may be faster than spawning the client, but it fragments the command contract. First build the daemon-backed CLI, then compare against a Lua-direct path if client startup remains measurable.

## Integration Points

- `ansible/roles/ghostty_nav/files/ghostty-navd`: Swift daemon source, SwiftFormat/SwiftLint configuration, and `justfile`.
- `ansible/roles/ghostty_nav/files/ghostty-nav`: Go client source, `go.mod`, `.golangci.yml`, and `justfile`.
- `ansible/roles/ghostty_nav`: Builds the Go client and Swift daemon, installs the LaunchAgent, updates Go dependencies on the same cadence as `shp`, and reloads the daemon after changes.
- `chezmoi/dot_config/nvim/lua/lib/ghostty-nav.lua`: Keeps current command contract and relies on caller TTY identity handled by the Go client.
- `chezmoi/dot_local/bin/executable_ghostty-ide`: Continues using `ghostty-nav split`, `resize`, and `toggle-zoom`.
- `chezmoi/dot_local/bin/executable_ideo`: Continues using `ghostty-nav` layout commands.
- `chezmoi/dot_zshrc.tmpl`: Existing `ghostty-nav title` callers continue to work client-side.
- `docs/designs/12-ghostty-ssh-nvim-bridge.md`: Remains deferred; future remote bridge can reuse the Go client over an SSH-forwarded Unix socket after stable `terminal.tty` exists or after a bridge identity mechanism is designed.

## Implementation Plan

- [ ] Phase 1: Restructure role source layout
  - Goal: Separate the macOS daemon and portable client into independently built source roots.
  - Files: `ansible/roles/ghostty_nav/files/ghostty-navd/`, `ansible/roles/ghostty_nav/files/ghostty-nav/`.
  - Work:
    - Move Swift daemon code under `files/ghostty-navd/Sources/`.
    - Add a Swift daemon `justfile`.
    - Add a Go client module under `files/ghostty-nav/` modeled after `ansible/roles/shp/files/shp`.
    - Remove the shared Swift client/server source concept.
  - Validation:
    - `just build` works in each source root.

- [ ] Phase 2: Implement explicit JSON protocol in both languages
  - Goal: Replace Swift enum `Codable` IPC with stable cross-language JSON.
  - Files: Swift daemon protocol source; Go client protocol package.
  - Work:
    - Implement one concrete request type per command: `ping`, `terminal-id`, `tab-terminal-count`, `clear-cache`, `activate`, `deactivate`, `move`, `split`, `resize`, `toggle-zoom`.
    - Decode the envelope first, then decode the same payload into the selected concrete request type.
    - Use one-key resize amounts: `amount: {"pixels": N}` or `amount: {"percent": N}`.
    - Implement response fields: `value` and `error`; `error` presence indicates failure.
    - Keep one newline-delimited JSON request per connection.
  - Validation:
    - Manual `ghostty-nav ping` returns `pong`.
    - Malformed or unsupported commands produce useful error logs and responses when `reply` is true.

- [ ] Phase 3: Rewrite daemon socket handling with Network.framework
  - Goal: Replace raw BSD socket handling with `NWListener` and `NWConnection`.
  - Files: Swift daemon network/server source.
  - Work:
    - Bind `~/.local/run/ghostty-nav/ghostty-navd.sock` using `NWEndpoint.unix(path:)`.
    - Remove stale socket path on startup.
    - Receive one newline-delimited request per connection.
    - Send a response only when `reply` is true.
    - Keep lifecycle and failure logs in `~/.local/state/ghostty-nav/ghostty-navd.log`.
    - Truncate the daemon log when it exceeds the configured size cap.
  - Validation:
    - Launch daemon manually and through launchd.
    - Confirm concurrent `ping` calls get correct responses.
    - Confirm no raw BSD socket code remains.

- [ ] Phase 4: Implement Go `ghostty-nav` client
  - Goal: Replace public `ghostty-nav` with a portable Go client while preserving command syntax.
  - Files: `ansible/roles/ghostty_nav/files/ghostty-nav/`.
  - Work:
    - Use Cobra for CLI parsing.
    - Implement `GHOSTTY_NAV_SOCKET` override with default `~/.local/run/ghostty-nav/ghostty-navd.sock`.
    - Implement TTY precedence: `--tty`, then `GHOSTTY_NAV_TTY`, then automatic `/dev/tty` discovery.
    - Resolve caller TTY automatically for terminal-scoped commands; support explicit `--tty`.
    - Implement commands: `activate`, `deactivate`, `move`, `terminal-id`, `tab-terminal-count`, `split`, `resize`, `toggle-zoom`, `clear-cache`, `title`, `ping`.
    - Keep `title` client-local via OSC 2.
    - Use `--wait` to force acknowledgement for non-returning commands.
  - Validation:
    - Existing shell workflows still work: `ide`, `ghostty-ide`, and `ideo` layout commands.
    - Neovim navigation still activates/deactivates and moves Ghostty splits.

- [ ] Phase 5: Update Ansible deployment
  - Goal: Build/install the Go client and Swift daemon with role-owned dependency/update behavior.
  - Files: `ansible/roles/ghostty_nav/defaults/main.yml`, `tasks/main.yml`, `handlers/main.yml`, LaunchAgent template.
  - Work:
    - Mirror the `shp` role's Go dependency upgrade stamp pattern for `ghostty-nav`.
    - Build the Go client from `files/ghostty-nav`.
    - Build the Swift daemon via `just` from `files/ghostty-navd`.
    - Install SwiftFormat and SwiftLint through the macOS and work Homebrew bundles.
    - Do not reference or manage `ghostty-nav-oneshot`; any old binary copy is manual and outside Ansible.
    - Install `house.thurstons.ghostty-navd.plist`.
    - Use `community.general.launchd` to enable/start/reload the agent when binaries or plist change.
  - Validation:
    - `uv run poe laptop --tags ghostty-nav --check` passes where possible.
    - `uv run poe laptop --tags ghostty-nav` installs and starts daemon.
    - `launchctl print gui/$UID/house.thurstons.ghostty-navd` shows running service.
    - `cd ansible && ansible-lint roles/ghostty_nav` passes.
    - `uv run poe lint:cli-tools` runs `just check` for `shp`, the Go client, and the Swift daemon.

- [ ] Phase 6: Simplify Neovim integration
  - Goal: Keep Nvim integration declarative and stateless.
  - Files: `chezmoi/dot_config/nvim/lua/lib/ghostty-nav.lua`.
  - Work:
    - Remove explicit `terminal-id` caching.
    - Remove local key-table state tracking and stale-exit sentinel behavior.
    - Send `ghostty-nav activate nvim` unconditionally on `VimEnter`, `VimResume`, and `FocusGained`.
    - Send `ghostty-nav deactivate` on `VimSuspend` and `VimLeavePre`.
  - Validation:
    - Headless Lua load succeeds.
    - Manual Ghostty/Nvim split navigation works.
    - Manual recovery remains possible through `ghostty-nav deactivate` or the existing Ghostty keybinding.

- [ ] Phase 7: Compare performance ad hoc
  - Goal: Verify the daemon path improves the hot path before considering Lua-direct socket writes or raw AppleEvents.
  - Files: none required; optional scratch commands in notes.
  - Work:
    - Compare repeated `ghostty-nav-oneshot move right` against daemon-backed `ghostty-nav move right` where safe.
    - Measure socket/client overhead separately with `ghostty-nav ping`.
    - Observe perceived Neovim edge navigation latency.
  - Validation:
    - Record rough numbers in the implementation report.
    - If client startup remains significant, plan a follow-up experiment for direct Lua socket writes.
    - If daemon-side AppleScript remains significant, plan a follow-up experiment for raw AppleEvents.
