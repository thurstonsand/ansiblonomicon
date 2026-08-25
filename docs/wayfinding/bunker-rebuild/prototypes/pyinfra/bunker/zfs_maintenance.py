"""The zfs_maintenance role, as pyinfra deploys.

Snapshots, scrubs, SMART tests and ZFS event handling. Everything that has
something to say says it through the alerting deploy — which is why `DEFAULTS`
starts from `alerting.DEFAULTS`. That merge is this prototype's answer to
`meta/main.yml: dependencies: [alerting]`: the paths alerting owns stay in scope
even when only the scrub part of the deploy runs.

Each part is its own `@deploy`, so a partial run is `pyinfra inventory.py
parts/scrub.py` rather than `--tags scrub`.
"""

from __future__ import annotations

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.server import Hostname
from pyinfra.operations import apt, files, systemd

from bunker import alerting
from bunker.alerting import check_name, register_check
from bunker.operations import zpool_property

DEFAULTS = {
    **alerting.DEFAULTS,
    "zfs_maintenance_bin_dir": "/usr/local/bin",
    # Pools absent from this list are deliberately snapshot-free.
    "zfs_maintenance_sanoid_datasets": [],
    "zfs_maintenance_sanoid_template": {
        "frequently": 0,
        "hourly": 24,
        "daily": 7,
        "monthly": 1,
        "yearly": 0,
    },
    "zfs_maintenance_sanoid_schedule": "0 * * * *",
    "zfs_maintenance_sanoid_grace": 1800,
    # One timer per pool, staggered. Each entry needs pool, calendar,
    # healthchecks_schedule and healthchecks_grace.
    "zfs_maintenance_scrubs": [],
    "zfs_maintenance_smart_schedule": "(S/../.././02|L/../01/./03)",
    "zfs_maintenance_smart_temp_limits": "4,45,55",
    "zfs_maintenance_zed_events": [
        "statechange",
        "data",
        "scrub_finish",
        "resilver_finish",
    ],
    "zfs_maintenance_zed_throttle_seconds": 900,
    # `autoreplace` is what makes the hot spare more than decoration.
    "zfs_maintenance_pools_autoreplace": [],
}

TEMPLATES = "templates"


@deploy("Configure sanoid snapshots", data_defaults=DEFAULTS)
def sanoid():
    check = check_name("sanoid")

    apt.packages(name="Install sanoid", packages=["sanoid"])

    # Debian ships sanoid without its config directory.
    files.directory(
        name="Ensure the sanoid config directory exists",
        path="/etc/sanoid",
        user="root",
        group="root",
        mode="755",
    )

    files.template(
        name="Configure sanoid policy",
        src=f"{TEMPLATES}/sanoid.conf.j2",
        dest="/etc/sanoid/sanoid.conf",
        user="root",
        group="root",
        mode="644",
        jinja_env_kwargs={"trim_blocks": True},
        zfs_maintenance_sanoid_datasets=host.data.zfs_maintenance_sanoid_datasets,
        zfs_maintenance_sanoid_template=host.data.zfs_maintenance_sanoid_template,
    )

    register_check(
        check=check,
        schedule=host.data.zfs_maintenance_sanoid_schedule,
        grace=host.data.zfs_maintenance_sanoid_grace,
    )

    files.directory(
        name="Ensure the sanoid drop-in directory exists",
        path="/etc/systemd/system/sanoid.service.d",
        user="root",
        group="root",
        mode="755",
    )

    dropin = files.template(
        name="Report sanoid runs to Healthchecks",
        src=f"{TEMPLATES}/sanoid-healthchecks.conf.j2",
        dest="/etc/systemd/system/sanoid.service.d/10-healthchecks.conf",
        user="root",
        group="root",
        mode="644",
        alerting_state_dir=host.data.alerting_state_dir,
        alerting_bin_dir=host.data.alerting_bin_dir,
        zfs_maintenance_sanoid_check=check,
    )

    systemd.daemon_reload(
        name="Reload systemd for sanoid",
        _if=dropin.did_change,
    )

    systemd.service(
        name="Enable the sanoid timer",
        service="sanoid.timer",
        running=True,
        enabled=True,
    )


