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
            (source / "scripts").mkdir()
            shutil.copy2(PUBLISHER, source / "scripts/publish-amp-plugins.sh")
            capability = plugins.parent
            original = PUBLISHER.parent.parent / "bootstrap/capabilities/agent-harness"
            for name in (
                "render_amp_plugins.py",
                "amp_modes.py",
                "catalogue.py",
                "harness_filters.py",
            ):
                shutil.copy2(original / name, capability / name)
            shutil.copy2(PUBLISHER.parent.parent / "pyproject.toml", source)
            (source / ".venv").symlink_to(sys.prefix, target_is_directory=True)
            upstream = root / "upstream.ts"
            upstream.write_text(
                "const MODEL = 'upstream/default'\n"
                'const REASONING_EFFORT = "medium";\n'
                "const instructions = `Original prompt.`\n"
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
            ):
                self.assertEqual(
                    run("git", "--git-dir", str(remote), "show", f"main:{name}"),
                    expected,
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
                "const instructions = `Updated upstream prompt.`\n"
            )
            publish()
            self.assertEqual(
                run("git", "--git-dir", str(remote), "show", "main:oracle.ts"),
                'const MODEL = "vendor/reviewer"\n'
                'const REASONING_EFFORT = "xhigh"\n'
                "const instructions = `Updated upstream prompt.`",
            )
            published = run("git", "--git-dir", str(remote), "rev-parse", "main")
            for invalid in (
                "const MODEL = chooseModel()\nconst REASONING_EFFORT = 'low'\n",
                "const MODEL = 'a'\nconst MODEL = 'b'\nconst REASONING_EFFORT = 'low'\n",
                "const MODEL = 'a'\nconst REASONING_EFFORT = chooseEffort()\n",
            ):
                with self.subTest(invalid=invalid):
                    upstream.write_text(invalid)
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        publish()
                    self.assertIn("expected one", failure.exception.stderr)
                    self.assertEqual(
                        run("git", "--git-dir", str(remote), "rev-parse", "main"),
                        published,
                    )
