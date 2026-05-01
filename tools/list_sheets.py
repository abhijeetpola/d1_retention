"""Tool: list_sheets — discovery for the registered Google Sheets tabs.

The LLM calls this when it does not know which sheet to read for a given
question. Each entry includes a one-line description, the dictionary path
the LLM should `load_file()` for column-level guidance, and the freshness
state from the per-sheet meta sidecar.

Freshness state is informational. The PM-script preflight refreshes any
pre_fetch tab whose schedule window has passed before this tool is reachable,
so by the time the LLM can call list_sheets, the registered sheets are
already as fresh as today's schedule allows.
"""

from __future__ import annotations

from typing import Any

from tools._common import server
from tools._sheet_store import list_sheets as _list_sheets_impl


@server.tool(
    description=(
        "List all registered Google Sheets tabs the run can read from. Call "
        "this when the PM's question implies a non-default sheet (weekly or "
        "monthly retention questions) and you are not sure which sheet to "
        "use, or when you want to see column lists and dictionary paths "
        "before reading. "
        "Each entry has: name (the sheet identifier), primary (true for the "
        "default daily fact table), description (one line), dictionary (a "
        "Markdown file under data/docs that documents the sheet's columns "
        "— call `load_file(<dictionary>)` before reading the sheet for the "
        "first time in a run), aliases (alternate names the sheet answers "
        "to), schema_columns (best-known column list from the last fetch; "
        "may be empty until the sheet has been fetched once), last_fetched_at, "
        "and last_changed_at. "
        "Returns {ok, count, sheets: [...]}."
    )
)
def list_sheets() -> dict[str, Any]:
    sheets = _list_sheets_impl()
    return {
        "ok": True,
        "count": len(sheets),
        "sheets": sheets,
    }
