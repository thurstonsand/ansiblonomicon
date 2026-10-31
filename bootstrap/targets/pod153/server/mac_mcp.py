#!/usr/bin/env python3
"""Install the Messages and Reminders MCP servers that pod153 serves to executor.sh."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

HOME = Path.home()
REMCTL = HOME / "bin/remctl"
REMCTL_RELEASES = "https://github.com/viticci/remctl/releases"
# Homebrew's Python already holds the Full Disk Access grant the scheduled reconcile needs,
# so the Messages server shares that grant instead of needing its own.
MESSAGES_PYTHON = "/opt/homebrew/opt/python@3/bin/python3"
MESSAGES_TOOL = "mac-messages-mcp"
# Releases trail main by months, and main carries contact-scoped search, conversation
# listing, and paging, so track main.
MESSAGES_REPO = "https://github.com/carterlasalle/mac_messages_mcp"
MESSAGES_SOURCE = f"{MESSAGES_TOOL} @ git+{MESSAGES_REPO}"
MESSAGES_ENV = HOME / ".local/share/uv/tools" / MESSAGES_TOOL
AGENTS = {
    "remctl": "dev.mise.house.thurstons.remctl-mcp",
    "messages": "dev.mise.house.thurstons.messages-mcp",
}


def latest_remctl() -> str:
    with urllib.request.urlopen(f"{REMCTL_RELEASES}/latest", timeout=60) as response:
        return response.url.rsplit("/v", 1)[1]


def installed_remctl() -> str | None:
    if not REMCTL.exists():
        return None
    return subprocess.run(
        [REMCTL, "--version"], check=True, text=True, capture_output=True
    ).stdout.strip()


def install_remctl() -> None:
    with tempfile.TemporaryDirectory(prefix="ansiblonomicon-remctl.") as tmp:
        image = Path(tmp) / "RemCTL.dmg"
        mount = Path(tmp) / "mounted"
        mount.mkdir()
        urllib.request.urlretrieve(
            f"{REMCTL_RELEASES}/latest/download/RemCTL-arm64.dmg", image
        )
        subprocess.run(
            [
                "hdiutil",
                "attach",
                image,
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                mount,
                "-quiet",
            ],
            check=True,
        )
        try:
            # What the image's "Install RemCTL" app runs; the installer verifies the
            # MacStories Developer ID before it copies anything.
            app = mount / "RemCTL Capability Host.app"
            subprocess.run(
                [
                    "/bin/bash",
                    app / "Contents/Resources/Distribution/install.sh",
                    "--prebuilt",
                    app,
                    "--bootstrap",
                ],
                check=True,
                stdin=subprocess.DEVNULL,
            )
        finally:
            subprocess.run(["hdiutil", "detach", mount, "-quiet"], check=True)


def messages_versions() -> str | None:
    if not (MESSAGES_ENV / "bin/python").exists():
        return None
    return subprocess.run(
        ["uv", "pip", "freeze", "--python", MESSAGES_ENV / "bin/python"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def restart(agent: str) -> None:
    label = f"gui/{os.getuid()}/{AGENTS[agent]}"
    if (
        subprocess.run(["launchctl", "print", label], capture_output=True).returncode
        == 0
    ):
        subprocess.run(["launchctl", "kickstart", "-k", label], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    installed, latest = installed_remctl(), latest_remctl()
    if installed != latest:
        if args.check:
            print(f"server: would install RemCTL {latest} (have {installed})")
        else:
            install_remctl()
            restart("remctl")
            print(f"server: installed RemCTL {latest}")

    if args.check:
        head = subprocess.run(
            ["git", "ls-remote", MESSAGES_REPO, "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.split()[0]
        if f"{MESSAGES_REPO}@{head}" not in (messages_versions() or ""):
            print(f"server: would install {MESSAGES_TOOL} {head[:7]}")
        return
    before = messages_versions()
    subprocess.run(
        [
            "uv",
            "tool",
            "install",
            "--upgrade",
            "--quiet",
            "--python",
            MESSAGES_PYTHON,
            MESSAGES_SOURCE,
            "--with-executables-from",
            "mcp-proxy",
        ],
        check=True,
    )
    if messages_versions() != before:
        restart("messages")
        print(f"server: installed {MESSAGES_TOOL}")


if __name__ == "__main__":
    main()
