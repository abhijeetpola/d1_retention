# D1 Retention Analysis

## What you have access to

- A daily slice of `d1_retention.csv`, filtered to **`platform=android`, `acquisition_source=organic`**, last 180 days. This is the inlined "## Pre-loaded data" table above.
- MCP tools for **deterministic math**:
  - `compute_rolling_average(metric, platform, acquisition_source, end_date, window_days)`
  - `compute_stable_baseline(metric, platform, acquisition_source, weekday=None, baseline_start_date="2026-01-01")`
  - `compare_to_baseline(date, metric, platform, acquisition_source, baseline_kind="stable" | "rolling7")`
  - `flag_dip_days(metric, platform, acquisition_source, days_back, threshold_pp_drop=2.0, threshold_pp_alert=4.0, baseline="rolling7")`
  - `compute_signals_for_day(date, platform, acquisition_source)` — returns the 8-step diagnostic signals as one dict.
  - `compute_acquisition_mix_shift(date, platform, baseline_days=7)` — per-source share deltas (organic / paid / WTA / others) for Stage 1 step 2.
- MCP tools for **context**:
  - `list_files()` — every file under `data/` with a one-line description.
  - `load_file('<path>')` — load a context document or the full sheet.

**Rule:** for any rolling average, baseline, or threshold check — call the tool. Do not derive averages or apply thresholds yourself. Pre-compute is restrictive; the tools let YOU choose the window per query.

## Date convention — which date the PM means

When the PM names a date or date range, treat it as the **report day** — the row they saw on their dashboard. The cohort whose retention you are diagnosing arrived `N` days earlier (`N = 1` for D1, `7` for D7, `30` for D30).

| PM says | Row to read | Cohort day | What that number describes |
|---|---|---|---|
| "D1 on April 2" | April 2 | April 1 | April 1 install cohort returning April 2 |
| "D7 on April 16" | April 16 | April 9 | April 9 install cohort returning April 16 |
| "D30 on April 16" | April 16 | March 17 | March 17 install cohort returning April 16 |
| "D1 last week" | each row Apr 21–27 | Apr 20–26 | seven cohorts, one per row |

**Where each diagnostic step lives:**
- Stage-1 platform check → on the **report day** (Android vs iOS for the same metric).
- Stage-1 acquisition mix shift → on the **cohort day** (WTA / paid / others install volume).
- Stage-2 D0 signals (opt-in, login, uninstall, engagement) → all on the **cohort day**.
- Stage-3 hook / news → check both the **cohort day** (D0 news) and the **report day** (D1 news).

**Metric to cite in the headline**, in priority order:
1. `dx_corrected[cohort_day]` — install-aligned, clean attribution. Same number numerically as `dx[report_day]` but anchored to the cohort. Use this when filled in.
2. `dx[report_day]` — return-aligned. Fall back to this only when `dx_corrected[cohort_day]` is blank because the cohort is too recent.

**The single exception:** if the PM explicitly says "the install cohort on X" or "users who joined on X", flip — `cohort_day = X` and `report_day = X + N`.

## The three-stage retention framework

A failure at any stage kills D1. Diagnose in this order:

```
STAGE 1: ACQUISITION
  Who did we bring in, and with what promise?
                ↓
STAGE 2: D0 EXPERIENCE
  Did the app deliver in the first session?
                ↓
STAGE 3: HOOK TO RETURN
  Did we give them a reason to come back — and execute?
```

For the full methodology — news taxonomy, post-news dip pattern, causal chain, stable baseline rationale — load `docs/retention_methodology.md`.

## Thresholds

Comparison is always against the **7-day rolling average** ending the day BEFORE the date in question (not a long-term mean). Use `compare_to_baseline(..., baseline_kind="rolling7")` to get the delta.

| Δ vs 7-day avg | Direction | Action |
|---|---|---|
| < 2pp | Either | Report. No diagnostic. |
| 2–4pp | Drop | **Flag** — run the diagnostic checklist below. |
| > 4pp | Drop | **Alert** — full diagnosis, surface proactively. |
| 2–4pp | Rise | **Investigate** — what-worked analysis. |
| > 4pp | Rise | **Full** what-worked analysis, surface proactively. |

