"""The effect DSL -- card text as data, not as code.

**What is and is not in here.** Keywords are *not* DSL. `[Action]`, `[Hidden]`,
`[Tank]`, `[Temporary]` are permissions and behaviours the engine keys off bits
in `CardTable.kw_mask`; that is PLAN.md §3's rule and it is what keeps this file
small. What needs a language is the part keyword flags cannot express: the
*effect body* and *which things it applies to*.

    Back Off:  [Hidden] [Action] Stun a unit.
               If you played this from your hand, draw 1.
               ^^^^^^^^^^^^^^^^^^^ flags     ^^^^^^^^^^^ this is the DSL's job

So a card is: a speed, a list of target slots, and a list of ops. Adding a card
is adding a data entry. Adding a *kind* of card is adding an op.

**Targets are slots, filled one at a time.** Rule 355 makes targeting a
finalization-time commitment, and 355.10 lists six things that look like targets
and are not. Getting this wrong is not a rules quibble -- "Kill a unit if it has
3 might or less" and "Kill a unit with 3 might or less" differ in whether an
opponent can respond by growing the unit (355.9.b). So a `TargetSpec` carries the
*restriction* separately from any *condition*: a restriction narrows what may be
chosen, a condition is checked at resolution and can fail.

**Locality is per slot, not per card** (811.1.d.2.a). A `[Hidden]` card played
from a Facedown Zone may only target things at *that* battlefield -- but a slot
marked free, and any effect that does not target, is unrestricted. That is why
locality lives on the slot rather than on the card: `Smoke and Mirrors` is
playable from hiding at battlefield A in response to an attack on battlefield B,
because its effect chooses units it does not target.
"""

from __future__ import annotations

from typing import NamedTuple

# --- speeds. When may this card be played? Wire format: append only. -------
SPEED_MAIN, SPEED_ACTION, SPEED_REACTION = range(3)
SPEED_NAMES = ("main", "action", "reaction")

# --- target slots ---------------------------------------------------------
TK_UNIT, TK_BATTLEFIELD = range(2)

W_ANY, W_FRIENDLY, W_ENEMY = range(3)      # relative to the caster
WHO_NAMES = ("any", "friendly", "enemy")

# Locality of a slot when the card is played from a Facedown Zone (811.1.d.2.a).
LOC_FREE, LOC_BOUND = range(2)

# Relations between slots. `Facebreaker` needs "at the same battlefield";
# `Smoke and Mirrors` needs "at a different location".
REL_NONE, REL_SAME_BF, REL_DIFFERENT_LOC = range(3)

# --- ops ------------------------------------------------------------------
OP_STUN, OP_DRAW, OP_SWAP_LOC = range(3)
OP_NAMES = ("stun", "draw", "swap_loc")

# --- conditions, checked at resolution ------------------------------------
COND_NONE, COND_FROM_HAND, COND_ANY_TARGET_TEMPORARY = range(3)


class TargetSpec(NamedTuple):
    """One target slot. Restrictions here narrow what is *legal to choose*."""
    kind: int = TK_UNIT
    who: int = W_ANY
    locality: int = LOC_BOUND
    rel: int = REL_NONE
    rel_to: int = -1          # index of the earlier slot `rel` refers to
    max_might: int = -1       # 355.9.b "with N might or less"; -1 = no limit
    at_battlefield: bool = False   # must be at a Battlefield, not a base


class Op(NamedTuple):
    op: int
    target: int = -1          # index into the card's target slots, or -1
    target_b: int = -1        # second slot, for two-place ops like swap
    n: int = 0                # numeric parameter (cards drawn, damage dealt)
    cond: int = COND_NONE


class CardSpec(NamedTuple):
    speed: int
    targets: tuple[TargetSpec, ...] = ()
    ops: tuple[Op, ...] = ()

    @property
    def n_targets(self) -> int:
        return len(self.targets)


# ---------------------------------------------------------------------------
# The card data. This is the part that grows; everything above is fixed.
# ---------------------------------------------------------------------------
# Each entry is a transcription of the printed text. Keep the text in the
# comment so a future reader can check the transcription without the card.

SPECS: dict[str, CardSpec] = {

    # [Hidden] [Action] [Stun] a unit.
    # If you played this from your hand, draw 1.
    "Back Off": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_STUN, target=0),
             Op(OP_DRAW, n=1, cond=COND_FROM_HAND)),
    ),

    # [Hidden] [Action] Stun a friendly unit and an enemy unit at the same
    # battlefield.
    "Facebreaker": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),
                 TargetSpec(who=W_ENEMY, at_battlefield=True,
                            rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_STUN, target=0), Op(OP_STUN, target=1)),
    ),

    # [Hidden] [Action] Choose a unit you control and another unit you control
    # at a different location. If at least one of them has [Temporary], move
    # each to the other's location. Draw 1.
    #
    # "Choose", not "target" (355.10.a): the units are NOT targets, so the
    # locality rule does not bind them and this is playable from hiding at a
    # battlefield that is not the one being attacked. Both slots are LOC_FREE
    # for exactly that reason -- it is the case the project owner used to
    # correct an earlier reading, and the reason locality is per slot.
    "Smoke and Mirrors": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),
                 TargetSpec(who=W_FRIENDLY, locality=LOC_FREE,
                            rel=REL_DIFFERENT_LOC, rel_to=0)),
        ops=(Op(OP_SWAP_LOC, target=0, target_b=1,
                cond=COND_ANY_TARGET_TEMPORARY),
             Op(OP_DRAW, n=1)),
    ),
}


def spec_for(table, card: int) -> CardSpec | None:
    """The spec for a card id, or None if it is not implemented yet."""
    return SPECS.get(table.names[card])


def implemented(table) -> list[int]:
    """Card ids with a spec. The v1 spell pool grows by extending SPECS."""
    return [c for c in range(table.n) if table.names[c] in SPECS]
