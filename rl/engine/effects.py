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
TK_UNIT, TK_BATTLEFIELD, TK_SPELL, TK_LOCATION, TK_TRASH_CARD = range(5)

# The stored value of a target slot means whatever its KIND says it means:
# TK_UNIT a permanent row, TK_SPELL a Chain Item uid (C_UID), TK_LOCATION a
# location int, TK_TRASH_CARD a CARD ID. Nothing has to disambiguate them at
# runtime because the slot's kind is always known from the spec.
#
# **TK_TRASH_CARD stores the card, not the trash index, and that is the rules
# answer rather than a convenience.** 108.2.c: "Cards in each player's Trash are
# unordered. Their sequence does not matter." Two copies of one card in an
# unordered zone are indistinguishable, so there is nothing for a per-copy
# identity to mean -- and an index would be actively wrong, because the window
# between finalization and resolution (359.3.e) is exactly when another card
# dies into the trash and shifts everything after it.

W_ANY, W_FRIENDLY, W_ENEMY = range(3)      # relative to the caster
WHO_NAMES = ("any", "friendly", "enemy")

# Locality of a slot when the card is played from a Facedown Zone (811.1.d.2.a).
LOC_FREE, LOC_BOUND = range(2)

# Relations between slots. `Facebreaker` needs "at the same battlefield";
# `Smoke and Mirrors` needs "at a different location".
REL_NONE, REL_SAME_BF, REL_DIFFERENT_LOC = range(3)

# --- ops ------------------------------------------------------------------
(OP_STUN, OP_DRAW, OP_SWAP_LOC, OP_MODIFY_MIGHT, OP_COUNTER,
 OP_NO_SPELLS, OP_CREATE_TOKEN, OP_MOVE_TO, OP_RETURN_TO_HAND,
 OP_DAMAGE, OP_KILL, OP_DRAW_CONTROLLER, OP_READY,
 OP_MODIFY_MIGHT_ALL, OP_DAMAGE_ALL,
 OP_DISCARD, OP_KILL_ALL, OP_EXHAUST_ALL, OP_HEAL_AT,
 OP_ADD_ENERGY, OP_ADD_POWER, OP_BUFF, OP_BUFF_ALL_AT,
 OP_BLINK, OP_TRASH_TO_HAND) = range(25)
OP_NAMES = ("stun", "draw", "swap_loc", "modify_might", "counter",
            "no_spells", "create_token", "move_to", "return_to_hand",
            "damage", "kill", "draw_controller", "ready", "modify_might_all",
            "damage_all", "discard", "kill_all", "exhaust_all", "heal_at",
            "add_energy", "add_power", "buff", "buff_all_at", "blink",
            "trash_to_hand")

# --- pseudo target slots --------------------------------------------------
# A spell's ops address targets by slot index. A unit's ability also has to say
# "me" and "here", which are not choices and so are not slots. These negative
# indices mean exactly those, and `resolve._slot` is the one place that decodes
# them -- so every op that takes a target works with them for free.
T_SELF = -2      # the permanent the ability is printed on
T_HERE = -3      # that permanent's current location
T_CTX = -4       # the location captured when the trigger fired (359.3.f.3)
T_OWNER_BASE = -5  # the base of the unit in the op's FIRST slot ("to its base")

# --- conditions, checked at resolution ------------------------------------
(COND_NONE, COND_FROM_HAND, COND_ANY_TARGET_TEMPORARY,
 COND_ONLY_UNIT_THERE, COND_CONTROL_N_GEAR) = range(5)


