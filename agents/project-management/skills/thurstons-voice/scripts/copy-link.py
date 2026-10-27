#!/usr/bin/env python3
"""Print a Markdown link that copies the message on stdin when clicked.

The link targets the `clipcopy:` scheme, which ClipCopy.app handles by copying
the decoded text. The heredoc's final newline is not part of the message.
"""

import sys
import urllib.parse

message = sys.stdin.read().removesuffix("\n")
print(f"[copy](clipcopy:{urllib.parse.quote(message, safe='')})")
