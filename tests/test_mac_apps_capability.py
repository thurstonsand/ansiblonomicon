import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "bootstrap/capabilities/mac-apps/reconcile.py"


def executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\nset -eu\n" + body)
    path.chmod(0o755)


def fixture(
    tmp_path: Path,
    *,
    declared: str = "101\n202\n",
    installed: str = "101 One\n999 Unmanaged\n",
    outdated: str = "101 One\n999 Unmanaged\n",
    brew_outdated: str = '{"formulae": [], "casks": []}',
    brew_after_upgrade: str | None = None,
    fail: str = "",
    check_rc: int = 0,
    mas_outdated_check: bool = False,
):
    binary = tmp_path / "bin"
    binary.mkdir()
    calls = tmp_path / "calls"
    brew_state = tmp_path / "brew-state.json"
    brew_state.write_text(brew_outdated)
    after_upgrade = tmp_path / "brew-state-after-upgrade.json"
    after_upgrade.write_text(brew_after_upgrade or brew_outdated)
    brewfile = tmp_path / "Brewfile.work"
    brewfile.write_text(
        'private_homebrew_dsl(:keep_me)\nbrew "libpq", link: true\n'
        'mas "Declared App", id: 101\n'
    )
    common = (
        'printf "%s %s\\n" "$(basename "$0")" "$*" >> "$CALLS"\n'
        'printf "env HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS=%s '
        "HOMEBREW_NO_REQUIRE_TAP_TRUST=%s MAS_NO_AUTO_INDEX=%s "
        'HOMEBREW_NO_AUTO_UPDATE=%s HOMEBREW_NO_INSTALL_UPGRADE=%s\\n" '
        '"${HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS-}" '
        '"${HOMEBREW_NO_REQUIRE_TAP_TRUST-}" "${MAS_NO_AUTO_INDEX-}" '
        '"${HOMEBREW_NO_AUTO_UPDATE-}" "${HOMEBREW_NO_INSTALL_UPGRADE-}" '
        '>> "$CALLS"\n'
    )
    executable(
        binary / "brew",
        common
        + f'''case "$1 ${{2-}}" in
  "ruby -e")
    [ "${{4-}}" = "--" ]
    [ "${{5-}}" = "$BREWFILE" ]
    [ "$#" -eq 5 ]
    printf "parser-path %s\\n" "$5" >> "$CALLS"
    {"printf 'parser diagnostic marker\\n' >&2; exit 31" if fail == "parser" else f'printf "{declared}"'}
    ;;
esac
case "$*" in
  "bundle check "*)
    [ "{fail}" != check ] || {{ printf 'check diagnostic marker\\n' >&2; exit 29; }}
    {'case "$*" in *--no-upgrade*) exit 0;; *) exit 1;; esac' if mas_outdated_check else f"exit {check_rc}"} ;;
  "outdated --formula --json=v2") cat "$BREW_STATE" ;;
  "upgrade --formula")
    [ "{fail}" = "upgrade" ] && exit 23
    cp "$BREW_AFTER_UPGRADE" "$BREW_STATE"
    ;;
  "install mas") [ "{fail}" = "mas" ] && exit 23 || exit 0 ;;
  "bundle install "*) [ "{fail}" = "install" ] && exit 23 || exit 0 ;;
  "bundle cleanup "*)
    [ "$*" = "bundle cleanup --force --formula --cask --tap --file=$BREWFILE" ]
    [ "{fail}" = "cleanup" ] && exit 23 || exit 0
    ;;
esac
''',
    )
    executable(
        binary / "mas",
        common
        + f'''case "$1" in
  list) printf "{installed}" ;;
  outdated) printf "{outdated}" ;;
esac
''',
    )
    executable(
        binary / "sudo",
        common + ("exit 17\n" if fail == "sudo" else ""),
    )
    env = {
        **os.environ,
        "PATH": f"{binary}:/usr/bin:/bin",
        "CALLS": str(calls),
        "BREWFILE": str(brewfile.resolve()),
        "BREW_STATE": str(brew_state),
        "BREW_AFTER_UPGRADE": str(after_upgrade),
        "HOME": str(tmp_path / "home"),
    }
    env.pop("HOMEBREW_NO_REQUIRE_TAP_TRUST", None)
    return brewfile, calls, env


