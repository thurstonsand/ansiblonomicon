import os
from pathlib import Path
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/git-client"
IDENTITY = ROOT / "bootstrap/capabilities/vcs-identity/mise.toml"
PUBLIC_KEY = "ssh-ed25519 AAAATEST personal@test"
SIGNING_PROGRAM = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign"
BASE_ENV = {
    "PATH": os.environ["PATH"],
    "LANG": "C.UTF-8",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def isolated_env(home: Path, target: Path, *, delta: bool) -> dict[str, str]:
    return {
        **BASE_ENV,
        "HOME": str(home),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "MISE_CACHE_DIR": str(home / ".cache/mise"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_DATA_DIR": str(home / ".local/share/mise"),
        "MISE_STATE_DIR": str(home / ".local/state/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(target / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(target / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "GIT_CLIENT_DELTA": str(delta).lower(),
        "GIT_CONFIG_GLOBAL": str(home / ".config/git/config"),
    }


def fixture(tmp_path: Path, profile: str) -> tuple[Path, Path, dict[str, str]]:
    home = tmp_path / "home"
    target = tmp_path / "target"
    home.mkdir(parents=True)
    target.mkdir(parents=True)
    (target / "git-client").symlink_to(CAPABILITY / "files", target_is_directory=True)
    (target / "mise.toml").symlink_to(CAPABILITY / "mise.toml")
    work = profile == "work"
    scm = """[url "ssh://git@Git.Corp.test:2222/Team"]
    insteadOf = "https://git.corp.test/scm/"
[url "ssh://git@forge.test"]
    insteadOf = "https://forge.test/"
"""
    (target / "mise.local.toml").write_text(
        '[vars]\nvcs_personal_email = "personal@test"\n'
        f'vcs_personal_public_signing_key = "{PUBLIC_KEY}"\n'
        f'git_client_home = "{home}"\n'
        f'host_profile = "{"work" if work else "personal"}"\n'
        + (
            f'git_personal_signing_key = "{home}/.ssh/id_ed25519_git"\n'
            if profile == "pod"
            else ""
        )
        + f"git_signing_program = {'"' + SIGNING_PROGRAM + '"' if profile != 'pod' else '""'}\n"
        + (
            'vcs_work_email = "work@test"\nvcs_work_signing_key = "ssh-ed25519 AAAAWORK"\n'
            if work
            else ""
        )
        + ("git_scm_config = '''\n" + scm + "'''\n" if work else "")
    )
    if work:
        (target / "mise.git-client-work.toml").write_text(
            '[dotfiles]\n"~/.config/git/personal.inc" = { source = "git-client/personal.inc.tera", mode = "template" }\n'
        )
    env = isolated_env(home, target, delta=True)
    if work:
        env["MISE_ENV"] = "git-client-work"
    return home, target, env


def git(home: Path, *args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        env={
            **BASE_ENV,
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": str(home / ".config/git/config"),
        },
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_hosts_use_shared_personal_identity_defaults() -> None:
    shared = tomllib.loads(IDENTITY.read_text())["vars"]
    assert shared == {
        "vcs_personal_email": "thurstonsand@gmail.com",
        "vcs_personal_public_signing_key": (
            "ssh-ed25519 "
            "AAAAC3NzaC1lZDI1NTE5AAAAIF6GpY+hdZp60Fbnk9B03sntiJRx7OgLwutV5vJpV6P+"
        ),
    }
    for host in ("ML-DFC6YK6VJQ", "Thurstons-MacBook-Pro", "pod042"):
        host_vars = tomllib.loads(
            (ROOT / "bootstrap/targets" / host / "mise.toml").read_text()
        )["vars"]
        assert host_vars["host_profile"] == (
            "work" if host == "ML-DFC6YK6VJQ" else "personal"
        )
        assert "git_client_profile" not in host_vars
        assert "vcs_personal_email" not in host_vars
        assert "vcs_personal_public_signing_key" not in host_vars
    assert (
        "git_personal_signing_key"
        not in tomllib.loads(
            (ROOT / "bootstrap/targets/ML-DFC6YK6VJQ/mise.toml").read_text()
        )["vars"]
    )
    assert (
        "git_personal_signing_key"
        not in tomllib.loads(
            (ROOT / "bootstrap/targets/Thurstons-MacBook-Pro/mise.toml").read_text()
        )["vars"]
    )
    assert tomllib.loads((ROOT / "bootstrap/targets/pod042/mise.toml").read_text())[
        "vars"
    ]["git_personal_signing_key"] == ("/home/thurstonsand/.ssh/id_ed25519_git")


@pytest.mark.parametrize("profile", ["pod", "personal", "work"])
def test_actual_mise_produces_literal_effective_git_settings(
    tmp_path: Path, profile: str
) -> None:
    home, target, env = fixture(tmp_path, profile)
    command = ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"]
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert git(home, "config", "--global", "user.email") == (
        "work@test" if profile == "work" else "personal@test"
    )
    assert git(home, "config", "--global", "core.pager") == "delta"
    assert git(home, "config", "--global", "commit.gpgSign") == "true"
    assert git(home, "config", "--global", "gpg.format") == "ssh"
    assert git(home, "config", "--global", "user.signingKey") == (
        str(home / ".ssh/id_ed25519_git")
        if profile == "pod"
        else "ssh-ed25519 AAAAWORK"
        if profile == "work"
        else PUBLIC_KEY
    )
    program = subprocess.run(
        ["git", "config", "--global", "--get", "gpg.ssh.program"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if profile == "pod":
        assert program.returncode == 1
    else:
        assert program.stdout.strip() == SIGNING_PROGRAM
    assert (home / ".config/git/attributes").is_symlink()
    assert (home / ".config/git/ignore").is_symlink()
    if profile == "work":
        personal = home / "code/personal/nested/project"
        external = home / "code/work/project"
        for path in (personal, external):
            path.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        assert git(home, "config", "user.email", cwd=personal) == "personal@test"
        assert git(home, "config", "user.signingKey", cwd=personal) == PUBLIC_KEY
        assert git(home, "config", "user.email", cwd=external) == "work@test"
        rewrites = git(
            home, "config", "--global", "--get-regexp", r"^url\."
        ).splitlines()
        assert (
            "url.ssh://git@Git.Corp.test:2222/Team.insteadof https://git.corp.test/scm/"
            in rewrites
        )
        assert "url.ssh://git@forge.test.insteadof https://forge.test/" in rewrites


def test_adoption_preserves_unknown_repeated_values_and_is_metadata_idempotent(
    tmp_path: Path,
) -> None:
    home, target, env = fixture(tmp_path, "work")
    config = home / ".config/git/config"
    config.parent.mkdir(parents=True)
    config.write_text(
        "[user]\nemail = old@test\n"
        '[url "ssh://git@Git.Corp.test:2222/Team"]\ninsteadOf = https://git.corp.test/scm/\n'
        '[url "ssh://git@git.corp.test:2222/Team"]\ninsteadOf = https://unmanaged.test/\n'
        '[includeIf "gitdir:~/code/personal/"]\npath = personal.inc\n'
        '[includeIf "gitdir:~/Code/Personal/"]\npath = unmanaged.inc\n'
        '[credential "https://ampcode.com"]\nhelper = amp\n[safe]\ndirectory = /one\ndirectory = /two\n'
    )
    config.chmod(0o640)
    (home / ".gitconfig").write_text(
        '[includeIf "gitdir:~/code/personal/"]\npath = ~/.config/git/personal.inc\n'
        "[credential]\nhelper = osxkeychain\n"
    )
    (config.parent / "attributes").write_text("*.lockb binary diff=lockb\n")
    (config.parent / "ignore").write_text(".DS_Store\n.cache\n.nix\n")
    command = [
        "mise",
        "-C",
        str(target),
        "bootstrap",
        "--only",
        "dotfiles",
        "--force-dotfiles",
        "--yes",
    ]
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert config.stat().st_mode & 0o777 == 0o640
    assert (config.parent / "attributes").is_symlink()
    assert (config.parent / "ignore").is_symlink()
    assert (
        git(home, "config", "--get", "credential.https://ampcode.com.helper") == "amp"
    )
    assert git(home, "config", "--get-all", "safe.directory").splitlines() == [
        "/one",
        "/two",
    ]
    assert git(home, "config", "--get-all", "user.email") == "work@test"
    assert (
        git(
            home,
            "config",
            "--global",
            "--get-all",
            "url.ssh://git@git.corp.test:2222/Team.insteadOf",
        )
        == "https://unmanaged.test/"
    )
    assert (
        git(
            home,
            "config",
            "--global",
            "--get",
            "includeIf.gitdir:~/Code/Personal/.path",
        )
        == "unmanaged.inc"
    )
    assert (
        git(home, "config", "--file", str(home / ".gitconfig"), "credential.helper")
        == "osxkeychain"
    )
    legacy_include = subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(home / ".gitconfig"),
            "--get-all",
            "includeIf.gitdir:~/code/personal/.path",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert legacy_include.returncode == 1
    first = config.stat().st_mtime_ns
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert config.stat().st_mtime_ns == first
    config.write_text(
        config.read_text() + '[credential "https://new.test"]\nhelper = new\n'
    )
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert git(home, "config", "--get", "credential.https://new.test.helper") == "new"


def test_check_and_missing_work_facts_do_not_write(tmp_path: Path) -> None:
    home, target, env = fixture(tmp_path, "work")
    env.pop("MISE_ENV")
    local_config = target / "mise.local.toml"
    text = local_config.read_text()
    text = text.replace('vcs_work_email = "work@test"\n', "").replace(
        'vcs_work_signing_key = "ssh-ed25519 AAAAWORK"\n', ""
    )
    start = text.index("git_scm_config = '''")
    end = text.index("'''", start + len("git_scm_config = '''")) + 3
    local_config.write_text(text[:start] + text[end:])
    result = subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not (home / ".config/git").exists()

    home2, target2, env2 = fixture(tmp_path / "check", "personal")
    subprocess.run(
        ["mise", "-C", str(target2), "bootstrap", "--only", "dotfiles", "--dry-run"],
        env=env2,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not (home2 / ".config/git").exists()


def test_delta_settings_are_absent_when_tool_detection_is_false(tmp_path: Path) -> None:
    home, target, env = fixture(tmp_path, "personal")
    env["GIT_CLIENT_DELTA"] = "false"
    config = home / ".config/git/config"
    config.parent.mkdir(parents=True)
    config.write_text(
        "[core]\npager = delta\n[interactive]\ndiffFilter = delta --color-only\n"
        "[delta]\nnavigate = true\nside-by-side = true\nline-numbers = true\n"
        "hyperlinks = true\nfeatures = decorations\n"
    )
    legacy_global = home / ".gitconfig"
    legacy_global.write_text(
        '[includeIf "gitdir:~/code/personal/"]\npath = ~/.config/git/personal.inc\n'
    )
    subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["git", "config", "--global", "--get", "core.pager"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert git(home, "config", "--global", "delta.features") == "decorations"
    assert "personal.inc" in legacy_global.read_text()


def test_work_profile_allows_omitted_scm_config(tmp_path: Path) -> None:
    home, target, env = fixture(tmp_path, "work")
    target_config = target / "mise.local.toml"
    text = target_config.read_text()
    start = text.index("git_scm_config = '''")
    end = text.index("'''", start + len("git_scm_config = '''")) + 3
    target_config.write_text(text[:start] + text[end:])

    actual_work = tomllib.loads(
        (ROOT / "bootstrap/targets/ML-DFC6YK6VJQ/mise.toml").read_text()
    )
    assert "git_scm_config" not in actual_work["vars"]

    subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert git(home, "config", "--global", "user.email") == "work@test"


def test_malformed_scm_is_rejected_before_existing_config_is_touched(
    tmp_path: Path,
) -> None:
    home, target, env = fixture(tmp_path, "work")
    original = b"[credential]\nhelper = existing\n"
    config = home / ".config/git/config"
    config.parent.mkdir(parents=True)
    config.write_bytes(original)
    target_config = target / "mise.local.toml"
    target_config.write_text(
        target_config.read_text().replace(
            '[url "ssh://git@Git.Corp.test:2222/Team"]', '[url "unterminated]'
        )
    )

    result = subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert config.read_bytes() == original
    assert list(config.parent.iterdir()) == [config]
