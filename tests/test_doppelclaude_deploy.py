import importlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_deploy_passes_only_worker_credentials_over_stdin(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
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


def test_missing_credentials_prevent_deployment(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    deploy = importlib.import_module("doppelclaude_deploy")
    monkeypatch.delenv("CLI_PROXY_API_KEY", raising=False)
    run = Mock()
    monkeypatch.setattr(deploy.subprocess, "run", run)
    with pytest.raises(ValueError, match="CLI_PROXY_API_KEY"):
        deploy.main()
    run.assert_not_called()
