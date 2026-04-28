# Shpool-backed OpenClaw shell persistence

## Problem Statement

OpenClaw needs lightweight, SSH-friendly persistent shell sessions without relying on tmux as the daily remote workspace. The target behavior is tmux-like survival across SSH disconnects while preserving native terminal scrollback, copy/paste, and Ghostty window management.

The deployment must be Ansible-managed, safe for normal machine/batch SSH access, and integrated with the existing Ghostty-oriented local workflow.

## Design Decisions

### 1. Scope OpenClaw first, leave tmux installed

Shpool will be deployed on the OpenClaw Debian VM first. TrueNAS is appliance-like and is not a good initial target. Tmux remains installed because it is already configured and still useful as an escape hatch, but the new daily workflow will use shpool sessions instead.

### 2. Use a user systemd service/socket with linger

Shpool owns user shell sessions, so it should run under the target user rather than as a root/system daemon. The Ansible role will install user units in `~/.config/systemd/user/` and enable linger for the OpenClaw user.

`loginctl enable-linger <user>` allows that user's systemd manager to run without an active login session. This lets the shpool socket and prune timer exist after reboot and while the user is logged out.

The role will set `nodaemonize = true`. This rejects shpool's client-side fallback daemonization and forces the managed systemd path. If systemd is broken, failure should be loud. Silent orphan daemons are unhelpful.

### 3. Keep normal SSH clean for batch access

The existing `Host openclaw` remains a plain SSH target. Ansible, rsync, scp, and scripts should not be routed through shpool. Interactive persistence is invoked explicitly by helper functions that inline the remote `shpool attach` command over `ssh -t`.

### 4. Minimal shpool config

OpenClaw will deploy a small `~/.config/shpool/config.toml`:

```toml
nodaemonize = true
default_dir = "."
session_restore_mode = { lines = 200 }
output_spool_lines = 10000
prompt_prefix = ""

[[keybinding]]
binding = "Ctrl-b d"
action = "detach"
```

Rationale:

- `default_dir = "."` makes explicit attach directories work naturally.
- restoring 200 lines gives useful reconnect context without flooding the terminal.
- keeping 10000 spool lines preserves deeper restoration capacity without replaying it by default.
- `prompt_prefix = ""` avoids fighting starship/zsh prompt styling; `$SHPOOL_SESSION_NAME` remains available.
- `Ctrl-b d` detaches shpool. `Ctrl-d` remains shell EOF and exits the underlying shell session.

No extra `forward_env` entries are configured initially. Shpool already forwards `TERM`, `DISPLAY`, `LANG`, and `SSH_AUTH_SOCK`, starts a login shell, and reads `/etc/environment`. Additional terminal metadata can be added later only if a concrete rendering issue appears.

### 5. Add automatic pruning only for temporary sessions

Native shpool TTL is absolute from creation and does not refresh on reattach. That does not match the desired "idle since last disconnected" semantics.

Instead, OpenClaw will install a user timer that runs every few hours and kills only sessions matching all of these conditions:

- name starts with `tmp-`
- status is disconnected
- `last_disconnected_at_unix_ms` is older than 48 hours

Stable sessions like `edit-ansiblonomicon`, `agent-ansiblonomicon`, `edit-openclaw`, and `agent-openclaw` are never pruned by this timer.

### 6. Ghostty-specific `ideo` local workflow

The local `ideo` helper will be Ghostty-specific and use the existing `ghostty-nav` split machinery.

Initial interface:

```sh
ideo <project> [agent-command...]
```

Supported projects start hard-coded. Unknown or omitted projects fail fast.

- `ansiblonomicon` -> `~/code/ansiblonomicon`
- `openclaw` -> `~/code/openclaw`

The helper opens two stable remote shpool sessions:

- `edit-<project>` in the project directory, creating it with `nvim .` through an interactive zsh login shell
- `agent-<project>` in the project directory, optionally creating it with the provided agent command through an interactive zsh login shell

The helper inlines the SSH command rather than requiring SSH host aliases. `Host openclaw` remains the only SSH target.

## Edge Cases

- **Systemd user bus unavailable:** linger is enabled before user units are started. The role uses the user's runtime directory for user `systemctl` calls.
- **First deployment without shpool installed:** shpool is added to OpenClaw cargo packages and the shpool role runs after language tools.
- **Remote batch access:** unaffected because no `RemoteCommand` is added to the base SSH host.
- **Agent command on existing session:** `shpool attach --cmd` only runs on session creation. Reattaching to an existing `agent-*` session will not restart the agent command. This is desired.
- **Command environment:** shpool `--cmd` does not run through the user's shell by default. `ideo` wraps editor and agent commands in `/usr/bin/zsh -ilc '<command>; exec /usr/bin/zsh -il'` so PATH and shell initialization match an interactive OpenClaw login.
- **Ctrl-D confusion:** `Ctrl-d` exits the shell process and ends the shpool session. Detach is `Ctrl-b d`.
- **Temporary session cleanup:** the prune script only kills disconnected `tmp-*` sessions. Active temporary sessions and named/stable sessions survive.
- **Quoting remote commands:** helper scripts construct shell-quoted remote command strings locally to avoid relying on SSH config aliases.

## Rejected Alternatives

- **System-wide shpool daemon:** rejected because shpool supervises user shells. A root-owned system daemon adds privilege and ownership complexity without value.
- **SSH aliases with `RemoteCommand`:** rejected for the primary `ideo` path because the desired workflow can inline commands and keep SSH config simple.
- **Native `--ttl` for ephemeral cleanup:** rejected because TTL is absolute from creation, not idle since last disconnect.
- **Replacing tmux package/config immediately:** rejected. Shpool is not a multiplexer and tmux remains a useful fallback.

## Integration Points

- `ansible/openclaw.config.yml`: add `shpool` to OpenClaw cargo packages.
- `ansible/playbooks/openclaw.yml`: include the new `shpool` role after language tools.
- `ansible/roles/shpool/`: install config, user systemd units, linger, and tmp-session prune timer.
- `chezmoi/dot_local/bin/executable_ideo`: add Ghostty helper script for the remote split workflow.

## Implementation Plan

- [ ] Add `shpool` to `cargo_packages_extra` in `ansible/openclaw.config.yml`.
- [ ] Create `ansible/roles/shpool/tasks/main.yml`.
- [ ] Add shpool config and user systemd templates.
- [ ] Add `shpool-prune-tmp` script and user timer templates.
- [ ] Include the `shpool` role in `ansible/playbooks/openclaw.yml` after `language_tools`.
- [ ] Add a Ghostty-specific `ideo` helper under `chezmoi/dot_local/bin/`.
- [ ] Run lint/checks relevant to Ansible and shell templates.
