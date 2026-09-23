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

CATALOGUE = REPO / "bootstrap/capabilities/agent-harness/catalogue.py"
catalogue_spec = importlib.util.spec_from_file_location("catalogue_test", CATALOGUE)
assert catalogue_spec is not None and catalogue_spec.loader is not None
catalogue = importlib.util.module_from_spec(catalogue_spec)
catalogue_spec.loader.exec_module(catalogue)


def asymmetric_catalogue(repo: Path) -> None:
    (repo / "ansible/roles/agent_harness/vars").mkdir(parents=True)
    (repo / "ansible/playbooks").mkdir()
    (repo / "ansible/models.yml").write_text("models: {}\n")
    (repo / "ansible/template.txt").write_text("looked-up\n")
    capability = repo / "bootstrap/capabilities/agent-harness"
    for name, skills, agents in (
        ("claude", "~/personal/skills", "~/personal/agents"),
        ("amp", "~/amp/skills", None),
    ):
        directory = capability / "harnesses" / name
        directory.mkdir(parents=True)
        directory.joinpath("mise.toml").write_text(
            f'[harness]\nname = "{name}"\nskills_root = "{skills}"\n'
            + (f'agents_root = "{agents}"\n' if agents else "")
            + 'name_transform = "preserve"\n'
        )
    (capability / "profiles.toml").write_text(
        """[profiles.personal]
target_agents = ["claude", "amp"]
explicit_only = ["amp"]
[profiles.work]
target_agents = ["claude"]
explicit_only = []
[profiles.pod042]
target_agents = ["claude", "amp"]
explicit_only = ["amp"]
"""
    )
    (repo / "ansible/roles/agent_harness/vars/agents.yml").write_text(
        """agent_harness_agents:
  claude:
    skills_dir: "{{ ansible_facts.env.HOME }}/{{ 'work' if ansible_hostname == 'work-mac' else 'personal' }}/skills"
    agents_dir: "{{ ansible_facts.env.HOME }}/{{ 'work' if ansible_hostname == 'work-mac' else 'personal' }}/agents"
    name_transform: preserve
  amp:
    skills_dir: "{{ ansible_facts.env.HOME }}/amp/skills"
    agents_dir: null
    name_transform: preserve
"""
    )
    (capability / "catalogue.toml").write_text(
        """[[sources]]
local = "plugins"
[[sources.plugins]]
name = "fixture"
skills = { common = "common" }
agents = { helper = "helper.md" }
exclude_data = ["*.pyc"]
[[sources.plugins]]
name = "fixture"
target_agents = ["amp"]
skills = { amp-only = "amp-only" }
[[sources]]
local = "plugins"
included_on = ["work"]
[[sources.plugins]]
name = "fixture"
skills = { work-only = "work-only" }
[[sources]]
local = "plugins"
excluded_on = ["work"]
[[sources.plugins]]
name = "fixture"
skills = { not-work = "not-work" }
"""
    )
    plugins = repo / "plugins"
    plugins.mkdir()
    (plugins / "helper.md").write_text("---\nname: helper\n---\nhelper\n")
    (plugins / "helper.md").chmod(0o644)
    for name in ("common", "amp-only", "work-only", "not-work"):
        skill = plugins / name
        skill.mkdir()
        (skill / "SKILL.md.j2").write_text(
            "---\nname: " + name + "\n---\n{{ ansible_hostname }} "
            "{{ lookup('file', playbook_dir + '/../template.txt') }}\n"
        )
    script = plugins / "common/run.sh"
    script.write_bytes(b"#!/bin/sh\necho fixture\n")
    script.chmod(0o755)
    (plugins / "common/ignored.pyc").write_bytes(b"ignored")


