#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-frontmatter"]
# ///
"""Print the frontier of a wayfinder map: open, unblocked, unclaimed tickets.

Usage: frontier.py docs/wayfinding/<effort-slug>
Output: one `path<TAB>name` line per frontier ticket, in number order.
"""

from pathlib import Path
import re
import sys
from typing import cast

import frontmatter


def ticket_number(raw: object) -> int | None:
    match = re.match(r"\d+", str(raw))
    return int(match.group()) if match else None


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: frontier.py docs/wayfinding/<effort-slug>")
    tickets_dir = Path(sys.argv[1]) / "tickets"
    if not tickets_dir.is_dir():
        sys.exit(f"no tickets directory at {tickets_dir}")

    tickets: dict[int, tuple[Path, frontmatter.Post]] = {}
    for path in sorted(tickets_dir.glob("*.md")):
        number = ticket_number(path.name)
        if number is not None:
            tickets[number] = (path, frontmatter.load(path))

    for path, ticket in tickets.values():
        if ticket.get("status") != "open" or ticket.get("claimed"):
            continue

        blocked = False
        for dep in cast("list[object]", ticket.get("blocked-by") or []):
            dep_number = ticket_number(dep)
            entry = tickets.get(dep_number) if dep_number is not None else None
            if entry is None:
                print(
                    f"warning: {path.name} blocked by unknown ticket {dep!r}",
                    file=sys.stderr,
                )
                blocked = True
            elif entry[1].get("status") != "closed":
                blocked = True
        if blocked:
            continue

        name = next(
            (
                line[2:].strip()
                for line in ticket.content.splitlines()
                if line.startswith("# ")
            ),
            path.stem,
        )
        print(f"{path}\t{name}")


if __name__ == "__main__":
    main()
