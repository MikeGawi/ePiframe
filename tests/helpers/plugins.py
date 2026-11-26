"""The test plugins in tests/plugins (every hook of Plugin API v2)."""

from pathlib import Path

TEST_PLUGINS = Path(__file__).resolve().parents[1] / "plugins"
ORDER_FILE = str(TEST_PLUGINS / "order.cfg")
