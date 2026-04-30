"""Tool: list_files — directory listing with one-line descriptions per file."""

from __future__ import annotations

from tools._common import DATA_DIR, extract_description, server


@server.tool(
    description=(
        "List every file available in the sandbox data folder, each with a "
        "one-line description of its purpose. Returns "
        "{'files': [{'path': '<relative path>', 'desc': '<one-line description>'}, ...]}. "
        "Use the description to decide which files are worth loading via load_file('<path>'). "
        "Empty desc means the file did not declare one."
    )
)
def list_files() -> dict[str, list[dict[str, str]]]:
    if not DATA_DIR.exists():
        return {"files": []}
    items: list[dict[str, str]] = []
    for p in sorted(DATA_DIR.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        items.append(
            {
                "path": str(p.relative_to(DATA_DIR)),
                "desc": extract_description(p),
            }
        )
    return {"files": items}
