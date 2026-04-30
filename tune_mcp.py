"""MCP server aggregator for the PM tuning sandbox.

Imports every tool file under `tools/` so each `@server.tool` decorator runs
and registers the tool with the FastMCP instance. PMs add new tools by
copying `tools/_TEMPLATE.py` to a new file in the same folder; the aggregator
picks it up automatically on the next launch.

Files in `tools/` whose names start with `_` (e.g. `_common.py`, `_TEMPLATE.py`)
are skipped — they are helpers and templates, not tools.

Launched as a subprocess by `./tune` via:
    python tune_mcp.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools._common import server  # noqa: E402  (path setup must run first)

TOOLS_DIR = PROJECT_ROOT / "tools"

for _path in sorted(TOOLS_DIR.glob("*.py")):
    name = _path.stem
    if name.startswith("_") or name == "generate_catalog":
        continue
    importlib.import_module(f"tools.{name}")


if __name__ == "__main__":
    server.run()