class TargetSpec(NamedTuple):
    """One target slot. Restrictions here narrow what is *legal to choose*."""
    kind: int = TK_UNIT
    who: int = W_ANY
    locality: int = LOC_BOUND
    rel: int = REL_NONE
    rel_to: int = -1          # index of the earlier slot `rel` refers to
    max_might: int = -1       # 355.9.b "with N might or less"; -1 = no limit
    at_battlefield: bool = False   # must be at a Battlefield, not a base
    # Cost restrictions, for TK_SPELL. Defy: "costs no more than {4 energy}
    # and no more than {any rune}" -- energy <= 4 AND power <= 1.
    max_energy: int = -1
    max_power: int = -1
    # "another unit" on a unit's own ability: exclude the ability's source.
    # Distinct from `rel`, which relates a slot to an earlier SLOT.
    not_self: bool = False
    # "up to N" -- the slot may be left EMPTY. 355.14 lets a player choose
    # fewer targets than the maximum, so the card is still legal to play with
    # nothing to point at, and each unfilled slot simply does nothing. Without
    # this, "Deal 6 to each of up to two units" would be unplayable whenever
    # only one unit existed.
    optional: bool = False
    # For TK_TRASH_CARD: which cards in the trash the slot may name.
    # `card_type` is the printed type ("Unit", "Spell", "Gear"); a tuple means
    # "a unit OR gear", which Guardian of the Passage asks for. `tags` is a
    # tag whitelist -- Starhound's "a Bird, Cat, Dog, or Poro". Both empty means
    # any card, which is what Guerilla Warfare's keyword restriction needs once
    # it is expressed through `has_keyword` instead.
    card_type: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    has_keyword: str | None = None


class Op(NamedTuple):
    op: int
    target: int = -1          # index into the card's target slots, or -1
    target_b: int = -1        # second slot, for two-place ops like swap
    n: int = 0                # numeric parameter (cards drawn, Might delta)
    cond: int = COND_NONE
    # A card-printed Might floor, e.g. Stupefy's "to a minimum of 1 Might".
    # Stricter than the general floor of 0 in 143.2.b, and part of the effect
    # rather than a rule, which is why it lives on the Op.
    floor: int | None = None
    # For OP_CREATE_TOKEN: the token card's name, and whether the created
    # units enter ready. Units normally enter exhausted; "Play a READY
    # 3 Might Sprite" overrides that, which is most of the card's value.
    token: str | None = None
    ready: bool = False
    # For OP_MOVE_TO / OP_CREATE_TOKEN: also ready the unit afterwards.
    then_ready: bool = False
    # For OP_ADD_POWER: which domain's Power is added to the Rune Pool.
    domain: int = -1
    # For OP_BLINK: send it back to its owner's base instead of where it stood.
    to_base: bool = False


class CardSpec(NamedTuple):
    speed: int
    targets: tuple[TargetSpec, ...] = ()
    ops: tuple[Op, ...] = ()

    @property
    def n_targets(self) -> int:
        return len(self.targets)


# --- triggered abilities (382-383) ----------------------------------------
# Trigger conditions. Wire format: append only.
#
# TR_DEATH is [Deathknell] (808.1.c, "When I die, [Effect]"). TR_MOVE fires on
# the source leaving a location, and its captured `ctx` is the location it left
# -- Lillia's "play a Sprite unit token THERE" means where she came from, and
# 359.3.f.3 fixes that at trigger time, not at resolution.
(TR_PLAY_ME, TR_DEATH, TR_MOVE, TR_HOLD, TR_CONQUER,
 TR_PLAY_SPELL, TR_ACTIVATED) = range(7)
TRIGGER_NAMES = ("play_me", "death", "move", "hold", "conquer", "play_spell",
                 "activated")

# TR_ACTIVATED is not a trigger at all -- it is the marker for an ACTIVATED
# ability (151.1: "Costs followed by a ':' and then an effect"). No event ever
# fires it; the player pays and puts it on the Chain themselves via A_ACTIVATE.
# It rides the trigger machinery because 151.2.a.1 says an activated ability
# "behaves, once activated, like a spell without an associated card" -- the
# same finalization, targeting, priority and resolution a triggered ability
# already uses. Giving it its own path would duplicate all of that.

# TR_HOLD and TR_CONQUER are the two ways a battlefield Scores (469/470), and
# they fire for the units standing there rather than for the player. TR_PLAY_SPELL
# fires on its controller playing any spell -- 349 makes "played" mean finalized,
# so it fires when the spell is put on the Chain, not when it resolves.


# [Repeat] (820), not implemented yet -- the constraint is recorded because it
# is the part that is easy to get wrong. 820.1.c.3: **each Repeat cost can be
# paid only a single time.** It is an optional additional cost that buys ONE
# extra execution, not a loop, so nothing can be repeated arbitrarily by paying
# again. A card printing two separate Repeat instances (820.1.c.2, 820.3) may
# pay each once, for three executions total; that is the only way past two.
# 820.2.a: the choices for the extra execution are made at the normal time and
# need not match the first, so a repeated targeted effect needs a second set of
# target slots rather than a re-use of the first. Confirmed with the project
# owner.
REPEAT_PAYMENTS_PER_INSTANCE = 1


