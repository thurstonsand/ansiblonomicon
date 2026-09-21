import grp
import os
from pathlib import Path
import pwd
import stat
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/shell"
HOSTS = {
    "pod042": ("personal", "linux"),
    "Thurstons-MacBook-Pro": ("personal", "darwin"),
    "ML-DFC6YK6VJQ": ("work", "darwin"),
}


def isolated_env(home: Path, target: Path) -> dict[str, str]:
    return {
        "PATH": os.environ["PATH"],
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
    }


@pytest.mark.parametrize("host", HOSTS)
def test_hosts_use_real_shared_sources_and_declare_one_zshenv_owner(host: str) -> None:
    target = ROOT / "bootstrap/targets" / host
    assert (target / "mise.shell.toml").resolve() == (
        CAPABILITY / "mise.toml"
    ).resolve()
    assert (target / "shell").resolve() == (CAPABILITY / "files").resolve()
    shared = tomllib.loads((CAPABILITY / "mise.toml").read_text())
    assert "~/.zshenv" not in shared["dotfiles"]
    if host == "ML-DFC6YK6VJQ":
        work = tomllib.loads((target / "mise.shell-work.toml").read_text())
        assert work["bootstrap"]["files"]["/Users/tsandberg/.zshenv"] == {
            "source": "shell/zshenv.tera",
            "template": True,
            "owner": "tsandberg",
            "group": "staff",
            "mode": "0600",
        }
        assert "hooks" not in work["bootstrap"]
    else:
        personal = tomllib.loads((target / "mise.shell-personal.toml").read_text())
        assert personal["dotfiles"]["~/.zshenv"]["mode"] == "template"


