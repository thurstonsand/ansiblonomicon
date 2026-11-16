"""Exercise publication against a local Git remote instead of the hosted account."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

PUBLISHER = Path(__file__).resolve().parents[5] / "scripts/publish-amp-plugins.sh"


class PublishPluginsTest(unittest.TestCase):
    def test_scoped_publication_preserves_other_plugins_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            remote = root / "remote.git"
            seed = root / "seed"
            bin_dir = root / "bin"
            for directory in (source, seed, bin_dir):
                directory.mkdir()

            def run(*args: str, cwd: Path = source) -> str:
                return subprocess.run(
                    args, cwd=cwd, check=True, capture_output=True, text=True
                ).stdout.strip()

            for repo in (source, seed):
                run("git", "init", "-b", "main", cwd=repo)
                run("git", "config", "user.name", "Publisher test", cwd=repo)
                run("git", "config", "user.email", "test@example.invalid", cwd=repo)
            run("git", "init", "--bare", "-b", "main", str(remote))
            (seed / "unrelated.ts").write_text("keep me\n")
            (seed / "owned").mkdir()
            (seed / "owned/obsolete.ts").write_text("remove me\n")
            (seed / "one.ts").write_text("old version\n")
            run("git", "add", ".", cwd=seed)
            run("git", "commit", "-m", "Seed hosted plugins", cwd=seed)
            run("git", "remote", "add", "origin", str(remote), cwd=seed)
            run("git", "push", "origin", "main", cwd=seed)
            initial = run("git", "--git-dir", str(remote), "rev-parse", "main")

            plugins = source / "bootstrap/capabilities/agent-harness/amp-plugins"
            (plugins / "owned").mkdir(parents=True)
            (plugins / "owned/index.ts").write_text("current directory plugin\n")
            (plugins / "one.ts").write_text("current file plugin\n")
            (plugins / "reviewer.ts").write_text(
                "const MODEL = 'local/default'\n"
                "const REASONING_EFFORT = 'low'\n"
                "const INSTRUCTIONS = ''\n"
            )
            (source / "scripts").mkdir()
            shutil.copy2(PUBLISHER, source / "scripts/publish-amp-plugins.sh")
            capability = plugins.parent
            prompt = capability / "reviewer.md"
            prompt.write_text(
                "---\nname: reviewer\n---\n\n"
                'Review `src/handler.ts`, "quotes", \\paths, and ${templates}.\n'
                "Keep both lines.\n"
            )
            original = PUBLISHER.parent.parent / "bootstrap/capabilities/agent-harness"
            for name in (
                "render_amp_plugins.py",
                "catalogue.py",
                "harness_filters.py",
            ):
                shutil.copy2(original / name, capability / name)
            shutil.copy2(PUBLISHER.parent.parent / "pyproject.toml", source)
            (source / ".venv").symlink_to(sys.prefix, target_is_directory=True)
            upstream = root / "upstream.ts"
            lifecycle = """async function runSubagent(
	agent: Agent,
	message: string,
	ctx: PluginToolContext,
	timeoutMs: number,
): Promise<string> {
	const thread = await agent.createThread({ parentThreadID: ctx.thread.id })
	const cancel = (): void => void thread.cancel()
	ctx.signal.addEventListener('abort', cancel, { once: true })
	try {
		await thread.appendUserMessage({ type: 'user-message', content: message })
		const reply = await thread.waitForResponse({ timeoutMs })
		return reply.content.flatMap((block) => (block.type === 'text' ? [block.text] : [])).join('')
	} finally {
		ctx.signal.removeEventListener('abort', cancel)
	}
}
"""
            upstream_tools = """		tools: {
			include: [
				'shell_command',
				'web_search',
				'read_web_page',
				'read_thread',
				'find_thread',
				'finder',
				'librarian',
			],
			exclude: ['tool_search', 'code_exec'],
		},"""
            registration = (
                """
