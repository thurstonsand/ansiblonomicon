from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

import pytest

TARGET = Path(__file__).resolve().parents[1] / "bootstrap/targets/type-a-no2"
RECONCILER = TARGET / "reconcile_loadout.py"

FAKE_OMARCHY = """\
#!/usr/bin/env python3
import json, os, shutil, subprocess, sys
from pathlib import Path

with open(os.environ["OMARCHY_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
state = Path(os.environ["OMARCHY_STATE"])
themes = Path.home() / ".config/omarchy/themes"

def commit(checkout):
    subprocess.run(
        ["git", "-C", str(checkout), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-q", "--allow-empty", "-m", "release"],
        check=True,
    )

plugins = Path.home() / ".config/omarchy/plugins"
match sys.argv[1:]:
    case ["pkg", "present", name]:
        sys.exit(0 if name in state.read_text().split() else 1)
    case ["pkg", "add", *names] | ["pkg", "aur", "add", *names]:
        state.write_text(state.read_text() + "".join(f"{n}\\n" for n in names))
    case ["pkg", "drop", *names]:
        state.write_text("".join(f"{n}\\n" for n in state.read_text().split() if n not in names))
    case ["theme", "install", url]:
        name = url.rsplit("/", 1)[-1].removesuffix(".git").removeprefix("omarchy-").removesuffix("-theme")
        (themes / name).mkdir(parents=True)
    case ["theme", "remove", name]:
        (themes / name).rmdir()
    case ["plugin", "add", "--yes", url]:
        ids = json.loads(os.environ.get("FAKE_PLUGIN_IDS", "{}"))
        checkout = plugins / ids.get(url, url.rsplit("/", 1)[-1].removesuffix(".git"))
        checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
        commit(checkout)
    case ["plugin", "remove", "--yes", plugin_id]:
        shutil.rmtree(plugins / plugin_id)
    case ["plugin", "catalog"]:
        user = [{"id": p.name, "sourceDir": str(p)} for p in plugins.iterdir()] if plugins.exists() else []
        builtin = [{"id": "omarchy.clock", "sourceDir": "/usr/share/omarchy/shell/plugins/clock"}]
        print(json.dumps(builtin + user))
    case _:
        sys.exit(2)
"""


@pytest.fixture
def omarchy(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    command = bin_dir / "omarchy"
    command.write_text(FAKE_OMARCHY)
    command.chmod(0o755)
    pacman = bin_dir / "pacman"
    pacman.write_text('#!/bin/sh\n[ "$1" = -Qqe ] && cat "$OMARCHY_STATE"\n')
    pacman.chmod(0o755)
    omarchy_path = tmp_path / "omarchy"
    (omarchy_path / "install").mkdir(parents=True)
    (omarchy_path / "install/omarchy-base.packages").write_text(
        "# Omarchy core packages\n\nomarchy-core\n"
    )
    pacman_log = tmp_path / "pacman.log"
    pacman_log.write_text(
        "[2026-09-04T06:13:27+0000] [PACMAN] Running 'pacman -r /mnt -Sy --needed base linux-ptl'\n"
        "[2026-09-04T06:13:28+0000] [ALPM] installed linux-ptl (7.2-1)\n"
        "[2026-09-22T19:01:24-0400] [PACMAN] Running 'pacman -S --noconfirm --needed 1password'\n"
    )
    install_log = tmp_path / "omarchy-install.log"
    install_log.write_text("User finalization complete.\n")
    finished = datetime(2026, 9, 4, 6, 14, tzinfo=UTC).timestamp()
    os.utime(install_log, (finished, finished))
    home = tmp_path / "home"
    home.mkdir()
    state = tmp_path / "installed"
    state.write_text("direnv\nomarchy-core\n")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(home),
        "OMARCHY_PATH": str(omarchy_path),
        "OMARCHY_LOG": str(tmp_path / "calls"),
        "OMARCHY_STATE": str(state),
        "PACMAN_LOG": str(pacman_log),
        "INSTALL_LOG": str(install_log),
    }
    return env, state


