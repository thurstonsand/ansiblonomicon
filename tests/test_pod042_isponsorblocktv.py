from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (
    ROOT / "bootstrap/targets/pod042/containers/stacks/isponsorblocktv/compose.yaml"
)


def test_isponsorblocktv_compose_is_valid() -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--quiet"],
        check=True,
    )


def test_isponsorblocktv_preserves_pairing_on_a_private_network() -> None:
    compose = COMPOSE.read_text()
    assert "container_name" not in compose
    assert "ports:" not in compose
    assert "network_mode:" not in compose
    assert "networks:" not in compose
    assert "PUID" not in compose
    assert "PGID" not in compose
    assert "healthcheck:" not in compose
    assert "restart: unless-stopped" in compose
    assert (
        "/mnt/black-box/docker/isponsorblocktv/isponsorblocktv/app/data:/app/data"
        in compose
    )