class Ability(NamedTuple):
    """One triggered ability. Deliberately shaped like a `CardSpec`.

    383.3 -- "a Triggered Ability behaves like an Activated Ability and is
    placed on the Chain". So it finalizes, targets, and resolves through
    exactly the machinery a spell already uses; `targets`/`ops`/`n_targets`
    match `CardSpec` so `resolve.py` needs no idea which it is holding. What a
    spell has and this does not is a *speed*: an ability is never played, so
    there is no timing permission to check.

    `optional` is 383.3.a's "you may" **as the first part of the effect**,
    which is decided at FINALIZATION, not on resolution -- declining removes
    the ability from the chain and it counts as never having triggered
    (383.3.a.2). A "you may" appearing later in the text is a different thing
    and is decided on resolution (383.3.a.3); that is a condition, not this.
    """
    trigger: int
    targets: tuple[TargetSpec, ...] = ()
    ops: tuple[Op, ...] = ()
    optional: bool = False
    # --- activated abilities only (trigger == TR_ACTIVATED) ---------------
    # 204.1.b: "on activated abilities, the Base Cost is the resource or
    # instruction written before the ':'". 151.2 restricts a Gear's activated
    # ability to its controller's Main Phase in an Open State and NOT during a
    # Showdown, which is exactly what SPEED_MAIN already means.
    speed: int = SPEED_MAIN
    cost_energy: int = 0
    cost_power: int = 0
    cost_exhaust: bool = False        # "Exhaust:" -- the source must be ready
    # 337.2 -- a resource-adding ability resolves IMMEDIATELY and never waits
    # on the Chain, so it cannot be responded to. The cards say so themselves:
    # "Abilities that add resources can't be reacted to." Without this an [Add]
    # would open a priority window in which the opponent could answer the mana
    # before it existed, which is the opposite of the rule.
    immediate: bool = False

    @property
    def n_targets(self) -> int:
        return len(self.targets)


# ---------------------------------------------------------------------------
# The card data. This is the part that grows; everything above is fixed.
# ---------------------------------------------------------------------------
# Each entry is a transcription of the printed text. Keep the text in the
# comment so a future reader can check the transcription without the card.

SPRITE_TOKEN = "Sprite (274) // Buff"   # 3 Might Fae unit token, [Temporary]

