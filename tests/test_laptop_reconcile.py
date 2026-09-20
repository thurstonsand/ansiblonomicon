import os
from pathlib import Path
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_language_tools(
    tmp_path: Path,
    *,
    host: str,
    check: bool,
    failure: str = "",
) -> tuple[int, list[str]]:
    task = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["language-tools"]
    binary = tmp_path / "bin"
    binary.mkdir()
    calls = tmp_path / "calls"
    commands = {
        binary / "hostname": 'printf "%s\\n" "$HOST"',
        binary / "python3": """printf 'python3 %s\n' "$*" >> "$CALLS"
case "$FAILURE:$*" in
  preflight:*--profile\\ work*--check) exit 23 ;;
  runtime:*--profile\\ work*) case "$*" in *--check) ;; *) exit 23 ;; esac ;;
esac
""",
        binary / "mise": """printf 'mise %s\n' "$*" >> "$CALLS"
[ "$FAILURE" != python-index ] || exit 23
""",
    }
    for path, body in commands.items():
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
    result = subprocess.run(
        ["sh", "-c", task["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{binary}:/usr/bin:/bin",
            "HOST": host,
            "CALLS": str(calls),
            "FAILURE": failure,
            "MISE_PROJECT_ROOT": str(tmp_path),
            "usage_check": "true" if check else "",
        },
        check=False,
    )
    return result.returncode, calls.read_text().splitlines()


def run_laptop(
    tmp_path: Path,
    *,
    task: str,
    host: str,
    tags: str,
    check: bool,
    failure: str = "",
) -> tuple[int, list[str]]:
    tasks = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]
    (tmp_path / "ansible").mkdir()
    (tmp_path / "scripts").mkdir()
    binary = tmp_path / "bin"
    binary.mkdir()
    calls = tmp_path / "calls"
    commands = {
        binary / "hostname": 'printf "%s\\n" "$HOST"',
        binary / "mise": """printf 'mise %s\n' "$*" >> "$CALLS"
if [ "$2" = //:reconcile:laptop ]; then exec sh -c "$LAPTOP_RUN"; fi
if [ "$2" = "//:$FAILURE" ]; then exit 23; fi
""",
        tmp_path / "scripts/fnox-host": """printf 'fnox %s\n' "$*" >> "$CALLS"
while [ "$1" != -- ]; do shift; done
shift
exec "$@"
""",
        binary / "ansible-playbook": """printf 'ansible %s\n' "$*" >> "$CALLS"
test "$ANSIBLE_CACHE_PLUGIN" = memory || exit 99
if [ "$FAILURE" = ansible ]; then exit 23; fi
""",
    }
    for path, body in commands.items():
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
    home = tmp_path / "home"
    standalone = home / ".local/bin"
    standalone.mkdir(parents=True)
    (standalone / "mise").symlink_to(binary / "mise")
    result = subprocess.run(
        ["sh", "-c", tasks[task]["run"]],
        cwd=tmp_path / "ansible",
        env={
            **os.environ,
            "PATH": f"{binary}:/usr/bin:/bin",
            "HOST": host,
            "CALLS": str(calls),
            "LAPTOP_RUN": tasks["reconcile:laptop"]["run"],
            "FAILURE": failure,
            "usage_tags": tags,
            "usage_check": "true" if check else "",
            "HOME": str(home),
        },
        check=False,
    )
    return result.returncode, calls.read_text().splitlines()


def run_mac_apps(
    tmp_path: Path, *, host: str, check: bool, fail_install: bool = False
) -> tuple[int, list[str]]:
    task = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["mac-apps"]
    binary = tmp_path / "bin"
    binary.mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    calls = tmp_path / "calls"
    commands = {
        binary / "hostname": 'printf "%s\\n" "$HOST"',
        binary
        / "mise": 'printf "mise %s\\n" "$*" >> "$CALLS"; [ "$FAIL_INSTALL" != true ] || exit 23',
        binary
        / "python3": 'printf "python3 %s askpass=%s\\n" "$*" "${SUDO_ASKPASS-}" >> "$CALLS"',
        scripts / "fnox-host": """printf 'fnox %s\n' "$*" >> "$CALLS"
while [ "$1" != -- ]; do shift; done
shift
exec "$@"
""",
    }
    for path, body in commands.items():
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
    environment = dict(os.environ)
    environment.pop("SUDO_ASKPASS", None)
    environment.update(
        {
            "PATH": f"{binary}:/usr/bin:/bin",
            "HOST": host,
            "CALLS": str(calls),
            "MISE_PROJECT_ROOT": str(tmp_path),
            "usage_check": "true" if check else "",
            "HOME": str(tmp_path / "home"),
            "FAIL_INSTALL": "true" if fail_install else "false",
        }
    )
    result = subprocess.run(
        ["sh", "-c", task["run"]],
        cwd=tmp_path,
        env=environment,
        check=False,
    )
    return result.returncode, calls.read_text().splitlines()


