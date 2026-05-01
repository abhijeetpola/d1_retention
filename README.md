# PM Tuning Sandbox — D1 Retention Analysis

> **PMs — start with [`PM_QUICKSTART.md`](PM_QUICKSTART.md). Engineers — read on.**

A small project that lets the product team tune the LLM analysis for D1 retention without writing any code.

You edit one Markdown file. You run one command. You read the report.

That's it.

---

## What's in this folder

| File / folder | What it is |
|---|---|
| `d1-retention-analysis.md` | **The one file you edit.** It contains the hypothesis, instructions for the LLM, and the report shape you want. |
| `data/sheets/app_health_daily.csv` | The primary daily retention dataset. The first `./tune` run on or after 11:00 AM IST each day refreshes this and three pivot sheets automatically — you do not edit any of them. |
| `data/docs/` | **Drop any extra context here.** Causal docs, release notes, data dictionaries — anything you'd like the LLM to optionally read when needed. |
| `outputs/` | Where the generated report lands after each run. |
| `tune` | The one command you run. |
| `tune_mcp.py`, `config.yaml`, `pyproject.toml` | Engineer-managed plumbing. You don't need to touch these. |

---

## One-time setup

```bash
# Install dependencies
uv sync

# Make sure Claude CLI is logged in
claude --version
# (if not installed, get it from https://claude.com/code)

# Sanity check
./tune doctor
```

If `./tune doctor` says everything is fine, you're ready.

---

## The tuning loop

```
1. Open d1-retention-analysis.md in any text editor (VS Code, TextEdit,
   Cursor, vim — anything you like).

2. Edit the prose. Common tuning moves:
   - Sharpen a hypothesis
   - Change the steps you want the LLM to take
   - Adjust the "Report shape" section to ask for different sections
   - Add or remove caveats / instructions

3. ⌘S to save.

4. Switch to Terminal in this folder and run either:
        ./tune
   or with a one-shot question on top:
        ./tune "Why did D1 dip on March 8?"

5. The script:
   - reads your prose
   - reads the data
   - calls Claude (you'll see a spinner with elapsed time ticking up)
   - renders the final report inline in your Terminal
   - writes the report into outputs/<today>-d1-retention-analysis.md
   - auto-opens it in your default Markdown viewer

6. Read the report. Decide what's still vague, what you'd want pivoted,
   what new hypothesis to test. Edit the prose again. Repeat.
```

### A worked first edit

What "tune the prose" looks like in practice. Open `d1-retention-analysis.md`,
find Stage 2 (D0 Experience). The default prose treats opt-in, login,
engagement, and uninstall as four equal signals. Suppose you want the LLM
to lead with opt-in when it moves at all. You change one bullet:

```
Before:  **3. D0 notification opt-in rate.**
         Most powerful leading indicator. No opt-in = no push reach on D1.

After:   **3. D0 notification opt-in rate.** *(the lead Stage-2 signal)*
         If `signals.pct_d0_notification_opt_in_delta_pp` moves more than
         1pp on the cohort day, this is your headline driver — say so in
         the Diagnosis. Other Stage-2 signals are supporting evidence.
```

Save. Run `./tune "Why did D1 dip on April 27?"`. Compare the new report's
Diagnosis line to the old one — you should see opt-in named first instead
of buried as one of four bullets. That single edit + run is the loop.

Each run typically takes 2–5 minutes. Cost is around $0.30–$1.50 (charged
to your Claude subscription, not to a separate API budget). If a run takes
much longer or costs much more, the LLM is probably re-loading the full sheet
unnecessarily — see the troubleshooting section.

---

## Daily sheet refresh

The project reads from a Google Sheets workbook with multiple tabs (the primary
daily fact table plus three D1 cohort pivots — daily, weekly, monthly). Tabs
are listed in `data/sheets/_registry.yaml` along with their freshness rule.

**Refresh schedule.** The first `./tune` run on or after 11:00 AM IST each day
downloads any registered tab whose cache is older than today's threshold.
Same-day later runs read from the local cache silently. The first refresh of
the day shows one line per sheet:

