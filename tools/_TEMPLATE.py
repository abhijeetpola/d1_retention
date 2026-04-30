"""TEMPLATE for a new tool. Copy this file, rename it, and edit the marked sections.

How to use this file:
    1. Copy this file to a new name in the same folder. Use lower_snake_case.
       Example: `cp tools/_TEMPLATE.py tools/compute_deeplink_share.py`
    2. Edit ONLY the lines marked `# EDIT THIS`.
    3. Leave the lines marked `# LEAVE AS-IS` alone.
    4. Save. Run `./tune --verify` to confirm the new tool registered cleanly.
    5. Re-run `python generate_catalog.py` so the new tool gets a card in
       `primitives.md`. Now you can reference it from the playbook prose.

This file is skipped by the MCP aggregator because its name starts with `_`.
That means copying it is safe — your *new* file (without a leading `_`) is
the one that registers as a tool.
"""

# LEAVE AS-IS — these imports give you everything most tools need.
from __future__ import annotations

from typing import Any

from tools._common import (
    aggregate,
    cohort_rate,
    delta_pp,
    filter_window,
    get_rows,
    server,
    validate_segment,
)


# EDIT THIS — the description string the LLM reads to decide whether to call
# your tool. Keep it under 8 lines. Cover: what the tool does, when to use it,
# every parameter with one sentence, and the return shape.
#
# The catalog generator (generate_catalog.py) reads this string and turns it
# into a PM-friendly card in primitives.md, so it pays to write it carefully.
@server.tool(
    description=(
        "ONE-SENTENCE summary of what this tool computes. "
        "Then a sentence or two on when the LLM should call it. "
        "Parameters: "
        "  date — YYYY-MM-DD, the day to analyze. "
        "  platform — 'android' or 'ios'. "
        "  acquisition_source — 'organic' / 'paid' / 'WTA' / 'others' / 'All'. "
        "Returns {ok, date, platform, acquisition_source, <your output fields>}."
    )
)
# EDIT THIS — the function name (must match your filename without .py),
# the parameter names and defaults, and the return-type annotation.
def compute_template_metric(
    date: str,
    platform: str,
    acquisition_source: str,
) -> dict[str, Any]:
    # LEAVE AS-IS — every tool should validate platform + source up front.
    # `validate_segment` returns None when valid, an error string otherwise.
    err = validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}

    # EDIT THIS — the actual calculation. This is where the math lives.
    # Use the helpers from tools._common rather than raw pandas:
    #
    #   rows = get_rows(platform=..., acquisition_source=..., date_from=..., date_to=...)
    #     → returns a DataFrame slice you can read.
    #
    #   total = aggregate(rows, "<column>", "sum" | "mean" | "median" | "count" | "min" | "max")
    #     → one number across the rows. Returns None if no numeric data.
    #
    #   rate = cohort_rate(rows, users_col="d1_users", installs_col="d1_installs")
    #     → cohort-aggregated retention rate (the methodology-correct way for
    #       weekly / monthly retention). Returns a fraction like 0.276.
    #
    #   delta = delta_pp(today_value, baseline_value)
    #     → percentage-point delta, both inputs as fractions (0.293, not 29.3).
    #
    #   trailing = filter_window(rows, end_date="2026-04-15", days=7)
    #     → rows in the trailing window ending on end_date.
    #
    # Worked example (delete this block once you have your real math):
    rows = get_rows(
        platform=platform,
        acquisition_source=acquisition_source,
        date_from=date,
        date_to=date,
    )
    if rows.empty:
        return {
            "ok": False,
            "error": f"no row for {date} on {platform}/{acquisition_source}",
        }
    your_metric_value = aggregate(rows, "dau", "sum")
    if your_metric_value is None:
        return {"ok": False, "error": f"value missing on {date}"}

    # EDIT THIS — the dict you return. Keep keys consistent with other tools:
    #   - Always include "ok": True.
    #   - Always echo the inputs (date, platform, acquisition_source) so the
    #     LLM can see what you computed it for.
    #   - Round numbers sensibly: 6 decimals for fractions, 2 for percentages,
    #     3 for ratios, 0 for integer counts.
    return {
        "ok": True,
        "date": date,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "your_metric_value": round(float(your_metric_value), 2),
    }


# Tips you may want to keep in mind:
#
# - When you need help-functions that don't exist yet (like a new aggregation
#   or a new filter), fill out request.md at the project root rather than
#   adding pandas calls here. The engineer will add a helper to _common.py and
#   you can use it cleanly.
#
# - Test your tool standalone before referencing it from the playbook:
#       uv run python -c "from tools.<your_file> import <your_function>; \
#                         print(<your_function>('2026-04-01', 'android', 'organic'))"
#
# - Run `./tune --verify` whenever you change your tool. It catches typos
#   without spending money on an LLM run.
