#!/usr/bin/python3
import argparse
import http.client
import os
from pathlib import Path
import stat
import subprocess
import sys
import urllib.parse
from uuid import UUID

from pod042_storage import POOLS, clean_scrub

CHECKS = (
    "pod042-heartbeat",
    "pod042-scrub-ark",
    "pod042-scrub-black-box",
    "pod042-sanoid",
    "pod042-sanoid-prune",
)


SIGNALS = ("start", "0", "fail")


def result(phase: str, scrub: str | None) -> str:
    if phase == "start":
        return "start"
    succeeded = (
        os.environ.get("SERVICE_RESULT") == "success"
        and os.environ.get("EXIT_CODE") == "exited"
        and os.environ.get("EXIT_STATUS") == "0"
    )
    if succeeded and scrub is not None:
        try:
            succeeded = clean_scrub(scrub)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ):
            succeeded = False
    return "0" if succeeded else "fail"


def send(check: str, signal: str) -> None:
    if os.geteuid() != 0:
        raise ValueError("Root is required")
    path = Path("/etc/alerting/checks") / f"{check}.url"
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, encoding="utf-8") as credential:
        metadata = os.fstat(credential.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != 0
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise ValueError("Unsafe credential file")
        url = urllib.parse.urlsplit(credential.read().strip())
    if (
        url.scheme != "https"
        or url.netloc != "hc-ping.com"
        or url.query
        or url.fragment
        or url.path != f"/{UUID(url.path.removeprefix('/'))}"
    ):
        raise ValueError("Invalid ping URL")
    connection = http.client.HTTPSConnection("hc-ping.com", timeout=15)
    try:
        connection.request("POST", f"{url.path}/{signal}", body=b"")
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
    finally:
        connection.close()


def attempt(check: str, signal: str) -> bool:
    try:
        send(check, signal)
    except (OSError, ValueError, KeyError, RuntimeError, http.client.HTTPException):
        print(
            "hc-ping: notification failed; check credentials and connectivity",
            file=sys.stderr,
        )
        return False
    return True


# A hook's result is decided once, in the producer's ExecStopPost, where the
# stop timeout and shutdown forbid waiting out an outage. Redelivery moves to a
# transient unit; the newest result for a check replaces any pending older one.
def redeliver(check: str, signal: str) -> int:
    unit = f"hc-ping-retry-{check}.service"
    return subprocess.run(
        [
            "/usr/bin/systemd-run",
            "--quiet",
            "--no-block",
            "--collect",
            f"--unit={unit}",
            "--property=Restart=on-failure",
            "--property=RestartSec=30s",
            "--property=RestartSteps=6",
            "--property=RestartMaxDelaySec=15min",
            "--property=StartLimitIntervalSec=0",
            "/usr/local/bin/hc-ping",
            "send",
            check,
            signal,
        ],
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("start", "finish", "send"))
    parser.add_argument("check", choices=CHECKS)
    parser.add_argument("signal", nargs="?", choices=SIGNALS)
    parser.add_argument("--scrub", choices=POOLS)
    args = parser.parse_args()
    if (args.phase == "send") != (args.signal is not None):
        parser.error("signal is required for send and only for send")
    if args.phase == "send":
        return 0 if attempt(args.check, args.signal) else 1

    signal = result(args.phase, args.scrub)
    subprocess.run(
        ["/usr/bin/systemctl", "stop", f"hc-ping-retry-{args.check}.service"],
        check=False,
        stderr=subprocess.DEVNULL,
    )
    if attempt(args.check, signal):
        return 0
    if redeliver(args.check, signal) != 0:
        print("hc-ping: could not schedule redelivery", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
