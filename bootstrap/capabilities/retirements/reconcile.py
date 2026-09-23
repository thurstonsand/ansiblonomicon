"""Retire personal-host legacy resources through native mise absence declarations."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import tomllib

import tomlkit

HOSTS = {"Thurstons-MacBook-Pro", "pod042"}


def absence_resources(home: Path, paths: list[str]) -> dict[str, object]:
    files: dict[str, object] = {}
    directories: dict[str, object] = {}
    for relative in paths:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path == Path("."):
            raise ValueError(f"Invalid retired path: {relative}")
        target = home / path
        if not target.parent.resolve().is_relative_to(home.resolve()):
            raise ValueError(f"Retired path parent escapes home: {relative}")
        if target.is_dir() and not target.is_symlink():
            for root, names, leaves in os.walk(target, followlinks=False):
                current = Path(root)
                directories[str(current)] = {"state": "absent", "recursive": False}
                for leaf in leaves:
                    files[str(current / leaf)] = {"state": "absent"}
                for name in list(names):
                    child = current / name
                    if child.is_symlink():
                        files[str(child)] = {"state": "absent"}
                        names.remove(name)
        else:
            files[str(target)] = {"state": "absent"}
    return {"files": files, "directories": directories}


def reconcile(home: Path, hostname: str, check: bool) -> int:
    if hostname not in HOSTS:
        raise ValueError(f"Personal retirements are not enabled on {hostname}")
    data = tomllib.loads(Path(__file__).with_name("paths.toml").read_text())
    paths: list[str] = data["paths"]
    changed = False
    if hostname == "Thurstons-MacBook-Pro":
        paths.extend(data["macos"]["paths"])
    resources = absence_resources(home, paths)
    if hostname == "Thurstons-MacBook-Pro":
        for label in data["macos"]["launch_agents"]:
            job = f"gui/{os.getuid()}/{label}"
            result = subprocess.run(
                ["launchctl", "print", job], capture_output=True, check=False
            )
            if result.returncode == 0:
                changed = True
                print(f"Retire launch agent {label}")
                if not check:
                    subprocess.run(["launchctl", "bootout", job], check=True)
    changed |= any(
        (home / path).exists() or (home / path).is_symlink() for path in paths
    )
    with tempfile.TemporaryDirectory(prefix="ansiblonomicon-retirements-") as scratch:
        target = Path(scratch)
        (target / "mise.toml").write_text(
            tomlkit.dumps({"min_version": "2026.9.11", "bootstrap": resources})
        )
        subprocess.run(
            [
                "mise",
                "-C",
                str(target),
                "bootstrap",
                "files",
                "apply",
                "--dry-run" if check else "--yes",
            ],
            check=True,
            env={
                "HOME": str(home),
                "PATH": os.environ["PATH"],
                "MISE_STATE_DIR": str(target / "state"),
                "MISE_CEILING_PATHS": str(target.parent),
                "MISE_TRUSTED_CONFIG_PATHS": str(target),
                "MISE_GLOBAL_CONFIG_FILE": str(target / ".global.toml"),
                "MISE_SYSTEM_CONFIG_FILE": str(target / ".system.toml"),
            },
        )
    return int(check and changed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return reconcile(Path.home(), socket.gethostname().split(".")[0], args.check)


if __name__ == "__main__":
    raise SystemExit(main())
