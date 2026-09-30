from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires installed macOS Homebrew"
)
def test_installed_brew_ruby_calls_askpass_through_clean_environment(
    tmp_path: Path,
) -> None:
    brew = shutil.which("brew")
    if brew is None:
        pytest.skip("Homebrew is not installed")
    profiles = {
        "Thurstons-MacBook-Pro": "macos",
        "ML-DFC6YK6VJQ": "work",
    }
    profile = profiles.get(socket.gethostname().split(".", 1)[0])
    if profile is None:
        pytest.skip("Mac hostname has no declared fnox profile")

    root = tmp_path / "isolated checkout"
    (root / "scripts").mkdir(parents=True)
    for name in ("fnox-host", "fnox_host.py", "automation_identity.py"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    askpass = root / "scripts/sudo-askpass.sh"
    shutil.copy2(ROOT / "scripts/sudo-askpass.sh", askpass)
    secret = (
        "HOMEBREW_SUDO_ASKPASS_PASS_WORK"
        if profile == "work"
        else "HOMEBREW_SUDO_ASKPASS_PASS"
    )
    (root / "fnox.toml").write_text(
        'root = true\nenv = "exec"\nif_missing = "error"\nprompt_auth = false\n'
        "[daemon]\nenabled = false\n[secrets]\n"
        f'{secret} = {{ provider = "synthetic", value = "unused" }}\n'
    )
    for name in ("macos", "work", "pod042", "orb"):
        (root / f"fnox.{name}.toml").write_text('import = ["fnox.toml"]\n')

    ruby = """
ENV["PATH"] = "/usr/bin:/bin"
path = ENV.fetch("SUDO_ASKPASS")
exec([path, path])
"""
    home = tmp_path / "home"
    home.mkdir()
    environment = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOMEBREW_NO_AUTO_UPDATE": "1",
        "HOMEBREW_NO_ANALYTICS": "1",
        "USER": "tsandberg" if profile == "work" else "thurstonsand",
        "SUDO_ASKPASS": str(askpass),
        "HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE": profile,
        "HOMEBREW_ANSIBLONOMICON_EXEC_KEYS": f'["{secret}"]',
        "HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON": sys.executable,
        secret: "synthetic-password",
    }
    result = subprocess.run(
        [brew, "ruby", "-e", ruby],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "synthetic-password\n"
