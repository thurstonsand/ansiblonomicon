#!/usr/bin/python

DOCUMENTATION = """
---
module: initshutdownscript
short_description: Manage TrueNAS init/shutdown scripts via midclt
description:
  - Create, update, or delete init/shutdown scripts on TrueNAS SCALE.
  - Uses midclt directly for SCALE compatibility.
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

import json
from typing import Any

from ansible.module_utils.basic import AnsibleModule

RESOURCE = "initshutdownscript"
IDENTITY_FIELD = "comment"

# Fields that can be set on create or update
MANAGED_FIELDS = ["type", "command", "script", "when", "enabled", "timeout"]

# Type alias for TrueNAS resource records
ResourceRecord = dict[str, Any]


def run_midclt(module: AnsibleModule, method: str, *args: Any) -> Any:
    """Run a midclt command and return parsed JSON output."""
    cmd: list[str] = ["midclt", "call", method]
    for arg in args:
        cmd.append(json.dumps(arg) if not isinstance(arg, str) else arg)

    rc, stdout, stderr = module.run_command(cmd)
    if rc != 0:
        module.fail_json(msg=f"midclt {method} failed: {stderr}", rc=rc)

    if stdout.strip():
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as e:
            module.fail_json(
                msg=f"midclt {method} returned invalid JSON: {e}", output=stdout
            )
    return None


def query_existing(module: AnsibleModule, identity_value: str) -> ResourceRecord | None:
    """Query for existing resource by identity field."""
    filter_arg = [[IDENTITY_FIELD, "=", identity_value]]
    results = run_midclt(module, f"{RESOURCE}.query", filter_arg)
    if results and len(results) > 0:
        return results[0]  # type: ignore[no-any-return]
    return None


def build_payload(module: AnsibleModule) -> ResourceRecord:
    """Build the create/update payload from module params."""
    payload: ResourceRecord = {IDENTITY_FIELD: module.params[IDENTITY_FIELD]}
    for field in MANAGED_FIELDS:
        value = module.params.get(field)
        if value is not None:
            payload[field] = value
    return payload


def compute_diff(existing: ResourceRecord, desired: ResourceRecord) -> ResourceRecord:
    """Compute which fields differ between existing and desired state."""
    changes: ResourceRecord = {}
    for key, desired_value in desired.items():
        if key == "id":
            continue
        existing_value = existing.get(key)
        if existing_value != desired_value:
            changes[key] = desired_value
    return changes


def format_diff(before: ResourceRecord, after: ResourceRecord) -> dict[str, str]:
    """Format diff output for Ansible."""
    return {
        "before": json.dumps(before, indent=2, sort_keys=True),
        "after": json.dumps(after, indent=2, sort_keys=True),
    }


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "comment": {"type": "str", "required": True},
            "type": {"type": "str", "choices": ["COMMAND", "SCRIPT"]},
            "command": {"type": "str"},
            "script": {"type": "str"},
            "when": {"type": "str", "choices": ["PREINIT", "POSTINIT", "SHUTDOWN"]},
            "enabled": {"type": "bool", "default": True},
            "timeout": {"type": "int"},
            "state": {
                "type": "str",
                "default": "present",
                "choices": ["present", "absent"],
            },
        },
        supports_check_mode=True,
        mutually_exclusive=[["command", "script"]],
        required_if=[
            ("state", "present", ("type", "when"), False),
            ("type", "COMMAND", ("command",), True),
            ("type", "SCRIPT", ("script",), True),
        ],
    )

    result: dict[str, Any] = {"changed": False}
    state: str = module.params["state"]
    identity_value: str = module.params[IDENTITY_FIELD]

    existing = query_existing(module, identity_value)

    if state == "absent":
        if existing is None:
            module.exit_json(**result)

        result["changed"] = True
        result["diff"] = format_diff(existing, {})

        if not module.check_mode:
            run_midclt(module, f"{RESOURCE}.delete", existing["id"])

        module.exit_json(**result)

    # state == present
    desired = build_payload(module)

    if existing is None:
        # Create new
        result["changed"] = True
        result["diff"] = format_diff({}, desired)

        if not module.check_mode:
            created = run_midclt(module, f"{RESOURCE}.create", desired)
            result["id"] = created["id"] if isinstance(created, dict) else created

        module.exit_json(**result)

    # Update existing - check what differs
    changes = compute_diff(existing, desired)

    if not changes:
        result["id"] = existing["id"]
        module.exit_json(**result)

    # Build after state for diff
    after = existing.copy()
    after.update(changes)

    result["changed"] = True
    result["id"] = existing["id"]
    result["diff"] = format_diff(existing, after)

    if not module.check_mode:
        run_midclt(module, f"{RESOURCE}.update", existing["id"], changes)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
