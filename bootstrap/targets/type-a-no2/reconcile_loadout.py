#!/usr/bin/env python3
"""Reconcile declared packages, themes, and plugins through Omarchy's own commands."""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tomllib
from typing import cast

PACKAGE_NAME = re.compile(r"[a-z0-9][a-z0-9@._+-]*\Z")
# The names omarchy-theme-install and omarchy-plugin-remove accept.
THEME_NAME = re.compile(r"[a-z0-9_][a-z0-9._+-]*\Z")
PLUGIN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
KINDS = {"packages", "aur", "themes", "plugins"}
PACMAN_RUN = re.compile(r"\[(?P<time>[^\]]+)\] \[PACMAN\] Running '(?P<command>[^']*)'")
PKG_ADD = re.compile(r"^\s*omarchy-pkg-add ([a-z0-9][a-z0-9@._+ -]*)$", re.MULTILINE)
PLUGINS_DIR = Path.home() / ".config/omarchy/plugins"
SETUP_STATE = Path.home() / ".local/state/omarchy-loadout/plugin-setup"


@dataclass(frozen=True)
class Plugin:
    source: str
    # Runs from the plugin checkout after install and again whenever its commit changes,
    # since Omarchy clones plugins without running any install steps of their own.
    setup: str | None


@dataclass(frozen=True)
class Manifest:
    packages: dict[str, str]
    aur: dict[str, str]
    # A git URL to install from, or None when the theme or plugin is declared absent.
    themes: dict[str, str | None]
    plugins: dict[str, Plugin | None]


def declared_packages(table: dict[object, object]) -> dict[str, str]:
    packages: dict[str, str] = {}
    for name, state in table.items():
        if (
            not isinstance(name, str)
            or not PACKAGE_NAME.fullmatch(name)
            or state not in {"present", "absent"}
        ):
            raise ValueError(f"invalid package declaration: {name} = {state!r}")
        packages[name] = cast(str, state)
    return packages


def declared_sources(
    kind: str, table: dict[object, object], name_pattern: re.Pattern[str]
) -> dict[str, str | None]:
    sources: dict[str, str | None] = {}
    for name, declaration in table.items():
        if not isinstance(name, str) or not name_pattern.fullmatch(name):
            raise ValueError(f"invalid {kind} name: {name!r}")
        if declaration == {"state": "absent"}:
            sources[name] = None
        elif (
            isinstance(declaration, dict)
            and set(cast(dict[str, object], declaration)) == {"source"}
            and isinstance(declaration["source"], str)
        ):
            sources[name] = declaration["source"]
        else:
            raise ValueError(f"invalid {kind} declaration: {name} = {declaration!r}")
    return sources


def declared_plugins(table: dict[object, object]) -> dict[str, Plugin | None]:
    plugins: dict[str, Plugin | None] = {}
    for name, declaration in table.items():
        if not isinstance(name, str):
            raise ValueError(f"invalid plugin name: {name!r}")
        setup = None
        if isinstance(declaration, dict):
            fields = cast(dict[str, object], declaration)
            setup = fields.get("setup")
            if setup is not None and not isinstance(setup, str):
                raise ValueError(f"invalid plugin setup: {name} = {setup!r}")
            declaration = {k: v for k, v in fields.items() if k != "setup"}
        source = declared_sources("plugin", {name: declaration}, PLUGIN_ID)[name]
        if source is None and setup is not None:
            raise ValueError(f"absent plugin declares setup: {name}")
        plugins[name] = None if source is None else Plugin(source, setup)
    return plugins


def load_manifest(path: Path) -> Manifest:
    data = tomllib.loads(path.read_text())
    if not set(data) <= KINDS or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError(f"manifest may only contain the tables {sorted(KINDS)}")
    tables = cast(dict[str, dict[object, object]], data)
    return Manifest(
        packages=declared_packages(tables.get("packages", {})),
        aur=declared_packages(tables.get("aur", {})),
        themes=declared_sources("theme", tables.get("themes", {}), THEME_NAME),
        plugins=declared_plugins(tables.get("plugins", {})),
    )