```
Refreshing sheets (daily threshold)
  ✓ app_health_daily (1494 KB · no-change · content identical to cached copy)
  ✓ app_d1_retention_health_daily (17 KB · fetched · updated)
  ✓ app_d1_retention_health_weekly (26 KB · fetched · updated)
  ✓ app_d1_retention_health_monthly (1 KB · no-change · content identical to cached copy)
  Done in 2.1s · 4 sheet(s) refreshed.
```

**Need fresh data mid-day?** Run `./tune --refresh "..."`. This bypasses the
schedule and re-downloads every registered sheet before the run. Use when you
know the source workbook just updated and you want this run to reflect it.

**Network failure handling.** If a sheet cannot be fetched (network down,
Google rate-limiting, etc.) the run continues with the cached copy and prints
a warning line. The cached file is never overwritten with garbage.

**Adding a new sheet.** Append a stanza to `data/sheets/_registry.yaml` with
the tab's `gid`, write a column dictionary at `data/dict/<sheet_name>.md`
modelled on the existing ones, and the next run picks it up.

---

## What you can ask the LLM to do in the prose

In your `d1-retention-analysis.md`:

- **Refer to columns by name** — e.g., "compare `d1` against `d1_corrected`",
  "look at `pct_dau_via_notifications` on dip days"
- **Ask it to load extra files** — e.g., "if you want context on what changed,
  call `load_file('docs/known_incidents.md')`"
- **Ask it to query a different segment** — every retention number is fetched
  through `get_rows(platform, acquisition_source, date_from, date_to)` or a
  `compute_*` tool at run time. There is no inlined data table. To diagnose
  a non-Android-organic segment, prose-instruct: "if the PM is asking about
  iOS or paid acquisition, call `get_rows(platform='ios', ...)` and run the
  same diagnostic checklist." For full historical breakdowns the LLM can
  fall back to `load_file('sheets/app_health_daily.csv')`.

The LLM also has `list_docs()` available — it lists the methodology and
event-context documents in `data/docs/` so it can pick which ones to load.

### How to write a tool call in your prose

The LLM picks up a tool reference when you write it as a function-call signature wrapped in backticks. Three rules:

1. **Wrap the call in backticks** so the LLM sees it as a tool, not commentary. `compute_signals_for_day(date="2026-04-02", platform="android", acquisition_source="organic")` reads as "call this." Plain-text descriptions like "we could compute the signals for that day" do not — the LLM treats them as suggestions, not instructions.

2. **Use imperative voice.** "Call `compute_X(...)` to get Y" or "**Call** `compute_X(...)` first" lands as an instruction. Conditional or hedging language ("you might call X if you want") lands as optional. If a step in the diagnostic should always run, write it as a command.

3. **Use named placeholders for values that depend on the run.** Where the value comes from the PM's query at run time, write a placeholder instead of a literal: `compute_signals_for_day(date=d1_cohort_day, platform="android", acquisition_source="organic")`. The LLM resolves `d1_cohort_day` against the date convention defined near the top of the playbook. The same goes for `<segment.platform>` and `<segment.source>` if you want the call to follow whatever segment the PM is asking about.

Place the call where in the flow you want it to fire. A line in Stage 1 fires before Stage 2 numbers. A line in "Report shape" fires only when the LLM is building the card. The LLM follows the structure of your prose.

### Where to find the full tool list

`primitives.md` is the source of truth — auto-generated from the registered MCP tools, one card per tool with parameters, defaults, return shape, and a copy-pasteable worked example. Ten tools today: two for files (`list_docs`, `load_file`), two for sheets (`list_sheets`, `get_rows`), and six for deterministic math (`compute_rolling_average`, `compute_stable_baseline`, `compare_to_baseline`, `flag_dip_days`, `compute_signals_for_day`, `compute_acquisition_mix_shift`). Defaults match the PM methodology (2pp = flag, 4pp = alert, baseline starts 2026-01-01) but every parameter is exposed — you can override any of them from the playbook prose.

---

## How to add an extra context document

Just drop the file into `data/docs/`:

```bash
cp ~/Documents/our-causal-doc.md data/docs/causal_doc.md
```

Then mention it in your playbook prose:

```markdown
If you want my mental model of how product changes flow into retention,
call `load_file('docs/causal_doc.md')` before forming verdicts.
```

The LLM will load it mid-reasoning when the playbook asks.

---

## Authoring playbook calculations (the PM loop)

