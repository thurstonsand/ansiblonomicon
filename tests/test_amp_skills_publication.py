"""The Amp User Skills render is pure, Ansible-free, and mirrors host deployment."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = "bootstrap/capabilities/agent-harness"
ENGINE_FILES = (
    "agent_harness_deploy.py",
    "catalogue.py",
    "harness_filters.py",
    "publish_amp_skills.py",
    "session-title-prompt.txt",
)


def load_publisher(repo: Path):
    spec = importlib.util.spec_from_file_location(
        f"publish_{repo.name}", repo / CAPABILITY / "publish_amp_skills.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        },
    )


def fixture_repo(root: Path) -> tuple[Path, Path]:
    """A checkout with the native capability only: no ansible/ tree at all."""
    repo = root / "repo"
    capability = repo / CAPABILITY
    (capability / "harnesses/amp").mkdir(parents=True)
    (capability / "harnesses/claude").mkdir()
    for name in ENGINE_FILES:
        shutil.copy(ROOT / CAPABILITY / name, capability / name)
    (capability / "models.yml").write_text(
        "models:\n  anthropic:\n    sonnet:\n      version: sonnet-fixture\n"
        "      agent_harness:\n        aliases:\n          amp: amp-sonnet\n"
        "          claude: sonnet\n"
    )
    (capability / "harnesses/amp/mise.toml").write_text(
        '[harness]\nname = "amp"\nskills_root = "~/.config/amp/skills"\n'
        'name_transform = "preserve"\n'
    )
    (capability / "harnesses/claude/mise.toml").write_text(
        '[harness]\nname = "claude"\nskills_root = "~/.claude/skills"\n'
        'agents_root = "~/.claude/agents"\nname_transform = "preserve"\n'
    )
    (capability / "profiles.toml").write_text(
        '[profiles.personal]\ntarget_agents = ["claude", "amp"]\nexplicit_only = ["amp"]\n'
        '[profiles.amp_publish]\ntarget_agents = ["amp"]\nexplicit_only = []\n'
    )
    (capability / "catalogue.toml").write_text(
        """[[sources]]
repo = "example/upstream"
[[sources.plugins]]
name = "upstream"
include_skills = ["kept"]

