#!/usr/bin/env python3

from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
import json
import os
from pathlib import Path
import re
import sys
import tomllib
from typing import cast
from uuid import UUID

PING_ENV = {
    "pod042-heartbeat": "POD042_HEARTBEAT_PING_URL",
    "pod042-scrub-ark": "POD042_SCRUB_ARK_PING_URL",
    "pod042-scrub-black-box": "POD042_SCRUB_BLACK_BOX_PING_URL",
    "pod042-sanoid": "POD042_SANOID_PING_URL",
    "pod042-sanoid-prune": "POD042_SANOID_PRUNE_PING_URL",
}


class ReconcileError(Exception):
    pass


def record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReconcileError("Expected an API/config object")
    result = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in result):
        raise ReconcileError("Invalid object keys")
    return cast(dict[str, object], result)


def records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ReconcileError("Expected an API/config list")
    return [record(item) for item in cast(list[object], value)]


def text(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ReconcileError("Missing or invalid text field")
    return value


def uuid(value: str) -> str:
    try:
        if str(UUID(value)) == value:
            return value
    except ValueError:
        pass
    raise ReconcileError("Invalid API/config identifier")


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    kind: str

    @classmethod
    def parse(cls, data: dict[str, object]) -> "Channel":
        return cls(uuid(text(data, "id")), text(data, "name"), text(data, "kind"))


@dataclass(frozen=True)
class Metadata:
    slug: str
    name: str
    schedule: str | None
    tz: str | None
    grace: int
    methods: str
    manual_resume: bool
    channels: str

    @classmethod
    def parse(cls, data: dict[str, object]) -> "Metadata":
        grace = data.get("grace")
        manual_resume = data.get("manual_resume")
        if type(grace) is not int or not 60 <= grace <= 31536000:
            raise ReconcileError("Invalid grace period")
        if not isinstance(manual_resume, bool):
            raise ReconcileError("Invalid manual resume flag")
        schedule = text(data, "schedule") if "schedule" in data else None
        tz = text(data, "tz") if schedule is not None else None
        channels = text(data, "channels")
        if channels:
            for channel in channels.split(","):
                uuid(channel)
        methods = text(data, "methods")
        if methods not in ("", "POST"):
            raise ReconcileError("Invalid ping methods")
        return cls(
            text(data, "slug"),
            text(data, "name"),
            schedule,
            tz,
            grace,
            methods,
            manual_resume,
            channels,
        )

    def payload(self) -> dict[str, str | int | bool | None]:
        return {
            "slug": self.slug,
            "name": self.name,
            "schedule": self.schedule,
            "tz": self.tz,
            "grace": self.grace,
            "methods": self.methods,
            "manual_resume": self.manual_resume,
            "channels": self.channels,
        }


@dataclass(frozen=True)
class Check:
    id: str
    ping_url: str
    metadata: Metadata

    @classmethod
    def parse(cls, data: dict[str, object]) -> "Check":
        identifier = uuid(text(data, "uuid"))
        ping_url = text(data, "ping_url")
        if ping_url != f"https://hc-ping.com/{identifier}":
            raise ReconcileError("Invalid returned ping URL")
        return cls(identifier, ping_url, Metadata.parse(data))


class Healthchecks:
    def __init__(self, key: str):
        self.key = key

    def request(
        self,
        path: str,
        payload: dict[str, str | int | bool | None] | None = None,
    ) -> dict[str, object]:
        connection = HTTPSConnection("healthchecks.io", timeout=15)
        try:
            connection.request(
                "GET" if payload is None else "POST",
                f"/api/v3/{path}",
                body=None if payload is None else json.dumps(payload),
                headers={"X-Api-Key": self.key, "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if response.status not in (200, 201):
                raise ReconcileError(f"Healthchecks HTTP status {response.status}")
            return record(json.loads(response.read()))
        except (OSError, HTTPException, ValueError):
            raise ReconcileError("Healthchecks request or response failed") from None
        finally:
            connection.close()

    def verify_channel(self, expected: Channel) -> None:
        channels = [
            Channel.parse(item)
            for item in records(self.request("channels/").get("channels"))
        ]
        matches = [channel for channel in channels if channel.id == expected.id]
        if matches != [expected]:
            raise ReconcileError("Required Hark webhook integration missing or changed")

    def checks(self) -> dict[str, Check]:
        checks: dict[str, Check] = {}
        for item in records(self.request("checks/").get("checks")):
            slug = text(item, "slug")
            if slug not in PING_ENV:
                continue
            if slug in checks:
                raise ReconcileError("Duplicate managed check slug; refusing changes")
            checks[slug] = Check.parse(item)
        return checks

    def save(self, desired: Metadata, existing: Check | None) -> Check:
        path = "checks/" if existing is None else f"checks/{existing.id}"
        saved = Check.parse(self.request(path, desired.payload()))
        if saved.metadata != desired or (existing and saved.id != existing.id):
            raise ReconcileError(
                "Healthchecks write response did not match declaration"
            )
        return saved


def declarations() -> tuple[Channel, list[Metadata]]:
    with Path(__file__).with_name("checks.toml").open("rb") as source:
        config = record(tomllib.load(source))
    channel = Channel.parse(record(config.get("channel")))
    if channel.name != "Hark" or channel.kind != "webhook":
        raise ReconcileError("Declaration must select the Hark webhook")
    desired = [
        Metadata.parse({**item, "channels": channel.id})
        for item in records(config.get("checks"))
    ]
    if (
        len(desired) != len(PING_ENV)
        or {check.slug for check in desired} != PING_ENV.keys()
    ):
        raise ReconcileError(
            "Declaration must contain exactly the managed pod042 checks"
        )
    if any(
        not check.schedule
        or check.tz != "America/Los_Angeles"
        or check.manual_resume
        or check.methods != "POST"
        for check in desired
    ):
        raise ReconcileError("Invalid managed check declaration")
    return channel, desired


def reconcile(api: Healthchecks, check_only: bool) -> dict[str, str]:
    channel, desired = declarations()
    api.verify_channel(channel)
    existing = api.checks()
    missing: list[str] = []
    for check in desired:
        current = existing.get(check.slug)
        if current is None:
            missing.append(check.slug)
            print(f"Healthchecks: create {check.slug}", file=sys.stderr)
        elif current.metadata != check:
            fields = ", ".join(
                key
                for key, value in check.payload().items()
                if current.metadata.payload()[key] != value
            )
            print(f"Healthchecks: update {check.slug} ({fields})", file=sys.stderr)
    if check_only and missing:
        raise ReconcileError(
            "Missing checks: " + ", ".join(missing) + "; child not started"
        )
    urls: dict[str, str] = {}
    for check in desired:
        current = existing.get(check.slug)
        if not check_only and (current is None or current.metadata != check):
            current = api.save(check, current)
        if current is None:
            raise ReconcileError("Missing check; child not started")
        urls[PING_ENV[check.slug]] = current.ping_url
    return urls


def main(args: list[str]) -> None:
    check_only = bool(args and args[0] == "--check")
    if check_only:
        args = args[1:]
    if len(args) < 2 or args[0] != "--":
        raise ReconcileError("Usage: reconcile.py [--check] -- CHILD ARGS")
    key = os.environ.pop("HEALTHCHECKS_API_KEY", "")
    os.environ.pop("ANSIBLONOMICON_EXEC_PROFILE", None)
    os.environ.pop("ANSIBLONOMICON_EXEC_KEYS", None)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ReconcileError("HEALTHCHECKS_API_KEY missing or invalid")
    urls = reconcile(Healthchecks(key), check_only)
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("OP_", "FNOX_"))
    }
    environment.update(urls)
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvpe(args[1], args[1:], environment)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ReconcileError as error:
        print(f"Healthchecks: {error}", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError):
        print("Healthchecks: configuration or child execution failed", file=sys.stderr)
        sys.exit(1)
