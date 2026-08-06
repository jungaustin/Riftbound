"""Random-game fuzz -- PLAN.md Phase 1.7, the M1 gate.

Usage: python3 rl/tests/fuzz.py [n_games] [victory_score]

Asserts: no exceptions, every game terminates, invariants hold at every step,
and the same seed reproduces a bit-identical result. Reports the truncation
rate, which is the number that actually matters -- anything much above ~2% means
games are stalling rather than being decided, and a stalled game teaches a
policy nothing.
"""

from __future__ import annotations

import pathlib
import sys
import time
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np

from rl.config import Config
from rl.engine import actions as A
from rl.engine import game
from rl.engine.cardtable import full_table


# Recorded v0 replay fingerprints: (deal seed, victory score) -> state_hash.
# Filled by running fuzz once after a deliberate engine change.
GOLDEN: dict[tuple[int, int], int] = {
    (12345, 3): -168154415714110210,
    (12345, 8): 5238592629090370362,
}


def v0_pool(table):
    """Cheap vanilla units -- no keywords outside Tier 1, no long text."""
    return [c for c in range(table.n)
            if table.is_type(c, "Unit") and table.v1_legal(c)
            and table.energy[c] <= 3 and table.power[c] <= 1
            and not table.has(c, "Temporary")]


def make_game(table, cfg, seed):
    rng = np.random.default_rng(seed)
    pool = v0_pool(table)
    decks = [[int(rng.choice(pool)) for _ in range(30)] for _ in range(2)]
    runes = [[int(rng.integers(6)) for _ in range(12)] for _ in range(2)]
    bfs = [c for c in range(table.n) if table.is_type(c, "Battlefield")][:2]
    return game.new_game(table, cfg, decks, runes, bfs, seed=seed)


def main(n_games=2000, victory=3, check=True):
    table = full_table()
    cfg = Config().at_victory_score(victory)
    print(f"fuzzing {n_games} games at victory_score={victory}, "
          f"invariants={'on' if check else 'off'}", flush=True)

    t0 = time.time()
    winners, turns, steps, trunc = Counter(), [], [], 0
    every = max(1, n_games // 20)
    for i in range(n_games):
        rng = np.random.default_rng(i)
        s = make_game(table, cfg, i)
        r = game.play_game(table, cfg, s, [game.random_agent(rng)] * 2,
                           check=check)
        winners[r["winner"]] += 1
        turns.append(r["turns"])
        steps.append(r["steps"])
        trunc += r["truncated"]
        # Stream progress: a long fuzz that gets interrupted must still have
        # said something useful, and stdout is block-buffered when piped.
        if (i + 1) % every == 0:
            done, el = i + 1, time.time() - t0
            print(f"  [{done:>7}/{n_games}] {done / el:6.0f} games/s  "
                  f"trunc={trunc / done:.2%}  "
                  f"seat0={winners[0] / done:.1%}  "
                  f"eta {(n_games - done) / (done / el):.0f}s", flush=True)
    dt = time.time() - t0

    print(f"  {n_games} games in {dt:.1f}s  ({n_games / dt:.0f} games/sec, "
          f"{sum(steps) / dt:.0f} decisions/sec)")
    print(f"  winner: seat0={winners[0]}  seat1={winners[1]}  "
          f"undecided={winners[-1]}")
    print(f"  turns:  mean {np.mean(turns):.1f}  max {max(turns)}")
    print(f"  steps:  mean {np.mean(steps):.1f}  max {max(steps)}")
    rate = trunc / n_games
    print(f"  truncated: {trunc}/{n_games} = {rate:.2%}"
          + ("  <-- ABOVE 2%, games are stalling" if rate > 0.02 else "  ok"))

    # Determinism: same seed, same trace.
    a = game.play_game(table, cfg, make_game(table, cfg, 12345),
                       [game.random_agent(np.random.default_rng(7))] * 2)
    b = game.play_game(table, cfg, make_game(table, cfg, 12345),
                       [game.random_agent(np.random.default_rng(7))] * 2)
    assert a == b, f"non-deterministic:\n  {a}\n  {b}"
    print(f"  determinism: identical replay under seed (hash {a['hash']})")

    # Golden fingerprint. `state_hash` is a blake2b digest, so it is stable
    # across processes and can pin v0's behaviour: any engine change that moves
    # this number changed how the units-only game plays, and that should be a
    # deliberate act rather than a surprise. Resumable combat (Reactions) does
    # NOT move it, because a priority window nobody can act in is skipped.
    if (12345, victory) in GOLDEN:
        want = GOLDEN[(12345, victory)]
        if a["hash"] != want:
            print(f"  \033[31mGOLDEN MISMATCH\033[0m v0 replay changed: "
                  f"{a['hash']} != {want}\n"
                  f"    {a}\n"
                  f"    If this was intended, update GOLDEN in fuzz.py.")
        else:
            print(f"  golden: v0 replay unchanged since it was recorded")

    first = winners[0] / max(1, winners[0] + winners[1])
    print(f"  first-player win rate: {first:.1%}")
    return rate


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    v = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    main(n, v)
