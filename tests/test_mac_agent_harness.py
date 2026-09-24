import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/agent-harness"
SPEC = importlib.util.spec_from_file_location(
    "mac_agent_harness", CAPABILITY / "agent_harness_deploy.py"
)
assert SPEC and SPEC.loader
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)
MANIFEST = "macos-managed-files.json"
OWNER = "example/catalogue\0fixture"


def write_manifest(path: Path, paths: list[str]) -> None:
    path.write_text(
        json.dumps({"version": 3, "plugins": {OWNER: paths}, "selection_proofs": {}})
    )


def git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )


def fixture_repo(root: Path, home: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    cache = home / ".cache/ansiblonomicon-harness"
    capability = repo / "bootstrap/capabilities/agent-harness"
    (capability / "harnesses/claude").mkdir(parents=True)
    (capability / "harnesses/claude/mise.toml").write_text(
        f'''[harness]
name = "claude"
skills_root = "{home}/.claude/skills"
agents_root = "{home}/.claude/agents"
name_transform = "preserve"
'''
    )
    (capability / "profiles.toml").write_text(
        '[profiles.personal]\ntarget_agents = ["claude"]\nexplicit_only = []\n'
    )
    (capability / "models.yml").write_text("models: {}\n")
    (capability / "catalogue.toml").write_text(
        '[[sources]]\nrepo = "example/catalogue"\n'
        '[[sources.plugins]]\nname = "fixture"\n'
    )
    checkout = cache / "example--catalogue"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".claude-plugin").mkdir()
    (checkout / ".claude-plugin/plugin.json").write_text(
        '{"name":"fixture","skills":"demo","agents":"agents","hooks":"./hook.json"}\n'
    )
    (checkout / "demo").mkdir()
    (checkout / "demo/SKILL.md").write_text("---\nname: demo\n---\nliteral skill\n")
    executable = checkout / "demo/run.sh"
    executable.write_text("#!/bin/sh\necho literal\n")
    executable.chmod(0o755)
    (checkout / "agents").mkdir()
    (checkout / "agents/helper.md").write_text(
        "---\nname: helper\n---\nliteral helper\n"
    )
    (checkout / "hook.json").write_text('{"hook":"literal"}\n')
    return repo, cache


def run_fixture(
    root: Path,
    home: Path,
    repo: Path,
    cache: Path,
    *,
    check: bool = False,
    cached: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(CAPABILITY / "agent_harness_deploy.py"),
        "--repo",
        str(repo),
        "--home",
        str(home),
        "--cache",
        str(cache),
        "--host-config",
        str(root / "host.toml"),
    ]
    (root / "host.toml").write_text(
        """[agent_harness]
profile = "personal"
hostname = "fixture-mac"
enabled = ["claude"]
explicit_only = []
trim_blocks = true
update = "86400s"
manifest = "macos-managed-files.json"
"""
    )
    if check:
        command.append("--check")
    if cached:
        command.append("--cached")
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "MISE_STATE_DIR": str(root / "mise-state"),
            **(env or {}),
        },
        check=False,
    )


