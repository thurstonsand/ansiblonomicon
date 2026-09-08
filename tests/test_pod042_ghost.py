import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "bootstrap/targets/pod042/containers/stacks/ghost/compose.yaml"


def test_ghost_compose_is_valid_and_requires_only_declared_secrets() -> None:
    environment = os.environ | {
        "GHOST_DB_PASSWORD": "test-db-password",
        "GHOST_MYSQL_ROOT_PASSWORD": "test-root-password",
        "GHOST_MAIL_AUTH_PASS": "test-mail-password",
    }
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--quiet"],
        check=True,
        env=environment,
    )


def test_ghost_uses_private_database_and_shared_ingress() -> None:
    compose = COMPOSE.read_text()
    assert "container_name" not in compose
    assert "ports:" not in compose
    assert "ipv4_address" not in compose
    assert "/mnt/capacity" not in compose
    assert "\n    user:" not in compose
    assert "entrypoint:" not in compose
    assert "condition: service_healthy" in compose
    assert "name: ingress" in compose
    assert "aliases:" not in compose
    assert "/mnt/black-box/docker/ghost/ghost_mysql/var/lib/mysql" in compose
    assert compose.count("restart: unless-stopped") == 2
    for secret in (
        "GHOST_DB_PASSWORD",
        "GHOST_MYSQL_ROOT_PASSWORD",
        "GHOST_MAIL_AUTH_PASS",
    ):
        assert f"${{{secret}:?required}}" in compose
