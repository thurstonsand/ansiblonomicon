from pathlib import Path
import tomllib

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
        ("sessions", "tools"),
    ):
        assert tasks[f"operator:{task}"]["depends"] == [f"operator:{prerequisite}"]


def test_operator_bootstrap_only_owns_installation_config():
    config = tomllib.loads((TARGET / "mise.operator.toml").read_text())
    assert set(config["bootstrap"]["files"]) == {
        "/home/thurstonsand/.config/mise/config.toml"
    }
    for script in ("configure", "reconcile"):
        assert not (TARGET / "operator" / script).exists()


def test_t3_keeps_vendor_working_directory_and_runtime():
    dropin = (TARGET / "remote-development/t3-operator.conf").read_text()
    assert "WorkingDirectory=" not in dropin
    assert "ExecStart" not in dropin
    assert "ansiblonomicon" not in dropin
    amp = (TARGET / "remote-development/amp-remote.service").read_text()
    assert "WorkingDirectory=/home/thurstonsand/code/ansiblonomicon" in amp
