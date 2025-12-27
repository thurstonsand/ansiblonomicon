#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: sharing_nfs
short_description: Manage TrueNAS NFS shares via midclt
description:
  - Create, update, or delete NFS shares on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity field is C(path) - the filesystem path being shared.
options:
  path:
    description:
      - The filesystem path to share via NFS.
    type: str
    required: true
  aliases:
    description:
      - List of path aliases for the share.
    type: list
    elements: str
    default: []
  comment:
    description:
      - Optional comment/description for the share.
    type: str
    default: ""
  networks:
    description:
      - List of networks allowed to access this share (CIDR notation).
    type: list
    elements: str
    default: []
  hosts:
    description:
      - List of hosts allowed to access this share.
    type: list
    elements: str
    default: []
  ro:
    description:
      - Whether the share is read-only.
    type: bool
    default: false
  maproot_user:
    description:
      - User to map root to (for root squashing).
    type: str
  maproot_group:
    description:
      - Group to map root to (for root squashing).
    type: str
  mapall_user:
    description:
      - Map all users to this user.
    type: str
  mapall_group:
    description:
      - Map all users to this group.
    type: str
  security:
    description:
      - List of security flavors (e.g., krb5, krb5i, krb5p, sys).
    type: list
    elements: str
    default: []
  enabled:
    description:
      - Whether the share is enabled.
    type: bool
    default: true
  state:
    description:
      - Whether the share should exist.
    type: str
    choices: [present, absent]
    default: present
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Create an NFS share for local network
  local.truenas.sharing_nfs:
    path: /mnt/pool/data
    networks:
      - 192.168.1.0/24
    maproot_user: root
    maproot_group: wheel
    enabled: true
    state: present

- name: Create a read-only NFS share
  local.truenas.sharing_nfs:
    path: /mnt/pool/readonly
    networks:
      - 192.168.1.0/24
    ro: true
    state: present

- name: Remove an NFS share
  local.truenas.sharing_nfs:
    path: /mnt/pool/oldshare
    state: absent
"""

RETURN = """
id:
  description: The ID of the share in TrueNAS.
  type: int
  returned: when state=present
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
