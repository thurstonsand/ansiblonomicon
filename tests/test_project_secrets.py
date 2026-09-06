import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    mise = shutil.which("mise")
    if mise is None:
        pytest.skip("mise is required for native environment integration")
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/project-secrets.sh", scripts / "project-secrets.sh")
    provider = scripts / "fnox-host"
    provider.write_text(
        '#!/bin/bash\nprintf "call\\n" >> "$(dirname "$0")/calls"\n'
        'printf "export CLOUDFLARE_API_TOKEN=synthetic-token\\n"\n'
    )
    provider.chmod(0o755)
    (root / "mise.toml").write_text(
        '[settings]\nenv_cache = true\n[env]\n_.source = { path = "scripts/project-secrets.sh", '
        "tools = true, redact = true }\n"
    )
    home = tmp_path / "home"
    home.mkdir()
    environment = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "MISE_TRUSTED_CONFIG_PATHS": str(root),
        "MISE_GLOBAL_CONFIG_FILE": str(tmp_path / "global.toml"),
        "MISE_SYSTEM_CONFIG_FILE": str(tmp_path / "system.toml"),
        "MISE_DATA_DIR": str(tmp_path / "data"),
        "MISE_STATE_DIR": str(tmp_path / "state"),
        "MISE_CACHE_DIR": str(tmp_path / "cache"),
    }
    return root, environment, mise


def test_native_source_cached_and_bootstrap_bypass(
    project: tuple[Path, dict[str, str], str],
) -> None:
    root, environment, mise = project
    result = subprocess.run(
        [
            mise,
            "exec",
            "--",
            "sh",
            "-c",
            '"$1" exec -- sh -c \'test "$CLOUDFLARE_API_TOKEN" = synthetic-token\' && '
            '"$1" exec -- sh -c \'test "$CLOUDFLARE_API_TOKEN" = synthetic-token\'',
            "proof",
            mise,
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert len((root / "scripts/calls").read_text().splitlines()) < 3
    cached = list(Path(environment["MISE_STATE_DIR"]).glob("env-cache/**/*"))
    assert any(path.is_file() for path in cached)
    assert all(
        b"synthetic-token" not in path.read_bytes() for path in cached if path.is_file()
    )
    provider = root / "scripts/fnox-host"
    provider.write_text('#!/bin/bash\necho "export PARTIAL=forbidden"\nexit 42\n')
    failed = subprocess.run(
        [mise, "exec", "--", "echo", "consumer-ran"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0
    assert "consumer-ran" not in failed.stdout
    enrolled = subprocess.run(
        [mise, "--no-env", "exec", "--", "echo", "enrollment-ran"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert enrolled.returncode == 0, enrolled.stderr
    assert "enrollment-ran" in enrolled.stdout


def test_native_shell_exit_and_clean_tmux_environment(
    project: tuple[Path, dict[str, str], str],
) -> None:
    root, environment, mise = project
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is required for shell integration")
    environment["MISE_BIN"] = mise
    environment["PROJECT"] = str(root)
    result = subprocess.run(
        [
            zsh,
            "-f",
            "-c",
            """
set -e
eval "$("$MISE_BIN" activate zsh)"
cd "$PROJECT"
eval "$("$MISE_BIN" hook-env -s zsh)"
test "$CLOUDFLARE_API_TOKEN" = synthetic-token
(
    clean_env="$("$MISE_BIN" -C / hook-env -s zsh)" || exit
    eval "$clean_env"
    sh -c 'test -z "${CLOUDFLARE_API_TOKEN+x}"'
)
test "$CLOUDFLARE_API_TOKEN" = synthetic-token
cd ..
eval "$("$MISE_BIN" hook-env -s zsh)"
test -z "${CLOUDFLARE_API_TOKEN+x}"
echo load-unload-and-clean-launch-passed
""",
        ],
        cwd=root.parent,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "load-unload-and-clean-launch-passed" in result.stdout
