"""Tool: list_docs — list methodology and event-context docs available for load_file."""

from __future__ import annotations

from tools._common import DATA_DIR, extract_description, server


@server.tool(
    description=(
        "List the methodology and event-context documents available for "
        "`load_file`. These live under `data/docs/` and cover release notes, "
        "holiday calendars, known incidents, news events, the retention "
        "methodology reference, and acquisition campaigns. Returns "
        "{'files': [{'path': '<docs/...>', 'desc': '<one-line description>'}, ...]}. "
        "Sheets are reached via `get_rows`, not `load_file`. Sheet "
        "dictionaries arrive in the prompt (primary) or in `get_rows` "
        "responses (pivots) — neither needs to be discovered through this tool."
    )
)
def list_docs() -> dict[str, list[dict[str, str]]]:
    docs_dir = DATA_DIR / "docs"
    if not docs_dir.exists():
        return {"files": []}
    items: list[dict[str, str]] = []
    for p in sorted(docs_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        items.append(
            {
                "path": str(p.relative_to(DATA_DIR)),
                "desc": extract_description(p),
            }
        )
    return {"files": items}
