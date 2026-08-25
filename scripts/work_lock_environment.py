#!/usr/bin/env python3
"""Inject a transient single-platform ``[tool.uv]`` environments restriction.

Used by ``mise run pull`` on the work machine to force wheel-only lock resolution;
see README.work.md.
"""

import sys

import tomlkit

WORK_ENVIRONMENT = "sys_platform == 'darwin' and platform_machine == 'arm64'"


def main() -> None:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as handle:
        doc = tomlkit.parse(handle.read())

    tool = doc.setdefault("tool", tomlkit.table())
    uv = tool.setdefault("uv", tomlkit.table())
    uv["environments"] = [WORK_ENVIRONMENT]
    uv["required-environments"] = [WORK_ENVIRONMENT]

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(tomlkit.dumps(doc))


if __name__ == "__main__":
    main()
