#!/usr/bin/env python3
"""Install the pinned UniFi provider into OpenTofu's filesystem mirror."""

import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import tempfile
import tomllib
from typing import cast
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "terraform/unifi/provider.toml"
DEFAULT_MIRROR = Path.home() / ".terraform.d/plugins"


def host_platform() -> str:
    systems = {"Darwin": "darwin", "Linux": "linux"}
    machines = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64"}
    try:
        return f"{systems[platform.system()]}_{machines[platform.machine()]}"
    except KeyError as error:
        raise SystemExit(
            f"unsupported provider platform: {platform.system()}_{platform.machine()}"
        ) from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with (
            urlopen(url, timeout=60) as response,
            tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream,
        ):
            temporary = Path(stream.name)
            shutil.copyfileobj(response, stream)
        temporary.replace(destination)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def install(
    mirror: Path,
    target: str,
    manifest_path: Path = MANIFEST,
    cache: Path | None = None,
) -> Path:
    with manifest_path.open("rb") as stream:
        manifest = tomllib.load(stream)

    source = cast(str, manifest["source"])
    repository = cast(str, manifest["repository"])
    version = cast(str, manifest["version"])
    checksums = cast(dict[str, str], manifest["platforms"])
    if target not in checksums:
        raise SystemExit(f"provider manifest does not support {target}")

    os_name, architecture = target.split("_", 1)
    archive_name = f"terraform-provider-unifi_{version}_{os_name}_{architecture}.zip"
    cache = cache or Path.home() / ".cache/ansiblonomicon/unifi-provider"
    archive = cache / archive_name
    expected_checksum = checksums[target]
    try:
        cache_is_valid = archive.exists() and sha256(archive) == expected_checksum
    except OSError:
        cache_is_valid = False
    if not cache_is_valid:
        download(
            f"https://github.com/{repository}/releases/download/v{version}/{archive_name}",
            archive,
        )
    try:
        archive_is_valid = sha256(archive) == expected_checksum
    except OSError:
        archive_is_valid = False
    if not archive_is_valid:
        archive.unlink(missing_ok=True)
        raise SystemExit(f"checksum verification failed for {archive_name}")

    binary_name = f"terraform-provider-unifi_v{version}"
    destination = mirror / source / version / target / binary_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with zipfile.ZipFile(archive) as package:
            expected_members = {"CHANGELOG.md", "LICENSE", "README.md", binary_name}
            if set(package.namelist()) != expected_members:
                raise SystemExit(f"unexpected contents in {archive_name}")
            with (
                package.open(binary_name) as source_stream,
                tempfile.NamedTemporaryFile(
                    dir=destination.parent, delete=False
                ) as destination_stream,
            ):
                temporary = Path(destination_stream.name)
                shutil.copyfileobj(source_stream, destination_stream)
        temporary.chmod(0o755)
        temporary.replace(destination)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror", type=Path, default=DEFAULT_MIRROR)
    parser.add_argument("--platform")
    args = parser.parse_args()
    target = args.platform or host_platform()
    destination = install(args.mirror.expanduser(), target)
    print(f"installed {target} provider at {destination}")


if __name__ == "__main__":
    main()
