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

CHECKS = ("pod042-heartbeat", "pod042-scrub-ark", "pod042-scrub-black-box")


def ping(phase: str, check: str, scrub: str | None) -> None:
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
    suffix = "/start"
    if phase == "finish":
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
        suffix = "/0" if succeeded else "/fail"
    connection = http.client.HTTPSConnection("hc-ping.com", timeout=15)
    try:
        connection.request("POST", url.path + suffix, body=b"")
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("start", "finish"))
    parser.add_argument("check", choices=CHECKS)
    parser.add_argument("--scrub", choices=POOLS)
    args = parser.parse_args()
    try:
        ping(args.phase, args.check, args.scrub)
    except (OSError, ValueError, KeyError, RuntimeError, http.client.HTTPException):
        print(
            "hc-ping: notification failed; check credentials and connectivity",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
