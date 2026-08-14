#!/usr/bin/env python3

import argparse
import base64
import json
from pathlib import Path
import re
import shutil

MAX_FILES_PER_SKILL = 50
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_REPOSITORY_BYTES = 25 * 1024 * 1024

SCRIPT_COMMAND = re.compile(
    r"node (?:<skill-base-dir>|\.claude/skills/impeccable)/scripts/"
    r"([A-Za-z0-9_./-]+\.(?:js|mjs))"
)


def bundle_impeccable(skills_dir: Path) -> None:
    skill_dir = skills_dir / "impeccable"
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return

    bundle: dict[str, dict[str, str]] = {}
    for path in sorted(path for path in skill_dir.rglob("*") if path.is_file()):
        content = path.read_bytes()
        try:
            encoded_content = content.decode()
            encoding = "utf8"
        except UnicodeDecodeError:
            encoded_content = base64.b64encode(content).decode()
            encoding = "base64"
        bundle[path.relative_to(skill_dir).as_posix()] = {
            "content": encoded_content,
            "encoding": encoding,
        }

    shutil.rmtree(scripts_dir)
    runner = Path(__file__).with_name("amp-skill-runner.mjs")
    shutil.copyfile(runner, skill_dir / "run.mjs")
    (skill_dir / "bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    )

    for path in skill_dir.rglob("*.md"):
        content = path.read_text()
        content = SCRIPT_COMMAND.sub(r"node <skill-base-dir>/run.mjs \1", content)
        content = content.replace(
            "Bash(node .claude/skills/impeccable/scripts/*)",
            "Bash(node */run.mjs *)",
        )
        path.write_text(content)


def validate(skills_dir: Path) -> None:
    repository_bytes = 0
    for skill_dir in sorted(path.parent for path in skills_dir.glob("*/SKILL.md")):
        files = [path for path in skill_dir.rglob("*") if path.is_file()]
        if len(files) > MAX_FILES_PER_SKILL:
            raise ValueError(
                f"{skill_dir.name} has {len(files)} files; Amp serves at most "
                f"{MAX_FILES_PER_SKILL} per global skill"
            )
        for path in files:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError(f"{path} exceeds Amp's 10 MiB global-skill file limit")
            try:
                path.read_text()
            except UnicodeDecodeError as error:
                raise ValueError(f"{path} is not UTF-8 text") from error
            repository_bytes += size

    if repository_bytes > MAX_REPOSITORY_BYTES:
        raise ValueError("rendered skills exceed Amp's 25 MiB global repository limit")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skills_dir", type=Path)
    args = parser.parse_args()

    bundle_impeccable(args.skills_dir)
    validate(args.skills_dir)


if __name__ == "__main__":
    main()
