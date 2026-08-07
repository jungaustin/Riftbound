"""A greedy heuristic baseline (PLAN.md Phase 2).

Deliberately shallow -- this exists to prove the engine rewards sane play, not
to play well. If it does not crush a random agent, either the engine is wrong or
the heuristic is, and finding that out here is far cheaper than finding it out
after a training run.

Priority order, and why:

  1. **Play a unit onto an empty Battlefield.** Free points: an immediate
     Conquer with no Showdown to lose (194.1.b). A greedy agent that does not
     take free points is not a useful baseline.
  2. **Attack only when the maths says you wipe them.** Because attackers are
     Recalled if any defender survives (466.1.a.2), a failed attack achieves
     *nothing at all* -- no chip damage, no ground. So the bar is not "I win the
     fight", it is "my pool kills every defender".
  3. **Otherwise develop**, biggest body first, and never retreat.

The attack test is exact rather than heuristic, because with vanilla units the
outcome is a closed-form function of summed Might (see `combat.py`).
"""

from __future__ import annotations

import numpy as np

from rl.engine import actions as A
from rl.engine import combat
from rl.engine.state import (P_CARD, P_CTRL, GameState, bf_index,
                             is_battlefield)


def _would_wipe(state: GameState, table, cfg, dst: int,
                extra: list[int]) -> bool:
    """Would sending `extra` to `dst` destroy every defender there?

    Uses the engine's own solver, so the baseline cannot disagree with the rules
    about Tank/Backline ordering or exact-lethal spending.
    """
    seat = state.active
    foe = 1 - seat
    defenders = list(state.units_at(dst, foe))
    if not defenders:
        return True
    attackers = list(state.units_at(dst, seat)) + extra
    pool = sum(combat.might_for_pool(state, table, i) for i in attackers)
    return len(combat.solve_kills(state, table, pool, defenders)) == len(defenders)


def _can_wipe(state: GameState, table, cfg, dst: int) -> bool:
    """Could every movable unit together wipe `dst`? The go/no-go for attacking."""
    movable = combat.movable_units(state, table, cfg, dst)
    return bool(movable) and _would_wipe(state, table, cfg, dst, movable)


def _biggest_enemy(state: GameState, table, seat: int, cands):
    """Prefer stunning the largest enemy unit; fall back to the smallest friend.

    Crude on purpose. The point of the baseline is to be a *fair yardstick*, not
    to play well -- but it has to use combat tricks at all, or "beats greedy"
    silently starts measuring an opponent that ignores half the game.
    """
    enemy = [a for a in cands if state.perms[a.arg, P_CTRL] != seat]
    pool = enemy or list(cands)
    key = (max if enemy else min)
    return key(pool, key=lambda a: int(table.might[int(state.perms[a.arg, P_CARD])]))


def greedy_agent(rng: np.random.Generator):
    def choose(state: GameState, table, cfg, seat: int, legal):
        kinds = {}
        for a in legal:
            kinds.setdefault(a.kind, []).append(a)

        # Filling a target slot: stun the biggest thing that is not ours.
        if A.A_TARGET in kinds:
            return _biggest_enemy(state, table, seat, kinds[A.A_TARGET])

        if A.A_HIDE_AT in kinds:
            return kinds[A.A_HIDE_AT][0]

        # A priority window. Spend a trick only when defending a showdown --
        # that is where Stun actually converts into a kill, because the
        # attacker deals nothing and is still Recalled or destroyed.
        if A.A_PASS in kinds:
            defending = (state.showdown_bf >= 0 and int(state.attacker) != seat)
            if defending:
                for k in (A.A_PLAY_HIDDEN, A.A_PLAY):
                    if k in kinds:
                        return kinds[k][0]
            return kinds[A.A_PASS][0]

        # Mid-decision points: finish what was started.
        if A.A_PLAY_AT in kinds:
            # Prefer an uncontrolled, undefended battlefield -- that is the
            # free Conquer. Otherwise stay home.
            foe = 1 - seat
            for a in kinds[A.A_PLAY_AT]:
                if (is_battlefield(a.arg)
                        and state.bf_ctrl[bf_index(a.arg)] != seat
                        and not state.has_units_at(a.arg, foe)):
                    return a
            return next(a for a in kinds[A.A_PLAY_AT]
                        if not is_battlefield(a.arg))

        if A.A_ADD in kinds or A.A_COMMIT in kinds:
            # Recomputed each step rather than remembered: `GameState` has
            # __slots__, and a stateless agent cannot desync from the position.
            declared = state.declared()
            # Declared units have not moved yet, so they are `extra`, not
            # already-present. Getting that backwards silently commits attacks
            # that cannot win, and Recall makes those worth exactly nothing.
            if declared and _would_wipe(state, table, cfg, state.decl_dst,
                                        declared):
                return kinds[A.A_COMMIT][0]
            if A.A_ADD in kinds:
                # Add the biggest body first, so we commit the smallest group
                # that clears the bar -- everything sent is a unit not defending
                # somewhere else, and the garrison left behind is what scores.
                return max(kinds[A.A_ADD],
                           key=lambda a: combat.might_for_pool(state, table, a.arg))
            if A.A_COMMIT in kinds:
                return kinds[A.A_COMMIT][0]
            return kinds[A.A_CANCEL][0]

        if A.A_HIDE in kinds:
            return kinds[A.A_HIDE][0]

        # 1 + 3. Play a card if we have one; the destination choice above then
        # steers it onto an empty battlefield when that is available.
        if A.A_PLAY in kinds:
            return max(kinds[A.A_PLAY],
                       key=lambda a: int(table.might[int(state.hand[seat, a.arg])]))

        # 2. Attack only where we can wipe them.
        for a in kinds.get(A.A_DECLARE, []):
            if _can_wipe(state, table, cfg, a.arg):
                return a

        if A.A_END_TURN in kinds:
            return kinds[A.A_END_TURN][0]
        return legal[0]
    return choose
