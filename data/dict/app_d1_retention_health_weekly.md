<!-- desc: Definitions of every column in app_d1_retention_health_weekly.csv — weekly D1 cohort pivot covering all platforms × all acquisition sources -->
# Data dictionary — `sheets/app_d1_retention_health_weekly.csv`

> Authoritative column reference for `sheets/app_d1_retention_health_weekly.csv`. The playbook (`d1-retention-analysis.md`) carries the diagnostic flow and refers to this sheet by name; this file carries the column-level depth — ISO-week conventions, cohort-aggregated rate semantics, partial-week gotchas, and when to prefer this sheet over the primary. Load via `load_file('dict/app_d1_retention_health_weekly.md')` before reading this sheet for the first time in a run.

Weekly D1 cohort retention pivot. **Pre-aggregated from the primary fact table** so you read week-aggregated D1 directly instead of computing it. This is the comprehensive pivot — it covers every platform × acquisition_source combination — and is the right sheet for week-over-week or weekly-trend questions.

## Coverage

This pivot has the full segmentation matrix:

| Dimension | Values present |
|---|---|
| `platform` | `android`, `ios` |
| `acquisition_source` | `All`, `organic`, `paid`, `WTA`, `others` |

`acquisition_source = 'All'` is the **pre-calculated aggregate** for the platform — do not sum the others to derive it. Always either filter to a specific source or read the `All` row directly, never both.

## Sheet structure

- One row per **(d1_cohort_week × platform × acquisition_source)**.
- The cohort_week is the **install week** — D1 retention is measured on installs whose install day fell in that ISO week, and "return" is the next-day return for each install.
- Rows whose `SUM of d1_installs = 0` show `d1_weekly = #DIV/0!`. Treat these as null.
- The very first row of the file may be blank (header artifact from the source pivot). Filter out rows where the cohort-week column is empty before doing analysis.

## Columns

| Column | Meaning |
|---|---|
| `d1_cohort_week` | Install week in ISO 8601 `YYYY-Www` format (e.g., `2025-W18` = week 18 of 2025, Monday-to-Sunday). |
| `platform` | `android` or `ios`. |
| `acquisition_source` | `All`, `organic`, `paid`, `WTA`, or `others`. |
| `SUM of d1_installs` | Total installs in the week for this segment. |
| `SUM of d1_users` | Total users from those installs who returned on D1 (the day after install). |
| `d1_weekly` | Cohort-aggregated D1 rate = `SUM of d1_users / SUM of d1_installs`. The methodology-correct weekly rate. |

## When to prefer this sheet

- "Compare D1 this week vs last week" — read two rows of this sheet and diff.
- "What is the weekly trend for Android organic D1 over the last quarter?" — filter platform/source, then read `d1_weekly` across `d1_cohort_week`.
- "Has iOS paid D1 changed week over week?" — same pattern, different filter.

## When NOT to use this sheet

- Single-day question — the daily granularity is in the primary `app_health_daily` (use `d1_corrected` per day).
- You want signals beyond D1 (opt-in, engagement, mix shift) — those live on the primary, not on this pivot.

## Methodology — cohort aggregation

Weekly D1 = `sum(d1_users in the week) / sum(d1_installs in the week)`. The `d1_weekly` column already has this. **Never average daily `d1` from the primary fact table to produce a weekly number** — that gives a biased result because it equally weights small and large install days. If for some reason you need to compute a weekly rate yourself, sum the absolute counts first and divide once.

## Gotchas

- The `d1_cohort_week` column uses ISO weeks, which start on Monday. Calendar weeks that begin on Sunday (e.g. retail conventions) will not line up.
- Most-recent week may be partial — installs late in the week have not yet had time to complete D1, so the week's `d1_weekly` value can drift downward as the cohort matures. Check `d1_installs` against neighbouring weeks; an unusually low value usually means the week is still landing.
- `acquisition_source = 'All'` rows include WTA in the aggregate. If the LLM's diagnosis cites organic D1 alone, filter to `organic`, not `All`.
