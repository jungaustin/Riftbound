# Session context — for starting a new chat

**Purpose.** Paste-free handoff. Read this plus `README.md` and you should be able
to pick up without asking for a summary. Claude keeps this current; it is
rewritten and pruned freely, so treat it as *state*, not a log.

**Last updated:** 2026-09-27 (critical path cleared; victory 8 set up, not launched)

---

## Right now

| | |
|---|---|
| **Running** | **`rl/runs/v7-victory8`** — 500 iters at victory 8 on `0ed3cf7`, ~7h. FOURTH attempt; the first three died at iterations 19, 8 and 8. Watch `ovf=` (board-row overflow) and `loop=` |
| **Committed** | Through `0ed3cf7`. Uncommitted: `decks/renata-gutter-palace/`, `decks/seraphine-not-alone/` (untracked) |
| **Branch** | `rl/card-scripting` |
| **Next** | Austin's judge list, batch 2. Scraped batch 84 is in (2159 rulings, corpus caught up to 12724) and found no new bugs |

**The engine is green on everything**: 13/13 suites, five fuzz modes at victory 3
*and* 8, five named regression seeds, 2023 judge calls, 0 known-bad.

### Austin's judge list, batch 1 — 3 interactions, 2 were engine bugs

`rl/tests/judge/cases_austin_01.py`, ids `AJ-NN` so they cannot be mistaken for
scraped RiftJudge numbers.

- **AJ-03 passed as-is** (three cases). Simultaneous triggers: your own two are
  offered as an order choice and LIFO is right (Yasuo reads 9 Might, not 6);
  opposing triggers are placed in turn order with no choice, so Vex denies
  Tideturner's move on your turn and allows it on theirs.
- **AJ-01 was wrong: 466.5 → 466.6 → 466.7 ran backwards.** Control was settled
  *after* the Showdown was torn down, so every Conquer trigger resolved in a
  world where the Combat had already ended. Now it suspends at a new
  `SD_CONQUER` step with the designations still on. Rengar reaches 8 Might.
- **AJ-02 was wrong: 372 was a fixed ladder.** Smite's banish sat ahead of
  Zhonya's, so the save was unreachable. Now `pend_repl` asks the dying
  permanent's controller. Both directions are real and both are tested.

### Four crashes fixed, all the same species

**Two code paths disagreeing about what a play costs.** Named seeds now run
first in `fuzz.main`, keyed by `(mode, victory)`:

| seed | mode | what |
|---|---|---|
| 859 | v1 spell, v3 | `priority` went stale when the Chain was COUNTERED empty |
| 95 | real-deck, v3 | an attached Equipment's granted ability, 721.2 off-by-one |
| 661 | v1 spell, v8 | an invariant read Undying Loyalty's printed cost |
| 5097 | real-deck, v8 | the **[Deflect] surcharge** offered against the printed cost, paid against the real one — this killed the first v8 run at iteration 19 |
| 55 | real-deck, v8 | Heimerdinger's **borrowed**-ability offer checked fewer costs than the permanent loop above it |

**`MAX_PERMS` is a capacity limit, not a bug, and now costs one episode.** Rows are
only reclaimed at end of turn, so the cap is on rows CREATED per turn. Measured at
victory 8: random peaks at 33 of 48, greedy at 36, one action adds at most 7 — so
what reaches it is a policy, not the rules. `state.BoardOverflow` is caught by
`env._apply` (the ONE funnel every `A.apply` goes through — a test scans `env.py`
to keep it that way) and ends the episode. Observed rate: ~1.3% in one iteration,
0% in the rest. Raise the cap only if `ovf=` climbs; it widens the board zone.

`actions.play_cost_reservation` is now the single answer to "what will this play
recycle", used by every offer site. Consistency is the load-bearing part: being
strict in one place only turns a crash into a deadlock.

**Also**: truncation is decided on points (408.2.b), sterile loops end the
episode and name the looper, `env.play` no longer spins on a truncation, and a
decklist built on unreleased cards is now SKIPPED rather than loaded mutilated
into the pool (`decks/seraphine-not-alone/` was entering training 39 cards with
no champion).

## Victory 8 is measured and ready

All three fuzz modes clean at victory 8. Caps have headroom: turns max 19 against
`turn_cap` 30, decisions max 529 against `decision_cap` 1500.

**The final point is properly gated, and measured in play** rather than only unit
tested — 400 real-deck games, how the 8th point fell: **Hold 285 (80.5%)**,
**Conquer with the whole board Scored 66 (18.6%)**, **a card's point-gain effect
3 (0.8%)**, and **58 Conquers were DENIED it** and drew a card instead (471.1.b).
Three routes, no fourth, and the gate is a live constraint.

