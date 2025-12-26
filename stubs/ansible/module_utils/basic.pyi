"""Type stubs for ansible.module_utils.basic.

Auto-generated via stubgen, then cleaned up for strict type checking.
"""

from collections.abc import Callable, Mapping, Sequence
from re import Pattern
from typing import Any, NoReturn

# Re-exports from ansible internals (commonly used)
def jsonify(data: Any) -> str: ...
def to_bytes(obj: str | bytes, encoding: str = "utf-8", errors: str = "surrogate_or_strict") -> bytes: ...
def to_native(obj: str | bytes, encoding: str = "utf-8", errors: str = "surrogate_or_strict") -> str: ...
def to_text(obj: str | bytes, encoding: str = "utf-8", errors: str = "surrogate_or_strict") -> str: ...

HAS_SYSLOG: bool
has_journal: bool
HAVE_SELINUX: bool
AVAILABLE_HASH_ALGORITHMS: dict[str, type]
SEQUENCETYPE: tuple[type, ...]
PASSWORD_MATCH: Pattern[str]
FILE_COMMON_ARGUMENTS: dict[str, dict[str, Any]]
PASSWD_ARG_RE: Pattern[str]

def get_platform() -> str: ...
def load_platform_subclass(cls: type, *args: Any, **kwargs: Any) -> Any: ...
def get_all_subclasses(cls: type) -> list[type]: ...
def heuristic_log_sanitize(data: str, no_log_values: set[str] | None = None) -> str: ...
def missing_required_lib(library: str, reason: str | None = None, url: str | None = None) -> str: ...
def env_fallback(*args: str, **kwargs: Any) -> str: ...
def get_bin_path(arg: str, required: bool = False, opt_dirs: Sequence[str] | None = None) -> str | None: ...