There are two flavours of authoring. The first — wiring up existing tools in your playbook — is what you'll do every day. The second — adding a new tool when none exists — is rarer but well within reach if you can read Python at a surface level.

### Using an existing tool in your playbook

Every calculation the LLM makes flows through one of the tools listed in `primitives.md`. Each card has a copy-pasteable worked example. The loop:

1. Open `primitives.md` and find a card whose worked example matches what
   you want to compute. Copy the example.
2. Paste the example into `d1-retention-analysis.md` at the step where it
   should fire, and edit the parameter values for your case. Use the prose
   convention from the section above (backticks, imperative voice, named
   placeholders).
3. Run `./tune --verify` to confirm every tool call in the playbook resolves.
   The verifier exits in under a second and costs nothing — no LLM is
   invoked. If you have a typo it tells you the line number and suggests
   the closest valid name.
4. Run `./tune --dry-run "..."` to inspect the prompt that would go to the
   LLM. Still no LLM call.
5. Run `./tune "..."` for the real analysis.

### Adding a new tool when no existing one fits

Sometimes you need a calculation no existing tool covers. You have two paths.

**If you can read Python at a surface level, author the tool yourself.** The template at `tools/_TEMPLATE.py` is heavily annotated; you copy it, edit a handful of marked lines, save. The aggregator picks the new file up automatically — there is no separate registration step. You do not write any pandas; the helpers in `tools/_common.py` (`get_rows`, `aggregate`, `cohort_rate`, `delta_pp`, `filter_window`) cover the math.

**If you'd rather hand it off to an engineer**, fill out `request.md` at the project root with the suggested name, a plain-English description, the inputs, and the expected output. Hand the file over. The engineer adds the tool, the catalog regenerates, and you reference it from the playbook like any other.

#### Worked end-to-end example

Suppose you want a Stage-0 sanity check: the ratio of new installs to DAU on a date. High ratio means the install pipeline is replenishing the base; low ratio means churn is winning. There's no existing tool for it. Here is the full path from "I want this" to "the LLM is calling it."

**Step 1 — copy the template:**

```bash
cp tools/_TEMPLATE.py tools/compute_install_to_dau_ratio.py
```

**Step 2 — open the new file and edit the marked lines.** Trimmed of template comments, the file ends up looking like:

```python
from __future__ import annotations
from typing import Any
from tools._common import (aggregate, get_rows, server, validate_segment)

@server.tool(
    description=(
        "Compute the ratio of installs to DAU for one date and segment. "
        "High ratio = installs are growing the base; low ratio = the active "
        "base is shrinking. Useful as a Stage-0 sanity check before D1 "
        "diagnosis. "
        "Parameters: "
        "  date — YYYY-MM-DD. "
        "  platform — 'android' or 'ios'. "
        "  acquisition_source — 'organic' / 'paid' / 'WTA' / 'others' / 'All'. "
        "Returns {ok, date, platform, acquisition_source, installs, dau, ratio}."
    )
)
def compute_install_to_dau_ratio(
    date: str,
    platform: str,
    acquisition_source: str,
) -> dict[str, Any]:
    err = validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}
    rows = get_rows(
        platform=platform,
        acquisition_source=acquisition_source,
        date_from=date,
        date_to=date,
    )
    installs = aggregate(rows, "installs", "sum")
    dau = aggregate(rows, "dau", "sum")
    if not installs or not dau:
        return {"ok": False, "error": f"missing values on {date}"}
    return {
        "ok": True,
        "date": date,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "installs": int(installs),
        "dau": int(dau),
        "ratio": round(installs / dau, 4),
    }
```

Save.

**Step 3 — confirm it registered:**

```bash
./tune --verify
```

You should see "10 tool(s) registered" (was 9). If anything is wrong — bad import, syntax error — the verifier prints the file and the line. Sub-second; no LLM call.

**Step 4 — regenerate the catalog:**

```bash
uv run python generate_catalog.py
```

`primitives.md` now has a new card for `compute_install_to_dau_ratio` with the parameter table and a worked example, generated automatically from the description string.

**Step 5 — reference it from the playbook.** Open `d1-retention-analysis.md` and add a paragraph at the spot in the diagnostic where the call should fire — for this example, right before Stage 1:

