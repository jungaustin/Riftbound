"""Runtime invariant checks, run after every mutation in debug mode.

PLAN.md Phase 0. These exist because the M1 gate is "100,000 random games, no
crashes, no illegal states" -- and an illegal state that does not crash is the
expensive kind. Each check here corresponds to a rule that a refactor could
silently break.

Cost is real (a few array ops per call), so this is gated behind a flag and
turned off for training runs. Turn it back on the moment anything looks wrong.
"""

from __future__ import annotations

import numpy as np

from rl.engine.effects import play_from_look_cost
from rl.engine.state import (MAX_HAND, N_BF, N_SEATS, P_ALIVE, P_ATTACHED_TO,
                             P_CTRL, P_DMG, P_LOC,
                             P_READY, GameState, bf_index, fd_slots,
                             is_battlefield)


class InvariantError(AssertionError):
    pass


def _fail(msg: str) -> None:
    raise InvariantError(msg)


def check(state: GameState, card_might: np.ndarray | None = None) -> None:
    """Assert every structural invariant. Raises `InvariantError` on violation."""
    p = state.perms[:state.n_perms]

    # --- points (rule 194.4: cannot go below zero) -------------------------
    if np.any(state.points < 0):
        _fail(f"negative points: {state.points.tolist()}")

    # --- permanents --------------------------------------------------------
    if state.n_perms and np.any((p[:, P_CTRL] < 0) | (p[:, P_CTRL] >= N_SEATS)):
        _fail("permanent with out-of-range controller")
    live = p[p[:, P_ALIVE] == 1] if state.n_perms else p
    if live.size:
        if np.any((live[:, P_LOC] < 0) | (live[:, P_LOC] >= N_SEATS + N_BF)):
            _fail("live permanent at an invalid location")
        if np.any(live[:, P_READY] > 1) or np.any(live[:, P_READY] < 0):
            _fail("permanent ready flag is not boolean")
        if np.any(live[:, P_DMG] < 0):
            _fail("permanent with negative damage")

    # --- attachment (716-719) ---------------------------------------------
    # `P_ATTACHED_TO` is a row index stored INSIDE `perms`, which is the one
    # kind of reference `compact_permanents` has no general machinery for -- so
    # a stale link here is the failure mode to expect, and it is silent: the
    # index stays in range and simply names the wrong card.
    # `n_attached` is denormalised -- it exists only so `attachments` can skip
    # the scan on a board with no Equipment. Recomputed here every call, because
    # a count maintained by four separate writers is exactly the thing that
    # drifts silently, and a drift DOWN would make live attachments invisible
    # rather than crash.
    live_att = int((state.perms[:state.n_perms, P_ATTACHED_TO] >= 0).sum())
    if int(state.n_attached) != live_att:
        _fail(f"n_attached is {int(state.n_attached)} but {live_att} rows are "
              f"Attached -- the denormalised count has drifted")
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        up = int(state.perms[i, P_ATTACHED_TO])
        if up < 0:
            continue
        if up == i:
            _fail(f"permanent {i} is attached to itself")
        if up >= state.n_perms or state.perms[up, P_ALIVE] != 1:
            _fail(f"permanent {i} is attached to dead or missing row {up} -- "
                  f"719.5 should have detached it as that card left the board")
        # 719.3 -- "A Top-Most Card and all cards Attached to it are at the
        # same location." Every location write goes through `set_location`
        # precisely so this holds; a mismatch means one slipped past it.
        elif int(state.perms[i, P_LOC]) != int(state.perms[up, P_LOC]):
            _fail(f"719.3 -- attached {i} at {int(state.perms[i, P_LOC])} but "
                  f"its Top-Most {up} is at {int(state.perms[up, P_LOC])}")
        # Damage used to be combat-only, so "any damage outside a Showdown is a
        # missed heal" held. It stopped holding the moment a spell could deal
        # damage: Falling Star marks 3 on a 5-Might unit in an Open State and it
        # legitimately stays there until the end-of-turn heal (317.2).
        #
        # The invariant that survives is 143.2.a: a LIVE unit must never be
        # carrying lethal damage, because it would already have been killed.
        # That still catches a missed kill check, which is the bug that
        # mattered.
        if card_might is not None:
            for row in live:
                m = int(card_might[int(row[0])]) + int(row[8])
                if int(row[P_DMG]) > 0 and int(row[P_DMG]) >= max(0, m):
                    _fail("a live unit is carrying lethal damage -- the "
                          "143.2.a kill check was missed")

    # --- runes -------------------------------------------------------------
    if np.any(state.runes_ready < 0) or np.any(state.runes_spent < 0):
        _fail("negative rune count")

    # --- chain / four-state coherence (rules 308-310) ---------------------
    if state.n_chain < 0 or state.n_chain > state.chain.shape[0]:
        _fail("chain length out of range")
    if state.is_open and state.n_chain != 0:
        _fail("is_open disagrees with chain length")

    # --- battlefields ------------------------------------------------------
    for i in state.live_bfs():
        ctrl = int(state.bf_ctrl[i])
        if ctrl < -1 or ctrl >= N_SEATS:
            _fail(f"battlefield {i} has invalid controller {ctrl}")
        # 107.3.c -- only the controller of a battlefield may occupy its
        # Facedown Zone.
        for k in fd_slots(i):
            owner = int(state.fd_owner[k])
            if owner >= 0:
                if int(state.fd_card[k]) < 0:
                    _fail(f"facedown slot {k} owner set with no card")
                if owner != ctrl:
                    _fail(f"facedown slot {k} owned by {owner} but battlefield "
                          f"{i} controlled by {ctrl} (107.3.c)")
            elif int(state.fd_card[k]) >= 0:
                _fail(f"facedown slot {k} card set with no owner")

    # --- showdown ----------------------------------------------------------
    if state.showdown_bf >= N_BF:
        _fail("showdown at a nonexistent battlefield")
    if state.showdown_bf >= 0 and not state.bf_contested[state.showdown_bf]:
        _fail("showdown in progress at an uncontested battlefield")
    if (state.attacker >= 0) != (state.showdown_bf >= 0):
        _fail("attacker designation and showdown disagree")
    # **A live Showdown must have a real Focus.** 345/464.2.d give Focus to a
    # seat, and `chain.after_resolution` passes it with `1 - focus` -- so a -1
    # left over from an Open State does not stay -1, it becomes 2 and then -1
    # again, and `acting_seat` hands the driver a seat that does not exist. The
    # game then stops in a position that is neither terminal nor actionable,
    # which is scored as an undecided game with no truncation to show for it.
    # `enter_main` used to write exactly that: it ran a Cleanup that could OPEN
    # a Showdown and then reset priority and Focus for the Main Phase anyway.
    if state.showdown_bf >= 0 and not 0 <= int(state.focus) < N_SEATS:
        _fail(f"showdown at bf {int(state.showdown_bf)} with focus "
              f"{int(state.focus)} -- nobody holds it")
    if state.showdown_bf >= 0 and not 0 <= int(state.priority) < N_SEATS:
        _fail(f"showdown at bf {int(state.showdown_bf)} with priority "
              f"{int(state.priority)} -- nobody can act")

    # No Battlefield may hold units from both players once combat is over. A
    # staged Combat (461) that never resolved is the single most likely bug in
    # the move/showdown path, and it is invisible without this check: the
    # position just quietly stops obeying rule 466.1.a.2.
    # ...but only in an OPEN state. 321 forbids a Cleanup while Chain Items are
    # resolving, so a spell that moves a unit onto an enemy legitimately leaves
    # the combat *staged but not initiated* until the Chain empties. Asserting
    # this unconditionally was wrong: it fired on correct play once movement
    # spells existed.
    #
    # A queued trigger is the same situation one step earlier. 323 is an
    # ORDERED task list: triggers become Pending Chain Items (320.1) well
    # before 323.13 initiates a staged Combat, so while `state.trig` is
    # non-empty the Cleanup has not reached that task yet. The visible case is
    # 383.3.d.1 -- two simultaneous triggers whose controller must choose the
    # order -- which stops the Cleanup mid-list with a real decision pending
    # and both seats standing on the same battlefield. `actions._settle` is
    # what guarantees the queue drains and the Cleanup finishes, so this is a
    # window of exactly one decision, never a resting state.
    if state.showdown_bf < 0 and state.is_open and not state.n_trig:
        for i in state.live_bfs():
            a, b = state.seats_at(N_SEATS + i)
            if a and b:
                _fail(f"battlefield {i} has units from both seats in an Open "
                      f"State -- a staged combat was never initiated (460/461)")

    # --- scoring (rule 470) ------------------------------------------------
    if np.any((state.bf_scored < 0) | (state.bf_scored > 1)):
        _fail("bf_scored is not boolean")

    # --- pending move declaration ------------------------------------------
    if state.declaring:
        if state.decl_dst < N_SEATS or state.decl_dst >= N_SEATS + N_BF:
            _fail(f"declaration to non-battlefield location {state.decl_dst}")
        if state.showdown_bf >= 0:
            _fail("move declared while a showdown is in progress")
        for i in state.declared():
            if i >= state.n_perms:
                _fail("declaration names a nonexistent permanent")
            row = state.perms[i]
            if row[P_ALIVE] != 1:
                _fail("declaration names a dead permanent")
            if row[P_CTRL] != state.active:
                _fail("declaration names a unit the turn player does not control")
            if row[P_READY] != 1:
                _fail("declaration names an exhausted unit")
    elif state.decl_mask:
        _fail("declaration units set with no destination")

    if state.pend_play >= 0:
        # Indexed into the ANNOUNCER's hand, not the turn player's -- an
        # [Ambush] unit is announced in a response window on the opponent's
        # turn (822.1.b), and the two hands are different lengths.
        if state.pend_play_seat < 0:
            _fail("pending play with no announcing seat recorded")
        # 108.3.d -- `CHAMPION_SRC` is a deliberate out-of-range index meaning
        # "from the Champion Zone", so it is exempt from the hand bound. The
        # card must actually be there, which is the real check.
        if state.pend_play == MAX_HAND:      # actions.CHAMPION_SRC
            if int(state.champion[int(state.pend_play_seat)]) < 0:
                _fail("pending champion play with an empty Champion Zone")
        elif state.pend_play >= state.n_hand[state.pend_play_seat]:
            _fail("pending play points past the end of the hand")
        if state.declaring:
            _fail("a play and a move declaration are open at the same time")

    # --- zone capacities ---------------------------------------------------
    for s in range(N_SEATS):
        if state.n_hand[s] < 0 or state.n_hand[s] > state.hand.shape[1]:
            _fail(f"seat {s} hand size out of range")
        if state.deck_ptr[s] > state.n_deck[s]:
            _fail(f"seat {s} drew past the end of its deck")


