import os
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
JJ = ROOT / "bootstrap/capabilities/jj-client"
IDENTITY = ROOT / "bootstrap/capabilities/vcs-identity/mise.toml"


def fixture(tmp_path: Path, profile: str) -> tuple[Path, Path, dict[str, str]]:
    home = tmp_path / "home"
    target = tmp_path / "target"
    home.mkdir(parents=True)
    target.mkdir()
    (target / "jj-client").symlink_to(JJ / "files", target_is_directory=True)
    (target / "mise.toml").symlink_to(JJ / "mise.toml")
    work = profile == "work"
    (target / "mise.local.toml").write_text(
        '[vars]\nvcs_personal_email = "personal@test"\n'
        'vcs_personal_public_signing_key = "ssh-ed25519 AAAAPERSONAL"\n'
        f'host_profile = "{"work" if work else "personal"}"\n'
        f'jj_signing_program = "{"" if profile == "pod" else "/Applications/1Password.app/Contents/MacOS/op-ssh-sign"}"\n'
        + (
            'vcs_work_email = "work@test"\nvcs_work_signing_key = "ssh-ed25519 AAAAWORK"\n'
            if work
            else ""
        )
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "MISE_CACHE_DIR": str(home / ".cache/mise"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_DATA_DIR": str(home / ".local/share/mise"),
        "MISE_STATE_DIR": str(home / ".local/state/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(target / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(target / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
    }
    return home, target, env


@pytest.mark.parametrize("profile", ["personal", "pod", "work"])
def test_actual_mise_renders_host_identity_and_signing_behavior(
    tmp_path: Path, profile: str
) -> None:
    home, target, env = fixture(tmp_path, profile)
    subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    config = tomllib.loads(
        (home / ".config/jj/conf.d/00-ansiblonomicon.toml").read_text()
    )
    assert config["user"] == {
        "email": "work@test" if profile == "work" else "personal@test",
        "name": "Thurston Sandberg",
    }
    assert config["signing"]["key"] == (
        "ssh-ed25519 AAAAWORK" if profile == "work" else "ssh-ed25519 AAAAPERSONAL"
    )
    assert config["signing"]["behavior"] == "drop"
    assert ("backends" in config["signing"]) is (profile != "pod")


def test_fragment_preserves_old_file_and_unknown_same_section_field(
    tmp_path: Path,
) -> None:
    home, target, env = fixture(tmp_path, "personal")
    path = home / ".config/jj/config.toml"
    path.parent.mkdir(parents=True)
    original = (
        b'# brackets in strings and comments must be harmless: "[x]" [y]\n'
        b'[user]\nemail = "old@test"\nname = "Old"\n\n'
        b'[ui]\ncolor = "always"\n\n[revsets]\nlog = "all()"\n'
    )
    path.write_bytes(original)
    path.chmod(0o640)
    before = path.stat()
    command = ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"]
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    fragment = home / ".config/jj/conf.d/00-ansiblonomicon.toml"

    # Each file must be valid TOML independently; JJ overlays tables rather than
    # concatenating them, so repeated [ui] tables across files are valid.
    legacy = tomllib.loads(path.read_text())
    managed = tomllib.loads(fragment.read_text())
    assert legacy["ui"]["color"] == "always"
    assert managed["ui"]["editor"] == "nvim"
    assert managed["user"]["email"] == "personal@test"
    after = path.stat()
    assert path.read_bytes() == original
    assert (after.st_mode, after.st_mtime_ns, after.st_ino) == (
        before.st_mode,
        before.st_mtime_ns,
        before.st_ino,
    )

    first = fragment.stat().st_mtime_ns
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert fragment.stat().st_mtime_ns == first

    if shutil.which("jj"):
        jj_env = {
            **env,
            "XDG_CONFIG_HOME": str(home / ".config"),
        }
        nonrepo = tmp_path / "nonrepo"
        nonrepo.mkdir()
        for key, expected in (
            ("ui.color", "always"),
            ("ui.editor", "nvim"),
            ("user.email", "personal@test"),
        ):
            result = subprocess.run(
                ["jj", "config", "get", key],
                env=jj_env,
                cwd=nonrepo,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip().strip('"') == expected


@pytest.mark.parametrize("missing", ["vcs_work_email", "vcs_work_signing_key"])
def test_missing_work_identity_fails_before_writing(
    tmp_path: Path, missing: str
) -> None:
    home, target, env = fixture(tmp_path, "work")
    local = target / "mise.local.toml"
    local.write_text(
        "\n".join(
            line
            for line in local.read_text().splitlines()
            if not line.startswith(f"{missing} =")
        )
        + "\n"
    )
    result = subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not (home / ".config/jj").exists()


def test_invalid_personal_identity_fails_before_writing(tmp_path: Path) -> None:
    home, target, env = fixture(tmp_path, "personal")
    local = target / "mise.local.toml"
    local.write_text(local.read_text().replace('"personal@test"', "'bad\"email'"))
    result = subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "contains characters unsafe for JJ config" in result.stderr
    assert not (home / ".config/jj").exists()


def test_shared_identity_is_declared_outside_consumers() -> None:
    assert (
        tomllib.loads(IDENTITY.read_text())["vars"]["vcs_personal_email"]
        == "thurstonsand@gmail.com"
    )
    assert "[vars]" not in (JJ / "mise.toml").read_text()


@pytest.mark.parametrize("host", ["Thurstons-MacBook-Pro", "pod042"])
def test_real_personal_target_dry_run_resolves_jj_assets(
    tmp_path: Path, host: str
) -> None:
    target = ROOT / "bootstrap/targets" / host
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "MISE_CACHE_DIR": str(home / ".cache/mise"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_DATA_DIR": str(home / ".local/share/mise"),
        "MISE_STATE_DIR": str(home / ".local/state/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(tmp_path / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(tmp_path / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "MISE_ENV": "vcs-identity,jj-client",
    }
    subprocess.run(
        [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "--only",
            "dotfiles",
            "--dry-run",
        ],
        env=env,
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
