# Session context — for starting a new chat

**Purpose.** Paste-free handoff. Read this plus `README.md` and you should be able
to pick up without asking for a summary. Claude keeps this current; it is
rewritten and pruned freely, so treat it as *state*, not a log.

**Last updated:** 2026-09-25 (v6 overnight run finished; maintenance rule in `CLAUDE.md`)

---

## Right now

| | |
|---|---|
| **Running** | Nothing. `rl/runs/v6-overnight` **completed all 1500 iters cleanly** (4.19M steps, ~6h, no crash) |
| **Uncommitted** | A lot. ~20 files. Nothing has been committed all session |
| **Branch** | `rl/card-scripting` |
| **Best checkpoint** | `rl/runs/v6-overnight/best.pt` — 58% vs greedy, 84% vs random |

---

## The two results from v6

**1. The generalization gap closed.** This is what the run was built to test.

| | train decks | held-out decks | gap |
|---|---|---|---|
| v5 (30 decks) | 54.5% | 48.0% | −6.5 |
| **v6 (40 train / 7 held out)** | **58.4%** | **54.8%** | **−3.7 ± 12.7** |

Not statistically significant (7 decks × 24 games is noisy), but the point
estimate halved while absolute strength rose. Training on more decks works;
"the agent does not generalize" is no longer the headline problem.

**2. The run plateaued at iteration ~300 of 1500.** Everything flat after that —
`len` 32, `turns` 5.15, `ev` +0.74 — while throughput *halved* (417 → 199 st/s,
the PFSP pool growing). 1000 iterations and ~4 hours bought about +2 points vs
greedy, and the 65% exit criterion was never reached.

**So compute is not the bottleneck.** Running longer at victory 5 is close to
worthless; the next gain has to come from changing what the agent can learn.

**Prime suspect: victory 5 is too short to be the real game.** `turns=5.14` means
games end in five turns. Attrition, board development and battlefield contention
barely exist in five turns. And per `BACKLOG.md`, tempo parity *inverts* at odd
victory scores — so victory 5 is actively teaching the wrong tempo for victory 8.

Per-deck spread is now 100% (0% on 4 decks, 100% on one). All four near-0% decks
load at `coverage=1.000`, so they are not broken at the card level — consistent
with the earlier finding that the spread is **deck strength in this engine**
(greedy-vs-greedy spread was 85.8%).

---

## What is true about the project

- **PPO**, on-policy actor-critic policy gradient. No Q, nothing takes a `max`.
  Terminal-only ±1 reward, `gamma=1.0`, so the critic *is* a win probability.
- **Engine is solid**: 2017 community judge calls pass, 62 engine bugs found and
  fixed, 12 test suites green.
- **Deck pool: 47 decks, 29 legends.** 25 Singapore Regional lists + 4 post-ban
  Kennen lists added 2026-09-25.
- **13 decks with banned cards** were in the pool until 2026-09-25. Now in
  `decks/banned/`, excluded inside `decklist_files` itself.
- Docs live in **`rl/docs/`** (`PLAN`, `LEARNING`, `PLAYING`, `RUNS`, `BACKLOG`),
  indexed by `rl/README.md`.

## Known-bad, in priority order

Full list with effort estimates in **`rl/docs/BACKLOG.md`**. The ones that bite:

1. **Damage assignment is made by the engine, not the player** (`D1`). Max-Might
   proxy, no ability awareness. Measured: the policy sequences multiple combats in
   10% of combat-turns vs random's 12% — it has **not** learned to swing
   separately, and cannot, because the engine's defender never punishes batching.
   Owner: "this changes things drastically, and that's why Backline and Tank exist."
2. **Truncation pays 0, losing pays −1** → a losing player is rewarded for
   stalling. Latent (`trunc=0.0%`) but bites at victory 8. Prerequisite for it.
3. **Chosen Champion cannot be played from the Champion Zone** (108.3.d). Every
   deck understated by one guaranteed threat.
4. **Bo3 battlefield choice and sideboarding do not exist.** Bo1's random pick is
   correct (485.5); Bo3's *choice* (486.5) has no action kind at all.
5. **"Name a tag" is restricted to tags already on the board.** The List fizzles
   against an empty board — dead exactly when played early.

---

## Working agreements

- **Never wrap `python3` in `timeout`** — breaks numpy here. Use the Bash tool's
  own timeout.
- A ruling that contradicts `data/rules.txt` goes in `rl/tests/judge/rejected.json`
  with the rule number.
- Commit messages end with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- **Measure, don't assume.** Several "obvious" claims were wrong and were caught
  by probing: `victory_bonus` invisible to the policy, 24 fields likewise, the
  per-deck spread being deck strength, two wrong claims in
  `reference/riftbound-deckbuilding-tips.txt`.
- Austin corrects rules from play experience; those corrections have been right
  every time. Verify against `data/tournament_rules.txt` (the authority for
  sideboarding — Core Rules never mention it) and save to memory.

## Open questions for Austin

- Commit the working tree? Nothing committed all session, and `best.pt` records
  `1dc45e4-dirty` — its engine state is only recoverable from `engine.patch`.
- The pre-training judge-call audit (his own gate) is still open.