SPECS: dict[str, CardSpec] = {

    # [Reaction] Give a unit -1 Might this turn, to a minimum of 1 Might. Draw 1.
    # The most-played spell in the corpus: 57 slots across 19 of 29 decks.
    "Stupefy": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1, floor=1),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Give a unit +2 Might this turn. Draw 1.
    "Discipline": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Give a unit -4 Might this turn, to a minimum of 1 Might.
    "Smoke Screen": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-4, floor=1),),
    ),

    # [Reaction] Counter a spell. Its controller can't play spells this turn.
    "Lilting Lullaby": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL),),
        ops=(Op(OP_COUNTER, target=0), Op(OP_NO_SPELLS, target=0)),
    ),

    # [Reaction] Counter a spell that costs no more than {4 energy} and no
    # more than {any rune}.  "{any rune}" is one Power symbol of any domain.
    "Defy": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, max_energy=4, max_power=1),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # [Hidden] [Action] Play a ready 3 Might Sprite unit token with [Temporary].
    # The token card carries [Temporary] itself, so it expires through the
    # existing Beginning-Phase path -- the conquer-vs-hold inversion.
    "Sprite Call": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_LOCATION),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=SPRITE_TOKEN, ready=True),),
    ),

    # Play two ready 3 Might Sprite unit tokens with [Temporary].
    "Sprite Burst": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=2, token=SPRITE_TOKEN, ready=True),),
    ),

    # [Action] Move a friendly unit and ready it.
    "Ride The Wind": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1, then_ready=True),),
    ),

    # Move an enemy unit.  Moving an enemy INTO your units stages a Combat by
    # presence (461) -- the engine already handles that, so this is removal.
    "Charm": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),),
    ),

    # [Reaction] Return a unit at a battlefield with 3 Might or less to its
    # owner's hand.  "with 3 Might or less" is a RESTRICTION (355.9.b), so a
    # 4-Might unit was never a legal choice and buffing in response saves it.
    "Gust": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True, max_might=3),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),),
    ),

    # [Reaction] Return a friendly unit and an enemy unit to their owners' hands.
    "Star-Crossed": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_ENEMY)),
        ops=(Op(OP_RETURN_TO_HAND, target=0),
             Op(OP_RETURN_TO_HAND, target=1)),
    ),

    # [Reaction] Give a friendly unit +1 Might this turn, then an additional
    # +1 Might this turn if it is the only unit you control there.
    "En Garde": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_MODIFY_MIGHT, target=0, n=1, cond=COND_ONLY_UNIT_THERE)),
    ),

    # [Hidden] [Action] Kill a unit at a battlefield. Its controller draws 2.
    # The draw goes to the TARGET's controller, not the caster -- a different
    # recipient from every other draw in the pool, hence its own op.
    "Hidden Blade": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_KILL, target=0),
             Op(OP_DRAW_CONTROLLER, target=0, n=2)),
    ),

    # Deal 3 to a unit. Deal 3 to a unit.  Two separate instances, so two
    # target slots -- and they may be the same unit, which 6 damage on one
    # body is often the point of.
    "Falling Star": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY), TargetSpec(who=W_ANY)),
        ops=(Op(OP_DAMAGE, target=0, n=3), Op(OP_DAMAGE, target=1, n=3)),
    ),

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

    # --- transcribed one by one from the card database ---------------------
    # These need no mechanism the DSL did not already have. Kept together so
    # the batch is legible; the ordering tool is `rl/tools/triage.py`.

    # [Hidden] Banish a unit, then its owner plays it to the same location,
    # ignoring its cost.
    #
    # The unit comes back as a NEW game object: damage gone, Buff gone (705),
    # "this turn" modifiers gone, entering exhausted (359.2.c) and firing its
    # own "when you play me" triggers. That is the whole card -- it resets a
    # buffed attacker and re-triggers a friendly one.
    "Temporal Breach": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_BLINK, target=0),),
    ),

    # [Action] Banish a friendly unit, then play it to base, ignoring its cost.
    "Portal Rescue": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_BLINK, target=0, to_base=True),),
    ),

    # [Reaction] Move up to 2 friendly units to base.
    "Flash": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY, optional=True),
                 TargetSpec(who=W_FRIENDLY, optional=True)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),
             Op(OP_MOVE_TO, target=1, target_b=T_OWNER_BASE)),
    ),

    # Deal 6 to each of up to two units.
    "Singularity": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, optional=True),
                 TargetSpec(who=W_ANY, optional=True)),
        ops=(Op(OP_DAMAGE, target=0, n=6), Op(OP_DAMAGE, target=1, n=6)),
    ),

    # [Action] Return a unit at a battlefield to its owner's hand.
    "Rebuke": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),),
    ),

    # --- trash recursion ---------------------------------------------------
    # Every card below names a card in a TRASH rather than on the board, which
    # is what TK_TRASH_CARD is for. Read the note beside it in this file before
    # adding another: the slot holds a card id, not a row and not an index.

    # [Action] Return a unit from your trash to your hand.
    "Morbid Return": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_TRASH_CARD, card_type=("Unit",)),),
        ops=(Op(OP_TRASH_TO_HAND, target=0),),
    ),

    # Return up to two cards with [Hidden] from your trash to your hand.
    #
    # The second sentence ("You can hide cards ignoring costs this turn") is a
    # turn-scoped cost modifier on the Hide action and is NOT implemented, so
    # this card is deliberately absent from `plays_as_printed`. Half a card is
    # still worth having: the half that is here is the reason the card is in a
    # deck, and the coverage metric counts it honestly as missing.
    "Guerilla Warfare": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, has_keyword="Hidden",
                            optional=True),
                 TargetSpec(kind=TK_TRASH_CARD, has_keyword="Hidden",
                            optional=True)),
        ops=(Op(OP_TRASH_TO_HAND, target=0),
             Op(OP_TRASH_TO_HAND, target=1)),
    ),

    # [Action] Deal 4 to a unit at a battlefield. Draw 1.
    "Void Seeker": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=4), Op(OP_DRAW, n=1)),
    ),

    # Kill all units.  Untargeted and total -- ours too.
    "The Ruination": CardSpec(speed=SPEED_MAIN, ops=(Op(OP_KILL_ALL),)),

    # Exhaust all friendly units, then deal 12 to ALL units at battlefields.
    # The exhaust is not a cost, it is the first instruction, so it happens
    # even if the damage kills nothing.
    "Unchecked Power": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EXHAUST_ALL), Op(OP_DAMAGE_ALL, n=12)),
    ),

    # [Reaction] Discard 1, then draw 2.
    "Lunar Boon": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=2)),
    ),

    # Draw 1.  [Flow] {2 energy}
    # The Flow cost and the "then banish it" rider are keyword behaviour
    # (829), not DSL -- the spec is just the printed effect.
    "Dredge Up": CardSpec(speed=SPEED_MAIN, ops=(Op(OP_DRAW, n=1),)),

    # [Action] Give a unit +5 Might this turn.
    "Punch First": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=5),),
    ),

    # [Action] Stun a unit.
    "Rune Prison": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_STUN, target=0),),
    ),

    # Draw 4.
    "Progress Day": CardSpec(speed=SPEED_MAIN, ops=(Op(OP_DRAW, n=4),)),

    # [Action] Deal 3 to a unit at a battlefield.
    "Hextech Ray": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=3),),
    ),

    # [Reaction] Give two friendly units each +2 Might this turn.
    # "two friendly units" is two slots; `legal_targets` already refuses to
    # fill a slot with a permanent an earlier slot took, so they are distinct.
    "Back to Back": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_FRIENDLY)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_MODIFY_MIGHT, target=1, n=2)),
    ),

    # [Reaction] Give a unit +2 Might this turn and another unit -2 Might this
    # turn.  No printed floor, so the general 143.2.b floor of 0 applies.
    "Defiant Dance": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY), TargetSpec(who=W_ANY)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_MODIFY_MIGHT, target=1, n=-2)),
    ),

    # [Reaction] Deal 1 to all units at battlefields.
    # Untargeted and unbounded, so no slots -- the same shape as Thousand-
    # Tailed Watcher's mass Might reduction, and it hits BOTH sides.
    "Flurry of Blades": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DAMAGE_ALL, n=1),),
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


