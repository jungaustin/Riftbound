# Per-Domain card inclusion rates (staples)

Rescued from `riftbound-handoff/` on 2026-08-03, which is now safe to delete. Verified working from this location (`parse_staples.py --selftest` and `--coverage` both pass here).

**What this answers:** for each of the six Domains, how often each card actually appears in decks of that Domain — inclusion %, average copies, and card type.

## Files

| File | What it is |
|---|---|
| `inclusion_all_types.csv` | **The primary artifact.** 100 rows, all card types, ≥20% inclusion. |
| `inclusion_vendetta.csv` | Same data filtered to Spells only (48 rows). |
| `all-cards-by-domain-vendetta.md` | Human-readable version of the above, grouped by Domain. |
| `spells-by-domain-vendetta.md` | Spells-only, human-readable. |
| `FINDINGS-2026-08-03.md` | **Read this before trusting a number.** Contains the metric correction below. |
| `METHODOLOGY.md` | Denominator definition, aggregation math, type filter, format decision. |
| `parse_staples.py` | Regenerates the CSVs from `html/`. `--selftest`, `--coverage`, `--threshold`. |
| `html/` | The 10 manually-saved riftdecks `/staples` pages. **Local-only (gitignored).** **The only source** — see the re-fetch warning. |
| `legacy/` | Per-Legend Unleashed-era data from the abandoned first approach. Not used by anything here. |

## The one thing you must know before using these numbers

riftdecks' raw "Popularity" figure uses **one global denominator shared across all six Domains** — the most-played card in the entire meta (Calm Rune) is pinned at 100%. That is structurally the same error the whole exercise exists to avoid: it measures *how much of the meta is Domain D*, not *how often D's decks run this card*. Fury Rune tops out at 46.26%, not 100%.

**The correction, already applied in these CSVs:**

```
inclusion(X, D) = popularity(X) / popularity(D_Rune)
```

Every deck of Domain D runs D Runes and no deck outside D legally may, so the Rune's popularity *is* D's share of the benchmark — dividing cancels the global denominator. Measured divisors: Calm 100 · Chaos 95.11 · Mind 79.57 · Body 76.11 · Order 62.24 · Fury 46.26.

Cross-checked two independent ways: Defy comes out 99.5% for Calm both here and via the per-Legend route in `legacy/`.

The `raw_popularity_pct` column is the uncorrected site figure — **do not use it directly.**

## Caveats

- **Current format only.** `/staples` is a rolling 30-day window, so this describes Vendetta and nothing else. There is no route to historical formats from these files.
- **Dual-Domain cards** need the *intersection* of two Domains as a denominator, which no single Rune supplies. Not normalised here; treat separately.
- **Colorless cards** have no Rune and are legal anywhere — excluded by design (METHODOLOGY §6).
- **Mild over-estimate.** A deck could hold D in identity and run zero D Runes. Rare, but it shrinks the denominator.
- **Small sample.** Vendetta is young; the top Legend had ~41 decks at capture. One deck moves a rate by ~2.4 points. Treat 20-25% as "shows up sometimes," not as a finding.
- **Names match this repo's card database**, verified 100/100 against `data/cards.json` (only casing differs on `Ride The Wind`).

## Re-fetching (read before trying)

riftdecks sits behind a **standing Cloudflare challenge** — every plain request returns 403 `cf-mitigated: challenge`, regardless of User-Agent. Retrying does not help. A real headful browser gets through and banks a `cf_clearance` cookie, but re-challenges after a handful of navigations, so bulk scraping is not viable. **The pages in `html/` were captured by hand and are effectively irreplaceable — do not delete them.**

To refresh: manually save `https://riftdecks.com/staples` filtered per Domain into `html/`, then run `python3 parse_staples.py`. The `--coverage` flag proves whether each Domain's saved pages reach deep enough to be complete at your threshold.

Real URL shape for per-Legend pages, if the `legacy/` route is ever resumed: `https://riftdecks.com/legends/constructed/{slug}?metagame_id={N}` where 4 = Vendetta, 3 = Unleashed, 2 = Spiritforged.

## What was discarded from the handoff package, and why

- `README.md` (old) — superseded on four points by `FINDINGS`; keeping both invites reading the wrong one. Its useful content is folded into this file and `METHODOLOGY.md`.
- `scripts/fetch_legend_stats.py` — parser is unfixable by regex tweak. Card names live in `<img alt>` / the row href, not the row text, so any text regex is off by one across the whole table. Never needed for this answer.
- `scripts/aggregate.py` — per-Legend route; produces actively wrong numbers when fed truncated tables.
- `presence_master-yi-*.csv`, `presence_reksai-*.csv` — flagged unverified and truncated. These were the documented trap: `aggregate.py` reads a missing card as 0%, which dragged Ride the Wind to a bogus 50.6% for Calm.
- `card_types.csv` — 136 of 137 entries unverified guesses; `parse_staples.py` reads real types and slugs off the page tiles instead.
- `sources/urls.md` — URL pattern documented as wrong.
- `report/research-report.md`, `reply.txt`, `requirements.txt` (two pip lines), `__pycache__`.
- Ten duplicate `.html` files at the repo root — byte-identical to `html/`, verified with `cmp`.
