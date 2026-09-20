from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "bootstrap/targets/pod042/monitoring/api/reconcile.py"
)
SPEC = spec_from_file_location("monitoring_reconcile", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
monitoring = module_from_spec(SPEC)
sys.modules[SPEC.name] = monitoring
SPEC.loader.exec_module(monitoring)


def test_child_environment_removes_all_scope_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def healthchecks(key: str) -> object:
        return object()

    def reconcile(api: object, check_only: bool) -> dict[str, str]:
        return {"PING_URL": "synthetic"}

    monkeypatch.setattr(monitoring, "Healthchecks", healthchecks)
    monkeypatch.setattr(monitoring, "reconcile", reconcile)

    def launch(path: str, args: list[str], environment: dict[str, str]) -> None:
        captured.update(environment)
        raise RuntimeError("child intercepted")

    monkeypatch.setattr(monitoring.os, "execvpe", launch)
    environment = {
        "HEALTHCHECKS_API_KEY": "synthetic_key",
        "HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": "pod042",
        "HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": '["HEALTHCHECKS_API_KEY"]',
        "HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON": "/python",
        "PATH": "/usr/bin:/bin",
    }
    with (
        patch.dict(os.environ, environment, clear=True),
        pytest.raises(RuntimeError, match="intercepted"),
    ):
        monitoring.main(["--", "/bin/true"])

    assert captured == {"PATH": "/usr/bin:/bin", "PING_URL": "synthetic"}
