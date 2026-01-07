"""Pytest configuration for agent_harness tests."""

from pathlib import Path
import sys

# Add filter_plugins to path so harness_filters can be imported
sys.path.insert(0, str(Path(__file__).parent.parent / "filter_plugins"))
