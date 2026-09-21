import os
from pathlib import Path
import shutil
import stat
import subprocess
import tomllib

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/user-tools"
MISE = shutil.which("mise")
assert MISE is not None


def isolated_env(home: Path, target: Path, path: str) -> dict[str, str]:
    return {
        "PATH": path,
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


def fixture(
    tmp_path: Path,
    *,
    personal: bool,
    commands: tuple[str, ...],
    services: str | None = None,
) -> tuple[Path, Path, dict[str, str], list[str]]:
    home, target, binaries = (
        tmp_path / "home",
        tmp_path / "checkout with spaces/target",
        tmp_path / "bin",
    )
    home.mkdir()
    target.mkdir(parents=True)
    binaries.mkdir()
    (binaries / "sh").symlink_to("/bin/sh")
    for command in commands:
        executable = binaries / command
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    (target / "user-tools").symlink_to(CAPABILITY / "files", target_is_directory=True)
    (target / "mise.user-tools.toml").symlink_to(CAPABILITY / "mise.toml")
    environments = ["user-tools"]
    if personal:
        (target / "mise.user-tools-personal.toml").symlink_to(
            CAPABILITY / "mise.personal.toml"
        )
        environments.append("user-tools-personal")
    (target / "mise.toml").write_text(
        "[vars]\n"
        'lazygit_services = ""\n'
        'rustup_default_toolchain = "stable-x86_64-unknown-linux-gnu"\n'
    )
    if services is not None:
        (target / "mise.local.toml").write_text(
            "[vars]\nlazygit_services = '''\n" + services + "'''\n"
        )
    env = isolated_env(home, target, str(binaries))
    env["MISE_ENV"] = ",".join(environments)
    assert MISE is not None
    command = [
        MISE,
        "-C",
        str(target),
        "bootstrap",
        "--only",
        "dotfiles",
        "--yes",
    ]
    return home, target, env, command


@pytest.mark.parametrize(
    ("commands", "expected"),
    [
        (("hunk", "delta"), "hunk pager"),
        (("delta",), "delta --paging=never"),
        ((), None),
    ],
)
def test_real_mise_renders_discovered_renderer_and_native_services(
    tmp_path: Path, commands: tuple[str, ...], expected: str | None
) -> None:
    services = (
        '  "gitlab.internal.example:8443/group/subgroup": '
        '"gitlab:gitlab.internal.example:8443/group/subgroup"\n'
        '  "stash.example.com:7999/projects/tools/repos/agent": '
        '"bitbucketServer:stash.example.com:7999/projects/tools/repos/agent"\n'
    )
    home, _, env, command = fixture(
        tmp_path, personal=False, commands=commands, services=services
    )
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    rendered = (home / ".config/lazygit/config.yml").read_text()
    config = yaml.safe_load(rendered)
    assert config["os"] == {"editPreset": "vscode"}
    if expected is None:
        assert "diffRenderers" not in config["git"]
    else:
        assert config["git"]["diffRenderers"] == [
            {"command": expected, "colorArg": "always"}
        ]
    assert "services:\n" + services in rendered
    assert config["services"] == {
        "gitlab.internal.example:8443/group/subgroup": (
            "gitlab:gitlab.internal.example:8443/group/subgroup"
        ),
        "stash.example.com:7999/projects/tools/repos/agent": (
            "bitbucketServer:stash.example.com:7999/projects/tools/repos/agent"
        ),
    }


def test_real_mise_rediscovers_renderer_when_path_changes(tmp_path: Path) -> None:
    home, _, env, command = fixture(tmp_path, personal=False, commands=())
    delta_bin = tmp_path / "delta-bin"
    hunk_bin = tmp_path / "hunk-bin"
    delta_bin.mkdir()
    hunk_bin.mkdir()
    for directory, name in ((delta_bin, "delta"), (hunk_bin, "hunk")):
        executable = directory / name
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)

    config_path = home / ".config/lazygit/config.yml"
    for path, expected in (
        (env["PATH"], None),
        (f"{delta_bin}:{env['PATH']}", "delta --paging=never"),
        (f"{hunk_bin}:{delta_bin}:{env['PATH']}", "hunk pager"),
    ):
        subprocess.run(
            [*command[:-1], "--force-dotfiles", command[-1]],
            env={**env, "PATH": path},
            check=True,
            capture_output=True,
            text=True,
        )
        rendered = yaml.safe_load(config_path.read_text())
        if expected is None:
            assert "diffRenderers" not in rendered["git"]
        else:
            assert rendered["git"]["diffRenderers"] == [
                {"command": expected, "colorArg": "always"}
            ]