**`--rollout 12288`, not the default 2048.** The reward is terminal-only, so the
unit of learning signal is the *episode*. Victory-8 episodes are ~6x longer than
victory 5's, which at the default rollout is 15 outcomes per PPO update against
v6's 92. 12288 measures back to 74–84. ~247 st/s, so 500 iterations is ~7 hours.

**All older checkpoints are dead**: `GLOBAL_DIM` 135 -> 145, and `ALL_KEYWORDS`
gained three entries (its index IS a card-feature column). Fine — v6 plateaued at
greedy level and was trained against a wrong combat model *and* a champion it
could never play, so victory 8 starts cold rather than with `--init`.

---

## What v6 settled (`rl/runs/v6-overnight`, 1500 iters, 4.19M steps)

The generalization gap closed — train 58.4% vs held-out 54.8% (−3.7 ± 12.7)
against v5's −6.5, not significant but the point estimate halved. **It plateaued
at iteration ~300 of 1500**, so compute was not the bottleneck; the suspect is
victory 5 being too short (5.14 turns) with tempo parity inverted at odd scores.
That is what v7 tests.

## What is true about the project

- **PPO**, on-policy actor-critic. No Q, nothing takes a `max`. Terminal-only ±1
  reward, `gamma=1.0`, so the critic *is* a win probability.
- **Engine is solid**: 2017 community judge calls pass, 62 engine bugs found and
  fixed, 13 suites green, all three fuzz modes clean at victory 3 *and* 8.
- **Deck pool: 47 decks, 29 legends.** 13 decks with banned cards live in
  `decks/banned/`, excluded inside `decklist_files` itself.
- Docs in **`rl/docs/`** (`PLAN`, `LEARNING`, `PLAYING`, `RUNS`, `BACKLOG`,
  `V8_SETUP`), indexed by `rl/README.md`.

## Unreleased sets

`data/upcoming/<SET_ID>.json` holds cards that are not out yet. Nothing there
reaches deckbuilding, ratings or training until its `released_on` passes or
`RIFTBOUND_UPCOMING=1` is set. `python cli.py upcoming` shows status;
`rl/tests/test_upcoming.py` enumerates every corpus reader and fails by name if a
new one appears ungated.

**RAD: 14 cards, `released_on` a placeholder of 2099-01-01.** Its `verification`
block lists what needs checking against the official gallery — every domain and
power cost is read off card art. Scripted: **[Disarm]**, **[Deploy]**, **[Show
Off]**, Primordial Roar. Still to script: Ziggs, Orianna, Ekko, K'Sante,
Seraphine x2, Neeko, Kai'Sa, Evelynn, Hexplosive Minefield, Ntofo Strikes, Bomb.
Work with `RIFTBOUND_UPCOMING=1 python -m rl.tests.test_new_keywords`.

[Deploy] takes **any** battlefield, not only yours (806.3's control clause is
unit-only; 149.2 says "unless an effect specifies otherwise"), and had to be
exempted from 149.3's stray-gear sweep, which was recalling it home every Cleanup
and made the keyword silently dead.

---

## Known-bad, in priority order

Full list with effort estimates in **`rl/docs/BACKLOG.md`**. The ones that bite:

1. **Bo3 battlefield choice and sideboarding do not exist.** Bo1's random pick is
   correct (485.5); Bo3's *choice* (486.5) has no action kind at all, and 27 of 47
   decklists carry an unparsed `Sideboard:` section.
2. **"Name a tag" is restricted to tags already on the board.** The List fizzles
   against an empty board — dead exactly when played early.
3. **718.3 — Equipment ability text.** An attached card's Effect Text is dropped,
   so "When I hold, score 1 point" silently does nothing.

## Working agreements

`CLAUDE.md` has the standing ones. Added here:

- `data/tournament_rules.txt` is the authority for sideboarding, competition rules
  and **how a game out of clock is decided (408.2.b)** — Core mentions none.
- **Measure, don't assume** paid four times this session: the seed-859 crash was
  not in `acting_seat` at all, `loop_watch_after` had to be raised once victory 8
  was measured, `--rollout` needed 6x, and the final-point gate was confirmed live
  only by counting denials in play.

## Open questions for Austin

- Commit `decks/renata-gutter-palace/`? It is the only untracked work left.
- The pre-training judge-call audit (his own gate) is still open, and victory 8 is
  training, so it sits in front of the launch.
- Heimerdinger is settled in that deck's favour — RiftJudge #12424 says he copies
  Mastermind's score from base and does NOT inherit her battlefield clause — so
  his **66** was capped by the open question, not by card quality. `ratings.md`
  and `README.md` still say the ruling is needed.
