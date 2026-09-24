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
        stderr=subprocess.PIPE,
        text=True,
    )
    (tmp_path / "stderr").write_text(result.stderr)
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
        f"--only files,dotfiles --dry-run env={environments}"
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


PERSONAL = "Thurstons-MacBook-Pro"
WORK = "ML-DFC6YK6VJQ"
HOST_SOFTWARE = {
    PERSONAL: [
        "claude-code",
        "opencode",
        "sessions",
        "shp",
        "uvc-util",
        "docker-context",
    ],
    WORK: ["pi", "sessions", "uvc-util"],
}
HOST_CONFIG = {PERSONAL: ["ssh-client"], WORK: ["python-index", "work-local"]}


@pytest.mark.parametrize("task", ["reconcile", "reconcile:laptop"])
@pytest.mark.parametrize("host", [PERSONAL, WORK])
@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "tags,theme",
    [
        ("", True),
        ("terminal-theme", True),
        ("homebrew,terminal-theme", True),
        ("all", True),
        ("all,terminal-theme", True),
        ("agent-harness", False),
        ("agent-config", False),
    ],
)
def test_laptop_dispatches_native_capabilities(
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
    full = not tags or "all" in selected
    if full or "homebrew" in selected:
        expected.append("mise run //:mise:install" + suffix)
    if not check:
        expected.append("mise run //:mise:maintain")
    if full or "homebrew" in selected:
        expected.append("mise run //:mac-apps" + suffix)
    if full:
        expected += [
            f"mise run //:{capability}" + suffix
            for capability in (
                "language-tools",
                "berkeley-mono",
                *HOST_SOFTWARE[host],
                "sysconfig",
            )
        ]
    if full or "agent-harness" in selected:
        expected.append("mise run //:agent-harness" + suffix)
    elif "agent-config" in selected:
        expected.append("mise run //:agent-config" + suffix)
    if theme:
        expected.append("mise run //:terminal-theme" + suffix)
    if full:
        config = [
            "git-client",
            "jj-client",
            "shell",
            "terminal-tools",
            "user-tools",
            "desktop-tools",
            "editor-config",
            "neovim",
            *HOST_CONFIG[host],
        ]
        # language-tools already reconciled work's Python index.
        expected += [
            f"mise run //:{capability}" + suffix
            for capability in config
            if capability != "python-index"
        ]
    assert status == 0
    assert calls == expected


@pytest.mark.parametrize(
    "host,failure",
    [
        (PERSONAL, "mise:maintain"),
        (PERSONAL, "mac-apps"),
        (WORK, "agent-harness"),
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


@pytest.mark.parametrize("host", [PERSONAL, WORK])
def test_agent_harness_failure_stops_before_config_capabilities(
    tmp_path: Path, host: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=host,
        tags="all",
        check=True,
        failure="agent-harness",
    )
    assert status == 23
    assert calls[-1] == "mise run //:agent-harness --check"


@pytest.mark.parametrize("host", [PERSONAL, WORK])
def test_public_agent_harness_routes_laptops_to_native_config_after_catalogue(
    tmp_path: Path, host: str
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
    result = subprocess.run(
        ["sh", "-c", task["run"]],
        env={**base_env, "HOST": host},
        check=False,
    )
    assert result.returncode == 0
    assert calls.read_text().splitlines() == [
        f"python {tmp_path}/bootstrap/capabilities/agent-harness/agent_harness_deploy.py "
        f"--repo {tmp_path} --home {tmp_path}/home "
        f"--cache {tmp_path}/home/.cache/ansiblonomicon-harness "
        f"--host-config {tmp_path}/bootstrap/targets/{host}/"
        "mise.agent-harness.toml --check",
        "mise run //:agent-config --check",
    ]


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
def test_mac_app_aliases_run_once(tmp_path: Path, tags: str) -> None:
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


@pytest.mark.parametrize("tag", ["ssh-client", "docker-context", "hostname"])
def test_personal_only_tags_are_rejected_on_work(tmp_path: Path, tag: str) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=WORK,
        tags=tag,
        check=True,
    )
    assert status != 0
    assert calls == []
    assert tag in (tmp_path / "stderr").read_text()


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


@pytest.mark.parametrize("host,profile", [(PERSONAL, "personal"), (WORK, "work")])
@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "tags,unsupported",
    [
        ("dotfiles", "dotfiles"),
        ("all,chezmoi", "chezmoi"),
        ("terminal-theme,not-a-capability", "not-a-capability"),
    ],
)
def test_unsupported_tags_fail_before_any_action(
    tmp_path: Path, host: str, profile: str, check: bool, tags: str, unsupported: str
) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=host,
        tags=tags,
        check=check,
    )
    assert status != 0
    assert calls == []
    assert (tmp_path / "stderr").read_text() == (
        f"Unsupported {profile}-host tags: {unsupported}\n"
    )


@pytest.mark.parametrize("check", [False, True])
def test_work_local_runs_after_python_index(tmp_path: Path, check: bool) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=WORK,
        tags="work-local,python-index",
        check=check,
    )
    suffix = " --check" if check else ""
    assert status == 0
    assert calls == ([] if check else ["mise run //:mise:maintain"]) + [
        "mise run //:python-index" + suffix,
        "mise run //:work-local" + suffix,
    ]


def test_work_local_is_rejected_on_personal(tmp_path: Path) -> None:
    status, calls = run_laptop(
        tmp_path,
        task="reconcile:laptop",
        host=PERSONAL,
        tags="work-local",
        check=True,
    )
    assert status != 0
    assert calls == []
