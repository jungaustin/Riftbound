"""The engine API: `legal_actions`, `apply`, `is_terminal`, `outcome`.

Every rules restriction that matters is enforced here, because an agent can only
ever return an index into the list this module builds. Nothing downstream
re-checks legality.

**Actions are factored, never a cartesian product.** A decision with several
parts becomes several decision points, each offering a small candidate set:

    play a card    ->  choose where it enters
    declare a move ->  add a unit, add another, ... -> COMMIT

This is the shape PLAN.md §1.3.a specifies for movement, and the same machinery
that target selection needs later (an "add one / STOP" loop bounded by a live
value -- Alphabet Strike). Building it once, generically, is why there is a
`pending` concept in `GameState` at all.

**Payment: a card's rune requirement is max(energy, power), not the sum.**
A Basic Rune has two independent abilities (164.2): exhaust for 1 Energy, or
Recycle for 1 Power of its domain. **Recycling has no ready requirement**, so a
rune already exhausted for Energy this turn can still be recycled for Power --
one physical rune paying both halves. `sim/engine/actions.py:93` gets this wrong
by removing recycled runes from the ready pool before checking Energy; do not
copy it. The real cost of Power is *attrition*: the rune goes to the bottom of
the Rune Deck (416.1.b) and must be re-channelled at 2/turn, so the board shrinks.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from rl.config import DOMAINS, Config
from rl.engine import combat, phases
from rl.engine.cardtable import CardTable
from rl.engine.state import (MAIN, N_BF, N_DOMAINS, N_SEATS, P_ALIVE, P_CARD,
                             P_CTRL, P_LOC, P_READY, GameState, base_loc,
                             bf_loc, is_battlefield)

# Action kinds. Wire format -- append only, never reorder.
(A_PASS, A_END_TURN, A_PLAY, A_PLAY_AT, A_DECLARE, A_ADD, A_COMMIT, A_CANCEL,
 A_RETREAT) = range(9)

KIND_NAMES = ("pass", "end_turn", "play", "play_at", "declare", "add",
              "commit", "cancel", "retreat")


class Action(NamedTuple):
    """A single decision point choice. `arg` is a hand index, permanent row, or
    location, depending on `kind`."""
    kind: int
    arg: int = -1

    def __repr__(self) -> str:
        return (f"{KIND_NAMES[self.kind]}"
                + (f"({self.arg})" if self.arg >= 0 else ""))


PASS = Action(A_PASS)


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------
# Power symbols on a multi-domain card: each symbol may be paid by a rune of ANY
# of the card's domains. The card data records a domain list and a power count
# but not the per-symbol breakdown, so a stricter reading cannot be
# distinguished from the data alone. Permissive never blocks a play a human
# could make; verify against card images before trusting a result that hinges on
# a multi-domain Power cost.
MULTI_DOMAIN_POWER_IS_PERMISSIVE = True


def card_domains(table: CardTable, card: int) -> list[int]:
    mask = int(table.domain_mask[card])
    return [d for d in range(N_DOMAINS) if mask >> d & 1]


def plan_payment(state: GameState, table: CardTable, seat: int,
                 card: int) -> list[int] | None:
    """Which domains to recycle for Power, or None if the card is unaffordable.

    Energy is generic (163.1.a) and comes from exhausting ready runes. Power is
    domain-bound (163.2) and comes from recycling, which may take an already
    exhausted rune -- so the two requirements are checked against *overlapping*
    pools, and a card needs max(energy, power) runes rather than their sum.
    """
    need_e = int(table.energy[card]) - int(state.pool_energy[seat])
    need_e = max(0, need_e)
    if need_e > state.total_ready_runes(seat):
        return None

    need_p = int(table.power[card])
    if need_p <= 0:
        return []
    doms = card_domains(table, card)
    if not doms:
        return None      # a Power cost with no domain is unpayable

    floating = sum(int(state.pool_power[seat, d]) for d in doms)
    need_p = max(0, need_p - floating)
    if need_p == 0:
        return []

    # Recycle from the domain held most, keeping scarce domains available.
    in_play = state.runes_in_play(seat)
    avail = sorted(doms, key=lambda d: (-int(in_play[d]), d))
    picks: list[int] = []
    left = {d: int(in_play[d]) for d in doms}
    for _ in range(need_p):
        best = max(avail, key=lambda d: (left[d], -d))
        if left[best] <= 0:
            return None
        left[best] -= 1
        picks.append(best)
    return picks


def pay(state: GameState, table: CardTable, seat: int, card: int,
        recycle: list[int]) -> None:
    """Exhaust for Energy, then recycle for Power. Order matters.

    Exhausting first is what makes one rune pay both halves: the recycle step
    can then take a rune that was just spent on Energy.
    """
    need_e = max(0, int(table.energy[card]) - int(state.pool_energy[seat]))
    state.pool_energy[seat] = max(
        0, int(state.pool_energy[seat]) - int(table.energy[card]))
    for _ in range(need_e):
        dom = int(np.argmax(state.runes_ready[seat]))
        assert state.runes_ready[seat, dom] > 0, "energy payment underflow"
        state.runes_ready[seat, dom] -= 1
        state.runes_spent[seat, dom] += 1

    need_p = int(table.power[card])
    for d in card_domains(table, card):
        use = min(need_p, int(state.pool_power[seat, d]))
        state.pool_power[seat, d] -= use
        need_p -= use
    for dom in recycle:
        state.recycle_rune(seat, dom)


# ---------------------------------------------------------------------------
# Legality
# ---------------------------------------------------------------------------

def play_destinations(state: GameState, table: CardTable, cfg: Config,
                      seat: int, card: int) -> list[int]:
    """Locations a permanent may be played to.

    Units may enter at their base or at any Battlefield -- playing onto an empty
    one is the no-combat Conquer path (194.1.b). Gear is base-only unless played
    from Hidden (811.1.d.1.a), which v0 does not reach.
    """
    if not table.is_type(card, "Unit"):
        return [base_loc(seat)]
    return [base_loc(seat)] + [bf_loc(i) for i in range(N_BF)]


def _hand_choices(state: GameState, seat: int) -> list[int]:
    """Hand indices, collapsing duplicates -- three identical cards are one
    choice, and offering all three triples the branching for nothing."""
    seen: set[int] = set()
    out = []
    for i in range(int(state.n_hand[seat])):
        c = int(state.hand[seat, i])
        if c not in seen:
            seen.add(c)
            out.append(i)
    return out


def legal_actions(state: GameState, table: CardTable, cfg: Config,
                  seat: int) -> list[Action]:
    """Every action `seat` may legally take right now.

    A player without priority gets nothing -- not even a pass. `pass` is a real
    action that yields a priority window; an empty list means "this seat is not
    being asked", which is what the driver loop tests.
    """
    if is_terminal(state):
        return []

    # --- mid-decision: a factored choice is open -------------------------
    if state.pend_play >= 0:
        if seat != state.active:
            return []
        card = int(state.hand[seat, state.pend_play])
        return [Action(A_PLAY_AT, loc)
                for loc in play_destinations(state, table, cfg, seat, card)]

    if state.declaring:
        if seat != state.active:
            return []
        out = [Action(A_ADD, i) for i in
               combat.movable_units(state, table, cfg, state.decl_dst)]
        if state.decl_mask:
            out.append(Action(A_COMMIT))
        out.append(Action(A_CANCEL))
        return out

    # --- showdown priority ------------------------------------------------
    if state.showdown_bf >= 0:
        if seat != state.priority:
            return []
        return [PASS] + combat.showdown_responses(state, table, cfg, seat)

    # --- Main Phase, Neutral Open ----------------------------------------
    # 316.5.b: only the Turn Player may act in a Neutral Open State.
    if state.phase != MAIN or seat != state.active:
        return []

    out: list[Action] = []
    for i in _hand_choices(state, seat):
        card = int(state.hand[seat, i])
        if cfg.units_only and not table.is_type(card, "Unit"):
            continue
        if plan_payment(state, table, seat, card) is None:
            continue
        out.append(Action(A_PLAY, i))

    for loc in combat.move_destinations(state, table, cfg):
        out.append(Action(A_DECLARE, loc))

    for i in range(state.n_perms):
        row = state.perms[i]
        if (row[P_ALIVE] == 1 and row[P_CTRL] == seat and row[P_READY] == 1
                and is_battlefield(int(row[P_LOC]))
                and table.is_type(int(row[P_CARD]), "Unit")):
            out.append(Action(A_RETREAT, i))

    out.append(Action(A_END_TURN))
    return out


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def apply(state: GameState, table: CardTable, cfg: Config,
          action: Action) -> dict:
    """Mutate `state` by `action`. Returns a small log dict for replays."""
    seat = state.active
    k = action.kind

    if k == A_PASS:
        if state.showdown_bf >= 0:
            combat.showdown_pass(state)
        return {}

    if k == A_PLAY:
        state.pend_play = action.arg
        return {}

    if k == A_PLAY_AT:
        return _resolve_play(state, table, cfg, seat, action.arg)

    if k == A_DECLARE:
        combat.declare_move(state, action.arg)
        return {}

    if k == A_ADD:
        combat.add_to_declaration(state, action.arg)
        return {}

    if k == A_COMMIT:
        return combat.commit_declaration(state, table, cfg)

    if k == A_CANCEL:
        combat.cancel_declaration(state)
        return {}

    if k == A_RETREAT:
        return combat.retreat(state, table, cfg, action.arg)

    if k == A_END_TURN:
        phases.end_turn(state, cfg)
        if not is_terminal(state):
            return phases.start_turn(state, table, cfg)
        return {}

    raise ValueError(f"unknown action kind {k}")


def _resolve_play(state: GameState, table: CardTable, cfg: Config,
                  seat: int, loc: int) -> dict:
    """Pay for the pending card and put it on the board.

    Units enter **exhausted** unless `[Accelerate]` was paid, so a unit played to
    a Battlefield cannot move again this turn and is locked there through the
    opponent's turn. That is the commitment, and it is why playing onto an empty
    Battlefield is a different decision from moving onto one.
    """
    idx = state.pend_play
    card = int(state.hand[seat, idx])
    recycle = plan_payment(state, table, seat, card)
    assert recycle is not None, "unaffordable card reached _resolve_play"
    pay(state, table, seat, card, recycle)

    n = int(state.n_hand[seat])
    state.hand[seat, idx:n - 1] = state.hand[seat, idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1
    state.pend_play = -1

    # v0 never pays [Accelerate]'s additional cost, so everything enters
    # exhausted. When Accelerate lands it becomes a choice at payment time, not
    # a property of the card.
    state.add_permanent(card, seat, loc, ready=False)
    return combat.cleanup(state, table, cfg, mover=seat, dst=loc)


# ---------------------------------------------------------------------------
# Terminal conditions
# ---------------------------------------------------------------------------

def is_terminal(state: GameState) -> bool:
    return state.winner >= 0 or state.truncated


def outcome(state: GameState) -> tuple[float, float]:
    """Per-seat reward, +1 / -1 / 0. Terminal-only, so with gamma=1.0 the critic
    learns a literal win probability (PLAN.md §1.2)."""
    if state.winner == 0:
        return (1.0, -1.0)
    if state.winner == 1:
        return (-1.0, 1.0)
    return (0.0, 0.0)


def acting_seat(state: GameState) -> int:
    """Which seat is being asked to choose, or -1 if none is."""
    if is_terminal(state):
        return -1
    if state.showdown_bf >= 0:
        return int(state.priority)
    return int(state.active)
