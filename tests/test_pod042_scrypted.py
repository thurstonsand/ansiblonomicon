from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "bootstrap/targets/pod042/containers/stacks/scrypted/compose.yaml"


def test_scrypted_compose_is_valid() -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--quiet"],
        check=True,
    )


def test_scrypted_preserves_homekit_runtime_contract() -> None:
    service = yaml.safe_load(COMPOSE.read_text())["services"]["scrypted"]

    assert service["image"] == "ghcr.io/koush/scrypted"
    assert service["network_mode"] == "host"
    assert service["restart"] == "unless-stopped"
    assert "healthcheck" in service
    assert service["environment"] == {
        "SCRYPTED_DOCKER_AVAHI": "true",
        "SCRYPTED_INSECURE_PORT": "11080",
        "SCRYPTED_SECURE_PORT": "10443",
    }
    assert service["volumes"] == [
        "/mnt/black-box/docker/scrypted/scrypted/server/volume:/server/volume",
        "/etc/localtime:/etc/localtime:ro",
    ]
    assert "container_name" not in service
    assert "ports" not in service
    assert "networks" not in service
    assert "labels" not in service
