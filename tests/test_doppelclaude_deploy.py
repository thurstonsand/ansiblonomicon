import importlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_deploy_passes_only_worker_credentials_over_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "path", [str(ROOT / "scripts"), *sys.path])
    deploy = importlib.import_module("doppelclaude_deploy")
    secrets = {
        "CLI_PROXY_API_KEY": "test-client-key",
        "CF_ACCESS_CLIENT_ID": "test-access-id",
        "CF_ACCESS_CLIENT_SECRET": "test-access-secret",
        "CLAUDE_CODE_OAUTH_TOKEN": "must-not-reach-worker",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)
    run = Mock()
    monkeypatch.setattr(deploy.subprocess, "run", run)
    deploy.main()
    assert run.call_count == 2
    assert run.call_args_list[0].args == (["wrangler", "deploy"],)
    bulk = run.call_args_list[1]
    assert bulk.args == (["wrangler", "secret", "bulk"],)
    assert json.loads(bulk.kwargs["input"]) == {
        "API_KEY": "test-client-key",
        "CF_ACCESS_CLIENT_ID": "test-access-id",
        "CF_ACCESS_CLIENT_SECRET": "test-access-secret",
    }
    assert bulk.kwargs["check"] is True
