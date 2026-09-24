import hashlib
from pathlib import Path
import shutil
import stat
import subprocess

from test_user_tools_capability import isolated_env

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "bootstrap/capabilities/desktop-tools"
MISE = shutil.which("mise")
assert MISE is not None


def fixture(
    tmp_path: Path, *, personal: bool
) -> tuple[Path, dict[str, str], list[str]]:
    home = tmp_path / "home"
    target = tmp_path / "checkout with spaces/target"
    home.mkdir()
    target.mkdir(parents=True)
    shutil.copytree(CAPABILITY / "files", target / "desktop-tools")
    (target / "mise.desktop-tools.toml").symlink_to(CAPABILITY / "mise.toml")
    environments = ["desktop-tools"]
    if personal:
        (target / "mise.desktop-tools-personal.toml").symlink_to(
            CAPABILITY / "mise.personal.toml"
        )
        environments.append("desktop-tools-personal")
    (target / "mise.toml").write_text('min_version = "2026.9.11"\n')
    env = isolated_env(home, target, "/usr/bin:/bin")
    env["MISE_ENV"] = ",".join(environments)
    mise = MISE
    assert mise is not None
    command = [
        mise,
        "-C",
        str(target),
        "bootstrap",
        "--only",
        "files,dotfiles",
        "--force-dotfiles",
        "--yes",
    ]
    return home, env, command


def fingerprint(paths: list[Path]) -> list[tuple[str, int, int, int]]:
    return [
        (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
            stat.S_IMODE(path.stat().st_mode),
        )
        for path in paths
    ]


def test_personal_apply_links_into_the_checkout_and_is_repeatable(
    tmp_path: Path,
) -> None:
    home, env, command = fixture(tmp_path, personal=True)
    preserved = [
        home / ".config/linearmouse/keep",
        home / ".mactop/keep",
        home / ".local/state/herdr/client/keep",
    ]
    for child in preserved:
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text("keep\n")
    unmanaged = home / ".config/linearmouse/linearmouse.json"
    unmanaged.write_text("regular file\n")

    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    source_root = command[2] + "/desktop-tools"
    expected = {
        home / ".config/linearmouse/linearmouse.json": "linearmouse.json",
        home / ".config/nextdns.conf": "nextdns.conf",
        home / ".mactop/config.json": "mactop.json",
        home / ".local/state/herdr/client/endpoints.json": "herdr-endpoints.json",
        home / "Library/Application Support/go/telemetry/mode": "go-telemetry-mode",
    }
    for target, source in expected.items():
        assert target.is_symlink()
        assert target.resolve() == Path(source_root) / source
    for child in preserved:
        assert child.read_text() == "keep\n"

    # Applications write their settings back through the link into the checkout.
    edited = home / ".mactop/config.json"
    edited.write_text('{"application": "edit"}\n')
    assert (Path(source_root) / "mactop.json").read_text() == (
        '{"application": "edit"}\n'
    )
    paths = list(expected)
    before = fingerprint(paths)
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert fingerprint(paths) == before
