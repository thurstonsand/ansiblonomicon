#!/usr/bin/env python3
"""Reconcile the declared macOS runtimes and global language tools."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import tomllib
from typing import TypeAlias, TypeGuard, cast

INTERVAL = 86400
LIST_SECTIONS = {
    "npm": ("packages", "allow_scripts"),
    "uv": ("packages", "retired"),
    "bun": ("packages",),
    "go": ("packages",),
    "cargo": ("packages",),
    "gem": ("packages",),
}

Scalar: TypeAlias = str | bool | int | float  # noqa: UP040 -- runs on Python 3.11
ConfigValue: TypeAlias = Scalar | dict[str, "ConfigValue"]  # noqa: UP040
ToolEntry: TypeAlias = dict[str, ConfigValue]  # noqa: UP040


@dataclass
class Inventory:
    tools: dict[str, ToolEntry]
    sections: dict[str, dict[str, list[str]]]


def npm_package_name(spec: str) -> str:
    if spec.startswith("@"):
        slash = spec.find("/")
        at = spec.find("@", slash)
        return spec if at < 0 else spec[:at]
    return spec.split("@", 1)[0]


def npm_tree(command: list[str], prefix: Path, *, cwd: Path) -> dict[str, object]:
    output = run(
        [
            *command,
            "list",
            "-g",
            "--depth=0",
            "--json",
            "--prefix",
            str(prefix),
        ],
        cwd=cwd,
        capture=True,
    )
    parsed = json.loads(output)
    return table(
        parsed.get("dependencies", {}), "npm returned malformed global inventory"
    )


def pending_npm_extras(pending: Path) -> dict[str, str]:
    saved = table(
        json.loads(pending.read_text()), f"invalid pending npm inventory {pending}"
    )
    result: dict[str, str] = {}
    for name, version in saved.items():
        if not isinstance(version, str):
            raise SystemExit(f"invalid pending npm inventory {pending}")
        result[name] = version
    return result


def capture_npm_extras(
    mise: str, pending: Path, managed: list[str], home: Path
) -> None:
    if pending.exists():
        # A failed run's old prefix is authoritative; never replace it after mise
        # may already have selected a different Node.
        pending_npm_extras(pending)
        return
    raw: object = json.loads(
        run([mise, "ls", "--current", "--json", "node"], cwd=home, capture=True)
    )
    if not isinstance(raw, list) or not raw:
        return
    raw_entries = cast(list[object], raw)
    entries = [
        entry for entry in raw_entries if is_table(entry) and entry.get("active")
    ]
    if not entries:
        return
    entry = entries[0]
    if not entry.get("installed") or not isinstance(entry.get("install_path"), str):
        return
    prefix = Path(cast(str, entry["install_path"]))
    dependencies = npm_tree(
        [str(prefix / "bin/node"), str(prefix / "lib/node_modules/npm/bin/npm-cli.js")],
        prefix,
        cwd=home,
    )
    excluded = {npm_package_name(spec) for spec in managed} | {"npm", "corepack"}
    saved: dict[str, str] = {}
    for name, raw_package in dependencies.items():
        if name in excluded:
            continue
        package = table(raw_package, f"unsupported npm global source for {name}")
        version = package.get("version")
        resolved = package.get("resolved")
        if (
            not isinstance(version, str)
            or package.get("link") is True
            or (isinstance(resolved, str) and resolved.startswith(("file:", "link:")))
        ):
            raise SystemExit(f"unsupported npm global source for {name}")
        saved[name] = version
    if saved:
        pending.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=pending.parent, delete=False
        ) as temporary:
            temporary.write(json.dumps(saved, sort_keys=True) + "\n")
        os.replace(temporary.name, pending)


def restore_npm_extras(pending: Path, npm: str, home: Path) -> None:
    if not pending.exists():
        return
    saved = pending_npm_extras(pending)
    prefix_text = run([npm, "prefix", "-g"], cwd=home, capture=True)
    prefix = Path(prefix_text)
    current = npm_tree([npm], prefix, cwd=home)
    specs: list[str] = []
    for name, version in saved.items():
        package = current.get(name)
        if not is_table(package) or package.get("version") != version:
            specs.append(f"{name}@{version}")
    if specs:
        run([npm, "install", "-g", "--prefix", str(prefix), *specs], cwd=home)


def run(command: list[str], *, cwd: Path, capture: bool = False) -> str:
    result = subprocess.run(
        command, cwd=cwd, check=True, text=True, capture_output=capture
    )
    return result.stdout.strip() if capture else ""


def empty_inventory() -> Inventory:
    return Inventory(
        tools={},
        sections={
            "npm": {"packages": [], "allow_scripts": []},
            "uv": {"packages": [], "retired": []},
            "bun": {"packages": []},
            "go": {"packages": []},
            "cargo": {"packages": []},
            "gem": {"packages": []},
        },
    )


def is_table(value: object) -> TypeGuard[dict[str, object]]:
    if not isinstance(value, dict):
        return False
    raw = cast(dict[object, object], value)
    return all(isinstance(key, str) for key in raw)


def table(value: object, message: str) -> dict[str, object]:
    if not is_table(value):
        raise SystemExit(message)
    return value


def string_list(value: object, message: str) -> list[str]:
    if not isinstance(value, list):
        raise SystemExit(message)
    raw = cast(list[object], value)
    if any(not isinstance(item, str) for item in raw):
        raise SystemExit(message)
    return cast(list[str], raw)


def read_source(path: Path) -> tuple[Inventory, bool]:
    try:
        parsed = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SystemExit(f"invalid inventory {path}: {error}") from error
    data: dict[str, object] = parsed
    allowed = {"inventory", "tools", *LIST_SECTIONS}
    unknown = set(data) - allowed
    if unknown:
        raise SystemExit(
            f"invalid inventory {path}: unknown sections {sorted(unknown)}"
        )
    inventory_options = table(
        data.get("inventory", {}),
        f"invalid inventory {path}: [inventory] must contain only boolean replace_shared",
    )
    replace_shared = inventory_options.get("replace_shared", False)
    if set(inventory_options) - {"replace_shared"} or not isinstance(
        replace_shared, bool
    ):
        raise SystemExit(
            f"invalid inventory {path}: [inventory] must contain only boolean replace_shared"
        )
    result = empty_inventory()
    tools = table(
        data.get("tools", {}), f"invalid inventory {path}: [tools] must be a table"
    )
    for name, raw_entry in tools.items():
        if "." in name:
            raise SystemExit(
                f"invalid inventory {path}: tool names containing dots are unsupported"
            )
        entry = table(
            raw_entry, f"invalid inventory {path}: tools.{name} needs a string version"
        )
        if not isinstance(entry.get("version"), str):
            raise SystemExit(
                f"invalid inventory {path}: tools.{name} needs a string version"
            )
        result.tools[name] = validate_tool_entry(entry, f"tools.{name}", path)
    for section, keys in LIST_SECTIONS.items():
        value = table(
            data.get(section, {}),
            f"invalid inventory {path}: malformed [{section}] table",
        )
        if set(value) - set(keys):
            raise SystemExit(f"invalid inventory {path}: malformed [{section}] table")
        for key, entries in value.items():
            result.sections[section][key] = string_list(
                entries,
                f"invalid inventory {path}: {section}.{key} must be a string array",
            )
    return result, replace_shared


def validate_tool_entry(value: dict[str, object], key: str, path: Path) -> ToolEntry:
    result: ToolEntry = {}
    for raw_child, nested in value.items():
        if "." in raw_child:
            raise SystemExit(
                f"invalid inventory {path}: literal-dot key at {key} is unsupported"
            )
        child_key = f"{key}.{raw_child}"
        if is_table(nested):
            result[raw_child] = validate_tool_entry(
                nested,
                child_key,
                path,
            )
        elif isinstance(nested, list):
            raise SystemExit(
                f"invalid inventory {path}: list value at {child_key} is unsupported by mise config set"
            )
        elif isinstance(nested, (str, bool, int, float)):
            result[raw_child] = nested
        else:
            raise SystemExit(
                f"invalid inventory {path}: unsupported value at {child_key}"
            )
    return result


def load(paths: list[Path]) -> Inventory:
    result = empty_inventory()
    for path in paths:
        data, replace_shared = read_source(path)
        if replace_shared:
            result = empty_inventory()
        result.tools.update(data.tools)
        for section, keys in LIST_SECTIONS.items():
            for key in keys:
                result.sections[section][key].extend(data.sections[section][key])
    return result


def leaves(value: dict[str, ConfigValue], prefix: str = "") -> list[tuple[str, Scalar]]:
    result: list[tuple[str, Scalar]] = []
    for key, child in value.items():
        name = f"{prefix}.{key}" if prefix else key
        result.extend(
            leaves(child, name) if isinstance(child, dict) else [(name, child)]
        )
    return result


def config_set(mise: str, config: Path, key: str, value: Scalar, home: Path) -> None:
    kind = {str: "string", bool: "bool", int: "integer", float: "float"}[type(value)]
    rendered = str(value).lower() if isinstance(value, bool) else str(value)
    run(
        [mise, "config", "set", "--file", str(config), key, "--type", kind, rendered],
        cwd=home,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("personal", "work"), required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extension", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.profile == "work" and (
        args.extension is None or not args.extension.is_file()
    ):
        raise SystemExit(
            "work migration requires an explicit private TOML inventory (an empty file is valid)"
        )
    if args.extension is not None and not args.extension.is_file():
        raise SystemExit(f"inventory does not exist: {args.extension}")
    sources = [root / "tools.toml", root / f"tools.{args.profile}.toml"] + (
        [args.extension] if args.extension else []
    )
    inventory = load(sources)
    home = Path.home()
    config = home / ".config/mise/config.toml"
    current: dict[str, object] = (
        tomllib.loads(config.read_text()) if config.exists() else {}
    )
    npm_script = root / "npm-globals.py"
    packages = inventory.sections["npm"]["packages"]
    allow_scripts = ",".join(sorted(set(inventory.sections["npm"]["allow_scripts"])))
    postinstall = (
        'PATH="$MISE_TOOL_INSTALL_PATH/bin:$PATH" '
        '"$MISE_TOOL_INSTALL_PATH/bin/npm" install -g '
        + shlex.join([f"--allow-scripts={allow_scripts}", *packages])
    )
    desired_tools = {name: dict(entry) for name, entry in inventory.tools.items()}
    if packages and "node" in desired_tools:
        desired_tools["node"]["postinstall"] = postinstall
    desired_leaves = [
        leaf
        for name, entry in desired_tools.items()
        for leaf in leaves(entry, f"tools.{name}")
    ]
    changed_keys: list[str] = []
    for key, value in desired_leaves:
        cursor: object = current
        for part in key.split("."):
            cursor = cursor.get(part) if is_table(cursor) else None
        if cursor != value:
            changed_keys.append(key)
    stamp = home / ".cache/ansiblonomicon/language-tools.stamp"
    fingerprint = hashlib.sha256(
        json.dumps(
            {"tools": inventory.tools, "sections": inventory.sections}, sort_keys=True
        ).encode()
    ).hexdigest()
    due = (
        not stamp.exists()
        or stamp.read_text().strip() != fingerprint
        or time.time() - stamp.stat().st_mtime >= INTERVAL
    )
    tools = list(inventory.tools)
    specs = [f"{tool}@{entry['version']}" for tool, entry in inventory.tools.items()]
    if args.check:
        print(
            f"language-tools: config set {', '.join(changed_keys) if changed_keys else 'none'}"
        )
        print(
            f"language-tools: ensure installed {', '.join(specs) if specs else 'none'}"
        )
        print(
            "language-tools: managed upgrades due"
            if due
            else "language-tools: managed upgrades current"
        )
        return

    mise = os.environ.get("MISE_BIN", str(home / ".local/bin/mise"))
    pending = home / ".cache/ansiblonomicon/npm-globals.pending.json"
    capture_npm_extras(mise, pending, packages, home)
    config.parent.mkdir(parents=True, exist_ok=True)
    if not config.exists():
        config.touch()
    for key, value in desired_leaves:
        if key in changed_keys:
            config_set(mise, config, key, value, home)
    run([mise, "trust", "--yes", str(config)], cwd=home)
    if tools:
        run([mise, "install", "--yes", *tools], cwd=home)
        if due:
            run([mise, "upgrade", "--yes", "--no-prune", *tools], cwd=home)

    # Only the declared install/upgrade above may install runtimes. The effective
    # global environment supplies Node/npm and private managers, not repo tools.
    os.environ["MISE_AUTO_INSTALL"] = "0"
    environment = json.loads(run([mise, "env", "--json"], cwd=home, capture=True))
    os.environ.update(environment)
    prefix = os.environ.get("HOMEBREW_PREFIX", "/opt/homebrew")
    os.environ["PATH"] = (
        f"{prefix}/opt/zig@0.15/bin:{home}/.cargo/bin:{os.environ['PATH']}"
    )

    npm_exec = [
        sys.executable,
        str(npm_script),
        *(["--present"] if not due else []),
        "npm",
        *map(str, sources),
    ]
    if packages:
        run(npm_exec, cwd=home)
    restore_npm_extras(pending, "npm", home)
    if inventory.sections["uv"]["retired"]:
        tool_dir = Path(run(["uv", "tool", "dir"], cwd=home, capture=True))
        for tool in inventory.sections["uv"]["retired"]:
            if (tool_dir / tool).exists():
                run(["uv", "tool", "uninstall", tool], cwd=home)
    if due:
        for tool in inventory.sections["uv"]["packages"]:
            run(["uv", "tool", "install", "--upgrade", tool], cwd=home)
        for package in inventory.sections["bun"]["packages"]:
            run(["bun", "install", "--global", package], cwd=home)
        for tool in inventory.sections["go"]["packages"]:
            run(["go", "install", tool if "@" in tool else f"{tool}@latest"], cwd=home)
        if inventory.sections["cargo"]["packages"]:
            run(["rustup", "default", "stable"], cwd=home)
            run(["cargo", "install", "cargo-binstall"], cwd=home)
            for package in inventory.sections["cargo"]["packages"]:
                run(["cargo", "binstall", "--no-confirm", package], cwd=home)
            if "bob-nvim" in inventory.sections["cargo"]["packages"]:
                run([str(home / ".cargo/bin/bob"), "use", "stable"], cwd=home)
        gem = os.environ.get("LANGUAGE_TOOLS_GEM", f"{prefix}/opt/ruby/bin/gem")
        for package in inventory.sections["gem"]["packages"]:
            run([gem, "install", package], cwd=home)
    if "bob-nvim" in inventory.sections["cargo"]["packages"]:
        target = home / ".local/share/bob/nvim-bin/nvim"
        link = home / ".local/bin/nvim"
        if not link.is_symlink() or link.readlink() != target:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.unlink(missing_ok=True)
            link.symlink_to(target)
    if due:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(fingerprint + "\n")
        stamp.chmod(0o644)
    pending.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
