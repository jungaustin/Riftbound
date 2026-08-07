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
from rl.engine import chain, combat, phases
from rl.engine import resolve as rsv
# Payment lives in `cost` so combat can ask about affordability without
# importing the action layer. Re-exported: callers still say A.plan_payment.
from rl.engine.cost import (MULTI_DOMAIN_POWER_IS_PERMISSIVE, card_domains,
                            pay, plan_payment)
from rl.engine.cardtable import CardTable
from rl.engine.effects import spec_for
from rl.engine.state import (C_BOUND_BF, C_CARD, C_CTRL, MAIN, N_BF,
                             N_DOMAINS, N_SEATS, P_ALIVE, P_CARD, P_CTRL,
                             P_LOC, P_READY, GameState, base_loc, bf_loc,
                             is_battlefield)

# Action kinds. Wire format -- append only, never reorder.
(A_PASS, A_END_TURN, A_PLAY, A_PLAY_AT, A_DECLARE, A_ADD, A_COMMIT, A_CANCEL,
 A_RETREAT, A_TARGET, A_HIDE, A_HIDE_AT, A_PLAY_HIDDEN) = range(13)

KIND_NAMES = ("pass", "end_turn", "play", "play_at", "declare", "add",
              "commit", "cancel", "retreat", "target", "hide", "hide_at",
              "play_hidden")


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

    # --- mid-decision: a target slot is open ------------------------------
    # Targets are chosen one slot at a time -- the same add-one loop as a Move
    # declaration, which is why that machinery was written generically. Each
    # slot's options depend on the slots already filled (Facebreaker's "at the
    # same battlefield"), so they cannot be enumerated as a product.
    if state.pend_slot >= 0:
        item = chain.oldest_pending(state)
        if item < 0 or int(state.chain[item, C_CTRL]) != seat:
            return []
        return [Action(A_TARGET, p) for p in _slot_options(state, table, item)]

    if state.pend_hide >= 0:
        if seat != state.active:
            return []
        _, spots = chain.hideable(state, table, cfg, seat)
        return [Action(A_HIDE_AT, i) for i in spots]

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

    # --- Closed State: a Chain exists, so both players get priority -------
    # 310.2 / 310.4 and 312.2.c-d. This is the same window whether or not a
    # Showdown is running -- 342.1 says a spell played in a Showdown creates a
    # Chain as normal, so there is deliberately only one priority loop.
    if state.n_chain > 0 or state.showdown_bf >= 0:
        if seat != state.priority:
            return []
        return ([PASS]
                + [Action(A_PLAY, i) for i in
                   chain.playable_hand_indices(state, table, cfg, seat)]
                # 811.6 -- a facedown card has [Reaction], so it may be played
                # into any window, including on the opponent's turn.
                + [Action(A_PLAY_HIDDEN, i) for i in
                   chain.hidden_playable(state, table, cfg, seat)])

    # --- Main Phase, Neutral Open ----------------------------------------
    # 316.5.b: only the Turn Player may act in a Neutral Open State.
    if state.phase != MAIN or seat != state.active:
        return []

    out: list[Action] = []
    for i in _hand_choices(state, seat):
        card = int(state.hand[seat, i])
        if table.is_type(card, "Unit"):
            if plan_payment(state, table, seat, card) is None:
                continue
            out.append(Action(A_PLAY, i))
    for i in chain.playable_hand_indices(state, table, cfg, seat):
        out.append(Action(A_PLAY, i))
    hide_cards, _ = chain.hideable(state, table, cfg, seat)
    for i in hide_cards:
        out.append(Action(A_HIDE, i))
    for i in chain.hidden_playable(state, table, cfg, seat):
        out.append(Action(A_PLAY_HIDDEN, i))

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
        if not chain.pass_priority(state):
            return {}                     # 339.2 -- priority moves on
        # 339.1 -- everyone passed in sequence with nothing added.
        if state.n_chain > 0:
            log = chain.resolve_top(state, table, cfg)   # 340.1, one item
            chain.after_resolution(state)                # 340.2-340.4
            if state.n_chain == 0:
                # 340.2 -- the Chain is empty, so play returns to an Open State
                # and a Cleanup can finally happen. It could not happen during
                # resolution (321: "while Chain Items are Resolving, a Cleanup
                # cannot occur"), so a spell that moved a unit onto an enemy
                # staged a Combat that nothing had yet initiated.
                log.update(combat.cleanup(state, table, cfg,
                                          mover=int(state.active), dst=-1))
                if state.showdown_bf >= 0:
                    # 340.2.a -- when the Chain empties, Focus and Priority pass
                    # to the next player, so the DEFENDER acts first. That is
                    # the opposite of 464.2.d, which gives the Attacker Focus
                    # when a Move declaration opens the Showdown: the two paths
                    # into a Showdown hand priority to opposite players.
                    #
                    # It matters because this is the window in which the
                    # defender answers a spell that dragged a unit in -- Gust it
                    # away, or Stupefy the blocker -- before combat locks in.
                    # Confirmed with the project owner.
                    d = 1 - int(state.attacker)
                    state.focus = d
                    state.priority = d
                    state.passes = 0
            return log
        if state.showdown_bf >= 0:
            # No Chain, so the Showdown Step itself is over and Combat resumes.
            log = combat.advance_combat(
                state, table, cfg, {"combat_at": int(state.showdown_bf)})
            if state.showdown_bf < 0:
                # That Combat finished. `cleanup` resolves every staged Combat,
                # but it returns early when one YIELDS for a response window --
                # so a second staged Combat at the other battlefield was left
                # uninitiated once the first one opened a Showdown. Re-run the
                # cleanup now that we are back in an Open State.
                log.update(combat.cleanup(state, table, cfg,
                                          mover=-1, dst=-1))
            return log
        return {}

    if k == A_PLAY:
        seat = int(state.priority)        # not `active`: responses happen on
        card = int(state.hand[seat, action.arg])  # the opponent's turn too
        if table.is_type(card, "Unit"):
            state.pend_play = action.arg
            return {}
        return _play_spell(state, table, cfg, seat, action.arg)

    if k == A_TARGET:
        return _choose_target(state, table, cfg, action.arg)

    if k == A_HIDE:
        state.pend_hide = action.arg
        return {}

    if k == A_HIDE_AT:
        return _hide_at(state, table, cfg, seat, action.arg)

    if k == A_PLAY_HIDDEN:
        return _play_from_hidden(state, table, cfg, int(state.priority),
                                 action.arg)

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


