#!/usr/bin/python3
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import NotRequired, TypedDict

POOLS = {"ark": "8619294010601504858", "black-box": "131852107186480998"}
FAULTS = {
    "checksum",
    "io",
    "data",
    "deadman",
    "delay",
    "io_failure",
    "probe_failure",
    "log_replay",
    "dio_verify_rd",
    "dio_verify_wr",
    "vdev.unknown",
    "vdev.open_failed",
    "vdev.corrupt_data",
    "vdev.no_replicas",
    "vdev.bad_guid_sum",
    "vdev.too_small",
    "vdev.bad_label",
    "vdev.bad_ashift",
}
OUTCOMES = {"scrub_finish", "scrub_abort", "resilver_finish"}


class Vdev(TypedDict):
    state: str
    read_errors: int | str
    write_errors: int | str
    checksum_errors: int | str
    vdevs: NotRequired[dict[str, "Vdev"]]


def healthy_vdevs(vdevs: dict[str, Vdev]) -> bool:
    return all(
        vdev["state"] == "ONLINE"
        and int(vdev["read_errors"]) == 0
        and int(vdev["write_errors"]) == 0
        and int(vdev["checksum_errors"]) == 0
        and healthy_vdevs(vdev.get("vdevs", {}))
        for vdev in vdevs.values()
    )


def clean_scrub(pool: str) -> bool:
    result = subprocess.run(
        ["/usr/sbin/zpool", "status", "-jp", pool],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    status = json.loads(result.stdout)["pools"][pool]
    if status["pool_guid"] != POOLS[pool]:
        raise RuntimeError(f"Unexpected pool GUID for {pool}")
    scan = status["scan_stats"]
    return (
        status["state"] == "ONLINE"
        and int(status["error_count"]) == 0
        and healthy_vdevs(status["vdevs"])
        and scan["function"] == "SCRUB"
        and scan["state"] == "FINISHED"
        and int(scan["errors"]) == 0
        and int(scan["processed"]) == 0
    )


def main() -> int:
    event = os.environ["ZEVENT_SUBCLASS"]
    if event not in FAULTS | OUTCOMES | {"statechange"}:
        return 0
    pool = os.environ["ZEVENT_POOL"]
    if pool not in POOLS:
        return 0
    state = os.environ.get("ZEVENT_VDEV_STATE_STR", "")
    if event == "statechange" and state == "ONLINE":
        return 0
    if event == "scrub_finish":
        try:
            if clean_scrub(pool):
                return 0
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            state = "UNVERIFIED"
    body = "\n".join(
        f"{key.removeprefix('ZEVENT_')}: {os.environ[key]}"
        for key in (
            "ZEVENT_POOL",
            "ZEVENT_POOL_GUID",
            "ZEVENT_EID",
            "ZEVENT_TIME_STRING",
            "ZEVENT_SUBCLASS",
            "ZEVENT_VDEV_STATE_STR",
            "ZEVENT_VDEV_PATH",
            "ZEVENT_VDEV_GUID",
            "ZEVENT_ZIO_ERR",
        )
        if key in os.environ
    )
    title = f"ZFS {event} {state} on {pool}".replace("  ", " ")
    command = ["/usr/local/bin/storage-alert", title, body]
    if event in OUTCOMES:
        return subprocess.run(command, check=False).returncode

    key = f"{pool}:{event}:{os.environ.get('ZEVENT_VDEV_GUID', '')}:{state}"
    directory = Path("/run/zed-storage-alert")
    directory.mkdir(mode=0o700, exist_ok=True)
    stamp = directory / hashlib.sha256(key.encode()).hexdigest()
    with stamp.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        previous = lock.read()
        now = time.monotonic()
        if previous and now - float(previous) < 3600:
            return 0
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            lock.seek(0)
            lock.truncate()
            lock.write(str(now))
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
