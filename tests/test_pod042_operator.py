import os
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"


def test_vendor_t3_replaces_npm_link_and_preserves_it_on_repeat(tmp_path: Path):
    for name in (
        ".amp/bin/amp",
        ".local/bin/claude",
        ".local/bin/codex",
        ".opencode/bin/opencode",
    ):
        executable = tmp_path / name
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    link = tmp_path / ".local/bin/t3"
    link.symlink_to(tmp_path / ".t3/cli/node_modules/.bin/t3")
    binary = tmp_path / ".t3/runtime/versions/0.0.42/t3"
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HOME/t3-calls"\n')
    binary.chmod(0o755)
    curl = tmp_path / "bin/curl"
    curl.parent.mkdir()
    curl.write_text(
        "#!/bin/sh\n"
        'if [ "$2" = -o ]; then echo https://github.com/pingdotgg/t3code/releases/tag/v0.0.42; exit; fi\n'
        'test "$2" = https://t3.codes/install.sh || exit 1\n'
        "echo 'test \"$T3CODE_VERSION\" = 0.0.42 || exit 1'\n"
        'echo install >> "$HOME/downloads"\n'
        'echo \'ln -sfn "$HOME/.t3/runtime/versions/0.0.42/t3" "$HOME/.local/bin/t3"\'\n'
    )
    curl.chmod(0o755)
    body = tomllib.loads((TARGET / "mise.operator.toml").read_text())["tasks"][
        "operator:agents"
    ]["run"]
    env = {**os.environ, "HOME": str(tmp_path), "PATH": f"{curl.parent}:/usr/bin:/bin"}
    for _ in range(2):
        subprocess.run(["bash", "-c", body], env=env, check=True)
    assert link.resolve() == binary
    assert (tmp_path / "downloads").read_text() == "install\n"
    assert (tmp_path / "t3-calls").read_text() == "--version\n--version\n"
