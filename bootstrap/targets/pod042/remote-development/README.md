# pod042 remote development

These are normal-user services for `thurstonsand`. T3 serves multiple projects from the operator's home and has no runtime dependency on this checkout. Amp is rooted at `/home/thurstonsand/code` and discovers every Git checkout up to two levels beneath it, so a new clone becomes a servable directory without touching the unit. Herdr runs from the operator's home and is reached by attaching a client over SSH. None of the three needs an inbound firewall rule or router port forward. T3 Connect uses its managed relay; Amp connects outbound; Herdr listens only on a unix socket in `~/.config/herdr/`.

## Integration contract

Mise supplies Node LTS. T3 uses its official standalone archive installer, with `~/.local/bin/t3` linked into `~/.t3/runtime/versions/`; `services.py` calls that native launcher directly. `operator:agents` reconciles the latest stable release; this capability reconciles its service afterward. The archive path avoids npm pruning the platform bundle on repeated installs and retains the existing Connect state in `~/.t3`. Amp uses its official installer and `/home/thurstonsand/.amp/bin/amp`. Codex and Claude use their official installers under `~/.local/bin`; OpenCode uses `~/.opencode/bin`. Native agent directories precede mise shims so old version-manager installations cannot shadow them.

Native dotfiles own the Amp and Herdr units and one T3 drop-in, not the vendor's `t3code.service` or launcher. The service-critical units are copies so the user manager remains independent of checkout availability; T3's npmrc links to its first-party source. Register this config environment after operator tooling. Its final hook runs `python3 remote-development/services.py apply` after operator installation without replacing the base bootstrap task. Native dry runs report the files; use the separate `plan` action to inspect vendor-managed service state. Named `remote-development:{reconcile,status,plan}` tasks are also provided. Paths in these tasks are relative to the target config root.

Enrollment must happen before enabling automatic reconciliation: missing T3 enrollment or Amp login state fails instead of claiming completion. Applying native files alone does not enable any of the services. Herdr needs no enrollment, only its shim from the operator config. Do not run the service CLI or helper with sudo. Only `loginctl enable-linger thurstonsand` receives privilege; the helper performs this after its user, hostname, and enrollment guards.

## Runtime prerequisites

Debian `polkitd` supplies the stock authorization policy for a user's own linger request, which T3's installer makes even when linger is already enabled. No custom privilege rule or root T3 process is needed.

Herdr is the reason the unit exists rather than the convenience of a boot start. A `herdr` client that finds no live socket spawns its own server, which inherits the SSH login's kernel session keyring. `pam_keyinit` revokes that keyring at logout while the server keeps running, so agents inside its panes lose every secret held there. On this host that is pi's MCP OAuth store, which has no Secret Service to fall back to. Under the user manager the server gets a keyring that outlives logins, and `keyutils` from the operator config gives pi's recovery path a way back to a revoked one.

That only holds while systemd owns the socket, so the unit sets `Restart=always` and `services.py` stops any server it does not own before starting the unit. Both cost the running panes. Stop the server for real with `systemctl --user stop herdr.service`, never `herdr server stop`, which the restart undoes ten seconds later. Herdr's own `herdr update` is equally unwelcome: mise owns the binary, so upgrade through `operator:tools` and let reconciliation notice `server_binary_stale` and restart the unit.

T3 alone selects `~/.config/t3code/npmrc` through `NPM_CONFIG_USERCONFIG`. Its `allow-scripts=node-pty` permission lets npm 12 build the native terminal module in vendor-managed runtime installs and updates. Project-scoped npm installs reject the equivalent CLI/environment allowlist; other npm consumers keep their own policy. A runtime installed before this permission needs a one-time `npm --prefix <runtime> rebuild node-pty` with this config selected, followed by a real PTY test. The CLI prefix carries its own built copy, which does not validate the vendor runtime's separate one.

## Initial human enrollment

In an interactive SSH login as `thurstonsand` on pod042:

```sh
export PATH="$HOME/.local/bin:$HOME/.amp/bin:$HOME/.opencode/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin"
cd /home/thurstonsand/code
amp login
```

Complete Amp sign-in through its printed browser instructions. No credential copying is required. The unit requires Amp's `$HOME/.local/share/amp/secrets.json` to exist. This is a necessary persisted-login guard, not proof that its token remains valid. If the installed Amp release uses a different credential backend, stop and adapt this guard rather than creating an empty secrets file.

```sh
t3 connect --headless
```

