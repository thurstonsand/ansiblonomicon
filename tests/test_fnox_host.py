from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tomllib
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


def run_fnox(
    root: Path,
    profile: str,
    operation: str,
    arguments: list[str],
    inherited: dict[str, str],
    token: str | None,
    *,
    fnox: str,
    secrets: list[str] | None = None,
) -> int:
    try:
        invocation = fnox_host.prepare_invocation(
            root,
            profile,
            operation,
            arguments,
            inherited,
            token,
            fnox=fnox,
            secrets=secrets,
        )
    except fnox_host.ConfigurationError:
        return 1
    return subprocess.run(
        invocation.argv, env=invocation.environment, check=False
    ).returncode


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
def fnox_binary() -> str:
    return (
        os.environ.get("FNOX_TEST_BINARY")
        or subprocess.check_output(["mise", "which", "fnox"], text=True).strip()
    )


@pytest.fixture
def environment(tmp_path: Path) -> dict[str, str]:
    binary = tmp_path / "bin"
    binary.mkdir()
    op = binary / "op"
    op.write_text(f"""#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["OP_CALLS"], "a") as log:
    log.write(json.dumps({{"args": args, "token": os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")}}) + "\\n")
if "blocked-account" in args or os.environ.get("FAIL_OP") or os.environ.get("FAIL_REF") in args:
    print("provider unavailable", file=sys.stderr)
    sys.exit(1)
values = {{"op://agent/shared/value": "sentinel-shared", "op://agent/host/value": "sentinel-host"}}
values.update(json.loads(os.environ.get("FAKE_VALUES", "{{}}")))
verb = next((argument for argument in args if argument in ("read", "inject")), None)
if verb == "read":
    print(values[args[args.index("read") + 1]])
elif verb == "inject":
    template = sys.stdin.read()
    for key, value in values.items():
        template = template.replace(key, value)
    sys.stdout.write(template)
else:
    sys.exit(2)
""")
    op.chmod(0o755)
    identity = tmp_path / ".config/fnox/config.toml"
    identity.parent.mkdir(parents=True)
    identity.write_text(
        '[secrets.FNOX_HOST_OP_TOKEN]\ndefault = "sentinel-token"\nenv = false\n'
    )
    identity.chmod(0o600)
    return {
        "PATH": f"{binary}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "OP_CALLS": str(tmp_path / "op-calls.jsonl"),
    }


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


def test_real_fnox_merges_host_and_root_without_leaking_tokens(
    configuration: Path, environment: dict[str, str], fnox_binary: str, tmp_path: Path
) -> None:
    output = tmp_path / "child.json"
    environment.update(
        {
            "FNOX_PROFILE": "work",
            "FNOX_DAEMON": "on",
            "FNOX_NO_DEFAULTS": "true",
            "SHARED": "stale-value",
            "WORK_ONLY": "stale-work-value",
            "OP_SERVICE_ACCOUNT_TOKEN": "stale-token",
        }
    )
    assert (
        run_fnox(
            configuration,
            "pod042",
            "exec",
            [
                sys.executable,
                "-c",
                "import json,os,sys; open(sys.argv[1], 'w').write(json.dumps(dict(os.environ)))",
                str(output),
            ],
            environment,
            "sentinel-token",
            fnox=fnox_binary,
            secrets=["SHARED", "HOST_ONLY"],
        )
        == 0
    )
    child = json.loads(output.read_text())
    assert child["SHARED"] == "sentinel-shared"
    assert child["HOST_ONLY"] == "sentinel-host"
    assert "WORK_ONLY" not in child
    assert not any(key.startswith(("OP_", "FNOX_")) for key in child)
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2
    assert all(call["args"][0] == "read" for call in calls)
    assert all("desktop-account" not in call["args"] for call in calls)
    assert all(call["token"] == "sentinel-token" for call in calls)


def test_exec_overwrites_inherited_python_metadata(
    configuration: Path, environment: dict[str, str], fnox_binary: str, tmp_path: Path
) -> None:
    output = tmp_path / "python"
    environment[fnox_host.EXEC_PYTHON] = "/bogus/inherited/python"
    assert (
        run_fnox(
            configuration,
            "macos",
            "exec",
            [
                sys.executable,
                "-c",
                "import os,sys; open(sys.argv[1], 'w').write(os.environ['HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON'])",
                str(output),
            ],
            environment,
            None,
            fnox=fnox_binary,
            secrets=["SHARED"],
        )
        == 0
    )
    assert output.read_text() == sys.executable


