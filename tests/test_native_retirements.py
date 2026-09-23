from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "native_retirements", ROOT / "bootstrap/capabilities/retirements/reconcile.py"
)
assert SPEC is not None and SPEC.loader is not None
retirements: Any = module_from_spec(SPEC)
SPEC.loader.exec_module(retirements)


def test_native_retirement_preserves_foreign_content_without_sudo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("mise") is None:
        pytest.skip("mise is required for the native removal regression")
    home = tmp_path / "home"
    retired = home / ".codex/skills/bro"
    (retired / "nested").mkdir(parents=True)
    (retired / "nested/file").write_text("retired")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep").write_text("outside")
    (retired / "external").symlink_to(foreign, target_is_directory=True)
    sibling = retired.parent / "keep.md"
    sibling.write_text("sibling")
    guard = tmp_path / "bin"
    guard.mkdir()
    sudo = guard / "sudo"
    sudo.write_text("#!/bin/sh\necho 'unexpected sudo' >&2\nexit 99\n")
    sudo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{guard}:{os.environ['PATH']}")

    assert retirements.reconcile(home, "pod042", True) == 1
    assert (retired / "nested/file").read_text() == "retired"
    assert retirements.reconcile(home, "pod042", False) == 0
    assert not retired.exists()
    assert sibling.read_text() == "sibling"
    assert (foreign / "keep").read_text() == "outside"
    assert retirements.reconcile(home, "pod042", True) == 0
    assert retirements.reconcile(home, "pod042", False) == 0


def test_work_is_rejected_before_reading_or_mutating_home(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not enabled on ML-DFC6YK6VJQ"):
        retirements.reconcile(tmp_path, "ML-DFC6YK6VJQ", False)


def test_retirement_rejects_parent_escape_but_removes_the_link_itself(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (home / "link").symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match="parent escapes home"):
        retirements.absence_resources(home, ["link/child"])
    assert retirements.absence_resources(home, ["link"]) == {
        "files": {str(home / "link"): {"state": "absent"}},
        "directories": {},
    }


def test_mac_retirement_previews_and_unloads_only_present_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = {
        f"gui/{os.getuid()}/house.thurstons.ghostty-navd",
    }
    removed: list[str] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[0] == "launchctl":
            if argv[1] == "print":
                return subprocess.CompletedProcess(argv, 0 if argv[2] in jobs else 1)
            removed.append(argv[2])
            jobs.remove(argv[2])
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(retirements.subprocess, "run", run)
    assert retirements.reconcile(tmp_path, "Thurstons-MacBook-Pro", True) == 1
    assert removed == []
    assert retirements.reconcile(tmp_path, "Thurstons-MacBook-Pro", False) == 0
    assert removed == [f"gui/{os.getuid()}/house.thurstons.ghostty-navd"]
    assert retirements.reconcile(tmp_path, "Thurstons-MacBook-Pro", True) == 0


def test_native_paths_cover_legacy_removal_contracts() -> None:
    data = tomllib.loads(
        (ROOT / "bootstrap/capabilities/retirements/paths.toml").read_text()
    )
    native = set(data["paths"] + data["macos"]["paths"])
    for legacy in (ROOT / ".ansibleremove", ROOT / "chezmoi/.chezmoiremove"):
        paths = {
            line.strip()
            for line in legacy.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        assert paths <= native


def test_mac_validates_retired_paths_before_unloading_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".config").symlink_to(tmp_path.parent, target_is_directory=True)

    def unexpected_run(*args: object, **kwargs: object) -> None:
        pytest.fail("Retirement ran a command before validating all paths")

    monkeypatch.setattr(retirements.subprocess, "run", unexpected_run)
    with pytest.raises(ValueError, match="parent escapes home"):
        retirements.reconcile(tmp_path, "Thurstons-MacBook-Pro", False)
