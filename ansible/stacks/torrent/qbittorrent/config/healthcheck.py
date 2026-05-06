#!/usr/bin/env python3
import json
import sys
import time
import urllib.request

BASE_URL = "http://127.0.0.1:80/api/v2"
MULLVAD_URL = "https://am.i.mullvad.net/connected"
GRACE_SECONDS = 600
REQUEST_TIMEOUT = 5


def check_vpn() -> None:
    with urllib.request.urlopen(MULLVAD_URL, timeout=REQUEST_TIMEOUT) as response:
        body = response.read().decode("utf-8", errors="replace")
    if "You are connected" not in body:
        raise RuntimeError("Mullvad connectivity check failed")


def get_json(path: str):
    with urllib.request.urlopen(
        f"{BASE_URL}{path}", timeout=REQUEST_TIMEOUT
    ) as response:
        return json.load(response)


try:
    check_vpn()
except Exception as exc:
    print(f"unhealthy: VPN connectivity unavailable: {exc}")
    sys.exit(1)

try:
    transfer = get_json("/transfer/info")
    torrents = get_json("/torrents/info")
except Exception as exc:
    print(f"unhealthy: qBittorrent API unavailable: {exc}")
    sys.exit(1)

incomplete = [torrent for torrent in torrents if torrent.get("progress", 0) < 1]

if not incomplete:
    print("healthy: no incomplete torrents")
    sys.exit(0)

if any(torrent.get("dlspeed", 0) > 0 for torrent in incomplete):
    print("healthy: at least one torrent is actively downloading")
    sys.exit(0)

if any(
    torrent.get("has_metadata")
    and (torrent.get("num_peers", 0) > 0 or torrent.get("num_seeds", 0) > 0)
    for torrent in incomplete
):
    print("healthy: metadata acquired and peers visible")
    sys.exit(0)

now = time.time()
oldest_age = max(now - torrent.get("added_on", now) for torrent in incomplete)
if oldest_age < GRACE_SECONDS:
    print("healthy: incomplete torrents are still within grace period")
    sys.exit(0)

all_stuck = all(
    (not torrent.get("has_metadata"))
    or torrent.get("state") == "metaDL"
    or torrent.get("total_size", -1) <= 0
    for torrent in incomplete
)

if transfer.get("dht_nodes", 0) == 0 and all_stuck:
    print("unhealthy: incomplete torrents are stuck and DHT is 0")
    sys.exit(1)

print("healthy: no conclusive wedged torrent session detected")
sys.exit(0)
