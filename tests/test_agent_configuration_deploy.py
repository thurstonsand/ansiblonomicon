# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "bootstrap/capabilities/agent-harness/configuration/deploy.py"
SPEC = importlib.util.spec_from_file_location("configuration_deploy", PATH)
assert SPEC and SPEC.loader
deploy: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


@pytest.mark.parametrize(
    ("hostname", "expected"),
    [
        ("Thurstons-MacBook-Pro", "Develop"),
        (deploy.WORK_HOST, "code"),
        ("pod042", "code"),
    ],
)
def test_load_data_uses_host_develop_directory(
    tmp_path: Path, hostname: str, expected: str
) -> None:
    repo = tmp_path / "repo"
    (repo / "ansible").mkdir(parents=True)
    shutil.copy(ROOT / "ansible/models.yml", repo / "ansible/models.yml")
    if hostname == deploy.WORK_HOST:
        local = repo / "bootstrap/capabilities/agent-harness/local" / hostname
        local.mkdir(parents=True)
        (local / "data.toml").write_text("[work_gateway]\n[work_models]\n")

    data = deploy.load_data(repo, hostname, tmp_path / "home")

    assert data["developDir"] == expected
    assert "host_defaults" not in data


def test_load_data_local_overlay_overrides_host_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "ansible").mkdir(parents=True)
    shutil.copy(ROOT / "ansible/models.yml", repo / "ansible/models.yml")
    local = repo / "bootstrap/capabilities/agent-harness/local/pod042"
    local.mkdir(parents=True)
    (local / "data.toml").write_text('developDir = "/srv/source"\n')

    data = deploy.load_data(repo, "pod042", tmp_path / "home")

    assert data["developDir"] == "/srv/source"


def test_render_all_work_uses_exact_declared_secret_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "ansible").mkdir(parents=True)
    shutil.copy(ROOT / "ansible/models.yml", repo / "ansible/models.yml")
    shutil.copy(
        ROOT / "ansible/session-title-prompt.txt",
        repo / "ansible/session-title-prompt.txt",
    )
    local = repo / "bootstrap/capabilities/agent-harness/local" / deploy.WORK_HOST
    local.mkdir(parents=True)
    (local / "data.toml").write_text(
        '[work_gateway]\nbase_url = "https://gateway.example.test"\n'
        'anthropic_provider = "work-anthropic"\nopenai_provider = "work-openai"\n'
        + "".join(
            f'[work_models.{name}]\nversion = "{name}-version"\n'
            f'display_name = "{name} display"\npi_alias = "{name}-alias"\n'
            "cost = { input = 1, output = 2 }\ncontext_window = 100000\n"
            "max_output = 10000\nsupports_temperature = true\n"
            for name in (
                "opus",
                "sonnet",
                "haiku",
                "gpt_sol",
                "gpt_terra",
                "gpt_luna",
            )
        )
    )
    home = tmp_path / "home"
    data = deploy.load_data(repo, deploy.WORK_HOST, home)
    secrets = {key: f"synthetic-{key}" for key in deploy.SECRET_KEYS[deploy.WORK_HOST]}

    rendered = deploy.render_all(repo, home, deploy.WORK_HOST, data, secrets)

    assert deploy.SECRET_KEYS[deploy.WORK_HOST] == {"ANTHROPIC_AUTH_TOKEN"}
    assert ".claude/settings.json" in rendered
    assert ".claude/hooks/_config.py" not in rendered
    assert not any(path.startswith(".codex/") for path in rendered)


def test_native_reconcile_writes_modes_links_removes_owned_and_is_repeatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    outputs = {
        ".claude/hooks/_config.py": "secret\n",
        ".claude/scripts/statusline.sh": "#!/bin/sh\n",
        ".pi/agent/settings.json": "{}\n",
    }
    asset = tmp_path / "asset"
    asset.write_text("static\n")
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: outputs)
    monkeypatch.setattr(
        deploy, "_assets", lambda *_: ([(asset, ".config/tool/static")], [], [])
    )
    state = home / ".cache/ansiblonomicon-harness/configuration"
    state.mkdir(parents=True, mode=0o700)
    (home / ".old").write_text("retired")
    proof = "file:" + hashlib.sha256(b"retired").hexdigest()
    (state / "owned.json").write_text(json.dumps({".old": proof}))

    before = sorted(path.relative_to(home) for path in home.rglob("*"))
    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=True
        )
        == 1
    )
    assert sorted(path.relative_to(home) for path in home.rglob("*")) == before
    assert (home / ".old").exists()
    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
        == 0
    )
    assert not (home / ".old").exists()
    assert stat.S_IMODE((home / ".claude/hooks/_config.py").stat().st_mode) == 0o600
    assert (
        stat.S_IMODE((home / ".claude/scripts/statusline.sh").stat().st_mode) == 0o755
    )
    assert stat.S_IMODE((home / ".pi/agent").stat().st_mode) == 0o700
    assert (home / ".config/tool/static").is_symlink()
    assert (home / ".config/tool/static").resolve() == asset
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    assert stat.S_IMODE((home / ".cache").stat().st_mode) != 0o700
    mtime = (home / ".claude/hooks/_config.py").stat().st_mtime_ns
    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
        == 0
    )
    assert (home / ".claude/hooks/_config.py").stat().st_mtime_ns == mtime
    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=True
        )
        == 0
    )


