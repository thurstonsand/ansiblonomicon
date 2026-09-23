#!/usr/bin/env python3
"""Render the amp_publish profile into a directory for the hosted Amp User Skills.

Publication never touches the operator home: Git sources are cloned into a
throwaway cache, templates render through the same catalogue engine the hosts
use, and only the Amp skills tree is written out. Hook fragments stay behind.
"""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_harness_deploy as engine
import catalogue

PROFILE = "amp_publish"
HOSTNAME = "amp-publish"


def render(repo: Path, root: Path, *, cached: bool) -> dict[Path, tuple[bytes, int]]:
    """Return published skill files keyed by their path inside the skills tree."""
    repo, root = repo.resolve(), root.resolve()
    checkouts = root / "sources"
    _, _, layouts, sources = catalogue.declarations(repo, root, PROFILE, HOSTNAME)
    skills_root = Path(layouts["amp"]["skills_dir"])
    if cached:
        engine.require_cached_sources(sources, checkouts)
    else:
        engine.sync_sources(sources, checkouts, time.time(), update="always")
    files = catalogue.render_files(
        repo, root, checkouts, PROFILE, HOSTNAME, trim_blocks=True
    )
    return {
        path.relative_to(skills_root): payload
        for path, payload in files.items()
        if path.is_relative_to(skills_root)
    }


def write(files: dict[Path, tuple[bytes, int]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"Publish output must be empty: {output}")
    for relative, (content, mode) in sorted(files.items()):
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(mode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cache",
        type=Path,
        help="Reuse this source cache instead of a throwaway one",
    )
    parser.add_argument(
        "--cached",
        action="store_true",
        help="Render from the existing cache without refreshing Git sources",
    )
    args = parser.parse_args()
    if args.cached and args.cache is None:
        parser.error("--cached requires --cache")
    if args.cache is not None:
        write(render(args.repo, args.cache, cached=args.cached), args.output)
        return
    with tempfile.TemporaryDirectory(prefix="amp-publish-") as temporary:
        write(render(args.repo, Path(temporary), cached=False), args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"publish-amp-skills: {error}", file=sys.stderr)
        raise SystemExit(1) from error
