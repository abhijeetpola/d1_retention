"""Tool: compute_acquisition_mix_shift — per-source share deltas for one date."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools._common import (
    MIX_SOURCES,
    VALID_PLATFORMS,
    coerce_metric,
    sheet,
    server,
)


@server.tool(
    description=(
        "Compute the per-source acquisition mix shift for a single date and "
        "platform — Stage 1 step 2 of the diagnostic checklist. "
        "Use this to answer 'did WTA / paid / others share spike on the cohort day?' — "
        "do NOT load the full sheet and compute by hand. "
        "Returns each source's installs, share-of-platform-total, the share "
        "delta in percentage points vs the trailing baseline_days mean, and "
        "the install-volume ratio vs the baseline mean. The denominator for "
        "share excludes the 'All' aggregate row. "
        "Returns {ok, date, platform, baseline_days, baseline_window, "
        "total_installs_today, total_installs_baseline_mean, "
        "total_installs_ratio, by_source: {source: {installs, share_pct, "
        "baseline_mean_installs, baseline_mean_share_pct, share_delta_pp, "
        "installs_ratio_vs_baseline}}, biggest_mover}."
    )
)
def compute_acquisition_mix_shift(
    date: str,
    platform: str,
    baseline_days: int = 7,
) -> dict[str, Any]:
    if platform not in VALID_PLATFORMS:
        return {
            "ok": False,
            "error": f"platform must be one of {VALID_PLATFORMS}, got {platform!r}",
        }
    if baseline_days <= 0:
        return {
            "ok": False,
            "error": f"baseline_days must be > 0, got {baseline_days}",
        }

    target = pd.to_datetime(date, errors="coerce")
    if pd.isna(target):
        return {"ok": False, "error": f"date not parseable: {date!r}"}

    df = sheet()
    df = df[
        (df["platform"] == platform) & (df["acquisition_source"] != "All")
    ].copy()
    if df.empty:
        return {
            "ok": False,
            "error": f"no rows for platform={platform!r} (excluding 'All')",
        }

    df["installs"] = coerce_metric(df["installs"]).fillna(0)

    pivot = df.pivot_table(
        index="date",
        columns="acquisition_source",
        values="installs",
        aggfunc="sum",
    ).fillna(0)
    for s in MIX_SOURCES:
        if s not in pivot.columns:
            pivot[s] = 0.0
    pivot = pivot[list(MIX_SOURCES)]
    pivot["__total"] = pivot[list(MIX_SOURCES)].sum(axis=1)
    for s in MIX_SOURCES:
        pivot[f"{s}__share"] = pivot[s].where(
            pivot["__total"] > 0, other=0
        ) / pivot["__total"].replace(0, pd.NA)

    if target not in pivot.index:
        return {
            "ok": False,
            "error": f"no row for {target.date()} on platform={platform!r}",
        }

    baseline_start = target - pd.Timedelta(days=baseline_days)
    baseline_end = target - pd.Timedelta(days=1)
    baseline_rows = pivot[
        (pivot.index >= baseline_start) & (pivot.index <= baseline_end)
    ]
    if baseline_rows.empty:
        return {
            "ok": False,
            "error": (
                f"baseline window has no rows ({baseline_start.date()}.."
                f"{baseline_end.date()})"
            ),
        }

    today_row = pivot.loc[target]
    today_total = float(today_row["__total"])
    baseline_total_mean = float(baseline_rows["__total"].mean())
    total_ratio = (
        round(today_total / baseline_total_mean, 3) if baseline_total_mean else None
    )

    by_source: dict[str, dict[str, Any]] = {}
    for s in MIX_SOURCES:
        today_installs = float(today_row[s])
        today_share = float(today_row.get(f"{s}__share") or 0.0)
        baseline_mean_installs = float(baseline_rows[s].mean())
        baseline_share_series = baseline_rows[f"{s}__share"].dropna()
        baseline_mean_share = (
            float(baseline_share_series.mean())
            if not baseline_share_series.empty
            else 0.0
        )
        share_delta_pp = round((today_share - baseline_mean_share) * 100.0, 2)
        installs_ratio = (
            round(today_installs / baseline_mean_installs, 3)
            if baseline_mean_installs > 0
            else None
        )
        by_source[s] = {
            "installs": int(today_installs),
            "share_pct": round(today_share * 100.0, 2),
            "baseline_mean_installs": round(baseline_mean_installs, 1),
            "baseline_mean_share_pct": round(baseline_mean_share * 100.0, 2),
            "share_delta_pp": share_delta_pp,
            "installs_ratio_vs_baseline": installs_ratio,
        }

    biggest_mover = max(
        MIX_SOURCES, key=lambda s: abs(by_source[s]["share_delta_pp"])
    )

    return {
        "ok": True,
        "date": str(target.date()),
        "platform": platform,
        "baseline_days": baseline_days,
        "baseline_window": f"{baseline_start.date()}..{baseline_end.date()}",
        "total_installs_today": int(today_total),
        "total_installs_baseline_mean": round(baseline_total_mean, 1),
        "total_installs_ratio": total_ratio,
        "by_source": by_source,
        "biggest_mover": biggest_mover,
    }
