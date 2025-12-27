#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: pool_scrub
short_description: Manage TrueNAS pool scrub tasks via midclt
description:
  - Create, update, or delete periodic scrub tasks on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity field is C(pool_name) - each pool can have one scrub task.
options:
  pool_name:
    description:
      - The name of the pool to scrub.
    type: str
    required: true
  threshold:
    description:
      - Days between scrubs. Scrub will be skipped if last scrub was within this many days.
    type: int
    default: 35
  description:
    description:
      - Optional description for the scrub task.
    type: str
    default: ""
  schedule:
    description:
      - Cron-style schedule as a dict with minute, hour, dom, month, dow keys.
    type: dict
  enabled:
    description:
      - Whether the scrub task is enabled.
    type: bool
    default: true
  state:
    description:
      - Whether the scrub task should exist.
    type: str
    choices: [present, absent]
    default: present
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Schedule weekly scrub on Tuesday at 4am
  local.truenas.pool_scrub:
    pool_name: performance
    threshold: 35
    schedule:
      minute: "0"
      hour: "4"
      dom: "*"
      month: "*"
      dow: "tue"
    enabled: true
    state: present

- name: Remove scrub task
  local.truenas.pool_scrub:
    pool_name: oldpool
    state: absent
"""

RETURN = """
id:
  description: The ID of the scrub task in TrueNAS.
  type: int
  returned: when state=present
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
