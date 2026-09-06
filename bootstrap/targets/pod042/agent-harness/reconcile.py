#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["jinja2>=3.1,<4", "pyyaml>=6,<7"]
# ///
"""Native pod042 file reconciliation using the shared harness resolver."""

import argparse
from collections.abc import Callable
import fnmatch
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from typing import TypedDict, cast

import jinja2
import yaml

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[4]
        / "ansible/roles/agent_harness/filter_plugins"
    ),
)
import harness_filters as filters
from harness_filters import SourceConfig

REPO = Path(__file__).resolve().parents[4]
HOME = Path("/home/thurstonsand")


class Profile(TypedDict):
    target_agents: list[str]
    explicit_only: list[str]


class Layout(TypedDict):
    skills_dir: str
    agents_dir: str | None
    name_transform: str


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Expected a mapping")
    entries = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in entries):
        raise ValueError("Expected string mapping keys")
    return cast(dict[str, object], entries)


def strings(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Expected a list of strings")
    entries = cast(list[object], value)
    if not all(isinstance(entry, str) for entry in entries):
        raise ValueError("Expected a list of strings")
    return cast(list[str], entries)


def environment(repo: Path, home: Path) -> jinja2.Environment:
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, keep_trailing_newline=True
    )

    def matches(value: str, pattern: str) -> bool:
        return re.match(pattern, value) is not None

    cast(dict[str, Callable[..., object]], env.tests)["match"] = matches

    def lookup(kind: str, path: str) -> str:
        if kind != "file":
            raise ValueError(f"Unsupported harness template lookup: {kind}")
        source = Path(path).resolve()
        if not source.is_relative_to(repo.resolve()):
            raise ValueError(f"Template lookup escapes checkout: {source}")
        return source.read_text().rstrip("\n")

    cast(dict[str, object], env.globals).update(
        ansible_facts={"env": {"HOME": str(home)}},
        ansible_hostname="pod042",
        playbook_dir=str(repo / "ansible/playbooks"),
        lookup=lookup,
    )
    return env


def declarations(
    repo: Path, home: Path
) -> tuple[jinja2.Environment, Profile, dict[str, Layout], list[SourceConfig]]:
    env = environment(repo, home)
    config = mapping(
        yaml.safe_load(
            env.from_string(
                (repo / "ansible/agent-harness.config.yml").read_text()
            ).render()
        )
    )
    raw_layouts = mapping(
        mapping(
            yaml.safe_load(
                env.from_string(
                    (repo / "ansible/roles/agent_harness/vars/agents.yml").read_text()
                ).render()
            )
        )["agent_harness_agents"]
    )
    layouts: dict[str, Layout] = {}
    for name, value in raw_layouts.items():
        entry = mapping(value)
        skills_dir = entry["skills_dir"]
        agents_dir = entry["agents_dir"]
        transform = entry["name_transform"]
        if (
            not isinstance(skills_dir, str)
            or not isinstance(transform, str)
            or not (agents_dir is None or isinstance(agents_dir, str))
        ):
            raise ValueError(f"Invalid harness layout: {name}")
        layouts[name] = {
            "skills_dir": skills_dir,
            "agents_dir": agents_dir,
            "name_transform": transform,
        }
    profiles = mapping(config["agent_harness_profiles"])
    raw_profile = mapping(profiles["pod042"])
    profile: Profile = {
        "target_agents": strings(raw_profile["target_agents"]),
        "explicit_only": strings(raw_profile.get("explicit_only", [])),
    }
    raw_sources = config["agent_harness_sources"]
    if not isinstance(raw_sources, list):
        raise ValueError("Expected harness source list")
    sources = filters.agent_harness_resolve_sources(
        [mapping(source) for source in cast(list[object], raw_sources)],
        "pod042",
        list(profiles),
        list(layouts),
    )
    return env, profile, layouts, sources


