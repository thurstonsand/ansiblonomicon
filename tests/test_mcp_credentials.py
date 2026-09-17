import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
    from scripts import mcp_credentials


def resolved_credential(_name: str) -> str:
    return "resolved"


def test_credential_resolves_one_named_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    invocation: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        invocation["command"] = command
        invocation["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="resolved\n")

    monkeypatch.setattr(subprocess, "run", run)

    assert mcp_credentials.credential("TEST_TOKEN") == "resolved"
    assert invocation["command"] == [
        str(mcp_credentials.ROOT / "scripts/fnox-host"),
        "get",
        "TEST_TOKEN",
    ]


def test_exec_remote_limits_environment_and_defers_header_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invocation: dict[str, object] = {}
    monkeypatch.setattr(mcp_credentials, "credential", resolved_credential)
    monkeypatch.setenv("UNRELATED_SECRET", "excluded")
    monkeypatch.setenv("SSL_CERT_FILE", "/certificate.pem")

    def execvpe(
        executable: str, command: list[str], environment: dict[str, str]
    ) -> None:
        invocation.update(
            executable=executable, command=command, environment=environment
        )

    monkeypatch.setattr(os, "execvpe", execvpe)

    mcp_credentials.exec_remote("https://example.test/mcp", "TEST_TOKEN")

    assert invocation["executable"] == "mcp-remote"
    assert invocation["command"] == [
        "mcp-remote",
        "https://example.test/mcp",
        "--header",
        "Authorization:Bearer ${TEST_TOKEN}",
    ]
    environment = invocation["environment"]
    assert isinstance(environment, dict)
    assert environment["HOME"] == os.environ["HOME"]
    assert environment["PATH"] == os.environ["PATH"]
    assert environment["SSL_CERT_FILE"] == "/certificate.pem"
    assert environment["TEST_TOKEN"] == "resolved"
    assert "UNRELATED_SECRET" not in environment


@pytest.mark.parametrize(
    ("mode", "credential_name"),
    [
        ("cloudflare-headers", "CLOUDFLARE_API_TOKEN"),
        ("home-assistant-headers", "HOMEASSISTANT_API_KEY"),
    ],
)
def test_headers_print_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    credential_name: str,
) -> None:
    resolved_names: list[str] = []

    def resolve(name: str) -> str:
        resolved_names.append(name)
        return "resolved"

    monkeypatch.setattr(mcp_credentials, "credential", resolve)
    monkeypatch.setattr("sys.argv", ["mcp_credentials.py", mode])

    mcp_credentials.main()

    assert resolved_names == [credential_name]
    assert json.loads(capsys.readouterr().out) == {"Authorization": "Bearer resolved"}


def test_work_web_search_requires_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["mcp_credentials.py", "work-web-search"])

    with pytest.raises(SystemExit, match="2"):
        mcp_credentials.main()
