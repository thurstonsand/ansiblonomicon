#!/usr/bin/env python3
"""Reconcile a Brewfile while keeping privileged MAS work explicit."""

import argparse
import os
from pathlib import Path
import subprocess
import time

INTERVAL = 86400
RUBY_MAS_IDS = r"""require "bundle/brewfile"
saved_stdout = STDOUT.dup
begin
  STDOUT.reopen(STDERR)
  dsl = Homebrew::Bundle::Brewfile.read(file: ARGV.fetch(0))
ensure
  STDOUT.reopen(saved_stdout)
  saved_stdout.close
end
dsl.entries.select { |entry| entry.type == :mas }.each do |entry|
  id = entry.options[:id]
  raise "MAS entry #{entry.name.inspect} has no id" unless id
  puts id
end
"""


def run(command: list[str], env: dict[str, str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        env=env,
    )
    return completed.stdout if capture else ""


def ids(output: str) -> list[str]:
    result = [line.strip() for line in output.splitlines() if line.strip()]
    if any(not value.isdecimal() for value in result):
        raise RuntimeError("Homebrew Bundle returned an invalid MAS application ID")
    return list(dict.fromkeys(result))


def listed_ids(output: str) -> set[str]:
    return {
        parts[0]
        for line in output.splitlines()
        if (parts := line.strip().split()) and parts[0].isdecimal()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brewfile", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stamp", type=Path)
    args = parser.parse_args()

    brewfile = args.brewfile.resolve(strict=True)
    stamp = args.stamp or Path.home() / ".cache/ansible-homebrew/upgrade.stamp"
    due = not stamp.exists() or time.time() - stamp.stat().st_mtime >= INTERVAL
    env = {
        **os.environ,
        "HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS": "1",
        "MAS_NO_AUTO_INDEX": "1",
    }
    # Parsing is nonmutating and must precede check: Bundle uses status 1 for
    # both invalid Ruby and ordinary dependency drift.
    declared = ids(
        run(
            ["brew", "ruby", "-e", RUBY_MAS_IDS, "--", str(brewfile)],
            {**env, "HOMEBREW_NO_AUTO_UPDATE": "1"},
            capture=True,
        )
    )
    if args.check:
        env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
        check = subprocess.run(
            [
                "brew",
                "bundle",
                "check",
                f"--file={brewfile}",
                "--verbose",
            ],
            text=True,
            env=env,
        )
        if check.returncode not in (0, 1):
            raise subprocess.CalledProcessError(check.returncode, check.args)
        print("mac-apps: drift" if check.returncode else "mac-apps: current")
        raise SystemExit(check.returncode)

    if declared:
        # MAS must be available before Bundle because privileged app operations
        # deliberately happen first.
        run(["brew", "install", "mas"], {**env, "HOMEBREW_NO_INSTALL_UPGRADE": "1"})
        installed = listed_ids(run(["mas", "list"], env, capture=True))
        for app_id in declared:
            if app_id not in installed:
                run(["sudo", "-A", "mas", "install", app_id], env)
        if due:
            outdated = listed_ids(run(["mas", "outdated"], env, capture=True))
            for app_id in declared:
                if app_id in outdated:
                    run(["sudo", "-A", "mas", "upgrade", app_id], env)

    bundle = ["brew", "bundle", "install", f"--file={brewfile}"]
    if not due:
        bundle.append("--no-upgrade")
    run(bundle, env)
    if due:
        # Bundle also supports npm/uv/Go and MAS cleanup. Only Homebrew's
        # formulae, casks and taps belong to this capability.
        run(
            [
                "brew",
                "bundle",
                "cleanup",
                "--force",
                "--formula",
                "--cask",
                "--tap",
                f"--file={brewfile}",
            ],
            env,
        )
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        stamp.chmod(0o644)


if __name__ == "__main__":
    main()
