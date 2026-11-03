#!/usr/bin/env python3
"""Install the Reminders MCP server that pod153 serves to executor.sh, nurb's engine, and pod153's Python."""

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import urllib.request

HOME = Path.home()
REMCTL = HOME / "bin/remctl"
REMCTL_RELEASES = "https://github.com/viticci/remctl/releases"
# The scheduled reconcile needs Full Disk Access and Automation, and macOS keys both grants to
# the Python binary it runs on. python.org signs its builds with
# the PSF's Developer ID, so the grants survive upgrades; Homebrew's ad-hoc signed Python
# lost them on every release.
PYTHON_API = "https://www.python.org/api/v2/downloads"
PYTHON_TEAM = "BMM5U3QVKW"
PYTHON_FRAMEWORK = Path("/Library/Frameworks/Python.framework/Versions")
# A new minor waits this long for its first bug fixes and for wheels to catch up.
PYTHON_MINOR_GRACE = timedelta(days=14)
# The framework ships no CA bundle; the package's Install Certificates command, which a
# framework-only install skips, would add certifi's. macOS keeps its own bundle current.
SYSTEM_CA_BUNDLE = Path("/etc/ssl/cert.pem")
# imsgbus in cupertino replaced mac-messages-mcp; delete these once pod153 converges.
RETIRED_MESSAGES_TOOL = "mac-messages-mcp"
RETIRED_MESSAGES_ENV = HOME / ".local/share/uv/tools" / RETIRED_MESSAGES_TOOL
RETIRED_MESSAGES_STATE = HOME / ".local/state/ansiblonomicon/messages-mcp.python"
RETIRED_MESSAGES_AGENT = "dev.mise.house.thurstons.messages-mcp"
# nurb ships as a desktop app whose engine wheel carries no workbench page, since the app
# shows its own copy, so the serve is built from the release's source, page included.
NURB_REPO = "https://github.com/Shpigford/nurb"
NURB = HOME / ".local/share/nurb"
NURB_ENV = NURB / "env"
# What the desktop app provisions the engine on.
NURB_PYTHON = "3.13"
AGENTS = {
    "remctl": "dev.mise.house.thurstons.remctl-mcp",
    "nurb": "dev.mise.house.thurstons.nurb",
}


def latest_release(releases: str) -> str:
    with urllib.request.urlopen(f"{releases}/latest", timeout=60) as response:
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


def installed_nurb() -> str | None:
    python = NURB_ENV / "bin/python"
    if not python.exists():
        return None
    return subprocess.run(
        [python, "-c", "import importlib.metadata as m; print(m.version('nurb'))"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def install_nurb(version: str) -> None:
    env = NURB / version
    python = env / "bin/python"
    with tempfile.TemporaryDirectory(prefix="ansiblonomicon-nurb.") as tmp:
        source = Path(tmp) / "nurb"
        subprocess.run(
            [
                "git",
                "-c",
                "advice.detachedHead=false",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                f"v{version}",
                NURB_REPO,
                source,
            ],
            check=True,
        )
        # Vite writes the page into the engine package, which the install then carries.
        workbench = ["--workspace", "packages/workbench"]
        subprocess.run(
            ["npm", "ci", *workbench, "--no-fund", "--no-audit", "--loglevel=error"],
            cwd=source,
            check=True,
        )
        subprocess.run(
            ["npm", "run", "build", *workbench, "--silent", "--", "--logLevel=error"],
            cwd=source,
            check=True,
        )
        requirements = Path(tmp) / "requirements.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--project",
                source / "engine",
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--quiet",
                "--output-file",
                requirements,
            ],
            check=True,
        )
        subprocess.run(
            [
                "uv",
                "venv",
                "--quiet",
                "--clear",
                "--python",
                NURB_PYTHON,
                "--managed-python",
                env,
            ],
            check=True,
        )
        subprocess.run(
            ["uv", "pip", "sync", "--quiet", "--python", python, requirements],
            check=True,
        )
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--quiet",
                "--no-deps",
                "--python",
                python,
                source / "engine",
            ],
            check=True,
        )
    staged = NURB_ENV.with_name(".env.new")
    staged.unlink(missing_ok=True)
    staged.symlink_to(version)
    staged.replace(NURB_ENV)
    for old in NURB.iterdir():
        if old.is_dir() and not old.is_symlink() and old.name != version:
            shutil.rmtree(old)


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


def link_ca_bundles(check: bool) -> None:
    for framework in PYTHON_FRAMEWORK.iterdir():
        bundle = framework / "etc/openssl/cert.pem"
        if framework.is_symlink() or (
            bundle.is_symlink() and bundle.readlink() == SYSTEM_CA_BUNDLE
        ):
            continue
        if check:
            print(f"server: would link {bundle} to {SYSTEM_CA_BUNDLE}")
        else:
            bundle.unlink(missing_ok=True)
            bundle.symlink_to(SYSTEM_CA_BUNDLE)
            print(f"server: linked {bundle} to {SYSTEM_CA_BUNDLE}")


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

    # Before any download: this script runs on the framework's python3.
    link_ca_bundles(args.check)
    installed, latest = installed_remctl(), latest_release(REMCTL_RELEASES)
    if installed != latest:
        if args.check:
            print(f"server: would install RemCTL {latest} (have {installed})")
        else:
            install_remctl()
            restart("remctl")
            print(f"server: installed RemCTL {latest}")

    installed, latest = installed_nurb(), latest_release(f"{NURB_REPO}/releases")
    if installed != latest:
        if args.check:
            print(f"server: would install nurb {latest} (have {installed})")
        else:
            install_nurb(latest)
            restart("nurb")
            print(f"server: installed nurb {latest}")

    python, release = latest_python()
    if not installed_python(python):
        if args.check:
            print(f"server: would install Python {python}")
        else:
            install_python(python, release)
            link_ca_bundles(args.check)
            print(f"server: installed Python {python}")

    if RETIRED_MESSAGES_ENV.exists():
        if args.check:
            print(f"server: would retire {RETIRED_MESSAGES_TOOL}")
        else:
            # The plist goes with the files step; a job outlives its plist until it is booted out.
            subprocess.run(
                ["launchctl", "bootout", f"gui/{os.getuid()}/{RETIRED_MESSAGES_AGENT}"]
            )
            subprocess.run(
                ["uv", "tool", "uninstall", RETIRED_MESSAGES_TOOL], check=True
            )
            RETIRED_MESSAGES_STATE.unlink(missing_ok=True)
            print(f"server: retired {RETIRED_MESSAGES_TOOL}")


if __name__ == "__main__":
    main()
