from pathlib import Path
import shutil
import subprocess

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


def test_ansible_does_not_propagate_sudo_password_environment() -> None:
    for path in (ROOT / "ansible").rglob("*.yml"):
        assert "HOMEBREW_SUDO_ASKPASS_PASS" not in path.read_text(), path
    homebrew = (ROOT / "ansible/roles/homebrew/tasks/main.yml").read_text()
    assert homebrew.count('SUDO_ASKPASS: "{{') == 3


def test_bootstrap_does_not_preauthenticate_desktop_account() -> None:
    bootstrap = (ROOT / "scripts/bootstrap.sh").read_text()
    assert "op account get" not in bootstrap
    assert "op signin" not in bootstrap


def test_token_installer_discovers_fnox_without_project_environment() -> None:
    installer = (ROOT / "scripts/pod042_service_token.py").read_text()
    assert '["mise", "--no-env", "which", "fnox"]' in installer