def test_native_preserves_home_and_amp_private_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    amp = home / ".config/amp"
    amp.mkdir(parents=True, mode=0o700)
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))

    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)

    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert stat.S_IMODE(amp.stat().st_mode) == 0o700


def test_check_omits_only_missing_package_link_from_native_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    configuration = tmp_path / "configuration"
    source = configuration / "fixture-package"
    source.mkdir(parents=True)
    (source / "package.json").write_text('{"name":"fixture-package"}\n')
    asset = tmp_path / "asset"
    asset.write_text("asset\n")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(deploy, "__file__", str(configuration / "deploy.py"))
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {".rendered": "value\n"})
    monkeypatch.setattr(
        deploy,
        "_assets",
        lambda *_: (
            [(asset, ".static")],
            [{"source": "fixture-package", "destination": ".package/node_modules"}],
            [],
        ),
    )

    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=True
        )
        == 1
    )
    assert "missing source dependencies" in capsys.readouterr().err
    assert list(home.iterdir()) == []


def test_lockless_package_install_is_stable_on_immediate_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = tmp_path / "configuration"
    dependency = configuration / "dependency"
    dependency.mkdir(parents=True)
    (dependency / "package.json").write_text(
        '{"name":"fixture-dependency","version":"1.0.0","main":"index.js"}\n'
    )
    (dependency / "index.js").write_text("module.exports = 'installed';\n")
    source = configuration / "consumer"
    source.mkdir()
    (source / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture-consumer",
                "dependencies": {"fixture-dependency": "file:../dependency"},
            }
        )
        + "\n"
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(deploy, "__file__", str(configuration / "deploy.py"))
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(
        deploy,
        "_assets",
        lambda *_: (
            [],
            [{"source": "consumer", "destination": ".consumer/node_modules"}],
            [],
        ),
    )
    real_run = subprocess.run
    npm_calls: list[list[str]] = []

    def record_run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "npm":
            npm_calls.append(command)
        return cast("subprocess.CompletedProcess[str]", real_run(command, **kwargs))

    monkeypatch.setattr(deploy.subprocess, "run", record_run)

    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)
    assert npm_calls == [["npm", "install", "--package-lock=false"]]
    assert not (source / "package-lock.json").exists()
    assert (source / "node_modules/fixture-dependency/index.js").is_file()
    delivered = home / ".consumer/node_modules"
    assert delivered.is_symlink()
    before = {
        path.relative_to(home): (
            path.is_symlink(),
            path.readlink() if path.is_symlink() else path.read_bytes(),
        )
        for path in home.rglob("*")
        if path.is_file() or path.is_symlink()
        if "mise-state" not in path.parts
    }

    npm_calls.clear()
    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)
    after = {
        path.relative_to(home): (
            path.is_symlink(),
            path.readlink() if path.is_symlink() else path.read_bytes(),
        )
        for path in home.rglob("*")
        if path.is_file() or path.is_symlink()
        if "mise-state" not in path.parts
    }
    assert npm_calls == []
    assert after == before


