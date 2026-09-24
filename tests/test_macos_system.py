import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/macos-system"
SPEC = importlib.util.spec_from_file_location(
    "pam_renderer", CAPABILITY / "pam_renderer.py"
)
assert SPEC and SPEC.loader
pam_renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pam_renderer)


@pytest.fixture
def without_sudo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "blocked-bin"
    binary.mkdir()
    sudo = binary / "sudo"
    sudo.write_text(
        "#!/bin/sh\necho 'unexpected sudo in disposable fixture' >&2\nexit 97\n"
    )
    sudo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("SUDO_ASKPASS", "/bin/false")


def test_personal_pam_canonicalizes_owned_lines_and_preserves_unknown_whitespace() -> (
    None
):
    source = "# header\n\nauth optional /old/pam_reattach.so\n  unknown  line \t\n#auth sufficient pam_tid.so\n"
    assert pam_renderer.render(source, "personal") == (
        "# header\n\n"
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "  unknown  line \t\n"
        "auth       sufficient     pam_tid.so\n"
    )


def test_work_pam_leaves_unmanaged_reattach_in_place_and_deduplicates_tid() -> None:
    source = "auth optional /custom/pam_reattach.so\n#auth sufficient pam_tid.so\nauth sufficient pam_tid.so\nother\n"
    assert pam_renderer.render(source, "work") == (
        "auth optional /custom/pam_reattach.so\n"
        "auth       sufficient     pam_tid.so\n"
        "other\n"
    )


def test_fresh_pam_state_is_valid() -> None:
    assert pam_renderer.render("", "personal") == (
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "auth       sufficient     pam_tid.so\n"
    )


def test_personal_pam_moves_only_reattach_before_existing_tid() -> None:
    source = (
        "\n# __PAM_EOF__\n"
        "auth sufficient pam_tid.so reuse_login\n"
        "auth optional pam_krb5.so try_first_pass\n"
        "auth optional /old/pam_reattach.so option\n"
        "auth sufficient pam_tid.so.other\n\n"
    )
    expected = (
        "\n# __PAM_EOF__\n"
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "auth       sufficient     pam_tid.so\n"
        "auth optional pam_krb5.so try_first_pass\n"
        "auth sufficient pam_tid.so.other\n\n"
    )
    assert pam_renderer.render(source, "personal") == expected
    assert pam_renderer.render(expected, "personal") == expected


def test_native_file_path_applies_checks_and_repeats_without_losing_lines(
    tmp_path: Path,
    without_sudo: None,
) -> None:
    destination = tmp_path / "sudo_local"
    destination.write_text(
        "\n# __PAM_EOF__\n\nauth optional /old/pam_reattach.so\n  unknown \t\n"
        "#auth sufficient pam_tid.so\n\n\n"
    )
    source = tmp_path / "sudo_local.tera"
    source.write_bytes((CAPABILITY / "files/sudo_local.tera").read_bytes())
    # Explicit ownership forces sudo even when it names the current user.
    (tmp_path / "mise.toml").write_text(
        'min_version = "2026.9.11"\n'
        '[vars]\nhost_profile = "personal"\n'
        f"[bootstrap.files.{str(destination)!r}]\n"
        'source = "sudo_local.tera"\n'
        "template = true\n"
        'mode = "0444"\n'
    )
    env = {
        **os.environ,
        "MACOS_SYSTEM_PYTHON": str(ROOT / ".venv/bin/python"),
        "MACOS_SYSTEM_PAM_RENDERER": str(CAPABILITY / "pam_renderer.py"),
    }

    subprocess.run(
        ["mise", "-C", str(tmp_path), "bootstrap", "files", "apply", "--yes"],
        env=env,
        check=True,
    )
    expected = (
        "\n# __PAM_EOF__\n\n"
        "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\n"
        "  unknown \t\n"
        "auth       sufficient     pam_tid.so\n\n\n"
    )
    assert destination.read_text() == expected
    assert destination.stat().st_mode & 0o777 == 0o444
    before = destination.stat().st_mtime_ns
    subprocess.run(
        ["mise", "-C", str(tmp_path), "bootstrap", "files", "apply", "--dry-run"],
        env=env,
        check=True,
    )
    subprocess.run(
        ["mise", "-C", str(tmp_path), "bootstrap", "files", "apply", "--yes"],
        env=env,
        check=True,
    )
    assert destination.stat().st_mtime_ns == before


