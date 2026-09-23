"""Pytest configuration shared by the repository tests."""

from pathlib import Path
import sys

# harness_filters is a plain module beside the native harness engine; the
# catalogue tests import it by name the same way catalogue.py does.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "bootstrap/capabilities/agent-harness")
)
