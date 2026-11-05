"""Exercise the JSON/stdin hook contract without launching a model."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import unittest

ASSETS = Path(__file__).resolve().parents[1] / "assets"


class CommandHooksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def invoke(
        self, script: str, event: dict[str, Any], *args: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ASSETS / script), *args],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env={**os.environ, "HOME": self.temp.name},
            check=False,
        )

    def test_timing_boundaries_and_failures_are_advisory(self) -> None:
        for duration, severity in (
            (60000, "none"),
            (60001, "slow"),
            (300000, "slow"),
            (300001, "very slow"),
        ):
            for hook in ("PostToolUse", "PostToolUseFailure"):
                with self.subTest(duration=duration, hook=hook):
                    result = self.invoke(
                        "command-timing.py",
                        {
                            "hook_event_name": hook,
                            "tool_name": "Bash",
                            "session_id": "session",
                            "tool_use_id": "call",
                            "duration_ms": duration,
                        },
                        "claude",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output = json.loads(result.stdout)
                    self.assertEqual(set(output), {"hookSpecificOutput"})
                    specific = output["hookSpecificOutput"]
                    self.assertEqual(specific["hookEventName"], hook)
                    text = specific["additionalContext"]
                    self.assertEqual("Slow feedback loop:" in text, severity == "slow")
                    self.assertEqual(
                        "Very slow feedback loop:" in text, severity == "very slow"
                    )
                    self.assertIn("Shell tool execution:", text)

    def test_codex_pairs_calls_without_crossing_sessions(self) -> None:
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "session_id": "one",
            "tool_use_id": "call",
        }
        start = self.invoke("command-timing.py", event, "codex")
        self.assertEqual(start.returncode, 0, start.stderr)
        self.assertEqual(start.stdout, "")
        event["hook_event_name"] = "PostToolUse"
        other = self.invoke(
            "command-timing.py", {**event, "session_id": "two"}, "codex"
        )
        self.assertEqual(other.stdout, "")
        finish = self.invoke("command-timing.py", event, "codex")
        self.assertEqual(finish.returncode, 0, finish.stderr)
        self.assertIn("Shell tool elapsed", finish.stdout)
        self.assertEqual(self.invoke("command-timing.py", event, "codex").stdout, "")

    def test_comment_guard_checks_additions_not_retained_comments_or_strings(
        self,
    ) -> None:
        for text, blocked in (
            ("# As requested, use a cache", True),
            ("// Used to be synchronous; now async", True),
            ("/* changed from one queue to two */", True),
            ("# The server requires a stable request ID for retries.", False),
            ('value = "# as requested"', False),
        ):
            for tool, args in (
                ("Edit", {"old_string": "value = 1", "new_string": text}),
                (
                    "MultiEdit",
                    {"edits": [{"old_string": "value = 1", "new_string": text}]},
                ),
                ("Write", {"file_path": "fresh.py", "content": text}),
                (
                    "apply_patch",
                    {
                        "command": f"*** Begin Patch\n*** Add File: fresh.py\n+{text}\n*** End Patch"
                    },
                ),
            ):
                with self.subTest(text=text, tool=tool):
                    result = self.invoke(
                        "no-chat-comments.py",
                        {"tool_name": tool, "tool_input": args, "cwd": self.temp.name},
                    )
                    self.assertEqual(
                        result.returncode, 2 if blocked else 0, result.stderr
                    )
        existing = "# as requested\nvalue = 1"
        Path(self.temp.name, "existing.py").write_text(existing)
        for tool, args in (
            (
                "Edit",
                {"old_string": existing, "new_string": "# as requested\nvalue = 2"},
            ),
            (
                "Write",
                {"file_path": "existing.py", "content": "# as requested\nvalue = 2"},
            ),
            (
                "apply_patch",
                {
                    "command": "*** Begin Patch\n*** Update File: existing.py\n@@\n # as requested\n-value = 1\n+value = 2\n*** End Patch"
                },
            ),
        ):
            result = self.invoke(
                "no-chat-comments.py",
                {"tool_name": tool, "tool_input": args, "cwd": self.temp.name},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
