"""Random-game fuzz -- PLAN.md Phase 1.7, the M1 gate.

Usage: python3 rl/tests/fuzz.py [n_games] [victory_score] [--spells|--decks]

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
from dataclasses import replace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np

from rl.config import Config
from rl.engine import actions as A
from rl.engine import game
from rl.engine.cardtable import full_table
from rl.engine import invariants
from rl.engine.state import (C_ABIL, C_CARD, C_CTRL, C_OWNER, N_BF,
                             N_SEATS, P_ALIVE, P_CTRL, P_CARD,
                             P_OWNER, N_FD)


# Recorded v0 replay fingerprints: (deal seed, victory) -> (winner, turns,
# steps, points).
#
# **Outcome, not `state_hash`.** The digest covers the whole state blob, so
# adding a field to `GameState` moves it even when the game plays out
# identically -- which is precisely when you are relying on it. Pinning the
# observable outcome instead means the check stays meaningful across state
# changes and only fires when v0 actually plays differently. `state_hash` is
# still the right tool for same-process determinism (identical seed, identical
# trace), which is checked separately just above.
# Re-pinned when `play_destinations` began enforcing 806.3 ("a Unit can only be
# played to your base or a Battlefield you control"). Games got roughly 3x
# longer -- mean steps 20.4 -> 56.9 at victory 3 -- because dropping a unit onto
# an empty Battlefield was a Conquer that never had to survive a Combat, and it
# was the fastest line in the game. Measured, not predicted.
# The same reasoning applies to the printed determinism hash: it moved when
# `n_attached` was added to `GameState` while every observable stayed put --
# same winner, same mean and max step counts, same seat-0 rate. A state field
# moving the digest is the digest working as documented, not a regression; the
# outcome golden is what would have caught a real one, and it did not fire.
# Re-pinned twice more, both times because the DEAL changed rather than the
# play:
#   - `keyword_mask` stopped crediting keywords a card merely MENTIONED, which
#     changed which units `v0_pool` accepts;
#   - `data/tokens.json` added the eight rulebook tokens `cards.json` omits,
#     and the table is sorted by name, so every card id after "Baron Pit"
#     shifted and `rng.choice(pool)` picks different cards.
# Neither touched a rule. The golden pins an OUTCOME under a fixed seed, so it
# is sensitive to the deal by design -- that is what makes it catch a genuine
# behaviour change, and it means a pool change has to be re-pinned by hand.
# Re-recorded when the opening hand went 5 -> 4. Rule 116 is "players each
# draw 4"; the 5 was a Magic reflex, and it made every opening hand 25% larger
# than the real game's. Changing the deal changes every game from turn one, so
# these moving was the expected outcome, not a regression -- and the gate
# refusing to accept it silently is the reason it is worth keeping.
#     before: (12345, 3) -> (0, 6, 68, [3, 1])
#             (12345, 8) -> (1, 12, 176, [7, 8])
#
# Re-recorded again when the Mulligan became a DECISION rather than a skipped
# step (117). The random agent now chooses one, which both adds decisions to
# every game and changes which cards each player holds -- so these had to move,
# and an unchanged golden would have meant no one was being asked.
#     before: (12345, 3) -> (1, 5, 77, [2, 3])
#             (12345, 8) -> (1, 10, 170, [7, 8])
#
# And again when A_CANCEL stopped being offered. The step counts fell hardest
# -- 83 -> 33 at victory 3 -- which is the measurement of how much of a random
# agent's action budget was going into declare/cancel round trips that changed
# nothing.
#     before: (12345, 3) -> (1, 5, 83, [0, 3])
#             (12345, 8) -> (1, 10, 154, [5, 8])
GOLDEN: dict[tuple[int, int], tuple] = {
    (12345, 3): (1, 4, 33, [1, 3]),
    (12345, 8): (1, 9, 109, [6, 8]),
}


def v0_pool(table):
    """Cheap vanilla units -- no keywords outside Tier 1, no long text."""
    return [c for c in range(table.n)
            if table.is_type(c, "Unit") and table.in_v1_scope(c)
            and table.energy[c] <= 3 and table.power[c] <= 1
            and not table.has(c, "Temporary")]


def make_game(table, cfg, seed):
    rng = np.random.default_rng(seed)
    pool = v0_pool(table)
    decks = [[int(rng.choice(pool)) for _ in range(30)] for _ in range(2)]
    runes = [[int(rng.integers(6)) for _ in range(12)] for _ in range(2)]
    bfs = [c for c in range(table.n) if table.is_type(c, "Battlefield")][:2]
    # The same match context the env derives -- see `game.deck_knowledge`.
    return game.new_game(table, cfg, decks, runes, bfs, seed=seed,
                         deck_known=game.deck_knowledge(cfg, seed))


def make_v1_game(table, cfg, seed):
    """A spell game -- real deck size, real spell density, the DSL pool."""
    from rl.ppo import v1_deal            # imported lazily: ppo pulls in torch
    decks, runes, bfs, legends = v1_deal(table)(seed)
    # No champions: a random pool is not a decklist, so it has no Chosen
    # Champion to separate out (112). `deck_known` still applies -- it is match
    # context, not a property of the list.
    return game.new_game(table, cfg, decks, runes, bfs, seed=seed,
                         legends=legends,
                         deck_known=game.deck_knowledge(cfg, seed))


_DECK_DEAL = None


def make_deck_game(table, cfg, seed):
    """A matchup between two REAL decklists -- the training distribution.

    Worth its own gate because it is the only mode that puts the whole card
    pool on the board: units with unread keywords, 12-energy dragons, tokens,
    [Hidden] units, and rune decks that are actually two domains rather than
    six. `v1_deal`'s random pool never produces any of that.
    """
    global _DECK_DEAL
    if _DECK_DEAL is None:
        from rl.ppo import deck_pool_deal
        _DECK_DEAL = deck_pool_deal(table)
    decks, runes, bfs, legends, champions = _DECK_DEAL(seed)
    # `champions` is not optional here even though `make_v1_game` has none to
    # pass: `state_hash` digests every slot, so an env that places the Chosen
    # Champion and an oracle that does not are two different games under one
    # seed. That is exactly how `deck_known` broke test_env [1].
    return game.new_game(table, cfg, decks, runes, bfs, seed=seed,
                         legends=legends, champions=champions,
                         deck_known=game.deck_knowledge(cfg, seed))



def cards_owned(state, table, seat: int) -> int:
    """Every non-token card accounted to `seat`, across every zone at once.

    The count is CONSERVED for a whole game: cards move between zones, but a
    card is never created, destroyed, or handed to the other player. Checking
    that is worth a gate of its own because nothing else notices when it
    breaks -- a card duplicated into a trash looks exactly like a card that was
    legitimately trashed, and only surfaces much later as a Fizz or a Forge of
    the Future naming a copy the game never had.

    Three things are easy to get wrong here:

      - A card being PLAYED is on the Chain and in no zone at all.
      - A Chain Item for an ABILITY names its source's card while that card is
        already somewhere else, so counting it would double-count.
      - **Tokens must be excluded in EVERY zone, not just on the board.** 186
        has a token cease to exist off the board, so it is genuinely created
        and destroyed and cannot be conserved -- but the v0 fixture deals decks
        of token CARDS, so filtering only the board silently loses one card per
        token played and makes the gate fire on a healthy game.
    """
    def live(ids):
        return sum(1 for c in ids if int(c) >= 0 and not table.is_token(int(c)))

    n = live(state.hand[seat, :int(state.n_hand[seat])])
    n += live(state.deck[seat, int(state.deck_ptr[seat]):int(state.n_deck[seat])])
    n += live(state.trash[seat, :int(state.n_trash[seat])])
    # Cards mid-"look at the top N" are off the deck and in no zone at all
    # until the player picks. They still belong to the seat looking at them.
    if int(state.pend_look) == seat:
        n += live(state.look_cards[:int(state.n_look)])
    n += live(state.banished[seat, :int(state.n_banished[seat])])
    # 108.3 -- the Champion Zone. 103.2 counts the Chosen Champion inside the
    # 40-card Main Deck, so it is a conserved card like any other, and since
    # 108.3.d it can LEAVE this zone. While it could not, omitting it here was
    # self-consistent (the count was simply 39 all game); the moment it became
    # playable the gate started reading the play as a card being created.
    n += live([state.champion[seat]])
    # **P_OWNER, not P_CTRL.** A card is conserved against the player who OWNS
    # it, and the two come apart the moment one is played out of someone else's
    # zone -- Kharox digs a unit from the opponent's trash and plays it under
    # his own control. Counting by controller read that as a card changing
    # hands, which is exactly the thing this gate exists to refuse, so it fired
    # on a legal play.
    n += sum(1 for i in range(state.n_perms)
             if state.perms[i, P_ALIVE] == 1
             and int(state.perms[i, P_OWNER]) == seat
             and not table.is_token(int(state.perms[i, P_CARD])))
    n += sum(1 for b in range(N_FD)
             if int(state.fd_owner[b]) == seat
             and not table.is_token(int(state.fd_card[b])))
    n += sum(1 for i in range(int(state.n_chain))
             if int(state.chain[i, C_ABIL]) < 0
             and (int(state.chain[i, C_OWNER]) if int(state.chain[i, C_OWNER]) >= 0
                  else int(state.chain[i, C_CTRL])) == seat
             and int(state.chain[i, C_CARD]) >= 0
             and not table.is_token(int(state.chain[i, C_CARD])))
    return n


def main(n_games=2000, victory=3, check=True, spells=False,
         decks=False):
    """Random-game gate. `spells=True` fuzzes the v1 game instead of v0.

    v1 had no standing fuzz for most of the build -- it was checked with
    throwaway scripts, which meant the one command that exercises the Chain,
    targeting, damage and the response windows was rewritten from memory each
    time and never ran in the same shape twice. v0's golden outcome does not
    cover any of that code, because units resolve immediately (337.2) and v0
    never opens a priority window at all.
    """
    table = full_table()
    cfg = Config().at_victory_score(victory)
    if spells or decks:
        cfg = replace(cfg, units_only=False)
    build = (make_deck_game if decks else
             make_v1_game if spells else make_game)
    mode = "real-deck" if decks else "v1 spell" if spells else "v0"
    print(f"fuzzing {n_games} {mode} games at "
          f"victory_score={victory}, invariants={'on' if check else 'off'}",
          flush=True)

    t0 = time.time()
    winners, turns, steps, trunc = Counter(), [], [], 0
    every = max(1, n_games // 20)
    for i in range(n_games):
        rng = np.random.default_rng(i)
        s = build(table, cfg, i)
        before = [cards_owned(s, table, k) for k in range(N_SEATS)]
        r = game.play_game(table, cfg, s, [game.random_agent(rng)] * 2,
                           check=check)
        after = [cards_owned(s, table, k) for k in range(N_SEATS)]
        if check and after != before:
            raise invariants.InvariantError(
                f"seed {i}: cards were created or changed owner -- per-seat "
                f"totals went {before} -> {after}")
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
    a = game.play_game(table, cfg, build(table, cfg, 12345),
                       [game.random_agent(np.random.default_rng(7))] * 2)
    b = game.play_game(table, cfg, build(table, cfg, 12345),
                       [game.random_agent(np.random.default_rng(7))] * 2)
    assert a == b, f"non-deterministic:\n  {a}\n  {b}"
    print(f"  determinism: identical replay under seed (hash {a['hash']})")

    # Golden outcome. Pins how v0 actually plays, so an engine change that
    # alters the units-only game is a deliberate act rather than a surprise.
    # Neither resumable combat nor the Chain moved it: units resolve
    # immediately (337.2) and a priority window nobody can act in is skipped.
    if not (spells or decks) and (12345, victory) in GOLDEN:
        got = (a["winner"], a["turns"], a["steps"], a["points"])
        want = GOLDEN[(12345, victory)]
        if got != want:
            print(f"  \033[31mGOLDEN MISMATCH\033[0m v0 plays differently now:"
                  f"\n    got  {got}\n    want {want}"
                  f"\n    If this was intended, update GOLDEN in fuzz.py.")
        else:
            print(f"  golden: v0 outcome unchanged {got}")

    first = winners[0] / max(1, winners[0] + winners[1])
    print(f"  first-player win rate: {first:.1%}")
    return rate


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(argv[0]) if len(argv) > 0 else 2000
    v = int(argv[1]) if len(argv) > 1 else 3
    main(n, v, spells="--spells" in sys.argv,
         decks="--decks" in sys.argv)
