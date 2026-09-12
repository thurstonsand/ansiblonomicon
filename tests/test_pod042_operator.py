import os
from pathlib import Path
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"


def test_operator_task_order_preserves_base_bootstrap():
    config = tomllib.loads((TARGET / "mise.operator.toml").read_text())
    tasks = config["tasks"]
    assert "bootstrap" not in tasks
    assert "operator:setup" in config["bootstrap"]["hooks"]["final"]["run"]
    for task, prerequisite in (
        ("setup", "tmux"),
        ("tmux", "dotfiles"),
        ("dotfiles", "sessions"),
        ("sessions", "agents"),
        ("agents", "tools"),
    ):
        assert tasks[f"operator:{task}"]["depends"] == [f"operator:{prerequisite}"]


def test_operator_bootstrap_only_owns_installation_config():
    config = tomllib.loads((TARGET / "mise.operator.toml").read_text())
    assert set(config["bootstrap"]["files"]) == {
        "/home/thurstonsand/.config/mise/config.toml"
    }
    for script in ("configure", "reconcile"):
        assert not (TARGET / "operator" / script).exists()


def test_agents_use_vendor_installers_and_node_globals():
    config = tomllib.loads((TARGET / "operator/mise.toml").read_text())
    for tool in ("amp", "codex", "claude", "opencode", "npm:t3"):
        assert tool not in config["tools"]
    tasks = tomllib.loads((TARGET / "mise.operator.toml").read_text())["tasks"]
    # One inventory, one installer: both call sites pass their own npm and nothing else.
    installer = "operator/node_packages.py"
    assert installer in config["tools"]["node"]["postinstall"]
    assert installer in tasks["operator:tools"]["run"][2]
    assert tasks["operator:agents"]["shell"] == "bash -c"


def test_node_inventory_keeps_t3_out_of_the_global_prefix():
    inventory = tomllib.loads((TARGET / "operator/node-packages.toml").read_text())
    assert "t3" not in inventory["global"]["packages"]
    # A global t3 runs npm's implicit node-gyp rebuild for msgpackr-extract's binding.gyp,
    # which no allow-scripts policy gates and this host cannot satisfy.
    t3 = inventory["prefixed"]["t3"]
    assert t3["prefix"] == "/home/thurstonsand/.local/share/t3code/cli"
    assert t3["npmrc"] == "/home/thurstonsand/.config/t3code/npmrc"
    assert t3["reason"].strip()
    # services.py reads this inventory for the CLI and its npmrc instead of repeating them,
    # and it calls that CLI directly: never a shim, never npx.
    services = (TARGET / "remote-development/services.py").read_text()
    assert "operator/node-packages.toml" in services
    assert t3["npmrc"] not in services
    assert '"npx"' not in services


@pytest.mark.parametrize(
    "failed_vendor", ["", "ampcode.com", "claude.ai", "chatgpt.com", "opencode.ai"]
)
def test_agent_installation_order_and_noop(tmp_path: Path, failed_vendor: str):
    home = tmp_path / "home"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    (home / ".local/bin").mkdir(parents=True)
    auth = home / ".codex/auth.json"
    auth.parent.mkdir()
    _ = auth.write_text("existing operator authentication")
    log = tmp_path / "calls"
    curl = binaries / "curl"
    _ = curl.write_text("""#!/bin/bash
set -eu
printf 'curl %s\\n' "$*" >> "$CALL_LOG"
if [ -n "$FAIL_VENDOR" ] && [[ "$*" == *"$FAIL_VENDOR"* ]]; then
  exit 22
fi
case "$2" in
  https://ampcode.com/install.sh) target=.amp/bin/amp ;;
  https://claude.ai/install.sh) target=.local/bin/claude ;;
  https://chatgpt.com/codex/install.sh) target=.local/bin/codex ;;
  https://opencode.ai/install) target=.opencode/bin/opencode ;;
  *) exit 99 ;;
esac
printf 'mkdir -p "$HOME/%s"\\n' "$(dirname "$target")"
printf 'touch "$HOME/%s"; chmod +x "$HOME/%s"\\n' "$target" "$target"
printf 'printf "installer %%s\\\\n" "$*" >> "$CALL_LOG"\\n'
""")
    curl.chmod(0o755)
    mise = binaries / "mise"
    _ = mise.write_text('#!/bin/bash\nprintf "mise %s\\n" "$*" >> "$CALL_LOG"\n')
    mise.chmod(0o755)
    script = tomllib.loads((TARGET / "mise.operator.toml").read_text())["tasks"][
        "operator:agents"
    ]["run"]
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{binaries}:/usr/bin:/bin",
        "CALL_LOG": str(log),
        "FAIL_VENDOR": failed_vendor,
    }
    result = subprocess.run(["bash", "-c", script], env=env, check=False)
    calls = log.read_text()
    assert auth.read_text() == "existing operator authentication"
    if failed_vendor:
        assert result.returncode == 22
        vendors = ["ampcode.com", "claude.ai", "chatgpt.com", "opencode.ai"]
        assert calls.count("curl ") == vendors.index(failed_vendor) + 1
        assert "mise " not in calls
        return
    assert result.returncode == 0
    assert calls.count("curl ") == 4
    assert "installer --no-modify-path" in calls
    retirement = (
        "mise --no-config --no-env uninstall --all amp codex claude opencode npm:t3\n"
    )
    assert calls.endswith(retirement)
    assert (home / ".local/bin/amp").resolve() == home / ".amp/bin/amp"
    _ = log.write_text("")
    _ = subprocess.run(["bash", "-c", script], env=env, check=True)
    assert log.read_text() == retirement


def test_t3_keeps_vendor_working_directory_and_runtime():
    dropin = (TARGET / "remote-development/t3-operator.conf").read_text()
    assert "WorkingDirectory=" not in dropin
    assert "ExecStart" not in dropin
    assert "ansiblonomicon" not in dropin
    amp = (TARGET / "remote-development/amp-remote.service").read_text()
    assert "WorkingDirectory=/home/thurstonsand/code/ansiblonomicon" in amp
