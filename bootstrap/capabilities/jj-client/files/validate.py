#!/usr/bin/env python3
"""Validate identity values before rendering Jujutsu configuration."""

import os
import sys


def validate() -> None:
    required = ["JJ_CLIENT_PERSONAL_EMAIL", "JJ_CLIENT_PERSONAL_SIGNING_KEY"]
    if os.environ["HOST_PROFILE"] == "work":
        required.extend(["JJ_CLIENT_WORK_EMAIL", "JJ_CLIENT_WORK_SIGNING_KEY"])
    for name in required:
        value = os.environ.get(name, "")
        if not value:
            raise RuntimeError(f"{name} is required")
        if any(character in value for character in ('"', "\\", "\n", "\r", "\0")):
            raise RuntimeError(f"{name} contains characters unsafe for JJ config")


def main() -> int:
    if sys.argv[1:] != ["validate"]:
        raise RuntimeError("usage: validate.py validate")
    validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
