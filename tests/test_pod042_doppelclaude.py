import json
import os
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "bootstrap/targets/pod042/containers/stacks/doppelclaude"


def test_runtime_is_private_and_bills_the_subscription() -> None:
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
            "DOPPELCLAUDE_IMAGE": "example.com/doppelclaude:latest",
            "DOPPELCLAUDE_HTTP_API_KEY": "test-client-key",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-subscription-token",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    service = json.loads(result.stdout)["services"]["doppelclaude"]
    assert "ports" not in service
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    # An API key would silently move billing off the subscription token.
    assert "ANTHROPIC_API_KEY" not in service["environment"]
    declaration = tomllib.loads(
        (STACK.parents[2] / "mise.doppelclaude.toml").read_text()
    )
    files = declaration["bootstrap"]["files"]
    assert files["/etc/ansiblonomicon/containers/doppelclaude/.env"]["mode"] == "0600"
