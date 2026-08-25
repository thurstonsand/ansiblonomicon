# Host facts for pod042 — the group_vars/pod042.yml analog. Deploy behaviour
# lives in each deploy's data_defaults; only what is true of this machine lives
# here.

# Alerting endpoints. The secrets arrive from the environment, which is where
# `uv run poe init-secrets` leaves them: the lookup('env', ...) analog, except
# it is just Python. The rig overrides all three with --data.
import os

alerting_healthchecks_api_url = "https://healthchecks.io/api/v3/checks/"
alerting_hark_webhook_url = os.environ.get("HARK_WEBHOOK_URL", "")
alerting_healthchecks_api_key = os.environ.get("HEALTHCHECKS_API_KEY", "")

# ZFS maintenance
zfs_maintenance_scrubs = [
    {
        "pool": "ark",
        "calendar": "*-*-01 04:00:00",
        "healthchecks_schedule": "0 4 1 * *",
        "healthchecks_grace": 86400,
    },
    {
        "pool": "black-box",
        "calendar": "*-*-05 04:00:00",
        "healthchecks_schedule": "0 4 5 * *",
        "healthchecks_grace": 7200,
    },
]

# Only ark carries the hot spare, but autoreplace is right on both.
zfs_maintenance_pools_autoreplace = ["ark"]

# black-box only: ark is deliberately snapshot-free (ticket 08).
zfs_maintenance_sanoid_datasets = [
    {"dataset": "black-box", "template": "production", "recursive": True},
]

# Every operation in this segment writes root-owned system state.
_sudo = True
