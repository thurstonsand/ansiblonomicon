#!/usr/bin/env python3
"""
MAM Dynamic Seedbox IP Updater

Checks if VPN IP changed and updates MAM only when needed.
State persisted to file so we retry on failures.
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

GLUETUN_URL = os.environ.get("GLUETUN_URL", "http://gluetun:8000")
MAM_ID = os.environ.get("MAM_ID", "")
STATE_FILE = Path(os.environ.get("STATE_FILE", "/data/state.json"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class State:
    last_synced_ip: str | None = None

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"last_synced_ip": self.last_synced_ip}))

    @classmethod
    def load(cls) -> "State":
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            return cls(last_synced_ip=data.get("last_synced_ip"))
        return cls()


def get_vpn_status() -> str | None:
    with urlopen(f"{GLUETUN_URL}/v1/vpn/status", timeout=10) as resp:
        data: dict[str, str] = json.load(resp)
        return data.get("status")


def get_vpn_ip() -> str | None:
    with urlopen(f"{GLUETUN_URL}/v1/publicip/ip", timeout=10) as resp:
        data: dict[str, str] = json.load(resp)
        return data.get("public_ip") or None


def update_mam_ip() -> bool:
    """Call MAM API. Returns True if IP is now synced (success or no change)."""
    req = Request(
        "https://t.myanonamouse.net/json/dynamicSeedbox.php",
        headers={"Cookie": f"mam_id={MAM_ID}"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data: dict[str, str] = json.load(resp)
            msg = data.get("msg", "")

            if msg == "Completed":
                logger.info("MAM IP updated successfully")
                return True
            elif msg == "No Change":
                logger.info("MAM IP unchanged")
                return True
            else:
                logger.info("MAM response: %s", msg)
                return True

    except HTTPError as e:
        if e.code == 429:
            logger.warning("MAM rate limited (1 update/hour) - will retry")
            return False
        raise


def main() -> int:
    if not MAM_ID:
        logger.error("MAM_ID environment variable is required")
        return 1

    status = get_vpn_status()
    if status != "running":
        logger.info("VPN not running (status: %s) - skipping", status)
        return 0

    current_ip = get_vpn_ip()
    if not current_ip:
        logger.warning("Could not get VPN IP - skipping")
        return 0

    state = State.load()

    if current_ip == state.last_synced_ip:
        logger.info("IP unchanged (%s) - skipping", current_ip)
        return 0

    logger.info("IP changed: %s -> %s", state.last_synced_ip or "<none>", current_ip)

    if update_mam_ip():
        state.last_synced_ip = current_ip
        state.save()

    return 0


if __name__ == "__main__":
    sys.exit(main())