def check_actions(state: GameState, table, cfg, seat: int, actions) -> None:
    """Invariants on the legal action list itself.

    These are properties of the *offer*, not of the position, so `check` cannot
    see them -- and they are exactly what a refactor of the enumerator breaks
    silently, because an over-permissive action list still produces a legal-
    looking game.
    """
    from rl.engine import actions as A
    from rl.engine import chain as chain_mod
    from rl.engine.combat import can_move
    from rl.engine.effects import spec_for

    kinds = {a.kind for a in actions}

    # Confirmed with the project owner: you cannot CHOOSE to move on the
    # opponent's turn. Only card effects move units then.
    if seat != state.active:
        for bad in (A.A_DECLARE, A.A_ADD, A.A_COMMIT, A.A_RETREAT):
            if bad in kinds:
                _fail(f"{A.KIND_NAMES[bad]} offered to seat {seat} on "
                      f"seat {state.active}'s turn")
        # Playing IS allowed on the opponent's turn, but only as a response:
        # you must hold priority, and there must be a window to respond in --
        # a Chain (310.2/310.4) or a Showdown. `speed_ok` then decides whether
        # the specific card may be played, which is checked below.
        # A_PLAY during a suspended look is Nocturne's permission on a card in
        # the look buffer, answered by whoever is looking -- not a response.
        if A.A_PLAY in kinds and state.pend_look < 0:
            if seat != int(state.priority):
                _fail(f"play offered to seat {seat}, who does not have priority,"
                      f" on seat {state.active}'s turn")
            if state.n_chain == 0 and state.showdown_bf < 0:
                _fail(f"play offered to seat {seat} on seat {state.active}'s "
                      f"turn with no Chain and no Showdown to respond in")

    # A card offered must actually be playable at this speed right now.
    #
    # ...unless a look is suspended: there `A_PLAY`'s arg indexes the LOOK
    # BUFFER, not the hand, so reading `state.hand` names an unrelated card --
    # and the permission comes from the effect that opened the look (Nocturne
    # plays a unit off the top mid-showdown), not from the card's own speed.
    # The priority check above already carves the same case out.
    for a in actions:
        if a.kind != A.A_PLAY or state.pend_look >= 0:
            continue
        # ...and 108.3.d lets the arg be `CHAMPION_SRC` instead of a hand
        # index, which is out of range by design.
        card = A.played_card(state, seat, int(a.arg))
        # 337.2 resolves Units and Gear immediately, without a Chain, so
        # neither has a *speed* to check -- both are Main-phase permanents.
        # Gear reached here as soon as it became playable and tripped a check
        # that was really "every non-unit is a spell".
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            continue
        spec = spec_for(table, card)
        if spec is None:
            _fail(f"card {table.names[card]!r} offered with no DSL spec")
        elif not chain_mod.speed_ok(state, cfg, seat, spec.speed):
            _fail(f"{table.names[card]!r} offered outside its speed window")

    # An activation offered must be one the engine itself would allow.
    for a in actions:
        if a.kind == A.A_ACTIVATE and a.arg not in A.activatable(
                state, table, cfg, seat):
            _fail(f"activation of permanent {a.arg} offered but not legal")

    # Every movement offered must pass the same filter the engine would apply --
    # in particular, lateral battlefield-to-battlefield movement needs [Ganking].
    if state.declaring:
        for a in actions:
            if a.kind == A.A_ADD and not can_move(state, table, cfg, a.arg,
                                                  state.decl_dst):
                _fail(f"illegal unit {a.arg} offered for a move to "
                      f"{state.decl_dst} (lateral move without [Ganking]?)")

    # An empty offer must mean the seat is genuinely not being asked. A seat that
    # has priority and no options would deadlock the driver loop.
    if not actions and A.acting_seat(state) == seat and not A.is_terminal(state):
        _fail(f"seat {seat} is to act but has no legal actions")

    # Never offer a play the player cannot pay for.
    #
    # `A_PLAY`'s arg is a HAND index at its usual offer site and a LOOK-BUFFER
    # index while a look is suspended (Nocturne's permission), so the cost to
    # check differs too: the printed one from hand, and the card's [A]
    # permission out of the buffer. Reading the hand during a look checked an
    # unrelated card's affordability -- which is how the deck fuzz caught this.
    for a in actions:
        if a.kind != A.A_PLAY:
            continue
        if state.pend_look >= 0:
            card = int(state.look_cards[a.arg])
            n = play_from_look_cost(table, card)
            if n < 0 or A.plan_wild_power(state, seat, n) is None:
                _fail(f"unpayable look-buffer play offered at slot {a.arg}")
        else:
            card = A.played_card(state, seat, int(a.arg))
            if (A.plan_payment(state, table, seat, card) is None
                    and not _affordable_by_discount(state, table, seat, card)):
                _fail(f"unaffordable card offered from "
                      f"{'the Champion Zone' if a.arg == A.CHAMPION_SRC else f'hand index {a.arg}'} "
                      f"({table.names[card]})")


