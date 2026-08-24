#!/usr/bin/env python3
"""One-shot equivalence check for the agent_harness declarative-resolution cutover.

Proves the rewritten resolver deploys the same resources as the old one on THIS
machine, then gets deleted. Run it after pulling the cutover commit:

    uv run python scripts/agent-harness-equiv.py capture --old-rev <pre-cutover-sha> \
        --profile work --extras ansible/work.config.local.yml
    # migrate work.config.local.yml to the new vocabulary, then:
    uv run python scripts/agent-harness-equiv.py verify \
        --profile work --extras ansible/work.config.local.yml

Capture rebuilds the OLD resolver and OLD config from git history, so it works
even though the working tree already has the new code. `--extras` reads
`agent_harness_sources_extra` from an (uncommitted) host config; pass the
pre-migration file to capture and the migrated file to verify. Delete this
script once every machine has verified.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
FILTERS = "ansible/roles/agent_harness/filter_plugins/harness_filters.py"
CONFIG = "ansible/agent-harness.config.yml"
BASELINE = Path(tempfile.gettempdir()) / "agent-harness-equiv-baseline.json"
CACHE = Path.home() / ".cache/ansiblonomicon-harness"


def load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("harness_filters_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_extras(path: str | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}
    extras: list[dict[str, Any]] = data.get("agent_harness_sources_extra", [])
    return extras


def localize(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for source in sources:
        if "local" in source:
            source["local"] = str(REPO / "agents")
    return sources


def normalize(resources: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    # Sets, not lists: the old resolver double-counted some skills (the bug that
    # motivated the rewrite) and twin plugin declarations legitimately share
    # sources. Deployment identity is (name, path); duplicates never deployed twice.
    return {
        "skills": sorted(
            {(r["name"], os.path.realpath(r["source"])) for r in resources["skills"]}
        ),
        "agents": sorted(
            {(r["name"], os.path.realpath(r["source"])) for r in resources["agents"]}
        ),
        "hooks": sorted(
            {(h["name"], h["content"]) for h in resources.get("hooks", [])}
        ),
    }


def capture(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        old_filters = Path(tmp) / "harness_filters.py"

        def show(path: str) -> str:
            return subprocess.run(
                ["git", "-C", str(REPO), "show", f"{args.old_rev}:{path}"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

        old_filters.write_text(show(FILTERS))
        old_cfg: dict[str, Any] = yaml.safe_load(show(CONFIG))
        h = load_module(old_filters)

        catalogue = old_cfg["agent_harness_source_catalogue"]
        resolved = h.agent_harness_resolve_sources(
            catalogue, args.profile, load_extras(args.extras)
        )
        resolved = localize(resolved)
        resources = h.agent_harness_build_plugin_resources(resolved, str(CACHE))
        resources["hooks"] = h.agent_harness_find_plugin_hooks(resolved, str(CACHE))

    BASELINE.write_text(json.dumps(normalize(resources)))
    counts = {k: len(v) for k, v in normalize(resources).items()}
    print(f"baseline captured from {args.old_rev} for profile {args.profile}: {counts}")
    print(f"wrote {BASELINE}")
    return 0


def verify(args: argparse.Namespace) -> int:
    h = load_module(REPO / FILTERS)
    cfg = yaml.safe_load((REPO / CONFIG).read_text())
    resolved = h.agent_harness_resolve_sources(
        cfg["agent_harness_sources"],
        args.profile,
        list(cfg["agent_harness_profiles"]),
        args.harnesses.split(","),
        load_extras(args.extras),
    )
    resources = normalize(
        h.agent_harness_build_plugin_resources(localize(resolved), str(CACHE))
    )

    baseline = json.loads(BASELINE.read_text())
    baseline = {k: [tuple(e) for e in v] for k, v in baseline.items()}
    failed = False
    for kind in ("skills", "agents", "hooks"):
        old, new = set(baseline[kind]), set(resources[kind])
        if old == new:
            print(f"{kind:7} {len(new):3} resources: IDENTICAL")
        else:
            failed = True
            for entry in sorted(old - new):
                print(f"{kind}: MISSING under new code: {entry}")
            for entry in sorted(new - old):
                print(f"{kind}: NEW under new code:     {entry}")
    print("RESULT:", "MISMATCH" if failed else "EQUIVALENT")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser(
        "capture", help="dump the OLD resolver's resources from git history"
    )
    cap.add_argument("--old-rev", required=True, help="last commit before the cutover")
    ver = sub.add_parser(
        "verify", help="compare the new resolver against the captured baseline"
    )
    ver.add_argument(
        "--harnesses",
        default="claude,amp,codex,opencode,pi",
        help="known harness names (vars/agents.yml keys)",
    )
    for p in (cap, ver):
        p.add_argument("--profile", required=True)
        p.add_argument(
            "--extras", help="host config yaml holding agent_harness_sources_extra"
        )

    args = parser.parse_args()
    return capture(args) if args.command == "capture" else verify(args)


if __name__ == "__main__":
    sys.exit(main())