class AnsibleModule:
    argument_spec: dict[str, dict[str, Any]]
    supports_check_mode: bool
    check_mode: bool
    bypass_checks: bool
    no_log: bool
    diff: bool
    mutually_exclusive: Sequence[Sequence[str]] | None
    required_together: Sequence[Sequence[str]] | None
    required_one_of: Sequence[Sequence[str]] | None
    required_if: Sequence[tuple[str, Any, Sequence[str], bool]] | None
    required_by: Mapping[str, Sequence[str]] | None
    cleanup_files: list[str]
    run_command_environ_update: dict[str, str]
    aliases: dict[str, str]
    no_log_values: set[str]
    params: dict[str, Any]
    _verbosity: int

    def __init__(
        self,
        argument_spec: dict[str, dict[str, Any]],
        bypass_checks: bool = False,
        no_log: bool = False,
        mutually_exclusive: Sequence[Sequence[str]] | None = None,
        required_together: Sequence[Sequence[str]] | None = None,
        required_one_of: Sequence[Sequence[str]] | None = None,
        add_file_common_args: bool = False,
        supports_check_mode: bool = False,
        required_if: Sequence[tuple[str, Any, Sequence[str], bool]] | None = None,
        required_by: Mapping[str, Sequence[str]] | None = None,
    ) -> None: ...
    @property
    def tmpdir(self) -> str: ...
    def warn(self, warning: str, *, help_text: str | None = None) -> None: ...
    def deprecate(
        self,
        msg: str,
        version: str | None = None,
        date: str | None = None,
        collection_name: str | None = None,
        *,
        help_text: str | None = None,
    ) -> None: ...
    def load_file_common_arguments(
        self, params: dict[str, Any], path: str | None = None
    ) -> dict[str, Any]: ...
    def selinux_mls_enabled(self) -> bool: ...
    def selinux_enabled(self) -> bool: ...
    def selinux_initial_context(self) -> list[str | None]: ...
    def selinux_default_context(self, path: str, mode: int = 0) -> list[str | None]: ...
    def selinux_context(self, path: str) -> list[str | None]: ...
    def user_and_group(self, path: str, expand: bool = True) -> tuple[int, int]: ...
    def find_mount_point(self, path: str) -> str: ...
    def is_special_selinux_path(self, path: str) -> tuple[bool, list[str] | None]: ...
    def set_default_selinux_context(self, path: str, changed: bool) -> bool: ...
    def set_context_if_different(
        self,
        path: str,
        context: list[str | None],
        changed: bool,
        diff: dict[str, Any] | None = None,
    ) -> bool: ...
    def set_owner_if_different(
        self,
        path: str,
        owner: str | int | None,
        changed: bool,
        diff: dict[str, Any] | None = None,
        expand: bool = True,
    ) -> bool: ...
    def set_group_if_different(
        self,
        path: str,
        group: str | int | None,
        changed: bool,
        diff: dict[str, Any] | None = None,
        expand: bool = True,
    ) -> bool: ...
    def set_mode_if_different(
        self,
        path: str,
        mode: str | int | None,
        changed: bool,
        diff: dict[str, Any] | None = None,
        expand: bool = True,
    ) -> bool: ...
    def set_attributes_if_different(
        self,
        path: str,
        attributes: str | None,
        changed: bool,
        diff: dict[str, Any] | None = None,
        expand: bool = True,
    ) -> bool: ...
    def get_file_attributes(
        self, path: str, include_version: bool = True
    ) -> dict[str, Any]: ...
    def set_fs_attributes_if_different(
        self,
        file_args: dict[str, Any],
        changed: bool,
        diff: dict[str, Any] | None = None,
        expand: bool = True,
    ) -> bool: ...
    def check_file_absent_if_check_mode(self, file_path: str) -> bool: ...
    def add_path_info(self, kwargs: dict[str, Any]) -> dict[str, Any]: ...
    def safe_eval(
        self,
        value: str,
        locals: dict[str, Any] | None = None,
        include_exceptions: bool = False,
    ) -> Any: ...
    def debug(self, msg: str) -> None: ...
    def log(self, msg: str, log_args: dict[str, Any] | None = None) -> None: ...
    def get_bin_path(
        self, arg: str, required: bool = False, opt_dirs: Sequence[str] | None = None
    ) -> str | None: ...
    def boolean(self, arg: Any) -> bool: ...
    def jsonify(self, data: Any) -> str: ...
    def from_json(self, data: str) -> Any: ...
    def add_cleanup_file(self, path: str) -> None: ...
    def do_cleanup_files(self) -> None: ...
    def exit_json(self, **kwargs: Any) -> NoReturn: ...
    def fail_json(
        self, msg: str, *, exception: BaseException | str | None = None, **kwargs: Any
    ) -> NoReturn: ...
    def fail_on_missing_params(self, required_params: Sequence[str] | None = None) -> None: ...
    def digest_from_file(self, filename: str, algorithm: str) -> str | None: ...
    def md5(self, filename: str) -> str | None: ...
    def sha1(self, filename: str) -> str | None: ...
    def sha256(self, filename: str) -> str | None: ...
    def backup_local(self, fn: str) -> str: ...
    def cleanup(self, tmpfile: str) -> None: ...
    def preserved_copy(self, src: str, dest: str) -> None: ...
    def atomic_move(
        self,
        src: str,
        dest: str,
        unsafe_writes: bool = False,
        keep_dest_attrs: bool = True,
    ) -> None: ...
    def run_command(
        self,
        args: str | Sequence[str],
        check_rc: bool = False,
        close_fds: bool = True,
        executable: str | None = None,
        data: str | bytes | None = None,
        binary_data: bool = False,
        path_prefix: str | None = None,
        cwd: str | None = None,
        use_unsafe_shell: bool = False,
        prompt_regex: str | None = None,
        environ_update: dict[str, str] | None = None,
        umask: int | str | None = None,
        encoding: str = "utf-8",
        errors: str = "surrogate_or_strict",
        expand_user_and_vars: bool = True,
        pass_fds: Sequence[int] | None = None,
        before_communicate_callback: Callable[..., None] | None = None,
        ignore_invalid_cwd: bool = True,
        handle_exceptions: bool = True,
    ) -> tuple[int, str, str]: ...
    def append_to_file(self, filename: str, str: str) -> None: ...
    @staticmethod
    def bytes_to_human(size: int) -> str: ...
    pretty_bytes = bytes_to_human
    @staticmethod
    def human_to_bytes(number: str, isbits: bool = False) -> int: ...
    @staticmethod
    def get_buffer_size(fd: int) -> int: ...

def get_module_path() -> str: ...
