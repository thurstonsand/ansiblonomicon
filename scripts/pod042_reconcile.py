#!/usr/bin/env python3
"""Reconcile pod042 in place through its native mise bootstrap target."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import socket
import subprocess
import sys
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOT = ROOT / "bootstrap" / "targets" / "pod042"
EXPECTED_HOSTNAME = "pod042"
CONTAINER_SECRETS = (
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_TOKEN",
    "DDCLIENT_GITHUB_PAT",
    "GHOST_DB_PASSWORD",
    "GHOST_MAIL_AUTH_PASS",
    "GHOST_MYSQL_ROOT_PASSWORD",
    "HARK_WEBHOOK_URL_POD042",
    "HEALTHCHECKS_API_KEY",
    "HOMEASSISTANT_API_KEY",
    "HOMEPAGE_OVERSEERR_API_KEY",
    "HOMEPAGE_PLEX_API_KEY",
    "NETDATA_CLAIM_TOKEN",
    "NEXTDNS_API_KEY",
    "NEXTDNS_PROFILE_ID",
    "PROWLARR_API_KEY",
    "QBITTORRENT_PASSWORD",
    "QBITTORRENT_USERNAME",
    "RADARR_API_KEY",
    "SONARR_API_KEY",
    "TORRENT_WIREGUARD_ADDRESS",
    "TORRENT_WIREGUARD_PRIVATE_KEY",
    "UNIFI_PASSWORD",
    "UNIFI_USERNAME",
    "XGS_PON_PASSWORD",
)
CAPABILITIES = (
    "base",
    "network",
    "repositories",
    "storage",
    "alerting",
    "containers",
    "maintenance",
    "monitoring",
    "datasets",
    "incus",
    "home-assistant",
    "sharing",
    "snapshots",
    "terminal-tools",
    "operator",
    "git-client",
    "jj-client",
    "ssh-client",
    "agent-harness",
    "remote-development",
    "terminal-theme",
    "shell",
    "user-tools",
    "neovim",
    "doppelclaude",
)
_VCS_CLIENT_INDEX = CAPABILITIES.index("git-client")
FULL_CAPABILITIES = (
    *CAPABILITIES[:_VCS_CLIENT_INDEX],
    "vcs-identity",
    *CAPABILITIES[_VCS_CLIENT_INDEX:],
    "terminal-tools-plugins",
    "shell-personal",
    "user-tools-personal",
    "neovim-personal",
    "ssh-client-pod042",
)


class ReconcileError(Exception):
    pass


def run_command(
    argv: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def command_output(argv: Sequence[str]) -> str:
    return run_command(argv, capture_output=True).stdout.strip()


def fail(message: str) -> NoReturn:
    raise ReconcileError(message)


def assert_hostname() -> None:
    actual = socket.gethostname().split(".", maxsplit=1)[0]
    if actual != EXPECTED_HOSTNAME:
        fail(f"pod042 target requires hostname {EXPECTED_HOSTNAME!r}, got {actual!r}")


def capabilities_for(capability: str | None) -> tuple[str, ...]:
    if capability is None:
        return FULL_CAPABILITIES
    if capability == "network":
        return ("repositories", "network")
    if capability == "operator":
        return ("base", "operator")
    if capability == "git-client":
        return ("vcs-identity", "git-client")
    if capability == "jj-client":
        return ("vcs-identity", "jj-client")
    if capability == "ssh-client":
        return ("ssh-client", "ssh-client-pod042")
    if capability == "agent-harness":
        return ("base", "operator", "agent-harness")
    if capability == "remote-development":
        return ("base", "operator", "agent-harness", "remote-development")
    if capability == "terminal-theme":
        return ("terminal-theme",)
    if capability == "shell":
        return ("shell", "shell-personal")
    if capability == "user-tools":
        return ("user-tools", "user-tools-personal")
    if capability in ("neovim", "nvim-deps"):
        return ("neovim", "neovim-personal")
    if capability in ("terminal-tools", "tmux"):
        return ("terminal-tools", "terminal-tools-plugins")
    if capability == "storage":
        return ("repositories", "storage")
    if capability == "maintenance":
        return ("repositories", "storage", "alerting", "maintenance")
    if capability == "containers":
        return ("repositories", "storage", "alerting", "containers")
    if capability == "monitoring":
        return ("repositories", "storage", "alerting", "maintenance", "monitoring")
    if capability == "datasets":
        return ("repositories", "storage", "alerting", "maintenance", "datasets")
    if capability == "incus":
        return ("network", "repositories", "storage", "datasets", "incus")
    if capability == "home-assistant":
        return (
            "network",
            "repositories",
            "storage",
            "datasets",
            "incus",
            "home-assistant",
        )
    if capability == "sharing":
        return ("repositories", "storage", "datasets", "sharing")
    if capability == "snapshots":
        return (
            "repositories",
            "storage",
            "alerting",
            "maintenance",
            "monitoring",
            "datasets",
            "snapshots",
        )
    if capability not in CAPABILITIES:
        fail(f"unknown pod042 capability: {capability}")
    return (capability,)


def run_local(capability: str | None, check_mode: bool) -> None:
    assert_hostname()
    selected = capabilities_for(capability)
    root_capabilities = {
        "vcs-identity",
        "git-client",
        "jj-client",
        "ssh-client",
        "ssh-client-pod042",
        "terminal-theme",
        "shell",
        "shell-personal",
        "user-tools",
        "user-tools-personal",
        "neovim",
        "neovim-personal",
        "terminal-tools",
        "terminal-tools-plugins",
    }
    if "doppelclaude" in selected:
        run_command(["findmnt", "--mountpoint", "/mnt/black-box/docker"])
        run_command(["sudo", "-n", "docker", "network", "inspect", "ingress"])
    bootstrap_capabilities = tuple(
        item for item in selected if item not in root_capabilities
    )
    environments = ",".join(bootstrap_capabilities)
    command = [
        "env",
        f"MISE_CEILING_PATHS={TARGET_ROOT.parent}",
        f"MISE_TRUSTED_CONFIG_PATHS={TARGET_ROOT}",
        f"MISE_ENV={environments}",
        *(("MISE_JOBS=1",) if capability == "containers" else ()),
        "mise",
        "-C",
        str(TARGET_ROOT),
    ]
    if "containers" in selected or "monitoring" in selected:
        command = [
            sys.executable,
            "-B",
            str(TARGET_ROOT / "monitoring/api/reconcile.py"),
            *(["--check"] if check_mode else []),
            "--",
            *command,
        ]
    if any(
        item in selected
        for item in ("alerting", "containers", "sharing", "doppelclaude")
    ):
        secrets: list[str] = list(CONTAINER_SECRETS) if "containers" in selected else []
        if "alerting" in selected and "HARK_WEBHOOK_URL_POD042" not in secrets:
            secrets.append("HARK_WEBHOOK_URL_POD042")
        if "monitoring" in selected:
            secrets.append("HEALTHCHECKS_API_KEY")
        if "sharing" in selected:
            secrets.append("SAMBA_MEDIA_PASSWORD")
        if "doppelclaude" in selected:
            secrets.extend(("CLI_PROXY_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"))
        command = [
            sys.executable,
            "-B",
            str(ROOT / "scripts/fnox-host"),
            "exec",
            *(argument for secret in secrets for argument in ("--secret", secret)),
            "--",
            *command,
        ]
    if check_mode:
        if bootstrap_capabilities:
            run_command([*command, "bootstrap", "plan"])
        if "terminal-theme" in selected:
            run_command(
                [
                    "mise",
                    "-C",
                    str(ROOT),
                    "run",
                    "terminal-theme",
                    "--check",
                ]
            )
        if "git-client" in selected:
            run_command(
                [
                    "mise",
                    "-C",
                    str(ROOT),
                    "run",
                    "git-client",
                    "--check",
                ]
            )
        if "jj-client" in selected:
            run_command(
                [
                    "mise",
                    "-C",
                    str(ROOT),
                    "run",
                    "jj-client",
                    "--check",
                ]
            )
        if "ssh-client" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "ssh-client", "--check"])
        if "shell" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "shell", "--check"])
        if "terminal-tools" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "terminal-tools", "--check"])
        if "user-tools" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "user-tools", "--check"])
        if "neovim" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "neovim", "--check"])
        if "base" in selected:
            run_command(
                [
                    "sudo",
                    "-n",
                    "/usr/bin/python3",
                    str(TARGET_ROOT / "base/check.py"),
                ]
            )
        if "datasets" in selected:
            run_command(
                [
                    "sudo",
                    "-n",
                    "/usr/bin/python3",
                    str(TARGET_ROOT / "datasets/reconcile.py"),
                    "check",
                ]
            )
        if "maintenance" in selected:
            run_command(
                [
                    "/usr/bin/python3",
                    str(TARGET_ROOT / "maintenance/zed/pool-policy.py"),
                ]
            )
        if "network" in selected:
            run_command(
                [
                    "sudo",
                    "-n",
                    "/usr/bin/python3",
                    str(TARGET_ROOT / "network/check.py"),
                ]
            )
        if "incus" in selected:
            run_command(
                [
                    "sudo",
                    "-n",
                    "/usr/bin/python3",
                    str(TARGET_ROOT / "incus/reconcile.py"),
                    "check",
                ]
            )
        if "home-assistant" in selected:
            run_command(
                [
                    "sudo",
                    "-n",
                    "/usr/bin/python3",
                    str(TARGET_ROOT / "incus/home_assistant.py"),
                    "check",
                ]
            )
    else:
        if capability != "doppelclaude":
            run_command(
                [
                    "mise",
                    "-C",
                    str(TARGET_ROOT),
                    "run",
                    "mise:maintain",
                ]
            )
        if "base" in selected:
            # Mise applies accounts before packages; the login shell must exist first.
            run_command(
                [
                    "env",
                    f"MISE_CEILING_PATHS={TARGET_ROOT.parent}",
                    f"MISE_TRUSTED_CONFIG_PATHS={TARGET_ROOT}",
                    "MISE_ENV=base",
                    "mise",
                    "-C",
                    str(TARGET_ROOT),
                    "bootstrap",
                    "--only",
                    "packages",
                    "--yes",
                ]
            )
        if bootstrap_capabilities:
            run_command([*command, "bootstrap", "--yes"])
        if "terminal-theme" in selected:
            run_command(
                [
                    "mise",
                    "-C",
                    str(ROOT),
                    "run",
                    "terminal-theme",
                ]
            )
        if "git-client" in selected:
            run_command(
                [
                    "mise",
                    "-C",
                    str(ROOT),
                    "run",
                    "git-client",
                ]
            )
        if "jj-client" in selected:
            run_command(
                [
                    "mise",
                    "-C",
                    str(ROOT),
                    "run",
                    "jj-client",
                ]
            )
        if "ssh-client" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "ssh-client"])
        if "shell" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "shell"])
        if "terminal-tools" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "terminal-tools"])
        if "user-tools" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "user-tools"])
        if "neovim" in selected:
            run_command(["mise", "-C", str(ROOT), "run", "neovim"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capability", nargs="?")
    parser.add_argument("--check", action="store_true")
    return parser


def run(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    run_local(args.capability, args.check)
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (ReconcileError, subprocess.CalledProcessError) as error:
        print(f"pod042: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
