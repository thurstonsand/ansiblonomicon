"""Custom facts for the bunker deploys.

`HealthchecksChecks` is the interesting one: it reads a remote HTTP API rather
than the filesystem, which is what lets the `healthchecks_check` operation be
idempotent against a resource that has no on-disk representation.
"""

from __future__ import annotations

import json
from typing import override

from pyinfra.api import FactBase


class HealthchecksChecks(FactBase):
    """Every check registered in a Healthchecks project, keyed by slug.

    The Management API's list endpoint is a read, so this is safe to gather
    during the prepare phase: no check is created by looking.
    """

    default = dict

    @override
    def requires_command(self, api_url: str, api_key: str) -> str:
        # pyinfra passes the fact's own arguments to requires_command too, so
        # the signatures have to match.
        return "curl"

    @override
    def command(self, api_url: str, api_key: str) -> str:
        # Single line: pyinfra sends the fact command as one shell command.
        return f"curl -fsS --max-time 10 -H 'X-Api-Key: {api_key}' '{api_url}'"

    @override
    def process(self, output) -> dict[str, dict]:
        payload = json.loads("\n".join(output) or "{}")
        return {
            check["slug"]: check
            for check in payload.get("checks", [])
            if check.get("slug")
        }


class ZfsPoolProperty(FactBase):
    """One property of one pool. pyinfra ships `facts.zfs.ZfsPools`, which
    gathers every property of every pool in one call; this narrower fact exists
    to show what a fact with arguments looks like."""

    default = type(None)

    @override
    def requires_command(self, pool: str, prop: str) -> str:
        return "zpool"

    @override
    def command(self, pool: str, prop: str) -> str:
        return f"zpool get -H -o value {prop} {pool}"

    @override
    def process(self, output) -> str | None:
        return output[0].strip() if output else None