def _affordable_by_discount(state: GameState, table, seat: int,
                            card: int) -> bool:
    """Is this card payable only once a cost REDUCTION the play itself provides
    is counted? The printed cost being out of reach is then not a bug.

    The three offer sites all allow one, and this check knew about none of them,
    so it read a legal play as an illegal one:

      - **A trash-tag discount** (Undying Loyalty, "{2 energy} less if you
        choose a Bird, Cat, Dog or Poro"). `chain.tag_discount_targets` offers
        the play when the *discounted* cost is affordable and then narrows the
        target slot to the qualifying trash cards, so it can never finalize
        unpayable. Caught by the v1 spell fuzz at **victory 8, seed 661**: zero
        ready runes, so 2 Energy was unreachable, but the discount took it to 0
        and the remaining 1 Power is paid by RECYCLING a rune, which needs no
        ready one. Pre-existing, and only reachable in a long game.
      - **`paid_ignores_cost` with a payable kill cost** -- the card is free
        once the cost is paid, so the printed cost is never owed.
      - **`cost_kill_discount`** (Cruel Patron and the rest): the discount is
        the kill, which happens before the cost is planned.

    Kept as a predicate on the invariant side rather than by calling the offer
    functions, which would make the check vacuous -- it re-derives the
    exemption from the card's own spec.
    """
    from rl.engine import actions as A
    from rl.engine import chain
    from rl.engine import resolve as rsv
    spec = A.spec_for(table, card)
    if spec is None:
        return False
    if chain.tag_discount_targets(state, table, seat, card, spec):
        return True
    if (spec.paid_ignores_cost and spec.cost_kill is not None
            and rsv.cost_kill_targets(state, table, spec, seat)):
        return True
    return bool(spec.cost_kill_discount
                and A._kill_discount_options(state, table, seat, card, spec))
