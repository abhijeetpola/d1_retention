<!-- desc: Definitions of every column in app_d1_retention_health_monthly.csv — monthly D1 cohort pivot. NOTE: covers android × {WTA, paid} only -->
# Data dictionary — `sheets/app_d1_retention_health_monthly.csv`

> Authoritative column reference for `sheets/app_d1_retention_health_monthly.csv`. The playbook (`d1-retention-analysis.md`) carries the diagnostic flow and refers to this sheet by name; this file carries the column-level depth — coverage limits, cohort-aggregated rate semantics, partial-month gotchas, and when to prefer this sheet over the weekly pivot or the primary. Load via `load_file('dict/app_d1_retention_health_monthly.md')` before reading this sheet for the first time in a run.

Monthly D1 cohort retention pivot. **Pre-aggregated from the primary fact table** so you read the month-aggregated D1 directly instead of computing it.

## Coverage limits — read this first

This pivot is **not** comprehensive. As of 2026-04, it covers:

| Dimension | Values present |
|---|---|
| `platform` | `android` only |
| `acquisition_source` | `WTA`, `paid` |

Every other segment (Android organic / others, all iOS segments) is **absent**. The sheet has roughly 26 rows total because of this scoping. If the PM asks about Android organic D1 by month, fall back to the primary `app_health_daily` or use the weekly pivot and aggregate the four/five weeks yourself by cohort sum.

## Sheet structure

- One row per **(d1_cohort_month × platform × acquisition_source)**.
- The cohort_month is the **install month** — D1 retention is measured on installs whose install day fell in that calendar month.
- Rows whose `SUM of d1_installs = 0` show `d1_monthly = #DIV/0!`. Treat these as null.

## Columns

| Column | Meaning |
|---|---|
| `d1_cohort_month` | Install month in `Mon-YY` format (e.g., `Apr-25`, `May-25`). Ordering is calendar-natural. |
| `platform` | `android` only on this sheet. |
| `acquisition_source` | `WTA` or `paid` only on this sheet. |
| `SUM of d1_installs` | Total installs in the month for this segment. |
| `SUM of d1_users` | Total users from those installs who returned on D1. |
| `d1_monthly` | Cohort-aggregated D1 rate = `SUM of d1_users / SUM of d1_installs`. |

## When to prefer this sheet

- Question is "what was Android paid D1 in March?" — read this directly.
- Month-over-month comparison for Android paid or WTA — this sheet has the right granularity.

## When NOT to use this sheet

- Question involves Android organic / others or any iOS segment — those rows do not exist here. Read the primary fact table and aggregate yourself, or pivot the weekly sheet by month.
- You need signals beyond D1 (opt-in, engagement, login, mix shift) — those live on the primary.
- You want week-over-week granularity inside a month — use `app_d1_retention_health_weekly` instead.

## Methodology — cohort aggregation

Monthly D1 = `sum(d1_users in the month) / sum(d1_installs in the month)`. Already done; never re-derive by averaging the daily column. The same install-weighting argument applies — small days and large days do not contribute equally, and averaging daily rates ignores that.

## Gotchas

- The most-recent month is almost always partial; installs late in the month have not yet had D1 measured. Watch the `SUM of d1_installs` value relative to prior months — a sharp drop usually means the month is still in flight, not a real install collapse.
- The `Mon-YY` date format is human-friendly but harder to sort programmatically. If reading rows in code, parse with `pd.to_datetime(..., format='%b-%y')`.
