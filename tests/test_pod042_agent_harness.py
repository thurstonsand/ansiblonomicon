"""Native harness shares the catalogue, resolver and platform layouts."""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "bootstrap/targets/pod042/agent-harness/reconcile.py"
spec = importlib.util.spec_from_file_location("pod042_harness", SCRIPT)
assert spec is not None and spec.loader is not None
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def test_profile_and_linux_layout() -> None:
    _, profile, layouts, sources = harness.declarations(REPO, harness.HOME)
    assert profile["target_agents"] == ["claude", "amp", "codex", "opencode", "pi"]
    assert profile["explicit_only"] == ["amp"]
    assert (
        layouts["opencode"]["skills_dir"] == "/home/thurstonsand/.config/opencode/skill"
    )
    assert (
        layouts["opencode"]["agents_dir"] == "/home/thurstonsand/.config/opencode/agent"
    )
    assert layouts["codex"]["agents_dir"] is None
    assert (
        Path(harness.filters.__file__)
        == REPO / "ansible/roles/agent_harness/filter_plugins/harness_filters.py"
    )
    assert any(source.get("repo") == "Shpigford/nurb" for source in sources)
    assert not any(
        source.get("local", "").endswith("agents/work") for source in sources
    )


def test_local_resources_all_platforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = harness.declarations

    def local_declarations(repo: Path, home: Path):
        env, profile, layouts, sources = original(repo, home)
        return (
            env,
            profile,
            layouts,
            [source for source in sources if "local" in source],
        )

    monkeypatch.setattr(harness, "declarations", local_declarations)
    home = tmp_path / "home"
    cache = home / ".cache/ansiblonomicon-harness"
    files = harness.render_files(REPO, home, cache)
    paths = {str(path.relative_to(home)) for path in files}
    assert ".claude/skills/handoff/SKILL.md" in paths
    assert ".codex/skills/notify/SKILL.md" in paths
    assert ".pi/agent/skills/grill-me/SKILL.md" in paths
    assert ".config/opencode/skill/notify/SKILL.md" in paths
    amp = {
        path
        for path in paths
        if path.startswith(".config/amp/skills/") and path.endswith("/SKILL.md")
    }
    assert amp == {".config/amp/skills/truenas-docker-ops/SKILL.md"}
    handoff = files[home / ".claude/skills/handoff/SKILL.md"][0].decode()
    assert "{{" not in handoff
    assert "{%" not in handoff
    assert "claude-code-auto-title" not in handoff
    assert (REPO / "ansible/session-title-prompt.txt").read_text().strip() in handoff
    notify = home / ".pi/agent/skills/notify/scripts/notify.sh"
    assert files[notify][1] == 0o755
    assert b"fnox-host" in files[notify][0]
    assert not any(path.endswith(".j2") for path in paths)
    assert not any(
        "settings.json" in path or path.endswith("AGENTS.md") for path in paths
    )


def test_reconcile_only_removes_owned_files_and_check_is_read_only(
    tmp_path: Path,
) -> None:
    home = tmp_path
    cache = home / ".cache/ansiblonomicon-harness"
    external = home / ".codex/skills/external/SKILL.md"
    external.parent.mkdir(parents=True)
    external.write_text("owned by Codex")
    managed = home / ".codex/skills/managed/SKILL.md"
    files = {managed: (b"managed", 0o644)}
    harness.reconcile(files, home, cache, True)
    assert not managed.exists()
    assert not cache.exists()
    harness.reconcile(files, home, cache, False)
    assert managed.read_bytes() == b"managed"
    first_mtime = managed.stat().st_mtime_ns
    harness.reconcile(files, home, cache, False)
    assert managed.stat().st_mtime_ns == first_mtime
    harness.reconcile({}, home, cache, False)
    assert not managed.exists()
    assert external.read_text() == "owned by Codex"


def test_refuse_manifest_escape(tmp_path: Path) -> None:
    cache = tmp_path / ".cache/ansiblonomicon-harness"
    cache.mkdir(parents=True)
    (cache / "pod042-managed-files.json").write_text(json.dumps(["../outside"]))
    with pytest.raises(ValueError, match="escapes"):
        harness.reconcile({}, tmp_path, cache, False)


def test_native_hook_operator_ownership() -> None:
    config = (REPO / "bootstrap/targets/pod042/mise.agent-harness.toml").read_text()
    assert "sudo -u thurstonsand env -i" in config
    assert "HOME=/home/thurstonsand" in config
    assert "uv run --script" in config
    assert "ansible-playbook" not in config
    assert "os.getuid() != 1000" in SCRIPT.read_text()
    assert "os.getgid() != 1000" in SCRIPT.read_text()
