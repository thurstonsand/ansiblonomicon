#!/usr/bin/env python3
"""Render agent configuration and deliver it with native mise primitives."""
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, cast

import tomlkit
import yaml

HOST_CONFIGS = {
    "Thurstons-MacBook-Pro": "bootstrap/targets/Thurstons-MacBook-Pro/mise.agent-harness.toml",
    "pod042": "bootstrap/targets/pod042/agent-harness/host.toml",
    "ML-DFC6YK6VJQ": "bootstrap/targets/ML-DFC6YK6VJQ/mise.agent-harness.toml",
}
WORK_HOST = "ML-DFC6YK6VJQ"
RENDERERS = {
    "amp": "amp",
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "pi": "pi",
}
SECRET_KEYS = {
    WORK_HOST: {"ANTHROPIC_AUTH_TOKEN"},
    "Thurstons-MacBook-Pro": {"CLI_PROXY_API_KEY", "PARALLEL_API_KEY"},
    "pod042": {"CLI_PROXY_API_KEY", "PARALLEL_API_KEY"},
}
PRIVATE = {
    ".claude/hooks/_config.py",
    ".config/amp/settings.json",
    ".config/opencode/opencode.jsonc",
    ".pi/agent/auth.json",
    ".pi/agent/models.json",
    ".codex/config.toml",
}
EXECUTABLE = {".claude/scripts/statusline.sh", ".local/bin/pi"}


def _mode(relative: str, hostname: str) -> int:
    private = (
        relative in PRIVATE
        or relative == ".claude.json"
        or (hostname == WORK_HOST and relative == ".claude/settings.json")
    )
    return 0o600 if private else 0o755 if relative in EXECUTABLE else 0o644


