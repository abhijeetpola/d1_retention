<!-- desc: Paid-acquisition campaigns and creative refreshes — explains install-quality (d0_uninstall) spikes by source -->
# Acquisition campaigns — paid marketing log

A short log of paid-acquisition pushes inside the window of
`sheets/d1_retention.csv`. Use this to explain spikes in `installs` and
`d0_uninstalls` on the `paid`, `WTA`, and `others` rows of the per-source
sheet.

This file is **marketing-maintained**. The rows below are illustrative
samples — replace with real campaigns.

## How to read this

| Column | Meaning |
|---|---|
| `Start date` | Day the campaign went live |
| `End date` | Day the campaign ended (or "ongoing") |
| `Campaign` | Internal name |
| `Channel` | Where the spend ran (Google UAC, Meta, X, YouTube, OEM, etc.) |
| `Acquisition source label` | How the source appears in `d1_retention.csv` (`paid` / `WTA` / `others`) |
| `Budget tier` | small / medium / large (relative to typical week) |
| `Expected D1` | What the team expected for that cohort |

## Sample campaigns

| Start date | End date | Campaign | Channel | Source label | Budget tier | Expected D1 |
|---|---|---|---|---|---|---|
| 2025-10-15 | 2025-10-25 | [Sample] Diwali festival push | Google UAC | paid | large | 0.10–0.13 (low; festival creatives skew casual) |
| 2025-11-12 | 2025-11-18 | [Sample] News-app comparison creative refresh | Meta | paid | medium | 0.14–0.17 (typical) |
| 2026-01-20 | ongoing | [Sample] WhatsApp share reward program | WTA | WTA | small | 0.20+ (referrals retain better) |
| 2026-03-08 | 2026-03-15 | [Sample] IPL launch creative blitz | YouTube + OEM | paid + others | large | 0.12–0.15 (cricket creatives, broad targeting) |

## How to use this file

If an `installs` spike on a flagged dip day matches a campaign window
above, cite the campaign and the expected D1 — and check whether the
observed paid-source D1 fell *outside* the expected range. The most
useful action items come from campaigns that ran as planned but
under-delivered on retention.

If you have access to the per-source breakdown (load the full sheet via
`load_file('sheets/d1_retention.csv')`), the cleanest comparison is:
campaign-window paid D1 vs paid D1 in the prior 7 quiet days.

## Marketing instructions for maintaining

- One row per campaign push, not per ad-set.
- Campaigns that ran for under 3 days can be skipped unless they had
  outsized spend.
- `Source label` must match exactly how the campaign was tagged in the
  attribution provider — that is what shows up in `d1_retention.csv`.
- Date format: `YYYY-MM-DD`. For ongoing campaigns, use `ongoing`.
- Drop rows older than the data window when the sheet is refreshed.
