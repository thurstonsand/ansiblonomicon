from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"


def test_node_inventory_keeps_t3_out_of_the_global_prefix():
    inventory = tomllib.loads((TARGET / "operator/node-packages.toml").read_text())
    assert "t3" not in inventory["global"]["packages"]
    # A global t3 runs npm's implicit node-gyp rebuild for msgpackr-extract's binding.gyp,
    # which no allow-scripts policy gates and this host cannot satisfy.
    t3 = inventory["prefixed"]["t3"]
    # Inside T3's own default home, so no T3CODE_HOME has to be carried anywhere.
    assert t3["prefix"] == "/home/thurstonsand/.t3/cli"
    assert t3["npmrc"] == "/home/thurstonsand/.config/t3code/npmrc"
    assert t3["reason"].strip()
    # services.py reads this inventory for the CLI and its npmrc instead of repeating them,
    # and it calls that CLI directly: never a shim, never npx.
    services = (TARGET / "remote-development/services.py").read_text()
    assert "operator/node-packages.toml" in services
    assert t3["npmrc"] not in services
    assert '"npx"' not in services
