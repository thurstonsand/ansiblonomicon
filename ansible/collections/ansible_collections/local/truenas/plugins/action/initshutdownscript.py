"""Action plugin for initshutdownscript - runs on controller, not TrueNAS."""

from typing import Any

from ansible.plugins.action import ActionBase
from ansible_collections.local.truenas.plugins.plugin_utils.midclt import (
    MidcltClient,
    MidcltError,
    ResourceRecord,
    format_diff,
)

RESOURCE = "initshutdownscript"
IDENTITY_FIELD = "comment"
MANAGED_FIELDS = ["type", "command", "script", "when", "enabled", "timeout"]


def build_payload(params: dict[str, Any]) -> ResourceRecord:
    """Build the create/update payload from task params."""
    payload: ResourceRecord = {IDENTITY_FIELD: params[IDENTITY_FIELD]}
    for field in MANAGED_FIELDS:
        value = params.get(field)
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


class ActionModule(ActionBase):
    """Manage TrueNAS init/shutdown scripts via midclt.

    This action plugin runs entirely on the Ansible controller.
    Only raw midclt commands are executed on TrueNAS.
    """

    def run(
        self, tmp: str | None = None, task_vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = super().run(tmp, task_vars)
        result["changed"] = False

        params = self._task.args
        state: str = params.get("state", "present")
        identity_value: str = params.get(IDENTITY_FIELD, "")

        if not identity_value:
            result["failed"] = True
            result["msg"] = f"'{IDENTITY_FIELD}' is required"
            return result

        client = MidcltClient(self._low_level_execute_command)

        try:
            existing = client.query_one(
                RESOURCE, [[IDENTITY_FIELD, "=", identity_value]]
            )
        except MidcltError as e:
            result["failed"] = True
            result["msg"] = str(e)
            result["rc"] = e.rc
            return result

        if state == "absent":
            if existing is None:
                return result

            result["changed"] = True
            result["diff"] = format_diff(existing, {})

            if not self._play_context.check_mode:
                try:
                    client.delete(RESOURCE, existing["id"])
                except MidcltError as e:
                    result["failed"] = True
                    result["msg"] = str(e)
                    result["rc"] = e.rc

            return result

        # state == present
        # Validate required fields
        script_type = params.get("type")
        when = params.get("when")
        if not script_type or not when:
            result["failed"] = True
            result["msg"] = "'type' and 'when' are required when state=present"
            return result

        if script_type == "COMMAND" and not params.get("command"):
            result["failed"] = True
            result["msg"] = "'command' is required when type=COMMAND"
            return result

        if script_type == "SCRIPT" and not params.get("script"):
            result["failed"] = True
            result["msg"] = "'script' is required when type=SCRIPT"
            return result

        desired = build_payload(params)

        if existing is None:
            result["changed"] = True
            result["diff"] = format_diff({}, desired)

            if not self._play_context.check_mode:
                try:
                    created = client.create(RESOURCE, desired)
                    result["id"] = created.id
                except MidcltError as e:
                    result["failed"] = True
                    result["msg"] = str(e)
                    result["rc"] = e.rc

            return result

        # Update existing - check what differs
        changes = compute_diff(existing, desired)

        if not changes:
            result["id"] = existing["id"]
            return result

        after = existing.copy()
        after.update(changes)

        result["changed"] = True
        result["id"] = existing["id"]
        result["diff"] = format_diff(existing, after)

        if not self._play_context.check_mode:
            try:
                client.update(RESOURCE, existing["id"], changes)
            except MidcltError as e:
                result["failed"] = True
                result["msg"] = str(e)
                result["rc"] = e.rc

        return result
