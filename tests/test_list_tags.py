import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("playbook", "native_owns_agent_harness"),
    [("macos", True), ("work", False)],
)
def test_agent_harness_tag_ownership(
    tmp_path: Path, playbook: str, native_owns_agent_harness: bool
) -> None:
    binary = tmp_path / "bin"
    binary.mkdir()
    ansible_playbook = binary / "ansible-playbook"
    ansible_playbook.write_text(
        "#!/bin/sh\nprintf 'playbook tags: [agent-harness]\\n'\n"
    )
    ansible_playbook.chmod(0o755)

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/list-tags.sh"), playbook],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{binary}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    native_tags = (
        result.stdout.splitlines()[0].removeprefix("Native mise tags: ").split()
    )
    assert ("agent-harness" in native_tags) is native_owns_agent_harness
    assert "playbook tags: [agent-harness]" in result.stdout
