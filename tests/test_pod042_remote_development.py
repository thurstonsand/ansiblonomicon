import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pod042_remote_development",
    ROOT / "bootstrap/targets/pod042/remote-development/services.py",
)
assert spec is not None and spec.loader is not None
services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(services)


@pytest.mark.parametrize("missing", ["desired", "authenticated"])
def test_requires_enrollment(monkeypatch: pytest.MonkeyPatch, missing: str):
    state = {"desired": True, "authenticated": True, "linked": False}
    state[missing] = False

    def output(*args: str) -> str:
        return json.dumps(state)

    monkeypatch.setattr(services, "output", output)
    with pytest.raises(SystemExit, match="enrollment missing"):
        services.require_t3()