@pytest.mark.parametrize("profile,host_os", HOSTS.values())
def test_real_mise_render_is_valid_zsh_and_noop(
    profile: str, host_os: str, tmp_path: Path
) -> None:
    home, target = tmp_path / "home", tmp_path / "target"
    home.mkdir()
    target.mkdir()
    retired = home / ".config/direnv/direnv.toml"
    retired.parent.mkdir(parents=True)
    retired.symlink_to(target / "removed-direnv.toml")
    (target / "shell").symlink_to(CAPABILITY / "files", target_is_directory=True)
    (target / "mise.shell.toml").symlink_to(CAPABILITY / "mise.toml")
    (target / "mise.shell-personal.toml").write_text(
        '[dotfiles]\n"~/.zshenv" = { source = "shell/zshenv.tera", mode = "template" }\n'
    )
    (target / "mise.toml").write_text(
        f'[vars]\nhost_profile = "{profile}"\nhost_os = "{host_os}"\n'
    )
    env = isolated_env(home, target)
    env["MISE_ENV"] = "shell,shell-personal"
    if profile == "work":
        env["SOURCEGRAPH_TOKEN"] = "sgp_synthetic-ABC123456789"
    command = [
        "mise",
        "-C",
        str(target),
        "bootstrap",
        "--only",
        "files,dotfiles",
        "--force-dotfiles",
        "--yes",
    ]
    preview = subprocess.run(
        [*command[:-1], "--dry-run"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "direnv.toml" in preview.stdout + preview.stderr
    assert retired.is_symlink()
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert not retired.is_symlink()
    assert not retired.exists()
    paths = [home / name for name in (".zshenv", ".zprofile", ".zshrc")]
    for path in paths:
        subprocess.run(["zsh", "-n", str(path)], check=True)
        assert "direnv" not in path.read_text()
    before = [
        (
            p.stat().st_ino,
            p.stat().st_mtime_ns,
            p.stat().st_ctime_ns,
            stat.S_IMODE(p.stat().st_mode),
        )
        for p in paths
    ]
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    after = [
        (
            p.stat().st_ino,
            p.stat().st_mtime_ns,
            p.stat().st_ctime_ns,
            stat.S_IMODE(p.stat().st_mode),
        )
        for p in paths
    ]
    assert after == before
    zshenv = paths[0].read_text()
    assert ('"$HOME/scripts"' in zshenv) is (profile == "work")
    assert ('"$HOME/.amp/bin"' in zshenv) is (host_os == "linux")
    (home / ".zshenv.local").write_text("LOCAL_OVERRIDE=loaded\n")
    override = subprocess.run(
        [
            "env",
            "-i",
            f"HOME={home}",
            "zsh",
            "-f",
            "-c",
            'source "$1"; print -rn -- "$LOCAL_OVERRIDE"',
            "zsh",
            str(paths[0]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert override.stdout == "loaded"


def render_fixture_zshenv(
    tmp_path: Path, homebrew_prefix: Path, *, ruby_body: str | None
) -> subprocess.CompletedProcess[str]:
    home, target = tmp_path / "home", tmp_path / "target"
    home.mkdir()
    (target / "shell").mkdir(parents=True)
    template = (
        (CAPABILITY / "files/zshenv.tera")
        .read_text()
        .replace("/opt/homebrew", str(homebrew_prefix))
    )
    (target / "shell/zshenv.tera").write_text(template)
    (target / "mise.shell-personal.toml").write_text(
        '[dotfiles]\n"~/.zshenv" = { source = "shell/zshenv.tera", mode = "template" }\n'
    )
    (target / "mise.toml").write_text(
        '[vars]\nhost_profile = "personal"\nhost_os = "darwin"\n'
    )
    if ruby_body is not None:
        ruby = homebrew_prefix / "opt/ruby/bin/ruby"
        ruby.parent.mkdir(parents=True)
        ruby.write_text(f"#!/bin/sh\n{ruby_body}\n")
        ruby.chmod(0o755)
    env = isolated_env(home, target)
    env["MISE_ENV"] = "shell-personal"
    return subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_native_template_detects_ruby_and_rustup_and_renders_sourceable_path(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "homebrew"
    rustup = prefix / "opt/rustup/bin/rustup"
    rustup.parent.mkdir(parents=True)
    rustup.write_text("#!/bin/sh\nexit 0\n")
    rustup.chmod(0o755)
    result = render_fixture_zshenv(tmp_path, prefix, ruby_body="printf '3.3.0\\n'")
    assert result.returncode == 0, result.stderr
    rendered = tmp_path / "home/.zshenv"
    sourced = subprocess.run(
        [
            "env",
            "-i",
            f"HOME={tmp_path / 'home'}",
            "zsh",
            "-f",
            "-c",
            'source "$1"; print -rl -- $path',
            "zsh",
            str(rendered),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert str(prefix / "opt/ruby/bin") in sourced
    assert str(prefix / "lib/ruby/gems/3.3.0/bin") in sourced
    assert str(prefix / "opt/rustup/bin") in sourced


def test_native_template_excludes_missing_tools(tmp_path: Path) -> None:
    prefix = tmp_path / "missing-homebrew"
    result = render_fixture_zshenv(tmp_path, prefix, ruby_body=None)
    assert result.returncode == 0, result.stderr
    rendered = (tmp_path / "home/.zshenv").read_text()
    assert str(prefix / "opt/ruby/bin") not in rendered
    assert str(prefix / "opt/rustup/bin") not in rendered


@pytest.mark.parametrize("hook_status", [0, 23])
def test_tmux_clears_mise_environment_and_preserves_arguments(
    tmp_path: Path, hook_status: int
) -> None:
    result = render_fixture_zshenv(tmp_path, tmp_path / "missing", ruby_body=None)
    assert result.returncode == 0, result.stderr
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name, body in {
        "mise": (
            '[ "$*" = "-C / hook-env -s zsh" ] || exit 99\n'
            f"printf 'unset PROJECT_SECRET\\n'\nexit {hook_status}\n"
        ),
        "tmux": 'printf "%s\\n" "${PROJECT_SECRET-unset}" "$@"',
        "direnv": "exit 98",
    }.items():
        executable = binaries / name
        executable.write_text(f"#!/bin/sh\n{body}\n")
        executable.chmod(0o755)
    result = subprocess.run(
        [
            "zsh",
            "-f",
            "-c",
            'source "$1"; path=("$2" $path); export PROJECT_SECRET=fixture; '
            'tmux new-session "two words"; result=$?; '
            'print -r -- "parent=$PROJECT_SECRET"; exit $result',
            "zsh",
            str(tmp_path / "home/.zshenv"),
            str(binaries),
        ],
        env=isolated_env(tmp_path / "home", tmp_path / "target"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == hook_status, result.stderr
    assert result.stdout.splitlines() == (
        ["unset", "new-session", "two words", "parent=fixture"]
        if hook_status == 0
        else ["parent=fixture"]
    )


def test_native_template_fails_when_present_ruby_query_fails(tmp_path: Path) -> None:
    result = render_fixture_zshenv(tmp_path, tmp_path / "homebrew", ruby_body="exit 23")
    assert result.returncode != 0


def test_work_private_file_renders_token_atomically_and_is_noop(tmp_path: Path) -> None:
    if subprocess.run(["sudo", "-n", "true"], check=False).returncode:
        pytest.skip(
            "passwordless sudo is unavailable; cannot exercise root-owned files"
        )

    user = pwd.getpwuid(os.getuid())
    home, target = tmp_path / "home", tmp_path / "target"
    destination = home / ".zshenv"
    home.mkdir()
    target.mkdir()
    (target / "shell").symlink_to(CAPABILITY / "files", target_is_directory=True)
    (target / "mise.shell-work.toml").write_text(
        f'[bootstrap.files."{destination}"]\n'
        'source = "shell/zshenv.tera"\ntemplate = true\n'
        f'owner = "{user.pw_name}"\n'
        f'group = "{grp.getgrgid(user.pw_gid).gr_name}"\nmode = "0600"\n'
    )
    (target / "mise.toml").write_text(
        '[vars]\nhost_profile = "work"\nhost_os = "darwin"\n'
    )
    token = "sgp_synthetic-ABC123456789"
    env = isolated_env(home, target)
    env.update({"MISE_ENV": "shell-work", "SOURCEGRAPH_TOKEN": token})
    command = [
        "mise",
        "-C",
        str(target),
        "bootstrap",
        "--only",
        "files",
        "--yes",
    ]
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    first = destination.stat()
    assert stat.S_IMODE(first.st_mode) == 0o600
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    second = destination.stat()
    assert (
        second.st_ino,
        second.st_mtime_ns,
        second.st_ctime_ns,
        stat.S_IMODE(second.st_mode),
    ) == (first.st_ino, first.st_mtime_ns, first.st_ctime_ns, 0o600)
    result = subprocess.run(
        [
            "env",
            "-i",
            f"HOME={home}",
            "zsh",
            "-f",
            "-c",
            'source "$1"; print -rn -- "$SOURCEGRAPH_TOKEN"',
            "zsh",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == token


@pytest.mark.parametrize("check", [False, True])
def test_work_task_credentials_sudo_and_check_are_scoped(
    tmp_path: Path, check: bool
) -> None:
    task = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["shell"]["run"]
    project, calls = tmp_path / "repo", tmp_path / "calls"
    (project / "scripts").mkdir(parents=True)
    fnox = project / "scripts/fnox-host"
    fnox.write_text(
        "#!/bin/sh\n"
        'printf "fnox %s %s %s %s %s\\n" "$1" "$2" "$3" "$4" "$5" >> "$CALLS"\n'
        'export SOURCEGRAPH_TOKEN="$SYNTHETIC_TOKEN"\n'
        'export HOMEBREW_SUDO_ASKPASS_PASS_WORK="$SYNTHETIC_PASSWORD"\n'
        'while [ "$1" != -- ]; do shift; done; shift\nexec "$@"\n'
    )
    fnox.chmod(0o755)
    for name, body in {
        "hostname": "echo ML-DFC6YK6VJQ",
        "sudo": 'printf "sudo %s\\n" "$*" >> "$CALLS"',
        "mise": 'printf "mise %s env=%s token=%s\\n" "$*" "$MISE_ENV" "$SOURCEGRAPH_TOKEN" >> "$CALLS"',
    }.items():
        path = tmp_path / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)
    result = subprocess.run(
        ["sh", "-ec", task],
        check=True,
        env={
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "CALLS": str(calls),
            "MISE_PROJECT_ROOT": str(project),
            "usage_check": "1" if check else "",
            "SYNTHETIC_TOKEN": "sgp_synthetic-ABC123",
            "SYNTHETIC_PASSWORD": "own password",
        },
        capture_output=True,
        text=True,
    )
    assert "sgp_synthetic-ABC123" not in result.stdout + result.stderr
    assert "own password" not in result.stdout + result.stderr
    lines = calls.read_text().splitlines()
    if check:
        assert lines == [
            f"mise -C {project}/bootstrap/targets/ML-DFC6YK6VJQ bootstrap --only files,dotfiles --force-dotfiles --dry-run env=shell,shell-work token=preview"
        ]
    else:
        assert lines[0] == (
            "fnox exec --secret SOURCEGRAPH_TOKEN --secret "
            "HOMEBREW_SUDO_ASKPASS_PASS_WORK"
        )
        assert lines[1:] == [
            "sudo -A -v",
            f"mise -C {project}/bootstrap/targets/ML-DFC6YK6VJQ bootstrap --only files,dotfiles --force-dotfiles --yes env=shell,shell-work token=sgp_synthetic-ABC123",
        ]
