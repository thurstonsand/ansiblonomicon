#!/usr/bin/env python3
"""Hold network-online.target open until DHCP has delivered a route and a resolver."""

import json
from pathlib import Path
import subprocess
import time

RESOLVER = Path("/etc/resolv.conf")
DEADLINE_SECONDS = 120
POLL_SECONDS = 0.5


def gateway() -> str | None:
    routes = json.loads(
        subprocess.run(
            ["/usr/sbin/ip", "-json", "route", "show", "default"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    for route in routes:
        address = route.get("gateway")
        if address:
            return str(address)
    return None


def nameservers() -> list[str]:
    if not RESOLVER.exists():
        return []
    return [
        fields[1]
        for fields in (line.split() for line in RESOLVER.read_text().splitlines())
        if len(fields) > 1 and fields[0] == "nameserver"
    ]


def main() -> int:
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        route, resolvers = gateway(), nameservers()
        if route and resolvers:
            print(f"routed via {route}, resolving through {', '.join(resolvers)}")
            return 0
        if time.monotonic() >= deadline:
            missing = " and ".join(
                filter(
                    None,
                    [
                        None if route else "a default route",
                        None if resolvers else "a nameserver",
                    ],
                )
            )
            print(f"gave up after {DEADLINE_SECONDS}s without {missing}")
            return 1
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
