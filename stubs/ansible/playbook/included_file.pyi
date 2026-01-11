from _typeshed import Incomplete
from ansible._internal._templating._engine import TemplateEngine as TemplateEngine
from ansible.errors import AnsibleError as AnsibleError
from ansible.executor.task_result import _RawTaskResult
from ansible.inventory.host import Host as Host
from ansible.module_utils.common.text.converters import to_text as to_text
from ansible.parsing.dataloader import DataLoader as DataLoader
from ansible.playbook.handler import Handler as Handler
from ansible.playbook.role_include import IncludeRole as IncludeRole
from ansible.playbook.task_include import TaskInclude as TaskInclude
from ansible.utils.display import Display as Display
from ansible.vars.manager import VariableManager as VariableManager

display: Incomplete

class IncludedFile:
    def __init__(self, filename, args, vars, task, is_role: bool = False) -> None: ...
    def add_host(self, host: Host) -> None: ...
    def __eq__(self, other): ...
    @staticmethod
    def process_include_results(results: list[_RawTaskResult], iterator, loader: DataLoader, variable_manager: VariableManager) -> list[IncludedFile]: ...
