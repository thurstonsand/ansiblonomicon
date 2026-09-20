import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("user", "secret"),
    [
        ("thurstonsand", "HOMEBREW_SUDO_ASKPASS_PASS"),
        ("tsandberg", "HOMEBREW_SUDO_ASKPASS_PASS_WORK"),
    ],
)
@pytest.mark.parametrize("provider_status", [0, 23])
def test_askpass_requests_only_selected_password(
    tmp_path: Path, user: str, secret: str, provider_status: int
) -> None:
    root = tmp_path / "checkout with spaces"
    ansible = root / "ansible"
    scripts = root / "scripts"
    ansible.mkdir(parents=True)
    scripts.mkdir()
    askpass = ansible / "sudo-askpass.sh"
    shutil.copyfile(ROOT / "ansible/sudo-askpass.sh", askpass)
    provider = scripts / "fnox-host"
    provider.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$(dirname "$0")/calls"\n'
        'if [ "$PROVIDER_STATUS" != 0 ]; then\n'
        '  echo "synthetic provider failure" >&2\n'
        '  exit "$PROVIDER_STATUS"\n'
        "fi\nprintf 'synthetic-password\\n'\n"
    )
    provider.chmod(0o755)

    result = subprocess.run(
        ["/bin/bash", str(askpass)],
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "USER": user,
            "PROVIDER_STATUS": str(provider_status),
            "HOMEBREW_SUDO_ASKPASS_PASS": "stale-personal-password",
            "HOMEBREW_SUDO_ASKPASS_PASS_WORK": "stale-work-password",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert (scripts / "calls").read_text().splitlines() == ["get", secret]
    assert result.returncode == provider_status
    assert result.stdout == ("synthetic-password\n" if provider_status == 0 else "")
    assert result.stderr == (
        "" if provider_status == 0 else "synthetic provider failure\n"
    )


@pytest.mark.parametrize(
    ("user", "secret"),
    [
        ("thurstonsand", "HOMEBREW_SUDO_ASKPASS_PASS"),
        ("tsandberg", "HOMEBREW_SUDO_ASKPASS_PASS_WORK"),
    ],
)
def test_brew_filtered_scoped_exec_askpass_uses_cached_password(
    tmp_path: Path, user: str, secret: str
) -> None:
    root = tmp_path / "checkout with spaces"
    scripts = root / "scripts"
    ansible = root / "ansible"
    scripts.mkdir(parents=True)
    ansible.mkdir()
    for name in ("fnox-host", "fnox_host.py", "automation_identity.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    askpass = ansible / "sudo-askpass.sh"
    shutil.copy2(ROOT / "ansible/sudo-askpass.sh", askpass)

    (root / "fnox.toml").write_text(
        'root = true\nenv = "exec"\nif_missing = "error"\nprompt_auth = false\n'
        "[daemon]\nenabled = false\n"
        '[providers.agent]\ntype = "1password"\n'
        'token = { secret = "FNOX_HOST_OP_TOKEN" }\nauth_command = ""\n'
        f'[secrets]\n{secret} = {{ provider = "agent", value = "op://test/password" }}\n'
    )
    for profile in ("macos", "work", "pod042", "orb"):
        (root / f"fnox.{profile}.toml").write_text('import = ["fnox.toml"]\n')

    home = tmp_path / "home"
    identity = home / ".config/fnox/config.toml"
    identity.parent.mkdir(parents=True)
    identity.write_text(
        '[secrets.FNOX_HOST_OP_TOKEN]\ndefault = "synthetic-token"\nenv = false\n'
    )
    identity.chmod(0o600)
    binary = tmp_path / "bin"
    binary.mkdir()
    calls = tmp_path / "op-calls"
    op = binary / "op"
    op.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['OP_CALLS'], 'a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print('synthetic-password')\n"
    )
    op.chmod(0o755)
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    (hostile / "python3").write_text("#!/bin/sh\nexit 97\n")
    (hostile / "python3").chmod(0o755)
    fnox = (
        os.environ.get("FNOX_TEST_BINARY")
        or subprocess.check_output(["mise", "which", "fnox"], text=True).strip()
    )
    (binary / "fnox").symlink_to(fnox)

    result = subprocess.run(
        [
            sys.executable,
            str(scripts / "fnox-host"),
            "--orb",
            "exec",
            "--secret",
            secret,
            "--",
            "/bin/bash",
            "-c",
            (
                '/usr/bin/env -i USER="$USER" SUDO_ASKPASS="$SUDO_ASKPASS" '
                'HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE="$HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE" '
                'HOMEBREW_ANSIBLONOMICON_EXEC_KEYS="$HOMEBREW_ANSIBLONOMICON_EXEC_KEYS" '
                'HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON="$HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON" '
                f'{secret}="${{{secret}}}" '
                f'PATH={hostile}:/usr/bin:/bin /bin/bash "$1"'
            ),
            "askpass-child",
            str(askpass),
        ],
        env={
            "PATH": f"{binary}:/usr/bin:/bin",
            "HOME": str(home),
            "USER": user,
            "SUDO_ASKPASS": str(askpass),
            "OP_CALLS": str(calls),
            "OP_SERVICE_ACCOUNT_TOKEN": "synthetic-token",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "synthetic-password\n"
    assert len(calls.read_text().splitlines()) == 1


@pytest.mark.parametrize(
    "metadata",
    [
        {"HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": "orb"},
        {"HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": '["HOMEBREW_SUDO_ASKPASS_PASS"]'},
        {
            "HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": "work",
            "HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": '["HOMEBREW_SUDO_ASKPASS_PASS"]',
        },
        {
            "HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": "orb",
            "HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": "not-json",
        },
        {
            "HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": "orb",
            "HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": '["HOMEBREW_SUDO_ASKPASS_PASS"]',
        },
    ],
)
def test_brew_filtered_invalid_scope_rejects_without_provider_or_secret_output(
    tmp_path: Path, metadata: dict[str, str]
) -> None:
    root = tmp_path / "checkout"
    (root / "ansible").mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in ("fnox-host", "fnox_host.py", "automation_identity.py"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    askpass = root / "ansible/sudo-askpass.sh"
    shutil.copy2(ROOT / "ansible/sudo-askpass.sh", askpass)
    (root / "fnox.toml").write_text(
        'root = true\nenv = "exec"\nif_missing = "error"\nprompt_auth = false\n'
        "[daemon]\nenabled = false\n[secrets]\n"
        'HOMEBREW_SUDO_ASKPASS_PASS = { provider = "agent", value = "op://test/password" }\n'
    )
    for profile in ("macos", "work", "pod042", "orb"):
        (root / f"fnox.{profile}.toml").write_text('import = ["fnox.toml"]\n')
    calls = tmp_path / "provider-called"
    binary = tmp_path / "bin"
    binary.mkdir()
    fnox = binary / "fnox"
    fnox.write_text(f"#!/bin/sh\ntouch {calls}\necho leaked-secret\n")
    fnox.chmod(0o755)
    filtered = {
        "PATH": f"{binary}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "USER": "thurstonsand",
        "SUDO_ASKPASS": str(askpass),
        "HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON": sys.executable,
        **metadata,
    }
    if metadata.get("HOMEBREW_ANSIBLONOMICON_EXEC_KEYS", "").startswith("["):
        filtered["HOMEBREW_SUDO_ASKPASS_PASS"] = ""
    result = subprocess.run(
        [
            "/usr/bin/env",
            "-i",
            *[f"{key}={value}" for key, value in filtered.items()],
            str(askpass),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "leaked-secret" not in result.stdout
    assert not calls.exists()


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires installed macOS Homebrew"
)
def test_installed_brew_ruby_calls_askpass_through_clean_environment(
    tmp_path: Path,
) -> None:
    brew = shutil.which("brew")
    if brew is None:
        pytest.skip("Homebrew is not installed")
    profiles = {
        "Thurstons-MacBook-Pro": "macos",
        "ML-DFC6YK6VJQ": "work",
    }
    profile = profiles.get(socket.gethostname().split(".", 1)[0])
    if profile is None:
        pytest.skip("Mac hostname has no declared fnox profile")

    root = tmp_path / "isolated checkout"
    (root / "ansible").mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in ("fnox-host", "fnox_host.py", "automation_identity.py"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    askpass = root / "ansible/sudo-askpass.sh"
    shutil.copy2(ROOT / "ansible/sudo-askpass.sh", askpass)
    secret = (
        "HOMEBREW_SUDO_ASKPASS_PASS_WORK"
        if profile == "work"
        else "HOMEBREW_SUDO_ASKPASS_PASS"
    )
    (root / "fnox.toml").write_text(
        'root = true\nenv = "exec"\nif_missing = "error"\nprompt_auth = false\n'
        "[daemon]\nenabled = false\n[secrets]\n"
        f'{secret} = {{ provider = "synthetic", value = "unused" }}\n'
    )
    for name in ("macos", "work", "pod042", "orb"):
        (root / f"fnox.{name}.toml").write_text('import = ["fnox.toml"]\n')

    ruby = """
ENV["PATH"] = "/usr/bin:/bin"
path = ENV.fetch("SUDO_ASKPASS")
exec([path, path])
"""
    home = tmp_path / "home"
    home.mkdir()
    environment = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOMEBREW_NO_AUTO_UPDATE": "1",
        "HOMEBREW_NO_ANALYTICS": "1",
        "USER": "tsandberg" if profile == "work" else "thurstonsand",
        "SUDO_ASKPASS": str(askpass),
        "HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": profile,
        "HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": f'["{secret}"]',
        "HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON": sys.executable,
        secret: "synthetic-password",
    }
    result = subprocess.run(
        [brew, "ruby", "-e", ruby],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "synthetic-password\n"


@pytest.mark.parametrize("pin", ["", "/missing/python"])
def test_askpass_does_not_fallback_from_present_bad_python_pin(
    tmp_path: Path, pin: str
) -> None:
    root = tmp_path / "checkout"
    (root / "ansible").mkdir(parents=True)
    (root / "scripts").mkdir()
    askpass = root / "ansible/sudo-askpass.sh"
    shutil.copy2(ROOT / "ansible/sudo-askpass.sh", askpass)
    launcher = root / "scripts/fnox-host"
    launcher.write_text("#!/bin/sh\necho fallback-must-not-run\n")
    launcher.chmod(0o755)
    result = subprocess.run(
        ["/bin/bash", str(askpass)],
        env={
            "PATH": "/usr/bin:/bin",
            "USER": "thurstonsand",
            "HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON": pin,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""


def test_ansible_does_not_propagate_sudo_password_environment() -> None:
    for path in (ROOT / "ansible").rglob("*.yml"):
        assert "HOMEBREW_SUDO_ASKPASS_PASS" not in path.read_text(), path
    homebrew = (ROOT / "ansible/roles/homebrew/tasks/main.yml").read_text()
    assert homebrew.count('SUDO_ASKPASS: "{{') == 3
    assert homebrew.count('HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS: "1"') == 4


def test_bootstrap_does_not_preauthenticate_desktop_account() -> None:
    bootstrap = (ROOT / "scripts/bootstrap.sh").read_text()
    assert "op account get" not in bootstrap
    assert "op signin" not in bootstrap


def test_token_installer_discovers_fnox_without_project_environment() -> None:
    installer = (ROOT / "scripts/pod042_service_token.py").read_text()
    assert '["mise", "--no-env", "which", "fnox"]' in installer
