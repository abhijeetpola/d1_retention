<!-- desc: Indian public holidays in the data window — explains expected D1 dips on family-festival days -->
# Indian public holidays — Aug 2025 to Apr 2026

This file lists the major public holidays in India that fall inside the
window of `sheets/d1_retention.csv` (data starts 2025-05-01). Use it when
interpreting D1 dips that fall on or near these dates — holidays often:

- Compress news consumption: people are home with family, attention is on
  TV / WhatsApp / live streams instead of news apps.
- Shift the install mix: festival-driven traffic skews toward casual users
  who don't return.
- Drive lighter push engagement: editorial teams send fewer alerts; users
  open fewer.

A D1 dip on a holiday date is usually expected, not a regression.

## Confident dates (fixed every year)

| Date | Holiday | Region | Typical retention effect |
|---|---|---|---|
| 2025-08-15 | Independence Day | All India | High DAU spike (news interest), D1 typically dips next day from one-time visitors |
| 2025-10-02 | Gandhi Jayanti | All India | Light news day; DAU softer |
| 2025-12-25 | Christmas | All India (Christian-heavy in Kerala, Goa, NE) | Light news day |
| 2026-01-01 | New Year's Day | All India | High DAU, low D1 (one-time visitors arrive for year-end coverage) |
| 2026-01-14 | Makar Sankranti / Pongal | Mostly South & West | Regional engagement shift |
| 2026-01-26 | Republic Day | All India | High news interest, similar pattern to Independence Day |

## Approximate dates (movable feasts — PM verify if a flagged dip lands on or near these)

| Date (approx) | Holiday | Notes |
|---|---|---|
| 2025-08-27 | Ganesh Chaturthi (start) | Maharashtra-heavy; ~10-day festival, peaks on day 10 |
| 2025-09-05 | Onam | Kerala |
| 2025-10-02 | Dussehra (Vijayadashami) | All India; date can be Sep 30–Oct 3 depending on year |
| 2025-10-20 | Diwali | All India; typically 4–5 day window of low engagement |
| 2025-10-22 | Govardhan Puja | North India |
| 2025-10-23 | Bhai Dooj | North India |
| 2025-11-05 | Guru Nanak Jayanti | Punjab-heavy |
| 2026-03-04 | Holi | All India; engagement very soft this day |
| 2026-03-29 | Eid al-Fitr | All India; depends on moon sighting |

**Approximate** = the date may be off by 1–2 days. Cross-check before citing
in a verdict.

## How to use this file

If a flagged dip date matches a row above, mention the holiday in the
"Caveats" section of the report and discount the dip from any structural
verdict. If the dip is *much* larger than what holidays usually cause
(say D1 down 30%+ vs trailing mean), call it out as still notable.
