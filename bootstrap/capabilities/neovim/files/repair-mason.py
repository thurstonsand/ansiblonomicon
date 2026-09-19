#!/usr/bin/env python3
"""Remove Mason packages whose Python virtual environment is broken."""

from pathlib import Path
import shutil


def main() -> None:
    mason = Path.home() / ".local/share/nvim/mason"
    packages = mason / "packages"
    if not packages.is_dir():
        return

    # Match the old shell glob: packages without a Python venv never participate.
    # Collect first because the broken-link cleanup below changes lexists().
    python_candidates = [
        package / "venv/bin/python"
        for package in packages.iterdir()
        if (package / "venv/bin/python").exists()
        or (package / "venv/bin/python").is_symlink()
    ]
    broken_packages: list[Path] = []
    for python in python_candidates:
        if python.exists() and python.stat().st_mode & 0o111:
            continue
        broken_packages.append(python.parents[2])

    for path in mason.rglob("*"):
        if path.is_symlink() and not path.exists():
            path.unlink()

    for package in broken_packages:
        name = package.name
        for path in mason.rglob("*"):
            if path.is_symlink() and f"/packages/{name}/" in str(path.readlink()):
                path.unlink()
        shutil.rmtree(package)
        print(name)


if __name__ == "__main__":
    main()
