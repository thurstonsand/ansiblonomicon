#!/usr/bin/env python3
"""Verify every running container resolves an external name through its own resolver."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from random import randbytes
import socket
import subprocess

EXTERNAL_NAME = "api.github.com"
QUERY_TIMEOUT_SECONDS = 3.0
QUERY_ATTEMPTS = 2
INSPECT_FORMAT = (
    "{{.Name}}\t{{.State.Pid}}\t{{.HostConfig.NetworkMode}}\t{{.ResolvConfPath}}"
)


@dataclass(frozen=True)
class Container:
    name: str
    pid: int
    network_mode: str
    resolver: Path

    def nameservers(self) -> list[str]:
        """Docker writes this file on the host and bind-mounts it into the container."""
        if not self.resolver.exists():
            return []
        return [
            fields[1]
            for fields in (
                line.split() for line in self.resolver.read_text().splitlines()
            )
            if len(fields) > 1 and fields[0] == "nameserver"
        ]


def output(*command: str) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def running_containers() -> list[Container]:
    identifiers = output("/usr/bin/docker", "ps", "--quiet").split()
    if not identifiers:
        return []
    containers: list[Container] = []
    for line in output(
        "/usr/bin/docker", "inspect", "--format", INSPECT_FORMAT, *identifiers
    ).splitlines():
        name, pid, network_mode, resolver = line.split("\t")
        containers.append(
            Container(
                name=name.lstrip("/"),
                pid=int(pid),
                network_mode=network_mode,
                resolver=Path(resolver),
            )
        )
    return sorted(containers, key=lambda container: container.name)


def query(server: str) -> bool:
    """Ask one nameserver for EXTERNAL_NAME over UDP from the current namespace."""
    identifier = randbytes(2)
    labels = b"".join(
        bytes([len(label)]) + label.encode() for label in EXTERNAL_NAME.split(".")
    )
    request = (
        identifier
        + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        + labels
        + b"\x00\x00\x01\x00\x01"
    )
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(QUERY_TIMEOUT_SECONDS)
        try:
            sock.sendto(request, (server, 53))
            response = sock.recv(512)
        except OSError:
            return False
    answers = int.from_bytes(response[6:8], "big")
    return response[:2] == identifier and response[3] & 0x0F == 0 and answers > 0


def query_within(container: Container, server: str) -> bool:
    """Enter only the network namespace, so the host's Python runs against its resolvers."""
    for _ in range(QUERY_ATTEMPTS):
        completed = subprocess.run(
            [
                "/usr/bin/nsenter",
                "--net",
                f"--target={container.pid}",
                "--",
                "/usr/bin/python3",
                str(Path(__file__).resolve()),
                "--query",
                server,
            ],
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return True
    return False


def verify(containers: Sequence[Container]) -> list[str]:
    errors: list[str] = []
    for container in containers:
        if container.network_mode == "none":
            continue
        servers = container.nameservers()
        if not servers:
            errors.append(
                f"{container.name} has no nameserver; "
                "Docker generated its resolv.conf while the host had none"
            )
            continue
        if not any(query_within(container, server) for server in servers):
            errors.append(
                f"{container.name} cannot resolve {EXTERNAL_NAME} "
                f"through {', '.join(servers)}"
            )
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        metavar="NAMESERVER",
        help="resolve EXTERNAL_NAME through one nameserver and exit; used by nsenter",
    )
    return parser


def main() -> int:
    server = build_parser().parse_args().query
    if server is not None:
        return 0 if query(server) else 1
    containers = running_containers()
    errors = verify(containers)
    if errors:
        for error in errors:
            print(f"FAIL  {error}")
        return 1
    print(f"PASS  {len(containers)} running containers resolve {EXTERNAL_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
