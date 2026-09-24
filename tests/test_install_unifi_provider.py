from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import zipfile

import pytest
from pytest import MonkeyPatch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/install_unifi_provider.py"
SPEC = spec_from_file_location("install_unifi_provider", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

VERSION = "1.2.3-test.1"
TARGET = "linux_arm64"
BINARY = f"terraform-provider-unifi_v{VERSION}"
ARCHIVE = f"terraform-provider-unifi_{VERSION}_linux_arm64.zip"


def write_package(cache: Path, members: dict[str, bytes]) -> Path:
    cache.mkdir()
    archive = cache / ARCHIVE
    with zipfile.ZipFile(archive, "w") as package:
        for name, contents in members.items():
            package.writestr(name, contents)
    return archive


def write_manifest(path: Path, checksum: str) -> None:
    path.write_text(
        f'''source = "github.com/thurstonsand/unifi"
repository = "thurstonsand/terraform-provider-unifi"
version = "{VERSION}"

[platforms]
{TARGET} = "{checksum}"
'''
    )


def test_install_verifies_and_extracts_the_expected_binary(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    archive = write_package(
        cache,
        {
            "CHANGELOG.md": b"",
            "LICENSE": b"",
            "README.md": b"",
            BINARY: b"provider",
        },
    )
    manifest = tmp_path / "provider.toml"
    write_manifest(manifest, MODULE.sha256(archive))

    destination = MODULE.install(
        tmp_path / "mirror", TARGET, manifest_path=manifest, cache=cache
    )

    assert destination.read_bytes() == b"provider"
    assert destination.stat().st_mode & 0o111
    assert destination.parts[-6:] == (
        "github.com",
        "thurstonsand",
        "unifi",
        VERSION,
        TARGET,
        BINARY,
    )


def test_install_rejects_a_download_with_the_wrong_checksum(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    manifest = tmp_path / "provider.toml"
    write_manifest(manifest, "0" * 64)

    def download_bad_archive(_: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"not the released artifact")

    monkeypatch.setattr(MODULE, "download", download_bad_archive)

    with pytest.raises(SystemExit, match="checksum verification failed"):
        _ = MODULE.install(
            tmp_path / "mirror", TARGET, manifest_path=manifest, cache=cache
        )
    assert not (cache / ARCHIVE).exists()


def test_install_rejects_unexpected_archive_members(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    archive = write_package(cache, {BINARY: b"provider", "surprise": b"payload"})
    manifest = tmp_path / "provider.toml"
    write_manifest(manifest, MODULE.sha256(archive))

    with pytest.raises(SystemExit, match="unexpected contents"):
        _ = MODULE.install(
            tmp_path / "mirror", TARGET, manifest_path=manifest, cache=cache
        )