def test_strict_provider_failure_does_not_run_child(
    configuration: Path, environment: dict[str, str], fnox_binary: str, tmp_path: Path
) -> None:
    output = tmp_path / "child-ran"
    environment.update({"FAIL_OP": "1", "SHARED": "stale-value"})
    assert (
        run_fnox(
            configuration,
            "macos",
            "exec",
            ["/usr/bin/touch", str(output)],
            environment,
            None,
            fnox=fnox_binary,
            secrets=["SHARED"],
        )
        != 0
    )
    assert not output.exists()


def test_get_does_not_resolve_unrelated_work_provider(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    capfd: pytest.CaptureFixture[str],
) -> None:
    assert (
        run_fnox(
            configuration,
            "work",
            "get",
            ["SHARED"],
            environment,
            None,
            fnox=fnox_binary,
        )
        == 0
    )
    assert capfd.readouterr().out == "sentinel-shared\n"
    calls = Path(environment["OP_CALLS"]).read_text()
    assert "blocked-account" not in calls


def test_global_and_local_overrides_cannot_replace_remote_values(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    override = '[secrets]\nSHARED = { default = "stale-cache" }\n'
    global_config = tmp_path / "untrusted-fnox-config"
    global_config.mkdir()
    (global_config / "config.toml").write_text(override)
    (configuration / "fnox.local.toml").write_text(override)
    (configuration / ".fnox.macos.toml").write_text(override)
    environment["FNOX_CONFIG_DIR"] = str(global_config)
    assert (
        run_fnox(
            configuration,
            "macos",
            "get",
            ["SHARED"],
            environment,
            None,
            fnox=fnox_binary,
        )
        == 0
    )
    assert capfd.readouterr().out == "sentinel-shared\n"


@pytest.mark.parametrize("sibling", ["config.macos.toml", "config.local.toml"])
def test_real_global_identity_siblings_cannot_poison_get_or_exec(
    sibling: str,
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    capfd: pytest.CaptureFixture[str],
) -> None:
    global_config = Path(environment["HOME"]) / ".config/fnox"
    (global_config / sibling).write_text(
        '[secrets]\nSHARED = { default = "poison-shared" }\n'
        'GLOBAL_POISON = { default = "poison-extra", env = true }\n'
    )
    assert (
        run_fnox(
            configuration,
            "macos",
            "get",
            ["SHARED"],
            environment,
            None,
            fnox=fnox_binary,
        )
        == 0
    )
    assert capfd.readouterr().out == "sentinel-shared\n"
    assert (
        run_fnox(
            configuration,
            "macos",
            "exec",
            [
                sys.executable,
                "-c",
                'import os; assert os.environ["SHARED"] == "sentinel-shared"; assert "GLOBAL_POISON" not in os.environ',
            ],
            environment,
            None,
            fnox=fnox_binary,
            secrets=["SHARED"],
        )
        == 0
    )
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2
    assert all(call["token"] == "sentinel-token" for call in calls)


def test_child_exit_status_propagates(
    configuration: Path, environment: dict[str, str], fnox_binary: str
) -> None:
    assert (
        run_fnox(
            configuration,
            "macos",
            "exec",
            ["/bin/sh", "-c", "exit 42"],
            environment,
            None,
            fnox=fnox_binary,
            secrets=["SHARED"],
        )
        == 42
    )


def test_get_can_read_a_noninjected_bootstrap_secret(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    capfd: pytest.CaptureFixture[str],
) -> None:
    with (configuration / "fnox.macos.toml").open("a") as target:
        target.write(
            '\n[secrets]\nBOOTSTRAP = { provider = "agent", value = "op://agent/host/value", env = false }\n'
        )
    assert (
        run_fnox(
            configuration,
            "macos",
            "get",
            ["BOOTSTRAP"],
            environment,
            None,
            fnox=fnox_binary,
        )
        == 0
    )
    assert capfd.readouterr().out == "sentinel-host\n"


def test_checked_in_declarations_match_launcher_policy() -> None:
    keys = fnox_host.declared_keys(MODULE_PATH.parents[1])
    assert {
        "POD042_SERVICE_ACCOUNT_TOKEN",
        "ANTHROPIC_AUTH_TOKEN",
    } <= keys
    assert "FNOX_HOST_OP_TOKEN" not in keys


@pytest.mark.parametrize("profile", ["macos", "omarchy", "work", "pod042", "orb"])
def test_checked_in_host_sets_with_real_fnox(
    profile: str,
    environment: dict[str, str],
    fnox_binary: str,
    tmp_path: Path,
) -> None:
    root = MODULE_PATH.parents[1]
    shared = tomllib.loads((root / "fnox.toml").read_text())["secrets"]
    host = tomllib.loads((root / f"fnox.{profile}.toml").read_text())["secrets"]
    effective = {**shared, **host}
    environment["FAKE_VALUES"] = json.dumps(
        {
            entry["value"]: "sentinel-" + key
            for key, entry in effective.items()
            if "value" in entry
        }
    )
    environment["FNOX_WORK_ACCOUNT"] = "verified-work-account"
    output = tmp_path / "environment.json"
    token = "sentinel-token" if profile in {"pod042", "orb"} else None
    exported_keys = [
        key for key, entry in effective.items() if entry.get("env") is not False
    ]
    assert (
        run_fnox(
            root,
            profile,
            "exec",
            [
                sys.executable,
                "-c",
                "import json,os,sys; open(sys.argv[1], 'w').write(json.dumps(dict(os.environ)))",
                str(output),
            ],
            environment,
            token,
            fnox=fnox_binary,
            secrets=exported_keys,
        )
        == 0
    )
    child = json.loads(output.read_text())
    for key, entry in effective.items():
        if entry.get("env") is False:
            assert key not in child
        else:
            assert child[key] == "sentinel-" + key
    assert not any(key.startswith(("OP_", "FNOX_")) for key in child)
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == len(exported_keys)
    assert all("read" in call["args"] for call in calls)
    if token:
        assert all(
            call["token"] == token and "--account" not in call["args"] for call in calls
        )
    else:
        agent_calls = [call for call in calls if call["token"] is not None]
        desktop_calls = [call for call in calls if call["token"] is None]
        assert agent_calls
        assert all(call["token"] == "sentinel-token" for call in agent_calls)
        assert "--account" not in agent_calls[0]["args"]
        accounts = {
            call["args"][call["args"].index("--account") + 1] for call in desktop_calls
        }
        expected_accounts: set[str] = (
            {"PQ7X5W7V6FDADHPFFEO62TLFEM", "verified-work-account"}
            if profile == "work"
            else set()
        )
        assert accounts == expected_accounts


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


@pytest.mark.parametrize("termination", [signal.SIGINT, signal.SIGTERM])
def test_launcher_preserves_graceful_child_shutdown(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    termination: signal.Signals,
) -> None:
    scripts = configuration / "scripts"
    scripts.mkdir()
    shutil.copy2(MODULE_PATH, scripts / "fnox_host.py")
    shutil.copy2(MODULE_PATH.with_name("fnox-host"), scripts / "fnox-host")
    shutil.copy2(
        MODULE_PATH.with_name("automation_identity.py"),
        scripts / "automation_identity.py",
    )
    binary_dir = Path(environment["PATH"].split(":")[0])
    (binary_dir / "fnox").symlink_to(fnox_binary)
    environment["OP_SERVICE_ACCOUNT_TOKEN"] = "sentinel-token"
    child = """import os, signal, sys, time

def stop(signum, frame):
    time.sleep(0.4)
    # The signal can land inside print("ready"); print here would be a reentrant call.
    os.write(1, b"finished\\n")
    sys.exit(7)

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
print("ready", flush=True)
signal.pause()
"""
    with subprocess.Popen(
        [
            sys.executable,
            str(scripts / "fnox-host"),
            "--orb",
            "exec",
            "--secret",
            "SHARED",
            "--",
            sys.executable,
            "-c",
            child,
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        assert process.stdout is not None
        try:
            assert process.stdout.readline() == "ready\n"
            process.send_signal(termination)
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 7
            assert stdout == "finished\n"
            assert stderr == ""
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)


@pytest.mark.parametrize("profile", ["pod042", "orb"])
def test_legacy_injected_identity_needs_no_global_file_or_secret_declaration(
    profile: str,
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
) -> None:
    (Path(environment["HOME"]) / ".config/fnox/config.toml").unlink()
    assert "FNOX_HOST_OP_TOKEN" not in fnox_host.declared_keys(configuration)
    assert (
        run_fnox(
            configuration,
            profile,
            "get",
            ["SHARED"],
            environment,
            "sentinel-token",
            fnox=fnox_binary,
        )
        == 0
    )
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 1
    assert calls[0]["token"] == "sentinel-token"


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
    assert not Path(environment["OP_CALLS"]).exists()


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
    assert not Path(environment["OP_CALLS"]).exists()


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


def test_selected_agent_secret_never_touches_poisoned_private_provider(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
) -> None:
    (configuration / "fnox.macos.toml").write_text("""import = ["fnox.toml"]
[providers.personal]
type = "1password"
account = "blocked-account"
auth_command = ""
[secrets]
PRIVATE = { provider = "personal", value = "op://Private/password/value" }
""")
    assert (
        run_fnox(
            configuration,
            "macos",
            "exec",
            [
                sys.executable,
                "-c",
                'import os; assert os.environ["SHARED"] == "sentinel-shared"; assert "PRIVATE" not in os.environ',
            ],
            environment,
            None,
            fnox=fnox_binary,
            secrets=["SHARED"],
        )
        == 0
    )
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 1
    assert "blocked-account" not in calls[0]["args"]
    assert calls[0]["args"][-1] == "op://agent/shared/value"


def test_nested_exec_reuses_selected_values_and_drops_unselected_values(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
) -> None:
    environment.update(
        {
            fnox_host.EXEC_PROFILE: "pod042",
            fnox_host.EXEC_KEYS: '["SHARED", "HOST_ONLY"]',
            "SHARED": "cached-shared",
            "HOST_ONLY": "cached-host",
            "FAIL_OP": "1",
            "OP_SERVICE_ACCOUNT_TOKEN": "poison-token",
            "FNOX_PROFILE": "work",
        }
    )
    invocation = fnox_host.prepare_invocation(
        configuration,
        "pod042",
        "exec",
        ["true"],
        environment,
        None,
        fnox=fnox_binary,
        secrets=["SHARED"],
    )
    assert invocation.environment["SHARED"] == "cached-shared"
    assert "HOST_ONLY" not in invocation.environment
    assert json.loads(invocation.environment[fnox_host.EXEC_KEYS]) == ["SHARED"]
    assert not any(key.startswith(("OP_", "FNOX_")) for key in invocation.environment)
    assert fnox_host.resolve_values(
        configuration,
        "pod042",
        ["SHARED"],
        invocation.environment,
        None,
        fnox=fnox_binary,
    ) == {"SHARED": "cached-shared"}
    assert not Path(environment["OP_CALLS"]).exists()


def test_resolver_never_reaches_op_through_a_mise_shim(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    tmp_path: Path,
) -> None:
    shims = tmp_path / ".local/share/mise/shims"
    shims.mkdir(parents=True)
    shim = shims / "op"
    shim.write_text("#!/bin/sh\nexit 97\n")
    shim.chmod(0o755)
    environment["PATH"] = f"{shims}{os.pathsep}{environment['PATH']}"
    invocation = fnox_host.prepare_invocation(
        configuration,
        "macos",
        "get",
        ["SHARED"],
        environment,
        None,
        fnox=fnox_binary,
    )
    assert str(shims) not in invocation.environment["PATH"].split(os.pathsep)
    assert shutil.which("op", path=invocation.environment["PATH"]) == str(
        tmp_path / "bin/op"
    )
    assert fnox_host.resolved_output(invocation).strip() == "sentinel-shared"


def test_nested_late_private_read_uses_only_personal_provider(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
) -> None:
    (configuration / "fnox.macos.toml").write_text("""import = ["fnox.toml"]
[providers.personal]
type = "1password"
account = "personal-account"
auth_command = ""
[secrets]
PRIVATE = { provider = "personal", value = "op://Private/password/value" }
UNRELATED = { provider = "personal", value = "op://Private/unrelated/value" }
""")
    environment.update(
        {
            fnox_host.EXEC_PROFILE: "macos",
            fnox_host.EXEC_KEYS: '["SHARED"]',
            "SHARED": "cached-shared",
            "FAKE_VALUES": json.dumps(
                {"op://Private/password/value": "sentinel-private"}
            ),
        }
    )
    values = fnox_host.resolve_values(
        configuration, "macos", ["PRIVATE"], environment, None, fnox=fnox_binary
    )
    assert values == {"PRIVATE": "sentinel-private"}
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 1
    assert "personal-account" in calls[0]["args"]
    assert "op://Private/password/value" in calls[0]["args"]
    assert calls[0]["token"] is None


def test_partial_resolution_failure_never_starts_child_or_prints_values(
    configuration: Path,
    environment: dict[str, str],
    fnox_binary: str,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "must-not-exist"
    environment["FAIL_REF"] = "op://agent/host/value"
    assert (
        run_fnox(
            configuration,
            "pod042",
            "exec",
            ["touch", str(output)],
            environment,
            None,
            fnox=fnox_binary,
            secrets=["SHARED", "HOST_ONLY"],
        )
        == 1
    )
    assert not output.exists()
    captured = capfd.readouterr()
    assert captured.out == captured.err == ""
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2


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
    assert not Path(environment["OP_CALLS"]).exists()


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