def test_real_native_apply_check_repeat_and_exact_ownership(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    home.chmod(0o700)
    repo, cache = fixture_repo(tmp_path, home)
    config_layout = (
        repo / "bootstrap/capabilities/agent-harness/harnesses/config_fixture"
    )
    config_layout.mkdir()
    (config_layout / "mise.toml").write_text(
        f'''[harness]
name = "config_fixture"
skills_root = "{home}/.config/fixture/skills"
name_transform = "preserve"
'''
    )
    profiles = repo / "bootstrap/capabilities/agent-harness/profiles.toml"
    profiles.write_text(
        profiles.read_text().replace('["claude"]', '["claude", "config_fixture"]')
    )
    native_template = (
        repo / "bootstrap/capabilities/agent-harness/harnesses/claude/native.tera"
    )
    native_template.write_text("channel={{ vars.channel }}\n")
    with (
        repo / "bootstrap/capabilities/agent-harness/harnesses/claude/mise.toml"
    ).open("a") as declaration:
        declaration.write(
            f'''
[vars]
channel = "stable"
[dotfiles."{home}/.claude/native.conf"]
source = "native.tera"
mode = "template"
[bootstrap.files."{home}/.claude/secret.conf"]
source = "native.tera"
template = true
mode = "0600"
[bootstrap.files."{home}/.claude/retired.conf"]
state = "absent"
'''
        )
    retired_native = home / ".claude/retired.conf"
    retired_native.parent.mkdir(parents=True)
    retired_native.write_text("retire")
    (home / ".claude").mkdir(mode=0o700, exist_ok=True)
    (home / ".claude").chmod(0o700)
    (home / ".config").mkdir(mode=0o700)
    (home / ".cache").chmod(0o700)
    foreign_git = home / ".claude/.git"
    foreign_git.mkdir()
    synced = home / ".claude/synced"
    synced.mkdir()
    unrelated = home / ".claude/skills/external/SKILL.md"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("independently installed")
    stale = home / ".claude/skills/stale/SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    manifest = cache / MANIFEST
    write_manifest(manifest, [str(stale.relative_to(home))])

    check = run_fixture(tmp_path, home, repo, cache, check=True)
    assert check.returncode == 0, check.stderr
    assert stale.read_text() == "old"
    assert not (home / ".claude/skills/demo/SKILL.md").exists()

    apply = run_fixture(tmp_path, home, repo, cache)
    assert apply.returncode == 0, apply.stderr
    skill = home / ".claude/skills/demo/SKILL.md"
    script = home / ".claude/skills/demo/run.sh"
    agent = home / ".claude/agents/helper.md"
    hook = cache / "hooks/fixture.json"
    assert skill.read_text() == "---\nname: demo\n---\nliteral skill\n"
    assert script.read_text() == "#!/bin/sh\necho literal\n"
    assert agent.read_text() == "---\nname: helper\n---\nliteral helper\n"
    assert hook.read_text() == '{"hook":"literal"}\n'
    assert (home / ".claude/native.conf").read_text() == "channel=stable\n"
    assert (home / ".claude/secret.conf").read_text() == "channel=stable\n"
    assert (home / ".claude/secret.conf").stat().st_mode & 0o777 == 0o600
    assert not retired_native.exists()
    assert [path.stat().st_mode & 0o777 for path in (skill, script, agent, hook)] == [
        0o644,
        0o755,
        0o644,
        0o644,
    ]
    assert not stale.exists()
    assert unrelated.read_text() == "independently installed"
    assert foreign_git.is_dir()
    assert synced.is_dir()
    assert [
        path.stat().st_mode & 0o777
        for path in (home / ".claude", home / ".config", home / ".cache")
    ] == [0o700, 0o700, 0o700]
    mtimes = {
        path: path.stat().st_mtime_ns for path in (skill, script, agent, hook, manifest)
    }
    script.chmod(0o644)
    repeat = run_fixture(tmp_path, home, repo, cache)
    assert repeat.returncode == 0, repeat.stderr
    assert script.stat().st_mode & 0o777 == 0o755
    assert {path: path.stat().st_mtime_ns for path in mtimes} == mtimes


@pytest.mark.parametrize(
    "relative",
    ["../outside", ".claude/skills/../../.ssh/config", ".claude/skills/escape/file"],
)
def test_manifest_escape_and_symlink_escape_fail_before_mutation(
    tmp_path: Path, relative: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    outside = tmp_path / "outside"
    outside.mkdir()
    if relative.startswith(".claude"):
        (home / ".claude/skills").mkdir(parents=True)
        (home / ".claude/skills/escape").symlink_to(outside, target_is_directory=True)
        (outside / "file").write_text("safe")
    manifest = cache / MANIFEST
    write_manifest(manifest, [relative])
    before = manifest.read_bytes()

    result = run_fixture(tmp_path, home, repo, cache)
    assert result.returncode == 1
    assert "agent-harness:" in result.stderr
    assert manifest.read_bytes() == before
    assert not (home / ".claude/skills/demo/SKILL.md").exists()
    if (outside / "file").exists():
        assert (outside / "file").read_text() == "safe"


def test_manifest_itself_must_not_be_a_symlink(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    outside = tmp_path / "outside-manifest.json"
    outside.write_text("[]")
    (cache / MANIFEST).symlink_to(outside)

    result = run_fixture(tmp_path, home, repo, cache)

    assert result.returncode == 1
    assert "manifest must not be a symlink" in result.stderr
    assert outside.read_text() == "[]"


def test_failed_native_apply_retains_union_for_recovery(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    stale = home / ".claude/skills/stale/SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    manifest = cache / MANIFEST
    write_manifest(manifest, [str(stale.relative_to(home))])
    binary = tmp_path / "bin"
    binary.mkdir()
    fake = binary / "mise"
    fake.write_text("#!/bin/sh\nexit 23\n")
    fake.chmod(0o755)

    result = run_fixture(
        tmp_path, home, repo, cache, env={"PATH": f"{binary}:{os.environ['PATH']}"}
    )
    assert result.returncode == 1
    owned = json.loads(manifest.read_text())["plugins"]
    owned_paths = sorted(path for paths in owned.values() for path in paths)
    assert owned_paths == [
        ".cache/ansiblonomicon-harness/hooks/fixture.json",
        ".claude/agents/helper.md",
        ".claude/skills/demo/SKILL.md",
        ".claude/skills/demo/run.sh",
        ".claude/skills/stale/SKILL.md",
    ]


def test_cached_modes_require_complete_sources_and_do_not_advance_stamp(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    stamp = cache / "example--catalogue.last_update"
    stamp.write_text("unchanged")
    old = time.time() - 172800
    os.utime(stamp, (old, old))
    before = stamp.stat().st_mtime_ns
    assert run_fixture(tmp_path, home, repo, cache, check=True).returncode == 0
    assert run_fixture(tmp_path, home, repo, cache).returncode == 0
    assert stamp.stat().st_mtime_ns == before
    (cache / "example--catalogue/.git").rmdir()
    missing = run_fixture(tmp_path, home, repo, cache, check=True)
    assert missing.returncode == 1
    assert "Missing required cached harness sources" in missing.stderr


def test_normal_sync_honors_fresh_and_stale_interval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    checkout = cache / "example--catalogue"
    (checkout / ".git").mkdir(parents=True)
    stamp = cache / "example--catalogue.last_update"
    stamp.touch()
    source = {"repo": "example/catalogue", "plugins": [{"name": "fixture"}]}
    calls: list[list[str]] = []

    def record(command: list[str], *, check: bool) -> Any:
        del check
        calls.append(command)

    monkeypatch.setattr(subprocess, "run", record)
    harness.sync_sources([source], cache, stamp.stat().st_mtime + 86399)
    assert calls == []
    before = stamp.stat().st_mtime_ns
    harness.sync_sources([source], cache, stamp.stat().st_mtime + 86400)
    assert calls == [["git", "-C", str(checkout), "pull", "--ff-only"]]
    assert stamp.stat().st_mtime_ns >= before


def test_clone_failure_leaves_no_poisoned_checkout_and_retry_succeeds(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin"
    source: Any = {
        "repo": origin.as_uri(),
        "plugins": [{"name": "fixture"}],
    }
    cache = tmp_path / "cache"
    checkout = harness.checkout_for(source, cache)

    with pytest.raises(subprocess.CalledProcessError):
        harness.sync_sources([source], cache, time.time())
    assert not checkout.exists()
    assert not list(cache.glob(f".{checkout.name}.clone-*"))

    origin.mkdir()
    git("init", "-q", cwd=origin)
    (origin / "asset").write_text("ready")
    git("add", "asset", cwd=origin)
    git("commit", "-qm", "fixture", cwd=origin)
    harness.sync_sources([source], cache, time.time())
    assert (checkout / "asset").read_text() == "ready"


def test_manifest_owned_file_replaced_by_directory_is_preserved(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    owned = home / ".claude/skills/retired/SKILL.md"
    owned.mkdir(parents=True)
    child = owned / "foreign.txt"
    child.write_text("preserve me")
    manifest = cache / MANIFEST
    write_manifest(manifest, [str(owned.relative_to(home))])

    result = run_fixture(tmp_path, home, repo, cache)

    assert result.returncode == 1
    assert "Manifest-owned file was replaced by a directory" in result.stderr
    assert child.read_text() == "preserve me"
    assert json.loads(manifest.read_text())["plugins"] == {
        OWNER: [".claude/skills/retired/SKILL.md"]
    }


def test_omitted_plugin_retains_provenance_and_offline_remove_retires_it(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    first = run_fixture(tmp_path, home, repo, cache)
    assert first.returncode == 0, first.stderr
    skill = home / ".claude/skills/demo/SKILL.md"
    assert skill.read_text() == "---\nname: demo\n---\nliteral skill\n"

    config = repo / "bootstrap/capabilities/agent-harness/catalogue.toml"
    config.write_text("sources = []\n")
    omitted = run_fixture(tmp_path, home, repo, cache)
    assert omitted.returncode == 0, omitted.stderr
    assert skill.exists()
    retained = json.loads((cache / MANIFEST).read_text())["plugins"]
    assert any(".claude/skills/demo/SKILL.md" in paths for paths in retained.values())

    config.write_text(
        """[[sources]]
repo = "example/catalogue"
[[sources.plugins]]
name = "fixture"
remove = true
"""
    )
    shutil.rmtree(cache / "example--catalogue/.git")
    removed = run_fixture(tmp_path, home, repo, cache)
    assert removed.returncode == 0, removed.stderr
    assert not skill.exists()
    final = json.loads((cache / MANIFEST).read_text())["plugins"]
    assert not any(".claude/skills/demo/SKILL.md" in paths for paths in final.values())
    assert final[OWNER] == []

    repeated = run_fixture(tmp_path, home, repo, cache)
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads((cache / MANIFEST).read_text())["plugins"][OWNER] == []
