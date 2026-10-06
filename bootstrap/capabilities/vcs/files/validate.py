#!/usr/bin/env python3
"""Validate VCS identity and corporate Git configuration before mise writes it."""

import os
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    scm_config = os.environ.get("VCS_GIT_SCM_CONFIG", "")
    if scm_config:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as stream:
            stream.write(scm_config)
            stream.flush()
            subprocess.run(
                ["git", "config", "--file", str(Path(stream.name)), "--list"],
                check=True,
                capture_output=True,
                text=True,
            )

    required = [
        "VCS_PERSONAL_EMAIL",
        "VCS_PERSONAL_PUBLIC_SIGNING_KEY",
        "VCS_GIT_PERSONAL_SIGNING_KEY",
    ]
    if os.environ["HOST_PROFILE"] == "work":
        required.extend(["VCS_WORK_EMAIL", "VCS_WORK_SIGNING_KEY"])
    for name in required:
        value = os.environ.get(name, "")
        if not value:
            raise RuntimeError(f"{name} is required")
        if any(character in value for character in ('"', "\\", "\n", "\r", "\0")):
            raise RuntimeError(f"{name} contains characters unsafe for VCS config")


if __name__ == "__main__":
    main()
