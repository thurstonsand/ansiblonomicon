from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/ssh-client"


def fixture(
    tmp_path: Path, *, host_os: str, host: str, keys: bool
) -> tuple[Path, dict[str, str]]:
    target = tmp_path / "target"
    home = tmp_path / "home"
    target.mkdir()
    home.mkdir()
    (target / "ssh-client").symlink_to(CAPABILITY / "files", target_is_directory=True)
    (target / "mise.ssh-client.toml").symlink_to(CAPABILITY / "mise.toml")
    environments = ["ssh-client"]
    if keys:
        (target / "mise.ssh-client-pod042.toml").symlink_to(
            CAPABILITY / "mise.pod042.toml"
        )
        environments.append("ssh-client-pod042")
    (target / "mise.toml").write_text(
        f'[vars]\nhost_os = "{host_os}"\nssh_client_host = "{host}"\n'
    )
    inherited = os.environ.copy()
    inherited.pop("POD042_GIT_SSH_PRIVATE_KEY", None)
    inherited.pop("POD042_GIT_SSH_PUBLIC_KEY", None)
    env = {
        **inherited,
        "HOME": str(home),
        "MISE_DATA_DIR": str(tmp_path / "data"),
        "MISE_CACHE_DIR": str(tmp_path / "cache"),
        "MISE_STATE_DIR": str(tmp_path / "state"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(target / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(target / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(tmp_path),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "MISE_ENV": ",".join(environments),
    }
    return target, env


def generate_key_pair(tmp_path: Path) -> tuple[str, str]:
    private_key = tmp_path / "generated-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
    )
    return private_key.read_text(), private_key.with_suffix(".pub").read_text()


def ssh_settings(config: Path, env: dict[str, str], alias: str) -> dict[str, str]:
    result = subprocess.run(
        ["ssh", "-F", str(config), "-G", alias],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return dict(line.split(maxsplit=1) for line in result.stdout.splitlines())


def bootstrap(
    target: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "mise",
            "-C",
            str(target),
            "bootstrap",
            "--only",
            "files,dotfiles",
            "--force-dotfiles",
            *args,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("host_os", "host", "keys"),
    [("darwin", "Thurstons-MacBook-Pro", False), ("linux", "pod042", True)],
)
def test_real_mise_renders_parsable_private_config_and_stable_repeat(
    tmp_path: Path, host_os: str, host: str, keys: bool
) -> None:
    target, env = fixture(tmp_path, host_os=host_os, host=host, keys=keys)
    private_key, public_key = generate_key_pair(tmp_path)
    env.update(
        POD042_GIT_SSH_PRIVATE_KEY=f"\n{private_key}\n",
        POD042_GIT_SSH_PUBLIC_KEY=f"\n{public_key}\n",
    )
    home = Path(env["HOME"])
    unrelated = home / ".ssh/known_hosts"
    unrelated.parent.mkdir()
    unrelated.write_text("fixture-host fixture-key\n")
    config = home / ".ssh/config"
    config.write_text("stale config\n")
    config.chmod(0o664)

    applied = bootstrap(target, env, "--yes")
    assert applied.returncode == 0, applied.stderr
    proxy = home / ".local/libexec/ssh-smart-proxy"
    assert stat.S_IMODE((home / ".ssh").stat().st_mode) == 0o700
    assert stat.S_ISREG(config.stat().st_mode)
    assert stat.S_IMODE(config.stat().st_mode) == 0o644
    assert stat.S_IMODE(proxy.stat().st_mode) == 0o755
    assert unrelated.read_text() == "fixture-host fixture-key\n"
    repeated_paths = [config, proxy]
    if keys:
        rendered_private = home / ".ssh/id_ed25519_git"
        rendered_public = home / ".ssh/id_ed25519_git.pub"
        assert rendered_private.read_text() == private_key.strip() + "\n"
        assert rendered_public.read_text() == public_key.strip() + "\n"
        assert stat.S_IMODE(rendered_private.stat().st_mode) == 0o600
        assert stat.S_IMODE(rendered_public.stat().st_mode) == 0o644
        derived = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(rendered_private)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert derived[:2] == public_key.split()[:2]
        repeated_paths.extend((rendered_private, rendered_public))

    aliases = [
        line.split()[1]
        for line in config.read_text().splitlines()
        if line.startswith("Host ") and "*" not in line
    ]
    assert aliases
    for alias in aliases:
        settings = ssh_settings(config, env, alias)
        assert settings["addkeystoagent"] == "false"
        if host_os == "darwin":
            assert settings["identityagent"].endswith(
                "2BUA8C4S2C.com.1password/t/agent.sock"
            )
        else:
            assert "identityagent" not in settings

    before = {
        path: (path.stat().st_ino, path.stat().st_mtime_ns) for path in repeated_paths
    }
    repeated = bootstrap(target, env, "--yes")
    assert repeated.returncode == 0, repeated.stderr
    assert {
        path: (path.stat().st_ino, path.stat().st_mtime_ns) for path in before
    } == before


def test_missing_secrets_fail_before_any_write_and_values_are_not_logged(
    tmp_path: Path,
) -> None:
    target, env = fixture(tmp_path, host_os="linux", host="pod042", keys=True)
    failed = bootstrap(target, env, "--yes")
    assert failed.returncode != 0
    assert not (Path(env["HOME"]) / ".ssh").exists()

    private = "fixture-private-never-log"
    public = "fixture-public-never-log"
    env.update(
        POD042_GIT_SSH_PRIVATE_KEY=private,
        POD042_GIT_SSH_PUBLIC_KEY=public,
    )
    applied = bootstrap(target, env, "--yes")
    assert applied.returncode == 0, applied.stderr
    assert private not in applied.stdout + applied.stderr
    assert public not in applied.stdout + applied.stderr


@pytest.mark.parametrize(
    ("host_os", "ping_status", "nc_probe_status", "expected"),
    [
        ("linux", 0, 1, ["ping:-c 1 -W 1 10.0.0.2", "nc:10.0.0.2 22"]),
        (
            "linux",
            1,
            0,
            [
                "ping:-c 1 -W 1 10.0.0.2",
                "nc:-z -w 1 10.0.0.2 22",
                "nc:10.0.0.2 22",
            ],
        ),
        (
            "darwin",
            1,
            1,
            [
                "ping:-c 1 -W 1000 10.0.0.2",
                "nc:-z -G 1 10.0.0.2 22",
                "cloudflared:access ssh --hostname tunnel.example",
            ],
        ),
    ],
)
def test_proxy_probes_local_first_then_selects_connection(
    tmp_path: Path,
    host_os: str,
    ping_status: int,
    nc_probe_status: int,
    expected: list[str],
) -> None:
    target, env = fixture(
        tmp_path,
        host_os=host_os,
        host="pod042" if host_os == "linux" else "Thurstons-MacBook-Pro",
        keys=False,
    )
    applied = bootstrap(target, env, "--yes")
    assert applied.returncode == 0, applied.stderr
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "calls"
    for command, body in {
        "ping": f'echo "ping:$*" >> "$CALL_LOG"\nexit {ping_status}\n',
        "nc": (
            'echo "nc:$*" >> "$CALL_LOG"\n'
            f'case "$1" in -z) exit {nc_probe_status} ;; esac\nexit 0\n'
        ),
        "cloudflared": 'echo "cloudflared:$*" >> "$CALL_LOG"\nexit 0\n',
    }.items():
        path = fake_bin / command
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
    env.update(PATH=f"{fake_bin}:{env['PATH']}", CALL_LOG=str(log))
    proxy = Path(env["HOME"]) / ".local/libexec/ssh-smart-proxy"
    result = subprocess.run(
        [str(proxy), "alias", "10.0.0.2", "22", "tunnel.example"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == expected
