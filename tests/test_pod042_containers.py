import base64
import hashlib
from pathlib import Path
import subprocess
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"


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


def test_docker_and_netdata_stay_on_loopback() -> None:
    platform = (TARGET / "containers/stacks/platform/compose.yaml").read_text()
    netdata = (TARGET / "containers/config/netdata.conf").read_text()
    # The socket proxy fronts the root-equivalent Docker socket: read-only, local only.
    assert "127.0.0.1:2375:2375" in platform
    assert 'POST: "0"' in platform
    assert "bind to = 127.0.0.1:19999" in netdata
    assert "allow mcp from = localhost" in netdata


def test_netdata_claim_token_is_group_private() -> None:
    bootstrap = tomllib.loads((TARGET / "mise.containers.toml").read_text())[
        "bootstrap"
    ]
    claim = bootstrap["files"]["/etc/netdata/claim.conf"]
    assert (claim["owner"], claim["group"], claim["mode"]) == (
        "root",
        "netdata",
        "0640",
    )
    assert 'secret(name="netdata_claim_token")' in claim["content"]


def test_netns_repair_watches_every_gluetun_dependent() -> None:
    compose = TARGET / "containers/stacks/torrent/compose.yaml"
    services = yaml.safe_load(compose.read_text())["services"]
    assert set(services["netns-repair"]["environment"]["DEPENDENTS"].split()) == {
        name
        for name, service in services.items()
        if service.get("network_mode") == "service:gluetun"
    }
    subprocess.run(
        ["sh", "-n", str(TARGET / "containers/stacks/torrent/netns-repair.sh")],
        check=True,
    )
