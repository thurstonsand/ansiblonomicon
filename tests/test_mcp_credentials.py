import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
    from scripts import mcp_credentials


def resolved_credential(_name: str) -> str:
    return "resolved"


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
