#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["jinja2>=3.1,<4", "pyyaml>=6,<7", "tomlkit>=0.13,<1"]
# ///
"""Guarded pod042 entry point for the shared native harness reconciler."""

import argparse
import os
from pathlib import Path
import socket
import sys

REPO = Path(__file__).resolve().parents[4]
HOME = Path("/home/thurstonsand")
sys.path.insert(0, str(REPO / "bootstrap/capabilities/agent-harness"))
import agent_harness_deploy as engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cached", action="store_true")
    args = parser.parse_args()
    if (
        socket.gethostname() != "pod042"
        or os.getuid() != 1000
        or os.getgid() != 1000
        or Path.home() != HOME
    ):
        raise SystemExit("Run only as pod042's thurstonsand operator (UID/GID 1000)")
    host = engine.load_host(Path(__file__).with_name("host.toml"))
    engine.reconcile(
        REPO,
        HOME,
        HOME / ".cache/ansiblonomicon-harness",
        host.profile,
        host.hostname,
        check=args.check,
        cached=args.cached,
        update=host.update,
        manifest_name=host.manifest,
        enabled_harnesses=host.enabled,
        explicit_only=host.explicit_only,
        trim_blocks=host.trim_blocks,
    )


if __name__ == "__main__":
    main()
