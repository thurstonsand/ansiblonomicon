#!/usr/bin/env python3
"""Stop hook: derive a session title from the transcript via the Anthropic API."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import cast

from _common import (
    HookInput,
    TitleRequestError,
    generate_title,
    load_title_config,
    log,
    read_current_title,
    write_pending_title,
)

CONFIG = load_title_config()


def main() -> None:
    hook = cast(HookInput, json.load(sys.stdin))

    if hook.get("agent_id"):
        return

    transcript = hook["transcript_path"]

    if not Path(transcript).is_file():
        return

    if read_current_title(transcript):
        return

    session_id = hook["session_id"]
    cwd = hook["cwd"]

    try:
        title = generate_title(
            session_id,
            cwd,
            transcript,
            api_url=CONFIG.api_url,
            model=CONFIG.model,
            token=CONFIG.token,
            prompt=CONFIG.prompt,
            max_context_bytes=CONFIG.max_context_bytes,
        )
    except (ValueError, TitleRequestError) as e:
        log(session_id, cwd, str(e))
        print(f"auto-title: {e}", file=sys.stderr)
        sys.exit(1)

    write_pending_title(session_id, title)
    log(session_id, cwd, f'generated title "{title}" (model={CONFIG.model})')


if __name__ == "__main__":
    main()
