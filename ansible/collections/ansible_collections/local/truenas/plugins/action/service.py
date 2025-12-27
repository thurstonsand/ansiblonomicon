"""Action plugin for service - runs on controller, not TrueNAS."""

from typing import Any

from ansible.plugins.action import ActionBase
from ansible_collections.local.truenas.plugins.plugin_utils.midclt import (
    MidcltClient,
    MidcltError,
    ResourceRecord,
    format_diff,
)


class ActionModule(ActionBase):
    """Manage TrueNAS service state via midclt.

    This action plugin runs entirely on the Ansible controller.
    Only raw midclt commands are executed on TrueNAS.
    """

    def run(
        self, tmp: str | None = None, task_vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = super().run(tmp, task_vars)
        result["changed"] = False

        params = self._task.args
        service_name: str = params.get("name", "")
        desired_enabled: bool | None = params.get("enabled")
        desired_state: str | None = params.get("state")

        if not service_name:
            result["failed"] = True
            result["msg"] = "'name' is required"
            return result

        client = MidcltClient(self._low_level_execute_command)

        try:
            service = client.service_query(service_name)
        except MidcltError as e:
            result["failed"] = True
            result["msg"] = str(e)
            result["rc"] = e.rc
            return result

        if service is None:
            result["failed"] = True
            result["msg"] = f"Service '{service_name}' not found"
            return result

        result["id"] = service["id"]

        current_enabled: bool = service["enable"]
        current_running: bool = service["state"] == "RUNNING"

        before_state: ResourceRecord = {
            "enable": current_enabled,
            "state": service["state"],
        }
        after_state = before_state.copy()

        try:
            # Handle enabled setting
            if desired_enabled is not None and desired_enabled != current_enabled:
                result["changed"] = True
                after_state["enable"] = desired_enabled

                if not self._play_context.check_mode:
                    client.service_update(service_name, {"enable": desired_enabled})

            # Handle state (start/stop/restart)
            if desired_state == "started" and not current_running:
                result["changed"] = True
                after_state["state"] = "RUNNING"

                if not self._play_context.check_mode:
                    client.service_start(service_name)

            elif desired_state == "stopped" and current_running:
                result["changed"] = True
                after_state["state"] = "STOPPED"

                if not self._play_context.check_mode:
                    client.service_stop(service_name)

            elif desired_state == "restarted":
                result["changed"] = True
                after_state["state"] = "RUNNING"

                if not self._play_context.check_mode:
                    client.service_restart(service_name)

        except MidcltError as e:
            result["failed"] = True
            result["msg"] = str(e)
            result["rc"] = e.rc
            return result

        # Get final state for result
        if not self._play_context.check_mode and result["changed"]:
            try:
                service = client.service_query(service_name)
                if service:
                    result["running"] = service["state"] == "RUNNING"
                else:
                    result["running"] = False
            except MidcltError:
                result["running"] = False
        else:
            result["running"] = after_state["state"] == "RUNNING"

        if result["changed"]:
            result["diff"] = format_diff(before_state, after_state)

        return result
