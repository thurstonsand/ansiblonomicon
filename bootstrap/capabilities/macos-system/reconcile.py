#!/usr/bin/env python3
"""Narrow orchestration around native mise macOS resources."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, cast

DEFAULT_SECTIONS = (
    "dock",
    "finder",
    "nsglobaldomain",
    "menubar",
    "desktop-services",
    "permissions",
    "hostname",
)
DEFAULT_DOMAINS = {
    "com.apple.dock": "Dock",
    "com.apple.finder": "Finder",
    "com.apple.desktopservices": "Finder",
    "com.apple.menuextra.clock": "SystemUIServer",
}


def run(
    command: list[str], *, capture: bool = False, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, check=True, text=True, capture_output=capture, env=env
    )


def native_env(target: Path, environments: str) -> dict[str, str]:
    env = {
        **os.environ,
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "MISE_ENV": environments,
        "MISE_GLOBAL_CONFIG_FILE": str(target.parent / ".isolated-global.toml"),
        "MISE_SYSTEM_CONFIG_FILE": str(target.parent / ".isolated-system.toml"),
        "MACOS_SYSTEM_PYTHON": sys.executable,
        "MACOS_SYSTEM_PAM_RENDERER": str(Path(__file__).with_name("pam_renderer.py")),
    }
    return env


def scutil_value(key: str) -> str | None:
    result = subprocess.run(
        ["scutil", "--get", key], check=False, text=True, capture_output=True
    )
    if result.returncode == 0:
        return result.stdout.rstrip("\n")
    if key == "HostName" and result.stderr.strip() == "HostName: not set":
        return None
    raise subprocess.CalledProcessError(
        result.returncode,
        result.args,
        output=result.stdout,
        stderr=result.stderr,
    )


def defaults_status(target: Path, environments: str) -> list[dict[str, Any]]:
    result = run(
        [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "macos",
            "defaults",
            "status",
            "--json",
        ],
        capture=True,
        env=native_env(target, environments),
    )
    payload = json.loads(result.stdout)["macos_defaults"]
    if not payload.get("available", False):
        raise RuntimeError("native macOS defaults are unavailable on this host")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("unexpected native defaults status JSON")
    return cast(list[dict[str, Any]], entries)


def restart(applications: set[str]) -> None:
    failures: list[subprocess.CalledProcessError] = []
    for application in sorted(applications):
        result = subprocess.run(
            ["killall", application], check=False, text=True, capture_output=True
        )
        if result.returncode and not (
            result.returncode == 1 and "No matching processes" in result.stderr
        ):
            failures.append(
                subprocess.CalledProcessError(
                    result.returncode,
                    result.args,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            )
    if failures:
        raise failures[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--profile", choices=("personal", "work"), required=True)
    parser.add_argument("--sections", default=",".join(DEFAULT_SECTIONS))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--hostname", default="Thurstons-MacBook-Pro")
    args = parser.parse_args()
    target = cast(Path, args.target).resolve()
    section_text = cast(str, args.sections)
    sections = list(dict.fromkeys(section_text.split(",")))
    if not section_text or "" in sections:
        parser.error("sections must not be empty")
    unknown = set(sections) - set(DEFAULT_SECTIONS)
    if unknown:
        parser.error(f"unknown sections: {','.join(sorted(unknown))}")
    if args.profile == "work" and "hostname" in sections:
        parser.error("hostname is intentionally unmanaged on work")

    defaults = [
        section for section in sections if section not in ("permissions", "hostname")
    ]
    environments = ",".join(defaults)
    entries = defaults_status(target, environments) if defaults else []
    changed = [entry for entry in entries if entry.get("state") != "set"]

    changed_file = False
    permissions_env = native_env(target, "permissions")
    if "permissions" in sections:
        file_status = run(
            ["mise", "-C", str(target), "bootstrap", "files", "status", "--json"],
            capture=True,
            env=permissions_env,
        )
        resources = json.loads(file_status.stdout)
        if not isinstance(resources, list):
            raise ValueError("unexpected native file status JSON")
        file_entries = cast(list[dict[str, object]], resources)
        changed_file = any(item.get("action") != "noop" for item in file_entries)
        if (
            changed_file
            and args.profile == "personal"
            and not Path("/opt/homebrew/lib/pam/pam_reattach.so").exists()
        ):
            raise RuntimeError(
                "pam_reattach module is required before changing personal sudo authentication"
            )

    differing = []
    if "hostname" in sections:
        differing = [
            key
            for key in ("HostName", "ComputerName", "LocalHostName")
            if scutil_value(key) != args.hostname
        ]

    restarts = {
        DEFAULT_DOMAINS[entry["domain"]]
        for entry in changed
        if entry.get("domain") in DEFAULT_DOMAINS
    }
    if changed:
        command = [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "macos",
            "defaults",
            "apply",
            "--yes",
        ]
        if args.check:
            command.append("--dry-run")
        try:
            run(command, env=native_env(target, environments))
        except subprocess.CalledProcessError:
            if not args.check:
                now_set = {
                    (entry.get("domain"), entry.get("key"))
                    for entry in defaults_status(target, environments)
                    if entry.get("state") == "set"
                }
                restart(
                    {
                        DEFAULT_DOMAINS[entry["domain"]]
                        for entry in changed
                        if (entry.get("domain"), entry.get("key")) in now_set
                        and entry.get("domain") in DEFAULT_DOMAINS
                    }
                )
            raise
    if args.check:
        if restarts:
            print("would restart: " + ", ".join(sorted(restarts)))
    else:
        restart(restarts)

    if changed_file:
        command = [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "files",
            "apply",
            "--yes",
        ]
        if args.check:
            command.append("--dry-run")
        run(command, env=permissions_env)

    if differing:
        if args.check:
            print("hostname: would set " + ", ".join(differing))
        else:
            for key in differing:
                run(["sudo", "-A", "scutil", "--set", key, args.hostname])


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, KeyError, ValueError, RuntimeError) as error:
        detail = getattr(error, "stderr", None)
        print(f"macos-system: {detail.strip() if detail else error}", file=sys.stderr)
        raise SystemExit(1) from error
