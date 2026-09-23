import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/editor-config"
PYTHON = ROOT / ".venv/bin/python"
PERSONAL_FILES = {
    ".config/zed/settings.json": None,
    ".config/zed/keymap.json": 0o644,
    ".config/zed/tasks.json": 0o644,
    "Library/Application Support/Cursor/User/settings.json": None,
    "Library/Application Support/Cursor/User/keybindings.json": 0o644,
    "Library/Application Support/Windsurf/User/settings.json": None,
    "Library/Application Support/Windsurf/User/keybindings.json": 0o644,
    "Library/Application Support/Antigravity/User/settings.json": None,
    "Library/Application Support/Antigravity/User/keybindings.json": 0o644,
    "Library/Application Support/io.datasette.llm/keys.json": 0o600,
    "Library/Application Support/io.datasette.llm/extra-openai-models.yaml": 0o600,
    "Library/Application Support/io.datasette.llm/default_model.txt": 0o644,
}
FAKE_SECRET_NAMES = (
    "CLI_PROXY_API_KEY",
    "CF_ACCESS_CLIENT_ID",
    "CF_ACCESS_CLIENT_SECRET",
)


def renderer_args(kind: str, *, models: Path, profile: str = "personal") -> list[str]:
    return [
        str(PYTHON),
        str(CAPABILITY / "render.py"),
        kind,
        f"--models={models}",
        f"--profile={profile}",
        "--monospace-font=m",
        "--proportional-font=p",
        "--font-size=13",
        "--go-local-imports=",
        "--gopls-build-flags=",
    ]


def prepare_target(tmp_path: Path, profile: str) -> tuple[Path, Path]:
    host = "Thurstons-MacBook-Pro" if profile == "personal" else "ML-DFC6YK6VJQ"
    target = tmp_path / "target"
    home = tmp_path / "home with spaces"
    if target.exists():
        return target, home
    target.mkdir(parents=True)
    shutil.copy(ROOT / f"bootstrap/targets/{host}/mise.toml", target / "mise.toml")
    shutil.copy(
        ROOT / f"bootstrap/targets/{host}/mise.editor-config.toml",
        target / "mise.editor-config.toml",
    )
    (target / "editor-config").symlink_to(CAPABILITY, target_is_directory=True)
    (target / "mise.local.toml").write_text(
        """[vars]
editor_monospace_font = "Asymmetric Mono \\"quoted\\"\\nsecond line"
editor_proportional_font = "Distinct Proportional"
editor_font_size = "17"
go_local_imports = "example.net/private\\nexample.net/secondary"
gopls_build_flags = "-tags=asymmetric\\n-race"
"""
    )
    for relative in PERSONAL_FILES:
        (home / relative).parent.mkdir(parents=True, exist_ok=True)
    return target, home


