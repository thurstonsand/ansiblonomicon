"""Action plugin for vm - runs on controller, not TrueNAS."""

import secrets
from typing import Any, cast

from ansible.plugins.action import ActionBase
from ansible_collections.local.truenas.plugins.plugin_utils.midclt import (
    MidcltClient,
    MidcltError,
    ResourceRecord,
    format_diff,
)

VM_RESOURCE = "vm"
DEVICE_RESOURCE = "vm.device"

VM_MANAGED_FIELDS = [
    "command_line_args",
    "cpu_mode",
    "cpu_model",
    "name",
    "description",
    "vcpus",
    "cores",
    "threads",
    "cpuset",
    "nodeset",
    "enable_cpu_topology_extension",
    "pin_vcpus",
    "suspend_on_snapshot",
    "trusted_platform_module",
    "memory",
    "min_memory",
    "hyperv_enlightenments",
    "bootloader",
    "bootloader_ovmf",
    "autostart",
    "hide_from_msr",
    "ensure_display_device",
    "time",
    "shutdown_timeout",
    "arch_type",
    "machine_type",
    "uuid",
]

DEVICE_IDENTITY_KEYS = {
    "DISK": ["path"],
    "RAW": ["path"],
    "CDROM": ["path"],
    "NIC": ["mac"],
    "DISPLAY": ["type"],
    "USB": ["device"],
    "PCI": ["pptdev"],
}

POWER_STATES = {"started", "stopped", "restarted"}
ZVOL_FIELDS = ["name", "volsize", "volblocksize", "sparse", "comments"]


def normalize(value: Any) -> Any:
    """Normalize TrueNAS API values for comparison."""
    if value == "":
        return None
    return value


def as_record(value: Any) -> ResourceRecord:
    """Return value as a resource record, or an empty record."""
    return cast(ResourceRecord, value) if isinstance(value, dict) else {}


def as_record_list(value: Any) -> list[ResourceRecord]:
    """Return value as a list of resource records, ignoring malformed entries."""
    if not isinstance(value, list):
        return []
    items = cast(list[Any], value)
    return [cast(ResourceRecord, item) for item in items if isinstance(item, dict)]


def build_vm_payload(params: dict[str, Any]) -> ResourceRecord:
    """Build VM create/update payload from provided parameters."""
    payload: ResourceRecord = {}
    for field in VM_MANAGED_FIELDS:
        if field in params and params[field] is not None:
            payload[field] = params[field]
    return payload


def compute_field_changes(
    existing: ResourceRecord, desired: ResourceRecord, fields: list[str] | None = None
) -> ResourceRecord:
    """Return fields whose desired values differ from existing values."""
    changes: ResourceRecord = {}
    desired_items = (
        desired.items()
        if fields is None
        else ((k, desired[k]) for k in fields if k in desired)
    )
    for key, desired_value in desired_items:
        if normalize(existing.get(key)) != normalize(desired_value):
            changes[key] = desired_value
    return changes


def device_identity(device: ResourceRecord) -> str:
    """Return a stable identity string for a desired or existing VM device."""
    explicit_identity = device.get("identity")
    if explicit_identity:
        return f"{device.get('dtype')}:{explicit_identity}"

    dtype = str(device.get("dtype", ""))
    attributes = as_record(device.get("attributes"))
    for key in DEVICE_IDENTITY_KEYS.get(dtype, []):
        value = attributes.get(key)
        if value:
            return f"{dtype}:{value}"

    if dtype == "DISPLAY":
        return "DISPLAY:SPICE"

    # Fall back to dtype plus order. This is intentionally conservative: callers
    # should provide a natural identity for multi-device dtypes.
    order = device.get("order")
    return f"{dtype}:order:{order}"


def sanitize_device(device: ResourceRecord) -> ResourceRecord:
    """Keep only fields accepted by vm.device.create/update."""
    sanitized: ResourceRecord = {
        "dtype": device["dtype"],
        "attributes": as_record(device.get("attributes")),
    }
    if device.get("order") is not None:
        sanitized["order"] = device["order"]
    if device.get("vm") is not None:
        sanitized["vm"] = device["vm"]
    return sanitized


