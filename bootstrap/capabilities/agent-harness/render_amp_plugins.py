#!/usr/bin/env python3
"""Fetch upstream Amp plugins and override their model and effort from models.yml."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import urllib.request

from amp_modes import EFFORTS, text
from catalogue import mapping
import yaml

CAPABILITY = Path(__file__).resolve().parent


def render(capability: Path, output: Path) -> None:
    document = mapping(yaml.safe_load((capability / "models.yml").read_text()))
    models = mapping(document["models"])
    plugins = mapping(mapping(document["amp"])["plugins"])
    output.mkdir(parents=True, exist_ok=True)
    for source in (capability / "amp-plugins").iterdir():
        destination = output / source.name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    for name, value in plugins.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise ValueError(f"Invalid plugin name {name!r}")
        plugin = mapping(value)
        provider, key = text(plugin, "model").split(".")
        model = mapping(mapping(models[provider])[key])
        alias = text(mapping(mapping(model["agent_harness"])["aliases"]), "amp")
        effort = text(plugin, "effort")
        if effort not in EFFORTS:
            raise ValueError(f"Unknown effort {effort!r} for {name}")
        destination = output / f"{name}.ts"
        if destination.exists():
            raise ValueError(f"Upstream plugin conflicts with {destination}")
        url = text(plugin, "source")
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8")
        for constant, replacement in (("MODEL", alias), ("REASONING_EFFORT", effort)):
            content, count = re.subn(
                rf"^const {constant} = (?:'[^'\n]+'|\"[^\"\n]+\");?$",
                f"const {constant} = {json.dumps(replacement)}",
                content,
                flags=re.MULTILINE,
            )
            if count != 1:
                raise ValueError(
                    f"{url}: expected one {constant} declaration, got {count}"
                )
        destination.write_text(content)
        print(f"{name}: {alias} ({effort}), from {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="Empty staging directory"
    )
    args = parser.parse_args()
    render(CAPABILITY, args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, KeyError, ValueError) as error:
        print(f"amp-plugins: {error}", file=sys.stderr)
        raise SystemExit(1) from error