def test_package_replaces_legacy_tree_without_sudo_and_resolves_from_deployed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    extension = tmp_path / "runtime-test.ts"
    extension.write_text('import jiti from "jiti"; export default typeof jiti;\n')
    destination = ".pi/agent/extensions/node_modules"
    legacy = home / destination
    legacy.mkdir(parents=True)
    (legacy / "generated-package").mkdir()
    (legacy / "generated-package/package.json").write_text('{"generated":true}\n')
    sibling = legacy.parent / "foreign.ts"
    sibling.write_text("keep\n")
    sudo_called = tmp_path / "sudo-called"
    binary = tmp_path / "bin"
    binary.mkdir()
    sudo = binary / "sudo"
    sudo.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" > {sudo_called}\nexit 97\n")
    sudo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    source = PATH.parent / "assets/pi/extensions"
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(
        deploy,
        "_assets",
        lambda *_: (
            [(extension, ".pi/agent/extensions/runtime-test.ts")],
            [
                {
                    "source": "assets/pi/extensions",
                    "destination": destination,
                    "hosts": ["pod042"],
                }
            ],
            [],
        ),
    )

    deploy.reconcile(
        repo=ROOT,
        home=home,
        hostname="Thurstons-MacBook-Pro",
        secrets={},
        check=False,
    )

    assert legacy.is_symlink()
    assert legacy.resolve() == source / "node_modules"
    assert sibling.read_text() == "keep\n"
    assert not sudo_called.exists()
    assert not (
        home / ".cache/ansiblonomicon-harness/configuration/native-transition"
    ).exists()
    jiti_module = source / "node_modules/jiti/lib/jiti.mjs"
    script = (
        f"import {{ createJiti }} from {json.dumps(jiti_module.as_uri())};"
        f"const load=createJiti({json.dumps(str(home / '.pi/agent/extensions/loader.mjs'))});"
        f"console.log((await load.import({json.dumps(str(home / '.pi/agent/extensions/runtime-test.ts'))})).default);"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "function"


def test_changed_owned_output_is_not_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target = home / ".retired"
    target.write_text("changed")
    state = home / ".cache/ansiblonomicon-harness/configuration"
    state.mkdir(parents=True)
    old = "file:" + hashlib.sha256(b"original").hexdigest()
    (state / "owned.json").write_text(json.dumps({".retired": old}))
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))

    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
        == 0
    )
    assert target.read_text() == "changed"


def test_invalid_input_is_validated_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {"../escape": "bad"})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))
    with pytest.raises(ValueError, match="unsafe"):
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
    assert list(home.iterdir()) == []


def test_output_asset_collision_is_validated_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    asset = tmp_path / "asset"
    asset.write_text("asset")
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {".same": "rendered"})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([(asset, ".same")], [], []))
    with pytest.raises(ValueError, match="conflicting"):
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
    assert list(home.iterdir()) == []


def test_mcp_converts_claude_schema_preserves_foreign_and_rejects_transport(
    tmp_path: Path,
) -> None:
    (tmp_path / ".claude.json").write_text(
        json.dumps({"mcpServers": {"foreign": {"command": "keep"}}})
    )
    _, rendered = deploy._mcp_output(
        tmp_path,
        {
            "mcp_servers": [
                {
                    "name": "owned",
                    "transport": "stdio",
                    "command": "x",
                    "args": ["--flag"],
                    "env": {"TOKEN": "value"},
                },
                {
                    "name": "remote",
                    "transport": "http",
                    "url": "https://example.test/mcp",
                    "headers": {"Authorization": "Bearer value"},
                },
            ]
        },
    )
    assert json.loads(rendered)["mcpServers"] == {
        "foreign": {"command": "keep"},
        "owned": {
            "command": "x",
            "args": ["--flag"],
            "env": {"TOKEN": "value"},
        },
        "remote": {
            "type": "http",
            "url": "https://example.test/mcp",
            "headers": {"Authorization": "Bearer value"},
        },
    }
    with pytest.raises(ValueError, match="transport"):
        deploy._mcp_output(
            tmp_path, {"mcp_servers": [{"name": "bad", "transport": "socket"}]}
        )


def test_native_mcp_nonempty_to_empty_preserves_app_owned_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target = home / ".claude.json"
    target.write_text(
        json.dumps(
            {
                "theme": "foreign",
                "mcpServers": {"foreign": {"command": "keep"}},
            }
        )
    )
    data = {
        "mcp_servers": [{"name": "owned", "transport": "stdio", "command": "managed"}]
    }
    monkeypatch.setattr(deploy, "load_data", lambda *_: data)
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))

    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)
    assert json.loads(target.read_text())["mcpServers"]["owned"] == {
        "command": "managed"
    }

    data["mcp_servers"] = []
    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)
    assert target.is_file()
    assert json.loads(target.read_text()) == {
        "theme": "foreign",
        "mcpServers": {"foreign": {"command": "keep"}},
    }
    assert ".claude.json" not in json.loads(
        (home / ".cache/ansiblonomicon-harness/configuration/owned.json").read_text()
    )