def compute_device_changes(
    existing: ResourceRecord, desired: ResourceRecord
) -> ResourceRecord:
    """Return device fields that differ, comparing only caller-provided attrs."""
    changes: ResourceRecord = {}

    if existing.get("dtype") != desired.get("dtype"):
        changes["dtype"] = desired["dtype"]

    if desired.get("order") is not None and existing.get("order") != desired.get(
        "order"
    ):
        changes["order"] = desired["order"]

    desired_attributes = as_record(desired.get("attributes"))
    existing_attributes = as_record(existing.get("attributes"))
    attribute_changes = compute_field_changes(existing_attributes, desired_attributes)
    if attribute_changes:
        merged_attributes = existing_attributes.copy()
        merged_attributes.update(attribute_changes)
        changes["attributes"] = merged_attributes

    return changes


def merge_diff(
    existing_diff: dict[str, Any], key: str, before: Any, after: Any
) -> None:
    """Append a nested diff entry."""
    existing_diff[key] = {"before": before, "after": after}


class ActionModule(ActionBase):
    """Manage opinionated TrueNAS VMs via midclt."""

    def run(
        self, tmp: str | None = None, task_vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = super().run(tmp, task_vars)
        result["changed"] = False
        changed_devices: list[ResourceRecord] = []
        result["changed_devices"] = changed_devices

        params: dict[str, Any] = self._task.args
        name = str(params.get("name", ""))
        state = str(params.get("state", "present"))
        power_state = params.get("power_state")

        if not name:
            result["failed"] = True
            result["msg"] = "'name' is required"
            return result
        if state not in {"present", "absent"}:
            result["failed"] = True
            result["msg"] = "'state' must be 'present' or 'absent'"
            return result
        if power_state is not None and power_state not in POWER_STATES:
            result["failed"] = True
            result["msg"] = "'power_state' must be one of started, stopped, restarted"
            return result

        client = MidcltClient(self._low_level_execute_command)

        try:
            existing = client.query_one(VM_RESOURCE, [["name", "=", name]])
        except MidcltError as e:
            result["failed"] = True
            result["msg"] = str(e)
            result["rc"] = e.rc
            return result

        if state == "absent":
            if existing is None:
                return result
            result["changed"] = True
            result["id"] = existing["id"]
            result["diff"] = format_diff(existing, {})
            if not self._play_context.check_mode:
                try:
                    client.delete(VM_RESOURCE, int(existing["id"]))
                except MidcltError as e:
                    result["failed"] = True
                    result["msg"] = str(e)
                    result["rc"] = e.rc
            return result

        desired_vm = build_vm_payload(params)
        desired_vm["name"] = name
        diff: dict[str, Any] = {}

        try:
            for zvol in as_record_list(params.get("zvols", [])):
                zvol_name = zvol.get("name")
                if not zvol_name:
                    result["failed"] = True
                    result["msg"] = "Each zvol entry requires 'name'"
                    return result
                if not zvol.get("volsize"):
                    result["failed"] = True
                    result["msg"] = f"zvol '{zvol_name}' requires 'volsize'"
                    return result

                existing_zvol = client.query_one(
                    "pool.dataset", [["id", "=", zvol_name]]
                )
                desired_zvol: ResourceRecord = {
                    "name": zvol_name,
                    "type": "VOLUME",
                    "volsize": zvol["volsize"],
                }
                for field in ZVOL_FIELDS:
                    if field in zvol and zvol[field] is not None:
                        desired_zvol[field] = zvol[field]

                if existing_zvol is None:
                    result["changed"] = True
                    merge_diff(diff, f"zvol:{zvol_name}", {}, desired_zvol)
                    if not self._play_context.check_mode:
                        client.create_dataset(desired_zvol)

            if existing is None:
                if "memory" not in desired_vm:
                    result["failed"] = True
                    result["msg"] = "'memory' is required when creating a VM"
                    return result

                result["changed"] = True
                merge_diff(diff, "vm", {}, desired_vm)

                if self._play_context.check_mode:
                    vm_id = -1
                else:
                    created = client.create(VM_RESOURCE, desired_vm)
                    vm_id = created.id
                existing = desired_vm.copy()
                existing["id"] = vm_id
            else:
                vm_id = int(existing["id"])
                vm_changes = compute_field_changes(existing, desired_vm)
                if vm_changes:
                    after_vm = existing.copy()
                    after_vm.update(vm_changes)
                    result["changed"] = True
                    merge_diff(diff, "vm", existing, after_vm)
                    if not self._play_context.check_mode:
                        client.update(VM_RESOURCE, vm_id, vm_changes)
                    existing = after_vm

            result["id"] = vm_id

            existing_devices = (
                client.query(DEVICE_RESOURCE, [["vm", "=", vm_id]]) if vm_id > 0 else []
            )
            existing_by_identity = {
                device_identity(device): device for device in existing_devices
            }

            for raw_device in as_record_list(params.get("devices", [])):
                desired_device = sanitize_device(raw_device)
                desired_device["vm"] = vm_id
                identity = device_identity(raw_device)
                matching_device = existing_by_identity.get(identity)

                if matching_device is None:
                    create_device = desired_device.copy()
                    create_attributes = as_record(
                        create_device.get("attributes")
                    ).copy()
                    if create_device[
                        "dtype"
                    ] == "DISPLAY" and not create_attributes.get("password"):
                        create_attributes["password"] = secrets.token_urlsafe(18)
                        create_device["attributes"] = create_attributes

                    diff_device = create_device.copy()
                    diff_attributes = as_record(diff_device.get("attributes")).copy()
                    if "password" in diff_attributes:
                        diff_attributes["password"] = "<generated>"
                        diff_device["attributes"] = diff_attributes

                    result["changed"] = True
                    changed_devices.append({"identity": identity, "action": "create"})
                    merge_diff(diff, f"device:{identity}", {}, diff_device)
                    if not self._play_context.check_mode:
                        created_device = client.create(DEVICE_RESOURCE, create_device)
                        changed_devices[-1]["id"] = created_device.id
                    continue

                device_changes = compute_device_changes(matching_device, desired_device)
                if not device_changes:
                    continue

                update_payload = sanitize_device(matching_device)
                update_payload.update(device_changes)
                update_payload["vm"] = vm_id

                after_device = matching_device.copy()
                after_device.update(device_changes)

                result["changed"] = True
                changed_devices.append(
                    {
                        "identity": identity,
                        "action": "update",
                        "id": matching_device["id"],
                    }
                )
                merge_diff(diff, f"device:{identity}", matching_device, after_device)
                if not self._play_context.check_mode:
                    client.update(
                        DEVICE_RESOURCE, int(matching_device["id"]), update_payload
                    )

            if power_state is not None:
                vm_record = (
                    client.query_one(VM_RESOURCE, [["id", "=", vm_id]])
                    if vm_id > 0
                    else existing
                )
                status = (vm_record or {}).get("status", {})
                running = status.get("state") == "RUNNING"

                if power_state == "started" and not running:
                    result["changed"] = True
                    merge_diff(diff, "power_state", status.get("state"), "RUNNING")
                    if not self._play_context.check_mode:
                        client.vm_start(vm_id)
                elif power_state == "stopped" and running:
                    result["changed"] = True
                    merge_diff(diff, "power_state", status.get("state"), "STOPPED")
                    if not self._play_context.check_mode:
                        client.vm_stop(vm_id)
                elif power_state == "restarted":
                    result["changed"] = True
                    merge_diff(diff, "power_state", status.get("state"), "RUNNING")
                    if not self._play_context.check_mode:
                        client.vm_restart(vm_id)

        except MidcltError as e:
            result["failed"] = True
            result["msg"] = str(e)
            result["rc"] = e.rc
            return result

        if result["changed"]:
            result["diff"] = diff

        return result
