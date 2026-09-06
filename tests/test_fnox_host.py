from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tomllib

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/fnox_host.py"
SPEC = spec_from_file_location("fnox_host", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
fnox_host = module_from_spec(SPEC)
sys.modules[SPEC.name] = fnox_host
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
) -> int:
    invocation = fnox_host.build_command(
        root, profile, operation, arguments, inherited, token, fnox=fnox
    )
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
account = "desktop-account"
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
    return subprocess.check_output(["mise", "which", "fnox"], text=True).strip()


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
if "blocked-account" in args or os.environ.get("FAIL_OP"):
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


@pytest.mark.parametrize("hostname", ["omarchy", "ML-other", "POD042", "runner-123"])
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
        "env = true",
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
    assert len(calls) == 1
    assert calls[0]["args"][0] == "inject"
    assert "desktop-account" not in calls[0]["args"]
    assert calls[0]["token"] == "sentinel-token"


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
    global_config = tmp_path / ".config/fnox"
    global_config.mkdir(parents=True)
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
        "FNOX_HOST_OP_TOKEN",
        "POD042_SERVICE_ACCOUNT_TOKEN",
        "ANTHROPIC_AUTH_TOKEN",
    } <= keys


@pytest.mark.parametrize("profile", ["macos", "work", "pod042", "orb"])
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
    counts = {"macos": 33, "work": 38, "pod042": 59, "orb": 31}
    assert len(set(child) & fnox_host.declared_keys(root)) == counts[profile]
    calls = [
        json.loads(line)
        for line in Path(environment["OP_CALLS"]).read_text().splitlines()
    ]
    batches = {"macos": 2, "work": 3, "pod042": 1, "orb": 1}
    assert len(calls) == batches[profile]
    verbs = [
        next(arg for arg in call["args"] if arg in {"read", "inject"}) for call in calls
    ]
    expected_verbs = (
        ["inject", "inject", "read"]
        if profile == "work"
        else ["inject"] * batches[profile]
    )
    assert sorted(verbs) == expected_verbs
    if token:
        assert all(
            call["token"] == token and "--account" not in call["args"] for call in calls
        )
    else:
        assert all(call["token"] is None for call in calls)
        accounts = {call["args"][call["args"].index("--account") + 1] for call in calls}
        expected_accounts = {"PQ7X5W7V6FDADHPFFEO62TLFEM"}
        if profile == "work":
            expected_accounts.add("verified-work-account")
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
    binary_dir = Path(environment["PATH"].split(":")[0])
    (binary_dir / "fnox").symlink_to(fnox_binary)
    environment["OP_SERVICE_ACCOUNT_TOKEN"] = "sentinel-token"
    child = """import signal, sys, time

def stop(signum, frame):
    time.sleep(0.4)
    print("finished", flush=True)
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
