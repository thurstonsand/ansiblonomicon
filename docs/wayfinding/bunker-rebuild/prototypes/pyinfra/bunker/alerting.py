"""The alerting role, as a pyinfra deploy.

One channel, one contract: scheduled jobs report to Healthchecks, events POST to
Hark. `DEFAULTS` is the public half of the interface — deploys that install jobs
speaking this contract (zfs_maintenance, restic_backup) merge it into their own
data defaults, which is what `meta/main.yml: dependencies: [alerting]` buys in
Ansible.
"""

from __future__ import annotations

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.server import Hostname
from pyinfra.operations import apt, files, systemd

from bunker.operations import healthchecks_check

DEFAULTS = {
    "alerting_bin_dir": "/usr/local/bin",
    "alerting_state_dir": "/etc/alerting",
    "alerting_hark_webhook_url": None,
    "alerting_healthchecks_api_key": None,
    "alerting_healthchecks_api_url": "https://healthchecks.io/api/v3/checks/",
    "alerting_healthchecks_timezone": "America/New_York",
    "alerting_heartbeat_schedule": "*/15 * * * *",
    "alerting_heartbeat_grace": 900,
    "alerting_heartbeat_calendar": "*:0/15",
}

TEMPLATES = "templates"


def check_name(suffix: str) -> str:
    """Checks are named for the host that owns the job."""
    return f"{host.get_fact(Hostname)}-{suffix}"


@deploy("Register a Healthchecks check", data_defaults=DEFAULTS)
def register_check(check: str, schedule: str, grace: int, install_url: bool = True):
    """The check.yml analog: one check, registered, with its ping URL dropped
    where the job's unit can load it as a systemd credential."""

    # `name` is reserved: it is the global argument that labels an operation or
    # deploy, so the check's own name has to travel under a different key.
    return healthchecks_check(
        name=f"Register Healthchecks check {check}",
        check=check,
        schedule=schedule,
        grace=grace,
        api_url=host.data.alerting_healthchecks_api_url,
        api_key=host.data.alerting_healthchecks_api_key,
        timezone=host.data.alerting_healthchecks_timezone,
        url_file=(
            f"{host.data.alerting_state_dir}/checks/{check}.url"
            if install_url
            else None
        ),
    )


@deploy("Configure alerting", data_defaults=DEFAULTS)
def alerting():
    if (
        not host.data.alerting_hark_webhook_url
        or not host.data.alerting_healthchecks_api_key
    ):
        raise DeployError(
            "alerting_hark_webhook_url and alerting_healthchecks_api_key must be "
            "resolved before configuring alerting. Run `uv run poe init-secrets`."
        )

    state_dir = host.data.alerting_state_dir
    bin_dir = host.data.alerting_bin_dir
    source = host.get_fact(Hostname)
    heartbeat = check_name("heartbeat")

    apt.packages(
        name="Install alerting dependencies",
        packages=["curl", "jq"],
    )

    for directory in (state_dir, f"{state_dir}/checks"):
        files.directory(
            name=f"Ensure {directory} exists",
            path=directory,
            user="root",
            group="root",
            mode="700",
        )

    files.template(
        name="Install the Hark webhook credential",
        src=f"{TEMPLATES}/hark-webhook-url.j2",
        dest=f"{state_dir}/hark-webhook-url",
        user="root",
        group="root",
        mode="600",
        alerting_hark_webhook_url=host.data.alerting_hark_webhook_url,
    )

    for script in ("storage-alert", "hc-run"):
        files.template(
            name=f"Install {script}",
            src=f"{TEMPLATES}/{script}.j2",
            dest=f"{bin_dir}/{script}",
            user="root",
            group="root",
            mode="755",
            alerting_state_dir=state_dir,
            alerting_source=source,
        )

    register_check(
        check=heartbeat,
        schedule=host.data.alerting_heartbeat_schedule,
        grace=host.data.alerting_heartbeat_grace,
    )

    unit_changes = [
        files.template(
            name=f"Install alerting-heartbeat.{suffix}",
            src=f"{TEMPLATES}/alerting-heartbeat.{suffix}.j2",
            dest=f"/etc/systemd/system/alerting-heartbeat.{suffix}",
            user="root",
            group="root",
            mode="644",
            alerting_state_dir=state_dir,
            alerting_bin_dir=bin_dir,
            alerting_heartbeat_check=heartbeat,
            alerting_heartbeat_calendar=host.data.alerting_heartbeat_calendar,
        )
        for suffix in ("service", "timer")
    ]

    # The handler analog. `_if` defers the check to execute time, so it reads
    # what the template operations actually did, not what they looked like
    # before the deploy started.
    systemd.daemon_reload(
        name="Reload systemd for alerting",
        _if=lambda: any(unit.did_change() for unit in unit_changes),
    )

    systemd.service(
        name="Enable the host-alive timer",
        service="alerting-heartbeat.timer",
        running=True,
        enabled=True,
    )
