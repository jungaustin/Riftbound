# The victory-8 run — setup, and why the numbers are what they are

Everything here is measured on this engine at `64395ee`, not carried over from
the victory-5 runs. Victory 8 is the real game (194.3); every run before it was
curriculum.

## Launch

```sh
python3 -m rl.ppo 500 --victory 8 --spells --real-decks \
    --holdout 7 --envs 64 --rollout 12288 \
    --eval-every 20 --eval-games 100 --per-deck 40 \
    --out rl/runs/v7-victory8
```

**Cold start, no `--init`.** Every older checkpoint is already dead — `GLOBAL_DIM`
went 135 -> 145 and `ALL_KEYWORDS` gained three entries, and its index *is* a
card-feature column. That is convenient rather than costly: v6 was trained
against a wrong combat model (the engine assigned damage) and a champion it could
never play, so there is nothing in it worth warm-starting from.

## `--rollout 12288`, not the default 2048 — this is the one decision that matters

The reward is terminal-only, so the unit of learning signal is the **episode**,
not the step. Measured:

| | mean episode length | episodes per update at `rollout 2048` |
|---|---|---|
| v6, victory 5 | 32.9 transitions | **92** |
| victory 8 | ~160 transitions (rising to ~235 at random play) | **15** |

Fifteen win/loss outcomes per PPO update is six times less signal than v6 got,
at the same nominal rollout. `--rollout 12288` measures back to **74–84
episodes** per update, which is v6's number. Throughput is 247 st/s on CPU, so an
iteration is ~50s and 500 iterations is ~7 hours.

**Iteration counts are not comparable to v6's.** v6 ran 1500 iterations for 4.19M
env-steps; this is ~12,400 env-steps per iteration, so 500 iterations is ~6.2M —
about 1.5x v6's total compute in a third of the iterations.

## What victory 8 is expected to fix

v6 plateaued at iteration ~300 of 1500 and never reached the 65% bar, so
**compute was not the bottleneck**. The standing suspicion is the curriculum
itself: victory 5 finishes in 5.14 turns, and **tempo parity inverts at odd
victory scores**, so v3/v5 were teaching the wrong tempo. Victory 8 runs 9.6
turns (measured, random play), which is the game the decks were built for.

## Caps are sized for it, measured

1,000 real-deck games at victory 8 under random play:

| | measured max | cap | headroom |
|---|---|---|---|
| turns | 19 | `turn_cap` 30 | 1.6x |
| decisions | 529 | `decision_cap` 1500 | 2.8x |
| | | `loop_watch_after` 700 | above the ceiling, so healthy games never hash |

Truncation is 0.00% in all three fuzz modes at victory 8.

## The final point is gated, and the gate is live

471.1.b: the 8th point cannot be taken by Conquer unless the player Scored
**every** battlefield that turn. 471.1.a.1 exempts every non-Conquer source.
Measured across 400 real-deck games at victory 8:

| how the 8th point fell | | |
|---|---|---|
| Hold — exempt by 471.1.a.1 | 285 | 80.5% |
| Conquer with the whole board Scored | 66 | 18.6% |
| a card's point-gain effect — also exempt | 3 | 0.8% |
| **Conquers DENIED the point** (drew a card instead) | **58** | — |

So all three routes to the 8th point are reachable, there is no fourth, and the
restriction is a live constraint rather than dead code — 58 denials in 400 games.
Staged coverage is `test_combat` [12] plus judge cases 10614 and 471.1.a.1 in
`cases_65`.

## Two things to watch in the log

- **`loop=`** is new, printed next to `trunc=`. A nonzero value means a policy
  found a livelock and sat in it; the pair separates that from "games are simply
  running long".
- **`trunc=`** no longer means a free 0. A truncated game is decided on points by
  408.2.b, so a rising `trunc` with a falling win rate now means something.
