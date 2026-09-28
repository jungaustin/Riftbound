# Training run log

See `BACKLOG.md` for what is queued. Append a row per run. A checkpoint without its engine commit is unreproducible,
which is why `ck["engine"]` exists — a `-dirty` suffix means uncommitted changes,
so the exact engine is only recoverable from the run directory.

All numbers are 100 deals x 2 seats, paired and seat-swapped, against fixed
external opponents. **Self-play win rate is not in this table because it is ~50%
by construction and measures nothing.**

---

## Summary

| run | victory | decks | iters | best vs random | best vs greedy | notes |
|---|---|---|---|---|---|---|
| Phase 4 | 3 | procedural (`v1_deal`) | 150 | 93.1% | **69.0%** | pre-deck-conditioning; not comparable to real decks |
| `v3-deckcond` | 3 | 30 real | 150 | 81.5% | **54.5%** @ iter 80 | first real-deck run; deck + champion zones |
| `v4-standing` | 3 | 30 real | 150 | 81.0% | **50.5%** @ iter 140 | + 51 standing-state globals, turns-to-win |
| `v5-warm` | 5 | 30 real | 150 | 79.0% | **54.5%** @ iter 110 | warm-started from v4 `best.pt`; **best so far**, barely drifted. Peak `vs_greedy` was 55.5% at a later eval, but `best.pt` is chosen on `vs_random + vs_greedy` and ties go to the earlier checkpoint |

The 65% exit bar in `ppo.py` was calibrated against `v1_deal`'s procedural decks.
The real-deck distribution is far harder and more diverse; **Phase 4's 69% and
v3's 54.5% are not comparable numbers.**

---

## Self-play drift — measured twice

| run | best | last | drop | pool |
|---|---|---|---|---|
| Phase 4 | 69.0% (iter 100) | 60.2% (iter 150) | **8.8 pts** | off |
| `v3-deckcond` | 54.5% (iter 80) | 47.0% (iter 150) | **7.5 pts** | **on**, `pool_frac=0.5` |
| `v5-warm` | 55.5% (peak eval) | 54.5% (iter 150) | **1.0 pt** | **on**, `pool_frac=0.5` |

`v5-warm` barely drifted. Two plausible reasons, not yet separated: the longer
victory-5 games give more signal per episode, and it started from a competent
warm-start rather than from noise, so it spent no iterations flailing. Worth
re-testing at victory 8 before treating it as solved.

Late training made the policy measurably **worse against a fixed opponent** while
`vs_random` stayed flat, with non-overlapping intervals. The PFSP opponent pool
did **not** prevent it: the pool is one lineage of past selves, not a population,
so every entry shares the same blind spots.

Two practical consequences:

- **Always use `best.pt`, not `last.pt`.**
- Picking "best" by periodic eval is itself mild overfitting to the eval set. The
  honest headline is the best number, but it is not a stable capability until
  an exploitability probe exists.

---

## v4 per-deck breakdown (vs greedy, 12 deals x 2 seats x 30 decks)

**A 75-point spread, well beyond the noise.** The generalist is *not* uniformly
competent, which is the empirical answer to "should I train specialists": yes for
a handful of weak decks, warm-started — not thirty separate agents.

| worst | | best | |
|---|---|---|---|
| `meta/ven-1-azir-calm-order` | **4.2%** ±8.0 | `meta/reksai-fury-order` | **79.2%** ±16.2 |
| `meta/sivir-body-chaos` | 8.3% ±11.1 | `meta/darius-fury-order` | 79.2% ±16.2 |
| `meta/lillia-sprite-tempo-netdeck` | 20.8% ±16.2 | `meta/annie-chaos-fury` | 79.2% ±16.2 |
| `meta/lillia-galewinds-unleashed` | 25.0% ±17.3 | `empower-chaos/body-chaos-v1` | 70.8% ±18.2 |
| `meta/lux-mind-order` | 29.2% ±18.2 | `meta/ven-3-masteryi-body-calm` | 66.7% ±18.9 |

Median around 50%. Full table in `rl/runs/v4-standing/train.log`.

**v5 reproduced the spread** (70.8%, noise ±27.3%) with almost the same decks at
each end -- `sivir-body-chaos` and `ven-1-azir-calm-order` worst at 8.3%,
`darius-fury-order` and `annie-chaos-fury` best at 79.2%. Two independent runs
agreeing on *which* decks are badly served is much stronger evidence than one
run's spread, and it makes the deck-strength confound (caveat 1) the next thing
to rule out.

**Two caveats before acting on this.**

1. **It conflates agent weakness with deck strength.** "Bad with Azir" and "Azir
   is bad against the field" produce the same number. Separating them needs
   greedy piloting each deck as a per-deck baseline. Not yet run.
2. **n=24 per deck**, so ±8–20% each. The *spread* is real; individual rankings
   are not. Do not read the ordering as meaningful.

Checked and ruled out: all five worst decks are at **100% main-deck coverage**, so
this is not a scripting gap.

---

## Reproducing a run

```bash
cat rl/runs/<name>/PROVENANCE.txt     # engine commit, date, dirty state
git apply rl/runs/<name>/engine.patch # when the tree was dirty
head -3 rl/runs/<name>/train.log      # the exact config line
```

`train.log` holds every iteration line and eval, so the trend can be re-read
without rerunning anything.
