"""MCP server for the PM tuning sandbox.

Two tools the LLM can call mid-reasoning:
  - list_files()             — see what's in the sandbox folder
  - load_file(filename)      — read one file by relative path

Path-traversal protected: every read resolves under DATA_DIR or is rejected.

Launched as a subprocess by `./tune` via:
    python tune_mcp.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = (PROJECT_ROOT / "data").resolve()

server = FastMCP(name="sandbox")


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
                "desc": _extract_description(p),
            }
        )
    return {"files": items}


_DESC_RE = re.compile(r"<!--\s*desc:\s*(.+?)\s*-->", re.IGNORECASE)
_BUILTIN_DESCS: dict[str, str] = {
    "sheets/d1_retention.csv": (
        "Daily retention sheet — 50 cols × all platforms × all acquisition "
        "sources × dates from 2025-05-01. Pre-loaded slice in the prompt is "
        "the 'All' source for the last 180 days; load this file for "
        "per-source breakdowns or older history."
    ),
}


def _extract_description(path: Path) -> str:
    """Best-effort one-line description for `path`.

    Order: builtin map → first-line `<!-- desc: ... -->` → first H1 within first
    6 lines → empty string.
    """
    rel = str(path.relative_to(DATA_DIR))
    if rel in _BUILTIN_DESCS:
        return _BUILTIN_DESCS[rel]
    if path.suffix.lower() not in (".md", ".txt"):
        return ""
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for _ in range(6):
                line = f.readline()
                if not line:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                m = _DESC_RE.search(stripped)
                if m:
                    return m.group(1)
                if stripped.startswith("# "):
                    return stripped[2:].strip()
    except OSError:
        pass
    return ""


@server.tool(
    description=(
        "Load one file from the sandbox data folder. "
        "Supported types: .csv, .tsv, .xlsx, .md, .txt, .json, .yaml, .yml. "
        "CSV/TSV/XLSX are rendered as Markdown tables. Other types are returned "
        "as text. The filename is relative to the data/ folder, e.g. "
        "'docs/causal_doc.md' or 'sheets/d1_retention.csv'."
    )
)
def load_file(filename: str) -> dict[str, Any]:
    target = _safe_resolve(filename)
    if target is None:
        return {
            "ok": False,
            "error": (
                f"refusing to load {filename!r}: must be a relative path "
                f"that stays within data/. Try list_files() to see what is "
                f"available."
            ),
        }
    if not target.exists():
        available = list_files()["files"]
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
            content = _render_table(target, sep="\t" if suffix == ".tsv" else ",")
        elif suffix == ".xlsx":
            content = _render_table(target, excel=True)
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


def _safe_resolve(filename: str) -> Path | None:
    """Resolve `filename` relative to DATA_DIR; return None if it escapes."""
    if filename.startswith(("/", "~")):
        return None
    candidate = (DATA_DIR / filename).resolve()
    try:
        candidate.relative_to(DATA_DIR)
    except ValueError:
        return None
    return candidate


def _render_table(path: Path, *, sep: str = ",", excel: bool = False) -> str:
    if excel:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path, sep=sep, thousands=",")
    rows, cols = df.shape
    header = (
        f"_{path.name}: {rows:,} rows × {cols} columns_\n\n"
        if rows > 0
        else f"_{path.name}: empty file_\n\n"
    )
    return header + df.to_markdown(index=False)


if __name__ == "__main__":
    server.run()
