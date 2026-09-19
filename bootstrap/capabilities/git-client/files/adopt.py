#!/usr/bin/env python3
"""Adopt legacy Git settings into mise's managed block without losing app keys."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

START = "# >>> mise:ansiblonomicon >>> managed by mise — do not edit between markers\n"
END = "# <<< mise:ansiblonomicon <<<\n"
LEGACY_OPTIONAL_KEYS = {
    "core.pager",
    "interactive.difffilter",
    "delta.navigate",
    "delta.side-by-side",
    "delta.line-numbers",
    "delta.hyperlinks",
}


def git_config(
    path: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "config", "--file", str(path), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def keys(config: str) -> set[str]:
    if not config.strip():
        return set()
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as stream:
        stream.write(config)
        stream.flush()
        result = git_config(Path(stream.name), "--name-only", "--list")
    return set(result.stdout.splitlines())


def remove_keys(config: str, owned: set[str]) -> str:
    if not config.strip() or not (keys(config) & owned):
        return config
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False
    ) as stream:
        stream.write(config)
        path = Path(stream.name)
    try:
        for key in sorted(keys(config) & owned):
            git_config(path, "--unset-all", key)
        return path.read_text()
    finally:
        path.unlink()


def adopt_file(path: Path) -> None:
    original = path.read_text()
    if original.count(START) != 1 or original.count(END) != 1:
        raise RuntimeError(f"missing or ambiguous mise markers in {path}")
    before, remainder = original.split(START)
    block, after = remainder.split(END)
    owned = keys(block) | LEGACY_OPTIONAL_KEYS
    adopted = (
        remove_keys(before, owned) + START + block + END + remove_keys(after, owned)
    )
    if adopted != original:
        mode = path.stat().st_mode
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            stream.write(adopted)
            replacement = Path(stream.name)
        try:
            replacement.chmod(mode)
            replacement.replace(path)
        finally:
            replacement.unlink(missing_ok=True)


def remove_legacy_global_include(path: Path) -> None:
    if not path.exists():
        return
    key = "includeIf.gitdir:~/code/personal/.path"
    values = git_config(path, "--get-all", key, check=False).stdout.splitlines()
    if "~/.config/git/personal.inc" in values:
        git_config(path, "--unset-all", key, "^~/.config/git/personal\\.inc$")


def validate() -> None:
    scm_config = os.environ.get("GIT_CLIENT_SCM_CONFIG", "")
    if scm_config:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as stream:
            stream.write(scm_config)
            stream.flush()
            git_config(Path(stream.name), "--list")

    required = ["GIT_CLIENT_PERSONAL_EMAIL", "GIT_CLIENT_PERSONAL_SIGNING_KEY"]
    if os.environ["HOST_PROFILE"] == "work":
        required.extend(["GIT_CLIENT_WORK_EMAIL", "GIT_CLIENT_WORK_SIGNING_KEY"])
    for name in required:
        value = os.environ.get(name, "")
        if not value:
            raise RuntimeError(f"{name} is required")
        if any(character in value for character in ('"', "\\", "\n", "\r", "\0")):
            raise RuntimeError(f"{name} contains characters unsafe for Git config")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "validate":
        validate()
        return 0
    home = Path(os.environ["HOME"])
    adopt_file(home / ".config/git/config")
    if os.environ["HOST_PROFILE"] == "work":
        remove_legacy_global_include(home / ".gitconfig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
