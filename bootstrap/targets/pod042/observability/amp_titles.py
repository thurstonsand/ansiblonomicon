#!/usr/bin/env python3
"""Send every Amp thread title to the usage index; only the signed-in Amp CLI can list them."""

import json
import subprocess
import sys
from urllib.request import Request, urlopen

PAGE = 500


def main() -> None:
    (url,) = sys.argv[1:]
    titles: dict[str, str] = {}
    offset = 0
    while True:
        listed = subprocess.run(
            [
                "amp",
                "threads",
                "list",
                "--json",
                "--include-archived",
                f"--limit={PAGE}",
                f"--offset={offset}",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        page: list[dict[str, str]] = json.loads(listed)
        titles |= {thread["id"]: thread["title"] for thread in page if thread["title"]}
        if len(page) < PAGE:
            break
        offset += PAGE
    request = Request(
        url,
        data=json.dumps(titles).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30):
        pass


if __name__ == "__main__":
    main()
