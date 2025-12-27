from typing import Any

from ansible.playbook.play_context import PlayContext
from ansible.playbook.task import Task

class ActionBase:
    _task: Task
    _play_context: PlayContext

    def run(
        self, tmp: str | None = None, task_vars: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    def _low_level_execute_command(
        self,
        cmd: str,
        sudoable: bool = True,
        in_data: bytes | None = None,
        executable: str | None = None,
        encoding_errors: str = "surrogate_then_replace",
        chdir: str | None = None,
    ) -> dict[str, Any]: ...
