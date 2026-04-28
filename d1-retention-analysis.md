# D1 Retention Analysis

## What you have access to

The following data has already been loaded into your prompt:

- A daily slice of the **`d1_retention.csv`** sheet, filtered to the **All** acquisition source for the last 180 days, across both `ios` and `android` platforms. This is the inlined "## Pre-loaded data" table above.

Beyond that, you have two MCP tools:

- `list_files()` — returns every file in `data/` along with a one-line description of what it is. Always call this once early in your reasoning. The descriptions tell you which files are worth loading for the dip days you flag.
- `load_file('<path>')` — load the contents of any file `list_files()` showed you. Use this to pull in the full sheet for per-source detail, a data dictionary to interpret columns correctly, or any context document (holiday calendar, event log, incident log, release log, marketing campaigns) that looks relevant to the dip dates you're investigating.

## My hypothesis

D1 retention has been volatile across platforms over the last few months. I think three things are driving it:

1. **News intensity / breaking-news traffic.** On high-impact news days, a wave of one-time visitors arrives for the breaking story but does not return. The mechanical effect: `dau` and `installs` spike, the new-user denominator swells, `d1` drops the next day. Verifiable via the relationship between `installs` (or `dau`) on day T and `d1` on day T.

2. **Notification-channel sensitivity.** When `pct_dau_via_notifications` is unusually high (or rises suddenly), retention may be propped up artificially by re-engagement pushes. When that share drops, "real" retention is exposed. Look at `dau_via_notifications` / `dau_via_launcher` / `dau_via_deeplink` ratios on dip days vs steady-state days.

3. **iOS vs Android divergence.** The two platforms behave differently around news events because of differences in app-install friction, default notification behaviour, and acquisition mix. Check whether retention dips happen simultaneously on both platforms, or whether one leads the other.

## What I want you to do

**Step 1 — find the dip days.**
Compute a trailing 7-day mean of `d1` per platform. Flag every day where `d1` falls more than 5% below its trailing mean. List those dates explicitly.

**Step 2 — test hypothesis #1.**
For each flagged day, look at `installs` and `dau` on that same day vs the trailing average. If installs / dau spike to roughly 1.5× or more of normal alongside the `d1` dip, hypothesis #1 is supported. Cite the specific numbers.

**Step 3 — test hypothesis #2.**
For the same flagged days, look at `pct_dau_via_notifications`, `pct_dau_via_launcher`, and `pct_dau_via_deeplink`. Is there a pattern? Does `pct_dau_via_notifications` rise on dip days (suggesting push-driven retention propping things up before the dip), or does it fall (suggesting users are tuning out)?

**Step 4 — test hypothesis #3.**
Compare ios-row dip days vs android-row dip days. Are they the same dates, or do they diverge? If they diverge meaningfully, that says something about the acquisition / engagement mechanics on each platform.

**Step 5 — surprising finding.**
Mention one thing in the data that I didn't ask about but that you think the PM should know.

**Step 6 — pull in extra context as needed.**
Call `list_files()` (if you haven't already) to see what context documents are available — each one comes with a one-line description. For each flagged dip date, decide which docs are worth reading: a holiday calendar to rule out family-festival days, an event log for news / sports spikes, an incidents log for push outages, a release log for product changes, a marketing log for paid-acquisition spikes, a data dictionary to disambiguate `d1` vs `d1_corrected`. Load the full sheet (per-source breakdown) only if a verdict on hypothesis #1 or #2 changes once you look at it.

## Report shape

Produce these sections in order:

- **TL;DR** — 2 sentences max
- **Hypothesis verdicts table** — one row per hypothesis, columns: `# | Hypothesis | Verdict | One-line evidence`. Verdict is one of: `HELD UP`, `INCONCLUSIVE`, `REJECTED`, `MIXED`.
- **Key findings** — 4-6 bullets, each citing specific dates and numeric values
- **Evidence table** — at least 5 rows, columns: `Date | Platform | d1 | trailing-7d mean | Δ vs trailing | dau | installs | pct_dau_via_notifications | Note`
- **Suggested actions** — 3-5 concrete actions ranked by expected impact and effort. Be specific. If an action involves spending money or changing push frequency, say where exactly.
- **Caveats** — what limitations of the data restrict the strength of each verdict

Be specific with dates and numbers. Do not generalise vaguely. Every claim must trace to a row in the inlined table or a file you load.
