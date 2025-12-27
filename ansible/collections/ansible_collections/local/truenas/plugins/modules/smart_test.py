#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: smart_test
short_description: Manage TrueNAS SMART test schedules via midclt
description:
  - Create, update, or delete SMART test schedules on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity is C(type) + C(all_disks) - typically one SHORT and one LONG test.
options:
  type:
    description:
      - The type of SMART test to schedule.
    type: str
    required: true
    choices: [SHORT, LONG]
  all_disks:
    description:
      - Whether to run the test on all disks.
      - Part of identity (with type) to find existing schedules.
    type: bool
    default: true
  disks:
    description:
      - List of disk identifiers to test (only used when all_disks=false).
    type: list
    elements: str
    default: []
  desc:
    description:
      - Description for the SMART test schedule.
    type: str
    default: ""
  schedule:
    description:
      - Cron-style schedule as a dict with hour, dom, month, dow keys.
    type: dict
  state:
    description:
      - Whether the SMART test schedule should exist.
    type: str
    choices: [present, absent]
    default: present
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Create daily short SMART test at midnight
  local.truenas.smart_test:
    type: SHORT
    all_disks: true
    schedule:
      hour: "0"
      dom: "*"
      month: "*"
      dow: "*"
    state: present

- name: Create monthly long SMART test on the 1st at 1am
  local.truenas.smart_test:
    type: LONG
    all_disks: true
    schedule:
      hour: "1"
      dom: "1"
      month: "*"
      dow: "*"
    state: present

- name: Remove a SMART test schedule
  local.truenas.smart_test:
    type: SHORT
    all_disks: true
    state: absent
"""

RETURN = """
id:
  description: The ID of the SMART test schedule in TrueNAS.
  type: int
  returned: when state=present
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
