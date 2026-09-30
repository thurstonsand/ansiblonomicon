from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/fnox_host.py"
SPEC = spec_from_file_location("fnox_host", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
fnox_host = module_from_spec(SPEC)
sys.modules[SPEC.name] = fnox_host
with patch.object(sys, "path", [str(MODULE_PATH.parent), *sys.path]):
    SPEC.loader.exec_module(fnox_host)


@pytest.fixture
def configuration(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "fnox.toml").write_text("""\
root = true
env = "exec"
if_missing = "error"
prompt_auth = false
[daemon]
enabled = false
[providers.agent]
type = "1password"
token = { secret = "FNOX_HOST_OP_TOKEN" }
auth_command = ""
[secrets]
SHARED = { provider = "agent", value = "op://agent/shared/value" }
""")
    for profile in fnox_host.PROFILES:
        (root / f"fnox.{profile}.toml").write_text('import = ["fnox.toml"]\n')
    with (root / "fnox.pod042.toml").open("a") as target:
        target.write("""\
[providers.agent]
type = "1password"
token = { secret = "FNOX_HOST_OP_TOKEN" }
auth_command = ""
[secrets]
HOST_ONLY = { provider = "agent", value = "op://agent/host/value" }
""")
    with (root / "fnox.work.toml").open("a") as target:
        target.write("""\
[providers.work]
type = "1password"
account = "blocked-account"
auth_command = ""
[secrets]
WORK_ONLY = { provider = "work", value = "op://work/blocked/value" }
""")
    return root


@pytest.fixture
def environment(tmp_path: Path) -> dict[str, str]:
    identity = tmp_path / ".config/fnox/config.toml"
    identity.parent.mkdir(parents=True)
    identity.write_text(
        '[secrets.FNOX_HOST_OP_TOKEN]\ndefault = "sentinel-token"\nenv = false\n'
    )
    identity.chmod(0o600)
    return {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}


@pytest.mark.parametrize(
    ("hostname", "profile"),
    [
        ("Thurstons-MacBook-Pro", "macos"),
        ("Thurstons-MacBook-Pro.local", "macos"),
        ("ML-DFC6YK6VJQ", "work"),
        ("pod042", "pod042"),
    ],
)
def test_exact_host_selection(hostname: str, profile: str) -> None:
    assert fnox_host.select_profile(hostname, orb=False) == profile


@pytest.mark.parametrize(
    "hostname", ["omarchy", "ml-dfc6yk6vjq", "POD042", "runner-123"]
)
def test_unknown_hosts_do_not_default_to_macos(hostname: str) -> None:
    with pytest.raises(fnox_host.ConfigurationError, match="unregistered host"):
        fnox_host.select_profile(hostname, orb=False)


def test_orb_is_an_explicit_execution_context() -> None:
    assert fnox_host.select_profile("runner-123", orb=True) == "orb"


def test_desktop_authentication_clears_inherited_authority() -> None:
    result = fnox_host.authentication_environment(
        "macos",
        {
            "PATH": "/usr/bin",
            "SHARED": "stale",
            "OP_SERVICE_ACCOUNT_TOKEN": "stale-token",
            "FNOX_OP_SERVICE_ACCOUNT_TOKEN": "stale-token",
            "OP_CONNECT_HOST": "wrong-server",
            "OP_CONNECT_TOKEN": "wrong-token",
            "FNOX_NO_DEFAULTS": "true",
            "OP_SESSION_desktop": "desktop-session",
        },
        {"SHARED"},
        None,
    )
    assert result == {"PATH": "/usr/bin", "OP_SESSION_desktop": "desktop-session"}


@pytest.mark.parametrize("token", [None, "", " ", "one\ntwo", "one\rtwo"])
def test_orb_requires_one_supplied_token(token: str | None) -> None:
    with pytest.raises(fnox_host.ConfigurationError, match="service token"):
        fnox_host.authentication_environment("orb", {}, set(), token)


def test_token_file_is_private_and_not_a_symlink(tmp_path: Path) -> None:
    path = tmp_path / "token"
    path.write_text("sentinel-token\n")
    path.chmod(0o600)
    assert fnox_host.read_token(path, os.getuid()) == "sentinel-token"
    path.chmod(0o644)
    with pytest.raises(fnox_host.ConfigurationError, match="mode-0600"):
        fnox_host.read_token(path, os.getuid())
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        fnox_host.read_token(link, os.getuid())


@pytest.mark.parametrize(
    "extra",
    [
        'sync = { provider = "agent", value = "cached" }',
        'default = "fallback"',
        "as_file = true",
        'env = "shell"',
    ],
)
def test_disallowed_secret_modes_fail_before_resolution(
    configuration: Path, extra: str
) -> None:
    target = configuration / "fnox.macos.toml"
    target.write_text(
        'import = ["fnox.toml"]\n[secrets.BAD]\nprovider = "agent"\nvalue = "op://agent/bad/value"\n'
        + extra
    )
    with pytest.raises(fnox_host.ConfigurationError):
        fnox_host.declared_keys(configuration)


@pytest.mark.parametrize("executable", ["KEY=value", "./program=name"])
def test_env_assignments_cannot_dump_injected_secrets(executable: str) -> None:
    with pytest.raises(fnox_host.ConfigurationError, match="executable"):
        fnox_host.child_command([executable], {})


def test_child_executable_is_not_parsed_as_env_options() -> None:
    assert fnox_host.child_command(["-bad", "argument"], {}) == [
        "/usr/bin/env",
        "--",
        "-bad",
        "argument",
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ["exec", "--", "true"],
        ["exec", "--secret", "SHARED"],
        ["exec", "--secret", "SHARED", "true"],
        ["exec", "--secret", "--", "true"],
        ["exec", "--secret", "SHARED", "--unknown", "--", "true"],
    ],
)
def test_exec_requires_explicit_selection_and_separator(
    arguments: list[str],
    configuration: Path,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fnox_host, "ROOT", configuration)
    monkeypatch.setattr(
        fnox_host.socket, "gethostname", lambda: "Thurstons-MacBook-Pro"
    )
    monkeypatch.setattr(sys, "argv", ["fnox-host", *arguments])
    with (
        patch.dict(os.environ, environment, clear=True),
        pytest.raises(SystemExit) as error,
    ):
        fnox_host.main()
    assert error.value.code == 2


