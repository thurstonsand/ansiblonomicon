#!/usr/bin/env python3
"""Reconcile the licensed Berkeley Mono font attachment from 1Password."""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

EXPECTED = (
    "BerkeleyMonoNerdFontMono-Regular.otf",
    "BerkeleyMonoNerdFontMono-Bold.otf",
    "BerkeleyMonoNerdFontMono-Oblique.otf",
    "BerkeleyMonoNerdFontMono-BoldOblique.otf",
)
ACCOUNT = "PQ7X5W7V6FDADHPFFEO62TLFEM"
REFERENCE = "op://Private/Berkeley Mono Font/nerd-font"
FONT_SIGNATURES = (b"OTTO", b"\x00\x01\x00\x00")


def validate_paths(font_dir: Path) -> list[str]:
    if font_dir.exists() and not font_dir.is_dir():
        raise ValueError(f"font directory is not a directory: {font_dir}")
    if font_dir.is_symlink() and not font_dir.exists():
        raise ValueError(f"font directory is a dangling symlink: {font_dir}")

    missing: list[str] = []
    for name in EXPECTED:
        destination = font_dir / name
        if destination.is_file():
            continue
        if destination.is_symlink():
            raise ValueError(f"font destination is a dangling symlink: {destination}")
        if destination.exists():
            raise ValueError(f"font destination is not a regular file: {destination}")
        missing.append(name)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    font_dir = Path.home() / "Library/Fonts"
    try:
        missing = validate_paths(font_dir)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if not missing:
        return 0
    if args.check:
        for name in missing:
            print(
                f"Berkeley Mono font would be installed: {font_dir / name}",
                file=sys.stderr,
            )
        return 0

    environment = os.environ.copy()
    for name in ("OP_SERVICE_ACCOUNT_TOKEN", "OP_CONNECT_HOST", "OP_CONNECT_TOKEN"):
        environment.pop(name, None)
    result = subprocess.run(
        ["op", "read", REFERENCE, "--account", ACCOUNT],
        env=environment,
        stdout=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        print(
            "failed to read Berkeley Mono font archive from 1Password", file=sys.stderr
        )
        return result.returncode
    try:
        with zipfile.ZipFile(io.BytesIO(result.stdout)) as archive:
            members = set(archive.namelist())
            if any(name not in members for name in EXPECTED):
                raise ValueError("archive is missing expected root font members")
            payloads = {name: archive.read(name) for name in EXPECTED}
            if any(not payloads[name].startswith(FONT_SIGNATURES) for name in EXPECTED):
                raise ValueError("archive contains an invalid expected OpenType font")
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        print(f"invalid Berkeley Mono font archive: {error}", file=sys.stderr)
        return 1

    font_dir.mkdir(parents=True, exist_ok=True)
    for name in missing:
        destination = font_dir / name
        fd, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=font_dir)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(payloads[name])
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o644)
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if not destination.is_file():
                    print(
                        f"font destination appeared but is not a regular file: {destination}",
                        file=sys.stderr,
                    )
                    return 1
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
