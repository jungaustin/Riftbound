# Session context — for starting a new chat

**Purpose.** Paste-free handoff. Read this plus `README.md` and you should be able
to pick up without asking for a summary. Claude keeps this current; it is
rewritten and pruned freely, so treat it as *state*, not a log.

**Last updated:** 2026-09-25 (D1, the Chosen Champion, and the RAD keywords)

---

## Right now

| | |
|---|---|
| **Running** | Nothing |
| **Committed** | Through `0947b4c`. Tree clean |
| **Branch** | `rl/card-scripting` |
| **Queue** | D1, Chosen Champion, and the 3 RAD keywords done -> **victory 8**, after backlog 1-2 (truncation + sterile loop, S each) |

**All older checkpoints are dead**: `GLOBAL_DIM` 135 -> 145, and
`ALL_KEYWORDS` gained three entries (its index IS a card-feature column).
Fine — v6 plateaued at greedy level and was trained against a wrong combat
model *and* a champion it could never play, so victory 8 should start fresh
rather than `--init`.

Landed today, each with tests and a commit message that carries the detail:
**D1** damage assignment is the player's (`3cd3c2a`), **108.3.d** the Chosen
Champion is playable (`d29e1a4`), **135.2.e.6.b** a domainless card pays Power
in any domain (`bb0114b`), the **unreleased-set gate** (`aa193d6`), and the
three **RAD keywords** (`fc10df7`, `6bf616a`).

---

## What v6 settled (`rl/runs/v6-overnight`, 1500 iters, 4.19M steps)

**The generalization gap closed** — train 58.4% vs held-out 54.8% (−3.7 ±
12.7), against v5's −6.5. Not significant at 7 decks x 24 games, but the point
estimate halved while absolute strength rose. More decks works.

**It plateaued at iteration ~300 of 1500**, so **compute is not the
bottleneck**: 1000 further iterations bought ~2 points and the 65% exit
criterion was never reached. Prime suspect is that victory 5 is too short to
be the real game (`turns=5.14`), and tempo parity *inverts* at odd victory
scores, so it teaches the wrong tempo.

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

## Unreleased sets

`data/upcoming/<SET_ID>.json` holds cards that are not out yet. Nothing there
reaches deckbuilding, ratings or training until its `released_on` passes or
`RIFTBOUND_UPCOMING=1` is set. `python cli.py upcoming` shows the status;
`rl/tests/test_upcoming.py` enumerates every corpus reader and fails by name
if a new one appears ungated.

**RAD is loaded: 14 cards, `released_on` a placeholder of 2099-01-01.** Nine
came from card scans, four from a paraphrase, plus a reconstructed Bomb token.
The file's `verification` block lists what still needs checking against the
official gallery -- every domain and power cost is read off card art.

Scripted so far: **[Disarm]**, **[Deploy]**, **[Show Off]** and Primordial
Roar. Work on this with the flag on:

```
RIFTBOUND_UPCOMING=1 python -m rl.tests.test_new_keywords
```

[Deploy] takes **any** battlefield, not only yours — 806.3's control clause is
unit-only and 149.2 says "unless an effect specifies otherwise". It also had to
be exempted from 149.3's stray-gear sweep, which was recalling it home on the
next Cleanup and made the whole keyword silently dead.

---

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
