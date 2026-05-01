"""Tool: compute_rolling_average — N-day rolling mean for one segment."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools._common import (
    aggregate,
    get_rows,
    server,
    validate_segment,
)


@server.tool(
    description=(
        "Compute the rolling average of `metric` over `window_days` ending on "
        "`end_date` (inclusive) for one platform × acquisition_source segment. "
        "Use this whenever you need a 7-day or any-N-day rolling average — do "
        "not derive it yourself. Returns "
        "{ok, metric, platform, acquisition_source, end_date, window_days, "
        "average, n_observations}. Set window_days=7 for the standard 7-day "
        "rolling baseline used in the dip threshold rules."
    )
)
def compute_rolling_average(
    metric: str,
    platform: str,
    acquisition_source: str,
    end_date: str,
    window_days: int = 7,
) -> dict[str, Any]:
    err = validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}
    if window_days <= 0:
        return {"ok": False, "error": f"window_days must be > 0, got {window_days}"}

    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(end):
        return {"ok": False, "error": f"end_date not parseable: {end_date!r}"}
    start = end - pd.Timedelta(days=window_days - 1)

    rows = get_rows(
        platform=platform,
        acquisition_source=acquisition_source,
        date_from=start,
        date_to=end,
    )
    if metric not in rows.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}

    average = aggregate(rows, metric, "mean")
    if average is None:
        return {
            "ok": False,
            "error": (
                f"no values for metric={metric} in {start.date()}..{end.date()} "
                f"({platform} / {acquisition_source})"
            ),
        }
    n = aggregate(rows, metric, "count") or 0
    n = int(n)
    return {
        "ok": True,
        "metric": metric,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "end_date": str(end.date()),
        "start_date": str(start.date()),
        "window_days": window_days,
        "average": round(float(average), 6),
        "n_observations": n,
        # Partial-window flag: true when fewer days had data than were requested.
        # The LLM should weaken its severity verdict when the baseline is partial
        # (a 5-of-7 mean is materially noisier than a full-7 mean).
        "partial_window": n < window_days,
        "coverage_pct": round(n / window_days * 100.0, 1) if window_days else 0.0,
    }