export default function (amp) {
	const agent = amp.createAgent({
		model: MODEL, reasoningEffort: REASONING_EFFORT, instructions,
"""
                + upstream_tools
                + """
	})
	amp.registerTool({
		name: 'research',
		execute: (input, ctx) => runSubagent(agent, input.task, ctx, 60000),
	})
}
"""
            )
            upstream.write_text(
                "const MODEL = 'upstream/default'\n"
                'const REASONING_EFFORT = "medium";\n'
                "const instructions = `Original prompt.`\n\n" + lifecycle + registration
            )
            (capability / "models.yml").write_text(
                yaml.safe_dump(
                    {
                        "models": {
                            "provider": {
                                "review": {
                                    "agent_harness": {
                                        "aliases": {"amp": "vendor/reviewer"}
                                    }
                                },
                                "search": {
                                    "agent_harness": {
                                        "aliases": {"amp": "vendor/searcher"}
                                    }
                                },
                            }
                        },
                        "amp": {
                            "plugins": {
                                "oracle": {
                                    "source": upstream.as_uri(),
                                    "model": "provider.review",
                                    "effort": "xhigh",
                                },
                                "finder": {
                                    "source": upstream.as_uri(),
                                    "model": "provider.search",
                                    "effort": "low",
                                },
                                "reviewer": {
                                    "instructions": "reviewer.md",
                                    "model": "provider.review",
                                    "effort": "high",
                                },
                            }
                        },
                    }
                )
            )
            run("git", "add", ".")
            run("git", "commit", "-m", "Declare plugins")

            repository = json.dumps(
                [
                    {
                        "scope": "user",
                        "exists": True,
                        "viewerCanWrite": True,
                        "cloneURL": str(remote),
                    }
                ]
            )
            amp = bin_dir / "amp"
            amp.write_text(
                '#!/usr/bin/env bash\nset -euo pipefail\ncase "$*" in\n'
                f"  'plugins repositories --json') printf '%s\\n' '{repository}' ;;\n"
                f'  "clone user-plugins "*) git clone "{remote}" "$3" ;;\n'
                '  *) echo "Unexpected Amp invocation: $*" >&2; exit 1 ;;\nesac\n'
            )
            amp.chmod(0o755)

            def publish(*args: str) -> str:
                return subprocess.run(
                    ["bash", "scripts/publish-amp-plugins.sh", *args],
                    cwd=source,
                    env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout

            self.assertIn("ready to publish", publish("--dry-run"))
            self.assertEqual(
                run("git", "--git-dir", str(remote), "rev-parse", "main"), initial
            )
            publish()
            for name, expected in (
                ("unrelated.ts", "keep me"),
                ("one.ts", "current file plugin"),
                ("owned/index.ts", "current directory plugin"),
                (
                    "oracle.ts",
                    'const MODEL = "vendor/reviewer"\n'
                    'const REASONING_EFFORT = "xhigh"\n'
                    "const instructions = `Original prompt.`",
                ),
                (
                    "finder.ts",
                    'const MODEL = "vendor/searcher"\n'
                    'const REASONING_EFFORT = "low"\n'
                    "const instructions = `Original prompt.`",
                ),
                (
                    "reviewer.ts",
                    'const MODEL = "vendor/reviewer"\n'
                    'const REASONING_EFFORT = "high"\n'
                    'const INSTRUCTIONS = "Review `src/handler.ts`, \\"quotes\\", '
                    '\\\\paths, and ${templates}.\\nKeep both lines."',
                ),
            ):
                actual = run("git", "--git-dir", str(remote), "show", f"main:{name}")
                if name in {"oracle.ts", "finder.ts"}:
                    actual = actual.split("\n\n", 1)[0]
                self.assertEqual(actual, expected)
            self.assertIn(
                upstream_tools,
                run("git", "--git-dir", str(remote), "show", "main:finder.ts"),
            )
            rendered = root / "rendered.ts"
            rendered.write_text(
                run("git", "--git-dir", str(remote), "show", "main:oracle.ts")
            )
            result = json.loads(
                run(
                    "node",
                    "--input-type=module",
                    "-e",
                    """
