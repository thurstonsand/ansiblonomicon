"""Action plugin for app - runs on controller, not TrueNAS."""

from copy import deepcopy
from typing import Any, cast

from ansible.plugins.action import ActionBase
from ansible_collections.local.truenas.plugins.plugin_utils.midclt import (
    MidcltClient,
    MidcltError,
    ResourceRecord,
    format_diff,
)

GENERATED_PREFIX = "ix_"


def as_record(value: Any) -> ResourceRecord:
    """Return value as a resource record, or an empty record."""
    return cast(ResourceRecord, value) if isinstance(value, dict) else {}


def strip_generated_values(values: ResourceRecord) -> ResourceRecord:
    """Remove top-level generated TrueNAS app fields."""
    return {
        key: value
        for key, value in values.items()
        if not key.startswith(GENERATED_PREFIX)
    }


def overlay_top_level(base: ResourceRecord, override: ResourceRecord) -> ResourceRecord:
    """Overlay caller values onto catalog defaults at top-level only."""
    merged = deepcopy(base)
    for key, value in override.items():
        merged[key] = deepcopy(value)
    return merged


def prune_to_shape(value: Any, shape: Any) -> Any:
    """Project value onto shape so TrueNAS-expanded defaults do not cause drift."""
    if isinstance(value, dict) and isinstance(shape, dict):
        value_record = cast(ResourceRecord, value)
        shape_record = cast(ResourceRecord, shape)
        projected: ResourceRecord = {}
        for key in sorted(shape_record):
            projected[key] = prune_to_shape(value_record.get(key), shape_record[key])
        return projected
    return cast(Any, value)


def normalize(value: Any) -> Any:
    """Normalize values for stable comparison."""
    if isinstance(value, dict):
        record = cast(ResourceRecord, value)
        return {key: normalize(record[key]) for key in sorted(record)}
    if isinstance(value, list):
        items = cast(list[Any], value)
        return [normalize(item) for item in items]
    return value


class ActionModule(ActionBase):
    """Manage a TrueNAS SCALE catalog app."""

    def run(
        self, tmp: str | None = None, task_vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = super().run(tmp, task_vars)
        result["changed"] = False

        params: dict[str, Any] = self._task.args
        name = str(params.get("name", ""))
        catalog_app = str(params.get("catalog_app", name))
        train = str(params.get("train", "stable"))
        version = str(params.get("version", "latest"))
        state = str(params.get("state", "present"))
        desired_values = as_record(params.get("values"))
        remove_images = bool(params.get("remove_images", True))
        remove_ix_volumes = bool(params.get("remove_ix_volumes", False))
        force_remove_ix_volumes = bool(params.get("force_remove_ix_volumes", False))

        if not name:
            result["failed"] = True
            result["msg"] = "'name' is required"
            return result
        if state not in {"present", "absent"}:
            result["failed"] = True
            result["msg"] = "'state' must be 'present' or 'absent'"
            return result

        client = MidcltClient(self._low_level_execute_command)

        try:
            existing = self._query_app(client, name)
        except MidcltError as e:
            return self._failed(result, e)

        if state == "absent":
            if existing is None:
                return result
            result["changed"] = True
            result["diff"] = format_diff(existing, {})
            if not self._play_context.check_mode:
                try:
                    client.call_job(
                        "app.delete",
                        name,
                        {
                            "remove_images": remove_images,
                            "remove_ix_volumes": remove_ix_volumes,
                            "force_remove_ix_volumes": force_remove_ix_volumes,
                        },
                    )
                except MidcltError as e:
                    return self._failed(result, e)
            return result

        try:
            target_version = self._target_version(client, catalog_app, train, version)
            defaults = self._catalog_defaults(
                client, catalog_app, train, target_version
            )
        except MidcltError as e:
            return self._failed(result, e)

        effective_values = overlay_top_level(
            defaults, strip_generated_values(desired_values)
        )
        result["target_version"] = target_version
        result["values"] = effective_values

        if existing is None:
            result["changed"] = True
            result["diff"] = format_diff(
                {},
                {
                    "name": name,
                    "catalog_app": catalog_app,
                    "train": train,
                    "version": target_version,
                    "values": effective_values,
                },
            )
            if not self._play_context.check_mode:
                try:
                    client.call_job(
                        "app.create",
                        {
                            "app_name": name,
                            "catalog_app": catalog_app,
                            "train": train,
                            "version": target_version,
                            "values": effective_values,
                        },
                    )
                except MidcltError as e:
                    return self._failed(result, e)
            return result

        existing_version = str(existing.get("version", ""))
        if version == "latest" and existing.get("upgrade_available"):
            result["changed"] = True
            result["upgrade"] = {"from": existing_version, "to": target_version}
            if not self._play_context.check_mode:
                try:
                    client.call_job(
                        "app.upgrade",
                        name,
                        {"app_version": "latest", "values": effective_values},
                    )
                except MidcltError as e:
                    return self._failed(result, e)
                return result
        elif version != "latest" and existing_version != target_version:
            result["failed"] = True
            result["msg"] = (
                f"app {name!r} is at version {existing_version!r}, "
                f"but pinned version is {target_version!r}; refusing implicit upgrade/downgrade"
            )
            return result

        try:
            current_config = as_record(client.call("app.config", name))
        except MidcltError as e:
            return self._failed(result, e)

        current_values = strip_generated_values(current_config)
        comparable_current = prune_to_shape(current_values, effective_values)
        if normalize(comparable_current) == normalize(effective_values):
            return result

        result["changed"] = True
        result["diff"] = format_diff(
            {"values": comparable_current}, {"values": effective_values}
        )
        if not self._play_context.check_mode:
            try:
                client.call_job("app.update", name, {"values": effective_values})
            except MidcltError as e:
                return self._failed(result, e)

        return result

    def _query_app(self, client: MidcltClient, name: str) -> ResourceRecord | None:
        apps = client.query("app", [["name", "=", name]])
        return apps[0] if apps else None

    def _target_version(
        self, client: MidcltClient, catalog_app: str, train: str, version: str
    ) -> str:
        if version != "latest":
            return version
        details = as_record(
            client.call("catalog.get_app_details", catalog_app, {"train": train})
        )
        return str(details.get("latest_version", "latest"))

    def _catalog_defaults(
        self, client: MidcltClient, catalog_app: str, train: str, version: str
    ) -> ResourceRecord:
        details = as_record(
            client.call("catalog.get_app_details", catalog_app, {"train": train})
        )
        versions = as_record(details.get("versions"))
        version_details = as_record(versions.get(version))
        defaults = as_record(version_details.get("values"))
        return strip_generated_values(defaults)

    def _failed(self, result: dict[str, Any], error: MidcltError) -> dict[str, Any]:
        result["failed"] = True
        result["msg"] = str(error)
        result["rc"] = error.rc
        return result