def sync_sources(sources: list[SourceConfig], cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for source in sources:
        if "repo" not in source or not source["plugins"]:
            continue
        origin = source["repo"]
        checkout = cache / filters.agent_harness_repo_to_cache_name(origin)
        url = origin if ":" in origin else f"https://github.com/{origin}.git"
        if not checkout.exists():
            subprocess.run(
                ["git", "clone", "--depth=1", url, str(checkout)], check=True
            )
        else:
            subprocess.run(
                ["git", "-C", str(checkout), "pull", "--ff-only"], check=True
            )


def excluded(path: Path, patterns: list[str]) -> bool:
    return any(part in {".git", ".claude-plugin"} for part in path.parts) or any(
        fnmatch.fnmatch(path.as_posix(), pattern.lstrip("/"))
        or any(fnmatch.fnmatch(part, pattern) for part in path.parts)
        for pattern in patterns
    )


def render_files(repo: Path, home: Path, cache: Path) -> dict[Path, tuple[bytes, int]]:
    env, profile, layouts, sources = declarations(repo, home)
    resources = filters.agent_harness_build_plugin_resources(sources, str(cache))
    models = mapping(
        mapping(yaml.safe_load((repo / "ansible/models.yml").read_text()))["models"]
    )
    files: dict[Path, tuple[bytes, int]] = {}

    def add(path: Path, content: bytes, mode: int) -> None:
        if path in files:
            raise ValueError(f"Duplicate harness destination: {path}")
        if not path.is_relative_to(home) or path == home:
            raise ValueError(f"Harness destination escapes operator home: {path}")
        files[path] = (content, mode)

    for target in profile["target_agents"]:
        layout = layouts[target]
        for kind in ("skills", "agents"):
            destination = (
                layout["skills_dir"] if kind == "skills" else layout["agents_dir"]
            )
            if destination is None:
                continue
            selected = filters.agent_harness_filter_resources(
                resources[kind],
                target,
                layout["name_transform"],
                target in profile.get("explicit_only", []),
            )
            for resource in selected:
                source = Path(resource["source"])
                name = resource["name"]
                if Path(name).name != name or name in {".", ".."}:
                    raise ValueError(f"Invalid harness resource name: {name}")
                if kind == "agents":
                    agent_content = filters.agent_harness_transform_skill(
                        str(source),
                        target,
                        models,
                        resource["plugin_root"],
                        name,
                    )["content"]
                    add(Path(destination) / f"{name}.md", agent_content.encode(), 0o644)
                    continue
                for asset in sorted(source.rglob("*")):
                    relative = asset.relative_to(source)
                    if (
                        excluded(relative, resource["exclude_data"])
                        or not asset.is_file()
                    ):
                        continue
                    if not asset.resolve().is_relative_to(source.resolve()):
                        raise ValueError(f"Skill asset escapes source: {asset}")
                    output = (
                        relative.with_suffix("") if asset.suffix == ".j2" else relative
                    )
                    if (
                        asset.name == "SKILL.md"
                        and asset.with_suffix(".md.j2").exists()
                    ):
                        continue
                    content = asset.read_bytes()
                    if asset.suffix == ".j2":
                        content = env.from_string(content.decode()).render().encode()
                    if output.name == "SKILL.md":
                        content = filters.agent_harness_transform_skill_content(
                            content.decode(),
                            target,
                            models,
                            resource["plugin_root"],
                            name,
                        )["content"].encode()
                    mode = 0o755 if asset.stat().st_mode & 0o111 else 0o644
                    add(Path(destination) / name / output, content, mode)
    for hook in resources["hooks"]:
        if Path(hook["name"]).name != hook["name"]:
            raise ValueError(f"Invalid hook name: {hook['name']}")
        add(cache / "hooks" / f"{hook['name']}.json", hook["content"].encode(), 0o644)
    return files


def reconcile(
    files: dict[Path, tuple[bytes, int]], home: Path, cache: Path, check: bool
) -> None:
    manifest = cache / "pod042-managed-files.json"
    previous = strings(json.loads(manifest.read_text())) if manifest.exists() else []
    stale = set(previous) - {str(path.relative_to(home)) for path in files}
    for relative in sorted(stale):
        path = home / relative
        if not path.resolve().is_relative_to(home.resolve()) or path == home:
            raise ValueError(f"Managed path escapes operator home: {path}")
        if path.is_file() or path.is_symlink():
            print(f"remove {path}")
            if not check:
                path.unlink()
    for path, (content, mode) in sorted(files.items()):
        if not path.resolve().is_relative_to(home.resolve()):
            raise ValueError(f"Destination symlink escapes operator home: {path}")
        if (
            path.is_file()
            and path.read_bytes() == content
            and path.stat().st_mode & 0o777 == mode
        ):
            continue
        print(f"write {path}")
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(mode)
    if not check:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(sorted(str(path.relative_to(home)) for path in files), indent=2)
            + "\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare cached sources without fetching or writing",
    )
    args = parser.parse_args()
    if (
        socket.gethostname() != "pod042"
        or os.getuid() != 1000
        or os.getgid() != 1000
        or Path.home() != HOME
    ):
        raise SystemExit("Run only as pod042's thurstonsand operator (UID/GID 1000)")
    cache = HOME / ".cache/ansiblonomicon-harness"
    _, _, _, sources = declarations(REPO, HOME)
    if not args.check:
        sync_sources(sources, cache)
    files = render_files(REPO, HOME, cache)
    reconcile(files, HOME, cache, args.check)
    print(f"Harness: {len(files)} managed files across five agents")


if __name__ == "__main__":
    main()
