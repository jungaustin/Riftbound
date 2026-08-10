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
from rl.engine.cardtable import CardTable
from rl.engine.state import MAX_DECK, N_DOMAINS, N_SEATS, RUNE_RING, GameState

# 116 -- "Players each draw 4." This was 5, which is a Magic reflex rather than
# a Riftbound rule, and it made every opening hand 25% larger than the real one.
STARTING_HAND = 4
# 117.1 -- "A player may choose up to two cards in their hand."
MULLIGAN_MAX = 2


def new_game(table: CardTable, cfg: Config, decks: list[list[int]],
             rune_decks: list[list[int]], battlefields: list[int],
             seed: int = 0, mulligan_choices=None) -> GameState:
    """Deal a game. `decks` are card ids, `rune_decks` are domain ids.

    Battlefields start **uncontrolled**: each player picked one (486.5) but
    neither has units there, and 190.4.c is unambiguous that Control requires
    Units. The opening position therefore has two free points on the table,
    which is most of why the first few turns are a race rather than a setup.
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

    s.active = 0
    s.turn = 1
    for seat in range(N_SEATS):
        s.active = seat
        phases.draw(s, STARTING_HAND)
    s.active = 0

    # 117 -- the Mulligan happens in turn order, before the first turn begins.
    # `mulligan_choices` is empty by default, which is the legal "choose zero"
    # and keeps `new_game` deterministic for the fuzz and the goldens.
    for seat in range(N_SEATS):
        keep = () if mulligan_choices is None else mulligan_choices[seat]
        if keep:
            mulligan(s, seat, keep)

    phases.start_turn(s, table, cfg)
    return s


def mulligan(state: GameState, seat: int, indices) -> list[int]:
    """117 -- set aside up to two cards, draw that many, then Recycle them.

    **The order is set-aside -> draw -> recycle, and it is not cosmetic.**
    117.2 draws before 117.3 recycles, so the cards going to the bottom cannot
    be among the ones drawn to replace them. Recycling first would let a player
    redraw the exact card they just put back -- vanishingly unlikely with a full
    deck, certain with a nearly empty one, and wrong either way.

    Returns the card ids that were recycled.
    """
    idxs = sorted(set(int(i) for i in indices), reverse=True)
    assert len(idxs) <= MULLIGAN_MAX, (
        f"117.1 allows up to {MULLIGAN_MAX} cards, got {len(idxs)}")
    assert all(0 <= i < int(state.n_hand[seat]) for i in idxs), \
        "mulligan index outside the hand"

    # Set aside: out of the hand, but NOT yet into the deck.
    aside = []
    for i in idxs:
        n = int(state.n_hand[seat])
        aside.append(int(state.hand[seat, i]))
        state.hand[seat, i:n - 1] = state.hand[seat, i + 1:n]
        state.hand[seat, n - 1] = -1
        state.n_hand[seat] = n - 1

    prev, state.active = int(state.active), seat
    phases.draw(state, len(aside))
    state.active = prev

    for card in aside:
        state.recycle_card(seat, card)
    return aside


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
