# Session context — for starting a new chat

**Purpose.** Paste-free handoff. Read this plus `README.md` and you should be able
to pick up without asking for a summary. Claude keeps this current; it is
rewritten and pruned freely, so treat it as *state*, not a log.

**Last updated:** 2026-09-27 (critical path cleared; victory 8 set up, not launched)

---

## Right now

| | |
|---|---|
| **Running** | Nothing |
| **Committed** | Through `64395ee`. Uncommitted: `decks/renata-gutter-palace/` (new deck, v1, untested) |
| **Branch** | `rl/card-scripting` |
| **Next** | **Launch the victory-8 run** — command and reasoning in `rl/docs/V8_SETUP.md`. Blocked only on the pre-training judge-call audit, which is Austin's own gate |

**The critical path is clear** (`64395ee`). Backlog 0–2 done, and chasing them
turned up three more pre-existing crashes:

- **`state.priority` went stale when the Chain was COUNTERED empty.** 340.2 hands
  priority back only on the path where an item *resolved*; `chain.counter` pops
  one and nobody restored it. So a unit played on the turn player's own turn was
  announced under the opponent's seat and indexed their hand. `_normalize_priority`
  now states the rule once, at the end of every `apply` — stale priority also lied
  to `obs` (which feeds `priority == seat` to the policy) and to `invariants`.
- **Truncation is decided on points (408.2.b)**, not called a draw: a lead of two
  or more wins, less is a draw. Paying a flat 0 made stalling profitable.
- **Sterile-loop detection** in `env._check_sterile_loop`, reported as `loop=` in
  the training log. Blames a seat only when it had an alternative; a forced loop
  falls back to 408.2.b.
- Plus: an attached Equipment's granted ability crashed on activation (721.2
  off-by-one between `activatable` and `_activate`; real-deck seed 95, *in the
  training distribution*); `env.play` spun forever on a truncation; and
  `invariants` called a legal Undying Loyalty play illegal by reading its printed
  cost (v1 spell seed 661 **at victory 8**).

Named seeds now run first in `fuzz.main`, keyed by `(mode, victory)` — every one
of these needed the game count or the victory score raised to be reachable.

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

**The generalization gap closed** — train 58.4% vs held-out 54.8% (−3.7 ± 12.7)
against v5's −6.5. Not significant at 7 decks x 24 games, but the point estimate
halved while absolute strength rose. More decks works.

**It plateaued at iteration ~300 of 1500**, so compute is not the bottleneck: 1000
further iterations bought ~2 points. Prime suspect is victory 5 being too short
(`turns=5.14`) with tempo parity *inverted* at odd victory scores. Per-deck spread
is 100%, but the near-0% decks all load at `coverage=1.000` — deck strength in
this engine, not broken cards.

## What is true about the project

- **PPO**, on-policy actor-critic policy gradient. No Q, nothing takes a `max`.
  Terminal-only ±1 reward, `gamma=1.0`, so the critic *is* a win probability.
- **Engine is solid**: 2017 community judge calls pass, 62 engine bugs found and
  fixed, 13 test suites green, all three fuzz modes clean at victory 3 and 8.
- **Deck pool: 47 decks, 29 legends.** 25 Singapore Regional lists + 4 post-ban
  Kennen lists added 2026-09-25.
- **13 decks with banned cards** are in `decks/banned/`, excluded inside
  `decklist_files` itself.
- Docs live in **`rl/docs/`** (`PLAN`, `LEARNING`, `PLAYING`, `RUNS`, `BACKLOG`,
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

- **Never wrap `python3` in `timeout`** — breaks numpy here. Use the Bash tool's
  own timeout.
- A ruling that contradicts `data/rules.txt` goes in `rl/tests/judge/rejected.json`
  with the rule number. `data/tournament_rules.txt` is the authority for
  sideboarding, competition rules and **how a game out of clock is decided
  (408.2.b)** — the Core Rules mention none of them.
- Commit messages end with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- **Measure, don't assume.** It paid four times this session alone: the seed-859
  crash was not in `acting_seat` at all, `loop_watch_after` had to be raised once
  victory 8 was measured, `--rollout` needed 6x, and the final-point gate was
  confirmed live only by counting denials in play.
- Austin corrects rules from play experience; those corrections have been right
  every time. Verify, then save to memory.

## Open questions for Austin

- Commit `decks/renata-gutter-palace/`? It is the only untracked work left.
- The pre-training judge-call audit (his own gate) is still open, and victory 8 is
  training, so it sits in front of the launch.
- Heimerdinger is settled in that deck's favour — RiftJudge #12424 says he copies
  Mastermind's score from base and does NOT inherit her battlefield clause — so
  his **66** was capped by the open question, not by card quality. `ratings.md`
  and `README.md` still say the ruling is needed.
