"""Action plugin for sharing_nfs - runs on controller, not TrueNAS."""

from typing import Any

from ansible.plugins.action import ActionBase
from ansible_collections.local.truenas.plugins.plugin_utils.midclt import (
    MidcltClient,
    MidcltError,
    ResourceRecord,
    format_diff,
)

RESOURCE = "sharing.nfs"
IDENTITY_FIELD = "path"
MANAGED_FIELDS = [
    "aliases",
    "comment",
    "networks",
    "hosts",
    "ro",
    "maproot_user",
    "maproot_group",
    "mapall_user",
    "mapall_group",
    "security",
    "enabled",
]


def build_payload(params: dict[str, Any]) -> ResourceRecord:
    """Build the create/update payload from task params."""
    payload: ResourceRecord = {IDENTITY_FIELD: params[IDENTITY_FIELD]}
    for field in MANAGED_FIELDS:
        value = params.get(field)
        if value is not None:
            payload[field] = value
    return payload


def normalize_value(value: Any) -> Any:
    """Normalize values for comparison (handle null vs empty string)."""
    if value is None or value == "":
        return None
    return value


def compute_diff(existing: ResourceRecord, desired: ResourceRecord) -> ResourceRecord:
    """Compute which fields differ between existing and desired state."""
    changes: ResourceRecord = {}
    for key, desired_value in desired.items():
        if key in ("id", "locked"):
            continue
        existing_value = existing.get(key)
        if normalize_value(existing_value) != normalize_value(desired_value):
            changes[key] = desired_value
    return changes


class ActionModule(ActionBase):
    """Manage TrueNAS NFS shares via midclt.

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
