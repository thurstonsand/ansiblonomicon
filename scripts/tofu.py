#!/usr/bin/env python3
"""Map canonical fnox credentials to OpenTofu's environment contract."""

import os
import sys

ALIASES = {
    "TF_VAR_cloudflare_api_token": "CLOUDFLARE_API_TOKEN",
    "TF_VAR_parent_home_ip": "PARENT_HOME_IP",
    "TF_VAR_unifi_username": "UNIFI_USERNAME",
    "TF_VAR_unifi_password": "UNIFI_PASSWORD",
    "TF_VAR_unifi_wan_mac_override": "UNIFI_WAN_MAC_OVERRIDE",
    "TF_VAR_yorha_passphrase": "YORHA_PASSPHRASE",
    "TF_VAR_lunar_tear_passphrase": "LUNAR_TEAR_PASSPHRASE",
    "TF_VAR_the_village_passphrase": "THE_VILLAGE_PASSPHRASE",
    "TF_VAR_scanners_passphrase": "SCANNERS_PASSPHRASE",
}

for destination, source in ALIASES.items():
    os.environ[destination] = os.environ[source]
os.execvp("tofu", ["tofu", *sys.argv[1:]])
