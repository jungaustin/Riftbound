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

from rl.engine.state import (N_BF, N_SEATS, P_ALIVE, P_CTRL, P_DMG, P_LOC,
                             P_READY, GameState, bf_index, is_battlefield)


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
    for i in range(N_BF):
        ctrl = int(state.bf_ctrl[i])
        if ctrl < -1 or ctrl >= N_SEATS:
            _fail(f"battlefield {i} has invalid controller {ctrl}")
        # 107.3.c -- only the controller of a battlefield may occupy its
        # Facedown Zone.
        owner = int(state.fd_owner[i])
        if owner >= 0:
            if int(state.fd_card[i]) < 0:
                _fail(f"battlefield {i} facedown owner set with no card")
            if owner != ctrl:
                _fail(f"battlefield {i} facedown owned by {owner} but "
                      f"controlled by {ctrl} (107.3.c)")
        elif int(state.fd_card[i]) >= 0:
            _fail(f"battlefield {i} facedown card set with no owner")

    # --- showdown ----------------------------------------------------------
    if state.showdown_bf >= N_BF:
        _fail("showdown at a nonexistent battlefield")
    if state.showdown_bf >= 0 and not state.bf_contested[state.showdown_bf]:
        _fail("showdown in progress at an uncontested battlefield")
    if (state.attacker >= 0) != (state.showdown_bf >= 0):
        _fail("attacker designation and showdown disagree")

    # No Battlefield may hold units from both players once combat is over. A
    # staged Combat (461) that never resolved is the single most likely bug in
    # the move/showdown path, and it is invisible without this check: the
    # position just quietly stops obeying rule 466.1.a.2.
    # ...but only in an OPEN state. 321 forbids a Cleanup while Chain Items are
    # resolving, so a spell that moves a unit onto an enemy legitimately leaves
    # the combat *staged but not initiated* until the Chain empties. Asserting
    # this unconditionally was wrong: it fired on correct play once movement
    # spells existed.
    if state.showdown_bf < 0 and state.is_open:
        for i in range(N_BF):
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
        if state.pend_play >= state.n_hand[state.pend_play_seat]:
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
        if A.A_PLAY in kinds:
            if seat != int(state.priority):
                _fail(f"play offered to seat {seat}, who does not have priority,"
                      f" on seat {state.active}'s turn")
            if state.n_chain == 0 and state.showdown_bf < 0:
                _fail(f"play offered to seat {seat} on seat {state.active}'s "
                      f"turn with no Chain and no Showdown to respond in")

    # A card offered must actually be playable at this speed right now.
    for a in actions:
        if a.kind != A.A_PLAY:
            continue
        card = int(state.hand[seat, a.arg])
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
    for a in actions:
        if a.kind == A.A_PLAY:
            card = int(state.hand[seat, a.arg])
            if A.plan_payment(state, table, seat, card) is None:
                _fail(f"unaffordable card offered from hand index {a.arg}")