**Streak rule:** if D1 is consistently above or below the rolling avg for 2+ days — even if each daily delta is < 2pp — run the analysis. The streak is the signal.

**Oscillation rule:** if D1 alternates above and below the rolling avg over 3+ consecutive days without settling, flag it as instability — variance, not trend.

To get the list of flagged days, call `flag_dip_days(metric="d1", platform="android", acquisition_source="organic", days_back=N)` for the window the PM's query implies.

## D1 diagnostic checklist

Run in order when D1 has moved ≥2pp. Each step references the deterministic value the tool returns. Cite the most direct signal as the lead; lower-priority signals support, they do not headline.

For any flagged day, **call `compute_signals_for_day(date, platform, acquisition_source)` first** — it returns all 8 signals in one call. Read the dict, then walk through the steps.

### Stage 1 — Acquisition

**1. Platform check.**
Compare same-day D1 movement on Android vs iOS.
- Both drop → likely news cycle or external factor.
- Android drops, iOS stable or up → Android-specific.

The signal: `signals.platform_d1_delta_pp` (this segment) vs `signals.ios_d1_delta_pp` (iOS comparator).

**2. Acquisition mix shift.**
Did WTA, paid, or others volume spike on `d1_cohort_day` (= date − 1)?
WTA users are lower-intent. When WTA spikes, some installs get misattributed as organic, dragging apparent organic D1 down even if true organic quality is unchanged. Cite when the data shows a spike AND organic D1 softened — but keep it proportionate. If a more direct D0 signal is moving (steps 3–6), that leads.

**Call `compute_acquisition_mix_shift(date=d1_cohort_day, platform="android")`** to get the exact share deltas and install-volume ratios per source. Read `share_delta_pp` (in percentage points) and `installs_ratio_vs_baseline` (1.0 = flat) for `organic`, `paid`, `WTA`, `others`, plus `biggest_mover` for the lead. Do NOT load the full sheet to compute these by hand — the tool already does the math.

### Stage 2 — D0 Experience

**3. D0 notification opt-in rate.**
Most powerful leading indicator. No opt-in = no push reach on D1.
Signal: `signals.pct_d0_notification_opt_in_delta_pp` (evaluated on `d1_cohort_day`).

**4. D0 session quality.** *(approximate — see data gaps in `docs/data_dictionary.md`; engagement metrics are all-DAU, not new-install-cohort-specific.)*
Did `avg_engagement_time_per_user` drop on the cohort day?
Signal: `signals.avg_engagement_time_delta_pct`. Use directionally only.

**5. D0 login rate.**
Logged-in users get personalisation → stronger content match → higher return intent.
Signal: `signals.pct_d0_login_delta_pp`.

**6. D0 uninstall rate.**
High D0 uninstalls = bad first impression at scale. These users are in the denominator but had no real shot at D1.
Signal: `signals.d0_uninstall_rate_delta_pp` (Android only — iOS does not provide this signal).

### Stage 3 — Hook

**7. Notification hook.** *(data gap — D1 send rate and CTR are not in the sheet.)*
If steps 1–6 look clean and D1 still dropped, this is the most likely explanation. State it plainly.

### Context (not a standalone explanation)

**8. Day of week.**
Signal: `signals.weekday`. Note as context only if everything else looks stable.

## iOS as a diagnostic tool

iOS is **not** the headline metric — Android organic is. But iOS is the cleanest comparator when Android moves.
- Android drops + iOS drops → external or common cause.
- Android drops + iOS stable / up → Android-specific (product, infra, acquisition).

Report iOS only when it helps explain Android. Not as a separate line item.

## Loading context documents

After the diagnostic, decide whether external context could explain the verdict:

- News-driven? Load `docs/major_events.md` to check for high-significance events on `d1_cohort_day` or `date`.
- Holiday-driven? Load `docs/india_holidays.md`.
- Infra outage? Load `docs/known_incidents.md`.
- Recent product change? Load `docs/product_release_log.md`.
- Paid burst? Load `docs/acquisition_campaigns.md`.

