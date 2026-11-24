"""Verify Antigravity configuration rendering and MCP config merging."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

CONFIG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONFIG_DIR))
import agy  # noqa: E402
import deploy  # noqa: E402

SAMPLE_LIBRARIAN_TOML = (
    'name = "librarian"\n'
    'description = "Research agent. Spawn it with fork_turns \\"none\\": '
    'it needs only the question, not this conversation."\n'
    'developer_instructions = "Use librarian CLI."\n'
)


class AgyRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.data = {
            "models": {
                "google": {
                    "gemini_neon": {
                        "version": "gemini-4-neon-high",
                        "display_name": "Gemini 4 Neon (High)",
                        "agent_harness": {"aliases": {"agy": "inherit"}},
                    },
                }
            }
        }

    def test_render_preserves_live_state_and_strips_empty_permissions(self) -> None:
        settings_path = self.home / ".gemini/antigravity-cli/settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "trustedWorkspaces": ["/home/test"],
                    "model": "Gemini 4 Neon (XHigh)",
                    "enableTerminalSandbox": False,
                    "permissions": {"ask": [], "deny": []},
                }
            )
        )
        hooks_path = self.home / ".gemini/config/hooks.json"
        hooks_path.parent.mkdir(parents=True)
        hooks_path.write_text(json.dumps({"user-custom": {"Stop": []}}))

        with (
            mock.patch.object(agy.librarian, "cli", return_value=Path("/bin/true")),
            mock.patch.object(
                agy.librarian,
                "codex_setup",
                return_value={".codex/agents/librarian.toml": SAMPLE_LIBRARIAN_TOML},
            ),
        ):
            outputs = agy.render(
                repo=self.home,
                home=self.home,
                hostname="pod042",
                data=self.data,
                secrets={},
            )

        settings = json.loads(outputs[".gemini/antigravity-cli/settings.json"])
        self.assertEqual(settings["model"], "Gemini 4 Neon (XHigh)")
        self.assertEqual(settings["trustedWorkspaces"], ["/home/test"])
        self.assertEqual(settings["agentMode"], "accept-edits")
        self.assertEqual(settings["toolPermission"], "always-proceed")
        self.assertEqual(settings["altScreenMode"], "always")
        self.assertNotIn("enableTerminalSandbox", settings)
        self.assertNotIn("permissions", settings)

        keybindings = json.loads(outputs[".gemini/antigravity-cli/keybindings.json"])
        self.assertEqual(keybindings["navigation.half_page_up"], ["alt+k"])
        self.assertEqual(keybindings["navigation.half_page_down"], ["alt+j"])
        self.assertEqual(keybindings["navigation.go_to_top"], ["alt+g"])
        self.assertEqual(keybindings["navigation.go_to_bottom"], ["alt+shift+g"])
        self.assertEqual(keybindings["subagent.jump_to_waiting"], ["alt+w"])

        hooks = json.loads(outputs[".gemini/config/hooks.json"])
        self.assertIn("user-custom", hooks)
        self.assertIn("command-timing", hooks)
        self.assertIn("no-chat-comments", hooks)

        librarian_md = outputs[".gemini/config/agents/librarian.md"]
        self.assertIn("model: inherit\n", librarian_md)
        self.assertNotIn("fork_turns", librarian_md)
        self.assertIn("Use librarian CLI.", librarian_md)
        self.assertNotIn(".gemini/config/rules/local.md", outputs)

    def test_render_emits_local_rule_when_local_md_exists(self) -> None:
        local_md = self.home / ".agents/local.md"
        local_md.parent.mkdir(parents=True)
        local_md.write_text("Local instructions.\n")
        with (
            mock.patch.object(agy.librarian, "cli", return_value=Path("/bin/true")),
            mock.patch.object(
                agy.librarian,
                "codex_setup",
                return_value={".codex/agents/librarian.toml": SAMPLE_LIBRARIAN_TOML},
            ),
        ):
            outputs = agy.render(
                repo=self.home,
                home=self.home,
                hostname="pod042",
                data=self.data,
                secrets={},
            )
        self.assertIn(
            "@[Local](~/.agents/local.md)", outputs[".gemini/config/rules/local.md"]
        )

    def test_agy_mcp_handles_empty_file_merges_and_retires_owned_servers(self) -> None:
        mcp_path = self.home / ".gemini/config/mcp_config.json"
        mcp_path.parent.mkdir(parents=True)
        mcp_path.write_text("")

        data = {
            "mcp_servers": [
                {
                    "name": "local-tool",
                    "transport": "stdio",
                    "command": "/usr/bin/tool",
                    "args": ["--flag"],
                    "tool_timeout_sec": 300,
                    "harnesses": ["agy"],
                },
                {
                    "name": "remote-tool",
                    "transport": "http",
                    "url": "https://example.test/mcp",
                    "headers": {"X-Test": "1"},
                    "oauth": {"client_id": "cid", "callback_port": 9999},
                    "harnesses": ["agy"],
                },
            ]
        }
        result = deploy._agy_mcp_output(self.home, data, set())  # pyright: ignore[reportPrivateUsage]
        assert result is not None
        relative, content = result
        self.assertEqual(relative, ".gemini/config/mcp_config.json")
        parsed = json.loads(content)
        self.assertEqual(
            parsed["mcpServers"]["local-tool"],
            {"command": "/usr/bin/tool", "args": ["--flag"], "timeoutSeconds": 300},
        )
        self.assertEqual(
            parsed["mcpServers"]["remote-tool"],
            {
                "serverUrl": "https://example.test/mcp",
                "headers": {"X-Test": "1"},
                "oauth": {"clientId": "cid"},
            },
        )

        # Unmanaged servers survive while retired managed servers are removed.
        parsed["mcpServers"]["manual"] = {"command": "/bin/echo"}
        mcp_path.write_text(json.dumps(parsed))
        retired = deploy._agy_mcp_output(  # pyright: ignore[reportPrivateUsage]
            self.home,
            {"mcp_servers": []},
            {"local-tool", "remote-tool"},
        )
        assert retired is not None
        after = json.loads(retired[1])
        self.assertEqual(list(after["mcpServers"]), ["manual"])


if __name__ == "__main__":
    unittest.main()
