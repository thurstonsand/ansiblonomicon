import json
import os
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "bootstrap/targets/pod042/containers/stacks/doppelclaude"


def test_compose_contract_and_private_runtime() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(STACK / "compose.yaml"),
            "config",
            "--format",
            "json",
        ],
        env=os.environ
        | {
            "DOPPELCLAUDE_IMAGE": "example.com/doppelclaude@sha256:" + "a" * 64,
            "DOPPELCLAUDE_HTTP_API_KEY": "test-client-key",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-subscription-token",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    service = json.loads(result.stdout)["services"]["doppelclaude"]
    assert service["platform"] == "linux/amd64"
    assert service["user"] == "3456:3456"
    assert service["read_only"] is True
    assert service["init"] is True
    assert service["stop_grace_period"] == "25s"
    assert "ports" not in service
    assert "build" not in service
    assert service.get("command") is None
    assert service.get("entrypoint") is None
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    environment = service["environment"]
    assert (
        environment["HOME"]
        == environment["DOPPELCLAUDE_STATE_DIR"]
        == "/var/lib/doppelclaude"
    )
    assert environment["CLAUDE_CONFIG_DIR"] == "/var/lib/doppelclaude/.claude"
    assert environment["PORT"] == "3456"
    assert environment["DOPPELCLAUDE_HTTP_HOST"] == "0.0.0.0"
    assert "DOPPELCLAUDE_HTTP_MODEL" not in environment
    assert environment["DOPPELCLAUDE_MAX_RUNTIMES"] == "32"
    assert environment["DOPPELCLAUDE_IDLE_TTL_MS"] == "3600000"
    assert environment["DOPPELCLAUDE_MAX_BODY_BYTES"] == "32000000"
    assert environment["DOPPELCLAUDE_REQUEST_TIMEOUT_MS"] == "600000"
    assert environment["DOPPELCLAUDE_SHUTDOWN_TIMEOUT_MS"] == "15000"
    assert environment["DOPPELCLAUDE_RETRY_ATTEMPTS"] == "2"
    assert "DOPPELCLAUDE_HTTP_API_KEY_FILE" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert len(service["volumes"]) == 1
    assert service["volumes"][0]["target"] == "/var/lib/doppelclaude"
    assert service["volumes"][0]["bind"].get("create_host_path", False) is False
    assert "http://127.0.0.1:3456/v1/models" in service["healthcheck"]["test"][-1]
    assert (
        '{ host = "doppelclaude-origin", service = "http://doppelclaude:3456" }'
        in (ROOT / "terraform/cloudflare/locals.tf").read_text()
    )
    declaration = tomllib.loads(
        (STACK.parents[2] / "mise.doppelclaude.toml").read_text()
    )
    files = declaration["bootstrap"]["files"]
    assert files["/etc/ansiblonomicon/containers/doppelclaude/.env"]["mode"] == "0600"
