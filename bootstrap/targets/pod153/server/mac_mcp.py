#!/usr/bin/env python3
"""Install the Messages and Reminders MCP servers that pod153 serves to executor.sh, and pod153's Python."""

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import urllib.request

HOME = Path.home()
REMCTL = HOME / "bin/remctl"
REMCTL_RELEASES = "https://github.com/viticci/remctl/releases"
# The scheduled reconcile and the Messages server need Full Disk Access and Automation, and
# macOS keys both grants to the Python binary they run on. python.org signs its builds with
# the PSF's Developer ID, so the grants survive upgrades; Homebrew's ad-hoc signed Python
# lost them on every release.
PYTHON_API = "https://www.python.org/api/v2/downloads"
PYTHON_TEAM = "BMM5U3QVKW"
PYTHON_FRAMEWORK = Path("/Library/Frameworks/Python.framework/Versions")
# A new minor waits this long for its first bug fixes and for wheels to catch up.
PYTHON_MINOR_GRACE = timedelta(days=14)
MESSAGES_TOOL = "mac-messages-mcp"
# Releases trail main by months, and main carries contact-scoped search, conversation
# listing, and paging, so track main.
MESSAGES_REPO = "https://github.com/carterlasalle/mac_messages_mcp"
MESSAGES_SOURCE = f"{MESSAGES_TOOL} @ git+{MESSAGES_REPO}"
MESSAGES_ENV = HOME / ".local/share/uv/tools" / MESSAGES_TOOL
# A patch release replaces the interpreter in place, so the environment looks unchanged
# while the running server still holds the old one; this records the Python it started on.
MESSAGES_STARTED_ON = HOME / ".local/state/ansiblonomicon/messages-mcp.python"
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


def fetch_json(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def latest_python() -> tuple[str, str]:
    """The newest release of any minor at least PYTHON_MINOR_GRACE old, and its release URI."""
    releases: dict[tuple[int, ...], tuple[datetime, str]] = {}
    for release in fetch_json(
        f"{PYTHON_API}/release/?is_published=true&pre_release=false"
    ):
        match = re.fullmatch(r"Python (3\.\d+\.\d+)", release["name"])
        if match:
            version = tuple(int(part) for part in match[1].split("."))
            date = datetime.fromisoformat(release["release_date"])
            releases[version] = (date, release["resource_uri"])
    first_release: dict[tuple[int, ...], datetime] = {}
    for version, (date, _) in releases.items():
        first_release[version[:2]] = min(date, first_release.get(version[:2], date))
    cutoff = datetime.now(UTC) - PYTHON_MINOR_GRACE
    version = max(v for v in releases if first_release[v[:2]] <= cutoff)
    return ".".join(map(str, version)), releases[version][1]


def python_binary(version: str) -> Path:
    minor = version.rsplit(".", 1)[0]
    return PYTHON_FRAMEWORK / minor / "bin" / f"python{minor}"


def installed_python(version: str) -> bool:
    binary = python_binary(version)
    return (
        binary.exists()
        and subprocess.run(
            [binary, "--version"], check=True, text=True, capture_output=True
        ).stdout.strip()
        == f"Python {version}"
    )


def install_python(version: str, release: str) -> None:
    release_id = release.rstrip("/").rsplit("/", 1)[1]
    (package,) = (
        file
        for file in fetch_json(f"{PYTHON_API}/release_file/?release={release_id}")
        if re.fullmatch(rf".*/python-{re.escape(version)}-macos\d+\.pkg", file["url"])
    )
    with tempfile.TemporaryDirectory(prefix="ansiblonomicon-python.") as tmp:
        pkg = Path(tmp) / "python.pkg"
        urllib.request.urlretrieve(package["url"], pkg)
        if hashlib.sha256(pkg.read_bytes()).hexdigest() != package["sha256_sum"]:
            raise SystemExit(
                f"server: {package['url']} does not match its published SHA-256"
            )
        signature = subprocess.run(
            ["pkgutil", "--check-signature", pkg],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        if f"Python Software Foundation ({PYTHON_TEAM})" not in signature or (
            "Notarization: trusted" not in signature
        ):
            raise SystemExit(
                f"server: {package['url']} is not the PSF's notarized package\n{signature}"
            )
        # Only the framework: the other choices add /usr/local/bin links, IDLE, docs, and a
        # profile updater that edits ~/.zprofile.
        choices = plistlib.loads(
            subprocess.run(
                ["installer", "-showChoiceChangesXML", "-pkg", pkg],
                check=True,
                capture_output=True,
            ).stdout
        )
        for choice in choices:
            if choice["choiceAttribute"] == "selected":
                choice["attributeSetting"] = int(
                    choice["choiceIdentifier"].startswith(
                        "org.python.Python.PythonFramework-"
                    )
                )
        choices_file = Path(tmp) / "choices.plist"
        choices_file.write_bytes(plistlib.dumps(choices))
        subprocess.run(
            [
                "sudo",
                "-n",
                "installer",
                "-pkg",
                pkg,
                "-applyChoiceChangesXML",
                choices_file,
                "-target",
                "/",
            ],
            check=True,
        )


def messages_versions() -> str | None:
    python = MESSAGES_ENV / "bin/python"
    if not python.exists():
        return None
    return (
        f"{python.resolve()}\n"
        + subprocess.run(
            ["uv", "pip", "freeze", "--python", python],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    )


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

    python, release = latest_python()
    if not installed_python(python):
        if args.check:
            print(f"server: would install Python {python}")
        else:
            install_python(python, release)
            print(f"server: installed Python {python}")

    if args.check:
        head = subprocess.run(
            ["git", "ls-remote", MESSAGES_REPO, "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.split()[0]
        installed = messages_versions() or ""
        if f"{MESSAGES_REPO}@{head}" not in installed or not installed.startswith(
            f"{python_binary(python)}\n"
        ):
            print(
                f"server: would install {MESSAGES_TOOL} {head[:7]} on Python {python}"
            )
        elif (
            not MESSAGES_STARTED_ON.exists()
            or MESSAGES_STARTED_ON.read_text() != python
        ):
            print(f"server: would restart {MESSAGES_TOOL} on Python {python}")
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
            python_binary(python),
            MESSAGES_SOURCE,
            "--with-executables-from",
            "mcp-proxy",
        ],
        check=True,
    )
    started_on = (
        MESSAGES_STARTED_ON.read_text() if MESSAGES_STARTED_ON.exists() else None
    )
    if started_on != python or messages_versions() != before:
        restart("messages")
        MESSAGES_STARTED_ON.parent.mkdir(parents=True, exist_ok=True)
        MESSAGES_STARTED_ON.write_text(python)
        print(f"server: restarted {MESSAGES_TOOL} on Python {python}")


if __name__ == "__main__":
    main()
