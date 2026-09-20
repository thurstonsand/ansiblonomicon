import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
_mise = shutil.which("mise")
assert _mise is not None
MISE = Path(_mise)
SOFTWARE = ROOT / "bootstrap/capabilities/software"
UVC_REPO = SOFTWARE / "uvc-repo.py"


def run(
    *args: str, env: dict[str, str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )


def executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nset -eu\n{body}\n")
    path.chmod(0o755)


def file_snapshot(root: Path) -> dict[str, tuple[bytes, int, int, int, int]]:
    return {
        str(path.relative_to(root)): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mode,
            path.stat().st_mtime_ns,
            path.stat().st_ctime_ns,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def isolated(tmp_path: Path) -> tuple[dict[str, str], Path, Path, Path, Path]:
    project = tmp_path / "project"
    targets = project / "bootstrap/targets"
    personal = targets / "Thurstons-MacBook-Pro"
    work = targets / "ML-DFC6YK6VJQ"
    for target, source_target in (
        (personal, ROOT / "bootstrap/targets/Thurstons-MacBook-Pro"),
        (work, ROOT / "bootstrap/targets/ML-DFC6YK6VJQ"),
    ):
        target.mkdir(parents=True)
        for name in (
            "mise.software.toml",
            "mise.software-files.toml",
            "mise.pi.toml",
        ):
            source = source_target / name
            if source.exists():
                shutil.copy2(source, target / name)
        (target / "software").symlink_to(SOFTWARE)
    shutil.copytree(ROOT / "ansible/roles/uvc_util/files", personal / "uvc-files")
    shutil.copytree(ROOT / "ansible/roles/uvc_util/files", work / "uvc-files")
    for role in ("sessions", "shp"):
        shutil.copytree(
            ROOT / f"ansible/roles/{role}/files/{role}",
            project / f"ansible/roles/{role}/files/{role}",
        )

    home = tmp_path / "home"
    fakebin = tmp_path / "bin"
    private_tmp = tmp_path / "tmp"
    for directory in (home, fakebin, private_tmp):
        directory.mkdir()
    private_tmp.chmod(0o700)
    env = {
        "HOME": str(home),
        "PATH": (
            f"{fakebin}:{Path(sys.executable).parent}:{MISE.parent}:/usr/bin:/bin"
        ),
        "TMPDIR": str(private_tmp),
        "MISE_PROJECT_ROOT": str(project),
        "MISE_DATA_DIR": str(tmp_path / "mise-data"),
        "MISE_CACHE_DIR": str(tmp_path / "mise-cache"),
        "MISE_STATE_DIR": str(tmp_path / "mise-state"),
        "MISE_CONFIG_DIR": str(tmp_path / "mise-config"),
        "MISE_GLOBAL_CONFIG_FILE": str(tmp_path / "absent-global.toml"),
        "MISE_SYSTEM_CONFIG_FILE": str(tmp_path / "absent-system.toml"),
        "MISE_CEILING_PATHS": str(targets),
        "MISE_NO_ENV": "1",
        "MISE_DISABLE_TOOLS": "1",
        "MISE_AUTO_INSTALL": "0",
        "MISE_YES": "1",
        "LC_ALL": "C.UTF-8",
    }
    return env, fakebin, project, personal, work


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def remote_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    (source / "src").mkdir(parents=True)
    git(source, "init", "-b", "main")
    git(source, "config", "user.email", "test@example.com")
    git(source, "config", "user.name", "Test")
    for name in ("uvc-util.m", "UVCController.m", "UVCType.m", "UVCValue.m", "one.h"):
        (source / "src" / name).write_text(name)
    git(source, "add", ".")
    git(source, "commit", "-m", "initial")
    git(tmp_path, "clone", "--bare", str(source), str(remote))
    return source, remote


def test_go_native_missing_fresh_due_failure_and_rebuild(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    reconcile = personal / "software/reconcile"
    log = Path(env["HOME"]) / "go.log"
    executable(
        fakebin / "go",
        'echo "$*" >> "$HOME/go.log"\n'
        'if [ "${FAIL_GO:-}" = 1 ]; then exit 7; fi\n'
        'if [ "$1" = -C ]; then shift 2; fi\n'
        'if [ "${1:-}" = build ]; then while [ "$1" != -o ]; do shift; done; mkdir -p "$(dirname "$2")"; printf built > "$2"; fi',
    )
    first = run(str(reconcile), "sessions", str(personal), "apply", env=env)
    assert first.returncode == 0, first.stderr
    output = Path(env["HOME"]) / ".local/bin/sessions"
    stamp = Path(env["HOME"]) / ".cache/ansiblonomicon/sessions/upgrade.stamp"
    assert output.read_text() == "built"
    assert stamp.stat().st_mode & 0o777 == 0o644
    assert log.read_text().splitlines()[:2] == ["get -u -t ./...", "mod tidy"]
    count = len(log.read_text().splitlines())
    assert (
        run(str(reconcile), "sessions", str(personal), "apply", env=env).returncode == 0
    )
    assert len(log.read_text().splitlines()) == count
    output.unlink()
    assert (
        run(str(reconcile), "sessions", str(personal), "apply", env=env).returncode == 0
    )
    assert output.read_text() == "built"
    old = time.time() - 90000
    os.utime(stamp, (old, old))
    before = stamp.stat().st_mtime_ns
    failed = run(
        str(reconcile),
        "sessions",
        str(personal),
        "apply",
        env={**env, "FAIL_GO": "1"},
    )
    assert failed.returncode != 0
    assert stamp.stat().st_mtime_ns == before


def test_go_native_touch_is_noop_but_same_mtime_content_change_rebuilds(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, project, personal, _ = isolated
    reconcile = personal / "software/reconcile"
    executable(
        fakebin / "go",
        'if [ "$1" = -C ]; then shift 2; fi; [ "$1" != build ] || { while [ "$1" != -o ]; do shift; done; echo build >> "$HOME/builds"; mkdir -p "$(dirname "$2")"; printf built > "$2"; }',
    )
    assert run(str(reconcile), "shp", str(personal), "apply", env=env).returncode == 0
    home = Path(env["HOME"])
    source = project / "ansible/roles/shp/files/shp/main.go"
    output = home / ".local/bin/shp"
    stamp = home / ".cache/ansiblonomicon/shp/upgrade.stamp"
    output_metadata = output.stat()
    stamp_metadata = stamp.stat()
    source_metadata = source.stat()
    os.utime(
        source,
        ns=(source_metadata.st_atime_ns, source_metadata.st_mtime_ns + 1_000_000_000),
    )
    assert run(str(reconcile), "shp", str(personal), "apply", env=env).returncode == 0
    assert (output.stat().st_mtime_ns, stamp.stat().st_mtime_ns) == (
        output_metadata.st_mtime_ns,
        stamp_metadata.st_mtime_ns,
    )
    assert (home / "builds").read_text() == "build\n"
    source.write_text(source.read_text().replace("package main", "package main\n"))
    os.utime(source, ns=(source_metadata.st_atime_ns, source_metadata.st_mtime_ns))
    real_state = Path(env["MISE_STATE_DIR"])
    state_before = file_snapshot(real_state)
    checked = run(str(reconcile), "shp", str(personal), "check", env=env)
    assert checked.returncode == 0, checked.stderr
    checked_again = run(str(reconcile), "shp", str(personal), "check", env=env)
    assert checked_again.returncode == 0, checked_again.stderr
    assert file_snapshot(real_state) == state_before
    assert (home / "builds").read_text() == "build\n"
    assert run(str(reconcile), "shp", str(personal), "apply", env=env).returncode == 0
    assert (home / "builds").read_text() == "build\nbuild\n"
    assert output.read_text() == "built"


def test_uvc_native_overlay_fetch_once_repeat_and_advancement(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, fakebin, _, personal, _ = isolated
    source, remote = remote_fixture(tmp_path)
    executable(
        fakebin / "gcc",
        'echo gcc >> "$HOME/calls"; while [ "$1" != -o ]; do shift; done; : > "$2"; chmod +x "$2"',
    )
    executable(
        fakebin / "git", 'echo "$*" >> "$HOME/git-calls"; exec /usr/bin/git "$@"'
    )
    args = (
        str(personal / "software/reconcile"),
        "uvc-util",
        str(personal),
        "apply",
        str(remote),
    )
    assert run(*args, env=env).returncode == 0
    home = Path(env["HOME"])
    for name in ("AGENTS.md", "configure_camera.py", "camera_settings.json"):
        assert (home / ".local/opt/uvc-util" / name).exists()
    assert (home / ".local/bin/configure_camera.py").is_symlink()
    assert "fetch --prune origin main" not in (home / "git-calls").read_text()
    output = home / ".local/opt/uvc-util/src/uvc-util"
    output_mtime = output.stat().st_mtime_ns
    assert run(*args, env=env).returncode == 0
    assert output.stat().st_mtime_ns == output_mtime
    assert (
        sum(
            "fetch --prune origin main" in line
            for line in (home / "git-calls").read_text().splitlines()
        )
        == 1
    )
    (source / "src/uvc-util.m").write_text("advanced")
    git(source, "commit", "-am", "advance")
    git(source, "push", str(remote), "main")
    assert run(*args, env=env).returncode == 0
    assert (home / "calls").read_text() == "gcc\ngcc\n"
    assert run(*args, env=env).returncode == 0
    assert (home / "calls").read_text() == "gcc\ngcc\n"


def test_uvc_unknown_untracked_preserved_and_tracked_dirt_fails(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, _, _, _, _ = isolated
    _, remote = remote_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    args = (sys.executable, str(UVC_REPO), str(checkout), "--origin", str(remote))
    assert run(*args, env=env).returncode == 0
    (checkout / "unknown").write_text("keep")
    assert run(*args, env=env).returncode == 0
    assert (checkout / "unknown").read_text() == "keep"
    (checkout / "src/uvc-util.m").write_text("dirty")
    rejected = run(*args, env=env)
    assert rejected.returncode == 1
    assert "tracked changes" in rejected.stderr


def test_uvc_check_reports_remote_advance_without_changing_checkout_metadata(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, _, _, _, _ = isolated
    source, remote = remote_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    args = (sys.executable, str(UVC_REPO), str(checkout), "--origin", str(remote))
    assert run(*args, env=env).returncode == 0
    (source / "src/uvc-util.m").write_text("advanced")
    git(source, "commit", "-am", "advance")
    git(source, "push", str(remote), "main")
    head = git(checkout, "rev-parse", "HEAD")
    metadata = (
        (checkout / ".git/FETCH_HEAD").stat().st_mtime_ns
        if (checkout / ".git/FETCH_HEAD").exists()
        else None
    )

    checked = run(*args, "--check", env=env)

    assert checked.returncode == 0, checked.stderr
    assert "ancestry is unavailable without fetching" in checked.stderr
    assert git(checkout, "rev-parse", "HEAD") == head
    assert (
        (checkout / ".git/FETCH_HEAD").stat().st_mtime_ns
        if (checkout / ".git/FETCH_HEAD").exists()
        else None
    ) == metadata


def test_uvc_check_rejects_clean_divergence_when_remote_commit_is_local(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, _, _, _, _ = isolated
    source, remote = remote_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    args = (sys.executable, str(UVC_REPO), str(checkout), "--origin", str(remote))
    assert run(*args, env=env).returncode == 0
    (source / "src/uvc-util.m").write_text("remote")
    git(source, "commit", "-am", "remote")
    git(source, "push", str(remote), "main")
    remote_head = git(source, "rev-parse", "HEAD")
    git(checkout, "fetch", str(remote), remote_head)
    git(checkout, "config", "user.email", "test@example.com")
    git(checkout, "config", "user.name", "Test")
    (checkout / "src/one.h").write_text("local")
    git(checkout, "commit", "-am", "local")

    checked = run(*args, "--check", env=env)

    assert checked.returncode == 1
    assert "main has diverged" in checked.stderr


def test_uvc_check_reports_branch_switch_without_touching_index(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, _, _, _, _ = isolated
    _, remote = remote_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    args = (sys.executable, str(UVC_REPO), str(checkout), "--origin", str(remote))
    assert run(*args, env=env).returncode == 0
    git(checkout, "checkout", "-b", "inspection")
    index = checkout / ".git/index"
    before = index.stat()
    result = run(*args, "--check", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stderr == "uvc-util checkout would switch to main\n"
    assert git(checkout, "branch", "--show-current") == "inspection"
    after = index.stat()
    assert (after.st_ino, after.st_mtime_ns, after.st_ctime_ns) == (
        before.st_ino,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )


def test_missing_uvc_check_reports_clone_and_build_without_creating_checkout(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, _, _, personal, _ = isolated
    result = run(
        str(personal / "software/reconcile"),
        "uvc-util",
        str(personal),
        "check",
        "https://example.invalid/uvc.git",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "uvc-util checkout would be cloned:" in result.stderr
    assert "uvc-util files and build would follow clone" in result.stderr
    assert not (Path(env["HOME"]) / ".local/opt/uvc-util").exists()


def test_uvc_check_previews_missing_overlays_after_interrupted_clone(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], tmp_path: Path
) -> None:
    env, _, _, personal, _ = isolated
    _, remote = remote_fixture(tmp_path)
    checkout = Path(env["HOME"]) / ".local/opt/uvc-util"
    git(tmp_path, "clone", str(remote), str(checkout))
    before = file_snapshot(checkout)
    result = run(
        str(personal / "software/reconcile"),
        "uvc-util",
        str(personal),
        "check",
        str(remote),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert (
        "configure_camera.py link would be reconciled after file deployment"
        in result.stderr
    )
    assert "gcc -o uvc-util" in result.stderr
    assert file_snapshot(checkout) == before


def test_official_tasks_pass_only_supported_installer_arguments(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    executable(
        fakebin / "curl",
        """url=$2
output=$4
case "$url" in
  https://claude.ai/install.sh)
    cat > "$output" <<'EOF'
#!/bin/sh
[ "$#" -eq 0 ] || { echo unexpected-claude-args >&2; exit 64; }
echo "$#:$*" > "$HOME/claude-argv"
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\n' > "$HOME/.local/bin/claude"
chmod +x "$HOME/.local/bin/claude"
EOF
    ;;
  https://opencode.ai/install)
    cat > "$output" <<'EOF'
#!/bin/sh
[ "$#" -eq 1 ] && [ "$1" = --no-modify-path ] || { echo unexpected-opencode-args >&2; exit 65; }
echo "$#:$*" > "$HOME/opencode-argv"
mkdir -p "$HOME/.opencode/bin"
printf '#!/bin/sh\n' > "$HOME/.opencode/bin/opencode"
chmod +x "$HOME/.opencode/bin/opencode"
EOF
    ;;
  *) exit 66 ;;
esac""",
    )
    reconcile = personal / "software/reconcile"
    claude = run(str(reconcile), "claude-code", str(personal), "apply", env=env)
    opencode = run(str(reconcile), "opencode", str(personal), "apply", env=env)
    assert claude.returncode == 0, claude.stderr
    assert opencode.returncode == 0, opencode.stderr
    home = Path(env["HOME"])
    assert (home / "claude-argv").read_text() == "0:\n"
    assert (home / "opencode-argv").read_text() == "1:--no-modify-path\n"


def test_official_failure_cleanup_existing_noop_and_check_no_download(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    installer = personal / "software/install-official"
    marker = Path(env["HOME"]) / "curl"
    executable(
        fakebin / "curl",
        'echo called >> "$HOME/curl"; printf "#!/bin/sh\\nexit 9\\n" > "$4"',
    )
    tool = Path(env["HOME"]) / "bin/tool"
    checked = run(str(installer), "tool", str(tool), "invalid", "--check", env=env)
    assert checked.returncode == 0
    assert checked.stderr == f"tool would be installed: {tool}\n"
    assert not marker.exists()
    failed = run(str(installer), "tool", str(tool), "invalid", env=env)
    assert failed.returncode == 9
    assert list(Path(env["TMPDIR"]).iterdir()) == []
    executable(tool, "exit 0")
    assert run(str(installer), "tool", str(tool), "invalid", env=env).returncode == 0
    assert marker.read_text() == "called\n"


def test_official_termination_cleans_download_and_does_not_resume(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    executable(
        fakebin / "curl",
        'printf "#!/bin/sh\\nexit 0\\n" > "$4"\n'
        "exec python3 -c 'import os, signal; os.kill(os.getppid(), signal.SIGTERM)'",
    )
    tool = Path(env["HOME"]) / "bin/tool"
    result = run(
        str(personal / "software/install-official"),
        "tool",
        str(tool),
        "invalid",
        env=env,
    )
    assert result.returncode == 143
    assert result.stderr == ""
    assert not tool.exists()
    assert list(Path(env["TMPDIR"]).iterdir()) == []


@pytest.mark.parametrize(
    ("installed", "link_target", "message"),
    [
        (None, None, "pi would be installed: 2.0.0"),
        ("2.0.0", "old-pi", "pi link would be updated:"),
        ("2.0.0", "release/2.0.0/pi/pi", ""),
        ("1.0.0", "release/1.0.0/pi/pi", "pi would be upgraded: 1.0.0 -> 2.0.0"),
    ],
)
def test_pi_check_reports_native_state_without_installing_or_mutating(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
    installed: str | None,
    link_target: str | None,
    message: str,
) -> None:
    env, fakebin, _, _, work = isolated
    home = Path(env["HOME"])
    if installed:
        executable(home / f"release/{installed}/pi/pi", "exit 0")
    link = home / ".local/libexec/pi"
    if link_target:
        link.parent.mkdir(parents=True)
        link.symlink_to(home / link_target)
    before = link.lstat() if link.is_symlink() else None
    executable(
        fakebin / "mise",
        'echo "$*" >> "$HOME/mise-check-calls"\n'
        'while [ "${1:-}" != latest ] && [ "${1:-}" != where ]; do shift; done\n'
        'case "$1:$2" in latest:--installed) '
        f"{f'printf {installed}' if installed else 'exit 0'} ;; "
        'latest:*) printf 2.0.0 ;; where:*) printf "%s/release/%s" "$HOME" "${2##*@}" ;; esac',
    )
    result = run(str(work / "software/reconcile"), "pi", str(work), "check", env=env)
    assert result.returncode == 0, result.stderr
    if message:
        assert message in result.stderr
    else:
        assert result.stderr == ""
    calls = (home / "mise-check-calls").read_text()
    assert " latest " in f" {calls} "
    assert " install " not in f" {calls} "
    assert " upgrade " not in f" {calls} "
    if before is None:
        assert not link.is_symlink()
    else:
        after = link.lstat()
        assert (after.st_ino, after.st_mode, after.st_mtime_ns, after.st_ctime_ns) == (
            before.st_ino,
            before.st_mode,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )


def test_due_go_check_reaches_build_preview_without_go_or_stamp_change(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, personal, _ = isolated
    executable(fakebin / "go", 'echo executed > "$HOME/go-executed"; exit 99')
    stamp = Path(env["HOME"]) / ".cache/ansiblonomicon/sessions/upgrade.stamp"
    result = run(
        str(personal / "software/reconcile"),
        "sessions",
        str(personal),
        "check",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "Go dependency maintenance is due:" in result.stdout
    assert '[install] $ mkdir -p "$HOME/.local/bin"' in result.stderr
    assert not (Path(env["HOME"]) / "go-executed").exists()
    assert not stamp.exists()


def test_pi_native_failure_does_not_relink_and_upgrade_keeps_sidecars(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, _, _, work = isolated
    home = Path(env["HOME"])
    old = home / "old-pi"
    executable(old, "exit 0")
    link = home / ".local/libexec/pi"
    link.parent.mkdir(parents=True)
    link.symlink_to(old)
    executable(
        fakebin / "mise",
        'echo "$*" >> "$HOME/pi-calls"\ncase "$1" in install) exit "${FAIL_INSTALL:-0}" ;; upgrade) exit "${FAIL_UPGRADE:-0}" ;; where) printf %s "$HOME/release" ;; esac',
    )
    failed = run(
        str(MISE),
        "-C",
        str(work),
        "run",
        "--skip-tools",
        "pi",
        env={**env, "MISE_ENV": "software,pi", "FAIL_UPGRADE": "8"},
    )
    assert failed.returncode != 0
    assert link.resolve() == old
    executable(home / "release/pi/pi", "exit 0")
    (home / "release/pi/LICENSE").write_text("sidecar")
    succeeded = run(
        str(MISE),
        "-C",
        str(work),
        "run",
        "--skip-tools",
        "pi",
        env={**env, "MISE_ENV": "software,pi"},
    )
    assert succeeded.returncode == 0, succeeded.stderr
    calls = (home / "pi-calls").read_text()
    assert "install --yes github:earendil-works/pi@latest" in calls
    assert "upgrade --yes --no-prune github:earendil-works/pi@latest" in calls
    assert (home / "release/pi/LICENSE").read_text() == "sidecar"
    assert link.resolve() == home / "release/pi/pi"


@pytest.mark.parametrize("check,mode", [(False, "apply"), (True, "check")])
def test_root_uvc_dispatch_passes_explicit_mode_before_origin(
    isolated: tuple[dict[str, str], Path, Path, Path, Path], check: bool, mode: str
) -> None:
    env, fakebin, project, _, _ = isolated
    executable(fakebin / "hostname", "printf Thurstons-MacBook-Pro")
    capture = project / "bootstrap/capabilities/software/reconcile"
    executable(capture, 'printf "%s\\n" "$@" > "$HOME/dispatch-argv"')
    body = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"][
        "software:dispatch"
    ]["run"]
    result = run(
        "/bin/sh",
        "-c",
        body,
        env={
            **env,
            "usage_capability": "uvc-util",
            "usage_check": "true" if check else "",
        },
        cwd=project,
    )
    assert result.returncode == 0, result.stderr
    assert (Path(env["HOME"]) / "dispatch-argv").read_text().splitlines() == [
        "uvc-util",
        str(project / "bootstrap/targets/Thurstons-MacBook-Pro"),
        mode,
        "https://github.com/thurstonsand/uvc-util.git",
    ]


def test_root_dispatch_retains_host_registration_limit(
    isolated: tuple[dict[str, str], Path, Path, Path, Path],
) -> None:
    env, fakebin, project, _, _ = isolated
    executable(fakebin / "hostname", "printf unregistered")
    body = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"][
        "software:dispatch"
    ]["run"]
    result = run(
        "/bin/sh",
        "-c",
        body,
        env={**env, "usage_capability": "uvc-util", "usage_check": ""},
        cwd=project,
    )
    assert result.returncode != 0
    assert result.stderr == "uvc-util is not registered on unregistered\n"