@pytest.mark.parametrize(
    "names",
    [[], ["SHARED", "WORK_ONLY"], ["FNOX_HOST_OP_TOKEN"], ["SHARED", "UNKNOWN"]],
)
def test_selection_is_validated_before_any_resolution(
    names: list[str],
    configuration: Path,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(*args: object, **kwargs: object) -> None:
        pytest.fail("invalid selection reached a subprocess")

    monkeypatch.setattr(fnox_host.subprocess, "run", unexpected_call)
    with pytest.raises(fnox_host.ConfigurationError, match="declared host secrets"):
        fnox_host.prepare_invocation(
            configuration,
            "macos",
            "exec",
            ["true"],
            environment,
            None,
            secrets=names,
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {fnox_host.EXEC_PROFILE: "macos"},
        {fnox_host.EXEC_KEYS: '["SHARED"]'},
        {fnox_host.EXEC_PROFILE: "work", fnox_host.EXEC_KEYS: '["SHARED"]'},
        *[
            {fnox_host.EXEC_PROFILE: "macos", fnox_host.EXEC_KEYS: value}
            for value in [
                "",
                "not-json",
                "null",
                "{}",
                "[]",
                "[1]",
                '["SHARED", "SHARED"]',
                '["WORK_ONLY"]',
                '["FNOX_HOST_OP_TOKEN"]',
            ]
        ],
    ],
)
def test_inherited_scope_rejects_malformed_or_mismatched_metadata(
    metadata: dict[str, str],
    configuration: Path,
    environment: dict[str, str],
) -> None:
    environment.update(metadata)
    environment["SHARED"] = "cached-shared"
    with pytest.raises(fnox_host.ConfigurationError):
        fnox_host.inherited_values(configuration, "macos", environment)


