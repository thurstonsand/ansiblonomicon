#!/usr/bin/env python3
"""Retitle script: regenerate session title on demand."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from _common import (
    TitleRequestError,
    generate_title,
    log,
    read_current_title,
    write_pending_title,
)
from _config import API_URL, MAX_CONTEXT_BYTES, MODEL, TITLE_PROMPT, TOKEN


def _transcript_path(session_id: str, cwd: str) -> Path:
    slug = cwd.replace("/", "-").replace(".", "-")
    return Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl"


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("retitle: session_id required as first argument", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1].strip()
    hint = sys.argv[2].strip() if len(sys.argv) > 2 else None
    cwd = os.getcwd()
    transcript = _transcript_path(session_id, cwd)

    if not transcript.is_file():
        print(f"retitle: transcript not found at {transcript}", file=sys.stderr)
        sys.exit(1)

    old_title = read_current_title(str(transcript))

    try:
        title = generate_title(
            session_id,
            cwd,
            str(transcript),
            api_url=API_URL,
            model=MODEL,
            token=TOKEN,
            prompt=TITLE_PROMPT,
            max_context_bytes=MAX_CONTEXT_BYTES,
            hint=hint,
        )
    except (ValueError, TitleRequestError) as e:
        log(session_id, cwd, f"retitle failed: {e}")
        print(f"retitle: {e}", file=sys.stderr)
        sys.exit(1)

    write_pending_title(session_id, title)
    log(session_id, cwd, f'retitle: "{old_title}" -> "{title}"')

    if old_title:
        print(f"{old_title} -> {title}")
    else:
        print(title)


if __name__ == "__main__":
    main()
