#!/usr/bin/python3
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import time

from pod042_storage import POOLS, clean_scrub

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