@pytest.mark.parametrize("values", [{}, {"SHARED": ""}])
def test_inherited_scope_requires_marked_nonempty_values(
    values: dict[str, str],
    configuration: Path,
    environment: dict[str, str],
) -> None:
    environment.update(
        {fnox_host.EXEC_PROFILE: "macos", fnox_host.EXEC_KEYS: '["SHARED"]', **values}
    )
    with pytest.raises(fnox_host.ConfigurationError, match="incomplete"):
        fnox_host.inherited_values(configuration, "macos", environment)


@pytest.mark.parametrize("operation", ["get", "exec"])
def test_cached_main_needs_neither_token_file_nor_fnox(
    operation: str,
    configuration: Path,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    (Path(environment["HOME"]) / ".config/fnox/config.toml").unlink()
    environment.update(
        {
            fnox_host.EXEC_PROFILE: "pod042",
            fnox_host.EXEC_KEYS: '["SHARED"]',
            "SHARED": "cached-shared",
        }
    )
    monkeypatch.setattr(fnox_host, "ROOT", configuration)
    monkeypatch.setattr(fnox_host.socket, "gethostname", lambda: "pod042")
    arguments = (
        ["get", "SHARED"]
        if operation == "get"
        else ["exec", "--secret", "SHARED", "--", "true"]
    )
    monkeypatch.setattr(sys, "argv", ["fnox-host", *arguments])
    launched: list[tuple[str, list[str], dict[str, str]]] = []

    def launch(binary: str, argv: list[str], environment: dict[str, str]) -> None:
        launched.append((binary, argv, environment))

    monkeypatch.setattr(fnox_host.os, "execvpe", launch)
    with patch.dict(os.environ, environment, clear=True):
        fnox_host.main()
    if operation == "get":
        assert capfd.readouterr().out == "cached-shared\n"
    else:
        assert len(launched) == 1
        assert launched[0][2]["SHARED"] == "cached-shared"


@pytest.mark.parametrize("operation", ["get", "exec"])
def test_main_sanitizes_failed_provider_output(
    operation: str,
    configuration: Path,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(fnox_host, "ROOT", configuration)
    monkeypatch.setattr(fnox_host.socket, "gethostname", lambda: "pod042")
    arguments = {
        "get": ["get", "SHARED"],
        "exec": ["exec", "--secret", "SHARED", "--secret", "HOST_ONLY", "--", "true"],
    }[operation]
    monkeypatch.setattr(sys, "argv", ["fnox-host", *arguments])

    def failed_resolution(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "leaked-value", "leaked-token")

    monkeypatch.setattr(fnox_host.subprocess, "run", failed_resolution)
    with (
        patch.dict(os.environ, environment, clear=True),
        pytest.raises(SystemExit) as error,
    ):
        fnox_host.entrypoint()
    assert error.value.code == 1
    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == "fnox-host: secret resolution failed for SHARED\n"


@pytest.mark.parametrize("inherited", [False, True])
def test_get_only_secret_cannot_enter_exec_scope(
    inherited: bool,
    configuration: Path,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (configuration / "fnox.macos.toml").open("a") as target:
        target.write(
            '\n[secrets]\nPOD042_SERVICE_ACCOUNT_TOKEN = { provider = "agent", value = "op://agent/host/value", env = false }\n'
        )
    if inherited:
        environment.update(
            {
                fnox_host.EXEC_PROFILE: "macos",
                fnox_host.EXEC_KEYS: '["SHARED", "POD042_SERVICE_ACCOUNT_TOKEN"]',
                "SHARED": "cached-shared",
                "POD042_SERVICE_ACCOUNT_TOKEN": "provider-token",
            }
        )

    def unexpected_call(*args: object, **kwargs: object) -> None:
        pytest.fail("get-only selection reached a subprocess")

    monkeypatch.setattr(fnox_host.subprocess, "run", unexpected_call)
    with pytest.raises(
        fnox_host.ConfigurationError, match="POD042_SERVICE_ACCOUNT_TOKEN is get-only"
    ):
        fnox_host.prepare_invocation(
            configuration,
            "macos",
            "exec",
            ["true"],
            environment,
            None,
            secrets=["SHARED", "POD042_SERVICE_ACCOUNT_TOKEN"],
        )
    if inherited:
        with pytest.raises(fnox_host.ConfigurationError, match="get-only"):
            fnox_host.resolve_values(
                configuration, "macos", ["SHARED"], environment, None
            )
