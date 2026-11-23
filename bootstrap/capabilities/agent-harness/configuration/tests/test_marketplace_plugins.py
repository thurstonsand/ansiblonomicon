"""Check marketplace plugin reconciliation against fake harness CLIs."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import marketplace_plugins

FAKE_CLI = """#!/bin/sh
case "$*" in
  "plugin list --json") cat "$STATE/$(basename "$0")-plugins.json" ;;
  "plugin marketplace list --json") cat "$STATE/$(basename "$0")-marketplaces.json" ;;
  *) echo "$(basename "$0") $*" >> "$STATE/log" ;;
esac
"""


class MarketplacePluginsTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.home = root / "home"
        self.state = root / "state"
        bin_dir = root / "bin"
        for path in (self.home, self.state, bin_dir):
            path.mkdir()
        for name in ("claude", "codex"):
            (bin_dir / name).write_text(FAKE_CLI)
            (bin_dir / name).chmod(0o755)
        (self.state / "claude-plugins.json").write_text(
            json.dumps(
                [
                    {"id": "kept@official", "scope": "user"},
                    {"id": "retired@official", "scope": "user"},
                    {"id": "manual@official", "scope": "user"},
                ]
            )
        )
        (self.state / "claude-marketplaces.json").write_text(
            json.dumps([{"name": "official"}])
        )
        (self.state / "codex-plugins.json").write_text(json.dumps({"installed": []}))
        (self.state / "codex-marketplaces.json").write_text(
            json.dumps({"marketplaces": [{"name": "corp"}]})
        )
        ownership = self.home / marketplace_plugins.OWNERSHIP
        ownership.parent.mkdir(parents=True)
        ownership.write_text(
            json.dumps(["claude:kept@official", "claude:retired@official"])
        )
        self.data = {
            "marketplaces": {
                "official": {"github": "owner/official"},
                "corp": {"git": "https://example.test/corp.git"},
            },
            "plugins": {
                "kept@official": {"harnesses": ["claude"]},
                "browser@corp": {"harnesses": ["claude", "codex"]},
            },
        }
        marketplace_plugins.conform(self.data)
        patcher = mock.patch.dict(
            os.environ,
            {"PATH": f"{bin_dir}:{os.environ['PATH']}", "STATE": str(self.state)},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def reconcile(self, check: bool) -> tuple[bool, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            changed = marketplace_plugins.reconcile(
                home=self.home,
                data=self.data,
                harnesses=["claude", "codex", "pi"],
                check=check,
            )
        return changed, output.getvalue()

    def test_apply_installs_declared_and_uninstalls_only_retired_owned(self) -> None:
        changed, _ = self.reconcile(check=False)

        self.assertTrue(changed)
        self.assertEqual(
            (self.state / "log").read_text().splitlines(),
            [
                "claude plugin marketplace add https://example.test/corp.git",
                "claude plugin install browser@corp --scope user",
                "claude plugin uninstall retired@official --scope user",
                "codex plugin add browser@corp",
            ],
        )
        self.assertEqual(
            json.loads((self.home / marketplace_plugins.OWNERSHIP).read_text()),
            ["claude:browser@corp", "claude:kept@official", "codex:browser@corp"],
        )

    def test_check_reports_without_running(self) -> None:
        changed, output = self.reconcile(check=True)

        self.assertTrue(changed)
        self.assertFalse((self.state / "log").exists())
        self.assertIn("would run codex plugin add browser@corp\n", output)

    def test_malformed_declarations_are_rejected(self) -> None:
        for data, reason in (
            (
                {
                    "marketplaces": {},
                    "plugins": {"x@nowhere": {"harnesses": ["claude"]}},
                },
                "x@nowhere must name a declared",
            ),
            (
                {"marketplaces": {"m": {"github": ""}}, "plugins": {}},
                "marketplace m needs exactly one of",
            ),
        ):
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(ValueError, reason),
            ):
                marketplace_plugins.conform(data)


if __name__ == "__main__":
    unittest.main()
