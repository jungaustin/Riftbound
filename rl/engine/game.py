"""Game setup and the driver loop.

`play_game` is the only thing that advances a game, so the fuzz gate, the
baselines, and the gym wrapper all share one control flow. An agent is any
callable `(state, table, cfg, seat, actions) -> Action`.

The loop asks whichever seat `acting_seat` names. A seat with an empty action
list is not being asked; an empty list for the seat that *is* to act is a
deadlock, and `invariants.check_actions` fails loudly on it rather than letting
the game spin to the turn cap.
"""

from __future__ import annotations

import numpy as np

from rl.config import DOMAINS, Config
from rl.engine import actions as A
from rl.engine import invariants, phases
# Setup constants and the Mulligan live in `phases`: `actions` needs them
# and `game` imports `actions`, so keeping them here made a real import
# cycle that only worked by luck of import order. Re-exported so the
# existing call sites keep working.
from rl.engine.phases import (MULLIGAN_MAX, STARTING_HAND,  # noqa: F401
                              mulligan)
from rl.engine.cardtable import CardTable
from rl.engine.state import MAX_DECK, N_DOMAINS, N_SEATS, RUNE_RING, GameState



def new_game(table: CardTable, cfg: Config, decks: list[list[int]],
             rune_decks: list[list[int]], battlefields: list[int],
             seed: int = 0, mulligan_choices=None,
             legends: list[int] | None = None) -> GameState:
    """Deal a game. `decks` are card ids, `rune_decks` are domain ids.

    Battlefields start **uncontrolled**: each player picked one (486.5) but
    neither has units there, and 190.4.c is unambiguous that Control requires
    Units. The opening position therefore has two free points on the table,
    which is most of why the first few turns are a race rather than a setup.

    `legends` is each seat's Champion Legend (111), placed in the Legend Zone
    before the first turn and never leaving it. Optional, and -1 per seat when
    omitted: a caller dealing a random pool has no decklist to take one from,
    and a game with no legend is a legal game with one fewer ability.
    """
    s = GameState()
    s.rng = np.random.default_rng(seed)

    for seat in range(N_SEATS):
        deck = list(decks[seat])
        s.rng.shuffle(deck)
        assert len(deck) <= MAX_DECK, "deck larger than MAX_DECK"
        s.n_deck[seat] = len(deck)
        s.deck[seat, :len(deck)] = deck

        runes = list(rune_decks[seat])
        s.rng.shuffle(runes)
        assert len(runes) <= RUNE_RING, "rune deck larger than the ring buffer"
        s.rune_deck[seat, :len(runes)] = runes
        s.rune_head[seat] = 0
        s.rune_left[seat] = len(runes)

    for i, bf in enumerate(battlefields):
        s.bf_card[i] = bf

    # 111 -- each player separates their Champion Legend into the Legend Zone.
    # Ready to begin with: 174.2.b establishes it at the start of the game, and
    # nothing has exhausted it yet.
    for seat in range(N_SEATS):
        if legends is not None and seat < len(legends):
            s.legend[seat] = int(legends[seat])
    s.legend_ready[:] = 1

    s.active = 0
    s.turn = 1
    for seat in range(N_SEATS):
        s.active = seat
        phases.draw(s, STARTING_HAND)
    s.active = 0

    # 117 -- the Mulligan happens in turn order, before the first turn begins,
    # and it is a real DECISION: "up to two" is a choice about a quarter of the
    # opening hand. So `new_game` stops here and hands the first decision to
    # the First Player; `actions._finish_mulligan` starts the turn once both
    # players are done (118).
    #
    # `mulligan_choices` short-circuits that for tests and for any caller that
    # wants a ready-to-play state.
    if mulligan_choices is None:
        s.pend_mull = 0
        return s
    for seat in range(N_SEATS):
        keep = mulligan_choices[seat]
        if keep:
            mulligan(s, seat, keep)
    phases.start_turn(s, table, cfg)
    # `start_turn` SUSPENDS if anything triggered in the Beginning Step (315.2),
    # and it is `_settle` that puts those triggers on the Chain and hands out
    # priority. Every other caller reaches it through `actions.apply`; this one
    # does not, and without this the state came back mid-Beginning-Phase with a
    # queued trigger and NO legal actions -- a deadlock rather than a game.
    # The Arena's Greatest fires on turn 1, so it is reachable from a plain
    # deal, not just a contrived one.
    A._settle(s, table, cfg)
    return s




def random_agent(rng: np.random.Generator):
    def choose(state, table, cfg, seat, actions):
        return actions[int(rng.integers(len(actions)))]
    return choose


def play_game(table: CardTable, cfg: Config, state: GameState, agents,
              check: bool = False, max_steps: int = 20000) -> dict:
    """Run to termination. Returns a summary dict.

    `check` turns on the invariant suite -- a few array ops per step, so it is
    off for training and on for the fuzz gate.
    """
    steps = 0
    while not A.is_terminal(state):
        seat = A.acting_seat(state)
        if seat < 0:
            break
        legal = A.legal_actions(state, table, cfg, seat)
        if check:
            invariants.check(state)
            invariants.check_actions(state, table, cfg, seat, legal)
        if not legal:
            # The seat to act has nothing to do; the position is stuck. Only
            # reachable if the enumerator regressed, and `check_actions` above
            # would already have fired when checking is on.
            raise invariants.InvariantError(
                f"seat {seat} to act with no legal actions on turn {state.turn}")
        A.apply(state, table, cfg,
                agents[seat](state, table, cfg, seat, legal))
        steps += 1
        if steps > max_steps:
            raise RuntimeError(f"game exceeded {max_steps} steps")

    return {
        "winner": int(state.winner),
        "truncated": bool(state.truncated),
        "turns": int(state.turn),
        "steps": steps,
        "points": state.points.tolist(),
        "hash": state.state_hash(),
    }
