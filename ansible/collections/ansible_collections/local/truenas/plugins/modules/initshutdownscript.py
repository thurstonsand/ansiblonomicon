#!/usr/bin/python
# This module is implemented as an action plugin.
# This file exists only for documentation and argument validation.

DOCUMENTATION = """
---
module: initshutdownscript
short_description: Manage TrueNAS init/shutdown scripts via midclt
description:
  - Create, update, or delete init/shutdown scripts on TrueNAS SCALE.
  - Runs as an action plugin on the controller - only midclt commands execute on TrueNAS.
  - Identity field is C(comment) - used to find existing scripts.
options:
  comment:
    description:
      - Name/identifier for the script. Used to find existing scripts.
    type: str
    required: true
  type:
    description:
      - Type of script.
      - C(COMMAND) runs a single command.
      - C(SCRIPT) runs a script file at the given path.
    type: str
    choices: [COMMAND, SCRIPT]
  command:
    description:
      - Command to execute (when type=COMMAND).
    type: str
  script:
    description:
      - Path to script file (when type=SCRIPT).
    type: str
  when:
    description:
      - When to execute the script.
      - C(PREINIT) - early boot, before services.
      - C(POSTINIT) - late boot, after services.
      - C(SHUTDOWN) - during shutdown.
    type: str
    choices: [PREINIT, POSTINIT, SHUTDOWN]
  enabled:
    description:
      - Whether the script is enabled.
    type: bool
    default: true
  timeout:
    description:
      - Seconds to wait for script to complete.
    type: int
  state:
    description:
      - Whether the script should exist.
    type: str
    choices: [present, absent]
    default: present
author:
  - Thurston Sandberg
"""

EXAMPLES = """
- name: Enable Wake-on-LAN at boot
  local.truenas.initshutdownscript:
    comment: "enable WOL"
    type: COMMAND
    command: "ethtool -s enp3s0 wol g"
    when: POSTINIT
    enabled: true
    timeout: 20
    state: present

- name: Remove old init script
  local.truenas.initshutdownscript:
    comment: "old script"
    state: absent
"""

RETURN = """
id:
  description: The ID of the script in TrueNAS.
  type: int
  returned: when state=present
diff:
  description: Before/after state for changed resources.
  type: dict
  returned: when changed
"""
