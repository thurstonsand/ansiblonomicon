"""Shared midclt helpers for action plugins.

Runs on the Ansible controller with full Python 3.12+ features.
Executes midclt commands remotely and parses JSON locally.
"""

from dataclasses import dataclass
import json
from typing import Any

type ResourceRecord = dict[str, Any]


@dataclass(slots=True)
class CreateResult:
    """Result from a midclt create operation."""

    id: int
    record: ResourceRecord | None = None


def format_diff(before: ResourceRecord, after: ResourceRecord) -> dict[str, str]:
    """Format diff output for Ansible."""
    return {
        "before": json.dumps(before, indent=2, sort_keys=True),
        "after": json.dumps(after, indent=2, sort_keys=True),
    }


class MidcltError(Exception):
    """Raised when a midclt command fails."""

    def __init__(self, method: str, stderr: str, rc: int) -> None:
        super().__init__(f"midclt {method} failed: {stderr}")
        self.method = method
        self.stderr = stderr
        self.rc = rc


class MidcltClient:
    """Execute midclt commands remotely via an Ansible action plugin.

    All JSON parsing happens locally on the controller.
    """

    def __init__(self, execute_command: Any) -> None:
        """Initialize with the action plugin's command executor.

        Args:
            execute_command: A callable that takes a command string and returns
                           (rc, stdout, stderr). Typically action._low_level_execute_command.
        """
        self._execute = execute_command

    def service_query(self, service_name: str) -> ResourceRecord | None:
        """Query a service by name."""
        return self.query_one("service", [["service", "=", service_name]])

    def service_update(self, service_name: str, settings: ResourceRecord) -> None:
        """Update service settings (uses service name, not ID)."""
        self._call("service.update", service_name, settings)

    def service_start(self, service_name: str) -> bool:
        """Start a service. Returns True on success."""
        result = self._call("service.start", service_name)
        return bool(result)

    def service_stop(self, service_name: str) -> bool:
        """Stop a service. Returns True on success."""
        result = self._call("service.stop", service_name)
        return bool(result)

    def service_restart(self, service_name: str) -> bool:
        """Restart a service. Returns True on success."""
        result = self._call("service.restart", service_name)
        return bool(result)

    def _call(self, method: str, *args: ResourceRecord | list[Any] | int | str) -> Any:
        """Execute a midclt call and return parsed JSON output."""
        cmd_parts = ["midclt", "call", method]
        for arg in args:
            if isinstance(arg, str):
                cmd_parts.append(self._shell_quote(arg))
            else:
                cmd_parts.append(self._shell_quote(json.dumps(arg)))

        cmd = " ".join(cmd_parts)
        result = self._execute(cmd)

        rc = result.get("rc", 1)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")

        if rc != 0:
            raise MidcltError(method, stderr, rc)

        output = stdout.strip()
        if output:
            # midclt sometimes returns Python literals (True/False/None) instead of JSON
            if output in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[output]
            try:
                return json.loads(output)
            except json.JSONDecodeError as e:
                raise MidcltError(
                    method, f"Invalid JSON: {e}\nOutput: {output}", rc
                ) from e
        return None

    @staticmethod
    def _shell_quote(s: str) -> str:
        """Quote a string for shell execution."""
        return "'" + s.replace("'", "'\"'\"'") + "'"

    def query(
        self, resource: str, filters: list[list[Any]] | None = None
    ) -> list[ResourceRecord]:
        """Query resources with optional filters. Always returns a list."""
        if filters:
            result = self._call(f"{resource}.query", filters)
        else:
            result = self._call(f"{resource}.query")
        return result if result else []

    def query_one(
        self, resource: str, filters: list[list[Any]]
    ) -> ResourceRecord | None:
        """Query for a single resource. Returns None if not found."""
        results = self.query(resource, filters)
        return results[0] if results else None

    def create(self, resource: str, payload: ResourceRecord) -> CreateResult:
        """Create a resource. Returns ID and optionally the full record."""
        result: ResourceRecord | int = self._call(f"{resource}.create", payload)
        if isinstance(result, dict):
            return CreateResult(id=int(result["id"]), record=result)
        return CreateResult(id=int(result))

    def update(self, resource: str, resource_id: int, changes: ResourceRecord) -> None:
        """Update a resource by ID."""
        self._call(f"{resource}.update", resource_id, changes)

    def delete(self, resource: str, resource_id: int) -> None:
        """Delete a resource by ID."""
        self._call(f"{resource}.delete", resource_id)

    def get_pool_id(self, pool_name: str) -> int | None:
        """Look up pool ID by name. Returns None if not found."""
        results = self.query("pool", [["name", "=", pool_name]])
        return results[0]["id"] if results else None