# --- static abilities -----------------------------------------------------
# A trigger is an *event*: it fires, goes on the Chain, resolves, and is done.
# A static is a *continuous* property of the board -- Petal Pixie's Might
# changes the instant a Sprite arrives beside her, with nothing on the Chain and
# no window to respond in. So it cannot be an Op, and it is not recomputed at
# any particular moment: `combat.might` derives it on every read.
#
# The consequence that is easy to miss: because 143.2.a is itself a continuous
# check ("if a Unit EVER has damage equalling or exceeding its Might"), a static
# going away can kill. Killing Soul Shepherd shrinks every token she was pumping
# and any of them already carrying damage dies with her.
ST_MIGHT = 0
ST_NAMES = ("might",)

# Who a static applies to.
SC_SELF, SC_FRIENDLY_UNITS = range(2)


class Static(NamedTuple):
    """One continuous ability.

    Flat when `per_keyword` is None ("Your token units have +1 Might"), and
    scaled by a board count when it is not ("I have +1 Might for each of your
    units with [Temporary] at my battlefield").
    """
    kind: int = ST_MIGHT
    n: int = 0
    scope: int = SC_SELF
    scope_token: bool = False        # ...and only token units
    # Counting clause. `per_same_loc` is "at my battlefield"; `per_friendly`
    # is the "of your units" in the same sentence.
    per_keyword: str | None = None
    per_friendly: bool = True
    per_same_loc: bool = True


STATICS: dict[str, tuple[Static, ...]] = {

    # I have +1 Might for each of your units with [Temporary] at my battlefield.
    "Petal Pixie": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per_keyword="Temporary",
               per_friendly=True, per_same_loc=True),
    ),

    # Your token units have +1 Might.  No location clause: it reaches the whole
    # board, which is what makes it the payoff for a token deck.
    "Soul Shepherd": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, scope_token=True),
    ),
}


def statics_for(table, card: int) -> tuple[Static, ...]:
    """Every static ability printed on a card id."""
    return STATICS.get(table.names[card], ())


