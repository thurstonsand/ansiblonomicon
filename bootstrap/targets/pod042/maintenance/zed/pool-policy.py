#!/usr/bin/python3
import argparse
from datetime import UTC, datetime
import json
import subprocess
import time

from pod042_storage import clean_scrub

POOLS = {
    "ark": {
        "guid": "8619294010601504858",
        "failmode": "wait",
        "autotrim": "off",
        "autoreplace": "off",
    },
    "black-box": {
        "guid": "131852107186480998",
        "failmode": "wait",
        "autotrim": "on",
        "autoreplace": "off",
    },
}


def properties(pool: str) -> dict[str, str]:
    result = subprocess.run(
        [
            "/usr/sbin/zpool",
            "get",
            "-Hp",
            "-o",
            "property,value",
            "guid,failmode,autotrim,autoreplace",
            pool,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    current = dict(line.split("\t") for line in result.stdout.splitlines())
    if current["guid"] != POOLS[pool]["guid"]:
        raise RuntimeError(
            f"Refusing unexpected pool GUID for {pool}: {current['guid']}"
        )
    return current


def upgrade_features() -> None:
    pending: list[str] = []
    for pool in POOLS:
        properties(pool)
        result = subprocess.run(
            ["/usr/sbin/zpool", "get", "-H", "-o", "property,value", "all", pool],
            check=True,
            capture_output=True,
            text=True,
        )
        features = dict(
            line.split("\t", maxsplit=1) for line in result.stdout.splitlines()
        )
        disabled = {
            prop
            for prop, value in features.items()
            if prop.startswith("feature@") and value == "disabled"
        }
        if disabled - {"feature@longname", "feature@large_microzap"}:
            raise RuntimeError(
                f"Unreviewed disabled features on {pool}: {sorted(disabled)}"
            )
        if disabled:
            pending.append(pool)
    if not pending:
        print("Pool features already enabled")
        return
    versions = subprocess.run(
        ["/usr/sbin/zfs", "version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if len(versions) != 2 or versions[0].removeprefix("zfs-") != versions[
        1
    ].removeprefix("zfs-kmod-"):
        raise RuntimeError("ZFS userspace and kernel module versions must match")
    for pool in pending:
        if not clean_scrub(pool):
            raise RuntimeError(
                f"Feature upgrade requires a clean completed scrub: {pool}"
            )
        result = subprocess.run(
            ["/usr/sbin/zpool", "status", "-jp", pool],
            check=True,
            capture_output=True,
            text=True,
        )
        end = int(json.loads(result.stdout)["pools"][pool]["scan_stats"]["end_time"])
        if not 0 <= time.time() - end <= 35 * 86400:
            raise RuntimeError(
                f"Feature upgrade requires a scrub within 35 days: {pool}"
            )
    snapshot = datetime.now(UTC).strftime("pre-feature-upgrade-%Y%m%dT%H%M%SZ")
    for pool in pending:
        subprocess.run(
            ["/usr/sbin/zfs", "snapshot", "-r", f"{pool}@{snapshot}"],
            check=True,
        )
    print(
        f"Preserved pre-upgrade snapshot {snapshot}; feature upgrades cannot be undone",
        flush=True,
    )
    for pool in pending:
        properties(pool)
        subprocess.run(["/usr/sbin/zpool", "upgrade", pool], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--apply", action="store_true")
    operation.add_argument("--upgrade", action="store_true")
    args = parser.parse_args()
    if args.upgrade:
        upgrade_features()
        return
    current = {pool: properties(pool) for pool in POOLS}
    for pool, desired in POOLS.items():
        for prop in ("failmode", "autotrim", "autoreplace"):
            if current[pool][prop] == desired[prop]:
                continue
            print(
                f"{pool}: {prop} {current[pool][prop]} -> {desired[prop]}", flush=True
            )
            if args.apply:
                properties(pool)
                subprocess.run(
                    ["/usr/sbin/zpool", "set", f"{prop}={desired[prop]}", pool],
                    check=True,
                )
                if properties(pool)[prop] != desired[prop]:
                    raise RuntimeError(f"Pool property did not converge: {pool} {prop}")


if __name__ == "__main__":
    main()
