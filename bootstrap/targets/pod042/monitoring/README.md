# Storage job monitoring

`mise pod042 monitoring` resolves the pod042 secret set, reconciles the three declared Healthchecks checks, then passes their scoped ping URLs to native bootstrap secret resources. Only the ping URLs persist, under `/etc/alerting/checks` with root ownership and mode 0600. The Healthchecks management key does not reach bootstrap or runtime jobs.

The heartbeat runs at boot and every fifteen minutes. It checks both SMART and ZED services independently; either failure marks the heartbeat failed. Its timer uses America/Los_Angeles, matching the host and check declarations.

Scrubs retain Debian's `zfs-scrub@.service` command, monthly calendar, persistent timers, and randomized delay. A drop-in adds start/result notifications. The root-run helper reads the named check's private file directly, so a missing notification credential cannot block the scrub. `LoadCredential` is intentionally not used: its credential directory is unavailable in `ExecStopPost` on this host. Systemd ignores notification-hook failure so the producer's exit status remains authoritative. The finish hook checks both the process result and actual ZFS scan state through the same health predicate as ZED; paused, incomplete, repaired, or errored scans are not reported as success. The shared module lives in Debian 13's standard local Python 3.13 site-packages directory. A final native hook reloads systemd without restarting idle timers, because mise only reloads when it plans a service action. Ark's three-day grace covers the observed 45-hour scrub; black-box allows two hours for the packaged timer's one-hour jitter and its much shorter scrub.

A new scrub check remains unarmed until the first actual scrub sends a ping. Initial scrubs are explicit commissioning operations, not an every-reconciliation hook. Never fake a successful scrub to arm a check.

SMART self-tests run through smartd 7.5, not custom timers. Daily shorts and monthly longs are staggered across the eight explicit devices; the long test supersedes that day's short. Smartd reports failures through Hark, and the host heartbeat detects a stopped smartd. Self-test schedules use the host's timezone. No device scan or removable KVM storage enters the schedule.

`POD042_SSH_CONTROL_PATH` lets the deployment driver reuse a previously authenticated OpenSSH control connection. Set `POD042_SSH_IDENTITY_AGENT=none` for unattended runs that must not prompt 1Password. Socket paths are session state, not repository configuration.
