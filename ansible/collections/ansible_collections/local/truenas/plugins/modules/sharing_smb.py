#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: sharing_smb
short_description: Manage TrueNAS SMB shares via midclt
description:
  - Create, update, or delete SMB shares on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity field is C(name) - the share name.
options:
  name:
    description:
      - The SMB share name (what clients see).
    type: str
    required: true
  path:
    description:
      - The filesystem path to share.
    type: str
  path_suffix:
    description:
      - Suffix appended to path (supports %U for username, etc.).
    type: str
  purpose:
    description:
      - Share preset/purpose.
    type: str
    choices: [NO_PRESET, DEFAULT_SHARE, ENHANCED_TIMEMACHINE, MULTI_PROTOCOL_AFP, MULTI_PROTOCOL_NFS, PRIVATE_DATASETS, WORM_DROPBOX]
    default: DEFAULT_SHARE
  comment:
    description:
      - Optional comment/description for the share.
    type: str
  ro:
    description:
      - Whether the share is read-only.
    type: bool
    default: false
  browsable:
    description:
      - Whether the share is visible in browse lists.
    type: bool
    default: true
  guestok:
    description:
      - Whether guest access is allowed.
    type: bool
    default: false
  hostsallow:
    description:
      - List of allowed hosts/networks.
    type: list
    elements: str
    default: []
  hostsdeny:
    description:
      - List of denied hosts/networks.
    type: list
    elements: str
    default: []
  recyclebin:
    description:
      - Whether to enable recycle bin.
    type: bool
    default: false
  abe:
    description:
      - Access-based enumeration (hide inaccessible files).
    type: bool
    default: false
  acl:
    description:
      - Whether to enable ACL support.
    type: bool
    default: true
  durablehandle:
    description:
      - Whether to enable durable handles for resilient file operations.
    type: bool
    default: true
  streams:
    description:
      - Whether to enable alternate data streams support.
    type: bool
    default: true
  timemachine:
    description:
      - Whether this is a Time Machine share.
    type: bool
    default: false
  timemachine_quota:
    description:
      - Quota in bytes for Time Machine (0 for unlimited).
    type: int
    default: 0
  shadowcopy:
    description:
      - Whether to enable shadow copies (previous versions).
    type: bool
    default: true
  fsrvp:
    description:
      - Whether to enable File Server Remote VSS Protocol.
    type: bool
    default: false
  auxsmbconf:
    description:
      - Additional smb.conf parameters.
    type: str
    default: ""
  enabled:
    description:
      - Whether the share is enabled.
    type: bool
    default: true
  home:
    description:
      - Whether this is a home share.
    type: bool
    default: false
  afp:
    description:
      - Whether AFP compatibility is enabled.
    type: bool
    default: false
  aapl_name_mangling:
    description:
      - Whether to enable Apple-style name mangling.
    type: bool
    default: false
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
- name: Create a simple SMB share
  local.truenas.sharing_smb:
    name: documents
    path: /mnt/pool/documents
    comment: "Shared documents"
    state: present

- name: Create a Time Machine share
  local.truenas.sharing_smb:
    name: timemachine-mac
    path: /mnt/pool/backup/timemachine
    purpose: ENHANCED_TIMEMACHINE
    path_suffix: "%U"
    timemachine: true
    state: present

- name: Remove an SMB share
  local.truenas.sharing_smb:
    name: oldshare
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
