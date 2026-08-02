from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from pytest import MonkeyPatch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/init-secrets.py"
SPEC = spec_from_file_location("init_secrets", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_service_account_wrapper_is_preferred(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    wrapper = tmp_path / ".local/bin/op"
    wrapper.parent.mkdir(parents=True)
    wrapper.touch()
    monkeypatch.setattr(MODULE.Path, "home", lambda: tmp_path)

    assert MODULE.service_account_op_wrapper() == wrapper
    assert MODULE.op_command() == str(wrapper)


def test_system_op_removes_service_account_token(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(MODULE.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    assert MODULE.service_account_op_wrapper() is None
    assert MODULE.op_command() == "op"
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in MODULE.op_environment()


def test_machine_secrets_are_filtered_for_pod042() -> None:
    config = {
        "HOMEBREW_SUDO_ASKPASS_PASS": "personal",
        "HOMEBREW_SUDO_ASKPASS_PASS_WORK": "work",
        "POD042_TRUENAS_SSH_PUBLIC_KEY": "shared",
    }

    assert MODULE.secrets_for_hostname(config, "pod042") == {
        "POD042_TRUENAS_SSH_PUBLIC_KEY": "shared"
    }
