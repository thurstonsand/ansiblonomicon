# T3 Code

This capability owns T3 Code on pod042 and pod153: the release, every server, and the checks that a server is up and enrolled. Each server is a plain `t3 serve` that mise declares, so a host can run as many as it needs. T3's own `t3 service` writes a single hard-coded `t3code` unit, so it could only ever run one, and the capability uninstalls it once on each host. That keeps `~/.t3` intact.

## Adding a server

Each target lists its servers in `mise.t3-instances.toml`. A server is named `t3code-<person>` and sets `T3CODE_HOME`, which is the only key the capability reads:

```toml
[bootstrap.linux.systemd.units.t3code-maggie]
description = "T3 Code server for Maggie, rooted at ~/code/maggie"
exec_start = "~/.local/bin/t3 serve --host 127.0.0.1 --port 3774"
working_directory = "~/code/maggie"
environment = { T3CODE_HOME = "/home/thurstonsand/.t3-maggie" }
```

On pod042 the `t3-systemd` overlay installs a prefix drop-in, `dev.mise.t3code-.service.d/server.conf`, which systemd applies to every `dev.mise.t3code-*.service`. It holds `PATH`, `NPM_CONFIG_USERCONFIG`, `Restart=always` every 30 seconds with no start limit, and the process and memory settings T3's own unit set, so the server outranks its agents under pressure. On pod153 launchd has no shared settings, so each agent repeats `keep_alive`, `throttle_interval = 5`, `process_type = "Interactive"`, and a log at `~/Library/Logs/t3code-<person>.log`. mise has no key for `ExitTimeOut`. The `t3-launchd` overlay's `t3-logs` agent copies any of those logs past 10 MB aside to `.log.1` every 10 minutes and empties it in place, the way T3's launcher bounded its own log. Journald bounds pod042's.

The drop-in's `NPM_CONFIG_USERCONFIG` selects `~/.config/t3code/npmrc` for T3 alone. Its `allow-scripts=node-pty` lets npm 12 build the native terminal module when T3 installs provider runtimes; project-scoped npm installs reject the equivalent CLI or environment allowlist, and other npm consumers keep their own policy.

Enroll a new server once with `t3 connect link --headless --base-dir <T3CODE_HOME>`; until then the reconcile fails and names that command.

## How a reconcile runs

`t3.py` does the work:

1. `prepare`, the post-dotfiles hook, installs the latest GitHub release with T3's installer when the linked one differs, and uninstalls the vendor service if its unit is still there. It runs before mise starts the servers, which need the binary and the port.
2. mise writes the units or agents and starts any that changed.
3. `apply`, the final hook, reloads systemd if a unit changed, restarts every server whose recorded version differs from the installed one, then runs `ready`.

`ready` is the one wait every later `t3` command sits behind. A new server migrates its database before it serves, and the CLI refuses that database meanwhile. Once it serves, the server writes `userdata/server-runtime.json` with its pid; it removes the file on a clean stop, and a crash leaves it stale. `ready` therefore waits until the file names the pid that systemd or launchd tracks. It fails with the server's last log lines as soon as that pid changes, which means the server exited, or after 10 minutes. Then it checks enrollment with `t3 connect status --json` for each server's `T3CODE_HOME`. pod042's `remote-development/services.py` calls `ready` too.

T3's launcher rolled a failed update back to a database snapshot. Plain `t3 serve` has no launcher, so a release that cannot start stays broken: `ready` fails the reconcile loudly with the server's own error, and the failure thread takes it from there. T3's in-app self-update and Settings → Reclaim also need the launcher and are unavailable; the daily reconcile updates instead.

Run it with `mise pod042 t3` on pod042 and `mise t3` (or `mise laptop -t t3`) on pod153. `--check` reports a pending install, uninstall, or restart.
