from ansible.executor.task_result import TaskResult
from ansible.inventory.host import Host
from ansible.playbook.included_file import IncludedFile
from ansible.playbook.task import Task
from ansible.plugins.callback.default import CallbackModule as DefaultCallback

DOCUMENTATION = """
name: changes_only
type: stdout
short_description: Only display debug, changed, and failed tasks
description:
  - Suppresses ok, skipped, and included task output
  - Only shows tasks that result in changes, failures, or debug output
author: Thurston Sandberg
extends_documentation_fragment:
  - default_callback
  - result_format_callback
"""


class CallbackModule(DefaultCallback):  # type: ignore[misc]
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "changes_only"

    def v2_runner_on_ok(self, result: TaskResult) -> None:
        is_changed = result._result.get("changed", False)
        action = result.task.action
        is_debug = action in ("debug", "ansible.builtin.debug")
        if is_changed or is_debug:
            if is_debug and not is_changed:
                self._display.display(
                    f"ok: [{result.host.name}] => {result._result.get('msg', '')}"
                )
            else:
                super().v2_runner_on_ok(result)

    def v2_runner_on_skipped(self, result: TaskResult) -> None:
        pass

    def v2_runner_item_on_ok(self, result: TaskResult) -> None:
        if result._result.get("changed", False):
            super().v2_runner_item_on_ok(result)

    def v2_runner_item_on_skipped(self, result: TaskResult) -> None:
        pass

    def v2_playbook_on_include(self, included_file: IncludedFile) -> None:
        pass

    def v2_runner_on_start(self, host: Host, task: Task) -> None:
        pass
