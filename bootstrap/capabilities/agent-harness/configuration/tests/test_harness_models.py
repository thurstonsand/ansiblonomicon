"""Check native frontmatter model resolution without changing agent prompts."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness_filters import agent_harness_transform_skill_content


class HarnessModelsTest(unittest.TestCase):
    def test_scalar_and_per_harness_models_render_as_native_aliases(self) -> None:
        tiers = {
            "fable": {"claude": "fable", "pi": "anthropic/fable-test"},
            "astra": {"pi": "openai/astra-test"},
        }
        for declaration, harness, expected in (
            ("{claude: fable, pi: astra}", "claude", "fable"),
            ("{claude: fable, pi: astra}", "pi", "openai/astra-test"),
            ("fable", "claude", "fable"),
            ("fable", "pi", "anthropic/fable-test"),
        ):
            with self.subTest(declaration=declaration, harness=harness):
                result = agent_harness_transform_skill_content(
                    f"---\nname: reviewer\nmodel: {declaration}\n---\nReview only.\n",
                    harness,
                    tiers,
                )
                self.assertEqual(
                    result["content"],
                    f"---\nname: reviewer\nmodel: {expected}\n---\nReview only.\n",
                )