def invoke(brewfile: Path, env: dict[str, str], stamp: Path, *extra: str):
    return subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "--brewfile",
            str(brewfile),
            "--stamp",
            str(stamp),
            *extra,
        ],
        env=env,
        text=True,
        capture_output=True,
    )


def old_stamp(path: Path) -> tuple[bytes, int, int]:
    path.write_bytes(b"existing stamp metadata\n")
    path.chmod(0o640)
    old = time.time_ns() - 90_000_000_000_000
    os.utime(path, ns=(old, old))
    stat = path.stat()
    return path.read_bytes(), stat.st_mode, stat.st_mtime_ns


def test_due_stamp_updates_declared_mas_and_replaces_stamp(
    tmp_path: Path,
) -> None:
    brewfile, calls, env = fixture(tmp_path)
    stamp = tmp_path / "stamp"
    _, _, old_mtime = old_stamp(stamp)
    result = invoke(brewfile, env, stamp)
    assert result.returncode == 0, result.stderr
    assert stamp.stat().st_mtime_ns > old_mtime
    assert stamp.stat().st_mode & 0o777 == 0o644
    assert "sudo -A mas upgrade 101" in calls.read_text()


def test_recent_stamp_is_unchanged_and_suppresses_upgrades_and_cleanup(
    tmp_path: Path,
) -> None:
    brewfile, calls, env = fixture(tmp_path)
    stamp = tmp_path / "stamp"
    old_stamp(stamp)
    now = time.time_ns()
    os.utime(stamp, ns=(now, now))
    metadata = (stamp.read_bytes(), stamp.stat().st_mode, stamp.stat().st_mtime_ns)
    result = invoke(brewfile, env, stamp)
    assert result.returncode == 0, result.stderr
    output = calls.read_text()
    assert f"brew bundle install --file={brewfile.resolve()} --no-upgrade" in output
    assert "mas upgrade" not in output and "bundle cleanup" not in output
    assert (
        stamp.read_bytes(),
        stamp.stat().st_mode,
        stamp.stat().st_mtime_ns,
    ) == metadata


@pytest.mark.parametrize("failure", ["install", "cleanup", "upgrade", "mas", "sudo"])
def test_failure_preserves_existing_stamp_metadata(
    tmp_path: Path, failure: str
) -> None:
    brewfile, _, env = fixture(tmp_path, fail=failure)
    stamp = tmp_path / "stamp"
    metadata = old_stamp(stamp)
    result = invoke(brewfile, env, stamp)
    assert result.returncode != 0
    assert (
        stamp.read_bytes(),
        stamp.stat().st_mode,
        stamp.stat().st_mtime_ns,
    ) == metadata


def test_check_ignores_pinned_formulae_and_casks(tmp_path: Path) -> None:
    brewfile, calls, env = fixture(
        tmp_path,
        check_rc=0,
        brew_outdated=json.dumps(
            {
                "formulae": [
                    {
                        "name": "wget",
                        "installed_versions": ["1"],
                        "current_version": "2",
                        "pinned": True,
                        "pinned_version": "1",
                    }
                ],
                "casks": [{"name": "firefox"}],
            }
        ),
    )
    result = invoke(brewfile, env, tmp_path / "stamp", "--check")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "mac-apps: current\n"
    assert "brew outdated --formula --json=v2" in calls.read_text()