```markdown
**Stage 0 — Acquisition velocity check.**
Before walking the diagnostic, get a read on whether the segment is growing
or shrinking on the cohort day:

Call `compute_install_to_dau_ratio(date=d1_cohort_day, platform="android",
acquisition_source="organic")`.

If `ratio < 0.05`, the cohort is small relative to the active base — D1 is
noisy. Note this in the report and lower confidence on borderline verdicts.
```

**Step 6 — run.** `./tune --verify` confirms the new playbook line resolves. `./tune "Why did D1 dip on April 27?"` runs the analysis. The LLM calls your new tool at the spot you specified, and the result flows into the diagnosis.

That is the full loop. Most new tools are 30–50 lines after the template comments are trimmed, and the verify-then-catalog cycle catches mistakes before any paid LLM run.

---

## Comparing two runs

Each run lands in a dated file under `outputs/`. The most recent always has a
sibling symlink at `outputs/latest.md`.

To see how a prose change affected the analysis:

```bash
diff outputs/2026-04-28-d1-retention-analysis.md outputs/2026-04-29-d1-retention-analysis.md
```

Or use VS Code's Source Control panel to see line-level diffs visually.

---

## Quick reference

| Command | What it does |
|---|---|
| `./tune` | Run the analysis end-to-end using just the playbook prose. |
| `./tune "Why did D1 dip on March 8?"` | Run end-to-end AND add a one-shot question for this specific run. The question is appended to the prompt with a "PM's specific question for THIS run" header — Claude treats it as the primary lens for the TL;DR and verdicts. |
| `./tune doctor` | Sanity-check the environment (claude installed, files in place). |
| `./tune --dry-run` | Show the prompt that would be sent. Don't call Claude. Useful for sanity checks while you tune the prose. |
| `./tune --dry-run "your question"` | Same, with the inline question included. Confirm the prompt looks right before paying for a real run. |
| `./tune --quiet` | Skip the inline report rendering in the terminal (only write the file). |
| `./tune --no-open` | Don't auto-open the report in your default Markdown viewer (only print inline + write file). |
| `./tune --refresh` | Force-refresh every registered sheet from Google before this run, ignoring the daily 11:00 AM IST schedule. Use when the source updated mid-day and you want this run to use the latest. |

### When you run `./tune`, the report is rendered in the Terminal AND written to a file

After Claude finishes:

1. The report is **rendered inline** in your Terminal using Markdown formatting (headings, tables, bullets) — you can scroll up and read it without leaving the Terminal.
2. The file `outputs/<date>-d1-retention-analysis.md` is written to disk.
3. `outputs/latest.md` (a symlink) is updated to point at the latest run.
4. Your default Markdown viewer auto-opens the file (suppress with `--no-open`).

### Two ways to use the inline-question feature

**As a quick one-off question** without changing the playbook:

```bash
./tune "Compare last week's D1 to the prior week. Where did the gap widen?"
```

This is great for "I just want to ask one thing on top of the standard analysis."

**As a tuning lever** alongside playbook edits:

```bash
$EDITOR d1-retention-analysis.md            # tune the structural prose
./tune "specifically focus on iOS deeplink share"   # add a per-run focus
```

The playbook prose is for stable, structural framing. The inline question is for ad-hoc focus on a single run. Both go into the same prompt; the inline question is highlighted to the LLM as "the primary lens for THIS run."

---

## When something doesn't look right

- **The report says "I cannot determine ..."** → the prose probably gave Claude too little to work with, OR the LLM did not pull the right segment. Try `./tune --dry-run` to see exactly what prompt is being sent, then sharpen the prose.
- **Claude says "file not found"** → call `list_docs()` from inside the playbook prose: tell the LLM to start with `list_docs()` to see which context docs are available.
- **Cost is higher than expected** → you're probably making Claude load the full CSV when it doesn't need it. Tune the prose so it only calls `load_file('sheets/app_health_daily.csv')` when the existing `get_rows` calls are truly insufficient.
- **`./tune` errors out with "claude not found"** → run `claude --version` to confirm the CLI is installed and logged in.

If something is genuinely broken, talk to the engineer. The plumbing
(`tune`, `tune_mcp.py`, `config.yaml`) is theirs.
