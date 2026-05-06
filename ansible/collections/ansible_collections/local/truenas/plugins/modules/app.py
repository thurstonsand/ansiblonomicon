#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: app
short_description: Manage TrueNAS SCALE catalog apps via midclt
description:
  - Creates, updates, upgrades, and deletes TrueNAS SCALE catalog apps.
  - Runs as an action plugin on the controller; only C(midclt) commands execute on TrueNAS.
  - C(values) are authoritative against catalog defaults. Top-level C(ix_*) generated values are ignored.
  - C(version=latest) installs/upgrades to the latest catalog version. A pinned version refuses implicit upgrade/downgrade.
options:
  name:
    description:
      - TrueNAS app instance name.
    type: str
    required: true
  catalog_app:
    description:
      - Catalog app slug. Defaults to C(name).
    type: str
  train:
    description:
      - Catalog train.
    type: str
    default: stable
  version:
    description:
      - Catalog app version to install.
      - C(latest) means install latest and upgrade when TrueNAS reports an upgrade available.
      - Any other value pins the installed app and refuses implicit upgrades/downgrades.
    type: str
    default: latest
  state:
    description:
      - Desired app state.
    type: str
    choices: [present, absent]
    default: present
  values:
    description:
      - Desired app values overlaid on catalog defaults.
      - Lists are authoritative. Dicts are recursively merged with catalog defaults.
      - Top-level generated C(ix_*) fields are ignored.
    type: dict
    default: {}
  remove_images:
    description:
      - Remove app images when C(state=absent).
    type: bool
    default: true
  remove_ix_volumes:
    description:
      - Remove ix-volumes when C(state=absent).
    type: bool
    default: false
  force_remove_ix_volumes:
    description:
      - Force ix-volume removal when C(state=absent).
    type: bool
    default: false
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Manage Netdata test app
  local.truenas.app:
    name: ansible-test-netdata
    catalog_app: netdata
    version: latest
    values:
      labels:
        - key: com.centurylinklabs.watchtower.enable
          value: "false"
          containers: [netdata]
      resources:
        limits:
          cpus: 1
          memory: 2048

- name: Remove Netdata test app and its ix-volumes
  local.truenas.app:
    name: ansible-test-netdata
    state: absent
    remove_ix_volumes: true
"""

RETURN = """
target_version:
  description: Catalog version targeted by the module.
  type: str
  returned: when state=present
values:
  description: Effective values sent to TrueNAS, after catalog defaults and desired values are merged.
  type: dict
  returned: when state=present
diff:
  description: Before/after app state or values when changed.
  type: dict
  returned: when changed
"""
