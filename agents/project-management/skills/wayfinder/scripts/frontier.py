#!/usr/bin/env python3
"""Print the frontier of a wayfinder map: open, unblocked, unclaimed tickets.

Usage: frontier.py docs/wayfinding/<effort-slug>
Output: one `path<TAB>name` line per frontier ticket, in number order.
"""

from pathlib import Path
import re
import sys


def ticket_number(raw: object) -> int | None:
    match = re.match(r"\d+", str(raw))
    return int(match.group()) if match else None


def load_ticket(path: Path) -> tuple[dict[str, object], str]:
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---":
        sys.exit(f"missing frontmatter in {path}")

    try:
        frontmatter_end = lines.index("---", 1)
    except ValueError:
        sys.exit(f"unterminated frontmatter in {path}")

    metadata: dict[str, object] = {}
    blocked_by: list[str] = []
    reading_blocked_by = False
    for line in lines[1:frontmatter_end]:
        if reading_blocked_by and (match := re.match(r"\s+-\s+(.+)", line)):
            blocked_by.append(match.group(1).strip(" '\""))
            continue

        reading_blocked_by = False
        if ":" not in line:
            continue

        key, value = (part.strip() for part in line.split(":", 1))
        if key == "blocked-by":
            reading_blocked_by = not value
            if value.startswith("[") and value.endswith("]"):
                blocked_by.extend(
                    item.strip(" '\"")
                    for item in value[1:-1].split(",")
                    if item.strip()
                )
            metadata[key] = blocked_by
        elif key in {"status", "claimed"}:
            metadata[key] = value.strip(" '\"")

    return metadata, "\n".join(lines[frontmatter_end + 1 :])


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: frontier.py docs/wayfinding/<effort-slug>")
    tickets_dir = Path(sys.argv[1]) / "tickets"
    if not tickets_dir.is_dir():
        sys.exit(f"no tickets directory at {tickets_dir}")

    tickets: dict[int, tuple[Path, dict[str, object], str]] = {}
    for path in sorted(tickets_dir.glob("*.md")):
        number = ticket_number(path.name)
        if number is not None:
            metadata, content = load_ticket(path)
            tickets[number] = (path, metadata, content)

    for path, ticket, content in tickets.values():
        if ticket.get("status") != "open" or ticket.get("claimed"):
            continue

        blocked = False
        dependencies = ticket.get("blocked-by")
        if not isinstance(dependencies, list):
            dependencies = []
        for dep in dependencies:
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
                for line in content.splitlines()
                if line.startswith("# ")
            ),
            path.stem,
        )
        print(f"{path}\t{name}")


if __name__ == "__main__":
    main()
