from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
    from scripts import automation_identity as identity


@dataclass
class Sandbox:
    root: Path
    home: Path
    environment: dict[str, str]
    fnox: str
    calls: Path


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "fnox.toml").write_text("""root = true
env = "exec"
if_missing = "error"
prompt_auth = false
[daemon]
enabled = false
[providers.agent]
type = "1password"
token = { secret = "FNOX_HOST_OP_TOKEN" }
auth_command = ""
[providers.personal]
type = "1password"
account = "desktop-account"
auth_command = ""
[secrets]
NEXTDNS_PROFILE_ID = { provider = "agent", value = "op://agent/probe/value" }
SHELL_ONLY = { provider = "agent", value = "op://agent/shell/value", env = true }
CLI_PROXY_API_KEY = { provider = "agent", value = "op://agent/cli/value" }
PARALLEL_API_KEY = { provider = "agent", value = "op://agent/parallel/value" }
PRIVATE = { provider = "personal", value = "op://Private/password/value" }
""")
    (root / "fnox.macos.toml").write_text("""import = ["fnox.toml"]
[secrets]
POD042_SERVICE_ACCOUNT_TOKEN = { provider = "personal", value = "op://agent/bootstrap/credential", env = false }
""")
    binary = tmp_path / "bin"
    binary.mkdir()
    op = binary / "op"
    op.write_text(f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
with open(os.environ["OP_CALLS"], "a") as stream:
    stream.write(json.dumps({{"args":args,"token":token}}) + "\\n")
if token and os.environ.get("FAIL_AGENT"):
    print("deliberately sensitive error: " + token, file=sys.stderr)
    sys.exit(1)
if "desktop-account" in args and os.environ.get("FAIL_PRIVATE") and "op://agent/bootstrap/credential" not in args:
    print("private credential must not be fetched", file=sys.stderr)
    sys.exit(1)
if token and os.environ.get("CHANGE_DESTINATION"):
    Path(os.environ["CHANGE_DESTINATION"]).write_text("concurrent edit")
values = {{
    "op://agent/bootstrap/credential": "shared-automation-token",
    "op://agent/probe/value": "probe-result",
    "op://agent/shell/value": "shell-result",
    "op://agent/cli/value": "cli-result",
    "op://agent/parallel/value": "parallel-result",
    "op://Private/password/value": "private-result",
}}
if "read" in args:
    print(values[args[args.index("read") + 1]])
elif "inject" in args:
    text = sys.stdin.read()
    for reference, value in values.items():
        text = text.replace(reference, value)
    sys.stdout.write(text)
else:
    sys.exit(2)
""")
    op.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    config = identity.identity_path(home)
    config.parent.mkdir(parents=True)
    config.write_text(
        '[secrets.FNOX_HOST_OP_TOKEN]\ndefault = "old-token"\nenv = false\n'
    )
    config.chmod(0o600)
    calls = tmp_path / "calls.jsonl"
    environment = {
        "HOME": str(home),
        "PATH": f"{binary}:/usr/bin:/bin",
        "OP_CALLS": str(calls),
    }
    fnox = (
        os.environ.get("FNOX_TEST_BINARY")
        or subprocess.check_output(["mise", "which", "fnox"], text=True).strip()
    )
    return Sandbox(root, home, environment, fnox, calls)


def call_records(sandbox: Sandbox) -> list[dict[str, object]]:
    return [
        cast(dict[str, object], json.loads(line))
        for line in sandbox.calls.read_text().splitlines()
    ]


def invoke(sandbox: Sandbox, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sandbox.fnox, "--no-daemon", "--non-interactive", *arguments],
        cwd=sandbox.root,
        env=sandbox.environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_enrollment_probes_before_atomic_private_replacement(sandbox: Sandbox) -> None:
    path = identity.identity_path(sandbox.home)
    before = path.stat().st_ino
    sandbox.environment.update(
        {
            "OP_SERVICE_ACCOUNT_TOKEN": "poison",
            "FNOX_OP_SERVICE_ACCOUNT_TOKEN": "poison",
            "POD042_SERVICE_ACCOUNT_TOKEN": "stale-token",
            "NEXTDNS_PROFILE_ID": "stale-probe-result",
            "FAIL_PRIVATE": "1",
        }
    )
    identity.enroll(path, sandbox.root, sandbox.fnox, sandbox.environment)
    assert identity.read_identity(path, os.getuid()) == "shared-automation-token"
    assert path.stat().st_ino != before
    assert path.stat().st_mode & 0o777 == 0o600
    assert list(path.parent.iterdir()) == [path]
    calls = call_records(sandbox)
    assert len(calls) == 2
    assert calls[0]["token"] is None
    assert calls[1]["token"] == "shared-automation-token"
    assert all("shared-automation-token" not in str(call["args"]) for call in calls)
    assert sandbox.environment["OP_SERVICE_ACCOUNT_TOKEN"] == "poison"


def test_first_enrollment_creates_a_private_native_directory(sandbox: Sandbox) -> None:
    path = identity.identity_path(sandbox.home)
    path.unlink()
    path.parent.rmdir()
    identity.enroll(path, sandbox.root, sandbox.fnox, sandbox.environment)
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert identity.read_identity(path, os.getuid()) == "shared-automation-token"


def test_failed_candidate_preserves_existing_identity_without_secret_error(
    sandbox: Sandbox,
) -> None:
    path = identity.identity_path(sandbox.home)
    before = path.read_bytes()
    inode = path.stat().st_ino
    sandbox.environment["FAIL_AGENT"] = "1"
    with pytest.raises(
        identity.IdentityError, match="failed its fnox probe"
    ) as failure:
        identity.enroll(path, sandbox.root, sandbox.fnox, sandbox.environment)
    assert "shared-automation-token" not in str(failure.value)
    assert path.read_bytes() == before
    assert path.stat().st_ino == inode
    assert list(path.parent.iterdir()) == [path]


def test_concurrent_edit_is_not_overwritten(sandbox: Sandbox) -> None:
    path = identity.identity_path(sandbox.home)
    sandbox.environment["CHANGE_DESTINATION"] = str(path)
    with pytest.raises(identity.IdentityError, match="changed during enrollment"):
        identity.enroll(path, sandbox.root, sandbox.fnox, sandbox.environment)
    assert path.read_text() == "concurrent edit"
    assert list(path.parent.iterdir()) == [path]


def test_unrelated_global_configuration_is_not_overwritten(sandbox: Sandbox) -> None:
    path = identity.identity_path(sandbox.home)
    path.write_text('[secrets]\nSOMETHING = { default = "preserve me" }\n')
    before = path.read_bytes()
    with pytest.raises(identity.IdentityError, match="hidden token"):
        identity.enroll(path, sandbox.root, sandbox.fnox, sandbox.environment)
    assert path.read_bytes() == before
    assert not sandbox.calls.exists()


def test_identity_rejects_permissions_symlinks_and_wrong_owner(
    sandbox: Sandbox,
) -> None:
    path = identity.identity_path(sandbox.home)
    path.chmod(0o644)
    with pytest.raises(identity.IdentityError, match="mode-0600"):
        identity.read_identity(path, os.getuid())
    path.chmod(0o600)
    with pytest.raises(identity.IdentityError, match="mode-0600"):
        identity.read_identity(path, os.getuid() + 1)
    link = path.parent / "link.toml"
    link.symlink_to(path)
    with pytest.raises(OSError):
        identity.enroll(link, sandbox.root, sandbox.fnox, sandbox.environment)
    assert identity.read_identity(path, os.getuid()) == "old-token"


def test_identity_directory_does_not_follow_symlinks_or_accept_shared_writes(
    sandbox: Sandbox,
) -> None:
    path = identity.identity_path(sandbox.home)
    path.parent.chmod(0o777)
    with pytest.raises(identity.IdentityError, match="directory must be owned"):
        identity.enroll(path, sandbox.root, sandbox.fnox, sandbox.environment)
    path.parent.chmod(0o700)
    link = sandbox.home / "linked-identity"
    link.symlink_to(path.parent, target_is_directory=True)
    with pytest.raises(identity.IdentityError, match="directory must be owned"):
        identity.enroll(
            link / "config.toml", sandbox.root, sandbox.fnox, sandbox.environment
        )
    assert identity.read_identity(path, os.getuid()) == "old-token"


def test_file_revision_ignores_reads_but_detects_metadata_changes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "identity"
    path.touch()
    metadata = SimpleNamespace(
        st_dev=1,
        st_ino=2,
        st_size=3,
        st_mtime_ns=4,
        st_ctime_ns=5,
        st_mode=0o100600,
        st_uid=6,
        st_gid=7,
        st_atime_ns=8,
    )
    with patch.object(Path, "lstat", return_value=metadata):
        revision = identity.file_revision(path)
        metadata.st_atime_ns = 9
        assert identity.file_revision(path) == revision
        metadata.st_ctime_ns = 10
        assert identity.file_revision(path) != revision


@pytest.mark.parametrize("token", ["", "a b", "a\nb", "a\rb", "a\tb"])
def test_malformed_token_is_rejected(token: str) -> None:
    with pytest.raises(identity.IdentityError):
        identity.validate_token(token)


def test_native_export_filters_before_fetch_and_never_exports_identity(
    sandbox: Sandbox,
) -> None:
    sandbox.environment["FAIL_PRIVATE"] = "1"
    result = invoke(sandbox, ["export", "--format=json"])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["secrets"] == {"SHELL_ONLY": "shell-result"}
    calls = call_records(sandbox)
    assert len(calls) == 1
    assert calls[0]["token"] == "old-token"
    assert "desktop-account" not in str(calls[0]["args"])


@pytest.mark.parametrize(
    "sibling", ["config.local.toml", "config.default.toml", "config.macos.toml"]
)
def test_explicit_native_export_ignores_global_sibling_overlays(
    sandbox: Sandbox, sibling: str
) -> None:
    directory = identity.identity_path(sandbox.home).parent
    (directory / sibling).write_text(
        '[secrets]\nSHELL_ONLY = { default = "poison-shell", env = true }\n'
        'GLOBAL_POISON = { default = "poison-extra", env = true }\n'
    )
    sandbox.environment["FAIL_PRIVATE"] = "1"
    result = invoke(
        sandbox,
        [
            "--config",
            str(sandbox.root / "fnox.toml"),
            "--profile",
            "default",
            "export",
            "--format=json",
        ],
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["secrets"] == {"SHELL_ONLY": "shell-result"}
    calls = call_records(sandbox)
    assert len(calls) == 1
    assert calls[0]["token"] == "old-token"


def test_native_get_fetches_only_requested_secret(sandbox: Sandbox) -> None:
    sandbox.environment["FAIL_PRIVATE"] = "1"
    result = invoke(sandbox, ["get", "PARALLEL_API_KEY"])
    assert result.returncode == 0, result.stderr
    assert result.stdout == "parallel-result\n"
    calls = call_records(sandbox)
    assert len(calls) == 1
    assert calls[0]["args"] == ["read", "op://agent/parallel/value"]


def test_private_get_uses_desktop_without_automation_identity(sandbox: Sandbox) -> None:
    identity.identity_path(sandbox.home).unlink()
    result = invoke(sandbox, ["get", "PRIVATE"])
    assert result.returncode == 0, result.stderr
    assert result.stdout == "private-result\n"
    calls = call_records(sandbox)
    assert len(calls) == 1
    assert calls[0]["token"] is None
    assert "desktop-account" in str(calls[0]["args"])


def test_explicit_exec_still_fetches_private_host_fields(sandbox: Sandbox) -> None:
    sandbox.environment["FAIL_PRIVATE"] = "1"
    result = invoke(sandbox, ["exec", "--", "/usr/bin/true"])
    assert result.returncode != 0
    assert any("desktop-account" in str(call["args"]) for call in call_records(sandbox))


def test_native_zsh_hook_loads_and_unloads_only_shell_keys(sandbox: Sandbox) -> None:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is not installed")
    sandbox.environment["FAIL_PRIVATE"] = "1"
    command = """eval "$("$1" --no-daemon --non-interactive hook-env -s zsh)"
"$2" -c 'import os; print(os.environ.get("SHELL_ONLY")); assert not any(k in os.environ for k in ("FNOX_HOST_OP_TOKEN", "OP_SERVICE_ACCOUNT_TOKEN", "PRIVATE", "CLI_PROXY_API_KEY", "PARALLEL_API_KEY"))'
cd "$3"
eval "$("$1" --no-daemon --non-interactive hook-env -s zsh)"
"$2" -c 'import os; print(os.environ.get("SHELL_ONLY"))'
"""
    result = subprocess.run(
        [
            zsh,
            "-f",
            "-c",
            command,
            "identity-test",
            sandbox.fnox,
            sys.executable,
            str(sandbox.home),
        ],
        cwd=sandbox.root,
        env=sandbox.environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "shell-result\nNone\n"
    assert len(call_records(sandbox)) == 1