def test_host_local_hook_asset_native_delivery_is_repeatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    local = repo / "bootstrap/capabilities/agent-harness/local/ML-DFC6YK6VJQ"
    hook = local / "claude/hooks/local/private-hook.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/usr/bin/env python3\n")
    hook.chmod(0o755)
    (local / "assets.toml").write_text(
        """[[files]]
source = "claude/hooks/local/private-hook.py"
destination = ".claude/hooks/local/private-hook.py"
mode = "symlink"
"""
    )
    all_links, _, _ = deploy._assets(repo, "ML-DFC6YK6VJQ")
    links = [item for item in all_links if item[0] == hook]
    home = tmp_path / "home"
    foreign = home / ".claude/hooks/local/foreign.py"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("keep\n")
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(deploy, "_assets", lambda *_: (links, [], []))

    deploy.reconcile(
        repo=repo, home=home, hostname="ML-DFC6YK6VJQ", secrets={}, check=False
    )
    delivered = home / ".claude/hooks/local/private-hook.py"
    assert delivered.is_symlink()
    assert delivered.resolve() == hook
    assert stat.S_IMODE(delivered.stat().st_mode) == 0o755
    mtime = delivered.lstat().st_mtime_ns
    deploy.reconcile(
        repo=repo, home=home, hostname="ML-DFC6YK6VJQ", secrets={}, check=False
    )
    assert delivered.lstat().st_mtime_ns == mtime
    assert foreign.read_text() == "keep\n"


@pytest.mark.parametrize(
    ("source", "destination"),
    [("../escape", ".safe"), ("hook.py", "../escape")],
)
def test_host_local_asset_rejects_unsafe_fields_before_writes(
    tmp_path: Path, source: str, destination: str
) -> None:
    repo = tmp_path / "repo"
    local = repo / "bootstrap/capabilities/agent-harness/local/pod042"
    local.mkdir(parents=True)
    (local / "hook.py").write_text("hook")
    (local / "assets.toml").write_text(
        f'[[files]]\nsource = "{source}"\ndestination = "{destination}"\nmode = "symlink"\n'
    )
    with pytest.raises(ValueError, match="unsafe"):
        deploy._assets(repo, "pod042")


def test_inventory_paths_are_validated_before_target_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    state = home / ".cache/ansiblonomicon-harness/configuration"
    state.mkdir(parents=True)
    (state / "owned.json").write_text(json.dumps({"../foreign": "file:proof"}))
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))

    with pytest.raises(ValueError, match="unsafe"):
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )


def test_rendered_destination_rejects_foreign_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    foreign = tmp_path / "foreign"
    foreign.write_text("keep")
    (home / ".rendered").symlink_to(foreign)
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {".rendered": "replace"})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))

    with pytest.raises(ValueError, match="destination symlink"):
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
    assert foreign.read_text() == "keep"


def test_interrupted_adoption_keeps_first_backup_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target = home / ".adopted"
    target.write_text("original")
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {".adopted": "managed"})
    monkeypatch.setattr(deploy, "_assets", lambda *_: ([], [], []))
    real_apply = deploy._apply_native
    calls = 0

    def interrupt_once(*args: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            target.write_text("interrupted")
            raise RuntimeError("interrupted")
        real_apply(*args)

    monkeypatch.setattr(deploy, "_apply_native", interrupt_once)
    with pytest.raises(RuntimeError, match="interrupted"):
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=False
        )
    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)

    backup = home / ".cache/ansiblonomicon-harness/configuration/backups/.adopted"
    assert backup.read_text() == "original"
    assert target.read_text() == "managed"


def test_explicit_retirement_preserves_foreign_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    retired = home / ".pi/agent/extensions/permission-gate"
    nested = retired / "nested/deeper"
    nested.mkdir(parents=True)
    (retired / "old.ts").write_text("old")
    (nested / "old.json").write_bytes(b"retired")
    external = tmp_path / "external"
    external.mkdir()
    external_file = external / "keep.bin"
    external_file.write_bytes(b"external")
    (retired / "external-link").symlink_to(external, target_is_directory=True)
    sibling = retired.parent / "foreign.ts"
    sibling.write_bytes(b"sibling")
    sudo_calls = tmp_path / "sudo-calls"
    binary = tmp_path / "bin"
    binary.mkdir()
    sudo = binary / "sudo"
    sudo.write_text(f"#!/bin/sh\nprintf call >> {sudo_calls}\nexit 97\n")
    sudo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setattr(deploy, "load_data", lambda *_: {"mcp_servers": []})
    monkeypatch.setattr(deploy, "render_all", lambda *_: {})
    monkeypatch.setattr(
        deploy,
        "_assets",
        lambda *_: ([], [], [".pi/agent/extensions/permission-gate"]),
    )

    before = {path: path.read_bytes() for path in (external_file, sibling)}
    assert (
        deploy.reconcile(
            repo=ROOT, home=home, hostname="pod042", secrets={}, check=True
        )
        == 1
    )
    assert retired.is_dir()
    assert (nested / "old.json").read_bytes() == b"retired"
    assert {path: path.read_bytes() for path in before} == before
    assert not sudo_calls.exists()

    deploy.reconcile(repo=ROOT, home=home, hostname="pod042", secrets={}, check=False)
    assert not retired.exists()
    assert external_file.read_bytes() == b"external"
    assert sibling.read_bytes() == b"sibling"
    assert not sudo_calls.exists()
