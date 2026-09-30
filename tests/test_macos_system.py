import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/macos-system"
SPEC = importlib.util.spec_from_file_location(
    "pam_renderer", CAPABILITY / "pam_renderer.py"
)
assert SPEC and SPEC.loader
pam_renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pam_renderer)


@pytest.fixture
def without_sudo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "blocked-bin"
    binary.mkdir()
    sudo = binary / "sudo"
    sudo.write_text(
        "#!/bin/sh\necho 'unexpected sudo in disposable fixture' >&2\nexit 97\n"
    )
    sudo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("SUDO_ASKPASS", "/bin/false")


def test_personal_pam_canonicalizes_owned_lines_and_preserves_unknown_whitespace() -> (
    None
):
    source = "# header\n\nauth optional /old/pam_reattach.so\n  unknown  line \t\n#auth sufficient pam_tid.so\n"
    assert pam_renderer.render(source, "personal") == (
        "# header\n\n"
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "  unknown  line \t\n"
        "auth       sufficient     pam_tid.so\n"
    )


def test_work_pam_leaves_unmanaged_reattach_in_place_and_deduplicates_tid() -> None:
    source = "auth optional /custom/pam_reattach.so\n#auth sufficient pam_tid.so\nauth sufficient pam_tid.so\nother\n"
    assert pam_renderer.render(source, "work") == (
        "auth optional /custom/pam_reattach.so\n"
        "auth       sufficient     pam_tid.so\n"
        "other\n"
    )


def test_fresh_pam_state_is_valid() -> None:
    assert pam_renderer.render("", "personal") == (
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "auth       sufficient     pam_tid.so\n"
    )


def test_personal_pam_moves_only_reattach_before_existing_tid() -> None:
    source = (
        "\n# __PAM_EOF__\n"
        "auth sufficient pam_tid.so reuse_login\n"
        "auth optional pam_krb5.so try_first_pass\n"
        "auth optional /old/pam_reattach.so option\n"
        "auth sufficient pam_tid.so.other\n\n"
    )
    expected = (
        "\n# __PAM_EOF__\n"
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "auth       sufficient     pam_tid.so\n"
        "auth optional pam_krb5.so try_first_pass\n"
        "auth sufficient pam_tid.so.other\n\n"
    )
    assert pam_renderer.render(source, "personal") == expected
    assert pam_renderer.render(expected, "personal") == expected


def test_native_file_path_applies_checks_and_repeats_without_losing_lines(
    tmp_path: Path,
    without_sudo: None,
) -> None:
    destination = tmp_path / "sudo_local"
    destination.write_text(
        "\n# __PAM_EOF__\n\nauth optional /old/pam_reattach.so\n  unknown \t\n"
        "#auth sufficient pam_tid.so\n\n\n"
    )
    source = tmp_path / "sudo_local.tera"
    source.write_bytes((CAPABILITY / "files/sudo_local.tera").read_bytes())
    # Explicit ownership forces sudo even when it names the current user.
    (tmp_path / "mise.toml").write_text(
        'min_version = "2026.9.11"\n'
        '[vars]\nhost_profile = "personal"\n'
        f"[bootstrap.files.{str(destination)!r}]\n"
        'source = "sudo_local.tera"\n'
        "template = true\n"
        'mode = "0444"\n'
    )
    env = {
        **os.environ,
        "MACOS_SYSTEM_PYTHON": str(ROOT / ".venv/bin/python"),
        "MACOS_SYSTEM_PAM_RENDERER": str(CAPABILITY / "pam_renderer.py"),
    }

    subprocess.run(
        ["mise", "-C", str(tmp_path), "bootstrap", "files", "apply", "--yes"],
        env=env,
        check=True,
    )
    expected = (
        "\n# __PAM_EOF__\n\n"
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "  unknown \t\n"
        "auth       sufficient     pam_tid.so\n\n\n"
    )
    assert destination.read_text() == expected
    assert destination.stat().st_mode & 0o777 == 0o444
    before = destination.stat().st_mtime_ns
    subprocess.run(
        ["mise", "-C", str(tmp_path), "bootstrap", "files", "apply", "--dry-run"],
        env=env,
        check=True,
    )
    subprocess.run(
        ["mise", "-C", str(tmp_path), "bootstrap", "files", "apply", "--yes"],
        env=env,
        check=True,
    )
    assert destination.stat().st_mtime_ns == before


def test_driver_real_native_fixture_ignores_hostile_ancestor(
    tmp_path: Path,
    without_sudo: None,
) -> None:
    target = tmp_path / "targets/host"
    target.mkdir(parents=True)
    destination = tmp_path / "disposable_pam"
    destination.write_text("# retained without newline")
    hostile = tmp_path / "hostile"
    (tmp_path / "hostile-source").write_text("must not apply")
    (tmp_path / "mise.toml").write_text(
        '[env]\n_.source = "hostile-env.sh"\n'
        f'[bootstrap.files.{str(hostile)!r}]\nsource = "hostile-source"\n'
    )
    (tmp_path / "hostile-env.sh").write_text(
        f"touch '{tmp_path / 'env-was-loaded'}'; exit 91\n"
    )
    (target / "sudo_local.tera").write_bytes(
        (CAPABILITY / "files/sudo_local.tera").read_bytes()
    )
    (target / "mise.permissions.toml").write_text(
        '[vars]\nhost_profile = "work"\n'
        f"[bootstrap.files.{str(destination)!r}]\n"
        'source = "sudo_local.tera"\ntemplate = true\n'
        'mode = "0444"\n'
    )
    result = subprocess.run(
        [
            sys.executable,
            str(CAPABILITY / "reconcile.py"),
            "--target",
            str(target),
            "--profile",
            "work",
            "--sections",
            "permissions",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert destination.read_text() == (
        "# retained without newline\nauth       sufficient     pam_tid.so\n"
    )
    assert destination.stat().st_mode & 0o777 == 0o444
    inode = destination.stat().st_ino
    repeat = subprocess.run(result.args, text=True, capture_output=True, check=False)
    assert repeat.returncode == 0, repeat.stderr
    assert destination.stat().st_ino == inode
    assert not hostile.exists()
    assert not (tmp_path / "env-was-loaded").exists()
