# Playing against the agent, and asking it for advice

Two modes, both in `rl/play.py`. Everything shown on screen is information a
player could legitimately have — nothing comes from the privileged critic.

---

## Play a game

```bash
python3 rl/play.py vs --ckpt rl/runs/v4-standing/best.pt --victory 3 --seat 0
```

| flag | |
|---|---|
| `--ckpt` | which checkpoint. `best.pt` is written whenever the eval improves, so it exists mid-run |
| `--victory` | **must match what the checkpoint was trained at** (3 for v3/v4, 5 for v5) |
| `--seat` | which side you sit on. 0 goes first |
| `--seed` | the deal. Same seed = same game, so a position can be replayed |
| `--decks` | narrow the decklist pool by substring, e.g. `--decks lillia` |
| `--deterministic` | agent always takes its top move. Off by default — the policy is stochastic on purpose |
| `--procedural` | deal `v1_deal`'s random-pool decks instead of real lists (training curriculum, not a real game) |

At the prompt: a **number** to play that action, `?` for the agent's ranking of
your options, `q` to quit.

Real decklists are the default. `--procedural` exists only to reproduce a
training position; those decks are 6-domain soup with an unrelated rune deck and
are no fun to sit across from.

## Ask it about a position

```bash
python3 rl/play.py advise --ckpt rl/runs/v4-standing/best.pt --victory 3 --seed 4 --ply 20
```

`--ply` fast-forwards with random moves to reach a live mid-game position. Output:

```
--- the agent's ranking (policy head; legitimate information only) ---
     move                                    policy  value after
     play Ravenbloom Student                  63.4%       -0.320
     play Frigid Touch                        23.1%       -0.455
     play Temporal Breach                      6.2%       -0.398
     end turn                                  0.3%       -0.990

critic (policy-side -- legitimate information only): -0.351
```

- **`policy`** — the probability the agent would pick that move. This is the
  actual learned distribution, not a score.
- **`value after`** — a 1-ply lookahead: `win_prob` of the resulting position,
  from the mover's point of view.
- **`critic`** — `win_prob` of the current position. In `[-1, +1]`, where `0` is
  an even game. Above, `-0.35` means it thinks it is behind.

Both value columns come from `value_sym`, the honest head. `value_priv` (which
sees the opponent's hand) is never consulted here — it would give advice that
looks right and cannot be acted on.

---

## Is it any good yet?

**Honestly: interesting, not yet satisfying.** As of v4 it is at **50.5% vs the
greedy heuristic baseline** — roughly heuristic strength. It will make mistakes
you can spot.

Two things stand between this and a game that feels like Riftbound:

1. **It is trained at victory 3, not 8.** That is a different and more lopsided
   game — first player is worth ~64% at victory 3 — and the tempo parity is
   *inverted* at odd victory scores (see `LEARNING.md` §5). Annealing to 8 is
   the single biggest improvement available.
2. **It cannot play its Chosen Champion** (108.3.d is not implemented). You will
   notice this in the first game: it simply never casts it. This also makes it
   weaker by one guaranteed threat.

**Its strength varies enormously by deck** — from 4% to 79% against greedy
depending on the list it pilots (see `RUNS.md`). If a game feels trivially easy
or impossible, check which deck it drew before concluding anything about the
agent. `--decks` pins the matchup.

## Which checkpoint to use

| file | |
|---|---|
| `best.pt` | highest `vs_random + vs_greedy` at an eval. **Use this one.** |
| `last.pt` | the final iteration. Usually *worse* — see the drift finding in `RUNS.md` |

`--victory` must match training. A mismatch will load (the observation shape does
not depend on it) but the agent will be aiming at the wrong finish line, which is
exactly the bug `victory_bonus` caused.

Both files record the engine commit in `ck["engine"]`; a `-dirty` suffix means it
was trained against uncommitted changes.