Complete T3's printed out-of-band login instructions. If it offers background installation, it is safe to defer it to reconciliation. `t3 connect --headless` enrolls the environment; it is not a server command. T3's home is its own default, `~/.t3`, so no environment variable has to be carried into enrollment, service management, or a human's shell.

Once the native files have deployed:

```sh
cd /home/thurstonsand/code/ansiblonomicon/bootstrap/targets/pod042
python3 remote-development/services.py apply
python3 remote-development/services.py status
```

Verify T3 appears online in the T3 client, then open an Amp remote terminal on runner `pod042` and confirm `amp runner dirs list` names every checkout under `~/code`. Test again after closing SSH and after a reboot. A systemd active state does not prove either authenticated relay is usable. Inspect failures with `journalctl --user -u amp-remote.service -u t3code.service`; T3's vendor status also prints its application log path.

## Vendor lifecycle evidence

Upstream source inspected 2026-09-06:

- [Background service docs](https://github.com/pingdotgg/t3code/blob/main/docs/user/background-service.md): `t3 service install`, `status`, `update`, and `uninstall`; Linux requires user systemd and linger.
- [CLI service implementation](https://github.com/pingdotgg/t3code/blob/main/apps/server/src/cli/service.ts): install and update call the same reconciliation function. It returns unchanged when `installed && current`, so repeated install is idempotent. It refuses downgrades and checks pending updates. Status is human-readable and does **not** exit nonzero just because a service is absent; the helper separately checks systemd.
- [Boot service implementation](https://github.com/pingdotgg/t3code/blob/main/apps/server/src/cloud/bootService.ts): vendor writes `~/.config/systemd/user/t3code.service`, uses a pinned foreground launcher under `$T3CODE_HOME/runtime`, and tracks runtime/unit drift. It retains ownership of that lifecycle. Deliberate updates use `t3 service update` after upgrading the CLI through npm; finish active work first.
- [Connect implementation](https://github.com/pingdotgg/t3code/blob/main/apps/server/src/cli/connect.ts): `t3 connect status --json` exposes `desired`, `authenticated`, and `linked` booleans. The helper requires `desired` and `authenticated` before starting the service. A newly enrolled host can still have `linked = false` until its server starts, so requiring it before startup would prevent the first connection. Check linking and live reachability after startup. The vendor service owns ongoing connection management after enrollment.
- [Amp CLI docs](https://ampcode.com/docs/cli): launch `amp` interactively for initial use. The service command is `amp --no-tui --remote-control-terminal --discover-dirs --runner-id pod042`.
- [One runner is now enough — 2026-09-17](https://ampcode.com/news/one-runner-is-now-enough): one runner serves many directories. `--discover-dirs` serves every Git checkout up to two levels beneath the working directory and picks up new clones; `amp runner dirs add|remove|list` changes the set on a live runner, and additions survive a restart from the same location. Verified on 0.0.1789646488-g024bbd: neither flag appears in `amp --help`, but unknown flags are rejected and these are not, and a probe run from `~/code` listed the three checkouts there.
- The same release makes `amp --no-tui` self-updating (`amp.runner.autoUpdate.enabled`, default on): it installs a new CLI hourly and restarts into it once no thread is running, at most once every 12 hours. `operator:agents` installs Amp only when absent, so this is now the mechanism that keeps the binary current, and it upgrades the interactive CLI along with the runner because both are the same file.

Herdr 0.9.0 inspected 2026-09-11. It documents no unit file and ships no `sd_notify`, so the unit rests on observed behavior instead: `herdr server` runs the server in the foreground and refuses a second one while the socket is live, `SIGTERM` exits 0 in well under a second and removes the socket, and `herdr status server --json` exits 0 either way with `running`, `restart_needed`, and `server_binary_stale`. The binary advertises `detached_server_daemon` and spawns exactly that from `src/server/autodetect.rs` when a client finds no server, which is the behavior the unit is racing.

Local validation covers TOML parsing, Python compilation, and a real wrong-host rejection. Enrollment, Linux unit validation, reboot persistence, and real remote sessions remain deployment checks.

Herdr was deployed and validated on pod042 on 2026-09-11: the unit runs under `user@1000.service`, restored its saved workspaces, and a process in one of its panes both read and wrote the pi MCP keyring entries that the previous SSH-spawned server could not reach. A second `services.py apply` left `MainPID` and `NRestarts` untouched. Reboot persistence is still unverified.
