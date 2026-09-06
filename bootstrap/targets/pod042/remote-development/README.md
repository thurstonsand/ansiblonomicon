# pod042 remote development

These are normal-user services for `thurstonsand`. T3 serves multiple projects from the operator's home and has no runtime dependency on this checkout. Only Amp is rooted at `/home/thurstonsand/code/ansiblonomicon`. Neither service needs an inbound firewall rule or router port forward. T3 Connect uses its managed relay; Amp connects outbound.

## Integration contract

Mise supplies Node LTS. T3 installs through that Node's npm; its CLI and Node resolve through `/home/thurstonsand/.local/share/mise/shims/{node,t3}`. Amp uses its official installer and `/home/thurstonsand/.amp/bin/amp`. Codex and Claude use their official installers under `~/.local/bin`; OpenCode uses `~/.opencode/bin`. Native agent directories precede mise shims so old version-manager installations cannot shadow them. T3 pins its own service runtime and Node executable.

Native files own the Amp unit and one T3 drop-in, not the vendor's `t3code.service` or launcher. Register this config environment after operator tooling. Its final hook runs `python3 remote-development/services.py apply` after operator installation without replacing the base bootstrap task. Native dry runs report the files; use the separate `plan` action to inspect vendor-managed service state. Named `remote-development:{reconcile,status,plan}` tasks are also provided. Paths in these tasks are relative to the target config root.

Enrollment must happen before enabling automatic reconciliation: missing T3 enrollment or Amp login state fails instead of claiming completion. Applying native files alone does not enable either service. Do not run the service CLI or helper with sudo. Only `loginctl enable-linger thurstonsand` receives privilege; the helper performs this after its user, hostname, and enrollment guards.

## Initial human enrollment

In an interactive SSH login as `thurstonsand` on pod042:

```sh
export PATH="$HOME/.local/bin:$HOME/.amp/bin:$HOME/.opencode/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin"
export T3CODE_HOME="$HOME/.local/share/t3code"
cd /home/thurstonsand/code/ansiblonomicon
amp login
```

Complete Amp sign-in through its printed browser instructions. No credential copying is required. The unit requires Amp's `$HOME/.local/share/amp/secrets.json` to exist. This is a necessary persisted-login guard, not proof that its token remains valid. If the installed Amp release uses a different credential backend, stop and adapt this guard rather than creating an empty secrets file.

```sh
t3 connect --headless
```

Complete T3's printed out-of-band login instructions. If it offers background installation, it is safe to defer it to reconciliation. `t3 connect --headless` enrolls the environment; it is not a server command. Use the same `T3CODE_HOME` for every enrollment and service-management command.

Once the native files have deployed:

```sh
cd /home/thurstonsand/code/ansiblonomicon/bootstrap/targets/pod042
python3 remote-development/services.py apply
python3 remote-development/services.py status
```

Verify T3 appears online in the T3 client, then open an Amp remote terminal on runner `pod042-ansiblonomicon`. Test again after closing SSH and after a reboot. A systemd active state does not prove either authenticated relay is usable. Inspect failures with `journalctl --user -u amp-remote.service -u t3code.service`; T3's vendor status also prints its application log path.

## Vendor lifecycle evidence

Upstream source inspected 2026-09-06:

- [Background service docs](https://github.com/pingdotgg/t3code/blob/main/docs/user/background-service.md): `t3 service install`, `status`, `update`, and `uninstall`; Linux requires user systemd and linger.
- [CLI service implementation](https://github.com/pingdotgg/t3code/blob/main/apps/server/src/cli/service.ts): install and update call the same reconciliation function. It returns unchanged when `installed && current`, so repeated install is idempotent. It refuses downgrades and checks pending updates. Status is human-readable and does **not** exit nonzero just because a service is absent; the helper separately checks systemd.
- [Boot service implementation](https://github.com/pingdotgg/t3code/blob/main/apps/server/src/cloud/bootService.ts): vendor writes `~/.config/systemd/user/t3code.service`, uses a pinned foreground launcher under `$T3CODE_HOME/runtime`, and tracks runtime/unit drift. It retains ownership of that lifecycle. Deliberate updates use `t3 service update` after upgrading the CLI through npm; finish active work first.
- [Connect implementation](https://github.com/pingdotgg/t3code/blob/main/apps/server/src/cli/connect.ts): `t3 connect status --json` exposes `desired`, `authenticated`, and `linked` booleans. The helper requires `desired` and `authenticated` before starting the service. A newly enrolled host can still have `linked = false` until its server starts, so requiring it before startup would prevent the first connection. Check linking and live reachability after startup. The vendor service owns ongoing connection management after enrollment.
- [Amp CLI docs](https://ampcode.com/docs/cli): launch `amp` interactively for initial use. The requested service command is exactly `amp --no-tui --remote-control-terminal --runner-id pod042-ansiblonomicon`.

Local validation covers TOML parsing, Python compilation, and a real wrong-host rejection. No live service or credential was touched. Enrollment, Linux unit validation, reboot persistence, and real remote sessions remain deployment checks.
