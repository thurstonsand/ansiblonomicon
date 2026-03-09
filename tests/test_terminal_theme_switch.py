from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tomllib

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "chezmoi/private_dot_local/private_bin/executable_terminal-theme-switch.py"
)
SPEC = spec_from_file_location("terminal_theme_switch", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

set_codex_tui_theme = MODULE.set_codex_tui_theme


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
