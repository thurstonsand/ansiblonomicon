#!/usr/bin/env python3
"""Render sudo_local while preserving lines outside this capability's ownership."""

import argparse
import base64
from pathlib import Path
import re

TID = re.compile(r"^#?auth\s+sufficient\s+pam_tid\.so(?:\s+.*)?$")
CANONICAL_TID = "auth       sufficient     pam_tid.so\n"


def render(content: str) -> str:
    lines = content.splitlines(keepends=True)
    tids = [
        index for index, line in enumerate(lines) if TID.fullmatch(line.rstrip("\r\n"))
    ]
    output: list[str] = []
    for index, line in enumerate(lines):
        if index in tids:
            if index == tids[0]:
                output.append(CANONICAL_TID)
            continue
        output.append(line)

    if not tids:
        if output and not output[-1].endswith(("\n", "\r")):
            output.append("\n")
        output.append(CANONICAL_TID)
    return "".join(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    args = parser.parse_args()
    content = args.path.read_text() if args.path.exists() else ""
    # Base64 protects trailing whitespace from exec()'s stdout trimming.
    print(base64.b64encode(render(content).encode()).decode(), end="")


if __name__ == "__main__":
    main()
