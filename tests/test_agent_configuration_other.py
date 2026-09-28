from importlib import util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
CONFIGURATION = ROOT / "bootstrap/capabilities/agent-harness/configuration"


def load(name: str) -> ModuleType:
    specification = util.spec_from_file_location(name, CONFIGURATION / f"{name}.py")
    assert specification is not None
    assert specification.loader is not None
    module = util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_strict_json_preserves_urls_and_rejects_jsonc(tmp_path: Path) -> None:
    amp = load("amp")
    source = tmp_path / "settings.json"
    source.write_text('{"url":"https://example.test/path"}')
    assert json.loads(amp._strict_json(source))["url"] == "https://example.test/path"

    source.write_text('{"url":"https://example.test/path", // comment\n}')
    with pytest.raises(json.JSONDecodeError):
        amp._strict_json(source)