# ---------------------------------------------------------------------------
# Unit abilities. Same shape as SPECS, keyed the same way; a card may have
# several, which is why the value is a tuple.
# ---------------------------------------------------------------------------
RECRUIT_TOKEN = "Recruit (271) // Buff"   # 1 Might domainless unit token
BIRD_TOKEN = "Bird"                       # 1 Might with [Deflect], rule 187.7
MECH_TOKEN = "Mech"                       # 3 Might, rule 187.4

ABILITIES: dict[str, tuple[Ability, ...]] = {

    # [Tank] When you play me, move a unit from a battlefield to its base.
    # "its base" is the TARGET's owner's base, not the caster's -- moving an
    # enemy unit sends it home, not to yours.
    "Maddened Marauder": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When you play me, if you control 3 or more other gear, draw 1.
    # A CONDITION, not a restriction: the card is played regardless and the
    # draw simply fails when the board does not support it.
    "Patched Porobot": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_CONTROL_N_GEAR, floor=3),)),
    ),

    # [Reaction] When you play me, heal your units here, then move an enemy
    # unit from here to its base.
    "Janna - Savior": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
                ops=(Op(OP_HEAL_AT, target=T_HERE),
                     Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE))),
    ),

    # [Tank] When you play me, draw 1.
    # [Tank] is a keyword flag the damage-assignment tiers already read, so the
    # DSL only owns the second sentence.
    "Lecturing Yordle": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
    ),

    # --- trash recursion, on a trigger -------------------------------------
    # 355.8 makes the empty-trash case free: an ability whose only slot has no
    # legal choice is never put on the Chain at all, so none of these deadlock
    # on turn one. That is already enforced centrally in `chain.fire`.

    # When you play me, return a unit from your trash to your hand.
    "Cemetery Attendant": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, card_type=("Unit",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a spell from your trash to your hand.
    "Annie - Stubborn": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, card_type=("Spell",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a gear from your trash to your hand.
    "Aspiring Engineer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, card_type=("Gear",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a Bird, Cat, Dog, or Poro from your trash to
    # your hand. A TAG list, not a type list -- the card says nothing about
    # whether the thing it returns is a unit.
    "Starhound": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD,
                                    tags=("Bird", "Cat", "Dog", "Poro")),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When I hold, you may return a unit or gear from your trash to your hand.
    # A Hold trigger, so it pays off a battlefield that survived the opponent's
    # whole turn -- and "unit or gear" is why `card_type` is a tuple.
    "Guardian of the Passage": (
        Ability(TR_HOLD, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD,
                                    card_type=("Unit", "Gear")),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, play a ready 3 Might Sprite unit token with [Temporary]
    # here.  "here" is my location -- not a choice, so not a target slot.
    "Sprite Mother": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When you play me, play a 1 Might Recruit unit token here.
    "Faithful Manufactor": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # When you play me, deal 6 to an enemy unit at a battlefield.
    "Riptide Rex": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
                ops=(Op(OP_DAMAGE, target=0, n=6),)),
    ),

    # When you play me, ready another unit.
    # "another" excludes me, which `REL_DIFFERENT` cannot express -- the
    # relation is to the SOURCE, not to an earlier slot -- so the slot carries
    # `not_self` and `_matches` checks it against the ability's source.
    "First Mate": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, not_self=True),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # [Accelerate] When I move from a location, play a 3 Might Sprite unit
    # token with [Temporary] there.
    #
    # "there" is the location she LEFT, and by the time this resolves she is
    # somewhere else -- so it cannot be read off her row and must come from
    # `ctx`, captured when the trigger fired (359.3.f.3). No "ready": unlike
    # Sprite Mother's token this one enters exhausted.
    "Lillia - Fae Fawn": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_CTX, n=1,
                        token=SPRITE_TOKEN),)),
    ),

    # [Accelerate] When you play me, give enemy units -3 Might this turn, to a
    # minimum of 1 Might.
    #
    # "enemy units" with no count and no choice: not targets (355.10), so no
    # slot and no restriction -- it simply applies to all of them.
    "Thousand-Tailed Watcher": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_MODIFY_MIGHT_ALL, n=-3, floor=1),)),
    ),

    # [Shield] When I hold, play a ready 3 Might Sprite unit token with
    # [Temporary] here.
    "Trevor Snoozebottom": (
        Ability(TR_HOLD,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When you play a spell, give me +1 Might this turn.
    # "me" is the source, which is not a target -- hence T_SELF.
    "Ravenbloom Student": (
        Ability(TR_PLAY_SPELL,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # [Accelerate] When I conquer, draw 1.
    "Kai'Sa, Survivor": (
        Ability(TR_CONQUER, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When I move, draw 1.
    "Stellacorn Herder": (
        Ability(TR_MOVE, ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Deathknell][>] Play a 1 Might Bird unit token with [Deflect] to your base.
    "Carrion Dredger": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=BIRD_TOKEN),)),
    ),

    # When you play me, play a 1 Might Bird unit token with [Deflect] here.
    "Frisky Hunter": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=BIRD_TOKEN),)),
    ),

    # [Deathknell] - Play two 3 Might Mech unit tokens to your base.
    # Unblocked by the rule-187 token supplement; target -1 defaults to the
    # controller's base, which is what the card says.
    "Ferrous Forerunner": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, n=2, token=MECH_TOKEN),)),
    ),

    # When you play me, buff another friendly unit.
    "Pit Rookie": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # [Legion] - When you play me, buff me.  [Legion] is unread, so this is
    # listed but will not count as printed until the keyword lands.
    "Trifarian Gloryseeker": (
        Ability(TR_PLAY_ME, ops=(Op(OP_BUFF, target=T_SELF),)),
    ),

    # [Backline] When I hold, [Buff] all units here.
    # "all units here" is untargeted and hits both sides.
    "Enthusiastic Promoter": (
        Ability(TR_HOLD, ops=(Op(OP_BUFF_ALL_AT, target=T_HERE),)),
    ),

    # [Deathknell] - Draw 1.
    "Watchful Sentry": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=1),)),
    ),


    # --- the Seal cycle: "Exhaust: [Reaction] - [Add] {X rune}" -------------
    # 337.2 makes a resource-adding ability resolve immediately, so `immediate`
    # keeps it off the Chain entirely.
    "Seal of Strength": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=0),)),
    ),
    "Seal of Focus": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=1),)),
    ),
    "Seal of Discord": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=2),)),
    ),
    "Seal of Rage": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=3),)),
    ),
    "Seal of Insight": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=4),)),
    ),
    "Seal of Unity": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=5),)),
    ),

    # Exhaust: [Reaction] - [Add] {1 energy}.
    "Energy Conduit": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, ops=(Op(OP_ADD_ENERGY, n=1),)),
    ),

    # Exhaust: Play three 1 Might Recruit unit tokens.
    "Vanguard Armory": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                ops=(Op(OP_CREATE_TOKEN, n=3, token=RECRUIT_TOKEN),)),
    ),

    # Exhaust: Give a unit +3 Might this turn.
    # The cost is the whole "Exhaust:" clause; the effect follows the colon.
    "Heart of Dark Ice": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),)),
    ),

    # [Temporary]
    # When you play this, play a ready 3 Might Sprite unit token with
    # [Temporary] to your base.
    # [Deathknell][>] Repeat this gear's play effect.
    #
    # The single most-played card in the corpus (39 slots) and the engine of
    # every Sprite deck: [Temporary] kills it at the start of each Beginning
    # Phase, its Deathknell repeats the play effect, so it makes a Sprite when
    # it lands and another one every time it expires. "Repeat this gear's play
    # effect" is the same op, which is why both abilities are literally the
    # same line -- no Repeat machinery involved (820 is a paid additional cost;
    # this is printed text).
    "Sprite Fountain": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=SPRITE_TOKEN, ready=True),)),
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=SPRITE_TOKEN, ready=True),)),
    ),

    # Ferrous Forerunner, Carrion Dredger and Honest Broker are deliberately
    # absent. Their Deathknells play Mech, Bird and Gold tokens, and none of
    # those token cards exist in `data/cards.json` -- only Recruit and Sprite
    # do. There is nothing to instantiate, so they stay substituted rather
    # than approximated with the wrong body.
}


def spec_for(table, card: int) -> CardSpec | None:
    """The spec for a card id, or None if it is not implemented yet."""
    return SPECS.get(table.names[card])


def abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every triggered ability printed on a card id."""
    return ABILITIES.get(table.names[card], ())


def implemented(table) -> list[int]:
    """Card ids with a spec. The v1 spell pool grows by extending SPECS."""
    return [c for c in range(table.n) if table.names[c] in SPECS]
