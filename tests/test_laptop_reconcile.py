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
    (tmp_path / "scripts").mkdir()
    binary = tmp_path / "bin"
    binary.mkdir()
    calls = tmp_path / "calls"
    calls.touch()
    commands = {
        binary / "hostname": 'printf "%s\\n" "$HOST"',
        binary / "mise": """printf 'mise %s\n' "$*" >> "$CALLS"
if [ "$2" = //:reconcile:laptop ]; then exec sh -c "$LAPTOP_RUN"; fi
if [ "$2" = "//:$FAILURE" ]; then exit 23; fi
""",
        tmp_path / "scripts/fnox-host": """printf 'fnox %s\n' "$*" >> "$CALLS"
[ "$HOST" = ML-DFC6YK6VJQ ] || exit 99
while [ "$1" != -- ]; do shift; done
shift
exec "$@"
""",
        binary / "uv": """printf 'uv %s\n' "$*" >> "$CALLS"
[ "$HOST" = ML-DFC6YK6VJQ ] || exit 99
[ "$1 $2 $3" = 'run --group work' ] || exit 99
shift 3
exec "$@"
""",
        binary / "ansible-playbook": """printf 'ansible %s\n' "$*" >> "$CALLS"
[ "$HOST" = ML-DFC6YK6VJQ ] || exit 99
test "$ANSIBLE_CACHE_PLUGIN" = memory || exit 99
test "$ANSIBLE_CONFIG" = "$MISE_PROJECT_ROOT/ansible/ansible.cfg" || exit 99
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
        cwd=tmp_path / tasks[task].get("dir", "."),
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
            "MISE_PROJECT_ROOT": str(tmp_path),
        },
        check=False,
    )
    assert not (tmp_path / "ansible").exists()
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


@pytest.mark.parametrize(
    "host,environments",
    [
        ("Thurstons-MacBook-Pro", "desktop-tools,desktop-tools-personal"),
        ("ML-DFC6YK6VJQ", "desktop-tools"),
    ],
)
def test_desktop_tools_root_check_never_fetches_secrets(
    tmp_path: Path, host: str, environments: str
) -> None:
    task = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["desktop-tools"]
    binary = tmp_path / "bin"
    scripts = tmp_path / "scripts"
    binary.mkdir()
    scripts.mkdir()
    calls = tmp_path / "calls"
    commands = {
        binary / "hostname": 'printf "%s\\n" "$HOST"',
        binary / "mise": 'printf "mise %s env=%s\\n" "$*" "$MISE_ENV" >> "$CALLS"',
        scripts / "fnox-host": 'printf "fnox %s\\n" "$*" >> "$CALLS"; exit 23',
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
            "MISE_PROJECT_ROOT": str(tmp_path),
            "usage_check": "true",
        },
        check=False,
    )

    assert result.returncode == 0
    assert calls.read_text().splitlines() == [
        f"mise -C {tmp_path}/bootstrap/targets/{host} bootstrap "
        f"--only files,dotfiles --force-dotfiles --dry-run env={environments}"
    ]


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
    file = tmp_path / f"bootstrap/capabilities/mac-apps/{brewfile}"
    python = f"python3 {helper} --brewfile {file}"
    assert status == 0
    if check:
        assert calls == [f"{python} --check askpass="]
    else:
        askpass = tmp_path / "scripts/sudo-askpass.sh"
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
    expected: list[str] = []
    suffix = " --check" if check else ""
    if task == "reconcile":
        expected.append(
            "mise run //:reconcile:laptop"
            + (f" --tags {tags}" if tags else "")
            + suffix
        )
    selected = tags.split(",") if tags else []
    if host == "Thurstons-MacBook-Pro" and any(
        tag in {"chezmoi", "terminal-theme-extra"} for tag in selected
    ):
        assert status != 0
        assert calls == expected
        return
    assert status == 0
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
    if full or "berkeley-mono" in selected:
        expected.append("mise run //:berkeley-mono" + suffix)
    software = (
        ["pi", "sessions", "uvc-util"]
        if host == "ML-DFC6YK6VJQ"
        else [
            "claude-code",
            "opencode",
            "sessions",
            "shp",
            "uvc-util",
            "docker-context",
        ]
    )
    for capability in software:
        if full or capability in selected:
            expected.append(f"mise run //:{capability}" + suffix)
    if full:
        expected.append("mise run //:sysconfig" + suffix)
    if host == "Thurstons-MacBook-Pro" and (full or "agent-harness" in selected):
        expected.append("mise run //:agent-harness" + suffix)
    native = {
        "mise",
        "mac-apps",
        "homebrew",
        "mas",
        "language-tools",
        "berkeley-mono",
        "docker-context",
        "claude-code",
        "opencode",
        "pi",
        "sessions",
        "shp",
        "uvc-util",
        "sysconfig",
        "dock",
        "finder",
        "nsglobaldomain",
        "menubar",
        "desktop-services",
        "permissions",
        "hostname",
        "terminal-theme",
        "git-client",
        "jj-client",
        "ssh-client",
        "shell",
        "terminal-tools",
        "tmux",
        "user-tools",
        "desktop-tools",
        "editor-config",
        "neovim",
        "nvim-deps",
        "python-index",
        "agent-harness",
        "agent-config",
    }
    if host == "ML-DFC6YK6VJQ":
        native.remove("agent-harness")
    ansible_tags = [tag for tag in selected if tag not in native]
    if host == "ML-DFC6YK6VJQ" and (full or ansible_tags):
        args = (
            f"-i {tmp_path}/ansible/inventory/control/macos.ini "
            f"{tmp_path}/ansible/playbooks/work.yml"
        )
        if check:
            args += " --check"
        if not full:
            args += f" --tags {','.join(ansible_tags)}"
        expected.extend(
            [
                "fnox exec --secret HOMEBREW_SUDO_ASKPASS_PASS_WORK "
                f"--secret ANTHROPIC_AUTH_TOKEN -- uv run --group work ansible-playbook {args}",
                f"uv run --group work ansible-playbook {args}",
                f"ansible {args}",
            ]
        )
    if host == "ML-DFC6YK6VJQ" and (full or "agent-harness" in selected):
        expected.append("mise run //:agent-config" + suffix)
    if "agent-config" in selected and "agent-harness" not in selected:
        expected.append("mise run //:agent-config" + suffix)
    if theme:
        expected.append("mise run //:terminal-theme" + suffix)
    if full:
        expected.append("mise run //:git-client" + suffix)
        expected.append("mise run //:jj-client" + suffix)
        expected.append("mise run //:shell" + suffix)
        expected.append("mise run //:terminal-tools" + suffix)
        expected.append("mise run //:user-tools" + suffix)
        expected.append("mise run //:desktop-tools" + suffix)
        expected.append("mise run //:editor-config" + suffix)
        expected.append("mise run //:neovim" + suffix)
        if host == "Thurstons-MacBook-Pro":
            expected.append("mise run //:ssh-client" + suffix)
            expected.append("mise run //:retirements" + suffix)
    assert calls == expected


@pytest.mark.parametrize(
    "host,failure",
    [
        ("Thurstons-MacBook-Pro", "mise:maintain"),
        ("Thurstons-MacBook-Pro", "mac-apps"),
        ("ML-DFC6YK6VJQ", "ansible"),
    ],
)
def test_failed_prerequisite_stops_before_native_theme(
    tmp_path: Path, host: str, failure: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=host,
        tags="",
        check=False,
        failure=failure,
    )
    assert status == 23
    assert "mise run //:terminal-theme" not in calls
    if failure == "mise:maintain":
        assert calls == ["mise run //:mise:install", "mise run //:mise:maintain"]


def test_mixed_scopes_run_sysconfig_once_before_agent_harness_and_theme(
    tmp_path: Path,
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="dock,terminal-theme,agent-harness",
        check=True,
    )
    assert status == 0
    assert calls == [
        "mise run //:sysconfig --sections dock --check",
        "mise run //:agent-harness --check",
        "mise run //:terminal-theme --check",
    ]


def test_work_agent_harness_continues_through_ansible() -> None:
    # The work playbook retains private extras and Glimpse support in the role.
    assert "name: agent_harness" in (ROOT / "ansible/playbooks/work.yml").read_text()
    assert not (ROOT / "ansible/playbooks/macos.yml").exists()


def test_personal_agent_harness_failure_stops_before_ansible_and_chezmoi(
    tmp_path: Path,
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="all",
        check=True,
        failure="agent-harness",
    )
    assert status == 23
    assert calls[-1] == "mise run //:agent-harness --check"
    assert not any(call.startswith(("fnox ", "ansible ")) for call in calls)


def test_public_agent_harness_routes_all_hosts_to_native_config_after_catalogue(
    tmp_path: Path,
) -> None:
    task = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["agent-harness"]
    binary = tmp_path / "bin"
    python = tmp_path / ".venv/bin/python"
    binary.mkdir()
    python.parent.mkdir(parents=True)
    calls = tmp_path / "calls"
    (binary / "hostname").write_text('#!/bin/sh\nprintf "%s\\n" "$HOST"\n')
    (binary / "hostname").chmod(0o755)
    (binary / "mise").write_text('#!/bin/sh\nprintf "mise %s\\n" "$*" >> "$CALLS"\n')
    (binary / "mise").chmod(0o755)
    python.write_text('#!/bin/sh\nprintf "python %s\\n" "$*" >> "$CALLS"\n')
    python.chmod(0o755)
    base_env = {
        **os.environ,
        "PATH": f"{binary}:/usr/bin:/bin",
        "MISE_PROJECT_ROOT": str(tmp_path),
        "HOME": str(tmp_path / "home"),
        "CALLS": str(calls),
        "usage_check": "true",
        "usage_cached": "",
    }
    personal = subprocess.run(
        ["sh", "-c", task["run"]],
        env={**base_env, "HOST": "Thurstons-MacBook-Pro"},
        check=False,
    )
    assert personal.returncode == 0
    assert calls.read_text().splitlines() == [
        f"python {tmp_path}/bootstrap/capabilities/agent-harness/agent_harness_deploy.py "
        f"--repo {tmp_path} --home {tmp_path}/home "
        f"--cache {tmp_path}/home/.cache/ansiblonomicon-harness "
        f"--host-config {tmp_path}/bootstrap/targets/Thurstons-MacBook-Pro/"
        "mise.agent-harness.toml --check",
        "mise run //:agent-config --check",
    ]
    calls.write_text("")
    work = subprocess.run(
        ["sh", "-c", task["run"]],
        env={**base_env, "HOST": "ML-DFC6YK6VJQ"},
        check=False,
    )
    assert work.returncode == 0
    assert calls.read_text().splitlines() == ["mise run //:agent-config --check"]


def test_sysconfig_plus_scoped_tag_keeps_full_union_semantics(tmp_path: Path) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="sysconfig,dock",
        check=True,
    )
    assert status == 0
    assert calls == ["mise run //:sysconfig --check"]


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
def test_user_tools_tag_runs_only_native_capability(
    tmp_path: Path, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="user-tools",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:user-tools" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("host", ["Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ"])
@pytest.mark.parametrize("check", [False, True])
def test_desktop_tools_tag_runs_only_native_capability(
    tmp_path: Path, host: str, check: bool
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=host,
        tags="desktop-tools",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:desktop-tools" + (" --check" if check else "")
    ]


@pytest.mark.parametrize("check", [False, True])
def test_ssh_client_tag_runs_only_on_personal_mac(tmp_path: Path, check: bool) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="ssh-client",
        check=check,
    )
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:ssh-client" + (" --check" if check else "")
    ]


def test_ssh_client_tag_is_rejected_on_work_without_ansible_fallthrough(
    tmp_path: Path,
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="ML-DFC6YK6VJQ",
        tags="ssh-client",
        check=True,
    )
    assert status != 0
    assert calls == []


def test_docker_context_tag_is_rejected_on_work_without_ansible_fallthrough(
    tmp_path: Path,
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="ML-DFC6YK6VJQ",
        tags="docker-context",
        check=True,
    )
    assert status != 0
    assert calls == []


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
    assert not (ROOT / "ansible/playbooks/macos.yml").exists()
    assert "terminal_theme" not in (ROOT / "ansible/playbooks/work.yml").read_text()


def test_ansible_no_longer_routes_migrated_mac_software_roles() -> None:
    assert not (ROOT / "ansible/playbooks/macos.yml").exists()
    work = (ROOT / "ansible/playbooks/work.yml").read_text()
    for role in ("pi_release", "sessions", "uvc_util"):
        assert f"name: {role}" not in work


@pytest.mark.parametrize(
    "host,tag",
    [
        ("Thurstons-MacBook-Pro", "claude-code"),
        ("Thurstons-MacBook-Pro", "opencode"),
        ("Thurstons-MacBook-Pro", "sessions"),
        ("Thurstons-MacBook-Pro", "shp"),
        ("Thurstons-MacBook-Pro", "uvc-util"),
        ("Thurstons-MacBook-Pro", "berkeley-mono"),
        ("Thurstons-MacBook-Pro", "docker-context"),
        ("ML-DFC6YK6VJQ", "pi"),
        ("ML-DFC6YK6VJQ", "sessions"),
        ("ML-DFC6YK6VJQ", "uvc-util"),
        ("ML-DFC6YK6VJQ", "berkeley-mono"),
    ],
)
def test_migrated_software_tag_routes_only_native_capability(
    tmp_path: Path, host: str, tag: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=host,
        tags=tag,
        check=True,
    )
    assert status == 0
    assert calls == [f"mise run //:{tag} --check"]


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "tags", ["dotfiles", "all,chezmoi", "terminal-theme,not-a-capability"]
)
def test_personal_unsupported_tags_fail_before_any_action(
    tmp_path: Path, check: bool, tags: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags=tags,
        check=check,
    )
    assert status != 0
    assert calls == []


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "tags", ["retirements", "retirements,terminal-theme,retirements"]
)
def test_personal_explicit_retirements_run_once_after_config(
    tmp_path: Path, check: bool, tags: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags=tags,
        check=check,
    )
    suffix = " --check" if check else ""
    expected = [] if check else ["mise run //:mise:maintain"]
    if "terminal-theme" in tags:
        expected.append("mise run //:terminal-theme" + suffix)
    assert status == 0
    assert calls == [*expected, "mise run //:retirements" + suffix]


@pytest.mark.parametrize("failure", ["terminal-theme", "retirements"])
def test_retirements_respect_config_failure_and_propagate_own_failure(
    tmp_path: Path, failure: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host="Thurstons-MacBook-Pro",
        tags="retirements,terminal-theme",
        check=True,
        failure=failure,
    )
    assert status == 23
    assert calls == ["mise run //:terminal-theme --check"] + (
        ["mise run //:retirements --check"] if failure == "retirements" else []
    )
