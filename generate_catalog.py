#!/usr/bin/env -S uv run python
"""Generate `primitives.md` — the PM-facing catalog of MCP tools.

Reads every registered tool from the MCP server and formats it into a card with:
  - A short prose summary (lifted from the tool's description string).
  - A parameter table with type, default, and required-vs-optional status.
  - A worked example the PM can copy and paste into the playbook.

Run this whenever a tool is added or its description changes:
    uv run python generate_catalog.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PRIMITIVES_MD = PROJECT_ROOT / "primitives.md"


# A few tool-specific worked examples. The catalog uses these when present;
# otherwise it builds a generic example from the input schema.
_WORKED_EXAMPLES: dict[str, str] = {
    "list_files": (
        "list_files()"
    ),
    "load_file": (
        'load_file(filename="docs/india_holidays.md")'
    ),
    "compute_rolling_average": (
        'compute_rolling_average(metric="d1_corrected", platform="android",\n'
        '                        acquisition_source="organic",\n'
        '                        end_date="2026-04-15", window_days=7)'
    ),
    "compute_stable_baseline": (
        'compute_stable_baseline(metric="d1_corrected", platform="android",\n'
        '                       acquisition_source="organic",\n'
        '                       weekday="wednesday")'
    ),
    "compare_to_baseline": (
        'compare_to_baseline(date="2026-04-02", metric="d1_corrected",\n'
        '                    platform="android", acquisition_source="organic",\n'
        '                    baseline_kind="rolling7")'
    ),
    "flag_dip_days": (
        'flag_dip_days(metric="d1_corrected", platform="android",\n'
        '              acquisition_source="organic", days_back=30,\n'
        '              baseline="rolling7")'
    ),
    "compute_signals_for_day": (
        'compute_signals_for_day(date="2026-04-02",\n'
        '                       platform="android",\n'
        '                       acquisition_source="organic")'
    ),
    "compute_acquisition_mix_shift": (
        'compute_acquisition_mix_shift(date="2026-04-01",\n'
        '                              platform="android",\n'
        '                              baseline_days=7)'
    ),
    "get_rows": (
        '# Last 30 days of iOS paid (default columns):\n'
        'get_rows(platform="ios", acquisition_source="paid")\n'
        '\n'
        '# Explicit date range, Android organic, custom columns:\n'
        'get_rows(platform="android", acquisition_source="organic",\n'
        '         date_from="2026-04-01", date_to="2026-04-07",\n'
        '         columns=["date", "d1_corrected", "installs",\n'
        '                  "pct_d0_notification_opt_in"])'
    ),
}


def _split_description(description: str) -> tuple[str, str]:
    """Separate the human-readable summary from the structured Returns clause.

    The convention in our tools: the first sentence(s) describe purpose; a
    'Returns {ok, ...}' clause near the end documents the return shape.
    """
    if not description:
        return "(no description)", ""
    text = description.strip()
    # Find the "Returns " marker if present.
    m = re.search(r"\bReturns\s+\{", text)
    if m:
        summary = text[: m.start()].strip().rstrip(".") + "."
        returns = text[m.start():].strip()
        return summary, returns
    return text, ""


def _generic_example(name: str, schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    parts: list[str] = []
    for pname, pinfo in props.items():
        if pname in required:
            ptype = pinfo.get("type", "string")
            placeholder = {
                "string": '"<value>"',
                "integer": "<int>",
                "number": "<number>",
                "boolean": "true",
            }.get(ptype, '"<value>"')
            parts.append(f'{pname}={placeholder}')
    args = ", ".join(parts)
    return f"{name}({args})"


def _format_parameters(schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return "_(no parameters)_\n"

    lines: list[str] = ["| Parameter | Type | Required | Default | Notes |",
                        "|---|---|---|---|---|"]
    for name, info in props.items():
        ptype = info.get("type", "string")
        is_required = "yes" if name in required else "no"
        default = info.get("default")
        default_repr = "—" if default is None and name in required else (
            "—" if default is None else f"`{default!r}`"
        )
        lines.append(f"| `{name}` | {ptype} | {is_required} | {default_repr} |  |")
    return "\n".join(lines) + "\n"


def _format_card(name: str, description: str, schema: dict) -> str:
    summary, returns_clause = _split_description(description)
    example = _WORKED_EXAMPLES.get(name) or _generic_example(name, schema)

    card = [f"## `{name}`", ""]
    card.append("**What it does**")
    card.append("")
    card.append(summary)
    card.append("")
    card.append("**Parameters**")
    card.append("")
    card.append(_format_parameters(schema))
    if returns_clause:
        card.append("**Return shape**")
        card.append("")
        card.append(returns_clause)
        card.append("")
    card.append("**Worked example (copy this, edit values, paste into the playbook)**")
    card.append("")
    card.append("```")
    card.append(example)
    card.append("```")
    card.append("")
    card.append("---")
    return "\n".join(card)


async def _build_catalog() -> str:
    sys.path.insert(0, str(PROJECT_ROOT))
    mcp_module = SourceFileLoader("mcp_srv", str(PROJECT_ROOT / "tune_mcp.py")).load_module()
    tools = await mcp_module.server.list_tools()
    tools_sorted = sorted(tools, key=lambda t: t.name)

    header = [
        "# Primitives — MCP tool catalog",
        "",
        "**Auto-generated by `generate_catalog.py`. Do not edit by hand.**",
        "",
        "Each card below documents one tool the LLM (and your playbook) can call.",
        "Use the worked example as a starting point: copy it, edit the values, and",
        "paste it into `d1-retention-analysis.md` where you want the calculation",
        "to happen. Then run `./tune --verify` to confirm the call is valid.",
        "",
        f"**{len(tools_sorted)} tools registered.**",
        "",
        "---",
        "",
    ]
    cards = [_format_card(t.name, t.description or "", t.inputSchema or {}) for t in tools_sorted]
    return "\n".join(header) + "\n\n".join(cards) + "\n"


def main() -> None:
    catalog = asyncio.run(_build_catalog())
    PRIMITIVES_MD.write_text(catalog, encoding="utf-8")
    print(f"Wrote {PRIMITIVES_MD.relative_to(PROJECT_ROOT)} ({len(catalog):,} chars)")


if __name__ == "__main__":
    main()