def test_real_mise_check_apply_and_repeat_preserve_outputs(tmp_path: Path) -> None:
    home, _, env, command = fixture(tmp_path, personal=True, commands=())
    preview = subprocess.run(
        [*command[:-1], "--dry-run"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "lazygit" in preview.stdout + preview.stderr
    assert not (home / ".config/lazygit/config.yml").exists()

    force_command = [*command[:-1], "--force-dotfiles", command[-1]]
    subprocess.run(force_command, env=env, check=True, capture_output=True, text=True)
    assert (home / ".config/gh/config.yml").read_text() == (
        'aliases: {}\ngit_protocol: ssh\nversion: "1"\n'
    )
    assert (home / ".rustup/settings.toml").read_text() == (
        'version = "12"\n'
        'default_toolchain = "stable-x86_64-unknown-linux-gnu"\n'
        "[overrides]\n"
    )
    assert (
        yaml.safe_load((home / ".config/lazygit/config.yml").read_text())[
            "promptToReturnFromSubprocess"
        ]
        is False
    )
    gh_path = home / ".config/gh/config.yml"
    rustup_path = home / ".rustup/settings.toml"
    assert not gh_path.is_symlink()
    assert not rustup_path.is_symlink()
    gh_path.write_text("mutated gh\n")
    rustup_path.write_text("mutated rustup\n")
    assert (CAPABILITY / "files/gh.yml").read_text() != "mutated gh\n"
    assert (CAPABILITY / "files/rustup-settings.toml.tera").read_text() != (
        "mutated rustup\n"
    )
    subprocess.run(force_command, env=env, check=True, capture_output=True, text=True)
    assert gh_path.read_text() == 'aliases: {}\ngit_protocol: ssh\nversion: "1"\n'
    assert rustup_path.read_text().startswith('version = "12"\n')

    paths = [
        home / ".config/lazygit/config.yml",
        home / ".config/gh/config.yml",
        home / ".rustup/settings.toml",
        home / ".local/libexec/tab-title.py",
        home / ".local/libexec/hunk/nvim",
    ]
    before = [
        (p.lstat().st_ino, p.lstat().st_mtime_ns, stat.S_IMODE(p.stat().st_mode))
        for p in paths
    ]
    subprocess.run(force_command, env=env, check=True, capture_output=True, text=True)
    after = [
        (p.lstat().st_ino, p.lstat().st_mtime_ns, stat.S_IMODE(p.stat().st_mode))
        for p in paths
    ]
    assert after == before
    assert stat.S_IMODE((home / ".local/libexec/tab-title.py").stat().st_mode) == 0o755
    assert stat.S_IMODE((home / ".local/libexec/hunk/nvim").stat().st_mode) == 0o755
    assert (home / ".local/bin/fnox-host").resolve() == (ROOT / "scripts/fnox-host")
    assert (home / ".local/bin/mcp-credentials").resolve() == (
        ROOT / "scripts/mcp_credentials.py"
    )
    title = subprocess.run(
        [str(home / ".local/libexec/tab-title.py"), "--nvim", str(tmp_path)],
        env={**env, "PATH": os.environ["PATH"]},
        check=True,
        capture_output=True,
        text=True,
    )
    assert title.stdout == f"nvim:{tmp_path.name}\n"
    hunk = subprocess.run(
        [str(home / ".local/libexec/hunk/nvim"), "file"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert hunk.returncode == 2
    assert hunk.stderr == "hunk nvim editor: NVIM_OUTER_SERVER is not set\n"


def test_common_only_apply_preserves_existing_personal_files(tmp_path: Path) -> None:
    home, _, env, command = fixture(tmp_path, personal=False, commands=())
    gh = home / ".config/gh/config.yml"
    rustup = home / ".rustup/settings.toml"
    gh.parent.mkdir(parents=True)
    rustup.parent.mkdir(parents=True)
    gh.write_text("work gh content\n")
    rustup.write_text("work rustup content\n")

    subprocess.run(
        [*command[:-1], "--force-dotfiles", command[-1]],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert gh.read_text() == "work gh content\n"
    assert rustup.read_text() == "work rustup content\n"


def test_registered_hosts_share_capability_and_only_personal_hosts_extend_it() -> None:
    for host in ("pod042", "Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ"):
        target = ROOT / "bootstrap/targets" / host
        assert (target / "user-tools").resolve() == (CAPABILITY / "files").resolve()
        assert (target / "mise.user-tools.toml").resolve() == (
            CAPABILITY / "mise.toml"
        ).resolve()
        personal = target / "mise.user-tools-personal.toml"
        assert personal.exists() is (host != "ML-DFC6YK6VJQ")
        values = tomllib.loads((target / "mise.toml").read_text())["vars"]
        assert values["lazygit_services"] == ""
        assert ("rustup_default_toolchain" in values) is (host != "ML-DFC6YK6VJQ")
