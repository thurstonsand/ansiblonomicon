# pyinfra reproduction of the alerting + zfs_maintenance segment

Ticket 19's prototype. It reproduces `ansible/roles/alerting` and `ansible/roles/zfs_maintenance` as wired into `ansible/playbooks/pod042.yml`, and converges pod042 to a byte-identical result. Findings live in `../../research/pyinfra-trial.md`.

This is a self-contained uv project. It is deliberately not part of the repo's root `pyproject.toml` and nothing outside this directory depends on it.

## Layout

```
inventory.py                 # pod042 = ["@local"]      (inventory/targets/pod042.yml)
group_data/pod042.py         # host facts, _sudo = True (group_vars/pod042.yml)
bunker/alerting.py           # @deploy alerting         (roles/alerting)
bunker/zfs_maintenance.py    # @deploy sanoid/scrub/smartd/zed (roles/zfs_maintenance)
bunker/operations.py         # custom ops: healthchecks_check, zpool_property
bunker/facts.py              # custom facts: HealthchecksChecks, ZfsPoolProperty
templates/                   # the role templates, unchanged except for three renames
deploy.py                    # the whole segment
parts/*.py                   # one entrypoint per part — the --tags analog
rig/                         # the Lima rig used to measure both tools
```

## Running it

```sh
uv sync
uv run pyinfra inventory.py deploy.py                  # detect changes, then confirm
uv run pyinfra inventory.py deploy.py --dry --diff     # dry run with file diffs
uv run pyinfra inventory.py parts/scrub.py -y          # just the scrub part
uv run pyinfra inventory.py deploy.py \
  --data alerting_healthchecks_api_url=... \
  --data alerting_healthchecks_api_key=... \
  --data alerting_hark_webhook_url=...                 # secrets, as CLI overrides
```

The three alerting endpoints have no defaults worth shipping, so they arrive as data. In the rig they point at a mock; in production they would come from the environment the same way the Ansible role reads them, via `os.environ` in `group_data/pod042.py`.

## Rebuilding the rig

`rig/` recreates the workstream-E gauntlet VM: Lima, arm64 Debian 13, real ZFS, file-backed `ark` and `black-box` pools, and a mock Healthchecks/Hark endpoint on 127.0.0.1:8099.

```sh
brew install lima
cd rig && ./prep.sh                       # build the VM (about two minutes)
limactl shell pod042test sudo -u thurston -i ./bench.sh    # paired timings, both tools
limactl shell pod042test sudo /usr/local/sbin/hammer.sh    # functional checks
limactl delete -f pod042test && brew uninstall lima        # cleanup
```

`reset.sh` returns the VM to a pre-converge state (packages purged, files removed, mock check registry wiped) so the two tools can each be measured from the same starting point.

## Deviations from the Ansible original

Three, all noted in the report:

- `templates/zfs-scrub-pool@.service.j2` takes `hostname` instead of `ansible_facts.hostname`, and `zfs-scrub-pool@.timer.j2` takes `pool`/`calendar` instead of `item.pool`/`item.calendar`. Rendered output is identical.
- `sanoid.conf.j2` needs `jinja_env_kwargs={"trim_blocks": True}` because Ansible sets `trim_blocks` by default and pyinfra does not.
- The smartd unit is enabled under its canonical name `smartmontools.service`. `systemctl enable smartd` fails on Debian ("Refusing to operate on linked unit file"); Ansible's `systemd_service` module resolves the alias, pyinfra passes the name through.
