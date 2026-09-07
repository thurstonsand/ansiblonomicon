import base64
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"


def load_module(name: str, path: Path) -> Any:
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module: Any = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def public_key_fingerprint(path: Path) -> str:
    encoded = "".join(
        line
        for line in path.read_text().splitlines()
        if line
        and not line.startswith("-")
        and ":" not in line
        and not line.startswith("=")
    )
    packet = base64.b64decode(encoded)
    if packet[0] & 0x40:
        length_type = packet[1]
        if length_type < 192:
            offset, length = 2, length_type
        elif length_type < 224:
            offset, length = 3, ((length_type - 192) << 8) + packet[2] + 192
        else:
            offset, length = 6, int.from_bytes(packet[2:6])
    else:
        assert packet[0] & 3 == 1
        offset, length = 3, int.from_bytes(packet[1:3])
    body = packet[offset : offset + length]
    return hashlib.sha1(b"\x99" + len(body).to_bytes(2) + body).hexdigest().upper()


def test_official_repository_keys_have_pinned_fingerprints() -> None:
    assert public_key_fingerprint(TARGET / "repositories/files/docker.asc") == (
        "9DC858229FC7DD38854AE2D88D81803C0EBFCD88"
    )
    assert public_key_fingerprint(TARGET / "repositories/files/netdata.asc") == (
        "6E155DC153906B73765A74A99DD4A74CECFA8F4F"
    )


def test_repository_sources_use_the_vendored_keys() -> None:
    docker = (TARGET / "repositories/files/docker.sources").read_text()
    netdata = (TARGET / "repositories/files/netdata.sources").read_text()
    assert "Signed-By: /etc/apt/keyrings/docker.asc" in docker
    assert "Signed-By: /etc/apt/keyrings/netdata.asc" in netdata


def test_platform_uses_native_mise_compose() -> None:
    bootstrap = tomllib.loads((TARGET / "mise.containers.toml").read_text())[
        "bootstrap"
    ]
    project = bootstrap["compose"]["platform"]
    assert project == {
        "project_dir": "/etc/ansiblonomicon/containers/platform",
        "files": ["compose.yaml"],
        "env_files": [".env"],
        "project_name": "platform",
        "state": "running",
        "sudo": True,
        "pull": "always",
        "wait": True,
        "wait_timeout": 120,
        "remove_orphans": True,
        "depends_on": ["service:docker"],
    }
    files = bootstrap["files"]
    compose = files["/etc/ansiblonomicon/containers/platform/compose.yaml"]
    environment = files["/etc/ansiblonomicon/containers/platform/.env"]
    assert compose["source"] == "containers/stacks/platform/compose.yaml"
    assert (compose["owner"], compose["group"], compose["mode"]) == (
        "root",
        "root",
        "0600",
    )
    assert environment["template"] is True
    assert environment["mode"] == "0600"
    assert 'secret(name="hark_webhook_url")' in environment["content"]
    assert "generic://" in environment["content"]


def test_platform_configuration_matches_runtime_boundaries() -> None:
    platform = (TARGET / "containers/stacks/platform/compose.yaml").read_text()
    daemon = json.loads((TARGET / "containers/config/daemon.json").read_text())
    netdata = (TARGET / "containers/config/netdata.conf").read_text()
    bootstrap = tomllib.loads((TARGET / "mise.containers.toml").read_text())[
        "bootstrap"
    ]
    assert "127.0.0.1:2375:2375" in platform
    assert 'POST: "0"' in platform
    assert 'EVENTS: "0"' in platform
    assert 'IMAGES: "1"' in platform
    assert "/var/run/docker.sock:/var/run/docker.sock" in platform
    assert "container_name" not in platform
    assert '"0 0 4 * * *"' in platform
    assert "WATCHTOWER_CLEANUP" in platform
    assert "WATCHTOWER_USE_COMPOSE_DEPENDS_ON" in platform
    assert daemon["default-address-pools"] == [{"base": "10.42.0.0/16", "size": 24}]
    assert daemon["live-restore"] is True
    assert "bind to = 127.0.0.1:19999" in netdata
    assert "allow mcp from = localhost" in netdata
    assert "enabled = no" in netdata
    assert set(bootstrap["packages"]) >= {
        "apt:docker-ce",
        "apt:docker-ce-cli",
        "apt:containerd.io",
        "apt:docker-buildx-plugin",
        "apt:docker-compose-plugin",
        "apt:netdata",
    }


def test_netdata_uses_the_shared_host_alert_sender() -> None:
    alerting = tomllib.loads((TARGET / "mise.alerting.toml").read_text())["bootstrap"]
    credential = alerting["files"]["/etc/alerting/hark-webhook-url"]
    assert "alerting" in alerting["groups"]
    assert (credential["owner"], credential["group"], credential["mode"]) == (
        "root",
        "alerting",
        "0640",
    )
    sender = (TARGET / "alerting/storage-alert.py").read_text()
    assert 'grp_id("alerting")' in sender
    assert "os.O_NOFOLLOW" in sender
    assert '"Idempotency-Key"' in sender
    config_path = TARGET / "containers/config/hark.conf"
    config = config_path.read_text()
    subprocess.run(
        [
            "bash",
            "-c",
            'source "$1" && [[ $SEND_CUSTOM == YES ]] '
            "&& [[ $DEFAULT_RECIPIENT_CUSTOM == hark ]] "
            "&& declare -F custom_sender >/dev/null",
            "bash",
            str(config_path),
        ],
        check=True,
    )
    assert "/usr/local/bin/storage-alert" in config
    assert "netdata-hark-notify" not in config
    for variable in ("status_message", "alarm", "info", "host", "status", "chart"):
        assert f"${variable}" in config


def test_finalize_converges_package_created_memberships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finalize = load_module("pod042_finalize", TARGET / "containers/finalize.py")
    account = type("Account", (), {"pw_gid": 100})()
    groups = {
        "systemd-journal": type(
            "Group", (), {"gr_name": "systemd-journal", "gr_mem": []}
        )(),
        "adm": type("Group", (), {"gr_name": "adm", "gr_mem": ["netdata"]})(),
        "alerting": type("Group", (), {"gr_name": "alerting", "gr_mem": []})(),
        "docker": type(
            "Group", (), {"gr_name": "docker", "gr_mem": ["netdata", "thurstonsand"]}
        )(),
        "media": type("Group", (), {"gr_name": "media", "gr_mem": ["thurstonsand"]})(),
        "primary": type("Group", (), {"gr_name": "primary", "gr_mem": []})(),
    }

    def get_account(_name: str) -> Any:
        return account

    def get_primary_group(_gid: int) -> Any:
        return groups["primary"]

    monkeypatch.setattr(finalize.pwd, "getpwnam", get_account)
    monkeypatch.setattr(finalize.grp, "getgrnam", groups.__getitem__)
    monkeypatch.setattr(finalize.grp, "getgrgid", get_primary_group)
    monkeypatch.setattr(finalize.grp, "getgrall", lambda: list(groups.values()))
    run = Mock()
    monkeypatch.setattr(finalize.subprocess, "run", run)
    finalize.main()
    assert [call.args[0] for call in run.call_args_list] == [
        ["gpasswd", "--delete", "netdata", "docker"],
        ["usermod", "-aG", "systemd-journal", "netdata"],
        ["usermod", "-aG", "alerting", "netdata"],
        ["systemctl", "restart", "netdata"],
    ]
    with pytest.raises(KeyError):
        finalize.add_group("netdata", "missing")
