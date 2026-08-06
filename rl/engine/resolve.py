"""The DSL interpreter: which targets are legal, and what happens on resolution.

Two halves, and the rules put a hard wall between them.

**Legality (355).** A target is chosen when the card is *finalized*, and every
restriction is checked then. `legal_targets` answers "what may fill slot k,
given the slots already filled". Slots fill one at a time, reusing the same
add-one/COMMIT machinery as a Move declaration -- which is why that machinery
was built generically in the first place.

**Resolution (359.3.e).** Between finalization and resolution the board can
change, so targets are re-checked on the way in. A target that became illegal is
skipped; if *every* target became illegal the whole effect is countered
(359.3.e.5/e.6). This is the difference that makes response windows matter, and
it is why `[Stun]` has to be a real status rather than a subtraction applied at
finalization.

The distinction the rules care about most, and the one worth getting right here:
a **restriction** narrows what may be chosen (checked at finalization, and again
at resolution), while a **condition** is checked only at resolution and can
simply fail. "Kill a unit with 3 might or less" is a restriction -- a 4-might
unit was never a legal choice. "Kill a unit if it has 3 might or less" is a
condition -- any unit is a legal target, and growing it in response makes the
spell fizzle (355.9.b).
"""

from __future__ import annotations

from rl.config import Config
from rl.engine import phases
from rl.engine.cardtable import CardTable
from rl.engine.effects import (COND_ANY_TARGET_TEMPORARY, COND_FROM_HAND,
                               COND_NONE, LOC_BOUND, OP_DRAW, OP_STUN,
                               OP_SWAP_LOC, REL_DIFFERENT_LOC, REL_NONE,
                               REL_SAME_BF, TK_UNIT, W_ANY, W_ENEMY,
                               W_FRIENDLY, CardSpec, Op, TargetSpec)
from rl.engine.state import (P_ALIVE, P_CARD, P_CTRL, P_LOC, GameState,
                             bf_loc, is_battlefield)


def _matches(state: GameState, table: CardTable, spec: TargetSpec, perm: int,
             seat: int, chosen: list[int], bound_bf: int) -> bool:
    """Does `perm` satisfy one slot's restrictions?"""
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
        return False
    if spec.kind == TK_UNIT and not table.is_type(int(row[P_CARD]), "Unit"):
        return False

    ctrl, loc = int(row[P_CTRL]), int(row[P_LOC])
    if spec.who == W_FRIENDLY and ctrl != seat:
        return False
    if spec.who == W_ENEMY and ctrl == seat:
        return False

    if spec.at_battlefield and not is_battlefield(loc):
        return False
    if spec.max_might >= 0 and int(table.might[int(row[P_CARD])]) > spec.max_might:
        return False

    # 811.1.d.2.a -- a bound slot may only reach the battlefield the card was
    # hidden at. `bound_bf` is -1 when the card was not played from hiding, in
    # which case locality never applies.
    if bound_bf >= 0 and spec.locality == LOC_BOUND and loc != bf_loc(bound_bf):
        return False

    if spec.rel != REL_NONE and 0 <= spec.rel_to < len(chosen):
        other = chosen[spec.rel_to]
        if other < 0:
            return False
        if perm == other:
            return False                   # "another unit" is never the same one
        other_loc = int(state.perms[other, P_LOC])
        if spec.rel == REL_SAME_BF and loc != other_loc:
            return False
        if spec.rel == REL_DIFFERENT_LOC and loc == other_loc:
            return False
    return True


def legal_targets(state: GameState, table: CardTable, spec: CardSpec, slot: int,
                  seat: int, chosen: list[int], bound_bf: int) -> list[int]:
    """Permanent rows that may fill `slot`, given the slots already chosen."""
    t = spec.targets[slot]
    return [i for i in range(state.n_perms)
            if i not in chosen
            and _matches(state, table, t, i, seat, chosen, bound_bf)]


def can_be_cast(state: GameState, table: CardTable, spec: CardSpec, seat: int,
                bound_bf: int) -> bool:
    """Is there any legal way to fill every slot?

    359.3.e.14.a -- a card that cannot legally choose all its targets cannot be
    played at all. Checked greedily, which is exact for the current specs (at
    most two slots) and would need a proper matching if a card ever wanted three
    mutually-constrained targets.
    """
    chosen: list[int] = []
    for slot in range(spec.n_targets):
        opts = legal_targets(state, table, spec, slot, seat, chosen, bound_bf)
        if not opts:
            return False
        chosen.append(opts[0])
    return True


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _condition_holds(state: GameState, table: CardTable, op: Op,
                     targets: list[int], from_hand: bool) -> bool:
    if op.cond == COND_NONE:
        return True
    if op.cond == COND_FROM_HAND:
        return from_hand
    if op.cond == COND_ANY_TARGET_TEMPORARY:
        return any(table.has(int(state.perms[t, P_CARD]), "Temporary")
                   for t in targets if t >= 0)
    raise ValueError(f"unknown condition {op.cond}")


def resolve(state: GameState, table: CardTable, cfg: Config, spec: CardSpec,
            seat: int, targets: list[int], bound_bf: int,
            from_hand: bool) -> dict:
    """Apply a finalized card's ops. Returns a log dict.

    Targets are re-checked here, not trusted from finalization: the window
    between the two is exactly where a response lands (359.3.e).
    """
    log: dict = {"resolved": [], "fizzled": []}

    still_legal: list[int] = []
    chosen_so_far: list[int] = []
    for slot, t in enumerate(targets):
        ok = (t >= 0 and _matches(state, table, spec.targets[slot], t, seat,
                                  chosen_so_far, bound_bf))
        still_legal.append(t if ok else -1)
        chosen_so_far.append(t if ok else -1)

    # 359.3.e.5/e.6 -- if every target is gone, the whole thing is countered.
    if spec.n_targets and all(t < 0 for t in still_legal):
        log["countered"] = True
        return log

    for op in spec.ops:
        if not _condition_holds(state, table, op, still_legal, from_hand):
            log["fizzled"].append(op.op)
            continue

        if op.op == OP_DRAW:
            log["drew"] = phases.draw(state, op.n)
            log["resolved"].append(op.op)
            continue

        a = still_legal[op.target] if 0 <= op.target < len(still_legal) else -1
        if op.target >= 0 and a < 0:
            log["fizzled"].append(op.op)      # this target specifically is gone
            continue

        if op.op == OP_STUN:
            # `stun` returns False on a redundant stun (423.1.a.1), which
            # "when you stun an enemy unit" triggers must not fire on.
            log["stunned"] = log.get("stunned", [])
            if state.stun(a):
                log["stunned"].append(a)
        elif op.op == OP_SWAP_LOC:
            b = still_legal[op.target_b] if 0 <= op.target_b < len(still_legal) else -1
            if b < 0:
                log["fizzled"].append(op.op)
                continue
            la, lb = int(state.perms[a, P_LOC]), int(state.perms[b, P_LOC])
            state.perms[a, P_LOC], state.perms[b, P_LOC] = lb, la
            log["swapped"] = (a, b)
        else:
            raise ValueError(f"unknown op {op.op}")
        log["resolved"].append(op.op)
    return log
