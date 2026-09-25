# Session context — for starting a new chat

**Purpose.** Paste-free handoff. Read this plus `README.md` and you should be able
to pick up without asking for a summary. Claude keeps this current; it is
rewritten and pruned freely, so treat it as *state*, not a log.

**Last updated:** 2026-09-25 (D1 and the Chosen Champion landed; victory 8 is next)

---

## Right now

| | |
|---|---|
| **Running** | Nothing |
| **Committed** | `d149bc1` session work, `3cd3c2a` D1, `d29e1a4` champion. Tree clean |
| **Branch** | `rl/card-scripting` |
| **Queue** | D1 done, Chosen Champion done -> **victory 8 curriculum is next**, after backlog 1-2 (truncation + sterile loop, S each) |

**All older checkpoints are dead**: `GLOBAL_DIM` 135 -> 141 across the two
fixes. That is fine — v6 plateaued at greedy level and was trained against a
wrong combat model *and* a champion it could never play, so a fresh victory-8
run is the right next move rather than `--init`.

The two engine fixes, both measured on real decks:

- **D1, damage assignment (`3cd3c2a`).** 465.2.c.2 gives the choice to the
  player dealing the damage; the engine was deciding, which made `[Tank]` and
  `[Backline]` inert and left no gradient toward sequencing attacks. Offered
  only when `assignment_is_a_choice` (the pool cannot cover every target):
  176 offers in 300 games, 114 with more than one candidate. Greedy answers via
  `combat.dmg_solver_choice`, so the baseline did not weaken.
- **108.3.d, the Chosen Champion (`d29e1a4`).** Playable from its zone as one
  more source for the ordinary unit path (`A_PLAY` arg `CHAMPION_SRC`). Offered
  at 2022 decision points in 200 games, taken 294 times; mean game length
  7.4 -> 7.0 turns. `state.champion` is now occupancy and `champion_reg` the
  permanent public identity — conflating them blanked the archetype signature
  the moment the champion was cast.

---

## What v6 settled (`rl/runs/v6-overnight`, 1500 iters, 4.19M steps)

| | train decks | held-out | gap |
|---|---|---|---|
| v5 (30 decks) | 54.5% | 48.0% | −6.5 |
| **v6 (40 train / 7 held out)** | **58.4%** | **54.8%** | **−3.7 ± 12.7** |

**The generalization gap closed** — not significant at 7 decks x 24 games, but
the point estimate halved while absolute strength rose. More decks works.

**It plateaued at iteration ~300 of 1500** (everything flat after; throughput
halved as the PFSP pool grew). 1000 iterations bought ~2 points and the 65%
exit criterion was never reached, so **compute is not the bottleneck**. Prime
suspect: victory 5 is too short to be the real game (`turns=5.14`), and tempo
parity *inverts* at odd victory scores, so it teaches the wrong tempo.

Per-deck spread is 100%, but the near-0% decks all load at `coverage=1.000` —
deck strength in this engine, not broken cards (greedy-vs-greedy spread 85.8%).

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

1. **`acting_seat` can name a seat with no legal actions.** Reproduces at
   `make_v1_game` seed **859**; pre-existing (fails at `d149bc1` too), found by
   raising the v1 spell fuzz from 300 to 2000 games. `play_game` raises whether
   or not invariants are on, so it is a crash, not a stall. The real-deck path
   is clean, which is why v6 never hit it.
2. **Truncation pays 0, losing pays −1** → a losing player is rewarded for
   stalling. Latent (`trunc=0.0%`) but bites at victory 8. Prerequisite for it.
3. **Bo3 battlefield choice and sideboarding do not exist.** Bo1's random pick
   is correct (485.5); Bo3's *choice* (486.5) has no action kind at all, and 27
   of 47 decklists carry an unparsed `Sideboard:` section.
4. **"Name a tag" is restricted to tags already on the board.** The List fizzles
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
