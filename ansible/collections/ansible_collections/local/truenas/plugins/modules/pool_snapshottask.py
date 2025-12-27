#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: pool_snapshottask
short_description: Manage TrueNAS periodic snapshot tasks via midclt
description:
  - Create, update, or delete periodic snapshot tasks on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity is C(dataset) + C(naming_schema) + C(lifetime_unit) - used to find existing tasks.
options:
  dataset:
    description:
      - The dataset to snapshot (pool or pool/dataset path).
    type: str
    required: true
  naming_schema:
    description:
      - Naming schema for snapshots (e.g., "auto-%Y-%m-%d_%H-%M").
    type: str
    required: true
  recursive:
    description:
      - Whether to snapshot child datasets recursively.
    type: bool
    default: true
  exclude:
    description:
      - List of child datasets to exclude from recursive snapshots.
    type: list
    elements: str
    default: []
  lifetime_value:
    description:
      - How long to keep snapshots (numeric value).
    type: int
  lifetime_unit:
    description:
      - Unit for lifetime_value.
      - Part of identity (with dataset and naming_schema) to find existing tasks.
    type: str
    required: true
    choices: [HOUR, DAY, WEEK, MONTH, YEAR]
  schedule:
    description:
      - Cron-style schedule as a dict with minute, hour, dom, month, dow keys.
      - Also supports begin/end for time window restrictions.
    type: dict
  enabled:
    description:
      - Whether the snapshot task is enabled.
    type: bool
    default: true
  allow_empty:
    description:
      - Whether to create snapshots even if no data changed.
    type: bool
    default: true
  vmware_sync:
    description:
      - Whether to sync with VMware before snapshot.
    type: bool
    default: false
  state:
    description:
      - Whether the snapshot task should exist.
    type: str
    choices: [present, absent]
    default: present
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Create 6-hourly snapshots with 3-day retention
  local.truenas.pool_snapshottask:
    dataset: performance
    naming_schema: "auto-%Y-%m-%d_%H-%M"
    recursive: true
    lifetime_value: 3
    lifetime_unit: DAY
    schedule:
      minute: "0"
      hour: "*/6"
      dom: "*"
      month: "*"
      dow: "*"
    enabled: true
    state: present

- name: Create monthly snapshots
  local.truenas.pool_snapshottask:
    dataset: performance
    naming_schema: "monthly-%Y-%m-%d_%H-%M"
    lifetime_value: 1
    lifetime_unit: MONTH
    schedule:
      minute: "0"
      hour: "0"
      dom: "1"
      month: "*"
      dow: "*"
    state: present

- name: Remove a snapshot task
  local.truenas.pool_snapshottask:
    dataset: performance
    naming_schema: "old-schema"
    lifetime_unit: DAY
    state: absent
"""

RETURN = """
id:
  description: The ID of the snapshot task in TrueNAS.
  type: int
  returned: when state=present
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
