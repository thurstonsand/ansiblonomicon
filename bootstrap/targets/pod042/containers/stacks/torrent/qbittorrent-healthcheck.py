#!/usr/bin/env python3
import json
import sys
import urllib.request

BASE_URL = "http://127.0.0.1:80/api/v2"
REQUEST_TIMEOUT = 5


def get_json(path: str):
    with urllib.request.urlopen(
        f"{BASE_URL}{path}", timeout=REQUEST_TIMEOUT
    ) as response:
        return json.load(response)


try:
    transfer = get_json("/transfer/info")
except Exception as exc:
    print(f"unhealthy: qBittorrent API unavailable: {exc}")
    sys.exit(1)

# A Gluetun reconnect storm can leave libtorrent's UDP sockets dead while TCP
# peers keep some torrents moving; DHT is the signal that survives that wedge.
dht_nodes = transfer.get("dht_nodes", 0)
if dht_nodes == 0:
    print("unhealthy: DHT has no nodes")
    sys.exit(1)

print(f"healthy: {dht_nodes} DHT nodes")