def run(
    manifest: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    logs = ["--pacman-log", env["PACMAN_LOG"], "--install-log", env["INSTALL_LOG"]]
    return subprocess.run(
        [sys.executable, str(RECONCILER), str(manifest), *logs, *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def calls(env: dict[str, str]) -> list[str]:
    log = Path(env["OMARCHY_LOG"])
    return log.read_text().splitlines() if log.exists() else []


def plugin_home(env: dict[str, str], plugin_id: str) -> Path:
    return Path(env["HOME"]) / ".config/omarchy/plugins" / plugin_id


def release(checkout: Path) -> None:
    subprocess.run(
        [
            *("git", "-C", str(checkout), "-c", "user.name=t", "-c", "user.email=t@t"),
            *("commit", "-q", "--allow-empty", "-m", "release"),
        ],
        check=True,
    )


def test_production_manifest_preview_apply_and_converge(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path]
) -> None:
    env, state = omarchy
    manifest = TARGET / "loadout.toml"
    declared = tomllib.loads(manifest.read_text())
    env["FAKE_PLUGIN_IDS"] = json.dumps(
        {
            plugin["source"]: plugin_id
            for plugin_id, plugin in declared["plugins"].items()
        }
    )
    with_setup = [
        plugin_id
        for plugin_id, plugin in declared["plugins"].items()
        if "setup" in plugin
    ]
    missing = [
        name
        for name, state in declared["packages"].items()
        if state == "present" and name != "direnv"
    ]
    preview = run(manifest, env, "--check")
    assert preview.returncode == 0, preview.stderr
    assert preview.stdout.splitlines() == [
        f"omarchy pkg add {' '.join(missing)}",
        f"omarchy pkg aur add {' '.join(declared['aur'])}",
        *(
            f"omarchy theme install {theme['source']}"
            for theme in declared["themes"].values()
        ),
        *(
            f"omarchy plugin add --yes {plugin['source']}"
            for plugin in declared["plugins"].values()
        ),
        *(f"setup {plugin_id}" for plugin_id in with_setup),
    ]
    assert state.read_text() == "direnv\nomarchy-core\n"
    assert not any(" add " in call or "install" in call for call in calls(env))

    # The real setup commands build and install system software, so apply swaps them
    # for a marker that proves each one ran inside its plugin's checkout.
    harmless = tmp_path / "loadout.toml"
    harmless.write_text(
        re.sub(
            r"setup = (\"[^\"]*\"|'''.*?''')",
            'setup = "touch setup-ran"',
            manifest.read_text(),
            flags=re.DOTALL,
        )
    )
    applied = run(harmless, env)
    assert applied.returncode == 0, applied.stderr
    for plugin_id in with_setup:
        assert (plugin_home(env, plugin_id) / "setup-ran").is_file()
    repeated = run(harmless, env, "--check")
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout == ""


def test_explicit_absence_only_removes_named_installs(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path]
) -> None:
    env, state = omarchy
    state.write_text("direnv\nold-tool\nold-aur-bin\nomarchy-core\n")
    home = Path(env["HOME"])
    for path in ("themes/old-theme", "themes/kept", "plugins/old.plugin"):
        (home / ".config/omarchy" / path).mkdir(parents=True)
    manifest = tmp_path / "loadout.toml"
    manifest.write_text(
        '[packages]\ndirenv = "present"\nold-tool = "absent"\n'
        '[aur]\nold-aur-bin = "absent"\n'
        '[themes]\nold-theme = { state = "absent" }\n'
        '[plugins]\n"old.plugin" = { state = "absent" }\n'
    )

    preview = run(manifest, env, "--check")
    assert preview.returncode == 0, preview.stderr
    assert preview.stdout.splitlines() == [
        "omarchy pkg drop old-tool old-aur-bin",
        "omarchy theme remove old-theme",
        "omarchy plugin remove --yes old.plugin",
        "undeclared theme: kept",
    ]
    applied = run(manifest, env)
    assert applied.returncode == 0, applied.stderr
    assert state.read_text() == "direnv\nomarchy-core\n"
    assert sorted(p.name for p in (home / ".config/omarchy/themes").iterdir()) == [
        "kept"
    ]
    assert not (home / ".config/omarchy/plugins/old.plugin").exists()


def test_check_reports_undeclared_installs_beyond_omarchy_lists_and_installer(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path]
) -> None:
    env, state = omarchy
    state.write_text("direnv\nomarchy-core\nlinux-ptl\n1password\nopenwhispr-bin\n")
    home = Path(env["HOME"])
    (home / ".config/omarchy/themes/hand-made").mkdir(parents=True)
    (home / ".config/omarchy/plugins/stray").mkdir(parents=True)
    manifest = tmp_path / "loadout.toml"
    manifest.write_text(
        '[packages]\ndirenv = "present"\n[aur]\nopenwhispr-bin = "present"\n'
    )

    preview = run(manifest, env, "--check")
    assert preview.returncode == 0, preview.stderr
    assert preview.stdout.splitlines() == [
        "undeclared package: 1password",
        "undeclared theme: hand-made",
        "undeclared plugin: stray",
    ]
    applied = run(manifest, env)
    assert applied.returncode == 0, applied.stderr
    assert applied.stdout == ""