def _load_module(directory: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, directory / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load renderer {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(cast(dict[str, Any], result[key]), value)
        else:
            result[key] = value
    return result


def load_data(repo: Path, hostname: str, home: Path) -> dict[str, Any]:
    defaults = tomllib.loads((Path(__file__).parent / "data.toml").read_text())
    host_defaults = defaults.pop("host_defaults", {})
    if not isinstance(host_defaults, dict) or not isinstance(
        host_defaults.get(hostname, {}), dict
    ):
        raise ValueError("host_defaults and each host entry must be mappings")
    defaults = _merge(defaults, cast(dict[str, Any], host_defaults.get(hostname, {})))
    models = yaml.safe_load(
        (repo / "bootstrap/capabilities/agent-harness/models.yml").read_text()
    )
    if not isinstance(models, dict):
        raise ValueError("agent configuration data sources must be mappings")
    data = _merge(defaults, models)
    data["developDir"] = data.get("developDir") or str(home / "Develop")
    local = repo / "bootstrap/capabilities/agent-harness/local" / hostname / "data.toml"
    if local.exists():
        raw = tomllib.loads(local.read_text())
        data = _merge(data, raw)
    if not isinstance(data.get("models"), dict) or not isinstance(
        data.get("fonts"), dict
    ):
        raise ValueError("models and fonts must be mappings")
    if not isinstance(data.get("mcp_servers", []), list):
        raise ValueError("mcp_servers must be a list")
    if hostname == WORK_HOST:
        for key in ("work_gateway", "work_models"):
            if not isinstance(data.get(key), dict):
                raise ValueError(f"native private data requires {key} on the work host")
    return data


def _safe_target(home: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe HOME-relative destination: {relative}")
    target = home / path
    parent = target.parent
    while parent != home:
        if parent.is_symlink():
            raise ValueError(f"destination has symlink ancestor: {target}")
        parent = parent.parent
    return target


def target_harnesses(repo: Path, hostname: str) -> list[str]:
    capability = Path(__file__).parent.parent
    host = _load_module(capability, "agent_harness_deploy").load_host(
        repo / HOST_CONFIGS[hostname]
    )
    profile = _load_module(capability, "catalogue").load_profile(repo, host.profile)
    return profile["target_agents"]


def render_all(
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
    harnesses: list[str],
) -> dict[str, str]:
    directory = Path(__file__).parent
    result = _load_module(directory, "instructions").render(
        repo=repo,
        home=home,
        hostname=hostname,
        data=data,
        secrets=secrets,
        harnesses=harnesses,
    )
    for harness in harnesses:
        outputs = _load_module(directory, RENDERERS[harness]).render(
            repo=repo, home=home, hostname=hostname, data=data, secrets=secrets
        )
        overlap = result.keys() & outputs.keys()
        if overlap:
            raise ValueError(f"renderers declare duplicate outputs: {sorted(overlap)}")
        result.update(outputs)
    return result


def _declared_mcp(data: dict[str, Any]) -> list[dict[str, Any]]:
    declared = data.get("mcp_servers", [])
    for item in declared:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("each mcp_servers entry requires a string name")
        transport = item.get("transport", "stdio")
        if transport not in {"stdio", "sse", "http"}:
            raise ValueError(f"unsupported MCP transport: {transport}")
    return declared


def _claude_mcp_output(
    home: Path, data: dict[str, Any], previously_owned: set[str] | None = None
) -> tuple[str, str] | None:
    declared = _declared_mcp(data)
    previously_owned = previously_owned or set()
    if not declared and not previously_owned:
        return None
    desired: dict[str, Any] = {}
    for item in declared:
        transport = item.get("transport", "stdio")
        if transport == "stdio":
            server = {
                "type": "stdio",
                **{key: item[key] for key in ("command", "args", "env") if key in item},
            }
        else:
            server = {"type": transport, "url": item.get("url")}
            if "headers" in item:
                server["headers"] = item["headers"]
        desired[item["name"]] = server
    target = _safe_target(home, ".claude.json")
    if target.is_symlink():
        raise ValueError(f"refusing rendered destination symlink: {target}")
    existing: dict[str, Any] = {}
    if target.exists():
        try:
            value = json.loads(target.read_text())
        except json.JSONDecodeError as error:
            raise ValueError(f"{target}: invalid JSON; refusing MCP update") from error
        if not isinstance(value, dict):
            raise ValueError(f"{target}: expected JSON object")
        existing = value
    servers = existing.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{target}: mcpServers must be an object")
    for name in previously_owned - desired.keys():
        servers.pop(name, None)
    servers.update(desired)
    return ".claude.json", json.dumps(existing, indent=2) + "\n"


def _codex_mcp_config(
    config: str, data: dict[str, Any], previously_owned: set[str]
) -> str:
    desired: dict[str, Any] = {}
    for item in _declared_mcp(data):
        transport = item.get("transport", "stdio")
        if transport == "sse":
            raise ValueError(f"Codex does not support SSE MCP server {item['name']}")
        if transport == "stdio":
            server = {
                key: item[key] for key in ("command", "args", "env") if key in item
            }
        else:
            server = {"url": item.get("url")}
            if "headers" in item:
                server["http_headers"] = item["headers"]
        desired[item["name"]] = server
    document = tomlkit.parse(config)
    if not desired and "mcp_servers" not in document:
        return config
    servers = document.setdefault("mcp_servers", tomlkit.table())
    for name in previously_owned - desired.keys():
        servers.pop(name, None)
    servers.update(desired)
    return tomlkit.dumps(document)


def _selected(item: dict[str, Any], hostname: str, harnesses: list[str]) -> bool:
    harness = item.get("harness")
    if harness is not None and harness not in RENDERERS:
        raise ValueError(f"unknown asset harness: {item}")
    hosts = item.get("hosts")
    return (harness is None or harness in harnesses) and (
        hosts is None or hostname in hosts
    )


def _assets(
    repo: Path, hostname: str, harnesses: list[str]
) -> tuple[list[tuple[Path, str]], list[dict[str, Any]], list[str]]:
    manifest = Path(__file__).parent / "assets.toml"
    raw = tomllib.loads(manifest.read_text()) if manifest.exists() else {}
    links: list[tuple[Path, str]] = []
    for item in raw.get("files", []):
        if _selected(item, hostname, harnesses):
            source = Path(__file__).parent / item["source"]
            if not source.is_file() or item.get("mode") != "symlink":
                raise ValueError(f"invalid static asset declaration: {item}")
            links.append((source, item["destination"]))
    local_root = repo / "bootstrap/capabilities/agent-harness/local" / hostname
    local_manifest = local_root / "assets.toml"
    local_raw = (
        tomllib.loads(local_manifest.read_text()) if local_manifest.exists() else {}
    )
    if set(local_raw) - {"files"} or not isinstance(local_raw.get("files", []), list):
        raise ValueError(f"{local_manifest}: only a files array is supported")
    for item in local_raw.get("files", []):
        if not isinstance(item, dict):
            raise ValueError(f"invalid local asset declaration: {item}")
        if not _selected(item, hostname, harnesses):
            continue
        source_value = item.get("source")
        destination = item.get("destination")
        if not isinstance(source_value, str) or not isinstance(destination, str):
            raise ValueError(f"invalid local asset declaration: {item}")
        source_relative = Path(source_value)
        if source_relative.is_absolute() or ".." in source_relative.parts:
            raise ValueError(f"unsafe local asset source: {source_value}")
        source = local_root / source_relative
        if (
            item.get("mode") != "symlink"
            or not source.is_file()
            or not source.resolve().is_relative_to(local_root.resolve())
        ):
            raise ValueError(f"invalid local asset declaration: {item}")
        # Validate here so a malformed local manifest is rejected before staging.
        _safe_target(Path("/home"), destination)
        links.append((source, destination))
    packages = [p for p in raw.get("packages", []) if _selected(p, hostname, harnesses)]
    absent = [p["destination"] for p in raw.get("absent", [])]
    return links, packages, absent


def _fingerprint(path: Path) -> str | None:
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_file():
        return "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def _private_dir(path: Path, stop: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = path
    while current != stop and current.is_relative_to(stop):
        current.chmod(0o700)
        current = current.parent


def _native_env(target: Path, state: Path, home: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
        "MISE_STATE_DIR": str(state),
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "MISE_GLOBAL_CONFIG_FILE": str(target / ".global.toml"),
        "MISE_SYSTEM_CONFIG_FILE": str(target / ".system.toml"),
    }


def _apply_native(target: Path, state: Path, home: Path, check: bool) -> None:
    env = _native_env(target, state, home)
    subprocess.run(
        [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "dotfiles",
            "apply",
            "--force",
            *(["--dry-run"] if check else ["--yes"]),
        ],
        check=True,
        env=env,
    )
    subprocess.run(
        [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "files",
            "apply",
            *(["--dry-run"] if check else ["--yes"]),
        ],
        check=True,
        env=env,
    )


def _stage_native(
    target: Path,
    rendered: Path,
    outputs: dict[str, str],
    links: list[tuple[Path, str]],
    home: Path,
    hostname: str,
    stale: set[Path],
) -> None:
    rendered.mkdir(parents=True, exist_ok=True)
    document: dict[str, object] = {
        "min_version": "2026.9.11",
        "dotfiles": {},
        "bootstrap": {"files": {}, "directories": {}},
    }
    dotfiles = cast(dict[str, object], document["dotfiles"])
    files = cast(
        dict[str, object], cast(dict[str, object], document["bootstrap"])["files"]
    )
    directories = cast(
        dict[str, object], cast(dict[str, object], document["bootstrap"])["directories"]
    )
    directories[str(home / ".pi/agent")] = {"mode": "0700"}
    if any(relative.startswith(".config/amp/") for relative in outputs):
        directories[str(home / ".config/amp")] = {"mode": "0700"}
    directories[str(home / ".cache/ansiblonomicon-harness/configuration")] = {
        "mode": "0700"
    }
    for index, (relative, content) in enumerate(sorted(outputs.items())):
        source = rendered / str(index)
        source.write_text(content)
        source.chmod(_mode(relative, hostname))
        file_mode = _mode(relative, hostname)
        if file_mode == 0o644:
            dotfiles[str(home / relative)] = {"source": str(source), "mode": "copy"}
        else:
            parent = (home / relative).parent
            if parent != home and parent not in {
                home / ".pi/agent",
                home / ".config/amp",
            }:
                parent_mode = (
                    stat.S_IMODE(parent.stat().st_mode) if parent.exists() else 0o755
                )
                directories.setdefault(str(parent), {"mode": f"{parent_mode:04o}"})
            files[str(home / relative)] = {
                "source": str(source),
                "mode": f"{file_mode:04o}",
            }
    for source, relative in links:
        dotfiles[str(home / relative)] = {"source": str(source), "mode": "symlink"}
    for path in sorted(stale):
        if path.is_dir() and not path.is_symlink():
            retired_directories = [path]
            for root, names, leaves in os.walk(path, followlinks=False):
                current = Path(root)
                for name in leaves:
                    files[str(current / name)] = {"state": "absent"}
                for name in list(names):
                    child = current / name
                    if child.is_symlink():
                        files[str(child)] = {"state": "absent"}
                        names.remove(name)
                    else:
                        retired_directories.append(child)
            for directory in retired_directories:
                directories[str(directory)] = {
                    "state": "absent",
                    "recursive": False,
                }
        else:
            files[str(path)] = {"state": "absent"}
    (target / "mise.toml").write_text(tomlkit.dumps(document))


def _read_inventory(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError(f"{path}: invalid ownership manifest")
    return cast(dict[str, str], value)


def _read_owned_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    value = json.loads(path.read_text())
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path}: invalid MCP ownership manifest")
    return set(value)


def reconcile(
    *, repo: Path, home: Path, hostname: str, secrets: dict[str, str], check: bool
) -> int:
    if hostname not in HOST_CONFIGS:
        raise ValueError(f"unsupported agent configuration host: {hostname}")
    data = load_data(repo, hostname, home)
    harnesses = target_harnesses(repo, hostname)
    outputs = render_all(repo, home, hostname, data, secrets, harnesses)
    state_dir = home / ".cache/ansiblonomicon-harness/configuration"
    mcp_ownership = state_dir / "mcp-owned.json"
    previously_owned_mcp = _read_owned_names(mcp_ownership)
    if "claude" in harnesses:
        mcp = _claude_mcp_output(home, data, previously_owned_mcp)
        if mcp:
            outputs[mcp[0]] = mcp[1]
    if ".codex/config.toml" in outputs:
        outputs[".codex/config.toml"] = _codex_mcp_config(
            outputs[".codex/config.toml"], data, previously_owned_mcp
        )
    links, packages, absent = _assets(repo, hostname, harnesses)
    package_states: list[tuple[Path, list[str], str, Path, Path | None]] = []
    for package in packages:
        source = Path(__file__).parent / package["source"]
        destination = _safe_target(home, package["destination"])
        lock = source / "package-lock.json"
        command = ["npm", "ci" if lock.exists() else "install"]
        if not lock.exists():
            command.append("--package-lock=false")
        if hostname == WORK_HOST and package.get("work_omit_dev"):
            command.append("--omit=dev")
        metadata = json.loads((source / "package.json").read_text())
        production_dependencies = metadata.get("dependencies", {})
        needs_modules = not (
            hostname == WORK_HOST
            and package.get("work_omit_dev")
            and not production_dependencies
        )
        identity = source.relative_to(Path(__file__).parent).as_posix()
        digest = hashlib.sha256(
            (identity + "\0" + "\0".join(command)).encode()
            + (source / "package.json").read_bytes()
            + (lock.read_bytes() if lock.exists() else b"")
        ).hexdigest()
        stamp = state_dir / (
            "npm-" + hashlib.sha256(identity.encode()).hexdigest()[:16] + ".sha256"
        )
        module_source = source / "node_modules"
        package_states.append(
            (source, command, digest, stamp, destination if needs_modules else None)
        )
        if needs_modules:
            links.append((module_source, package["destination"]))
    declarations = list(outputs) + [relative for _, relative in links]
    if len(declarations) != len(set(declarations)):
        raise ValueError("conflicting native destination declarations")
    targets = {relative: _safe_target(home, relative) for relative in declarations}
    package_destinations = {package["destination"] for package in packages}
    for relative, target in targets.items():
        if target.is_dir() and not target.is_symlink():
            if relative not in package_destinations:
                raise ValueError(f"refusing to replace directory target: {target}")
        elif (
            relative in package_destinations
            and target.exists()
            and not target.is_symlink()
        ):
            raise ValueError(
                f"refusing to replace non-directory package target: {target}"
            )
        if relative in outputs and target.is_symlink():
            raise ValueError(f"refusing rendered destination symlink: {target}")

    ownership = state_dir / "owned.json"
    previous = _read_inventory(ownership)
    # .claude.json is app-owned and only its declared MCP names are managed.
    previous.pop(".claude.json", None)
    previous_targets = {relative: _safe_target(home, relative) for relative in previous}
    absent_targets = {_safe_target(home, relative) for relative in absent}
    desired_fingerprints = {
        relative: "file:" + hashlib.sha256(content.encode()).hexdigest()
        for relative, content in outputs.items()
    }
    desired_fingerprints.update(
        {relative: "link:" + str(source) for source, relative in links}
    )
    stale = {
        previous_targets[relative]
        for relative, proof in previous.items()
        if relative not in targets and _fingerprint(previous_targets[relative]) == proof
    } | absent_targets
    changed = any(
        _fingerprint(targets[relative]) != proof
        or (
            relative in outputs
            and targets[relative].is_file()
            and stat.S_IMODE(targets[relative].stat().st_mode)
            != _mode(relative, hostname)
        )
        for relative, proof in desired_fingerprints.items()
    ) or any(_fingerprint(path) is not None or path.is_dir() for path in stale)

    for source, _, digest, stamp, destination in package_states:
        missing_modules = (
            destination is not None and not (source / "node_modules").is_dir()
        )
        if check and missing_modules:
            print(
                f"missing source dependencies: {source / 'node_modules'}",
                file=sys.stderr,
            )
        changed |= (
            missing_modules
            or not stamp.exists()
            or stamp.read_text().strip() != digest
            or (
                destination is not None
                and (
                    not destination.is_symlink()
                    or destination.resolve() != (source / "node_modules").resolve()
                )
            )
        )

    # Everything which can reject the plan has now run. Check stages outside HOME.
    if check:
        available_links = [
            (source, relative)
            for source, relative in links
            if source.exists() or relative not in package_destinations
        ]
        with tempfile.TemporaryDirectory(
            prefix="agent-configuration-check-"
        ) as temporary:
            root = Path(temporary)
            _stage_native(
                root,
                root / "rendered",
                outputs,
                available_links,
                home,
                hostname,
                stale,
            )
            _apply_native(root, root / "state", root / "home", True)
        return int(changed)

    _private_dir(state_dir, home / ".cache")
    backup = state_dir / "backups"
    for relative, target in targets.items():
        if relative in package_destinations:
            continue
        if relative not in previous and (target.exists() or target.is_symlink()):
            destination = backup / relative
            _private_dir(destination.parent, home / ".cache")
            if not destination.exists() and not destination.is_symlink():
                if target.is_symlink():
                    destination.symlink_to(os.readlink(target))
                else:
                    shutil.copy2(target, destination)
                    destination.chmod(0o600)
    native = state_dir / "native"
    rendered = state_dir / "rendered"
    _private_dir(native, home / ".cache")
    _private_dir(rendered, home / ".cache")
    # Install at the canonical source before publishing links to its dependency tree.
    for source, command, digest, stamp, destination in package_states:
        if (
            (destination is not None and not (source / "node_modules").is_dir())
            or not stamp.exists()
            or stamp.read_text().strip() != digest
        ):
            subprocess.run(command, cwd=source, check=True)
            stamp.write_text(digest + "\n")
            stamp.chmod(0o600)
    _stage_native(native, rendered, outputs, links, home, hostname, stale)
    _apply_native(native, state_dir / "mise-state", home, False)
    current = {
        relative: _fingerprint(target)
        for relative, target in targets.items()
        if relative != ".claude.json"
    }
    inventory = {
        relative: proof for relative, proof in current.items() if proof is not None
    }
    ownership.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    ownership.chmod(0o600)
    declared_mcp = sorted(
        item["name"] for item in data.get("mcp_servers", []) if isinstance(item, dict)
    )
    mcp_ownership.write_text(json.dumps(declared_mcp, indent=2) + "\n")
    mcp_ownership.chmod(0o600)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--real-secrets", action="store_true")
    args = parser.parse_args(argv)
    keys = SECRET_KEYS[args.hostname]
    secrets = {key: os.environ.get(key, f"CHECK_PLACEHOLDER_{key}") for key in keys}
    missing = [key for key in keys if key not in os.environ]
    if missing and (not args.check or args.real_secrets):
        parser.error("missing resolved secrets: " + ", ".join(missing))
    result = reconcile(
        repo=args.repo.resolve(),
        home=args.home.resolve(),
        hostname=args.hostname,
        secrets=secrets,
        check=args.check,
    )
    if missing:
        print(
            "secret-backed outputs were validated with placeholders; content parity is "
            "unresolved (rerun --check --real-secrets)",
            file=sys.stderr,
        )
        return 2
    return result


if __name__ == "__main__":
    sys.exit(main())