def test_driver_real_native_fixture_ignores_hostile_ancestor(
    tmp_path: Path,
    without_sudo: None,
) -> None:
    target = tmp_path / "targets/host"
    target.mkdir(parents=True)
    destination = tmp_path / "disposable_pam"
    destination.write_text("# retained without newline")
    hostile = tmp_path / "hostile"
    (tmp_path / "hostile-source").write_text("must not apply")
    (tmp_path / "mise.toml").write_text(
        '[env]\n_.source = "hostile-env.sh"\n'
        f'[bootstrap.files.{str(hostile)!r}]\nsource = "hostile-source"\n'
    )
    (tmp_path / "hostile-env.sh").write_text(
        f"touch '{tmp_path / 'env-was-loaded'}'; exit 91\n"
    )
    (target / "sudo_local.tera").write_bytes(
        (CAPABILITY / "files/sudo_local.tera").read_bytes()
    )
    (target / "mise.permissions.toml").write_text(
        '[vars]\nhost_profile = "work"\n'
        f"[bootstrap.files.{str(destination)!r}]\n"
        'source = "sudo_local.tera"\ntemplate = true\n'
        'mode = "0444"\n'
    )
    result = subprocess.run(
        [
            sys.executable,
            str(CAPABILITY / "reconcile.py"),
            "--target",
            str(target),
            "--profile",
            "work",
            "--sections",
            "permissions",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert destination.read_text() == (
        "# retained without newline\nauth       sufficient     pam_tid.so\n"
    )
    assert destination.stat().st_mode & 0o777 == 0o444
    inode = destination.stat().st_ino
    repeat = subprocess.run(result.args, text=True, capture_output=True, check=False)
    assert repeat.returncode == 0, repeat.stderr
    assert destination.stat().st_ino == inode
    assert not hostile.exists()
    assert not (tmp_path / "env-was-loaded").exists()


def run_driver(
    tmp_path: Path,
    *,
    sections: str,
    check: bool = False,
    mode: str = "",
) -> tuple[subprocess.CompletedProcess[str], dict[str, object], list[str]]:
    target = tmp_path / "targets/host"
    target.mkdir(parents=True)
    binary = tmp_path / "bin"
    binary.mkdir()
    state = tmp_path / "state.json"
    state.write_text(
        '{"defaults":{"com.apple.dock:autohide":false,'
        '"com.apple.finder:ShowPathbar":false},"pam":false,'
        '"hostname":{"HostName":null,"ComputerName":"old",'
        '"LocalHostName":"Thurstons-MacBook-Pro"}}'
    )
    if mode == "converged":
        initial = json.loads(state.read_text())
        initial["defaults"] = dict.fromkeys(initial["defaults"], True)
        initial["pam"] = True
        state.write_text(json.dumps(initial))
    calls = tmp_path / "calls"
    fake = binary / "mise"
    fake.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ['STATE']); s = json.loads(p.read_text())
with open(os.environ['CALLS'], 'a') as f:
 f.write('mise ' + ' '.join(sys.argv[1:]) + ' env=' + os.environ.get('MISE_ENV','') + ' ceiling=' + os.environ.get('MISE_CEILING_PATHS','') + '\\n')
if os.environ.get('MODE') == 'unavailable':
 print(json.dumps({'macos_defaults': {'available': False, 'entries': []}})); sys.exit()
if 'defaults' in sys.argv and 'status' in sys.argv:
 if os.environ.get('MODE') == 'malformed': print('{}'); sys.exit()
 entries=[]
 for pair, value in s['defaults'].items():
  domain, key = pair.split(':', 1)
  section = {'com.apple.dock':'dock', 'com.apple.finder':'finder'}[domain]
  if section in os.environ['MISE_ENV'].split(','):
   entries.append({'domain':domain,'key':key,'state':'set' if value else 'differs'})
 print(json.dumps({'macos_defaults': {'available': True, 'entries': entries}})); sys.exit()
if 'defaults' in sys.argv and 'apply' in sys.argv:
 if os.environ.get('MODE') == 'zero-apply': sys.exit(23)
 if '--dry-run' not in sys.argv:
  for pair in s['defaults']:
   section = 'dock' if pair.startswith('com.apple.dock:') else 'finder'
   if section in os.environ['MISE_ENV'].split(',') and (os.environ.get('MODE') != 'partial-apply' or 'dock' in pair): s['defaults'][pair] = True
  p.write_text(json.dumps(s))
 if os.environ.get('MODE') == 'partial-apply': sys.exit(23)
 sys.exit()
if 'files' in sys.argv and 'status' in sys.argv:
 if os.environ.get('MODE') == 'permission-preflight': print('{}')
 else: print(json.dumps([{'action':'noop' if s['pam'] else 'update'}]))
 sys.exit()
if 'files' in sys.argv and 'apply' in sys.argv:
 if os.environ.get('MODE') == 'pam-apply-fail': sys.exit(23)
 if '--dry-run' not in sys.argv: s['pam']=True; p.write_text(json.dumps(s))
 sys.exit()
sys.exit(90)
"""
    )
    fake.chmod(0o755)
    scutil = binary / "scutil"
    scutil.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys
p=pathlib.Path(os.environ['STATE']); s=json.loads(p.read_text()); key=sys.argv[2]
if sys.argv[1] == '--get':
 if os.environ.get('MODE') == 'scutil-error': print('access denied', file=sys.stderr); sys.exit(5)
 value=s['hostname'][key]
 if key == 'HostName' and value is None: print('HostName: not set', file=sys.stderr); sys.exit(1)
 print(value); sys.exit()
if sys.argv[1] == '--set':
 s['hostname'][key]=sys.argv[3]; p.write_text(json.dumps(s)); sys.exit()
"""
    )
    scutil.chmod(0o755)
    for name in ("sudo", "killall"):
        script = binary / name
        script.write_text(
            "#!/bin/sh\nprintf '%s %s\\n' "
            + name
            + ' "$*" >> "$CALLS"\n'
            + ('exec "$2" "$3" "$4" "$5"\n' if name == "sudo" else "")
            + (
                'if [ "$MODE" = restart-error ] && [ "$1" = Dock ]; then exit 7; fi\n'
                if name == "killall"
                else ""
            )
        )
        script.chmod(0o755)
    command = [
        sys.executable,
        str(CAPABILITY / "reconcile.py"),
        "--target",
        str(target),
        "--profile",
        "work" if "permissions" in sections else "personal",
        "--sections",
        sections,
    ]
    if check:
        command.append("--check")
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "PATH": f"{binary}:/usr/bin:/bin",
            "STATE": str(state),
            "CALLS": str(calls),
            "MODE": mode,
        },
        check=False,
    )
    return (
        result,
        cast(dict[str, object], json.loads(state.read_text())),
        (calls.read_text().splitlines() if calls.exists() else []),
    )


