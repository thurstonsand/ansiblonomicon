from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/prepare_amp_skills.py"
SPEC = spec_from_file_location("prepare_amp_skills", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_bundles_impeccable_scripts_without_changing_behavior(tmp_path: Path) -> None:
    skill_dir = tmp_path / "impeccable"
    (skill_dir / "scripts" / "lib").mkdir(parents=True)
    (skill_dir / "reference").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: impeccable\n---\nRun `node <skill-base-dir>/scripts/context.mjs`.\n"
    )
    (skill_dir / "reference" / "audit.md").write_text(
        "Run `node .claude/skills/impeccable/scripts/context.mjs`.\n"
    )
    (skill_dir / "scripts" / "lib" / "message.mjs").write_text(
        'export const message = "bundled";\n'
    )
    (skill_dir / "scripts" / "context.mjs").write_text(
        'import { readFileSync } from "node:fs";\n'
        'import { message } from "./lib/message.mjs";\n'
        'import { fileURLToPath } from "node:url";\n'
        'const skill = new URL("../SKILL.md", import.meta.url);\n'
        'console.log(`${message}:${readFileSync(fileURLToPath(skill), "utf8").length}`);\n'
    )

    MODULE.bundle_impeccable(tmp_path)

    assert not (skill_dir / "scripts").exists()
    assert "run.mjs context.mjs" in (skill_dir / "SKILL.md").read_text()
    assert "run.mjs context.mjs" in (skill_dir / "reference" / "audit.md").read_text()
    assert "scripts/context.mjs" in json.loads((skill_dir / "bundle.json").read_text())

    result = subprocess.run(
        ["node", skill_dir / "run.mjs", "context.mjs"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.startswith("bundled:")


def test_rejects_skills_amp_would_silently_omit(tmp_path: Path) -> None:
    skill_dir = tmp_path / "oversized"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: oversized\n---\n")
    for index in range(50):
        (skill_dir / f"{index}.txt").write_text("")

    with pytest.raises(ValueError, match="at most 50"):
        MODULE.validate(tmp_path)