[[sources]]
local = "agents/fixture"
[[sources.plugins]]
name = "fixture"
target_agents = { "amp_publish" = ["amp"], "*" = ["claude"] }
exclude_skills = { "amp_publish" = ["hidden"] }
exclude_data = ["*.pyc"]
hooks = true
"""
    )
    plugin = repo / "agents/fixture"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin/plugin.json").write_text('{"name": "fixture"}')
    (plugin / "hooks").mkdir()
    (plugin / "hooks/hooks.json").write_text('{"hooks": {"root": "${PLUGIN_ROOT}"}}')
    for name in ("templated", "hidden"):
        skill = plugin / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md.j2").write_text(
            f"---\nname: {name}\n---\n"
            "{% if ansible_hostname is match('ML-') %}\nwork\n{% else %}\npersonal\n{% endif %}\n"
            "{{ lookup('file', agent_harness_root ~ '/session-title-prompt.txt') }}\n"
        )
    templated = plugin / "skills/templated"
    (templated / "scripts").mkdir()
    (templated / "scripts/run.sh").write_bytes(b"#!/bin/sh\necho fixture\n")
    (templated / "scripts/run.sh").chmod(0o755)
    (templated / "scripts/config.toml.j2").write_text(
        'home = "{{ ansible_facts.env.HOME }}"\n'
    )
    (templated / "scripts/stale.pyc").write_bytes(b"ignored")

    upstream = root / "upstream"
    for name in ("kept", "dropped"):
        skill = upstream / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\nmodel: sonnet\n---\nBody\n"
        )
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin/plugin.json").write_text('{"name": "upstream"}')
    git("init", "-q", "-b", "main", cwd=upstream)
    git("add", ".", cwd=upstream)
    git("commit", "-q", "-m", "fixture", cwd=upstream)
    return repo, upstream


def test_render_uses_only_the_native_capability(tmp_path: Path) -> None:
    repo, upstream = fixture_repo(tmp_path)
    assert not (repo / "ansible").exists()
    cache = tmp_path / "cache"
    checkout = cache / "sources/example--upstream"
    checkout.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", str(upstream), str(checkout)],
        check=True,
        capture_output=True,
    )

    publisher = load_publisher(repo)
    files = publisher.render(repo, cache, cached=True)
    paths = {path.as_posix() for path in files}

    assert paths == {
        "kept/SKILL.md",
        "templated/SKILL.md",
        "templated/scripts/run.sh",
        "templated/scripts/config.toml",
    }
    skill = files[Path("templated/SKILL.md")][0].decode()
    prompt = (ROOT / CAPABILITY / "session-title-prompt.txt").read_text().strip()
    assert "personal\n" in skill
    assert prompt in skill
    assert "{{" not in skill and "{%" not in skill
    assert files[Path("templated/scripts/run.sh")][1] == 0o755
    assert files[Path("templated/scripts/config.toml")][0] == (
        f'home = "{cache.resolve()}"\n'.encode()
    )
    assert (
        files[Path("kept/SKILL.md")][0]
        == b"---\nname: kept\nmodel: amp-sonnet\n---\nBody\n"
    )
    assert not (repo / "ansible").exists()


def test_cli_writes_the_tree_without_importing_ansible(tmp_path: Path) -> None:
    repo, upstream = fixture_repo(tmp_path)
    cache = tmp_path / "cache"
    checkout = cache / "sources/example--upstream"
    checkout.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", str(upstream), str(checkout)],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "render"
    probe = (
        "import runpy, sys\n"
        "sys.argv = sys.argv[1:]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
        "assert not [m for m in sys.modules if m.split('.')[0] == 'ansible'], 'ansible imported'\n"
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            probe,
            str(repo / CAPABILITY / "publish_amp_skills.py"),
            "--repo",
            str(repo),
            "--output",
            str(output),
            "--cache",
            str(cache),
            "--cached",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rendered = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert rendered == {
        "kept/SKILL.md",
        "templated/SKILL.md",
        "templated/scripts/run.sh",
        "templated/scripts/config.toml",
    }
    assert (output / "templated/scripts/run.sh").stat().st_mode & 0o777 == 0o755
    assert (output / "templated/SKILL.md").stat().st_mode & 0o777 == 0o644
    assert not list(cache.glob("**/hooks/*.json"))

    refused = subprocess.run(
        [
            sys.executable,
            str(repo / CAPABILITY / "publish_amp_skills.py"),
            "--repo",
            str(repo),
            "--output",
            str(output),
            "--cache",
            str(cache),
            "--cached",
        ],
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 1
    assert "Publish output must be empty" in refused.stderr


def test_cached_render_requires_every_git_source(tmp_path: Path) -> None:
    repo, _ = fixture_repo(tmp_path)
    publisher = load_publisher(repo)
    with pytest.raises(ValueError, match="Missing required cached harness sources"):
        publisher.render(repo, tmp_path / "cache", cached=True)


def test_real_catalogue_publishes_the_amp_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = load_publisher(ROOT)
    catalogue = publisher.catalogue
    original = catalogue.declarations

    def local_declarations(repo: Path, home: Path, profile: str, hostname: str):
        env, profile_data, layouts, sources = original(repo, home, profile, hostname)
        return env, profile_data, layouts, [s for s in sources if "local" in s]

    monkeypatch.setattr(catalogue, "declarations", local_declarations)
    files = publisher.render(ROOT, tmp_path / "cache", cached=True)
    skills = {path.parts[0] for path in files}

    assert {"operating-pod042", "commit-msg", "wait-what", "tui-screenshot"} <= skills
    assert "notify" not in skills
    assert not any(skill in skills for skill in ("handoff", "retitle", "pi"))
    assert all(len(path.parts) >= 2 for path in files)
    assert not any(path.suffix == ".j2" for path in files)
    for content, _mode in files.values():
        assert b"{{ " not in content or b"${" in content