def test_explicit_profiles_render_literal_outputs_without_writes(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    asymmetric_catalogue(repo)
    home = tmp_path / "destination"
    cache = tmp_path / "cache"

    personal = catalogue.render_files(
        repo, home, cache, "personal", "personal-mac", trim_blocks=False
    )
    work = catalogue.render_files(
        repo, home, cache, "work", "work-mac", trim_blocks=False
    )
    pod = catalogue.render_files(
        repo, home, cache, "pod042", "pod042", trim_blocks=False
    )

    assert {
        str(path.relative_to(home)): (content, mode)
        for path, (content, mode) in personal.items()
    } == {
        "personal/skills/common/SKILL.md": (
            b"---\nname: common\n---\npersonal-mac looked-up\n",
            0o644,
        ),
        "personal/skills/common/run.sh": (b"#!/bin/sh\necho fixture\n", 0o755),
        "personal/skills/not-work/SKILL.md": (
            b"---\nname: not-work\n---\npersonal-mac looked-up\n",
            0o644,
        ),
        "personal/agents/helper.md": (
            b"---\nname: helper\n---\nhelper\n",
            0o644,
        ),
        "amp/skills/amp-only/SKILL.md": (
            b"---\nname: amp-only\n---\npersonal-mac looked-up\n",
            0o644,
        ),
    }
    assert {
        str(path.relative_to(home)): (content, mode)
        for path, (content, mode) in work.items()
    } == {
        "personal/skills/common/SKILL.md": (
            b"---\nname: common\n---\nwork-mac looked-up\n",
            0o644,
        ),
        "personal/skills/common/run.sh": (b"#!/bin/sh\necho fixture\n", 0o755),
        "personal/skills/work-only/SKILL.md": (
            b"---\nname: work-only\n---\nwork-mac looked-up\n",
            0o644,
        ),
        "personal/agents/helper.md": (
            b"---\nname: helper\n---\nhelper\n",
            0o644,
        ),
    }
    assert {
        str(path.relative_to(home)): (content, mode)
        for path, (content, mode) in pod.items()
    } == {
        "personal/skills/common/SKILL.md": (
            b"---\nname: common\n---\npod042 looked-up\n",
            0o644,
        ),
        "personal/skills/common/run.sh": (b"#!/bin/sh\necho fixture\n", 0o755),
        "personal/skills/not-work/SKILL.md": (
            b"---\nname: not-work\n---\npod042 looked-up\n",
            0o644,
        ),
        "personal/agents/helper.md": (
            b"---\nname: helper\n---\nhelper\n",
            0o644,
        ),
        "amp/skills/amp-only/SKILL.md": (
            b"---\nname: amp-only\n---\npod042 looked-up\n",
            0o644,
        ),
    }
    assert not home.exists()
    assert not cache.exists()


def test_render_files_applies_explicit_trim_policy_to_host_conditionals(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    asymmetric_catalogue(repo)
    template = repo / "plugins/common/conditional.txt.j2"
    template.write_text(
        "before\n{% if ansible_hostname == 'personal-mac' %}\nmac-only\n{% endif %}\nafter\n"
    )
    home = tmp_path / "destination"
    cache = tmp_path / "cache"
    output = home / "personal/skills/common/conditional.txt"

    untrimmed = catalogue.render_files(
        repo, home, cache, "personal", "personal-mac", trim_blocks=False
    )
    trimmed = catalogue.render_files(
        repo, home, cache, "personal", "personal-mac", trim_blocks=True
    )

    assert untrimmed[output][0] == b"before\n\nmac-only\n\nafter\n"
    assert trimmed[output][0] == b"before\nmac-only\nafter\n"


def test_enabled_harness_native_dotfile_template_is_composed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    asymmetric_catalogue(repo)
    declaration = repo / "bootstrap/capabilities/agent-harness/harnesses/claude"
    template = declaration / "settings.toml.tera"
    template.write_text('channel = "{{ channel }}"\n')
    with (declaration / "mise.toml").open("a") as config:
        config.write(
            """
[vars]
channel = "stable"
[dotfiles."~/.claude/settings.toml"]
source = "settings.toml.tera"
mode = "template"
[bootstrap.files."~/.claude/credentials"]
source = "settings.toml.tera"
template = true
mode = "0600"
[bootstrap.files."~/.claude/retired"]
state = "absent"
"""
        )
    home = tmp_path / "home"
    resources = catalogue.native_resources(repo, home, ["claude"])
    assert [resource["kind"] for resource in resources] == [
        "dotfiles",
        "files",
        "files",
    ]
    assert resources[0]["declaration"]["mode"] == "template"
    assert resources[1]["declaration"]["template"] is True
    assert resources[1]["declaration"]["mode"] == "0600"
    assert resources[2]["declaration"] == {"state": "absent"}


def test_profile_and_linux_layout() -> None:
    _, profile, layouts, sources = catalogue.declarations(
        REPO, harness.HOME, "pod042", "pod042"
    )
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
        Path(catalogue.filters.__file__)
        == REPO / "ansible/roles/agent_harness/filter_plugins/harness_filters.py"
    )
    assert any(source.get("repo") == "Shpigford/nurb" for source in sources)
    assert not any(
        source.get("local", "").endswith("agents/work") for source in sources
    )


def test_local_resources_all_platforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = catalogue.declarations

    def local_declarations(repo: Path, home: Path, profile_name: str, hostname: str):
        env, profile, layouts, sources = original(repo, home, profile_name, hostname)
        return (
            env,
            profile,
            layouts,
            [source for source in sources if "local" in source],
        )

    monkeypatch.setattr(catalogue, "declarations", local_declarations)
    home = tmp_path / "home"
    cache = home / ".cache/ansiblonomicon-harness"
    files = catalogue.render_files(
        REPO, home, cache, "pod042", "pod042", trim_blocks=False
    )
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
    assert not amp
    handoff = files[home / ".claude/skills/handoff/SKILL.md"][0].decode()
    assert "{{" not in handoff
    assert "{%" not in handoff
    assert "claude-code-auto-title" not in handoff
    assert (REPO / "ansible/session-title-prompt.txt").read_text().strip() in handoff
    notify = home / ".pi/agent/skills/notify/scripts/notify.sh"
    source = REPO / "agents/project-management/skills/notify/scripts/notify.sh"
    assert files[notify][1] == source.stat().st_mode & 0o777
    assert b"fnox-host" in files[notify][0]
    assert not any(path.endswith(".j2") for path in paths)
    assert not any(
        "settings.json" in path or path.endswith("AGENTS.md") for path in paths
    )


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown harness profile: missing"):
        catalogue.declarations(REPO, harness.HOME, "missing", "pod042")


def test_pod042_adapter_uses_common_deployment_engine() -> None:
    assert harness.engine.__file__ == str(
        REPO / "bootstrap/capabilities/agent-harness/agent_harness_deploy.py"
    )
    host = harness.engine.load_host(
        REPO / "bootstrap/targets/pod042/agent-harness/host.toml"
    )
    assert host.update == "always"
    assert host.trim_blocks is False


def test_refuse_manifest_escape(tmp_path: Path) -> None:
    cache = tmp_path / ".cache/ansiblonomicon-harness"
    cache.mkdir(parents=True)
    (cache / "pod042-managed-files.json").write_text(json.dumps(["../outside"]))
    inventory, proofs, legacy = harness.engine.load_inventory(
        cache / "pod042-managed-files.json"
    )
    assert legacy is True
    assert proofs == {}
    roots = (tmp_path / ".codex/skills",)
    with pytest.raises(ValueError, match=r"outside|escapes"):
        harness.engine.validate_destination(
            tmp_path / inventory["legacy"][0], tmp_path, roots
        )


def test_native_hook_operator_ownership() -> None:
    config = (REPO / "bootstrap/targets/pod042/mise.agent-harness.toml").read_text()
    assert "sudo -u thurstonsand env -i" in config
    assert "HOME=/home/thurstonsand" in config
    assert "uv run --script" in config
    assert "run //:agent-config" in config
    assert "chezmoi" not in config
    assert "ansible-playbook" not in config
    assert "os.getuid() != 1000" in SCRIPT.read_text()
    assert "os.getgid() != 1000" in SCRIPT.read_text()
