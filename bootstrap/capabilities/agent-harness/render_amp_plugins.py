#!/usr/bin/env python3
"""Prepare Amp plugins with the models and prompts declared in models.yml."""

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
        if "source" in plugin:
            if destination.exists():
                raise ValueError(f"Upstream plugin conflicts with {destination}")
            source = text(plugin, "source")
            with urllib.request.urlopen(source, timeout=30) as response:
                content = response.read().decode("utf-8")
        else:
            source = str(capability / "amp-plugins" / destination.name)
            content = destination.read_text()
        replacements = {"MODEL": alias, "REASONING_EFFORT": effort}
        if "instructions" in plugin:
            prompt = capability / text(plugin, "instructions")
            markdown = prompt.read_text()
            frontmatter = re.match(r"\A---\n.*?\n---\n", markdown, flags=re.DOTALL)
            if not frontmatter:
                raise ValueError(f"{prompt}: expected agent frontmatter")
            replacements["INSTRUCTIONS"] = markdown[frontmatter.end() :].strip()
        for constant, replacement in replacements.items():
            declarations = list(
                re.finditer(
                    rf"^const {constant} = (?:'[^'\n]*'|\"[^\"\n]*\");?$",
                    content,
                    flags=re.MULTILINE,
                )
            )
            if len(declarations) != 1:
                raise ValueError(
                    f"{source}: expected one {constant} declaration, got {len(declarations)}"
                )
            start, end = declarations[0].span()
            content = (
                content[:start]
                + f"const {constant} = {json.dumps(replacement)}"
                + content[end:]
            )
        destination.write_text(content)
        print(f"{name}: {alias} ({effort}), from {source}")


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
