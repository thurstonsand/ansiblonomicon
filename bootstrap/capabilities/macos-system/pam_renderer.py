#!/usr/bin/env python3
"""Render sudo_local while preserving lines outside this capability's ownership."""

import argparse
import base64
from pathlib import Path
import re

REATTACH = re.compile(r"^#?auth\s+optional\s+.*/pam_reattach\.so(?:\s+.*)?$")
TID = re.compile(r"^#?auth\s+sufficient\s+pam_tid\.so(?:\s+.*)?$")
CANONICAL_REATTACH = "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
CANONICAL_TID = "auth       sufficient     pam_tid.so\n"


def render(content: str, profile: str) -> str:
    lines = content.splitlines(keepends=True)
    tids = [
        index for index, line in enumerate(lines) if TID.fullmatch(line.rstrip("\r\n"))
    ]
    reattaches = [
        index
        for index, line in enumerate(lines)
        if REATTACH.fullmatch(line.rstrip("\r\n"))
    ]
    first_tid = tids[0] if tids else None
    keep_reattach = None
    if profile == "personal":
        preceding = [
            index for index in reattaches if first_tid is not None and index < first_tid
        ]
        keep_reattach = (
            preceding[0]
            if preceding
            else (reattaches[0] if first_tid is None and reattaches else None)
        )

    output: list[str] = []
    for index, line in enumerate(lines):
        if index in tids:
            if index == first_tid:
                if profile == "personal" and keep_reattach is None:
                    output.append(CANONICAL_REATTACH)
                output.append(CANONICAL_TID)
            continue
        if profile == "personal" and index in reattaches:
            if index == keep_reattach:
                output.append(CANONICAL_REATTACH)
            continue
        output.append(line)

    if first_tid is None:
        if output and not output[-1].endswith(("\n", "\r")):
            output.append("\n")
        if profile == "personal" and keep_reattach is None:
            output.append(CANONICAL_REATTACH)
        output.append(CANONICAL_TID)
    return "".join(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--profile", choices=("personal", "work"), required=True)
    args = parser.parse_args()
    content = args.path.read_text() if args.path.exists() else ""
    # Base64 protects trailing whitespace from exec()'s stdout trimming.
    print(base64.b64encode(render(content, args.profile).encode()).decode(), end="")


if __name__ == "__main__":
    main()
