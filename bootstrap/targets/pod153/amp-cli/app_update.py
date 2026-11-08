#!/usr/bin/env python3
"""Install Amp.app's staged Sparkle update once its runner has no thread working, like the CLI runner does."""

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import time

APP = Path("/Applications/Amp.app")
BUNDLE_ID = "com.ampcode.amp.macos"
# Sparkle extracts each downloaded update into its own directory here, then waits in Autoupdate for the app
# to quit, which it never does on a server, and downloads nothing newer meanwhile.
STAGING = (
    Path.home()
    / "Library/Caches"
    / BUNDLE_ID
    / "org.sparkle-project.Sparkle/Installation"
)
# The app's runner logs every agent state change, per thread, to no-tui.log, rotating it about twice a day.
RUNNER_LOGS = Path.home() / ".cache/amp/logs"
IDLE_STATES = {"idle", "error", "disconnected"}
# The CLI runner applies its own updates at most this often; a restart drops the runner's portals and desktop.
COOLDOWN = timedelta(hours=12)
# Twelve hours past the cooldown, a staged update still waiting means the runner never went idle or this broke.
STALE = timedelta(hours=24)


def output(*command: str) -> str:
    return subprocess.run(command, text=True, capture_output=True).stdout


def log(message: str) -> None:
    print(f"{datetime.now():%F %T} {message}", flush=True)


def build(app: Path) -> int:
    with open(app / "Contents/Info.plist", "rb") as info:
        return int(plistlib.load(info)["CFBundleVersion"])


def staged() -> tuple[int, datetime] | None:
    """The newest staged build newer than the installed one, and when Sparkle staged it."""
    installed = build(APP)
    candidates = [
        (build(app), datetime.fromtimestamp(app.parents[1].stat().st_mtime))
        for app in STAGING.glob("*/*/Amp.app")
        if build(app) > installed
    ]
    return max(candidates, default=None)


def updater() -> int | None:
    for pid in output("pgrep", "-x", "Autoupdate").split():
        if f"/Autoupdate {BUNDLE_ID} " in output("ps", "-o", "args=", "-p", pid):
            return int(pid)
    return None


def running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def started(pid: int) -> datetime:
    return datetime.strptime(
        " ".join(output("ps", "-o", "lstart=", "-p", str(pid)).split()),
        "%a %b %d %H:%M:%S %Y",
    )


def busy_threads(runner: int) -> list[str]:
    """Threads whose latest logged agent state for this runner process is a working one."""
    states: dict[str, str] = {}
    for path in sorted(
        RUNNER_LOGS.glob("no-tui.log*"), key=lambda p: p.stat().st_mtime
    ):
        with path.open(errors="replace") as lines:
            for line in lines:
                if "[observer] on" not in line:
                    continue
                event = json.loads(line)
                if event["pid"] != runner:
                    continue
                if event["message"] == "[observer] onAgentState":
                    states[event["threadId"]] = event["subtype"]
                elif (
                    event["message"] == "[observer] onSessionState"
                    and event["data"]["state"] == "disconnected"
                ):
                    states[event["threadId"]] = "disconnected"
    return sorted(
        thread for thread, state in states.items() if state not in IDLE_STATES
    )


def install() -> None:
    sparkle = updater()
    if sparkle is None or staged() is None:
        return
    amp_pids = output("pgrep", "-x", "Amp").split()
    if not amp_pids:
        return
    amp = int(amp_pids[0])
    uptime = datetime.now() - started(amp)
    if uptime < COOLDOWN:
        return
    runner = output("pgrep", "-P", str(amp), "-f", "--", "--no-tui").split()
    if not runner:
        log("waiting on Amp's runner, which is not running")
        return
    busy = busy_threads(int(runner[0]))
    if busy:
        log(f"waiting on {len(busy)} working thread(s): {', '.join(busy)}")
        return
    before = build(APP)
    log(f"quitting Amp after {uptime} to install its staged update")
    # SIGTERM quits Amp without an Automation grant; Amp stops its runner on the way out.
    os.kill(amp, signal.SIGTERM)
    try:
        for _ in range(120):
            if not running(sparkle):
                break
            time.sleep(1)
        else:
            sys.exit(
                f"{datetime.now():%F %T} Sparkle did not finish installing within 120s"
            )
    finally:
        # A no-op when Sparkle relaunched the app itself.
        subprocess.run(["open", "-g", str(APP)], check=True)
    log(f"installed build {build(APP)} over {before} and reopened Amp")


def audit() -> None:
    update = staged()
    if update is None:
        return
    version, since = update
    message = (
        f"Amp.app: build {version} has waited for an idle runner since {since:%F %T}"
    )
    if datetime.now() - since > STALE:
        sys.exit(f"{message}, past {STALE}; see ~/Library/Logs/amp-app-update.log")
    print(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        action="store_true",
        help=f"fail when a staged update has waited over {STALE}",
    )
    if parser.parse_args().audit:
        audit()
    else:
        install()


if __name__ == "__main__":
    main()