def test_driver_applies_typed_defaults_pam_and_restarts_once(tmp_path: Path) -> None:
    result, state, calls = run_driver(tmp_path, sections="dock,finder,permissions")
    assert result.returncode == 0
    assert state["defaults"] == {
        "com.apple.dock:autohide": True,
        "com.apple.finder:ShowPathbar": True,
    }
    assert state["pam"] is True
    assert [call for call in calls if call.startswith("killall ")] == [
        "killall Dock",
        "killall Finder",
    ]
    mise_calls = [call for call in calls if call.startswith("mise ")]
    assert all(f"ceiling={tmp_path}/targets" in call for call in mise_calls)
    assert any("env=dock,finder" in call for call in mise_calls)
    assert any("env=permissions" in call for call in mise_calls)


def test_driver_check_and_noop_do_not_write_or_restart(tmp_path: Path) -> None:
    result, state, calls = run_driver(
        tmp_path / "check", sections="dock,finder,permissions", check=True
    )
    assert result.returncode == 0
    assert not state["pam"]
    defaults = cast(dict[str, bool], state["defaults"])
    assert not any(defaults.values())
    assert not any(call.startswith(("sudo ", "killall ")) for call in calls)
    assert all("--dry-run" in call for call in calls if " apply " in call)
    result, state, calls = run_driver(
        tmp_path / "noop", sections="dock,finder,permissions", mode="converged"
    )
    assert result.returncode == 0, result.stderr
    assert state["pam"] is True
    assert not any(
        " apply " in call or call.startswith(("sudo ", "killall ")) for call in calls
    )


