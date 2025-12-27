"""Action plugin for smart_test - runs on controller, not TrueNAS."""

from typing import Any

from ansible.plugins.action import ActionBase
from ansible_collections.local.truenas.plugins.plugin_utils.midclt import (
    MidcltClient,
    MidcltError,
    ResourceRecord,
    format_diff,
)

RESOURCE = "smart.test"
IDENTITY_FIELDS = ["type", "all_disks"]
MANAGED_FIELDS = [
    "disks",
    "desc",
    "schedule",
]


def build_payload(params: dict[str, Any]) -> ResourceRecord:
    """Build the create/update payload from task params."""
    payload: ResourceRecord = {}
    for field in IDENTITY_FIELDS:
        payload[field] = params[field]
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
    """Manage TrueNAS SMART test schedules via midclt.

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

        if not params.get("type"):
            result["failed"] = True
            result["msg"] = "'type' is required"
            return result

        test_type: str = params["type"]
        if test_type not in ("SHORT", "LONG"):
            result["failed"] = True
            result["msg"] = "'type' must be SHORT or LONG"
            return result

        all_disks: bool = params.get("all_disks", True)
        params["all_disks"] = all_disks

        client = MidcltClient(self._low_level_execute_command)

        filters: list[list[Any]] = [
            ["type", "=", test_type],
            ["all_disks", "=", all_disks],
        ]

        try:
            existing = client.query_one(RESOURCE, filters)
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
        if params.get("schedule") is None:
            result["failed"] = True
            result["msg"] = "'schedule' is required when state=present"
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