const { default: plugin } = await import(process.argv[1])
let tool
let tools
let failure = false
plugin({
    createAgent: (options) => {
        tools = options.tools
        return { createThread: async () => ({
            id: 'T-research-child',
            appendUserMessage: async () => {},
            waitForResponse: async () => {
                if (failure) throw new Error('Inspection failed')
                return { content: [
                    { type: 'text', text: 'Found ' },
                    { type: 'image', url: 'ignored' },
                    { type: 'text', text: 'src/cache.ts.' },
                ] }
            },
            cancel: async () => {},
        }) }
    },
    registerTool: (definition) => { tool = definition },
})
const ctx = { thread: { id: 'T-parent' }, signal: new AbortController().signal }
const report = await tool.execute({ task: 'Inspect the cache.' }, ctx)
failure = true
let error
let cause
try { await tool.execute({ task: 'Inspect the cache.' }, ctx) }
catch (caught) { error = caught.message; cause = caught.cause?.message }
console.log(JSON.stringify({ report, error, cause, tools }))
""",
                    str(rendered),
                )
            )
            self.assertEqual(
                result,
                {
                    "report": "Found src/cache.ts.\n\nAgent thread: https://ampcode.com/threads/T-research-child",
                    "error": "Error: Inspection failed\n\nAgent thread: https://ampcode.com/threads/T-research-child",
                    "cause": "Inspection failed",
                    "tools": {
                        "include": [
                            "shell_command",
                            "web_search",
                            "read_web_page",
                            "read_thread",
                            "find_thread",
                            "plugin__finder__finder",
                            "plugin__librarian__librarian",
                        ],
                    },
                },
            )
            self.assertEqual(
                run(
                    "git",
                    "--git-dir",
                    str(remote),
                    "ls-tree",
                    "--name-only",
                    "main:owned",
                ),
                "index.ts",
            )
            published = run("git", "--git-dir", str(remote), "rev-parse", "main")
            self.assertIn("already current", publish())
            self.assertEqual(
                run("git", "--git-dir", str(remote), "rev-parse", "main"), published
            )
            upstream.write_text(
                "const MODEL = 'upstream/new-model'\n"
                "const REASONING_EFFORT = 'high'\n"
                "const instructions = `Updated upstream prompt.`\n\n"
                + lifecycle
                + registration
            )
            prompt.write_text("---\nname: reviewer\n---\n\nUpdated local prompt.\n")
            publish()
            self.assertEqual(
                run("git", "--git-dir", str(remote), "show", "main:oracle.ts").split(
                    "\n\n", 1
                )[0],
                'const MODEL = "vendor/reviewer"\n'
                'const REASONING_EFFORT = "xhigh"\n'
                "const instructions = `Updated upstream prompt.`",
            )
            self.assertEqual(
                run("git", "--git-dir", str(remote), "show", "main:reviewer.ts"),
                'const MODEL = "vendor/reviewer"\n'
                'const REASONING_EFFORT = "high"\n'
                'const INSTRUCTIONS = "Updated local prompt."',
            )
            published = run("git", "--git-dir", str(remote), "rev-parse", "main")
            prompt.write_text("Missing frontmatter.\n")
            with self.assertRaises(subprocess.CalledProcessError) as failure:
                publish()
            self.assertIn("expected agent frontmatter", failure.exception.stderr)
            self.assertEqual(
                run("git", "--git-dir", str(remote), "rev-parse", "main"), published
            )
            prompt.write_text("---\nname: reviewer\n---\n\nUpdated local prompt.\n")
            for invalid, diagnostic in (
                (
                    "const MODEL = chooseModel()\nconst REASONING_EFFORT = 'low'\n",
                    "expected one MODEL declaration, got 0",
                ),
                (
                    "const MODEL = 'a'\nconst MODEL = 'b'\nconst REASONING_EFFORT = 'low'\n",
                    "expected one MODEL declaration, got 2",
                ),
                (
                    "const MODEL = 'a'\nconst REASONING_EFFORT = chooseEffort()\n",
                    "expected one REASONING_EFFORT declaration, got 0",
                ),
            ):
                with self.subTest(invalid=invalid):
                    upstream.write_text(
                        invalid
                        + "const instructions = `Valid prompt.`\n\n"
                        + lifecycle
                        + registration
                    )
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        publish()
                    self.assertIn(diagnostic, failure.exception.stderr)
                    self.assertEqual(
                        run("git", "--git-dir", str(remote), "rev-parse", "main"),
                        published,
                    )
            source_body = lifecycle + registration
            for changed_tools in (
                "",
                upstream_tools + upstream_tools,
                upstream_tools.replace("'finder'", "'searcher'"),
                upstream_tools.replace("['tool_search', 'code_exec']", "['code_exec']"),
            ):
                with self.subTest(tools=changed_tools):
                    upstream.write_text(
                        "const MODEL = 'upstream/default'\n"
                        "const REASONING_EFFORT = 'low'\n"
                        "const instructions = `Prompt remains valid.`\n\n"
                        + source_body.replace(upstream_tools, changed_tools)
                    )
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        publish()
                    self.assertIn(
                        "expected one upstream Oracle tools block",
                        failure.exception.stderr,
                    )
                    self.assertEqual(
                        run("git", "--git-dir", str(remote), "rev-parse", "main"),
                        published,
                    )
            for changed in (
                registration,
                lifecycle + source_body,
                source_body.replace(
                    "parentThreadID: ctx.thread.id", "parentThreadID: undefined"
                ),
                source_body.replace("return reply.content", "return reply.blocks"),
                source_body.replace("=> runSubagent(", "=> runResearch("),
            ):
                with self.subTest(lifecycle=changed):
                    upstream.write_text(
                        "const MODEL = 'upstream/default'\n"
                        "const REASONING_EFFORT = 'low'\n"
                        "const instructions = `Prompt remains valid.`\n\n" + changed
                    )
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        publish()
                    self.assertIn(
                        "expected one upstream subagent lifecycle",
                        failure.exception.stderr,
                    )
                    self.assertEqual(
                        run("git", "--git-dir", str(remote), "rev-parse", "main"),
                        published,
                    )
