"""Tests for the frontmatter of every skill this repo ships."""

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
SKILL_ROOTS = (REPO_ROOT / "agents", REPO_ROOT / ".agents")
REQUIRED_FIELDS = {"name", "description"}


def skill_files() -> list[Path]:
    return sorted(path for root in SKILL_ROOTS for path in root.rglob("SKILL.md*"))


@pytest.mark.parametrize(
    "skill", skill_files(), ids=lambda path: str(path.relative_to(REPO_ROOT))
)
def test_skill_frontmatter_parses(skill: Path) -> None:
    text = skill.read_text()
    assert text.startswith("---\n"), "skill is missing frontmatter"

    frontmatter: dict[str, Any] = yaml.safe_load(text.split("---", 2)[1])
    assert isinstance(frontmatter, dict), "frontmatter is not a mapping"
    assert not REQUIRED_FIELDS - frontmatter.keys()

    for field in REQUIRED_FIELDS:
        assert isinstance(frontmatter[field], str), f"{field} must be a string"
        assert frontmatter[field].strip()
