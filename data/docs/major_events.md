<!-- desc: PM-maintained log of major news, sports, and political events that drove install or DAU spikes -->
# Major news / sports / political events — PM-maintained

A short log of high-impact events in the window of `sheets/d1_retention.csv`.
Use this to explain D1 dips that follow install or DAU spikes — when a
breaking story or a big match brings in a wave of one-time visitors, D1 the
next day often falls because the new-user denominator swells.

This file is **PM-maintained**. The rows below are illustrative samples.
PMs replace them with real events they remember.

## How to read this

| Column | Meaning |
|---|---|
| `Date` | Day of the event (or the day the news cycle peaked) |
| `Event` | Short label |
| `Type` | news / sports / politics / economy / disaster / celebrity |
| `Expected effect` | What the PM expected to see in retention |
| `Notes` | Anything observed after the fact, or special context |

## Sample events

| Date | Event | Type | Expected effect | Notes |
|---|---|---|---|---|
| 2025-06-12 | [Sample] Air India 171 crash | disaster | Install spike → D1 down 20–35% next 2 days; iOS more elastic | Replace with real event date if applicable |
| 2025-09-22 | [Sample] India vs Pakistan, Asia Cup final | sports | DAU spike, push share up; D1 mostly unchanged (cricket fans were already users) | Cross-check sports calendar |
| 2025-11-23 | [Sample] Maharashtra Assembly election results | politics | Install spike from paid news cycle; paid-source D1 weaker than organic | Per-source breakdown helps here |
| 2026-02-08 | [Sample] Union Budget 2026 | economy | Morning DAU spike, push share up, D1 stable | Affects business-news cohort more than mass |
| 2026-04-01 | [Sample] IPL season 19 starts | sports | Sustained DAU lift over 8 weeks, mixed D1 (depends on creative) | Season-long, not a single-day event |

## How to use this file

If a flagged dip date matches an event row above, cite both the event and
the expected effect in the "Key findings" section. If the observed dip is
much larger than what the PM expected, call it out — that's a signal
worth a follow-up investigation.

## PM instructions for maintaining

- Replace the `[Sample]` rows with real events as you remember them. Use
  the same format.
- Date format: `YYYY-MM-DD`.
- One row per event. If an event spans multiple days (election results,
  test match, festival), use the day the news cycle peaked.
- Keep the file under ~50 rows so the LLM doesn't drown in context. Drop
  rows older than the data window when refreshing the sheet.