def test_driver_preflight_failure_blocks_all_writes(tmp_path: Path) -> None:
    result, state, calls = run_driver(
        tmp_path,
        sections="dock,permissions",
        mode="permission-preflight",
    )
    assert result.returncode == 1
    defaults = cast(dict[str, bool], state["defaults"])
    assert not defaults["com.apple.dock:autohide"]
    assert not any(" apply " in call or call.startswith("killall ") for call in calls)


def test_driver_partial_defaults_failure_requeries_and_restarts_applied_domain(
    tmp_path: Path,
) -> None:
    result, state, calls = run_driver(
        tmp_path, sections="dock,finder", mode="partial-apply"
    )
    assert result.returncode == 1
    defaults = cast(dict[str, bool], state["defaults"])
    assert defaults == {
        "com.apple.dock:autohide": True,
        "com.apple.finder:ShowPathbar": False,
    }
    assert [call for call in calls if call.startswith("killall ")] == ["killall Dock"]


def test_driver_restarts_defaults_before_later_pam_apply_failure(
    tmp_path: Path,
) -> None:
    result, state, calls = run_driver(
        tmp_path, sections="dock,permissions", mode="pam-apply-fail"
    )
    assert result.returncode == 1
    defaults = cast(dict[str, bool], state["defaults"])
    assert defaults["com.apple.dock:autohide"]
    assert not defaults["com.apple.finder:ShowPathbar"]
    assert not state["pam"]
    assert [call for call in calls if call.startswith("killall ")] == ["killall Dock"]
    assert calls.index("killall Dock") < next(
        index for index, call in enumerate(calls) if "files apply" in call
    )


def test_driver_zero_write_failure_does_not_restart_and_restart_failure_continues(
    tmp_path: Path,
) -> None:
    result, state, calls = run_driver(
        tmp_path / "zero", sections="dock,finder", mode="zero-apply"
    )
    assert result.returncode == 1
    assert not any(cast(dict[str, bool], state["defaults"]).values())
    assert not any(call.startswith("killall ") for call in calls)
    result, _, calls = run_driver(
        tmp_path / "restart", sections="dock,finder", mode="restart-error"
    )
    assert result.returncode == 1
    assert [call for call in calls if call.startswith("killall ")] == [
        "killall Dock",
        "killall Finder",
    ]


def test_driver_accepts_unset_hostname_and_propagates_native_errors(
    tmp_path: Path,
) -> None:
    result, _, calls = run_driver(tmp_path, sections="hostname", check=True)
    assert result.returncode == 0
    assert "hostname: would set HostName, ComputerName\n" in result.stdout
    assert not any(call.startswith("sudo ") for call in calls)
    for mode in ("unavailable", "malformed"):
        failed, _, failed_calls = run_driver(
            tmp_path / mode, sections="dock", mode=mode
        )
        assert failed.returncode == 1
        assert not any(" apply " in call for call in failed_calls)
    failed, _, failed_calls = run_driver(
        tmp_path / "scutil", sections="hostname", mode="scutil-error"
    )
    assert failed.returncode == 1
    assert "access denied" in failed.stderr
    assert not any(call.startswith("sudo ") for call in failed_calls)


def test_driver_sets_only_drifting_hostname_keys(tmp_path: Path) -> None:
    result, state, calls = run_driver(tmp_path, sections="hostname")
    assert result.returncode == 0
    assert state["hostname"] == {
        "HostName": "Thurstons-MacBook-Pro",
        "ComputerName": "Thurstons-MacBook-Pro",
        "LocalHostName": "Thurstons-MacBook-Pro",
    }
    assert [call for call in calls if call.startswith("sudo ")] == [
        "sudo -A scutil --set HostName Thurstons-MacBook-Pro",
        "sudo -A scutil --set ComputerName Thurstons-MacBook-Pro",
    ]
