"""Custom operations for the bunker deploys."""

from __future__ import annotations

import json

from pyinfra import host
from pyinfra.api import HiddenValue, QuoteString, StringCommand, operation
from pyinfra.facts.files import FileContents

from bunker.facts import HealthchecksChecks, ZfsPoolProperty


@operation()
def healthchecks_check(
    check: str,
    schedule: str,
    grace: int,
    api_url: str,
    api_key: str,
    timezone: str,
    url_file: str | None = None,
):
    """Register one Healthchecks check and drop its ping URL where the job's
    unit can load it as a systemd credential.

    + check: check name, also used as its slug
    + schedule: cron expression the check is expected to ping on
    + grace: seconds of lateness tolerated before the check goes down
    + api_url / api_key: Healthchecks Management API endpoint and key
    + timezone: tz the schedule is interpreted in
    + url_file: where to write the ping URL; None for jobs that take it as a value

    Idempotency comes from the Management API's list endpoint, read as a fact:
    the POST only runs when the check is missing or one of its fields drifted.
    """

    checks = host.get_fact(HealthchecksChecks, api_url=api_url, api_key=api_key)
    existing = checks.get(check)

    desired = {
        "name": check,
        "slug": check,
        "schedule": schedule,
        "tz": timezone,
        "grace": int(grace),
        "channels": "*",
        "unique": ["name"],
    }

    drifted = existing is not None and (
        existing.get("schedule") != schedule
        or existing.get("tz") != timezone
        or int(existing.get("grace", -1)) != int(grace)
    )

    if existing is None or drifted:
        post = StringCommand(
            "curl",
            "-fsS",
            "--max-time",
            "10",
            "-X",
            "POST",
            "-H",
            # HiddenValue is the no_log analog: the key is masked in printed
            # command output but sent intact. It only works inside a command;
            # fact commands are plain strings, so the key is visible at -v.
            QuoteString(HiddenValue(f"X-Api-Key: {api_key}")),
            "-H",
            QuoteString("Content-Type: application/json"),
            "-d",
            QuoteString(json.dumps(desired)),
            QuoteString(api_url),
        )
        if url_file:
            yield StringCommand(
                "umask",
                "077;",
                post,
                "|",
                "jq",
                "-r",
                ".ping_url",
                ">",
                QuoteString(url_file),
            )
        else:
            yield StringCommand(post, ">", "/dev/null")
        return

    # The check is already correct; the only thing that can still be wrong is
    # the credential file on disk, and we know what belongs in it.
    if url_file:
        ping_url = existing["ping_url"]
        current = host.get_fact(FileContents, path=url_file)
        if current != [ping_url]:
            yield StringCommand(
                "umask",
                "077;",
                "printf",
                QuoteString("%s\\n"),
                QuoteString(ping_url),
                ">",
                QuoteString(url_file),
            )


@operation()
def zpool_property(pool: str, prop: str, value: str):
    """Set a zpool property, but only when it is not already set.

    The shell-based op pattern: `zpool set` is not idempotent by itself, so the
    operation gates it behind a fact and yields nothing when converged.
    """

    current = host.get_fact(ZfsPoolProperty, pool=pool, prop=prop)
    if current != value:
        yield StringCommand(
            "zpool", "set", QuoteString(f"{prop}={value}"), QuoteString(pool)
        )
