# Request — new MCP tool

Use this template when you want a calculation that no existing tool covers,
and the helpers in `tools/_common.py` aren't enough either. Fill in each
section, save as a new file (e.g. `requests/2026-04-29-funnel-conversion.md`),
and hand it to the engineer. They'll implement the new tool, the catalog
will pick it up automatically, and you can reference it from the playbook.

If you only need to *combine* existing tools, you don't need this — just
compose them in the playbook prose using cards from `primitives.md`.

---

## What I want to call the tool

Suggested name (lower_snake_case verb phrase, e.g. `compute_funnel_conversion`):

> _your suggestion here_

## What it should compute, in plain English

Two or three sentences. Pretend you're explaining the calculation to a new
teammate. Say what it returns, not how to implement it.

> _your description here_

## Inputs

What does the calculation need to be told? List every input by name with
the type and an example.

| Name | Type | Example | What it means |
|---|---|---|---|
| `date` | string | `"2026-04-15"` | _your explanation_ |
| `platform` | string | `"android"` | _your explanation_ |
| _add more rows_ | | | |

## Output

What comes back? Either a single number, a list, or a structured dict.
Show what a result would look like.

> _example output here_

## Where this fits in the playbook

Which step of the diagnostic checklist does this support? Or is it a new
step? Quote the playbook line(s) you'd modify or add.

> _your context here_

## Why this matters

Two sentences on the diagnostic value. What question does this help answer
that the existing tools can't?

> _your justification here_

## Special considerations (optional)

Anything subtle the engineer should know — e.g. methodology rules
("use cohort-aggregated rate, not mean of daily rates"), known data gaps,
edge cases to handle (zero-volume cohorts), or relevant context docs.

> _optional notes_