Use `list_files()` if you want to see the menu with descriptions.

## Report shape

Two-part structure. The top is a **fixed status card** so the PM can scan the verdict in 5 seconds. The bottom is the free-form diagnosis. Diagnosis-first — never walk through all the data and land on a conclusion at the end.

### Part 1 — Status card (always emit, exact shape)

Open the report with a one-line severity banner, then a 6-row table. Every report uses these exact field names so two reports can be diff-ed week over week.

```
🔴 ALERT · <one-line title summarising the move>

| Field             | Value                                                                     |
|-------------------|---------------------------------------------------------------------------|
| Cohort / segment  | <YYYY-MM-DD install cohort> · <platform> · <acquisition_source>           |
| Headline          | <metric> = <value%> (raw d1 on <report date> = <value%>)                  |
| vs 7-day rolling  | <±X.XXpp> / <±X.X% relative> (rolling avg <value%>)                       |
| vs stable basel.  | <±X.XXpp> (<weekday> baseline <value%>, IQR-clean, n=<count>)             |
| Primary driver    | <one-line cause cite> (Stage <1|2|3>)                                     |
| iOS comparator    | iOS <metric> <±X.XXpp> → <Android-specific | external/news | inconclusive>|
```

**Severity badge rules** (first cell of the banner — pick exactly one):

| Badge | When |
|---|---|
| 🔴 ALERT | Δ ≤ −4pp vs 7-day rolling |
| 🟡 FLAG | Δ between −2pp and −4pp |
| 🟢 NORMAL | Δ within ±2pp |
| 🟡 RISE FLAG | Δ between +2pp and +4pp |
| 🟢 RISE ALERT | Δ ≥ +4pp (still surface — what worked is worth knowing) |

**Card field discipline:**
- Every numeric value must come from a tool return, not your own arithmetic.
- If a field is genuinely unknown or not yet computable (e.g., stable baseline when `compute_stable_baseline` returned an error), write `n/a — <reason>` rather than omitting the row.
- Keep the card to exactly these 6 rows. Do not add rows. The whole point is consistency across runs.

### Part 2 — Diagnosis (free-form)

Below the card, write the four sections in order:

1. **Diagnosis** — verdict in one or two sentences. Name the most likely driver. No restating the headline number.
2. **Evidence** — only the numbers that support the diagnosis, stage-ordered. Cite by tool-returned values. No narration.
3. **Stable signals** — one line each, or skip. What did NOT move that might have.
4. **What to watch next** — one or two lines. Specific. No restating.

For a D1 rise, also close with: **is this repeatable?** News-driven → no, will normalise. Mix improvement → maybe, if held. D0 activation improvement → yes, if a product change drove it (name it). Unknown → say so.

## Hard rules (recap from system preamble)

- **No pattern claims without data.** "Typically", "usually", "tends to" are banned without verifying against this run's data. Priors from training data are not findings.
- **No multi-day pattern claims without a tool call.** Any phrase like "structural decline", "step-down", "recovered", "multi-week trend", "isolated event", "continuing problem" must be backed by a value returned from `compute_rolling_average`, `compare_to_baseline`, or `flag_dip_days`. Do not eyeball the inlined slice and assert a trend. If you want to claim "opt-in is structurally lower since April 1", call the tool for the late-March mean and the late-April mean and cite both numbers.
- **One cohort per verdict.** When you cite a D0 signal, name the cohort day explicitly (e.g., "April 1 cohort, opt-in down 4.4pp"). Do not mix cohort days inside the same diagnosis. If you want to argue "the dip was isolated", do it by showing the **same metric on the same cohort indexing** the next day or the next several days — not by jumping to a different cohort's signals.
- **Stage-ordered diagnosis.** The most direct signal leads.
- **No metric definitions in the headline report** — assume the PM knows what `d1`, `pct_d0_notification_opt_in`, etc. mean.
