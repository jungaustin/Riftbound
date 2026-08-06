# Lillia — Fae Fawn (Sprite Tempo)

**Legend:** Lillia - Bashful Bloom · **Champion:** Lillia - Fae Fawn · **Identity:** Calm+Mind

**The plan in one sentence:** make disposable 3-Might Sprites faster than the
opponent can profitably answer them, convert them into points by *conquering*
(not holding), and close with a body big enough to take the last point.

**Current version: `v7.txt`** — validated `LEGAL`, no `critique` flags.

## Files

| File | What it is |
|---|---|
| `v1.txt` … `v7.txt` | Decklists. Every one has been through `cli.py check`. |
| `playstyle.md` | Piloting guide — mulligan, early/mid/late, showdown priority. |
| `patterns.md` | Verified rulings and sequencing rules the deck depends on. |
| `ratings.md` | **Not yet generated.** The full 1-100 pool evaluation (see skill step 3). |

Version numbering has a gap — v2-v5 were deleted outside the build session.
Numbers are kept as-is so the surrounding notes still line up.

## Version history

| Ver | Change | Why |
|---|---|---|
| v1 | Original build | Sprite tempo, no top end. |
| v2 | +2 Thousand-Tailed Watcher, +2 Sprite Burst, LeBlanc 2→3; −2 Watchful Sentry, −2 Soul Shepherd, −1 Discipline. Back-Alley Bar → Sandswept Tomb | Playtest: no late-game threats, couldn't close. |
| v3 | Ahri - Alluring ×3 over Sprite Burst; runes 8/4; Grove of the God-Willow | Alternative: win by **Hold** rather than double-conquer. Ahri is a **PR promo** — check availability. |
| v4 | +2 Lillia - Protector of Dreams, LeBlanc 3→2 | Protector's Tank grant has no location clause, so she works from base. |
| v5 | LeBlanc cut entirely, Protector →3, Stupefy →3 | LeBlanc is a *mode switch*, not an engine — see `patterns.md`. |
| v6 | Sprite Mother ×3 → Trevor Snoozebottom ×3 | Sprite Mother is a 5-cost card (E4 **+P1**) for a 3-Might exhausted body. Trevor does the same job for 3, with no Power, and repeats. |
| v7 | Hall of Legends → Dusk Rose Lab, Sandswept Tomb → Black Flame Altar | Sandswept Tomb was a misread and is near-dead here. Hall of Legends rewards conquering, and v6 holds. |

## Known open questions

- **Curve is top-heavy.** No 4-cost units at all — the unit curve is 2 → 3 → 5 → 7.
  If turn 4 keeps feeling dead, LeBlanc at 2 is the natural filler, and she now
  has a home since Trevor holds ground reliably.
- **16 copies at cost 3.** Lumpy; some hands can't deploy two 3-drops until turn 4.
- **Vendetta (VEN) not evaluated in the list.** Sona - Harmonious, Iterative
  Design, Ahri - Inquisitive and Wraith of Echoes all looked live and none made
  it in. Worth a pass.
