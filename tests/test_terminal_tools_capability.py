import os
from pathlib import Path
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/terminal-tools"
HOSTS = ("pod042", "Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ")


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
        "MISE_ENV": "terminal-tools,fixture",
    }


@pytest.mark.parametrize(
    "host,platform_manifest,parts,expected_directory,has_ghostty,has_ideo,has_plugins",
    [
        (
            "pod042",
            "mise.terminal-tools-plugins.toml",
            "dotfiles,repos",
            None,
            False,
            False,
            True,
        ),
        (
            "Thurstons-MacBook-Pro",
            "mise.terminal-tools-darwin.toml",
            "dotfiles,repos",
            "/Users/thurstonsand/Develop",
            True,
            True,
            True,
        ),
        (
            "ML-DFC6YK6VJQ",
            "mise.terminal-tools-darwin.toml",
            "dotfiles",
            "/Users/tsandberg/code",
            True,
            False,
            False,
        ),
    ],
)
def test_real_registered_manifests_reconcile_idempotently(
    host: str,
    platform_manifest: str,
    parts: str,
    expected_directory: str | None,
    has_ghostty: bool,
    has_ideo: bool,
    has_plugins: bool,
    tmp_path: Path,
) -> None:
    home, target = tmp_path / "home", tmp_path / "target"
    home.mkdir()
    target.mkdir()
    registered = ROOT / "bootstrap/targets" / host
    (target / "terminal-tools").symlink_to(
        CAPABILITY / "files", target_is_directory=True
    )
    (target / "mise.toml").write_bytes((registered / "mise.toml").read_bytes())
    (target / "mise.terminal-tools.toml").write_bytes(
        (registered / "mise.terminal-tools.toml").read_bytes()
    )
    platform = (registered / platform_manifest).read_text()
    if has_plugins:
        plugin_repo = tmp_path / "tpm-source"
        installer = plugin_repo / "bin/install_plugins"
        installer.parent.mkdir(parents=True)
        installer.write_text('#!/bin/sh\nprintf "called\\n" >> "$HOME/plugin-hook"\n')
        installer.chmod(0o755)
        subprocess.run(["git", "init", "-q", str(plugin_repo)], check=True)
        subprocess.run(["git", "-C", str(plugin_repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(plugin_repo),
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        registered_home = tomllib.loads((registered / "mise.toml").read_text())["vars"][
            "terminal_tools_home"
        ]
        platform = platform.replace(registered_home, str(home)).replace(
            "https://github.com/tmux-plugins/tpm.git", str(plugin_repo)
        )
    (target / platform_manifest).write_text(platform)
    neighbor = home / ".config/tmux/unmanaged.conf"
    neighbor.parent.mkdir(parents=True)
    neighbor.write_text("keep me\n")
    command = [
        "mise",
        "-C",
        str(target),
        "bootstrap",
        "--only",
        parts,
        "--force-dotfiles",
    ]
    env = isolated_env(home, target)
    env["MISE_ENV"] = "terminal-tools," + platform_manifest.removeprefix(
        "mise."
    ).removesuffix(".toml")
    env["MISE_AUTO_INSTALL"] = "0"
    subprocess.run(
        [*command, "--dry-run"], env=env, check=True, capture_output=True, text=True
    )
    assert not (home / ".config/tmux/tmux.conf").exists()
    assert not (home / "plugin-hook").exists()
    assert not (home / ".config/tmux/plugins/tpm").exists()

    subprocess.run(
        [*command, "--yes"], env=env, check=True, capture_output=True, text=True
    )
    ghostty = home / ".config/ghostty/config"
    tmux = home / ".config/tmux/tmux.conf"
    assert tmux.resolve() == CAPABILITY / "files/tmux/tmux.conf"
    assert (home / ".local/bin/ideo").exists() is has_ideo
    if has_ghostty:
        rendered = ghostty.read_text()
        assert "font-family = BerkeleyMono Nerd Font Mono" in rendered
        assert "window-title-font-family = BerkeleyMono Nerd Font Mono Bold" in rendered
        assert "font-size = 13" in rendered
        assert f"working-directory = {expected_directory}" in rendered
    else:
        assert not ghostty.exists()
    assert (home / "plugin-hook").exists() is has_plugins

    managed = [
        tmux,
        home / ".config/tmux/gruvbox-dark.conf",
        home / ".config/tmux/gruvbox-light.conf",
    ]
    if has_ghostty:
        managed += [ghostty, home / ".local/bin/delta", home / ".local/bin/ide"]
    if has_ideo:
        managed.append(home / ".local/bin/ideo")

    def snapshot(path: Path) -> tuple[int, int, int, bytes]:
        stat = path.lstat()
        content = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
        return stat.st_mode, stat.st_ino, stat.st_mtime_ns, content

    before = {path: snapshot(path) for path in managed}
    subprocess.run(
        [*command, "--dry-run"], env=env, check=True, capture_output=True, text=True
    )
    assert {path: snapshot(path) for path in managed} == before
    subprocess.run(
        [*command, "--yes"], env=env, check=True, capture_output=True, text=True
    )
    assert {path: snapshot(path) for path in managed} == before
    assert neighbor.read_text() == "keep me\n"
