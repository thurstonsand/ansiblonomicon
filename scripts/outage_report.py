#!/usr/bin/env python3
"""Collect every log source for an internet outage window into one directory on pod042.

Read-only: it reads pod042's journal and pon-monitor's data, asks the stick for its live log, and
reads the UniFi controller's event log, devices, and system state. The UDM's support file is left
out because generating it writes to the controller and takes minutes.

    mise run outage:report -- 2026-11-08T05:40Z 2026-11-08T06:10Z
"""

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, cast

import httpx
from unifi_api import (
    DEFAULT_API_URL,
    HTTP_OK,
    HTTP_TIMEOUT,
    NetworkApi,
    decode_json,
    login,
)

PON_CONTAINER = "pon-monitor-pon-monitor-1"
PON_DATA = Path("/mnt/black-box/docker/pon-monitor/pon-monitor/data")
SYSTEM_LOG_PAGE_SIZE = 500
STICK_COMMAND = (
    'sshpass -p "$PON_STICK_PASSWORD" ssh -o HostKeyAlgorithms=+ssh-rsa '
    "-o PubkeyAuthentication=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
    '-o LogLevel=ERROR root@192.168.11.1 "uptime; logread"'
)


def instant(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError(f"{value} needs a zone, such as Z or -05:00")
    return moment.astimezone(UTC)


def capture(out: Path, name: str, command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    (out / name).write_text(result.stdout + result.stderr)
    if result.returncode:
        print(f"{name}: {command[0]} exited {result.returncode}", file=sys.stderr)


def samples(out: Path, since: datetime, until: datetime) -> int:
    rows: list[str] = []
    for path in sorted(PON_DATA.glob("samples.jsonl*"), reverse=True):
        for line in path.read_text().splitlines():
            stamp = instant(json.loads(line)["ts"])
            if since <= stamp <= until:
                rows.append(line)
    (out / "pon-samples.jsonl").write_text("".join(f"{row}\n" for row in rows))
    return len(rows)


def captures(out: Path, since: datetime, until: datetime) -> list[str]:
    copied: list[str] = []
    for path in sorted((PON_DATA / "captures").glob("*.log")):
        stamp = datetime.strptime(path.stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        if since <= stamp <= until:
            (out / "pon-captures").mkdir(exist_ok=True)
            shutil.copy(path, out / "pon-captures" / path.name)
            copied.append(path.name)
    return copied


def controller(out: Path, since: datetime, until: datetime) -> int:
    with httpx.Client(verify=False, timeout=HTTP_TIMEOUT) as client:
        login(
            client,
            DEFAULT_API_URL,
            os.environ["UNIFI_USERNAME"],
            os.environ["UNIFI_PASSWORD"],
        )
        events: list[object] = []
        page = 0
        while True:
            response = client.post(
                f"{DEFAULT_API_URL}/proxy/network/v2/api/site/default/system-log/all",
                json={
                    "timestampFrom": int(since.timestamp() * 1000),
                    "timestampTo": int(until.timestamp() * 1000),
                    "pageSize": SYSTEM_LOG_PAGE_SIZE,
                    "pageNumber": page,
                },
            )
            response.raise_for_status()
            body = cast(dict[str, Any], decode_json(response, "system-log"))
            events.extend(body["data"])
            page += 1
            if page >= body["total_page_count"]:
                break
        (out / "unifi-events.json").write_text(json.dumps(events, indent=2))
        devices = NetworkApi(client, DEFAULT_API_URL).get_json("/stat/device")
        (out / "unifi-devices.json").write_text(json.dumps(devices, indent=2))
        system = client.get(f"{DEFAULT_API_URL}/api/system")
        if system.status_code != HTTP_OK:
            raise RuntimeError(f"GET /api/system: HTTP {system.status_code}")
        (out / "unifi-system.json").write_text(json.dumps(system.json(), indent=2))
    return len(events)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect an internet outage window's logs on pod042."
    )
    parser.add_argument(
        "since", type=instant, help="window start, ISO 8601 with a zone"
    )
    parser.add_argument("until", type=instant, help="window end, ISO 8601 with a zone")
    parser.add_argument(
        "--out", type=Path, help="new directory for the report (default: a temp dir)"
    )
    args = parser.parse_args()
    since: datetime = args.since
    until: datetime = args.until
    out: Path = args.out or Path(
        tempfile.mkdtemp(prefix=f"outage-{since:%Y%m%dT%H%MZ}-")
    )
    out.mkdir(parents=True, exist_ok=True)

    journal_since = since.strftime("%Y-%m-%d %H:%M:%S UTC")
    journal_until = until.strftime("%Y-%m-%d %H:%M:%S UTC")
    capture(
        out,
        "pod042-journal.log",
        [
            "sudo",
            "-n",
            "journalctl",
            "--no-pager",
            "-o",
            "short-iso-precise",
            "--since",
            journal_since,
            "--until",
            journal_until,
        ],
    )
    capture(
        out,
        "pon-monitor.log",
        [
            "docker",
            "logs",
            "--timestamps",
            "--since",
            since.isoformat(),
            "--until",
            until.isoformat(),
            PON_CONTAINER,
        ],
    )
    capture(
        out,
        "stick-live.log",
        ["docker", "exec", PON_CONTAINER, "sh", "-c", STICK_COMMAND],
    )
    capture(
        out,
        "unifi-smoke.txt",
        [sys.executable, str(Path(__file__).with_name("unifi_smoke.py"))],
    )
    rows = samples(out, since, until)
    copied = captures(out, since, until)
    events = controller(out, since, until)

    print(out)
    print(
        f"  pon samples: {rows}, stick captures: {', '.join(copied) or 'none'}, controller events: {events}"
    )
    print(
        "  The stick log and unifi-smoke are live, not windowed. pon-monitor timestamps are UTC;"
    )
    print("  the stick's own clock is wrong. The UDM support file is not collected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