def test_declaration_keyed_differently_from_omarchy_fails_after_install(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path]
) -> None:
    env, _ = omarchy
    manifest = tmp_path / "loadout.toml"
    manifest.write_text(
        '[themes]\nmochi = { source = "https://example.com/omarchy-sakura-mochi-theme.git" }\n'
    )
    result = run(manifest, env)
    assert result.returncode != 0
    assert "theme mochi" in result.stderr


def test_plugin_setup_reruns_only_for_a_new_commit_or_command(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path]
) -> None:
    env, _ = omarchy
    manifest = tmp_path / "loadout.toml"
    url = "https://example.com/pods.git"
    env["FAKE_PLUGIN_IDS"] = json.dumps({url: "x.pods"})

    def declare(setup: str) -> None:
        manifest.write_text(
            f'[packages]\ndirenv = "present"\n[plugins]\n"x.pods" = {{ source = "{url}", setup = "{setup}" }}\n'
        )

    ran = plugin_home(env, "x.pods") / "ran"
    declare("echo v1 >> ran")

    assert run(manifest, env, "--check").stdout.splitlines() == [
        f"omarchy plugin add --yes {url}",
        "setup x.pods",
    ]
    assert run(manifest, env).returncode == 0
    assert ran.read_text() == "v1\n"
    assert run(manifest, env, "--check").stdout == ""
    assert run(manifest, env).returncode == 0
    assert ran.read_text() == "v1\n"

    release(plugin_home(env, "x.pods"))
    assert run(manifest, env, "--check").stdout == "setup x.pods\n"
    assert run(manifest, env).returncode == 0
    assert ran.read_text() == "v1\nv1\n"

    declare("echo v2 >> ran")
    assert run(manifest, env).returncode == 0
    assert ran.read_text() == "v1\nv1\nv2\n"
    assert run(manifest, env, "--check").stdout == ""

    manifest.write_text(
        '[packages]\ndirenv = "present"\n[plugins]\n"x.pods" = { state = "absent" }\n'
    )
    stamp = Path(env["HOME"]) / ".local/state/omarchy-loadout/plugin-setup/x.pods"
    assert stamp.is_file()
    assert run(manifest, env).returncode == 0
    assert not stamp.exists()


def test_failed_plugin_setup_is_retried(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path]
) -> None:
    env, _ = omarchy
    manifest = tmp_path / "loadout.toml"
    manifest.write_text(
        '[packages]\ndirenv = "present"\n'
        '[plugins]\n"x.pods" = { source = "https://example.com/x.pods.git", setup = "false" }\n'
    )
    assert run(manifest, env).returncode != 0
    assert run(manifest, env, "--check").stdout == "setup x.pods\n"


@pytest.mark.parametrize(
    "declaration",
    [
        '[packages]\n"bad/name" = "present"\n',
        '[packages]\ndirenv = "newest"\n',
        '[aur]\nopenwhispr-bin = "latest"\n',
        '[themes]\nmochi = "present"\n',
        '[themes]\nmochi = { source = "https://example.com/x.git", ref = "main" }\n',
        '[plugins]\n"../escape" = { state = "absent" }\n',
        '[plugins]\npods = { source = "https://example.com/pods.git", setup = 1 }\n',
        '[plugins]\npods = { state = "absent", setup = "./setup" }\n',
        '[fonts]\nberkeley = "present"\n',
    ],
)
def test_invalid_manifest_fails_before_calling_omarchy(
    tmp_path: Path, omarchy: tuple[dict[str, str], Path], declaration: str
) -> None:
    env, _ = omarchy
    manifest = tmp_path / "loadout.toml"
    manifest.write_text(declaration)
    result = run(manifest, env)
    assert result.returncode != 0
    assert calls(env) == []
