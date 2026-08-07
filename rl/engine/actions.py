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
from rl.engine.cost import (MULTI_DOMAIN_POWER_IS_PERMISSIVE, accelerate_cost,
                            card_domains, pay, plan_payment)
from rl.engine.cardtable import CardTable
from rl.engine.effects import TR_PLAY_ME, spec_for
from rl.engine.state import (C_ABIL, C_BOUND_BF, C_CARD, C_CTRL, C_SRC, MAIN,
                             MAX_CHAIN, N_BF,
                             N_DOMAINS, N_SEATS, P_ALIVE, P_CARD, P_CTRL,
                             P_LOC, P_READY, GameState, base_loc, bf_loc,
                             is_battlefield)

# Action kinds. Wire format -- append only, never reorder.
(A_PASS, A_END_TURN, A_PLAY, A_PLAY_AT, A_DECLARE, A_ADD, A_COMMIT, A_CANCEL,
 A_RETREAT, A_TARGET, A_HIDE, A_HIDE_AT, A_PLAY_HIDDEN,
 A_ACCEPT, A_DECLINE, A_PLAY_AT_FAST) = range(16)

KIND_NAMES = ("pass", "end_turn", "play", "play_at", "declare", "add",
              "commit", "cancel", "retreat", "target", "hide", "hide_at",
              "play_hidden", "accept", "decline", "play_at_fast")


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

    **A Unit may only be played to its controller's base or a Battlefield they
    already control.** 806.3 and 813.3.a both state this as the inherent
    restriction on playing Units, in identical words, while explaining that
    [Action] and [Reaction] do not lift it. This engine used to offer every
    Battlefield, which made playing onto an empty one a free Conquer that
    skipped the Move -- and a Move is the only thing that starts a Combat, so
    the cheapest way to take ground was to never fight for it.

    The restriction is what four separate printed texts exist to grant
    exceptions to, and every one of them was a dead letter while any
    Battlefield was legal:

        [Ambush]                    "I may be played to a battlefield where you
                                     control Units" (822.1.b)
        Rengar, Trophy Hunter       "...where there are enemy units"
        Rengar - Pouncing           "...you're attacking"
        Ocean Drake                 "You may play me to an open battlefield"

    None of those permissions are implemented yet, so this is deliberately the
    unmodified default. Gear is base-only (149.2) unless played from Hidden
    (811.1.d.1.a), which v0 does not reach.
    """
    if not table.is_type(card, "Unit"):
        return [base_loc(seat)]
    return ([base_loc(seat)]
            + [bf_loc(i) for i in range(N_BF) if int(state.bf_ctrl[i]) == seat])


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

    # 383.3.a -- a Triggered Ability whose effect BEGINS with "you may" is
    # accepted or declined at FINALIZATION, before targets are chosen. That
    # timing is the whole point: declining removes it from the chain and it
    # counts as never having triggered (383.3.a.2), so it cannot be responded
    # to and it never sees the board it would have changed. A "you may" later
    # in the text is a different thing, decided on resolution (383.3.a.3).
    if state.pend_may >= 0:
        item = int(state.pend_may)
        if int(state.chain[item, C_CTRL]) != seat:
            return []
        return [Action(A_ACCEPT), Action(A_DECLINE)]

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
        dsts = play_destinations(state, table, cfg, seat, card)
        out = [Action(A_PLAY_AT, loc) for loc in dsts]
        # 805.2 -- [Accelerate] is an Optional Additional Cost paid *as* the
        # unit is played, so it belongs to this decision rather than a later
        # one. Folding it into the destination choice keeps the pair atomic:
        # where to put it and whether to pay for haste are the same decision,
        # and splitting them would offer a second decision point with two
        # options and no new information.
        acc = accelerate_cost(table, card)
        if acc is not None and plan_payment(state, table, seat, card,
                                            acc[0], acc[1]) is not None:
            out += [Action(A_PLAY_AT_FAST, loc) for loc in dsts]
        return out

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
    log = _apply_one(state, table, cfg, action)
    log.update(_settle(state, table, cfg))
    return log


def _settle(state: GameState, table: CardTable, cfg: Config) -> dict:
    """Drain queued triggers onto the Chain and finalize what needs no choice.

    **One central place, deliberately.** Triggers are queued from wherever the
    condition is met -- inside combat damage, inside a Cleanup, inside a
    spell's resolution -- and every one of those sites would otherwise have to
    remember to drain the queue. Doing it once at the end of `apply` means a
    new trigger site cannot forget; the worst it can do is fire late by one
    action, and there is no priority window in between for that to matter.

    Nothing happens while a decision is already open: a queued trigger waits
    for the player to finish choosing targets rather than clobbering
    `pend_slot` mid-selection.
    """
    if (state.pend_slot >= 0 or state.pend_may >= 0 or state.pend_play >= 0
            or state.pend_hide >= 0 or state.declaring or is_terminal(state)):
        return {}
    log: dict = {}
    for _ in range(MAX_CHAIN + 1):
        if state.n_trig:
            log.update(chain.flush(state, table, cfg))
        log.update(_advance_pending(state, table, cfg))
        # A decision is required, or there is nothing left to drain.
        if state.pend_slot >= 0 or state.pend_may >= 0 or state.n_trig == 0:
            return log
    raise AssertionError("the trigger queue is not draining")


def _apply_one(state: GameState, table: CardTable, cfg: Config,
               action: Action) -> dict:
    seat = state.active
    k = action.kind

    if k == A_PASS:
        if not chain.pass_priority(state):
            return {}                     # 339.2 -- priority moves on
        # 339.1 -- everyone passed in sequence with nothing added.
        if state.n_chain > 0:
            log = chain.resolve_top(state, table, cfg)   # 340.1, one item
            chain.after_resolution(state)                # 340.2-340.4
            # 340.3 -- pending items go back to Finalize. A trigger that fired
            # during that resolution is sitting Pending right now and nothing
            # else would ever finalize it, because no player action is what put
            # it there.
            log.update(_advance_pending(state, table, cfg))
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

    if k == A_ACCEPT:
        return _accept_may(state, table, cfg)

    if k == A_DECLINE:
        return _decline_may(state, table, cfg)

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

    if k == A_PLAY_AT_FAST:
        return _resolve_play(state, table, cfg, seat, action.arg, fast=True)

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
    spec = chain.item_spec(state, table, item)
    assert spec is not None
    seat = int(state.chain[item, C_CTRL])
    slot = int(state.pend_slot)
    chosen = [int(x) for x in state.chain_targets[item, :slot]]
    # `choosable_targets`, not `legal_targets`: a choice that leaves a later
    # slot unfillable is itself illegal (359.3.e.14.a) and would deadlock.
    return rsv.choosable_targets(state, table, spec, slot, seat, chosen,
                                 int(state.chain[item, C_BOUND_BF]),
                                 int(state.chain[item, C_SRC]))


def _advance_pending(state: GameState, table: CardTable, cfg: Config) -> dict:
    """Finalize Pending items until one needs a decision (337.1.b, 359.3.b).

    A player action drives a spell straight through announce -> targets ->
    finalize, so this loop had no reason to exist. A **trigger** does not: it
    appears on the Chain without anyone having acted, and something has to
    finalize it. 359.3.b says the controller of pending items completes their
    steps before play continues, and 337.1.b says oldest first.

    Returns when the chain has no pending item, or when the oldest one is
    waiting on its controller for a "you may" (383.3.a) or a target.
    """
    log: dict = {}
    for _ in range(MAX_CHAIN + 1):
        item = chain.oldest_pending(state)
        if item < 0:
            return log
        spec = chain.item_spec(state, table, item)
        if getattr(spec, "optional", False):
            state.pend_may = item
            return log
        if spec.n_targets:
            state.pend_slot = 0
            return log
        log.update(_finalize_pending(state, table, cfg, item))
    raise AssertionError("pending chain items are not draining")


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

    spec = chain.item_spec(state, table, item)
    assert spec is not None
    if state.pend_slot + 1 < spec.n_targets:
        state.pend_slot = int(state.pend_slot) + 1
        return {}
    log = _finalize_pending(state, table, cfg, item)
    # Another trigger may still be pending behind this one (359.3.b).
    log.update(_advance_pending(state, table, cfg))
    return log


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
    state.pend_may = -1
    # A Triggered Ability has no card cost. 383.3.b's "cost within
    # instructions" -- Ekko's "Recycle me to ready your runes" -- would be paid
    # here, and no ability in the pool has one yet.
    if int(state.chain[item, C_ABIL]) >= 0:
        chain.finalize(state, item)
        state.priority = seat
        return {"finalized_ability": table.names[card]}
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


def _accept_may(state: GameState, table: CardTable, cfg: Config) -> dict:
    """383.3.a -- perform the optional Triggered Ability: carry on finalizing."""
    item = int(state.pend_may)
    state.pend_may = -1
    spec = chain.item_spec(state, table, item)
    if spec.n_targets:
        state.pend_slot = 0
        return {}
    log = _finalize_pending(state, table, cfg, item)
    log.update(_advance_pending(state, table, cfg))
    return log


def _decline_may(state: GameState, table: CardTable, cfg: Config) -> dict:
    """383.3.a.2 -- it is removed from the chain and considered not to have
    triggered. Not countered, not resolved: it never happened, so nothing that
    watches for the ability sees anything."""
    item = int(state.pend_may)
    state.pend_may = -1
    card = int(state.chain[item, C_CARD])
    chain._pop(state, item)
    log = {"declined": table.names[card]}
    log.update(_advance_pending(state, table, cfg))
    return log


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
                  seat: int, loc: int, fast: bool = False) -> dict:
    """Pay for the pending card and put it on the board.

    Units enter **exhausted** unless `[Accelerate]` was paid, so a unit played to
    a Battlefield cannot move again this turn and is locked there through the
    opponent's turn. That is the commitment, and it is why playing onto an empty
    Battlefield is a different decision from moving onto one.
    """
    idx = state.pend_play
    card = int(state.hand[seat, idx])
    extra = accelerate_cost(table, card) if fast else None
    assert not fast or extra is not None, "accelerated a card without [Accelerate]"
    ee, ep = extra if extra else (0, 0)
    recycle = plan_payment(state, table, seat, card, ee, ep)
    assert recycle is not None, "unaffordable card reached _resolve_play"
    pay(state, table, seat, card, recycle, ee, ep)

    n = int(state.n_hand[seat])
    state.hand[seat, idx:n - 1] = state.hand[seat, idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1
    state.pend_play = -1

    # 359.2.c -- units enter exhausted, unless [Accelerate] was paid. 805.6 is
    # precise that this is a REPLACEMENT: the unit "does not enter exhausted and
    # then become ready", so nothing that watches for a unit becoming ready
    # fires (805.6.a). Passing `ready=True` rather than readying afterwards is
    # what implements that distinction.
    src = state.add_permanent(card, seat, loc, ready=fast)

    # 359.2.b -- rules text executes as the permanent enters, so "When you play
    # me" triggers here, after it is on the board. 337.2 already resolved the
    # unit itself without a window; the trigger is a separate Chain Item and
    # *is* respondable.
    if chain.has_trigger(table, card, TR_PLAY_ME):
        chain.queue(state, TR_PLAY_ME, src, loc)
        # 321 -- a Cleanup cannot happen while Chain Items are pending, so the
        # Combat this unit's arrival may have staged waits. The pass loop runs
        # `cleanup` the moment the Chain empties, which is the same path a
        # spell that moves a unit already takes.
        return {"played": table.names[card], "at": loc}
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
    if state.pend_may >= 0:
        return int(state.chain[int(state.pend_may), C_CTRL])
    if state.n_chain > 0 or state.showdown_bf >= 0:
        return int(state.priority)
    return int(state.active)
