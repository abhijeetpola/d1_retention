"""Tool: load_file — read one file by relative path under data/.

Supported types: .csv, .tsv, .xlsx, .md, .txt, .json, .yaml, .yml. CSV/TSV/XLSX
are rendered as Markdown tables; other types are returned as text. Path-traversal
protected: every read resolves under DATA_DIR or is rejected.
"""

from __future__ import annotations

import json
from typing import Any

from tools._common import render_table, safe_resolve, server
from tools.list_docs import list_docs


@server.tool(
    description=(
        "Load one file from the sandbox data folder. "
        "Supported types: .csv, .tsv, .xlsx, .md, .txt, .json, .yaml, .yml. "
        "CSV/TSV/XLSX are rendered as Markdown tables. Other types are returned "
        "as text. The filename is relative to the data/ folder, e.g. "
        "'dict/app_health_daily.md' or 'sheets/app_health_daily.csv'."
    )
)
def load_file(filename: str) -> dict[str, Any]:
    target = safe_resolve(filename)
    if target is None:
        return {
            "ok": False,
            "error": (
                f"refusing to load {filename!r}: must be a relative path "
                f"that stays within data/. Try list_docs() to see what context "
                f"docs are available; sheets are reached via get_rows."
            ),
        }
    if not target.exists():
        available = list_docs()["files"]
        return {
            "ok": False,
            "error": f"file not found: {filename!r}",
            "available": available,
        }
    if not target.is_file():
        return {"ok": False, "error": f"not a file: {filename!r}"}

    suffix = target.suffix.lower()
    try:
        if suffix in (".csv", ".tsv"):
            content = render_table(target, sep="\t" if suffix == ".tsv" else ",")
        elif suffix == ".xlsx":
            content = render_table(target, excel=True)
        elif suffix in (".md", ".txt"):
            content = target.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".json":
            content = json.dumps(
                json.loads(target.read_text(encoding="utf-8")), indent=2
            )
        elif suffix in (".yaml", ".yml"):
            content = target.read_text(encoding="utf-8", errors="replace")
        else:
            return {"ok": False, "error": f"unsupported file type: {suffix}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return {"ok": True, "filename": filename, "content": content}