@pytest.mark.parametrize("check", [False, True])
def test_personal_language_tools_executes_without_private_extension(
    tmp_path: Path, check: bool
) -> None:
    status, calls = run_language_tools(
        tmp_path, host="Thurstons-MacBook-Pro", check=check
    )
    assert status == 0
    assert calls == [
        "python3 bootstrap/capabilities/language-tools/reconcile.py "
        "--profile personal" + (" --check" if check else "")
    ]
    assert "language-tools.local.toml" not in calls[0]


@pytest.mark.parametrize(
    "host,brewfile,secret",
    [
        ("Thurstons-MacBook-Pro", "Brewfile", "HOMEBREW_SUDO_ASKPASS_PASS"),
        ("ML-DFC6YK6VJQ", "Brewfile.work", "HOMEBREW_SUDO_ASKPASS_PASS_WORK"),
    ],
)
@pytest.mark.parametrize("check", [False, True])
def test_mac_apps_executes_scoped_host_payload(
    tmp_path: Path, host: str, brewfile: str, secret: str, check: bool
) -> None:
    status, calls = run_mac_apps(tmp_path, host=host, check=check)
    helper = tmp_path / "bootstrap/capabilities/mac-apps/reconcile.py"
    file = tmp_path / f"ansible/{brewfile}"
    python = f"python3 {helper} --brewfile {file}"
    assert status == 0
    if check:
        assert calls == [f"{python} --check askpass="]
    else:
        askpass = tmp_path / "ansible/sudo-askpass.sh"
        assert calls == [
            "mise run //:mise:install",
            f"fnox exec --secret {secret} -- python3 {helper} --brewfile {file}",
            f"{python} askpass={askpass}",
        ]


def test_mac_apps_stops_before_auth_and_cleanup_if_standalone_install_fails(
    tmp_path: Path,
) -> None:
    status, calls = run_mac_apps(
        tmp_path, host="Thurstons-MacBook-Pro", check=False, fail_install=True
    )
    assert status == 23
    assert calls == ["mise run //:mise:install"]


@pytest.mark.parametrize("check", [False, True])
def test_work_language_tools_preflights_then_configures_index_before_runtime(
    tmp_path: Path, check: bool
) -> None:
    status, calls = run_language_tools(tmp_path, host="ML-DFC6YK6VJQ", check=check)
    extension = tmp_path / "bootstrap/targets/ML-DFC6YK6VJQ/language-tools.local.toml"
    suffix = " --check" if check else ""
    assert status == 0
    assert calls == [
        "python3 bootstrap/capabilities/language-tools/reconcile.py "
        f"--profile work --extension {extension} --check",
        "mise run //:python-index" + suffix,
        "python3 bootstrap/capabilities/language-tools/reconcile.py "
        f"--profile work --extension {extension}" + suffix,
    ]


@pytest.mark.parametrize("failure", ["preflight", "python-index"])
def test_work_language_tools_failure_stops_runtime_writes(
    tmp_path: Path, failure: str
) -> None:
    status, calls = run_language_tools(
        tmp_path, host="ML-DFC6YK6VJQ", check=False, failure=failure
    )
    assert status == 23
    assert len(calls) == (1 if failure == "preflight" else 2)
    assert all(
        not (call.startswith("python3 ") and "--check" not in call) for call in calls
    )


@pytest.mark.parametrize("task", ["reconcile", "reconcile:laptop"])
@pytest.mark.parametrize("host", ["Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ"])
@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "tags,theme",
    [
        ("", True),
        ("terminal-theme", True),
        ("chezmoi,terminal-theme,homebrew", True),
        ("chezmoi", False),
        ("terminal-theme-extra", False),
        ("all", True),
        ("all,terminal-theme", True),
    ],
)
def test_laptop_dispatches_native_theme_outside_ansible(
    tmp_path: Path,
    task: str,
    host: str,
    check: bool,
    tags: str,
    theme: bool,
) -> None:
    status, calls = run_laptop(tmp_path, task=task, host=host, tags=tags, check=check)
    assert status == 0
    expected: list[str] = []
    suffix = " --check" if check else ""
    if task == "reconcile":
        expected.append(
            "mise run //:reconcile:laptop"
            + (f" --tags {tags}" if tags else "")
            + suffix
        )
    selected = tags.split(",") if tags else []
    normalized = ["mac-apps" if tag in ("homebrew", "mas") else tag for tag in selected]
    full = not tags or "all" in selected
    installs_mise = full or "mise" in selected or "mac-apps" in normalized
    if installs_mise:
        expected.append("mise run //:mise:install" + suffix)
    if not check:
        expected.append("mise run //:mise:maintain")
    if full or "mac-apps" in normalized:
        expected.append("mise run //:mac-apps" + suffix)
    if full or "language-tools" in selected:
        expected.append("mise run //:language-tools" + suffix)
    native = {
        "mise",
        "mac-apps",
        "homebrew",
        "mas",
        "language-tools",
        "terminal-theme",
        "git-client",
        "jj-client",
        "shell",
        "terminal-tools",
        "tmux",
        "neovim",
        "nvim-deps",
        "python-index",
    }
    ansible_tags = [tag for tag in selected if tag not in native]
    if full or ansible_tags:
        work = host == "ML-DFC6YK6VJQ"
        playbook = "work" if work else "macos"
        args = f"-i inventory/control/macos.ini playbooks/{playbook}.yml"
        if check:
            args += " --check"
        if not full:
            args += f" --tags {','.join(ansible_tags)}"
        secret = (
            "HOMEBREW_SUDO_ASKPASS_PASS_WORK" if work else "HOMEBREW_SUDO_ASKPASS_PASS"
        )
        fnox = f"fnox exec --secret {secret}" + (
            " --secret ANTHROPIC_AUTH_TOKEN" if work else ""
        )
        expected.extend([f"{fnox} -- ansible-playbook {args}", f"ansible {args}"])
    if theme:
        expected.append("mise run //:terminal-theme" + suffix)
    if full:
        expected.append("mise run //:git-client" + suffix)
        expected.append("mise run //:jj-client" + suffix)
        expected.append("mise run //:shell" + suffix)
        expected.append("mise run //:terminal-tools" + suffix)
        expected.append("mise run //:neovim" + suffix)
    assert calls == expected


