import hashlib
from pathlib import Path
import shutil
import stat
import subprocess

from test_user_tools_capability import isolated_env
import yaml

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
    (target / "desktop-tools").symlink_to(
        CAPABILITY / "files", target_is_directory=True
    )
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
    command = [mise, "-C", str(target), "bootstrap", "--only", "files", "--yes"]
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


def test_personal_apply_is_exact_private_atomic_and_repeatable(tmp_path: Path) -> None:
    home, env, command = fixture(tmp_path, personal=True)
    preserved = [
        home / ".config/linearmouse/keep",
        home / ".config/eightctl/keep",
        home / ".mactop/keep",
        home / ".local/state/herdr/client/keep",
    ]
    for child in preserved:
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text("keep\n")
    failed = subprocess.run(command, env=env, capture_output=True, text=True)
    assert failed.returncode != 0
    assert not (home / ".config/linearmouse/linearmouse.json").exists()
    assert not (home / "Library/Application Support/go/telemetry/mode").exists()

    email = 'name"quote\nsecond\\line$HOME'
    password = 'p@ss"word\nback\\slash$$'
    secret_env = {**env, "EIGHTCTL_EMAIL": email, "EIGHTCTL_PASSWORD": password}
    preview = subprocess.run(
        [*command[:-1], "--dry-run"],
        env=secret_env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not (home / ".config/linearmouse/linearmouse.json").exists()
    assert not (home / "Library/Application Support/go/telemetry/mode").exists()
    assert email not in preview.stdout + preview.stderr
    assert password not in preview.stdout + preview.stderr

    result = subprocess.run(
        command, env=secret_env, check=True, capture_output=True, text=True
    )
    assert email not in result.stdout + result.stderr
    assert password not in result.stdout + result.stderr
    expected = {
        home / ".config/linearmouse/linearmouse.json": "linearmouse.json",
        home / ".config/nextdns.conf": "nextdns.conf",
        home / ".mactop/config.json": "mactop.json",
        home / ".local/state/herdr/client/endpoints.json": "herdr-endpoints.json",
        home / "Library/Application Support/go/telemetry/mode": "go-telemetry-mode",
    }
    for target, source in expected.items():
        assert target.read_bytes() == (CAPABILITY / "files" / source).read_bytes()
        assert not target.is_symlink()
    eightctl = home / ".config/eightctl/config.yaml"
    assert yaml.safe_load(eightctl.read_text()) == {
        "email": email,
        "password": password,
    }
    assert stat.S_IMODE((home / ".config/linearmouse").stat().st_mode) == 0o755
    assert stat.S_IMODE((home / ".config/eightctl").stat().st_mode) == 0o755
    assert stat.S_IMODE((home / ".mactop").stat().st_mode) == 0o755
    assert stat.S_IMODE((home / ".local/state/herdr/client").stat().st_mode) == 0o755
    assert (
        stat.S_IMODE((home / ".config/linearmouse/linearmouse.json").stat().st_mode)
        == 0o644
    )
    assert stat.S_IMODE((home / ".config/nextdns.conf").stat().st_mode) == 0o644
    assert stat.S_IMODE((home / ".mactop/config.json").stat().st_mode) == 0o644
    assert (
        stat.S_IMODE((home / ".local/state/herdr/client/endpoints.json").stat().st_mode)
        == 0o600
    )
    assert stat.S_IMODE((home / ".config/eightctl/config.yaml").stat().st_mode) == 0o600
    assert (
        stat.S_IMODE(
            (home / "Library/Application Support/go/telemetry/mode").stat().st_mode
        )
        == 0o644
    )
    assert (
        stat.S_IMODE((home / "Library/Application Support/go").stat().st_mode) == 0o700
    )
    assert (
        stat.S_IMODE((home / "Library/Application Support/go/telemetry").stat().st_mode)
        == 0o700
    )
    for child in preserved:
        assert child.read_text() == "keep\n"

    paths = [*expected, eightctl]
    before = fingerprint(paths)
    subprocess.run(command, env=secret_env, check=True, capture_output=True, text=True)
    assert fingerprint(paths) == before


def test_work_common_only_preserves_personal_paths_without_secrets(
    tmp_path: Path,
) -> None:
    home, env, command = fixture(tmp_path, personal=False)
    personal = home / ".config/eightctl/config.yaml"
    personal.parent.mkdir(parents=True)
    personal.write_text("seeded personal config\n")
    unrelated = home / "Library/Application Support/go/keep"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("keep\n")
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert personal.read_text() == "seeded personal config\n"
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
