#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import sys
import time

from terminal_theme_common import ThemeLease, positive_int, read_mode, sync_mirror


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--ssh-pid", required=True)
    parser.add_argument("--ttl", required=True)
    parser.add_argument("--refresh", required=True)
    return parser.parse_args()


def pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lease_expiry(ttl_seconds: int) -> int:
    return int(time.time()) + ttl_seconds


def main() -> int:
    args = parse_args()
    try:
        ssh_pid = positive_int(args.ssh_pid, name="ssh_pid")
        ttl_seconds = positive_int(args.ttl, name="ttl")
        refresh_seconds = positive_int(args.refresh, name="refresh")
        lease = ThemeLease.add_lease(
            ssh_pid=ssh_pid,
            host=args.host,
            expires_at=lease_expiry(ttl_seconds),
        )
    except ValueError as exc:
        print(f"terminal-theme-ssh-lease: {exc}", file=sys.stderr)
        return 2

    def cleanup(_signum: int | None = None, _frame: object | None = None) -> None:
        lease.remove()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGHUP, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    sync_mirror(lease.host, read_mode())

    while pid_exists(ssh_pid):
        time.sleep(refresh_seconds)
        if pid_exists(ssh_pid):
            lease = ThemeLease.add_lease(
                ssh_pid=ssh_pid,
                host=args.host,
                expires_at=lease_expiry(ttl_seconds),
            )

    lease.remove()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