def test_due_formula_upgrade_updates_transitive_state_once_without_casks_or_pins(
    tmp_path: Path,
) -> None:
    eligible = {
        "name": "transitive-lib",
        "installed_versions": ["1"],
        "current_version": "2",
        "pinned": False,
        "pinned_version": None,
    }
    pinned = {
        "name": "held-tool",
        "installed_versions": ["3"],
        "current_version": "4",
        "pinned": True,
        "pinned_version": "3",
    }
    cask = {"name": "desktop-app", "installed_versions": ["1"]}
    initial = {"formulae": [eligible, pinned], "casks": [cask]}
    remaining = {"formulae": [pinned], "casks": [cask]}
    brewfile, calls, env = fixture(
        tmp_path,
        brew_outdated=json.dumps(initial),
        brew_after_upgrade=json.dumps(remaining),
    )
    stamp = tmp_path / "stamp"

    first = invoke(brewfile, env, stamp)
    assert first.returncode == 0, first.stderr
    assert json.loads((tmp_path / "brew-state.json").read_text()) == remaining

    second = invoke(brewfile, env, stamp)
    assert second.returncode == 0, second.stderr
    assert calls.read_text().splitlines().count("brew upgrade --formula") == 1
    assert json.loads((tmp_path / "brew-state.json").read_text()) == remaining


def test_check_detects_unpinned_formula_drift_without_mutation_or_stamp_write(
    tmp_path: Path,
) -> None:
    state = {
        "formulae": [
            {
                "name": "transitive-lib",
                "installed_versions": ["1"],
                "current_version": "2",
                "pinned": False,
                "pinned_version": None,
            }
        ],
        "casks": [{"name": "desktop-app"}],
    }
    brewfile, _, env = fixture(tmp_path, brew_outdated=json.dumps(state))
    stamp = tmp_path / "stamp"
    metadata = old_stamp(stamp)

    result = invoke(brewfile, env, stamp, "--check")

    assert result.returncode == 1, result.stderr
    assert result.stdout == "mac-apps: drift\n"
    assert json.loads((tmp_path / "brew-state.json").read_text()) == state
    assert (
        stamp.read_bytes(),
        stamp.stat().st_mode,
        stamp.stat().st_mtime_ns,
    ) == metadata


def test_ruby_mas_parser_isolates_brewfile_stdout_and_restores_it(
    tmp_path: Path,
) -> None:
    ruby = shutil.which("ruby")
    if ruby is None:
        pytest.skip("ruby is unavailable")

    ruby_lib = tmp_path / "ruby" / "bundle"
    ruby_lib.mkdir(parents=True)
    (ruby_lib / "brewfile.rb").write_text(
        """module Homebrew
  module Bundle
    Entry = Struct.new(:type, :name, :options)
    class DSL
      attr_reader :entries
      def initialize
        @entries = []
      end
      def mas(name, id:)
        @entries << Entry.new(:mas, name, { id: id })
      end
      def include(path)
        instance_eval(File.read(path), path)
      end
    end
    class Brewfile
      def self.read(file:)
        DSL.new.tap { |dsl| dsl.instance_eval(File.read(file), file) }
      end
    end
  end
end
"""
    )
    included = tmp_path / "included.rb"
    included.write_text(
        'puts "included text log"\nSTDOUT.puts "987654"\n'
        'warn "fixture diagnostic"\nmas "Computed", id: 100 + 23\n'
    )
    brewfile = tmp_path / "Brewfile"
    brewfile.write_text(
        f'puts "top-level text log"\nSTDOUT.puts "456789"\ninclude {str(included)!r}\n'
    )
    ruby_mas_ids = runpy.run_path(str(HELPER))["RUBY_MAS_IDS"]
    result = subprocess.run(
        [ruby, "-I", str(tmp_path / "ruby"), "-e", ruby_mas_ids, "--", str(brewfile)],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "123\n"
    assert result.stderr == (
        "top-level text log\n456789\nincluded text log\n987654\nfixture diagnostic\n"
    )