def package_installed(name: str) -> bool:
    present = subprocess.run(["omarchy", "pkg", "present", name], check=False)
    if present.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(present.returncode, present.args)
    return present.returncode == 0


def installed_themes() -> set[str]:
    themes_dir = Path.home() / ".config/omarchy/themes"
    if not themes_dir.is_dir():
        return set()
    return {entry.name for entry in themes_dir.iterdir() if entry.is_dir()}


def generated_themes() -> set[str]:
    """Themes the Aether app writes for itself, which have no source to declare."""
    themes_dir = Path.home() / ".config/omarchy/themes"
    return {marker.parent.name for marker in themes_dir.glob("*/.aether-managed")}


def installed_plugins() -> set[str]:
    catalog = subprocess.run(
        ["omarchy", "plugin", "catalog"], check=True, capture_output=True, text=True
    )
    return {
        plugin["id"]
        for plugin in json.loads(catalog.stdout)
        if Path(plugin["sourceDir"]).parent == PLUGINS_DIR
    }


def pending_setups(plugins: dict[str, Plugin | None]) -> dict[str, tuple[str, str]]:
    """Setup commands whose last successful run predates the plugin's current commit,
    keyed by plugin id, with the stamp that records a run of that command at that commit."""
    pending: dict[str, tuple[str, str]] = {}
    for plugin_id, plugin in plugins.items():
        if plugin is None or plugin.setup is None:
            continue
        checkout = PLUGINS_DIR / plugin_id
        commit = (
            subprocess.run(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if checkout.is_dir()
            else "uninstalled"
        )
        stamp = f"{commit}\n{plugin.setup}\n"
        recorded = SETUP_STATE / plugin_id
        if not recorded.is_file() or recorded.read_text() != stamp:
            pending[plugin_id] = (plugin.setup, stamp)
    return pending


def installer_packages(pacman_log: Path, install_log: Path) -> set[str]:
    """Packages Omarchy's installer asked pacman for, including hardware-specific ones
    its shipped lists leave out. The installer's log stops changing when it finishes."""
    finished = datetime.fromtimestamp(install_log.stat().st_mtime, UTC)
    packages: set[str] = set()
    for line in pacman_log.read_text().splitlines():
        run = PACMAN_RUN.match(line)
        if run is None:
            continue
        if datetime.fromisoformat(run["time"]) > finished:
            break
        packages.update(
            argument
            for argument in run["command"].split()[1:]
            if PACKAGE_NAME.fullmatch(argument)
        )
    return packages


def maintenance_packages(omarchy_bin: Path) -> set[str]:
    """Packages Omarchy's update commands install on demand, such as fwupd for firmware.
    Its opt-in installers are left out, since those record choices worth declaring."""
    return {
        package
        for script in omarchy_bin.glob("omarchy-update-*")
        for run in PKG_ADD.finditer(script.read_text())
        for package in run[1].split()
    }


def undeclared_packages(
    declared: dict[str, str], pacman_log: Path, install_log: Path
) -> set[str]:
    """Explicitly installed packages that neither Omarchy nor the manifest accounts for."""
    explicit = subprocess.run(
        ["pacman", "-Qqe"], check=True, capture_output=True, text=True
    ).stdout.split()
    omarchy_path = Path(os.environ["OMARCHY_PATH"])
    listed = {
        line.split("#", 1)[0].strip()
        for package_list in (omarchy_path / "install").glob("*.packages")
        for line in package_list.read_text().splitlines()
    }
    return (
        set(explicit)
        - listed
        - installer_packages(pacman_log, install_log)
        - maintenance_packages(omarchy_path / "bin")
        - set(declared)
    )


def source_commands(
    declared: dict[str, str | None],
    installed: set[str],
    install: list[str],
    remove: list[str],
) -> list[list[str]]:
    commands: list[list[str]] = []
    for name, url in declared.items():
        if url is not None and name not in installed:
            commands.append([*install, url])
        elif url is None and name in installed:
            commands.append([*remove, name])
    return commands


def unconverged(declared: dict[str, str | None], installed: set[str]) -> list[str]:
    return [
        name
        for name, url in declared.items()
        if (url is not None) != (name in installed)
    ]


def reconcile(
    manifest: Manifest, *, check: bool, pacman_log: Path, install_log: Path
) -> None:
    install = [
        name
        for name, state in manifest.packages.items()
        if state == "present" and not package_installed(name)
    ]
    install_aur = [
        name
        for name, state in manifest.aur.items()
        if state == "present" and not package_installed(name)
    ]
    drop = [
        name
        for name, state in (manifest.packages | manifest.aur).items()
        if state == "absent" and package_installed(name)
    ]
    themes = installed_themes()
    plugins = installed_plugins()

    commands: list[list[str]] = []
    if install:
        commands.append(["omarchy", "pkg", "add", *install])
    if install_aur:
        commands.append(["omarchy", "pkg", "aur", "add", *install_aur])
    if drop:
        commands.append(["omarchy", "pkg", "drop", *drop])
    commands += source_commands(
        manifest.themes,
        themes,
        ["omarchy", "theme", "install"],
        ["omarchy", "theme", "remove"],
    )
    plugin_sources = {
        plugin_id: None if plugin is None else plugin.source
        for plugin_id, plugin in manifest.plugins.items()
    }
    commands += source_commands(
        plugin_sources,
        plugins,
        ["omarchy", "plugin", "add", "--yes"],
        ["omarchy", "plugin", "remove", "--yes"],
    )

    for command in commands:
        print(shlex.join(command), flush=True)
        if not check:
            subprocess.run(command, check=True)

    if check:
        undeclared = [
            *(
                f"package: {name}"
                for name in sorted(
                    undeclared_packages(
                        manifest.packages | manifest.aur, pacman_log, install_log
                    )
                )
            ),
            *(
                f"theme: {name}"
                for name in sorted(themes - set(manifest.themes) - generated_themes())
            ),
            *(f"plugin: {name}" for name in sorted(plugins - set(manifest.plugins))),
        ]
        for entry in undeclared:
            print(f"undeclared {entry}")
    elif commands:
        # A theme's name comes from its URL and a plugin's id from its manifest, so a
        # declaration keyed differently would otherwise reinstall on every run.
        mismatched = [
            *(
                f"theme {name}"
                for name in unconverged(manifest.themes, installed_themes())
            ),
            *(
                f"plugin {name}"
                for name in unconverged(plugin_sources, installed_plugins())
            ),
        ]
        if mismatched:
            raise SystemExit(
                f"declared name does not match what Omarchy installed: {', '.join(mismatched)}"
            )

    if not check:
        for plugin_id, plugin in manifest.plugins.items():
            if plugin is None:
                (SETUP_STATE / plugin_id).unlink(missing_ok=True)

    for plugin_id, (setup, stamp) in pending_setups(manifest.plugins).items():
        print(f"setup {plugin_id}", flush=True)
        if not check:
            subprocess.run(
                ["bash", "-c", setup], cwd=PLUGINS_DIR / plugin_id, check=True
            )
            SETUP_STATE.mkdir(parents=True, exist_ok=True)
            (SETUP_STATE / plugin_id).write_text(stamp)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pacman-log", type=Path, default=Path("/var/log/pacman.log"))
    parser.add_argument(
        "--install-log", type=Path, default=Path("/var/log/omarchy-install.log")
    )
    args = parser.parse_args()
    reconcile(
        load_manifest(args.manifest),
        check=args.check,
        pacman_log=args.pacman_log,
        install_log=args.install_log,
    )


if __name__ == "__main__":
    main()
