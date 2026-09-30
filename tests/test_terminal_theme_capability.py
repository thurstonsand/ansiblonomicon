import os
from pathlib import Path
import stat
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/terminal-theme"
HOSTS = {
    "pod042": ("mirror", "", "/home/thurstonsand"),
    "Thurstons-MacBook-Pro": ("detector", "pod042", "/Users/thurstonsand"),
    "ML-DFC6YK6VJQ": ("detector", "", "/Users/tsandberg"),
}


def test_three_hosts_include_shared_capability_with_host_behavior() -> None:
    shared = (CAPABILITY / "mise.toml").resolve()
    for host, (profile, mirrors, home) in HOSTS.items():
        target = ROOT / "bootstrap/targets" / host
        assert (target / "mise.terminal-theme.toml").is_symlink()
        assert (target / "mise.terminal-theme.toml").resolve() == shared
        assert (target / "terminal-theme").is_symlink()
        assert (target / "terminal-theme").resolve() == (CAPABILITY / "files").resolve()
        config = tomllib.loads((target / "mise.toml").read_text())
        assert {
            key: config["vars"][key]
            for key in (
                "terminal_theme_home",
                "terminal_theme_profile",
                "terminal_theme_mirrors",
            )
        } == {
            "terminal_theme_home": home,
            "terminal_theme_profile": profile,
            "terminal_theme_mirrors": mirrors,
        }
        if host != "pod042":
            macos = target / "mise.terminal-theme-macos.toml"
            assert macos.is_symlink()
            assert macos.resolve() == (CAPABILITY / "mise.macos.toml").resolve()


def isolated_mise_env(home: Path, config: Path) -> dict[str, str]:
    uv = Path(subprocess.check_output(["mise", "which", "uv"], text=True).strip())
    return {
        "HOME": str(home),
        "PATH": f"{uv.parent}:{os.environ['PATH']}",
        "UV_PYTHON": sys.executable,
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_OFFLINE": "true",
        "USER": os.environ.get("USER", "thurstonsand"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "MISE_CACHE_DIR": str(home / ".cache/mise"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_DATA_DIR": str(home / ".local/share/mise"),
        "MISE_STATE_DIR": str(home / ".local/state/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(config / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(config / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(config.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(config),
    }


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_native_hunk_palette_matches_shared_asset_and_detects_drift(
    tmp_path: Path, mode: str
) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config"
    home.mkdir()
    config.mkdir()
    (home / ".terminal-bg").write_text(mode + "\n")
    (config / "terminal-theme").symlink_to(
        CAPABILITY / "files", target_is_directory=True
    )
    (config / "mise.terminal-theme.toml").symlink_to(CAPABILITY / "mise.toml")
    (config / "mise.toml").write_text(
        f'''[vars]\nterminal_theme_home = "{home}"\nterminal_theme_profile = "mirror"\n'''
    )
    env = isolated_mise_env(home, config)
    env["MISE_ENV"] = "terminal-theme"
    command = ["mise", "-C", str(config), "bootstrap", "--only", "dotfiles", "--yes"]

    applied = subprocess.run(
        command, env=env, check=False, capture_output=True, text=True
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    hunk = home / ".config/hunk/config.toml"
    first = hunk.stat().st_mtime_ns
    assert not hunk.is_symlink()
    rendered_theme = tomllib.loads(hunk.read_text())["custom_theme"]
    palette = tomllib.loads(
        (CAPABILITY / f"files/hunk-gruvbox-{mode}.toml").read_text()
    )["custom_theme"]
    assert rendered_theme == palette

    noop = subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert hunk.stat().st_mtime_ns == first
    assert "all files are applied" in (noop.stdout + noop.stderr).lower()

    rendered = hunk.read_text()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    tmux = fake_bin / "tmux"
    tmux.write_text("#!/bin/sh\nexit 0\n")
    tmux.chmod(0o755)
    for runtime_mode in (mode, "dark" if mode == "light" else "light", mode):
        subprocess.run(
            [
                sys.executable,
                str(CAPABILITY / "files/terminal-theme-switch.py"),
                "--no-mirror-sync",
                runtime_mode,
            ],
            env={**env, "PATH": f"{fake_bin}:{env['PATH']}"},
            check=True,
        )
    assert hunk.read_text() == rendered
    after_runtime = hunk.stat().st_mtime_ns
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert hunk.stat().st_mtime_ns == after_runtime

    hunk.write_text('theme = "drift"\n')
    preview = subprocess.run(
        [*command[:-1], "--dry-run"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert hunk.read_text() == 'theme = "drift"\n'
    preview_output = (preview.stdout + preview.stderr).lower()
    assert "pre-dotfiles" in preview_output
    assert "config.toml" in preview_output

    status = subprocess.run(
        ["mise", "-C", str(config), "bootstrap", "dotfiles", "status"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert "config.toml" in status.stdout, status.stdout + status.stderr
    assert "modified" in status.stdout.lower() or "differs" in status.stdout.lower()
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert tomllib.loads(hunk.read_text())["theme"] == "custom"


@pytest.mark.parametrize(
    ("terminal_home", "mirrors"),
    [("/Users/thurstonsand", "pod042"), ("/Users/tsandberg", "")],
)
def test_native_ssh_include_enforces_0644_from_0600_source(
    tmp_path: Path, terminal_home: str, mirrors: str
) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config"
    home.mkdir()
    config.mkdir()
    source = config / "terminal-theme-ssh.conf.tera"
    source.write_text((CAPABILITY / "files/terminal-theme-ssh.conf.tera").read_text())
    source.chmod(0o600)
    target = home / ".ssh/config.d/terminal-theme.conf"
    (config / "mise.toml").write_text(
        f'''[vars]\nterminal_theme_home = "{terminal_home}"\nterminal_theme_mirrors = "{mirrors}"\n'''
        f'''[bootstrap.directories."{target.parent}"]\nmode = "0700"\n'''
        f'''[bootstrap.files."{target}"]\nsource = "terminal-theme-ssh.conf.tera"\n'''
        """template = true\nmode = "0644"\n"""
    )
    env = isolated_mise_env(home, config)
    subprocess.run(
        ["mise", "-C", str(config), "bootstrap", "files", "apply", "--yes"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert stat.S_IMODE(source.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    rendered = target.read_text()
    assert rendered.startswith("# Managed by mise.")
    if mirrors:
        assert "Host pod042" in rendered
        assert terminal_home + "/.local/bin/terminal-theme-ssh-lease.py" in rendered
    else:
        assert "Host " not in rendered
