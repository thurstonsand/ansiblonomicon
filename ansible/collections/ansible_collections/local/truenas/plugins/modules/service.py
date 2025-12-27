#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: service
short_description: Manage TrueNAS service state via midclt
description:
  - Enable, disable, start, or stop services on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity field is C(name) - the service name.
options:
  name:
    description:
      - The service name (e.g., cifs, nfs, ssh, smartd, ups).
    type: str
    required: true
  enabled:
    description:
      - Whether the service should start on boot.
    type: bool
  state:
    description:
      - Desired state of the service.
      - C(started) ensures the service is running.
      - C(stopped) ensures the service is not running.
      - C(restarted) restarts the service.
      - If not specified, only the enabled setting is managed.
    type: str
    choices: [started, stopped, restarted]
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Ensure SMB service is enabled and running
  local.truenas.service:
    name: cifs
    enabled: true
    state: started

- name: Disable FTP service
  local.truenas.service:
    name: ftp
    enabled: false
    state: stopped

- name: Restart SSH service
  local.truenas.service:
    name: ssh
    state: restarted

- name: Just enable a service without starting it
  local.truenas.service:
    name: snmp
    enabled: true
"""

RETURN = """
id:
  description: The ID of the service in TrueNAS.
  type: int
  returned: always
running:
  description: Whether the service is currently running.
  type: bool
  returned: always
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