def _slot_options(state: GameState, table: CardTable, item: int) -> list[int]:
    """Legal permanents for the slot currently being filled."""
    card = int(state.chain[item, C_CARD])
    spec = spec_for(table, card)
    assert spec is not None
    seat = int(state.chain[item, C_CTRL])
    slot = int(state.pend_slot)
    chosen = [int(x) for x in state.chain_targets[item, :slot]]
    # `choosable_targets`, not `legal_targets`: a choice that leaves a later
    # slot unfillable is itself illegal (359.3.e.14.a) and would deadlock.
    return rsv.choosable_targets(state, table, spec, slot, seat, chosen,
                                 int(state.chain[item, C_BOUND_BF]))


def _play_spell(state: GameState, table: CardTable, cfg: Config, seat: int,
                hand_idx: int) -> dict:
    """Announce a spell: it goes on the Chain Pending, then targets are chosen.

    The card leaves hand now but does **not** resolve -- that is the whole point
    of the Chain. It waits for a priority window in which the opponent may
    respond, and only resolves when everyone passes (339.1).
    """
    card = int(state.hand[seat, hand_idx])
    n = int(state.n_hand[seat])
    state.hand[seat, hand_idx:n - 1] = state.hand[seat, hand_idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1

    item = chain.push(state, card, seat, from_hand=True, bound_bf=-1)
    spec = spec_for(table, card)
    assert spec is not None, f"{table.names[card]!r} has no spec"
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _choose_target(state: GameState, table: CardTable, cfg: Config,
                   perm: int) -> dict:
    item = chain.oldest_pending(state)
    assert item >= 0 and state.pend_slot >= 0, "no slot open"
    chain.set_target(state, item, int(state.pend_slot), perm)

    spec = spec_for(table, int(state.chain[item, C_CARD]))
    assert spec is not None
    if state.pend_slot + 1 < spec.n_targets:
        state.pend_slot = int(state.pend_slot) + 1
        return {}
    return _finalize_pending(state, table, cfg, item)


def _finalize_pending(state: GameState, table: CardTable, cfg: Config,
                      item: int) -> dict:
    """337.1 -- pay costs and mark Finalized. Does not pass priority (337.1.a).

    Costs are paid here rather than on announcement because that is when the
    rules say a card is played (349), and it matters: a card whose targets all
    became illegal before finalization never gets played, and never gets paid
    for.
    """
    card = int(state.chain[item, C_CARD])
    seat = int(state.chain[item, C_CTRL])
    if int(state.chain[item, C_BOUND_BF]) < 0:
        # 811.1.b -- a card played from Hidden ignores its cost entirely. The
        # rune was already paid when it was hidden.
        recycle = plan_payment(state, table, seat, card)
        assert recycle is not None, "unaffordable spell reached finalization"
        pay(state, table, seat, card, recycle)
    chain.finalize(state, item)
    # 337.1.a: the caster keeps priority, so they may respond to their own card.
    state.priority = seat
    return {"finalized": table.names[card],
            "targets": [int(x) for x in
                        state.chain_targets[item, :spec_for(table, card).n_targets]]}


def _hide_at(state: GameState, table: CardTable, cfg: Config, seat: int,
             bf: int) -> dict:
    """Hide the pending card facedown at `bf` for one rune (811.1.b).

    Hide is not a Play (811.1.c.1) and opens no Chain (811.1.c.2), so this
    resolves immediately and cannot be responded to. `fd_ply` records when, so
    the "beginning on the NEXT turn" clause can be enforced.
    """
    idx = int(state.pend_hide)
    card = int(state.hand[seat, idx])
    n = int(state.n_hand[seat])
    state.hand[seat, idx:n - 1] = state.hand[seat, idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1
    state.pend_hide = -1

    dom = int(np.argmax(state.runes_ready[seat]))     # pay [A]: any one rune
    assert state.runes_ready[seat, dom] > 0, "hide with no ready rune"
    state.runes_ready[seat, dom] -= 1
    state.runes_spent[seat, dom] += 1

    state.fd_owner[bf] = seat
    state.fd_card[bf] = card
    state.fd_ply[bf] = int(state.ply)
    return {"hid_at": bf}


def _play_from_hidden(state: GameState, table: CardTable, cfg: Config,
                      seat: int, bf: int) -> dict:
    """Play the facedown card at `bf` for 0 energy (811.1.b).

    Its bound target slots are restricted to that battlefield (811.1.d.2.a),
    which is carried on the chain item as `C_BOUND_BF` -- free slots ignore it,
    which is why Smoke and Mirrors still reaches across the board.
    """
    card = int(state.fd_card[bf])
    assert int(state.fd_owner[bf]) == seat, "not this seat's facedown card"
    state.fd_owner[bf] = -1
    state.fd_card[bf] = -1
    state.fd_ply[bf] = -1

    item = chain.push(state, card, seat, from_hand=False, bound_bf=bf)
    spec = spec_for(table, card)
    assert spec is not None
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced_from_hidden": table.names[card], "at": bf}
    return _finalize_pending(state, table, cfg, item)


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
    if state.pend_slot >= 0:
        item = chain.oldest_pending(state)
        if item >= 0:
            return int(state.chain[item, C_CTRL])
    if state.n_chain > 0 or state.showdown_bf >= 0:
        return int(state.priority)
    return int(state.active)