@pytest.mark.parametrize("failure", ["mise:maintain", "mac-apps", "ansible"])
def test_failed_prerequisite_stops_before_native_theme(
    tmp_path: Path, failure: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="",
        check=False,
        failure=failure,
    )
    assert status == 23
    assert "mise run //:terminal-theme" not in calls
    if failure == "mise:maintain":
        assert calls == ["mise run //:mise:install", "mise run //:mise:maintain"]


@pytest.mark.parametrize("tags", ["mac-apps", "homebrew", "mas", "homebrew,mas"])
def test_mac_app_aliases_run_once_without_ansible(tmp_path: Path, tags: str) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags=tags,
        check=True,
    )
    assert status == 0
    assert calls == [
        "mise run //:mise:install --check",
        "mise run //:mac-apps --check",
    ]


@pytest.mark.parametrize("host", ["Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ"])
@pytest.mark.parametrize("check", [False, True])
def test_language_tools_and_mise_tags_run_only_native_capabilities(
    tmp_path: Path, host: str, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=host,
        tags="language-tools,mise",
        check=check,
    )
    suffix = " --check" if check else ""
    assert status == 0
    assert calls == ["mise run //:mise:install" + suffix] + (
        [] if check else ["mise run //:mise:maintain"]
    ) + ["mise run //:language-tools" + suffix]
    assert not any(call.startswith(("ansible ", "fnox ")) for call in calls)


def test_failed_language_tools_stops_full_reconcile_before_later_work(
    tmp_path: Path,
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="all,terminal-theme",
        check=False,
        failure="language-tools",
    )
    assert status == 23
    assert calls[-1] == "mise run //:language-tools"
    assert "mise run //:terminal-theme" not in calls
    assert not any("--skip-tags" in call for call in calls)


@pytest.mark.parametrize("check", [False, True])
def test_git_client_tag_runs_only_native_capability(
    tmp_path: Path, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="git-client",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:git-client" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("check", [False, True])
def test_jj_client_tag_runs_only_native_capability(tmp_path: Path, check: bool) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="jj-client",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:jj-client" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("check", [False, True])
def test_shell_tag_runs_only_native_capability(tmp_path: Path, check: bool) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="ML-DFC6YK6VJQ",
        tags="shell",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:shell" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("tag", ["terminal-tools", "tmux"])
@pytest.mark.parametrize("check", [False, True])
def test_terminal_tools_tags_run_only_native_capability(
    tmp_path: Path, tag: str, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags=tag,
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:terminal-tools" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("tag", ["neovim", "nvim-deps"])
@pytest.mark.parametrize("check", [False, True])
def test_neovim_tags_run_only_native_capability(
    tmp_path: Path, tag: str, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags=tag,
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:neovim" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("check", [False, True])
def test_python_index_tag_runs_only_on_work(tmp_path: Path, check: bool) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="ML-DFC6YK6VJQ",
        tags="python-index",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:python-index" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("check", [False, True])
def test_mixed_aliases_route_to_both_native_capabilities(
    tmp_path: Path, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="tmux,nvim-deps",
        check=check,
    )
    suffix = " --check" if check else ""
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:terminal-tools" + suffix,
        "mise run //:neovim" + suffix,
    ]


def test_ansible_no_longer_owns_terminal_theme() -> None:
    assert not (ROOT / "ansible/roles/terminal_theme/tasks/main.yml").exists()
    for playbook in ("macos", "work"):
        assert (
            "terminal_theme"
            not in (ROOT / f"ansible/playbooks/{playbook}.yml").read_text()
        )