def run_native(
    tmp_path: Path,
    profile: str,
    *,
    secrets: bool = True,
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    target, home = prepare_target(tmp_path, profile)
    environment = {
        **os.environ,
        "HOME": str(home),
        "MISE_CEILING_PATHS": str(tmp_path),
        "MISE_TRUSTED_CONFIG_PATHS": str(tmp_path),
        "EDITOR_CONFIG_PYTHON": str(PYTHON),
        "EDITOR_CONFIG_RENDERER": str(CAPABILITY / "render.py"),
        "EDITOR_CONFIG_MODELS": str(ROOT / "ansible/models.yml"),
    }
    for name in FAKE_SECRET_NAMES:
        environment.pop(name, None)
    if secrets:
        environment.update(
            {
                "CLI_PROXY_API_KEY": 'key "quote"\nsecond line',
                "CF_ACCESS_CLIENT_ID": "__EDITOR_CONFIG_CF_CLIENT_SECRET__",
                "CF_ACCESS_CLIENT_SECRET": 'secret "quote"\nsecond line',
            }
        )
    result = subprocess.run(
        [
            "mise",
            "-E",
            "editor-config",
            "-C",
            str(target),
            "bootstrap",
            "--only",
            "files,dotfiles",
            "--force-dotfiles",
            "--yes",
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    return home, result


def metadata(
    home: Path, expected: dict[str, int | None]
) -> list[tuple[str, int, int, int, int, int]]:
    values: list[tuple[str, int, int, int, int, int]] = []
    for relative, mode in expected.items():
        path = home / relative
        info = path.stat()
        assert stat.S_ISREG(info.st_mode)
        if mode is not None:
            assert stat.S_IMODE(info.st_mode) == mode
        assert info.st_uid == os.getuid()
        assert info.st_gid == os.getgid()
        values.append(
            (
                relative,
                info.st_ino,
                info.st_mtime_ns,
                info.st_mode,
                info.st_uid,
                info.st_gid,
            )
        )
    return values


def test_personal_native_manifest_modes_scalars_secrets_and_idempotence(
    tmp_path: Path,
) -> None:
    sources = list((CAPABILITY / "files").rglob("*"))
    source_metadata = {
        path: (
            path.stat().st_ino,
            path.stat().st_size,
            path.stat().st_mtime_ns,
            path.stat().st_mode,
            path.stat().st_uid,
            path.stat().st_gid,
        )
        for path in sources
        if path.is_file()
    }
    assert {stat.S_IMODE(value[3]) for value in source_metadata.values()} == {0o644}
    home, result = run_native(tmp_path, "personal")
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    for sensitive in (
        'key "quote"\nsecond line',
        'secret "quote"\nsecond line',
        'key \\"quote\\"\\nsecond line',
        'secret \\"quote\\"\\nsecond line',
        "__EDITOR_CONFIG_CF_CLIENT_SECRET__",
    ):
        assert sensitive not in combined
    before = metadata(home, PERSONAL_FILES)
    zed = json.loads((home / ".config/zed/settings.json").read_text())
    assert zed["buffer_font_family"] == 'Asymmetric Mono "quoted"\nsecond line'
    assert zed["ui_font_family"] == "Distinct Proportional"
    cursor = json.loads(
        (home / "Library/Application Support/Cursor/User/settings.json").read_text()
    )
    assert cursor["editor.fontFamily"] == "Distinct Proportional"
    assert cursor["terminal.integrated.fontFamily"] == (
        'Asymmetric Mono "quoted"\nsecond line'
    )
    assert cursor["gopls"]["local"] == "example.net/private\nexample.net/secondary"
    assert cursor["gopls"]["buildFlags"] == ["-tags=asymmetric\n-race"]
    assert cursor["go.formatFlags"] == [
        "-local",
        "example.net/private\nexample.net/secondary",
    ]
    keys = json.loads(
        (home / "Library/Application Support/io.datasette.llm/keys.json").read_text()
    )
    assert keys["// Note"] == "This file stores secret API credentials. Do not share!"
    assert keys["llm-api-key"] == 'key "quote"\nsecond line'
    models_path = home / (
        "Library/Application Support/io.datasette.llm/extra-openai-models.yaml"
    )
    models_text = models_path.read_text()
    models = cast(list[dict[str, object]], yaml.safe_load(models_text))
    assert all(
        model["headers"]
        == {
            "CF-Access-Client-Id": "__EDITOR_CONFIG_CF_CLIENT_SECRET__",
            "CF-Access-Client-Secret": 'secret "quote"\nsecond line',
        }
        for model in models
    )
    before_content = {
        relative: hashlib.sha256((home / relative).read_bytes()).hexdigest()
        for relative in PERSONAL_FILES
    }
    _, repeated = run_native(tmp_path, "personal")
    assert repeated.returncode == 0, repeated.stderr
    assert metadata(home, PERSONAL_FILES) == before
    assert {
        relative: hashlib.sha256((home / relative).read_bytes()).hexdigest()
        for relative in PERSONAL_FILES
    } == before_content
    assert {
        path: (
            path.stat().st_ino,
            path.stat().st_size,
            path.stat().st_mtime_ns,
            path.stat().st_mode,
            path.stat().st_uid,
            path.stat().st_gid,
        )
        for path in source_metadata
    } == source_metadata


def test_work_needs_no_secrets_and_preserves_excluded_apps(tmp_path: Path) -> None:
    target, home = prepare_target(tmp_path, "work")
    excluded = home / "Library/Application Support/Cursor/User/settings.json"
    excluded.write_text("seeded work app\n")
    environment = {
        **os.environ,
        "HOME": str(home),
        "MISE_CEILING_PATHS": str(tmp_path),
        "MISE_TRUSTED_CONFIG_PATHS": str(tmp_path),
        "EDITOR_CONFIG_PYTHON": str(PYTHON),
        "EDITOR_CONFIG_RENDERER": str(CAPABILITY / "render.py"),
        "EDITOR_CONFIG_MODELS": str(ROOT / "ansible/models.yml"),
    }
    for name in FAKE_SECRET_NAMES:
        environment.pop(name, None)
    result = subprocess.run(
        [
            "mise",
            "-E",
            "editor-config",
            "-C",
            str(target),
            "bootstrap",
            "--only",
            "files,dotfiles",
            "--force-dotfiles",
            "--yes",
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    metadata(home, {key: PERSONAL_FILES[key] for key in list(PERSONAL_FILES)[:3]})
    zed = json.loads((home / ".config/zed/settings.json").read_text())
    assert "language_models" not in zed
    assert "ssh_connections" not in zed
    assert zed["languages"]["JSON"] == {"format_on_save": "off"}
    assert excluded.read_text() == "seeded work app\n"


def test_missing_personal_secrets_blocks_every_write(tmp_path: Path) -> None:
    home, result = run_native(tmp_path, "personal", secrets=False)
    assert result.returncode != 0
    assert not any((home / relative).exists() for relative in PERSONAL_FILES)


def test_catalogue_selection_and_zed_models_come_from_input(tmp_path: Path) -> None:
    catalogue = tmp_path / "models.yml"
    catalogue.write_text(
        """models:
  anthropic:
    opus: {version: opus-literal, display_name: Opus, vscode: {include: false}}
    excluded: {version: excluded, display_name: Excluded, vscode: {include: false}}
  openai:
    gpt_sol:
      version: sol-literal
      display_name: Sol Literal
      max_input: 12345
      max_output: 6789
      vscode: {include: false}
      variants:
        high: {id: high-literal, display_name: High Literal, vscode: true}
        excluded: {id: no-literal, display_name: No Literal, vscode: false}
  google:
    gemini_flash: {version: flash-literal, display_name: Flash, vscode: {include: false}}
    included: {version: included-literal, display_name: Included, vscode: {include: true}}
"""
    )
    zed = subprocess.run(
        renderer_args("zed", models=catalogue),
        check=True,
        capture_output=True,
        text=True,
    )
    settings = json.loads(zed.stdout)
    assert settings["language_models"]["openai"]["available_models"] == [
        {
            "name": "sol-literal",
            "display_name": "Sol Literal",
            "max_tokens": 12345,
            "max_output_tokens": 6789,
            "max_completion_tokens": 6789,
        },
        {
            "name": "high-literal",
            "display_name": "High Literal",
            "reasoning_effort": "high",
            "max_tokens": 12345,
            "max_output_tokens": 6789,
            "max_completion_tokens": 6789,
        },
    ]
    llm = subprocess.run(
        renderer_args("llm", models=catalogue),
        check=True,
        capture_output=True,
        text=True,
    )
    assert [item["model_name"] for item in yaml.safe_load(llm.stdout)] == [
        "high-literal",
        "included-literal",
    ]


@pytest.mark.parametrize("kind", ["zed", "vscode"])
def test_settings_commands_require_settings_arguments(kind: str) -> None:
    result = subprocess.run(
        [
            str(PYTHON),
            str(CAPABILITY / "render.py"),
            kind,
            f"--models={ROOT / 'ansible/models.yml'}",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "requires --profile, --monospace-font, --proportional-font, --font-size" in (
        result.stderr
    )


def test_registration_is_mac_only_and_uses_capability_directory() -> None:
    personal = ROOT / "bootstrap/targets/Thurstons-MacBook-Pro"
    work = ROOT / "bootstrap/targets/ML-DFC6YK6VJQ"
    for target in (personal, work):
        assert (target / "editor-config").resolve() == CAPABILITY
        assert (target / "mise.editor-config.toml").is_file()
    assert not list((ROOT / "bootstrap/targets/pod042").glob("*editor-config*"))


@pytest.mark.parametrize(
    ("host", "expected_font"),
    [
        ("Thurstons-MacBook-Pro", "Root Personal Override"),
        ("ML-DFC6YK6VJQ", "Root Work Override"),
    ],
)
def test_root_check_uses_real_mise_without_secrets_or_writes(
    tmp_path: Path, host: str, expected_font: str
) -> None:
    project = tmp_path / "repository"
    target = project / "bootstrap/targets" / host
    target.mkdir(parents=True)
    shutil.copy(ROOT / "mise.toml", project / "mise.toml")
    shutil.copy(ROOT / f"bootstrap/targets/{host}/mise.toml", target / "mise.toml")
    shutil.copy(
        ROOT / f"bootstrap/targets/{host}/mise.editor-config.toml",
        target / "mise.editor-config.toml",
    )
    (target / "mise.local.toml").write_text(
        f'[vars]\neditor_monospace_font = "{expected_font}"\n'
    )
    (target / "editor-config").symlink_to(CAPABILITY, target_is_directory=True)
    (project / "bootstrap/capabilities").mkdir(parents=True)
    (project / "bootstrap/capabilities/editor-config").symlink_to(
        CAPABILITY, target_is_directory=True
    )
    (project / "ansible").mkdir()
    (project / "ansible/models.yml").symlink_to(ROOT / "ansible/models.yml")
    (project / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
    sentinel = tmp_path / "fnox-was-called"
    (project / "scripts").mkdir()
    (project / "scripts/fnox-host").write_text(
        f'#!/bin/sh\ntouch "{sentinel}"\nexit 91\n'
    )
    (project / "scripts/fnox-host").chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "hostname").write_text(f'#!/bin/sh\nprintf "%s\\n" {host}\n')
    (fake_bin / "hostname").chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    mise_data = tmp_path / "mise-data"
    python_install = mise_data / "installs/python/3.14.7"
    python_install.parent.mkdir(parents=True)
    python_install.symlink_to(
        Path(
            subprocess.run(
                ["mise", "where", "python@3.14"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ),
        target_is_directory=True,
    )
    environment = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "MISE_CACHE_DIR": str(tmp_path / "mise-cache"),
        "MISE_CONFIG_DIR": str(tmp_path / "mise-config"),
        "MISE_DATA_DIR": str(mise_data),
        "MISE_STATE_DIR": str(tmp_path / "mise-state"),
        "MISE_SYSTEM_CONFIG_FILE": str(tmp_path / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(tmp_path / "absent-global.toml"),
        "MISE_TRUSTED_CONFIG_PATHS": str(project),
    }
    for name in FAKE_SECRET_NAMES:
        environment.pop(name, None)
    result = subprocess.run(
        [
            "mise",
            "-C",
            str(project),
            "run",
            "--skip-tools",
            "editor-config",
            "--check",
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not sentinel.exists()
    assert not any(home.rglob("settings.json"))
    assert not any(name in environment for name in FAKE_SECRET_NAMES)


def test_scoped_activation_applies_corrected_capability_exactly(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    home = tmp_path / "home"
    target.mkdir()
    home.mkdir()
    shutil.copy(
        ROOT / "bootstrap/targets/Thurstons-MacBook-Pro/mise.toml",
        target / "mise.toml",
    )
    shutil.copy(
        ROOT / "bootstrap/targets/Thurstons-MacBook-Pro/mise.editor-config.toml",
        target / "mise.editor-config.toml",
    )
    probe = tmp_path / "independent-exec.txt"
    probe_template = tmp_path / "activation-probe.tera"
    probe_template.write_text(
        '{{ exec(command="sh -c \'printf \\"%s|%s|%s|%s\\\\n\\" '
        '\\"${CF_ACCESS_CLIENT_ID-unset}\\" '
        '\\"${CF_ACCESS_CLIENT_SECRET-unset}\\" '
        '\\"${HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE-unset}\\" '
        '\\"${HOMEBREW_ANSIBLONOMICON_EXEC_KEYS-unset}\\"\'") }}\n'
    )
    with (target / "mise.editor-config.toml").open("a") as target_manifest:
        target_manifest.write(
            f'\n[bootstrap.files."{probe}"]\n'
            f'source = "{probe_template}"\n'
            "template = true\n"
        )
    (target / "mise.local.toml").write_text(
        '[vars]\neditor_monospace_font = "Native Override"\n'
    )
    (target / "editor-config").symlink_to(CAPABILITY, target_is_directory=True)
    for relative in PERSONAL_FILES:
        (home / relative).parent.mkdir(parents=True, exist_ok=True)

    fake_fnox = tmp_path / "fnox-host"
    activation = tmp_path / "activation"
    activation.mkdir()
    (activation / "mise.toml").write_text(
        """[env]
CLI_PROXY_API_KEY = "scoped-api-key"
CF_ACCESS_CLIENT_ID = "__EDITOR_CONFIG_CF_CLIENT_SECRET__"
CF_ACCESS_CLIENT_SECRET = "secret \\"quote\\"\\nsecond line"
HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE = "macos"
HOMEBREW_ANSIBLONOMICON_EXEC_KEYS = '["CF_ACCESS_CLIENT_ID","CF_ACCESS_CLIENT_SECRET","CLI_PROXY_API_KEY"]'
"""
    )
    fake_fnox.write_text(
        f"""#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" > {str(tmp_path / "scope.txt")!r}
while [[ $1 != -- ]]; do shift; done
shift
cd {str(activation)!r}
eval "$(mise activate bash)"
test -n "${{__MISE_DIFF:-}}"
exec "$@"
"""
    )
    fake_fnox.chmod(0o755)
    environment = {
        **os.environ,
        "HOME": str(home),
        "MISE_CACHE_DIR": str(tmp_path / "mise-cache"),
        "MISE_CONFIG_DIR": str(tmp_path / "mise-config"),
        "MISE_DATA_DIR": str(tmp_path / "mise-data"),
        "MISE_STATE_DIR": str(tmp_path / "mise-state"),
        "MISE_SYSTEM_CONFIG_FILE": str(tmp_path / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(tmp_path / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(tmp_path),
        "MISE_TRUSTED_CONFIG_PATHS": str(tmp_path),
        "EDITOR_CONFIG_PYTHON": str(PYTHON),
        "EDITOR_CONFIG_RENDERER": str(CAPABILITY / "render.py"),
        "EDITOR_CONFIG_MODELS": str(ROOT / "ansible/models.yml"),
    }
    for name in FAKE_SECRET_NAMES:
        environment.pop(name, None)
    result = subprocess.run(
        [
            str(fake_fnox),
            "exec",
            "--secret",
            "CLI_PROXY_API_KEY",
            "--secret",
            "CF_ACCESS_CLIENT_ID",
            "--secret",
            "CF_ACCESS_CLIENT_SECRET",
            "--",
            "mise",
            "-E",
            "editor-config",
            "-C",
            str(target),
            "bootstrap",
            "--only",
            "files,dotfiles",
            "--force-dotfiles",
            "--yes",
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "scope.txt").read_text().split(" -- ", maxsplit=1)[0] == (
        "exec --secret CLI_PROXY_API_KEY --secret CF_ACCESS_CLIENT_ID "
        "--secret CF_ACCESS_CLIENT_SECRET"
    )
    assert probe.read_text() == "unset|unset|unset|unset\n"
    for secret in (
        "scoped-api-key",
        "__EDITOR_CONFIG_CF_CLIENT_SECRET__",
        'secret "quote"\nsecond line',
    ):
        apply_log = result.stdout + result.stderr
        assert secret not in apply_log
        assert json.dumps(secret)[1:-1] not in apply_log
    assert (
        json.loads(
            (
                home / "Library/Application Support/io.datasette.llm/keys.json"
            ).read_text()
        )["llm-api-key"]
        == "scoped-api-key"
    )
    models = yaml.safe_load(
        (
            home
            / "Library/Application Support/io.datasette.llm/extra-openai-models.yaml"
        ).read_text()
    )
    assert all(
        model["headers"]
        == {
            "CF-Access-Client-Id": "__EDITOR_CONFIG_CF_CLIENT_SECRET__",
            "CF-Access-Client-Secret": 'secret "quote"\nsecond line',
        }
        for model in models
    )
    assert (
        json.loads((home / ".config/zed/settings.json").read_text())[
            "buffer_font_family"
        ]
        == "Native Override"
    )
