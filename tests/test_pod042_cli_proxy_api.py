from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "bootstrap/targets/pod042/containers/stacks/cli-proxy-api/compose.yaml"


def test_cli_proxy_api_compose_is_valid() -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--quiet"],
        check=True,
    )


def test_cli_proxy_api_preserves_state_without_public_ports_or_logs() -> None:
    compose = COMPOSE.read_text()
    state = "/mnt/black-box/docker/cli-proxy-api/cli-proxy-api/CLIProxyAPI"

    assert "container_name" not in compose
    assert "ports:" not in compose
    assert "ipv4_address" not in compose
    assert "\n    user:" not in compose
    assert "restart: unless-stopped" in compose
    assert 'com.centurylinklabs.watchtower.enable: "true"' in compose
    assert "name: ingress" in compose
    assert "- cli-proxy-api" in compose
    assert f"{state}/config.yaml:/CLIProxyAPI/config.yaml" in compose
    assert f"{state}/auths:/CLIProxyAPI/auths" in compose
    assert f"{state}/static:/CLIProxyAPI/static" in compose
    assert f"{state}/logs" not in compose

    for port in (8317, 8085, 1455, 54545, 51121, 11451):
        assert f'- "{port}"' in compose