@deploy("Configure pool scrubs", data_defaults=DEFAULTS)
def scrub():
    hostname = host.get_fact(Hostname)
    scrubs = host.data.zfs_maintenance_scrubs

    files.template(
        name="Install the scrub runner",
        src=f"{TEMPLATES}/zfs-scrub-pool.j2",
        dest=f"{host.data.zfs_maintenance_bin_dir}/zfs-scrub-pool",
        user="root",
        group="root",
        mode="755",
        alerting_bin_dir=host.data.alerting_bin_dir,
    )

    for entry in host.loop(scrubs):
        register_check(
            check=f"{hostname}-zfs-scrub-{entry['pool']}",
            schedule=entry["healthchecks_schedule"],
            grace=entry["healthchecks_grace"],
        )

    unit_changes = [
        files.template(
            name="Install the scrub service template unit",
            src=f"{TEMPLATES}/zfs-scrub-pool@.service.j2",
            dest="/etc/systemd/system/zfs-scrub-pool@.service",
            user="root",
            group="root",
            mode="644",
            hostname=hostname,
            alerting_state_dir=host.data.alerting_state_dir,
            alerting_bin_dir=host.data.alerting_bin_dir,
            zfs_maintenance_bin_dir=host.data.zfs_maintenance_bin_dir,
        )
    ]

    for entry in host.loop(scrubs):
        unit_changes.append(
            files.template(
                name=f"Install the scrub timer for {entry['pool']}",
                src=f"{TEMPLATES}/zfs-scrub-pool@.timer.j2",
                dest=f"/etc/systemd/system/zfs-scrub-pool@{entry['pool']}.timer",
                user="root",
                group="root",
                mode="644",
                pool=entry["pool"],
                calendar=entry["calendar"],
            )
        )

    systemd.daemon_reload(
        name="Reload systemd for scrub timers",
        _if=lambda: any(unit.did_change() for unit in unit_changes),
    )

    for entry in host.loop(scrubs):
        systemd.service(
            name=f"Enable the scrub timer for {entry['pool']}",
            service=f"zfs-scrub-pool@{entry['pool']}.timer",
            running=True,
            enabled=True,
        )


@deploy("Configure SMART monitoring", data_defaults=DEFAULTS)
def smartd():
    apt.packages(name="Install smartmontools", packages=["smartmontools"])

    files.template(
        name="Install the smartd alert handler",
        src=f"{TEMPLATES}/smartd-alert.j2",
        dest=f"{host.data.zfs_maintenance_bin_dir}/smartd-alert",
        user="root",
        group="root",
        mode="755",
        alerting_bin_dir=host.data.alerting_bin_dir,
    )

    config = files.template(
        name="Configure smartd",
        src=f"{TEMPLATES}/smartd.conf.j2",
        dest="/etc/smartd.conf",
        user="root",
        group="root",
        mode="644",
        zfs_maintenance_bin_dir=host.data.zfs_maintenance_bin_dir,
        zfs_maintenance_smart_schedule=host.data.zfs_maintenance_smart_schedule,
        zfs_maintenance_smart_temp_limits=host.data.zfs_maintenance_smart_temp_limits,
    )

    # Debian's smartd.service is an Alias= of smartmontools.service, and
    # `systemctl enable smartd` refuses to operate on a linked unit. Ansible's
    # systemd_service module resolves the alias; pyinfra hands the name to
    # systemctl as given, so the canonical name has to be used here.
    systemd.service(
        name="Enable smartd",
        service="smartmontools",
        running=True,
        enabled=True,
    )

    systemd.service(
        name="Restart smartd",
        service="smartmontools",
        restarted=True,
        _if=config.did_change,
    )


@deploy("Configure the ZFS event daemon", data_defaults=DEFAULTS)
def zed():
    apt.packages(name="Install the ZFS event daemon", packages=["zfs-zed"])

    zedlets = [
        files.template(
            name=f"Install the {event} zedlet",
            src=f"{TEMPLATES}/zedlet-storage-alert.sh.j2",
            dest=f"/etc/zfs/zed.d/{event}-storage-alert.sh",
            user="root",
            group="root",
            mode="755",
            alerting_bin_dir=host.data.alerting_bin_dir,
            zfs_maintenance_zed_throttle_seconds=host.data.zfs_maintenance_zed_throttle_seconds,
        )
        for event in host.data.zfs_maintenance_zed_events
    ]

    systemd.service(
        name="Enable the ZFS event daemon",
        service="zfs-zed",
        running=True,
        enabled=True,
    )

    systemd.service(
        name="Restart zed",
        service="zfs-zed",
        restarted=True,
        _if=lambda: any(zedlet.did_change() for zedlet in zedlets),
    )

    # Without autoreplace the hot spare never activates on its own.
    for pool in host.loop(host.data.zfs_maintenance_pools_autoreplace):
        zpool_property(
            name=f"Enable autoreplace on {pool}",
            pool=pool,
            prop="autoreplace",
            value="on",
        )


@deploy("Configure ZFS maintenance", data_defaults=DEFAULTS)
def zfs_maintenance():
    sanoid()
    scrub()
    smartd()
    zed()
