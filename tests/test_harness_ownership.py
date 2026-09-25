import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from test_mac_agent_harness import CAPABILITY, fixture_repo, harness


def run_fixture(
    root: Path,
    home: Path,
    repo: Path,
    cache: Path,
    *,
    enabled: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    host = root / "ownership-host.toml"
    enabled_toml = ", ".join(json.dumps(item) for item in (enabled or []))
    (repo / "bootstrap/capabilities/agent-harness/profiles.toml").write_text(
        f"[profiles.personal]\ntarget_agents = [{enabled_toml}]\nexplicit_only = []\n"
    )
    host.write_text(
        """[agent_harness]
profile = "personal"
hostname = "ownership-fixture"
trim_blocks = true
update = "86400s"
manifest = "macos-managed-files.json"
"""
    )
    return subprocess.run(
        [
            sys.executable,
            str(CAPABILITY / "agent_harness_deploy.py"),
            "--repo",
            str(repo),
            "--home",
            str(home),
            "--cache",
            str(cache),
            "--host-config",
            str(host),
            "--cached",
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "MISE_STATE_DIR": str(root / "mise-state")},
        check=False,
    )


def local_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    source = repo / "local-assets"
    skill = source / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\n---\nlocal literal\n")
    (skill / "asset.txt").write_text("local asset\n")
    catalogue(repo).write_text(
        """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "local-one"
skills = { demo = "demo" }
"""
    )
    return home, repo, cache, source


def catalogue(repo: Path) -> Path:
    return repo / "bootstrap/capabilities/agent-harness/catalogue.toml"


def manifest(cache: Path) -> dict[str, list[str]]:
    return json.loads((cache / "macos-managed-files.json").read_text())["plugins"]


def claude_declaration(repo: Path) -> Path:
    return repo / "bootstrap/capabilities/agent-harness/harnesses/claude/mise.toml"


def add_native(
    repo: Path, destination: Path, *, state: str = "present", kind: str = "dotfiles"
) -> None:
    declaration = claude_declaration(repo)
    if state == "present":
        (declaration.parent / "native.txt").write_text("native literal\n")
        value = 'source = "native.txt"\nmode = "copy"'
    else:
        value = 'state = "absent"'
    heading = "dotfiles" if kind == "dotfiles" else "bootstrap.files"
    with declaration.open("a") as stream:
        stream.write(f'\n[{heading}."{destination}"]\n{value}\n')


def test_explicit_empty_enabled_with_native_declarations_writes_no_home_output(
    tmp_path: Path,
) -> None:
    home, repo, cache, _ = local_fixture(tmp_path)
    native = home / ".claude/native.conf"
    add_native(repo, native)

    result = run_fixture(tmp_path, home, repo, cache, enabled=[])

    assert result.returncode == 0, result.stderr
    assert not native.exists()
    assert not (home / ".claude").exists()
    assert manifest(cache) == {f"{repo / 'local-assets'}\0local-one": []}


def test_deleting_last_native_resource_removes_recorded_standalone_file(
    tmp_path: Path,
) -> None:
    home, repo, cache, _ = local_fixture(tmp_path)
    native = home / ".claude/native.conf"
    add_native(repo, native)
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert first.returncode == 0, first.stderr
    assert native.read_text() == "native literal\n"
    assert manifest(cache)["native:claude"] == [".claude/native.conf"]

    declaration = claude_declaration(repo)
    declaration.write_text(declaration.read_text().split("\n[dotfiles.", 1)[0] + "\n")
    second = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert second.returncode == 0, second.stderr
    assert not native.exists()
    assert manifest(cache)["native:claude"] == []


@pytest.mark.parametrize("owner_state", ["active", "omitted"])
def test_native_absent_rejects_plugin_destination_before_mutation(
    tmp_path: Path, owner_state: str
) -> None:
    home, repo, cache, _ = local_fixture(tmp_path)
    destination = home / ".claude/skills/demo/SKILL.md"
    if owner_state == "omitted":
        initial = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
        assert initial.returncode == 0, initial.stderr
        catalogue(repo).write_text('[[sources]]\nlocal = "local-assets"\n')
    add_native(repo, destination, state="absent", kind="files")
    before_file = destination.read_bytes() if destination.exists() else None
    manifest_path = cache / "macos-managed-files.json"
    before_manifest = manifest_path.read_bytes() if manifest_path.exists() else None

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert result.returncode == 1
    expected = (
        "conflicts with desired owner" if owner_state == "active" else "is retained by"
    )
    assert expected in result.stderr
    assert (destination.read_bytes() if destination.exists() else None) == before_file
    assert (
        manifest_path.read_bytes() if manifest_path.exists() else None
    ) == before_manifest


def test_cross_native_absence_listed_first_rejects_present_collision(
    tmp_path: Path,
) -> None:
    home, repo, cache, _ = local_fixture(tmp_path)
    destination = home / ".claude/shared.conf"
    absent = repo / "bootstrap/capabilities/agent-harness/harnesses/absent"
    present = repo / "bootstrap/capabilities/agent-harness/harnesses/present"
    absent.mkdir()
    present.mkdir()
    (absent / "mise.toml").write_text(
        f'[harness]\nname = "absent"\nskills_root = "{home}/.absent/skills"\n'
        'name_transform = "preserve"\n'
        f'[bootstrap.files."{destination}"]\nstate = "absent"\n'
    )
    (present / "native.txt").write_text("must not be written\n")
    (present / "mise.toml").write_text(
        f'[harness]\nname = "present"\nskills_root = "{home}/.present/skills"\n'
        'name_transform = "preserve"\n'
        f'[dotfiles."{destination}"]\nsource = "native.txt"\nmode = "copy"\n'
    )
    manifest_path = cache / "macos-managed-files.json"

    result = run_fixture(tmp_path, home, repo, cache, enabled=["absent", "present"])

    assert result.returncode == 1
    assert "Conflicting native harness destination" in result.stderr
    assert not destination.exists()
    assert not manifest_path.exists()


def test_proved_missing_owner_is_allowed_while_new_owner_is_validated(
    tmp_path: Path,
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert first.returncode == 0, first.stderr
    shutil.rmtree(source / "demo")
    second = source / "second"
    second.mkdir()
    (second / "SKILL.md").write_text("---\nname: second\n---\nsecond\n")
    catalogue(repo).write_text(
        '[[sources]]\nlocal = "local-assets"\n'
        '[[sources.plugins]]\nname = "local-one"\nskills = { demo = "demo" }\n'
        '[[sources.plugins]]\nname = "local-two"\nskills = { second = "second" }\n'
    )

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert result.returncode == 0, result.stderr
    assert (home / ".claude/skills/second/SKILL.md").exists()
    assert not (home / ".claude/skills/demo/SKILL.md").exists()


def test_local_assets_are_symlinks_and_deleted_asset_unlinks_without_siblings(
    tmp_path: Path,
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert first.returncode == 0, first.stderr
    deployed = home / ".claude/skills/demo/asset.txt"
    assert deployed.is_symlink()
    assert os.readlink(deployed) == str(source / "demo/asset.txt")
    assert deployed.read_text() == "local asset\n"

    foreign = deployed.parent / "repository-sibling.txt"
    foreign.write_text("foreign remains\n")
    (source / "demo/asset.txt").unlink()
    second = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert second.returncode == 0, second.stderr
    assert not deployed.exists() and not deployed.is_symlink()
    assert foreign.read_text() == "foreign remains\n"
    assert (
        ".claude/skills/demo/asset.txt" not in manifest(cache)[f"{source}\0local-one"]
    )


@pytest.mark.parametrize("selection", ["include", "explicit"])
def test_proven_named_selection_allows_upstream_removal_only_after_success(
    tmp_path: Path, selection: str
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    if selection == "include":
        (source / ".claude-plugin").mkdir()
        (source / ".claude-plugin/plugin.json").write_text(
            '{"name":"local-one","skills":"skills"}\n'
        )
        (source / "demo").rename(source / "skills")
        declaration = 'include_skills = ["skills"]'
        selected = source / "skills"
    else:
        declaration = 'skills = { demo = "demo" }'
        selected = source / "demo"
    catalogue(repo).write_text(
        '[[sources]]\nlocal = "local-assets"\n[[sources.plugins]]\n'
        f'name = "local-one"\n{declaration}\n'
    )
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert first.returncode == 0, first.stderr
    deployed = (
        home / ".claude/skills" / ("skills" if selection == "include" else "demo")
    )
    foreign = deployed / "foreign.txt"
    foreign.write_text("keep\n")
    if selection == "explicit":
        (selected / "SKILL.md").unlink()
        assert (selected / "asset.txt").exists()
    else:
        shutil.rmtree(selected)

    removed = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    repeated = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert (removed.returncode, repeated.returncode) == (0, 0), removed.stderr
    assert foreign.read_text() == "keep\n"
    assert not (deployed / "SKILL.md").exists()
    owner = f"{source}\0local-one"
    document = json.loads((cache / "macos-managed-files.json").read_text())
    assert document["version"] == 3
    assert document["plugins"][owner] == []
    assert owner in document["selection_proofs"]


def test_proved_explicit_selection_still_requires_available_source_root(
    tmp_path: Path,
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert first.returncode == 0, first.stderr
    before = (cache / "macos-managed-files.json").read_bytes()
    shutil.rmtree(source)

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert result.returncode == 1
    assert "source root is not an available directory" in result.stderr
    assert (cache / "macos-managed-files.json").read_bytes() == before


def test_apply_failure_keeps_validated_proof_for_retry_after_upstream_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    manifest_path = cache / "macos-managed-files.json"
    native_apply = harness.apply_native

    def fail_apply(target: Path, state: Path, check: bool) -> None:
        native_apply(target, state, check)
        raise subprocess.CalledProcessError(1, "mise")

    monkeypatch.setattr(harness, "apply_native", fail_apply)
    with pytest.raises(subprocess.CalledProcessError):
        harness.reconcile(
            repo,
            home,
            cache,
            "personal",
            "ownership-fixture",
            check=False,
            cached=True,
            manifest_name="macos-managed-files.json",
            trim_blocks=True,
        )
    owner = f"{source}\0local-one"
    pending = json.loads(manifest_path.read_text())
    assert pending["selection_proofs"][owner]
    deployed = home / ".claude/skills/demo/SKILL.md"
    assert deployed.is_symlink()
    (source / "demo/SKILL.md").unlink()

    monkeypatch.setattr(harness, "apply_native", native_apply)

    harness.reconcile(
        repo,
        home,
        cache,
        "personal",
        "ownership-fixture",
        check=False,
        cached=True,
        manifest_name="macos-managed-files.json",
        trim_blocks=True,
    )

    assert json.loads(manifest_path.read_text())["plugins"][owner] == []
    assert not deployed.exists() and not deployed.is_symlink()


@pytest.mark.parametrize("change", ["explicit-path", "unknown-include"])
def test_changed_named_selection_is_strict_and_preserves_deployment(
    tmp_path: Path, change: str
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert first.returncode == 0, first.stderr
    deployed = home / ".claude/skills/demo/SKILL.md"
    before_manifest = (cache / "macos-managed-files.json").read_bytes()
    if change == "explicit-path":
        declaration = 'skills = { demo = "missing" }'
    else:
        (source / ".claude-plugin").mkdir()
        (source / ".claude-plugin/plugin.json").write_text(
            '{"name":"local-one","skills":"demo"}\n'
        )
        declaration = 'include_skills = ["unknown"]'
    catalogue(repo).write_text(
        '[[sources]]\nlocal = "local-assets"\n[[sources.plugins]]\n'
        f'name = "local-one"\n{declaration}\n'
    )

    rejected = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert rejected.returncode == 1
    assert deployed.read_text() == "---\nname: demo\n---\nlocal literal\n"
    assert (cache / "macos-managed-files.json").read_bytes() == before_manifest


def test_local_links_inherit_source_modes_while_git_copies_are_canonical(
    tmp_path: Path,
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    local_skill = source / "demo/SKILL.md"
    local_skill.chmod(0o664)
    local_agent = source / "helper.md"
    local_agent.write_text("---\nname: helper\n---\nlocal helper\n")
    local_agent.chmod(0o775)
    catalogue(repo).write_text(
        """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "local-one"
skills = { demo = "demo" }
agents = { helper = "helper.md" }
[[sources]]
repo = "example/catalogue"
[[sources.plugins]]
name = "fixture"
skills = { git-demo = "demo" }
agents = { git-helper = "agents/helper.md" }
"""
    )
    git_skill = cache / "example--catalogue/demo/SKILL.md"
    git_agent = cache / "example--catalogue/agents/helper.md"
    git_skill.chmod(0o664)
    git_agent.chmod(0o664)

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])

    assert result.returncode == 0, result.stderr
    deployed_local_skill = home / ".claude/skills/demo/SKILL.md"
    deployed_local_agent = home / ".claude/agents/helper.md"
    assert deployed_local_skill.is_symlink()
    assert deployed_local_agent.is_symlink()
    assert deployed_local_skill.resolve() == local_skill.resolve()
    assert deployed_local_agent.resolve() == local_agent.resolve()
    assert deployed_local_skill.stat().st_mode & 0o777 == 0o664
    assert deployed_local_agent.stat().st_mode & 0o777 == 0o775
    assert local_skill.stat().st_mode & 0o777 == 0o664
    assert local_agent.stat().st_mode & 0o777 == 0o775
    deployed_git_skill = home / ".claude/skills/git-demo/SKILL.md"
    deployed_git_agent = home / ".claude/agents/git-helper.md"
    assert deployed_git_skill.is_file() and not deployed_git_skill.is_symlink()
    assert deployed_git_agent.is_file() and not deployed_git_agent.is_symlink()
    assert deployed_git_skill.stat().st_mode & 0o777 == 0o644
    assert deployed_git_agent.stat().st_mode & 0o777 == 0o644
    assert git_skill.stat().st_mode & 0o777 == 0o664
    assert git_agent.stat().st_mode & 0o777 == 0o664


def test_omitted_owner_blocks_new_plugin_from_claiming_its_destination(
    tmp_path: Path,
) -> None:
    home, repo, cache, _source = local_fixture(tmp_path)
    assert run_fixture(tmp_path, home, repo, cache, enabled=["claude"]).returncode == 0
    deployed = home / ".claude/skills/demo/SKILL.md"
    original_target = os.readlink(deployed)
    catalogue(repo).write_text(
        """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "local-two"
skills = { demo = "demo" }
"""
    )

    collision = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert collision.returncode == 1
    assert "is retained by" in collision.stderr
    assert "local-one" in collision.stderr and "local-two" in collision.stderr
    assert deployed.is_symlink() and os.readlink(deployed) == original_target
    assert deployed.read_text() == "---\nname: demo\n---\nlocal literal\n"


@pytest.mark.parametrize("transition", ["selector", "enabled-empty"])
def test_harness_selection_removal_retires_owned_outputs(
    tmp_path: Path, transition: str
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    assert run_fixture(tmp_path, home, repo, cache, enabled=["claude"]).returncode == 0
    deployed = home / ".claude/skills/demo/SKILL.md"
    assert deployed.is_symlink()
    if transition == "selector":
        amp = repo / "bootstrap/capabilities/agent-harness/harnesses/amp"
        amp.mkdir()
        (amp / "mise.toml").write_text(
            f'''[harness]
name = "amp"
skills_root = "{home}/.amp/skills"
name_transform = "preserve"
'''
        )
        catalogue(repo).write_text(
            """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "local-one"
target_agents = ["amp"]
skills = { demo = "demo" }
"""
        )
        result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    else:
        result = run_fixture(tmp_path, home, repo, cache, enabled=[])
    assert result.returncode == 0, result.stderr
    assert not deployed.exists() and not deployed.is_symlink()
    assert manifest(cache)[f"{source}\0local-one"] == []


def test_repeated_same_plugin_asset_deduplicates(
    tmp_path: Path,
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    repeated = """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "sameassetdedupe"
skills = { demo = "demo" }
[[sources.plugins]]
name = "sameassetdedupe"
skills = { demo = "demo" }
"""
    catalogue(repo).write_text(repeated)
    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert result.returncode == 0, result.stderr
    deployed = home / ".claude/skills/demo/SKILL.md"
    assert deployed.is_symlink()
    assert os.readlink(deployed) == str(source / "demo/SKILL.md")
    assert (
        manifest(cache)[f"{source}\0sameassetdedupe"].count(
            ".claude/skills/demo/SKILL.md"
        )
        == 1
    )


def test_repeated_same_plugin_contradictory_remove_is_rejected(
    tmp_path: Path,
) -> None:
    home, repo, cache, _source = local_fixture(tmp_path)
    repeated = """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "sameassetdedupe"
skills = { demo = "demo" }
"""
    catalogue(repo).write_text(
        repeated
        + """[[sources.plugins]]
name = "sameassetdedupe"
remove = true
"""
    )
    rejected = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert rejected.returncode == 1
    assert "Plugin declared both enabled and removed" in rejected.stderr
    assert not (home / ".claude/skills/demo/SKILL.md").exists()
    assert not (cache / "macos-managed-files.json").exists()


def test_offline_remove_repeats_after_checkout_source_is_deleted(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo, cache = fixture_repo(tmp_path, home)
    assert run_fixture(tmp_path, home, repo, cache, enabled=["claude"]).returncode == 0
    skill = home / ".claude/skills/demo/SKILL.md"
    catalogue(repo).write_text(
        """[[sources]]
repo = "example/catalogue"
[[sources.plugins]]
name = "fixture"
remove = true
"""
    )
    shutil.rmtree(cache / "example--catalogue")
    first = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    second = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert (first.returncode, second.returncode) == (0, 0), (
        first.stderr,
        second.stderr,
    )
    assert not skill.exists()
    assert manifest(cache)["example/catalogue\0fixture"] == []


def test_malformed_cross_owner_inventory_is_rejected_without_mutation(
    tmp_path: Path,
) -> None:
    home, repo, cache, _ = local_fixture(tmp_path)
    owned = home / ".claude/skills/demo/SKILL.md"
    owned.parent.mkdir(parents=True)
    owned.write_text("foreign literal\n")
    data = {
        "version": 3,
        "plugins": {
            "owner-a": [str(owned.relative_to(home))],
            "owner-b": [str(owned.relative_to(home))],
        },
        "selection_proofs": {},
    }
    manifest_path = cache / "macos-managed-files.json"
    manifest_path.write_text(json.dumps(data))
    before = manifest_path.read_text()

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert result.returncode == 1
    assert "Malformed harness ownership manifest shares" in result.stderr
    assert "owner-a" in result.stderr and "owner-b" in result.stderr
    assert owned.read_text() == "foreign literal\n"
    assert manifest_path.read_text() == before


def test_non_v3_inventory_is_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "macos-managed-files.json"
    manifest_path.write_text(json.dumps({"version": 2, "plugins": {}}))

    with pytest.raises(ValueError, match="Malformed harness ownership manifest"):
        harness.load_inventory(manifest_path)


def test_in_home_parent_symlink_is_rejected_and_external_target_unchanged(
    tmp_path: Path,
) -> None:
    home, repo, cache, _ = local_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_text("unchanged\n")
    (home / ".claude").symlink_to(outside, target_is_directory=True)

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert result.returncode == 1
    assert "Managed path has a symlink ancestor" in result.stderr
    assert marker.read_text() == "unchanged\n"
    assert not (outside / "skills/demo/SKILL.md").exists()


def test_explicit_resolved_remove_cannot_delete_another_retained_owner(
    tmp_path: Path,
) -> None:
    home, repo, cache, source = local_fixture(tmp_path)
    assert run_fixture(tmp_path, home, repo, cache, enabled=["claude"]).returncode == 0
    deployed = home / ".claude/skills/demo/SKILL.md"
    original_target = os.readlink(deployed)
    catalogue(repo).write_text(
        """[[sources]]
local = "local-assets"
[[sources.plugins]]
name = "remove-other"
remove = true
skills = { demo = "demo" }
"""
    )

    result = run_fixture(tmp_path, home, repo, cache, enabled=["claude"])
    assert result.returncode == 1
    assert "Resolved removal" in result.stderr and "is retained by" in result.stderr
    assert "local-one" in result.stderr and "remove-other" in result.stderr
    assert deployed.is_symlink() and os.readlink(deployed) == original_target
    assert deployed.read_text() == "---\nname: demo\n---\nlocal literal\n"
    assert manifest(cache)[f"{source}\0local-one"]
