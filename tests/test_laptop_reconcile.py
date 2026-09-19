import os
from pathlib import Path
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


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
        },
        check=False,
    )
    return result.returncode, calls.read_text().splitlines()


@pytest.mark.parametrize("task", ["reconcile", "reconcile:laptop"])
@pytest.mark.parametrize("host", ["Thurstons-MacBook-Pro", "ML-DFC6YK6VJQ"])
@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "tags,remaining,theme",
    [
        ("", "", True),
        ("terminal-theme", None, True),
        ("chezmoi,terminal-theme,homebrew", "chezmoi,homebrew", True),
        ("chezmoi", "chezmoi", False),
        ("terminal-theme-extra", "terminal-theme-extra", False),
        ("all", "all", True),
    ],
)
def test_laptop_dispatches_native_theme_outside_ansible(
    tmp_path: Path,
    task: str,
    host: str,
    check: bool,
    tags: str,
    remaining: str | None,
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
    if not check:
        expected.append("mise run //:mise:maintain")
    if remaining is not None:
        work = host == "ML-DFC6YK6VJQ"
        playbook = "work" if work else "macos"
        secret = (
            "HOMEBREW_SUDO_ASKPASS_PASS_WORK" if work else "HOMEBREW_SUDO_ASKPASS_PASS"
        )
        arguments = f"-i inventory/control/macos.ini playbooks/{playbook}.yml" + suffix
        if remaining:
            arguments += f" --tags {remaining}"
        expected.append(
            f"fnox exec --secret {secret}"
            + (" --secret ANTHROPIC_AUTH_TOKEN" if work else "")
            + f" -- ansible-playbook {arguments}"
        )
        expected.append(f"ansible {arguments}")
    if theme:
        expected.append("mise run //:terminal-theme" + suffix)
    assert calls == expected


@pytest.mark.parametrize("failure", ["mise:maintain", "ansible"])
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
        assert calls == ["mise run //:mise:maintain"]


def test_ansible_no_longer_owns_terminal_theme() -> None:
    assert not (ROOT / "ansible/roles/terminal_theme/tasks/main.yml").exists()
    for playbook in ("macos", "work"):
        assert (
            "terminal_theme"
            not in (ROOT / f"ansible/playbooks/{playbook}.yml").read_text()
        )
