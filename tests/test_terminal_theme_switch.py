from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tomllib

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "ansible/roles/terminal_theme/files/terminal-theme-switch.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = spec_from_file_location("terminal_theme_switch", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

set_codex_tui_theme = MODULE.set_codex_tui_theme
set_hunk_theme = MODULE.set_hunk_theme


def test_replaces_existing_tui_theme() -> None:
    original = """model = "gpt-5.4"

[tui]
notifications = true
theme = "gruvbox-light"
status_line = ["project-root"]
"""

    updated = set_codex_tui_theme(original, "dark")
    parsed = tomllib.loads(updated)

    assert parsed["tui"]["theme"] == "gruvbox-dark"
    assert parsed["tui"]["status_line"] == ["project-root"]


def test_inserts_theme_into_existing_tui_section() -> None:
    original = """model = "gpt-5.4"

[tui]
notifications = true

[history]
persistence = "save-all"
"""

    updated = set_codex_tui_theme(original, "light")
    parsed = tomllib.loads(updated)

    assert parsed["tui"]["theme"] == "gruvbox-light"
    assert parsed["tui"]["notifications"] is True
    assert parsed["history"]["persistence"] == "save-all"


def test_appends_tui_section_when_missing() -> None:
    original = """model = "gpt-5.4"

[history]
persistence = "save-all"
"""

    updated = set_codex_tui_theme(original, "dark")
    parsed = tomllib.loads(updated)

    assert parsed["tui"]["theme"] == "gruvbox-dark"
    assert parsed["history"]["persistence"] == "save-all"


def test_sets_hunk_custom_dark_hard_theme() -> None:
    original = """theme = "graphite"
mode = "auto"
"""

    updated = set_hunk_theme(original, "dark")
    parsed = tomllib.loads(updated)

    assert parsed["theme"] == "graphite"
    assert parsed["custom_theme"]["label"] == "Gruvbox Dark Hard"
    assert "base" not in parsed["custom_theme"]
    assert parsed["custom_theme"]["background"] == "#1d2021"
    assert parsed["custom_theme"]["syntax"]["string"] == "#b8bb26"


def test_sets_hunk_custom_light_hard_theme() -> None:
    original = """theme = "custom"
mode = "auto"

[custom_theme]
base = "graphite"
label = "Gruvbox Dark Hard"

[custom_theme.syntax]
string = "#b8bb26"
"""

    updated = set_hunk_theme(original, "light")
    parsed = tomllib.loads(updated)

    assert parsed["theme"] == "custom"
    assert parsed["custom_theme"]["label"] == "Gruvbox Light Hard"
    assert "base" not in parsed["custom_theme"]
    assert parsed["custom_theme"]["background"] == "#f9f5d7"
    assert parsed["custom_theme"]["syntax"]["string"] == "#79740e"
