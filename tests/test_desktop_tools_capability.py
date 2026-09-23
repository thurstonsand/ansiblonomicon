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


def test_personal_apply_transitions_to_links_and_is_repeatable(tmp_path: Path) -> None:
    home, env, command = fixture(tmp_path, personal=True)
    preserved = [
        home / ".config/linearmouse/keep",
        home / ".config/eightctl/keep",
        home / "go/bin/keep",
        home / ".mactop/keep",
        home / ".local/state/herdr/client/keep",
    ]
    for child in preserved:
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text("keep\n")
    legacy = home / ".config/linearmouse/linearmouse.json"
    legacy.write_text("legacy regular file\n")
    retired = home / ".config/eightctl/config.yaml"
    retired.write_text("retired\n")
    retired_binary = home / "go/bin/eightctl"
    retired_binary.write_text("retired binary\n")
    subprocess.run(
        [*command[:-1], "--dry-run"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert legacy.read_text() == "legacy regular file\n"
    assert not legacy.is_symlink()
    assert retired.exists()
    assert retired_binary.exists()
    assert not (home / "Library/Application Support/go/telemetry/mode").exists()

    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert not retired.exists()
    assert not retired_binary.exists()
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

    edited = home / ".mactop/config.json"
    edited.write_text('{"application": "edit"}\n')
    assert (Path(source_root) / "mactop.json").read_text() == (
        '{"application": "edit"}\n'
    )
    paths = list(expected)
    before = fingerprint(paths)
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert fingerprint(paths) == before
    assert not retired.exists()
    assert not retired_binary.exists()
    assert (home / "go/bin/keep").read_text() == "keep\n"


def test_work_common_only_preserves_personal_paths_without_secrets(
    tmp_path: Path,
) -> None:
    home, env, command = fixture(tmp_path, personal=False)
    personal = home / ".config/linearmouse/linearmouse.json"
    personal.parent.mkdir(parents=True)
    personal.write_text("seeded personal config\n")
    retired = home / ".config/eightctl/config.yaml"
    retired.parent.mkdir(parents=True)
    retired.write_text("retired\n")
    retired_binary = home / "go/bin/eightctl"
    retired_binary.parent.mkdir(parents=True)
    retired_binary.write_text("retired binary\n")
    sibling = home / "go/bin/keep"
    sibling.write_text("keep\n")
    unrelated = home / "Library/Application Support/go/keep"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("keep\n")
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert personal.read_text() == "seeded personal config\n"
    assert not retired.exists()
    assert not retired_binary.exists()
    assert sibling.read_text() == "keep\n"
    assert unrelated.read_text() == "keep\n"
    assert (home / "Library/Application Support/go/telemetry/mode").read_text() == (
        "local 1970-01-01\n"
    )


def test_registered_targets_are_mac_only_and_sources_are_explicitly_readable() -> None:
    personal = ROOT / "bootstrap/targets/Thurstons-MacBook-Pro"
    work = ROOT / "bootstrap/targets/ML-DFC6YK6VJQ"
    pod = ROOT / "bootstrap/targets/pod042"
    assert (personal / "mise.desktop-tools-personal.toml").resolve() == (
        CAPABILITY / "mise.personal.toml"
    )
    assert (personal / "mise.desktop-tools.toml").resolve() == CAPABILITY / "mise.toml"
    assert (work / "mise.desktop-tools.toml").resolve() == CAPABILITY / "mise.toml"
    assert not (work / "mise.desktop-tools-personal.toml").exists()
    assert not list(pod.glob("*desktop-tools*"))
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o644
        for path in (CAPABILITY / "files").iterdir()
    )
