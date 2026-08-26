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

# The only import in this file, and it is one-way: `state` imports nothing from
# the engine, so naming its zone constants here cannot cycle. A card that says
# "recycle that spell after you play it" has to name a zone, and inventing a
# parallel enum for the DSL would mean two lists to keep in step.
from rl.engine.state import (COST_FREE, COST_NO_ENERGY,  # noqa: F401
                             COST_PRINTED, D_ANY, DEST_BANISH, DEST_HAND,
                             DEST_RECYCLE, DEST_TOP, DEST_TRASH, MAX_DECK,
                             MAX_LOOK,
                             MAX_TARGETS, N_SEATS)

# --- speeds. When may this card be played? Wire format: append only. -------
SPEED_MAIN, SPEED_ACTION, SPEED_REACTION = range(3)
SPEED_NAMES = ("main", "action", "reaction")

# --- target slots ---------------------------------------------------------
TK_UNIT, TK_BATTLEFIELD, TK_SPELL, TK_LOCATION, TK_TRASH_CARD = range(5)

# The stored value of a target slot means whatever its KIND says it means:
# TK_UNIT a permanent row, TK_SPELL a Chain Item uid (C_UID), TK_LOCATION a
# location int, TK_TRASH_CARD an (owner, card) pair packed by `pack_trash`.
# Nothing has to disambiguate them at runtime because the slot's kind is always
# known from the spec.
#
# **TK_TRASH_CARD stores the card, not the trash index, and that is the rules
# answer rather than a convenience.** 108.2.c: "Cards in each player's Trash are
# unordered. Their sequence does not matter." Two copies of one card in an
# unordered zone are indistinguishable, so there is nothing for a per-copy
# identity to mean -- and an index would be actively wrong, because the window
# between finalization and resolution (359.3.e) is exactly when another card
# dies into the trash and shifts everything after it.
#
# **It stores WHICH TRASH alongside the card, because a card id alone is not a
# choice.** Most trash cards say "your trash" and narrow to one pile, but the
# pool also prints "cards from trashes" (Forge of the Future, Shadows of the
# Past) and "cards from opponents' trashes" (Disposal Order). When both piles
# are in scope and each holds a Sprite Call, "Sprite Call" names two different
# decisions -- and they are not interchangeable the way two copies in ONE pile
# are, because 416.1.c recycles each card to its OWNER's deck. Packing the
# owner in is what lets the destination be owner-relative without a second
# lookup that could disagree.

W_ANY, W_FRIENDLY, W_ENEMY = range(3)      # relative to the caster
WHO_NAMES = ("any", "friendly", "enemy")


def pack_trash(owner: int, card: int) -> int:
    """Pack a trash choice into the single int a target slot stores.

    Card-major so that sorting packed values groups the copies of one card
    together, which keeps the option list stable and readable.
    """
    return card * N_SEATS + owner


def unpack_trash(value: int) -> tuple[int, int]:
    """Inverse of `pack_trash`. Returns `(owner, card)`."""
    card, owner = divmod(value, N_SEATS)
    return owner, card


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
 OP_BLINK, OP_TRASH_TO_HAND, OP_PLAY_FROM_TRASH,
 OP_PLAY_UNIT_FROM_TRASH, OP_RECYCLE_FROM_TRASH,
 OP_GAIN_XP, OP_GRANT_KEYWORD, OP_LOOK_TOP, OP_EMPOWER,
 OP_CHANNEL, OP_DEATH_GUARD, OP_REVEAL_HAND,
 OP_SCORE, OP_EACH_KILLS_OWN, OP_NO_MOVE,
 OP_ANY_DAMAGE_KILLS, OP_SWAP_MIGHT,
 OP_READY_RUNES, OP_DISCARD_CHOOSE,
 OP_RECYCLE_SELF, OP_SEE_HAND, OP_SEE_FACEDOWN,
 OP_READY_LEGEND) = range(46)
OP_NAMES = ("stun", "draw", "swap_loc", "modify_might", "counter",
            "no_spells", "create_token", "move_to", "return_to_hand",
            "damage", "kill", "draw_controller", "ready", "modify_might_all",
            "damage_all", "discard", "kill_all", "exhaust_all", "heal_at",
            "add_energy", "add_power", "buff", "buff_all_at", "blink",
            "trash_to_hand", "play_from_trash",
            "play_unit_from_trash", "recycle_from_trash", "gain_xp",
            "grant_keyword", "look_top", "empower", "channel",
            "death_guard", "reveal_hand", "score", "each_kills_own",
            "no_move", "any_damage_kills", "swap_might",
            "ready_runes", "discard_choose", "recycle_self", "see_hand",
            "see_facedown", "ready_legend")

# What an op's "for each ..." clause counts, for `Op.n_from_count`. Distinct
# from the CNT_* used by a Static's scaling: these are per-OP, and they are
# defined up here because SPECS below references them.
(CT_MY_BATTLEFIELDS, CT_MY_MIGHTY_UNITS, CT_ENEMIES_AT_TARGET,
 CT_MY_OTHER_BATTLEFIELDS) = range(4)

# CT_MY_OTHER_BATTLEFIELDS is Seat of Power's "for each OTHER battlefield you
# control". Its own is excluded by LOCATION rather than by subtracting one: a
# battlefield ability fires while its own control is being established, and
# "count then subtract" would be off by one in whichever direction the write
# had not happened yet.

# --- pseudo target slots --------------------------------------------------
# A spell's ops address targets by slot index. A unit's ability also has to say
# "me" and "here", which are not choices and so are not slots. These negative
# indices mean exactly those, and `resolve._slot` is the one place that decodes
# them -- so every op that takes a target works with them for free.
T_SELF = -2      # the permanent the ability is printed on
T_HERE = -3      # that permanent's current location
T_CTX = -4       # the location captured when the trigger fired (359.3.f.3)
T_OWNER_BASE = -5  # the base of the unit in the op's FIRST slot ("to its base")
# "at YOUR base" -- the resolving player's own base. Distinct from T_HERE, which
# is wherever the source happens to stand: Gear is base-only under 149.2, but a
# Gear played from a Facedown Zone sits at a battlefield instead, and Forge of
# the Future still makes its token at the base either way.
T_MY_BASE = -6
# The permanent a trigger fired FOR, as opposed to the one it is printed on.
# Mask of Foresight watches from a base while another unit attacks: T_SELF is
# the gear, T_SUBJECT is the attacker, and "give IT +1 Might" means the latter.
T_SUBJECT = -7
# The location a Move ENDED at, captured when the trigger fired. `T_CTX` is the
# other end of the same Move -- where the unit came from -- and printed text
# picks between them by word: Lillia's "play a Sprite THERE" is the origin,
# Irresistible Faefolk's "move an enemy unit to THAT battlefield" is the
# destination. Neither is `T_HERE`, which re-reads the source's own row and so
# means "this battlefield" -- true only while the source is still standing on
# it. See `state.C_CTX2` for why all three exist.
T_CTX2 = -8
# The contested battlefield of the Combat now running (459). Not a choice and
# not anybody's "here": Cannon Barrage is played from a hand, by either player,
# and "all enemy units IN COMBAT" means the ones standing on the ground being
# fought over. Outside a Showdown it decodes to `LOC_NONE`, and a sweep scoped
# to a location that does not exist reaches nothing -- see `_sweep`.
T_COMBAT = -9

# --- conditions, checked at resolution ------------------------------------
(COND_NONE, COND_FROM_HAND, COND_ANY_TARGET_TEMPORARY,
 COND_ONLY_UNIT_THERE, COND_CONTROL_N_GEAR, COND_DIED_ALONE,
 COND_LEGION, COND_LEVEL, COND_EMPOWERED,
 COND_PLAYED_TRIO,
 COND_FEW_RUNES,
 COND_NOT_DIED_ALONE, COND_CTX_BATTLEFIELD, COND_SELF_AT_BF,
 COND_N_OTHERS_HERE, COND_OTHERS_MIGHT,
 COND_READY_ENEMY_HERE, COND_CTX2_BATTLEFIELD,
 COND_FIRST_TURN, COND_DEFENDING_ALONE,
 COND_WAS_MIGHTY, COND_FEWER_RUNES_THAN_OPP,
 COND_PAID_ADDITIONAL) = range(23)

# COND_PAID_ADDITIONAL is "when you play me, IF YOU PAID THE ADDITIONAL COST,
# ...". A snapshot on the permanent (`F_PAID_ADDITIONAL`), not a live question:
# the payment happens as the card is played and the trigger resolves a priority
# window later, by which time nothing else on the board records it. See
# `PLAY_COSTS` for the costs themselves.

# COND_WAS_MIGHTY is Unsung Hero's "[Deathknell] - If I was [Mighty], draw 2".
# Past tense, so it reads the `F_DIED_MIGHTY` snapshot taken as the unit died
# rather than its row now: by the time a Deathknell resolves the turn's Might
# modifiers may already have been swept, and 740.2's 5+ Might is exactly the
# kind of fact a buff supplies.
#
# COND_FEWER_RUNES_THAN_OPP is Forsaken Baccai's "if you control FEWER runes
# than an opponent". A comparison between two boards, which is what separates
# it from COND_FEW_RUNES's fixed threshold -- the card is a catch-up mechanic
# and turns itself off the moment the rune counts level.

# COND_FIRST_TURN is The Arena's Greatest: "at the start of EACH PLAYER'S FIRST
# Beginning Phase". `state.turn` counts ROUNDS rather than plies -- it advances
# after the second seat's turn -- so both players' first Beginning Phase falls
# on turn 1, and the condition is that plain.
#
# COND_DEFENDING_ALONE is Forbidding Waste's "while a unit here is defending
# alone". Two facts at once, and both are live: the unit must be on the
# DEFENDING side of a running combat (459 designation, not who moved), and
# 740.2.a's "alone" -- no other friendly unit at that location. A static rather
# than a trigger, so it switches off the instant a second unit arrives.

# COND_PLAYED_TRIO is Swain's "if you've played a non-token unit, a non-token
# gear, and a spell this turn" -- all three kinds, in one turn. Read off
# `state.played_types`, which is set at the moment each card is PLAYED (349)
# rather than when it resolves, so a countered spell still counts toward it.

# COND_NOT_DIED_ALONE is Loyal Poro's "If I DIDN'T die alone" -- the negation
# of the flag Lonely Poro reads, and a separate value rather than a `negate`
# field because there is exactly one card on each side and a flag that applies
# to every condition is a lot of surface for that.
#
# COND_CTX_BATTLEFIELD is Harpoon Squad's "when I move FROM a battlefield":
# TR_MOVE captures the location left behind (359.3.f.3), so the question is
# about `ctx`, not about where the unit is now.
#
# COND_SELF_AT_BF is Mischievous Marai's "when you play me TO a battlefield" --
# about the source's own location, which for a play trigger is where it landed.
#
# COND_CTX2_BATTLEFIELD is the same question asked of the OTHER end of a Move:
# Irresistible Faefolk's "when I move TO a battlefield" is about where she
# arrived, so a retreat to base must not fire it. `ctx2` rather than her row,
# because the trigger has to survive her being removed in response to it.

# COND_READY_ENEMY_HERE is Dune Drake's "if there is a READY enemy unit
# here" -- an exhausted enemy does not count, which is what makes the card
# reward attacking into a board that can still answer.

# COND_N_OTHERS_HERE is Shen's "if there is EXACTLY ONE other unit you
# control here" -- an exact count, not a threshold, so `level` is the
# number it must equal. A second friendly unit turns it off again.
#
# COND_OTHERS_MIGHT is Kinkou Initiate's "if your OTHER units have total
# Might 5 or more": the sum of every other friendly unit's EFFECTIVE
# Might (statics and buffs included), against `level` as the threshold.

# COND_FEW_RUNES is Eclipse Dragon's "if you control 4 or fewer runes" --
# a count of the rune BOARD (ready plus spent), not the rune deck, since
# that is what "control" means for a rune. The threshold rides on the Op as
# `level`, reusing the field COND_LEVEL already uses for a number.

# COND_EMPOWERED is 828.1.b.1's dependent keyword: "[Empowered] - [Text]" is
# short for "While I have the Empowered status, this card gains '[Text]'". So
# it gates a static or an op on the SOURCE's own flag, and is read live --
# unlike COND_LEGION's snapshot, the status can be gained mid-turn and the
# ability switches on the instant it is.

# COND_LEVEL is "[Level N] - while you have N+ XP, get the effect". The
# threshold rides on the Op or Static as `level`, so one condition covers all
# of [Level 3], [Level 6] and [Level 11]. Unlike [Legion] this is genuinely
# continuous -- XP does not reset, and a static gated on it switches on the
# instant the XP arrives -- so it is read LIVE in both places.

# COND_LEGION is 822's [Legion]: "get the effect if you've played another card
# this turn". On a STATIC it reads the live counter, because a cost is worked
# out as the card is played and the card itself has not been counted yet. On an
# OP it reads the F_LEGION snapshot taken when the source was played, because
# by resolution the source HAS been counted and a priority window has passed.
# Same words, two readings, and only one of them is right in each place.


class TargetSpec(NamedTuple):
    """One target slot. Restrictions here narrow what is *legal to choose*."""
    kind: int = TK_UNIT
    # Whose things this slot may name, relative to the caster. **W_ANY is not a
    # default to fall back on -- it is a printed word, or rather its absence.**
    # "Give an ENEMY unit -2 Might" and "Give a unit -2 Might" are different
    # cards, and the second one may point at your own. The same reading applies
    # to a TK_TRASH_CARD slot, where `who` selects the PILE: W_FRIENDLY is
    # "your trash", W_ENEMY is "an opponent's trash", and W_ANY is the
    # unqualified "trashes", which reaches both.
    who: int = W_ANY
    locality: int = LOC_BOUND
    rel: int = REL_NONE
    rel_to: int = -1          # index of the earlier slot `rel` refers to
    # "up to one OTHER unit" -- must differ from the unit already chosen in
    # slot N, with NO location clause. Distinct from `rel`, whose every
    # value ties the two slots' LOCATIONS together; REL_DIFFERENT_LOC in
    # particular means a different place, not a different unit, and using
    # it for "another" is a mistake this codebase has made before.
    distinct_from: int = -1
    max_might: int = -1       # 355.9.b "with N might or less"; -1 = no limit
    # "an enemy unit with LESS Might than it" (Public Execution) -- the index
    # of an earlier slot to compare against, rather than a printed number.
    # Strictly less, and both sides read effective Might.
    less_might_than: int = -1
    at_battlefield: bool = False   # must be at a Battlefield, not a base
    # The mirror: "Deal 4 to a unit in a base", "Deal 3 to a unit at a base".
    # Unqualified, so it reaches EITHER base -- narrow it with `who` to get
    # "a friendly unit at your base". Both flags false means "anywhere", which
    # is what most cards print.
    at_base: bool = False
    # For TK_SPELL: may this slot also name an ABILITY on the Chain? Eleven of
    # the thirteen counter cards say "Counter a spell" and mean only a spell;
    # Not So Fast and Repulse say "spell or ability". Units never reach the
    # Chain at all (337.2), so they are never a question here.
    chain_abilities: bool = False
    # Not So Fast: "Counter an enemy spell or ability THAT CHOOSES a friendly
    # unit or gear." A restriction on what the countered item picked, not on
    # the item itself -- so it reads that Chain Item's own chosen targets.
    # Only permanent-kind slots count: a location or a Chain-uid target is not
    # "a friendly unit or gear", and reading either as a permanent row would
    # match whichever unit happened to sit in row 0-3.
    chooses_friendly_perm: bool = False
    # For TK_BATTLEFIELD: "a battlefield where you have units" (Moonfall). A
    # restriction on the battlefield itself, so it is re-checked at resolution
    # -- the units that qualified it can be answered in the response window.
    needs_own_units: bool = False
    # Cost restrictions, for TK_SPELL. Defy: "costs no more than {4 energy}
    # and no more than {any rune}" -- energy <= 4 AND power <= 1.
    max_energy: int = -1
    max_power: int = -1
    # "another unit" on a unit's own ability: exclude the ability's source.
    # Distinct from `rel`, which relates a slot to an earlier SLOT.
    not_self: bool = False
    # "an enemy unit HERE" -- at the SOURCE's location. `rel`/`rel_to` cannot
    # express this: they point at an earlier target slot, and "here" is not a
    # choice anyone made. Meaningless on a spell, which has no location.
    same_loc_as_source: bool = False
    # "an enemy CHAOS unit or gear" -- a restriction on the target's DOMAIN.
    # -1 is no restriction, which is what almost every card prints.
    domain: int = -1
    # "an ATTACKING unit" -- 459 designates every unit the Attacker
    # controls at the contested battlefield. Only meaningful during a
    # Showdown; outside one nothing is attacking and the slot is empty.
    attacking: bool = False
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
    # "a friendly unit WITHOUT [Temporary]" (Shadow's Call). Read through
    # `combat.perm_kw`, so a unit that was GIVEN the keyword is excluded too --
    # otherwise the card would happily double up on a unit already dying.
    lacks_keyword: str | None = None
    # The slot names a card that will be PLAYED, not merely moved, so it must
    # be a card the engine can actually play: it needs a DSL spec, and its
    # controller must be able to pay whatever this play still costs. Same
    # reasoning as [Deflect]'s surcharge -- affordability is part of target
    # LEGALITY, because offering a target that cannot be finalized announces a
    # card that then deadlocks (359.3.e.14.a).
    playable: bool = False
    # Which cost that play pays -- a COST_* from state.py. The pool prints
    # three: the printed cost, "ignoring its Energy cost. (You must still pay
    # its Power cost.)", and the flat "ignoring its cost". The reminder text on
    # the middle one exists because players get it wrong, and so would this.
    playable_cost: int = COST_PRINTED
    # A TK_LOCATION slot that names where a card will be PLAYED, so it must be
    # narrowed to 806.3's "your base or a Battlefield you control" rather than
    # offering every battlefield the way a movement destination does.
    play_destination: bool = False


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
    # The N in "[Level N]", when `cond` is COND_LEVEL.
    level: int = 0
    # Read the amount off a TARGET's current Might instead of `n`. Deathgrip
    # gives "+Might equal to its Might", where "its" is the unit being killed
    # -- so the number is whatever that unit is worth at resolution, statics
    # and buffs included, which is why it cannot be baked into `n`.
    n_from_might: int = -1
    # "draw 1 FOR EACH battlefield you control" / "for each of your Mighty
    # units" -- the amount is a board count rather than a printed number.
    # -1 is none; otherwise one of the CT_* kinds, and the amount is
    # `n * count` -- so `n` is the per-unit rate, not a flat number.
    n_from_count: int = -1
    # Destination = the LOCATION of the unit chosen in slot N. Zenith Blade
    # moves a friendly unit to "that enemy unit's battlefield", which is
    # neither `T_HERE` (the source's) nor a location slot the player picked.
    loc_of_target: int = -1
    # For OP_GRANT_KEYWORD: which keyword, and whether the grant expires. The
    # pool grants both ways -- Cleave's "[Assault 3] this turn" against Shadow's
    # Call's [Temporary], which lasts until the unit leaves. `n` carries the
    # value, so a bare keyword is n=1.
    keyword: str | None = None
    grant_this_turn: bool = True
    # For OP_CREATE_TOKEN: the token card's name, and whether the created
    # units enter ready. Units normally enter exhausted; "Play a READY
    # 3 Might Sprite" overrides that, which is most of the card's value.
    token: str | None = None
    ready: bool = False
    # For OP_MOVE_TO / OP_CREATE_TOKEN: also ready the unit afterwards.
    then_ready: bool = False
    # For OP_ADD_POWER: which domain's Power is added to the Rune Pool.
    domain: int = -1
    # "an ATTACKING unit" -- 459 designates every unit the Attacker
    # controls at the contested battlefield. Only meaningful during a
    # Showdown; outside one nothing is attacking and the slot is empty.
    attacking: bool = False
    # For OP_LOOK_TOP: `n` is how many cards to look at; these say where the
    # one the player picks goes and where everything else goes. Stacked Deck is
    # "Put 1 into your hand and recycle the rest" -- DEST_HAND and DEST_RECYCLE.
    # `pick_optional` is Lightning Rush's "you MAY choose a card from among
    # them", where declining is legal and all N take the rest-destination.
    pick_dest: int = DEST_HAND
    rest_dest: int = DEST_RECYCLE
    pick_optional: bool = False
    # "You may reveal a GEAR from among them" (Ornn), "a unit from among them"
    # (Ivern, Rift Herald). Empty means any card, which is what Stacked Deck
    # prints. A restriction on the pick only -- the rest still go wherever the
    # rest-destination says, whatever their types.
    pick_types: tuple[str, ...] = ()
    # For OP_CHANNEL: the runes arrive exhausted unless `ready`, and
    # `draw_if_short` is the "If you can't / if you couldn't channel N this
    # way, draw 1" rider several of these cards print -- a consolation for an
    # empty Rune Deck, checked against how many actually came off it.
    ready_runes: bool = False
    # For OP_READY_RUNES: defer to the end of the turn instead of readying now
    # (Targon's Peak). "At the end of THIS turn" is the current turn whoever's
    # it is, and `ending` runs once per turn, so a promise made on the
    # opponent's turn is kept at the end of THAT turn.
    at_end_of_turn: bool = False
    draw_if_short: int = 0
    # For OP_KILL_ALL: which printed type the sweep reaches.
    # Empty means Unit, which is what every board wipe meant before
    # "Kill all gear" needed the distinction.
    card_type: str = ""
    # For OP_DISCARD_CHOOSE: which entry of `DISCARD_BRANCHES` to run
    # once the discarded card's type is known.
    branch_key: int = -1
    # Chaining: after THIS op's deferred decision resolves, run the ops in
    # `FOLLOWUPS[then_key]`. Those may suspend again, which is how a card
    # gets two decisions in sequence. -1 for the common case of none.
    then_key: int = -1
    # --- scoping for the board-wide ops -----------------------------------
    # These three turn "all units at battlefields" into "each other enemy unit
    # THERE", which is what most of the mass effects in the pool actually say.
    # 355.10 still applies: none of this makes them targets, because there is
    # no count and no choice -- the SLOT that names the location is the target,
    # and the sweep that follows is not.
    at: int = -1              # slot (or T_*) giving the location to sweep
    who: int = W_ANY          # whose units the sweep reaches
    except_target: int = -1   # slot whose unit is spared -- "each OTHER unit"
    # "Give your MECHS +1 Might" (Danger Zone) -- a tag the swept units must
    # carry. Empty reaches every unit, which is what the mass effects that name
    # no kin print. A restriction and not a target (355.10): there is still no
    # count and no choice, so the opponent cannot answer by making one illegal.
    tag: str = ""
    # "all units AT BATTLEFIELDS" -- printed on the mass-damage cards and NOT
    # on the mass Might reduction, which reaches units at bases too. A property
    # of the card, so it lives here rather than being a default.
    at_battlefields: bool = False
    # For OP_PLAY_FROM_TRASH: where the replayed card goes afterwards. Fizz
    # says "Recycle that spell after you play it"; Kai'Sa says nothing, so hers
    # trashes normally. A DEST_* from state.py.
    dest: int = 0
    # For the play-from-trash ops: which cost the play pays. A COST_* from
    # state.py, and it must agree with the slot's `playable_cost` -- the slot
    # uses it to decide legality, the op uses it to charge.
    cost: int = 0
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
 TR_PLAY_SPELL, TR_ACTIVATED, TR_ATTACK_OR_DEFEND,
 TR_PLAY_UNIT, TR_OTHER_DIES, TR_GEAR_ABILITY,
 TR_DISCARD, TR_BEGINNING, TR_END_OF_TURN,
 TR_OPPONENT_SCORES, TR_READIED, TR_CHOSEN) = range(17)
TRIGGER_NAMES = ("play_me", "death", "move", "hold", "conquer", "play_spell",
                 "activated", "attack_or_defend", "play_unit",
                 "other_dies", "gear_ability", "discard",
                 "beginning", "end_of_turn", "opponent_scores",
                 "readied", "chosen")

# TR_READIED fires on the exhausted -> ready TRANSITION, not on every write of
# P_READY. The Awaken Phase readies the turn player's whole board at once
# (315.1.b) and that DOES count as readying -- so a wide board fires it several
# times a turn, which is the card's intent -- but a unit that was already ready
# has not become ready and fires nothing. A unit ENTERING ready never was
# exhausted, so it is not a readying either.
#
# TR_CHOSEN fires when a target slot is filled with a permanent (355.7), from
# the one site where that happens. "You" is the card's controller throughout
# this family, which is why the cards reward targeting your OWN units --
# [Deflect] exists precisely because an opponent choosing you is a different
# event, and no card in the pool watches for that one.

# TR_OPPONENT_SCORES is a watcher on the OTHER seat's points, so it fires from
# every site that awards one -- Hold in `phases.score_holds`, Conquer in
# `combat._establish_control`, and `OP_SCORE` for the cards that grant a point
# outright. Three sites rather than one because the engine has no single
# "award a point" primitive; if a fourth ever appears it has to fire here too.

# TR_BEGINNING and TR_END_OF_TURN are phase-timed: they fire for the TURN
# PLAYER's permanents at a point in their own turn, not off any game event.
# "at the start of YOUR Beginning Phase" and "at the end of YOUR turn" are
# both about the controller's turn, so neither fires on the opponent's.

# TR_OTHER_DIES and TR_GEAR_ABILITY are WATCHER triggers: they fire for a
# permanent because something happened to a DIFFERENT one. TR_DEATH fires
# for the thing that died; "when ANOTHER friendly unit dies" is a different
# question and needs its own firing site. Both go through
# `chain.fire_watchers`, which is `fire_play_unit` generalised -- one place
# that knows how to ask "who was watching for this".

# TR_ACTIVATED is not a trigger at all -- it is the marker for an ACTIVATED
# ability (151.1: "Costs followed by a ':' and then an effect"). No event ever
# fires it; the player pays and puts it on the Chain themselves via A_ACTIVATE.
# It rides the trigger machinery because 151.2.a.1 says an activated ability
# "behaves, once activated, like a spell without an associated card" -- the
# same finalization, targeting, priority and resolution a triggered ability
# already uses. Giving it its own path would duplicate all of that.

# Which side of a Combat a TR_ATTACK_OR_DEFEND ability cares about (459). The
# Attacker is the seat that declared the Move; every unit it controls at that
# battlefield attacks, and every unit anyone else controls there defends.
ROLE_EITHER, ROLE_ATTACK, ROLE_DEFEND = range(3)

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
    # "Kill this:" -- the source is killed to pay, which makes the ability a
    # once-per-permanent effect rather than a repeatable one. It is a COST, so
    # it is paid at finalization and the source is already gone by the time the
    # effect resolves; nothing here may reference it (383.2.c.2). Killing is a
    # real death, not a banish (427.2.a), so the card lands in its trash and any
    # [Deathknell] on it fires.
    cost_kill_self: bool = False
    # "Spend N XP:" -- 204.1.b again, an instruction before the ':'. A player
    # resource rather than a permanent's, so unlike Exhaust it does not care
    # which copy activates, and unlike a rune cost it is not refunded by
    # anything: XP spent is gone.
    cost_xp: int = 0
    # 337.2 -- a resource-adding ability resolves IMMEDIATELY and never waits
    # on the Chain, so it cannot be responded to. The cards say so themselves:
    # "Abilities that add resources can't be reacted to." Without this an [Add]
    # would open a priority window in which the opponent could answer the mana
    # before it existed, which is the opposite of the rule.
    immediate: bool = False
    # For TR_PLAY_UNIT: fire only when the unit played was a TOKEN. Lillia
    # grows on "a token unit"; a watcher for any unit would be a different and
    # much stronger card, and no rules text distinguishes them for free.
    subject_token: bool = False
    # For TR_READIED / TR_CHOSEN: the event's subject must be the watcher
    # itself. "When you choose or ready ME" is a different card from "when you
    # ready a friendly unit" (Pirate's Haven), and `fire_watchers` walks every
    # permanent its controller owns -- so without this, Irelia would grow every
    # time anything of yours was readied.
    subject_is_self: bool = False
    # "When you choose me WITH A SPELL" (Jae Medarda). An ability that chooses
    # is still a choice (355.7), so the narrowing has to be stated.
    subject_by_spell: bool = False
    # For TR_PLAY_UNIT: which card TYPE the played card must be. Every play of
    # a permanent comes through one firing site, gear included, so without this
    # "when you play another unit" fired on a gear -- Reluctant Leader grew off
    # a Cull, and Vex would stun one. A multi-type card satisfies each of its
    # types (a gear unit answers both watchers), so this is a membership test
    # and never an elif over types.
    subject_card_type: str = "Unit"
    # For TR_PLAY_UNIT: watch the OPPONENT's plays instead of your own.
    # Vex - Apathetic stuns what an opponent plays; Lillia grows on what
    # you play. Same trigger, opposite side.
    subject_enemy: bool = False
    # "When you play ANOTHER unit" -- the watcher must not be the unit that
    # was just played. Reluctant Leader grows on the rest of the board and
    # not on its own arrival.
    subject_not_self: bool = False
    # "When another NON-RECRUIT unit you control dies" -- a tag the subject
    # must NOT carry. Viktor makes Recruits, so without this he would feed
    # on his own tokens and never stop.
    subject_lacks_tag: str | None = None
    # "When you play me or another DRAGON" -- a tag the subject must carry, the
    # mirror of `subject_lacks_tag`. Gentle Gemdragon's second ability watches
    # its kin and nothing else; without this it would fire on every unit played
    # and be a strictly better card than the one printed.
    subject_tag: str | None = None
    # "The FIRST TIME ... each turn" -- gated on `state.once_used`, the same
    # per-permanent turn stamp Zilean's once-each-turn uses. Spent when the
    # trigger fires, so a second death in the same turn does nothing.
    once_each_turn: bool = False
    # "while I'm at a battlefield" -- a condition on the WATCHER's own
    # location, not the subject's. Vex in a base watches nothing.
    subject_at_battlefield: bool = False
    # --- TR_ATTACK_OR_DEFEND narrowing ------------------------------------
    # 459 designates every unit at the battlefield as an Attacker or a Defender
    # when the Combat begins, and most cards care which: "When I attack" is
    # half of what "when I attack or defend" means. Both are checked at TRIGGER
    # time (359.3.f.3) -- a unit that does not qualify never triggers at all,
    # and one that does keeps the effect even if the board changes during the
    # response window.
    #
    # These lived in `combat.open_showdown` as an unconditional gate, which was
    # correct for the single card that needed them and silently wrong for every
    # other: Mask of Foresight's "alone" clause was being applied to all
    # attack/defend triggers, so a card without the clause would have inherited
    # it. Anything printed on one card belongs on that card.
    # 383.3.b -- a cost inside the instructions: "you may PAY {1 energy}. If
    # you do, ...". Distinct from `optional`, which is a free yes/no. The
    # ability is only offered when the cost is affordable, and accepting
    # pays it; declining removes the ability (383.3.a.2) and costs nothing.
    opt_cost_energy: int = 0
    opt_cost_power: int = 0
    # 383.3.b again, paid in a body rather than in runes: "you may KILL ME to
    # ...". Always affordable -- the source is on the board or the ability
    # never triggered -- so unlike a rune cost it needs no offer-time check.
    # It is a cost, so it is paid at finalization and the source is a corpse
    # by the time the effect resolves; nothing in the ops may reference it.
    opt_cost_kill_self: bool = False
    subject_alone: bool = False       # "...attacks or defends ALONE" (740.2.a)
    subject_role: int = ROLE_EITHER   # attacker-only / defender-only / either
    # Whose attack this watches. "When I attack" (the common case) fires only
    # for the permanent the ability is printed on; "When a friendly unit
    # attacks or defends alone" fires for any of them, which is what lets Mask
    # of Foresight sit at a base and watch a battlefield.
    #
    # Defaults to the narrow reading on purpose. A card that wants the wide one
    # and forgets this under-fires, which is visible as a card that does
    # nothing; the other default would make a forgotten flag fire for the whole
    # board, which reads as a plausible effect and hides.
    subject_any_friendly: bool = False

    @property
    def n_targets(self) -> int:
        return len(self.targets)


# ---------------------------------------------------------------------------
# The card data. This is the part that grows; everything above is fixed.
# ---------------------------------------------------------------------------
# Each entry is a transcription of the printed text. Keep the text in the
# comment so a future reader can check the transcription without the card.

# Token identities. The name on the right is the CARD, and every characteristic
# a card's text recites about it -- "2 Might", "with [Deflect]" -- is printed on
# that card already (rule 187), so the recitation is reminder text and nothing
# here has to re-state it. `data/tokens.json` supplies the eight rule-187 tokens
# the export omits; Recruit and Sprite come from `cards.json` and carry a back
# face and a collector number in their names.
SPRITE_TOKEN = "Sprite (274) // Buff"   # 3 Might Fae unit token, [Temporary]
RECRUIT_TOKEN = "Recruit (271) // Buff"  # 1 Might Recruit unit token
SAND_SOLDIER_TOKEN = "Sand Soldier"     # 187.3 -- 2 Might, Shurima tag
MECH_TOKEN = "Mech"                     # 187.4 -- 3 Might, Mech tag
REFLECTION_TOKEN = "Reflection"         # 187.6 -- 0 Might, domainless
BIRD_TOKEN = "Bird"                     # 187.7 -- 1 Might, Bird tag, [Deflect]
TENTACLE_TOKEN = "Tentacle"             # 187.10 -- 1 Might, Bilgewater tag
# 187.5 -- a GEAR token, not a unit. Every card that makes one says "exhausted",
# which is the default (`Op.ready` is False), and every one of them sends it to
# the controller's base: 149.2 keeps gear there, and T_MY_BASE says so
# explicitly rather than leaning on OP_CREATE_TOKEN's fallback.
GOLD_TOKEN = "Gold // Buff"

# --- printed play-destination permissions (806.3 exceptions) ---------------
# 806.3/813.3.a restrict a Unit to its controller's base or a Battlefield they
# already control. Several cards print an exception to that, and until now every
# one of them was a dead letter -- `play_destinations` said so in its docstring.
#
# **"Open" and "occupied" are not defined rules terms.** They appear only in
# card text, so these are readings rather than citations, and both are stated
# here so a wrong one is visible and cheap to change:
#   PERM_OPEN   -- no units there at all, from either player. An empty
#                  battlefield is an uncontrolled one (190.4.c), which is what
#                  makes "play me to an open battlefield" a free claim.
#   PERM_ENEMY  -- at least one ENEMY unit there. Rengar's whole card is
#                  dropping onto a battlefield the opponent is holding.
#   PERM_ATTACK -- the battlefield you are currently attacking: the contested
#                  one (459) where you hold the Attacker designation. Unlike
#                  the other two this is a COMBAT-scoped permission, so it is
#                  empty outside a Showdown and the card is then an ordinary
#                  base play.
PERM_NONE, PERM_OPEN, PERM_ENEMY, PERM_ATTACK = range(4)

# Cards that replace a token-unit play with "that token and an additional copy
# of it". Keyed by name for the same reason PLAY_PERMISSIONS is: there is one
# such card, and a general replacement registry for n=1 would be scaffolding
# around a single entry. If a second one prints, this is where it goes.
#
# Zilean's clause carries three separate restrictions, all enforced in
# `resolve`'s OP_CREATE_TOKEN: the token must be a UNIT, Zilean must be AT A
# BATTLEFIELD, and it is ONCE EACH TURN (tracked per row in `state.once_used`).
TOKEN_DOUBLERS: frozenset[str] = frozenset({"Zilean - Time Mage"})

# "Then, do the following based on the discarded card's type." The branch runs
# AFTER the player has chosen what to pitch, so it cannot be ordinary ops on
# the card -- resolution has already returned by then. Keyed by card name and
# looked up when the choice comes back, the same shape as PLAY_PERMISSIONS.
#
# A card with more than one type takes EVERY matching branch: a gear unit is
# both, so it would draw AND ready runes. See `_played_bits` for the same rule
# on Swain, and note the branches are checked independently for that reason.
# Indexed by INT, not by name: `GameState` holds no Python objects (PLAN.md
# §1.8), and `state_hash` reads every non-array field through `int(v)`. A
# string here parsed fine and then broke determinism, cloning and the digest
# all at once -- the rule exists for a reason.
DB_HWEI = 0

# Op lists that run AFTER a deferred decision resolves -- see `Op.then_key`.
# Indexed by int for the same reason DISCARD_BRANCHES is: nothing but ints may
# reach `GameState`, and the key is stored there while the decision is pending.
FU_DIANA_REVEAL = 0
FU_GUARDS_READY = 1
FU_DRAW_1 = 2

# Populated below, once the ops they reference are defined.
FOLLOWUPS: list[tuple] = [(), (), ()]
# [FU_DIANA_REVEAL] "...then reveal the top card of your Main Deck. If it's a
# spell, draw it." A second look at N=1: the spell goes to hand, anything else
# goes back on top. `pick_optional` because a type-restricted pick must always
# leave a way out -- the top card need not be a spell.

DISCARD_BRANCHES: tuple[dict[str, tuple], ...] = (
    # [DB_HWEI] Hwei - Brooding Painter: "Then, do the following based on the
    # discarded card's type: Spell - Draw 1. Gear - Ready up to 2 runes.
    # Unit - Give me +3 Might this turn."
    {
        "Spell": (Op(OP_DRAW, n=1),),
        "Gear": (Op(OP_READY_RUNES, n=2),),
        "Unit": (Op(OP_MODIFY_MIGHT, target=T_SELF, n=3),),
    },
)

# Cards that suppress the [Temporary] expiry. LeBlanc - Everywhere At Once:
# "Your [Temporary] effects at my battlefield don't trigger." 816's reminder --
# "Kill it at the start of its controller's Beginning Phase" -- is the trigger
# being suppressed, so a Temporary permanent standing with a friendly LeBlanc
# at a BATTLEFIELD simply does not expire.
#
# Two restrictions the wording carries and a loose reading drops: "YOUR"
# effects, so it never spares an opponent's Temporary units; and "at MY
# BATTLEFIELD", so a LeBlanc sitting in a base suppresses nothing.
# Heimerdinger - Inventor: "I have all Exhaust abilities of all friendly
# legends, units, and gear." Keyed by name like the other bespoke registries.
# The borrowed ability is HIS: its Exhaust cost taps him, its effects say "me"
# about him, and the donor is untouched.
ABILITY_BORROWERS: frozenset[str] = frozenset({"Heimerdinger - Inventor"})

# "I can't be chosen by enemy spells and abilities unless I'm in combat."
# Absolute untargetability with a condition, unlike [Deflect]'s surcharge --
# there is no price that makes it legal. Keyed by name like the other bespoke
# registries; `resolve._matches` enforces it for every slot at once, so it
# covers spells and abilities without either having to opt in.
SAFE_UNLESS_IN_COMBAT: frozenset[str] = frozenset({"Akali, Silent"})

TEMPORARY_SUPPRESSORS: frozenset[str] = frozenset(
    {"LeBlanc - Everywhere At Once"})

# 359.2.c -- units enter EXHAUSTED. [Accelerate] is the printed exception the
# engine already knows; these are cards that print their own, each with a
# different condition. Keyed by name for the same reason PLAY_PERMISSIONS is:
# the condition is bespoke per card, not a shared mechanism.
ER_TWO_OTHERS_AT_BASE, ER_DIED_IN_BEGINNING = range(2)

ENTERS_READY_IF: dict[str, int] = {
    # "I enter ready if you have two or more OTHER units in your base."
    "Xin Zhao - Vigilant": ER_TWO_OTHERS_AT_BASE,
    # "If a friendly unit died during your Beginning Phase this turn, I enter
    # ready." Past tense -- see `state.died_in_beginning`.
    "Shadow Watcher": ER_DIED_IN_BEGINNING,
}

# Printed OPTIONAL ADDITIONAL COSTS, in runes, paid as the card is played.
#
# **The same shape as [Accelerate], and deliberately the same action.** 805.2
# makes [Accelerate] an Optional Additional Cost paid *as* the unit is played,
# and `A_PLAY_AT_FAST` already folds it into the destination choice so that
# where to put the unit and whether to pay extra stay one decision. A card that
# prints its own optional additional cost is that same decision with a
# different payload, so it rides the same action rather than adding a second
# one -- and no card in the pool prints both, which is asserted where they meet.
#
# What differs is what paying BUYS. [Accelerate] buys entering ready (805.6, a
# replacement). These buy a clause in the card's own text: "when you play me,
# IF YOU PAID THE ADDITIONAL COST, ...". So paying sets `F_PAID_ADDITIONAL` on
# the permanent and the trigger reads it through `COND_PAID_ADDITIONAL` -- a
# snapshot on the row, like F_LEGION, because the ability resolves a priority
# window after the payment happened.
#
# **The Power is domain-bound to the card's own domain in every printed case**,
# which is what `plan_payment` already does for [Accelerate] under 805.1.a.1.
# All six read "{X rune}" where X is the card's single domain; if one ever
# prints a rune it does not itself have, this registry is where that shows up.
PLAY_COSTS: dict[str, tuple[int, int]] = {
    # "You may pay {1 energy}{Fury rune} as an additional cost to play me."
    "Blast Corps Cadet": (1, 1),
    # "As you play me, you may pay {Calm rune} as an additional cost."
    "Clockwork Keeper": (0, 1),
    # "You may pay {Mind rune} as an additional cost to play me."
    "Frostcoat Cub": (0, 1),
    # "You may pay {Order rune} as an additional cost to play me."
    "Masa, Crashing Thunder": (0, 1),
    # "You may pay {Fury rune} as an additional cost to play me."
    "Pyke - Dockside Butcher": (0, 1),
    # "You may pay {1 energy} as an additional cost to play me." No rune at all,
    # which is why the pair is (energy, power) rather than a domain.
    "Sea Monkey": (1, 0),
}


PLAY_PERMISSIONS: dict[str, int] = {
    # [Ambush] I can be played to a battlefield where there are enemy units.
    "Rengar, Trophy Hunter": PERM_ENEMY,
    # You may play me to an open battlefield.
    "Ocean Drake": PERM_OPEN,
    "Sneaky Deckhand": PERM_OPEN,
    "Sai Scout": PERM_OPEN,
    # [Reaction] [Assault 2] I can be played to a battlefield you're attacking.
    # Its own reminder text spells the timing out -- "play any time, even
    # before spells and abilities resolve" -- so unlike the Trophy Hunter this
    # is a Reaction rather than an Ambush, and it reinforces an attack you have
    # already committed to rather than starting one.
    "Rengar - Pouncing": PERM_ATTACK,
}


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
    #
    # **"A spell" is exactly a spell.** Not a unit -- 337.2 resolves those
    # immediately and they never become a Chain Item, so there is nothing to
    # counter and this is not a Magic-style "counter target spell" that stops a
    # creature. And not an ability either: abilities do sit on the Chain
    # (383.3), so `chain_abilities` has to be opted into, and only Not So Fast
    # and Repulse ("spell or ability") print the words that would.
    "Lilting Lullaby": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER, target=0), Op(OP_NO_SPELLS, target=0)),
    ),

    # [Reaction] Counter a spell that costs no more than {4 energy} and no
    # more than {any rune}.  "{any rune}" is one Power symbol of any domain.
    #
    # The cost limit is another reason abilities are out: an ability has no
    # printed cost, so the only number to compare would be its SOURCE card's,
    # which the ability never paid.
    "Defy": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY,
                            max_energy=4, max_power=1),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # --- battlefield slots: "choose a battlefield and ... there" -----------
    # [Action] Choose a battlefield and an enemy unit there. Deal 4 to that
    # unit and 1 to each other enemy unit there.
    #
    # **Two slots, and the second is relative to the first.** The battlefield
    # is itself a target -- chosen at finalization, respondable -- and
    # `REL_SAME_BF` against slot 0 is what "there" means. That relation used to
    # assume the slot it pointed at held a unit ROW; a battlefield slot holds a
    # LOCATION, and reading one as the other compares against whichever unit
    # happens to sit in row 0-3.
    #
    # The second op is not a target (355.10): "each other enemy unit there" has
    # no count and no choice, so the opponent cannot answer by making one of
    # them illegal. `except_target=1` is the "other" -- the chosen unit takes 4,
    # not 5.
    "Crescent Strike": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY),
                 TargetSpec(who=W_ENEMY, rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_DAMAGE, target=1, n=4),
             Op(OP_DAMAGE_ALL, n=1, at=0, who=W_ENEMY, except_target=1)),
    ),

    # [Hidden] [Reaction] Choose a battlefield you control and a unit you
    # control at a different location. Move that unit to that battlefield and
    # give it +2 Might this turn.
    #
    # "A battlefield YOU CONTROL" is `who=W_FRIENDLY` on the battlefield slot;
    # "at a different location" is REL_DIFFERENT_LOC against it, which reads
    # the location directly rather than through a unit. Both slots are LOC_FREE
    # because the card is [Hidden] and the whole point is reinforcing a
    # battlefield from somewhere else -- binding them to the hiding place would
    # make the card unplayable from hiding, which is the only way it is played.
    "Resonating Strike": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_FRIENDLY,
                            locality=LOC_FREE),
                 TargetSpec(who=W_FRIENDLY, rel=REL_DIFFERENT_LOC, rel_to=0,
                            locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=1, target_b=0),
             Op(OP_MODIFY_MIGHT, target=1, n=2)),
    ),

    # [Action] Choose a battlefield where you have units. You may move up to
    # one enemy unit to that battlefield. Then give enemy units there -2 Might
    # this turn.
    #
    # The move is "up to one", so slot 1 is optional (355.14) -- the card is
    # still playable with no enemy to drag in, and then it is just a Might
    # reduction on whoever is already there. The Might sweep is scoped to the
    # battlefield and to enemies, and it happens AFTER the move, so a unit
    # pulled in by the first op is caught by the second.
    "Moonfall": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY,
                            needs_own_units=True),
                 TargetSpec(who=W_ENEMY, optional=True)),
        ops=(Op(OP_MOVE_TO, target=1, target_b=0),
             Op(OP_MODIFY_MIGHT_ALL, n=-2, at=0, who=W_ENEMY)),
    ),

    # --- granting a keyword ------------------------------------------------
    # [Action] Give a unit [Assault 3] this turn. (+3 Might while attacking.)
    #
    # The value is the keyword's, not a Might modifier: [Assault 3] is
    # conditional Might that exists only while the unit is an attacker
    # (807.1.c), so granting it is not the same as +3 Might and a unit that
    # never attacks gets nothing.
    "Cleave": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=3),),
    ),

    # [Hidden] [Action] Give a unit [Shield 3] and [Tank] this turn.
    #
    # Two grants, one card -- and the pairing is the point: [Shield 3] makes it
    # survive and [Tank] makes it the one that has to be dealt with, so the
    # damage lands where the Shield is.
    "Block": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Shield", n=3),
             Op(OP_GRANT_KEYWORD, target=0, keyword="Tank", n=1)),
    ),

    # Choose a friendly unit without [Temporary]. Give it [Temporary]. Draw 2.
    #
    # **The grant is NOT "this turn".** [Temporary] kills the unit at the start
    # of its controller's next Beginning Phase, so a grant that expired with
    # the turn would never fire at all -- the card would be a two-card draw
    # with no cost. `grant_this_turn=False` is what makes the drawback real.
    #
    # "Without [Temporary]" is a restriction rather than a condition, and it
    # reads the granted value too: a unit already given [Temporary] by another
    # copy is not a legal choice.
    "Shadow's Call": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY, lacks_keyword="Temporary"),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Temporary", n=1,
                grant_this_turn=False),
             Op(OP_DRAW, n=2)),
    ),

    # [Reaction] Kill a friendly unit to give +Might equal to its Might to
    # another friendly unit this turn. Draw 1.
    #
    # **The amount is read at resolution, not printed.** "Equal to its Might"
    # means whatever the sacrificed unit is worth when the spell resolves --
    # buffs, statics and this-turn modifiers included -- so `n_from_might`
    # points at the slot instead of `n` carrying a number. Feeding a Soul
    # Shepherd token is worth more than the token's printed Might, and that is
    # the card.
    #
    # Order matters and is the reverse of the sentence: the Might has to be
    # read BEFORE the kill, because a dead unit's Might is not a number any
    # more. The ops run in list order, so the buff is written first.
    "Deathgrip": CardSpec(
        speed=SPEED_REACTION,
        # "ANOTHER friendly unit" is a different UNIT, not a different
        # location -- the two units are usually standing together, which is
        # the whole point. `legal_targets` already excludes rows an earlier
        # slot took, so no relation is needed to say "another".
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_FRIENDLY)),
        ops=(Op(OP_MODIFY_MIGHT, target=1, n_from_might=0),
             Op(OP_KILL, target=0),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Counter a spell.  The plain one, with no rider at all.
    "Wind Wall": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # [Hidden] [Action] Play a ready 3 Might Sprite unit token with [Temporary].
    # The token card carries [Temporary] itself, so it expires through the
    # existing Beginning-Phase path -- the conquer-vs-hold inversion.
    "Sprite Call": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=SPRITE_TOKEN, ready=True),),
    ),

    # Play two ready 3 Might Sprite unit tokens with [Temporary].
    "Sprite Burst": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=2, token=SPRITE_TOKEN, ready=True),),
    ),

    # [Action] Deal 6 to a unit at a battlefield.
    "Falling Comet": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=6),),
    ),

    # [Action] Deal 8 to a unit.
    # No location clause at all, unlike Falling Comet directly above -- this
    # one reaches a unit sitting safely in a base.
    "Final Spark": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DAMAGE, target=0, n=8),),
    ),

    # Deal 3 to all enemy units at a battlefield.
    # "a battlefield" is singular and chosen, so it is a real slot; the sweep
    # then scopes to it with `at`. Not `at_battlefields`, which would mean
    # every battlefield at once.
    "Firestorm": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY),),
        ops=(Op(OP_DAMAGE_ALL, at=0, n=3, who=W_ENEMY),),
    ),

    # [Action] Give friendly units +5 Might this turn.  Decisive Strike's big
    # brother; same untargeted board-wide shape.
    "Grand Strategem": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=5, who=W_FRIENDLY),),
    ),

    # [Action] Look at the top 3 cards of your Main Deck. Put 1 into your hand
    # and recycle the rest.
    # The most-played uncovered card in the corpus, 22 slots across the decks.
    # Not "up to 1": the pick is mandatory, so `pick_optional` stays False and
    # the player always takes something.
    "Stacked Deck": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_LOOK_TOP, n=3,
                pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),),
    ),

    # Look at the top 3 cards of your Main Deck. You may choose a card from
    # among them and draw it. Put the rest into your trash.  [Flow]
    # "You MAY choose" -- declining is legal and all three go to the trash,
    # which is what `pick_optional` is for. The rest-destination is the trash
    # here and the deck bottom on Stacked Deck: same shape, different words.
    "Lightning Rush": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_LOOK_TOP, n=3, pick_optional=True,
                pick_dest=DEST_HAND, rest_dest=DEST_TRASH),),
    ),

    # Kill a unit.  No restriction of any kind -- the whole card.
    "Vengeance": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # Choose a friendly unit. Kill an enemy unit with less Might than it.
    # The bar is a unit you picked rather than a printed number, so the card
    # scales with your own board -- and both readings are effective Might, so
    # pumping your chosen unit in response widens what it can kill.
    "Public Execution": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_ENEMY, less_might_than=0)),
        ops=(Op(OP_KILL, target=1),),
    ),

    # Kill a unit at a battlefield with 3 Might or less.
    "Soul Harvest": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True, max_might=3),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Reaction] Give a unit -4 Might this turn. [Predict].
    # 436.1 -- Predicting is "looking at a single card from the top of the Main
    # Deck and choosing whether or not to Recycle it", so it is exactly the
    # look mechanic with N=1: recycling is the "pick", and declining puts the
    # card back on TOP (DEST_TOP), which is what makes Predict information
    # rather than card selection. 436.3.a -- X omitted means 1.
    #
    # The look must be last, and it is: the -4 resolves, then you Predict.
    "Eclipse": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-4, floor=1),
             Op(OP_LOOK_TOP, n=1, pick_optional=True,
                pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP)),
    ),

    # --- [Repeat] (820) -----------------------------------------------------
    # The Repeat COST is not transcribed here: it is parsed off the card by
    # `cardtable.repeat_cost` and paid by the action layer, exactly as the
    # [Flow] cost is. What these entries carry is the effect that gets executed
    # one additional time (820.1.d) when that cost is paid.

    # [Repeat] {2 energy}. Play a 2 Might Sand Soldier unit token.
    # The rulebook's own worked example of Repeat (820.1.d.1).
    "Desert's Call": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=SAND_SOLDIER_TOKEN),),
    ),

    # [Action] [Repeat] {1 energy}. Give a unit [Assault 2].
    # Cleave's shape with a Repeat rider: granted, not "this turn", so it lasts
    # until the unit leaves. Repeating it grants [Assault 2] twice, and 807.1.c
    # makes a granted instance an ADDITIONAL ability rather than a replacement,
    # so the values add to [Assault 4] on the same unit.
    "Blood Rush": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=2),),
    ),

    # [Reaction] [Repeat] {2 energy}. Give a unit -2 Might this turn.
    # No printed floor, so 143.2.b's general floor of 0 applies -- and repeated,
    # that is -4 on one unit for {4 energy}.
    "Frigid Touch": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2),),
    ),

    # [Repeat] {2 energy}. Ready a unit.
    # Repeating this readies the SAME unit twice, which does nothing the second
    # time -- 820.1.d re-executes the instructions, it does not re-target.
    "Upstage Comedy": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_READY, target=0),),
    ),

    # [Action] [Repeat] {1 energy}{Mind rune}. Deal 1 to up to three units at
    # the same location.
    # "up to three" is three optional slots (355.14), and "at the same
    # location" ties slots 1 and 2 to slot 0 -- not to a battlefield, so a base
    # qualifies as a location too.
    "Bellows Breath": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, optional=True),
                 TargetSpec(who=W_ANY, optional=True, rel=REL_SAME_BF, rel_to=0),
                 TargetSpec(who=W_ANY, optional=True, rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_DAMAGE, target=0, n=1),
             Op(OP_DAMAGE, target=1, n=1),
             Op(OP_DAMAGE, target=2, n=1)),
    ),

    # --- channelling (430.4.b) ----------------------------------------------
    # Every one of these says "EXHAUSTED": the rune joins the board but cannot
    # be spent this turn, which is what keeps them from being pure
    # acceleration. `ready_runes` stays False, unlike the two-per-turn of
    # 430.4.a which `phases.channel` brings in ready.

    # Channel 1 rune exhausted. If you can't, draw 1.
    "Mobilize": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_CHANNEL, n=1, draw_if_short=1),),
    ),

    # Channel 2 runes exhausted. If you couldn't channel 2 runes this way,
    # draw 1.  The rider pays out on a PARTIAL channel too -- one rune off an
    # almost-empty deck is still "couldn't channel 2".
    "Catalyst of Aeons": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_CHANNEL, n=2, draw_if_short=1),),
    ),

    # Choose an opponent. They reveal their hand. Choose a non-unit card from
    # it, and recycle that card.
    # "Choose an opponent" is forced at two seats, so it is not a target slot.
    # The pick is a decision made DURING resolution against a zone rather than
    # the board, so like the look mechanic it cannot use target slots (355.10)
    # -- it suspends and asks. Must be the card's last op for the same reason.
    "Sabotage": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_REVEAL_HAND, pick_types=("Spell", "Gear"),
                pick_dest=DEST_RECYCLE),),
    ),

    # Each player kills one of their units.
    # Each player chooses their OWN casualty, so there is no target slot -- the
    # caster does not pick the opponent's. Sequential, starting with the
    # resolving player, and a seat with no units simply skips.
    "Cull the Weak": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EACH_KILLS_OWN),),
    ),

    # [Action] When any unit takes damage this turn, kill it.
    # "ANY unit" -- both players', including the caster's own, which is what
    # makes this a board-wipe enabler rather than removal. A turn-scoped
    # modifier on lethality, not a trigger with a target.
    "Imperial Decree": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_ANY_DAMAGE_KILLS),),
    ),

    # [Reaction] Counter an enemy spell or ability that chooses a friendly unit
    # or gear.
    # `chain_abilities` because this is one of only two cards that says "or
    # ability"; `chooses_friendly_perm` is the "that chooses a friendly unit or
    # gear" clause, which is a restriction on the item's own targets. A slot
    # with no legal item is simply unplayable (355.8).
    "Not So Fast": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ENEMY, chain_abilities=True,
                            chooses_friendly_perm=True),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # [Hidden] [Action] Swap the Might of two units at the same battlefield
    # this turn.
    # Unqualified "two units", so either side's -- swapping your big unit's
    # Might onto their small one is as legal as the reverse. The second slot is
    # tied to the first by location, which is what "at the same battlefield"
    # means, and `not_self` keeps it from naming the same unit twice.
    "Switcheroo": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),
                 TargetSpec(who=W_ANY, at_battlefield=True, not_self=True,
                            rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_SWAP_MIGHT, target=0, target_b=1),),
    ),

    # [Reaction] [Repeat] {2 energy}. Give two friendly units each +1 Might
    # this turn.  Two slots, so repeating it gives each of them +2.
    "Bonds of Strength": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_FRIENDLY, not_self=True)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_MODIFY_MIGHT, target=1, n=1)),
    ),

    # [Reaction] [Repeat] {2 energy}. Draw 1.
    "Downstage Dramatics": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=1),),
    ),

    # [Reaction] [Repeat] {2 energy}. Give a unit +2 Might this turn.
    "Feral Strength": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),),
    ),

    # Kill an enemy Chaos ({Chaos rune}) unit or gear.
    # The domain is a restriction on the TARGET's own printed domain, not on
    # what this costs. "unit or gear" is the `card_type` tuple, as ever.
    "Decree of Unity": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY, domain=2,          # 2 == Chaos
                            card_type=("Unit", "Gear")),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Action] Kill all gear.
    # Both players', and gear only -- units are untouched. The sweep has always
    # been units-only because every wipe before this one was.
    "Thermo Beam": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_KILL_ALL, card_type="Gear"),),
    ),

    # [Action] [Repeat] {2 energy}. Stun an attacking unit.
    # Only legal during a Showdown -- 459 is what makes a unit "attacking", and
    # outside one there is nothing to choose, so the card cannot be played.
    "Thwonk!": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, attacking=True),),
        ops=(Op(OP_STUN, target=0),),
    ),

    # [Repeat] {2 energy}{Fury rune}. Deal 2 to a unit at a battlefield, then
    # deal 2 to up to one OTHER unit.
    # The second slot is "up to one" (355.14, so it may be left empty) and
    # "other" (not the first) -- but carries no location clause of its own, so
    # it can reach a unit sitting in a base.
    "Piercing Light": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),
                 TargetSpec(who=W_ANY, optional=True, distinct_from=0)),
        ops=(Op(OP_DAMAGE, target=0, n=2),
             Op(OP_DAMAGE, target=1, n=2)),
    ),

    # Draw 1, then draw 1 for each battlefield you or allies control.
    # Two ops: the flat draw, then the counted one. At two seats "you or
    # allies" is just you.
    "Right of Conquest": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_DRAW, n=1),
             Op(OP_DRAW, n=1, n_from_count=CT_MY_BATTLEFIELDS)),
    ),

    # [Action] Stun an enemy unit at a battlefield. You may move a friendly
    # unit to that enemy unit's battlefield.
    # The destination is slot 0's LOCATION -- not the caster's, and not a place
    # the player picks -- which is what `loc_of_target` says.
    "Zenith Blade": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),
                 TargetSpec(who=W_FRIENDLY, optional=True)),
        ops=(Op(OP_STUN, target=0),
             Op(OP_MOVE_TO, target=1, loc_of_target=0)),
    ),

    # Buff a friendly unit in your base, then move it to a battlefield.
    # Two slots: the unit (restricted to YOUR base by `at_base` plus
    # W_FRIENDLY) and the battlefield it goes to. `Op.target_b` points at the
    # location slot, so the destination is the one the player chose.
    "Showstopper": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY, at_base=True),
                 TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY,
                            locality=LOC_FREE)),
        ops=(Op(OP_BUFF, target=0),
             Op(OP_MOVE_TO, target=0, target_b=1)),
    ),

    # [Reaction] Give a friendly unit at a battlefield +2 Might this turn FOR
    # EACH enemy unit there.  `n` is the rate and the count multiplies it, so
    # this is +2 per enemy rather than a flat +2.
    "Against the Odds": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2,
                n_from_count=CT_ENEMIES_AT_TARGET),),
    ),

    # [Reaction] Return a friendly unit to its owner's hand. Its owner channels
    # 1 rune exhausted.
    # The slot is friendly, so "its owner" is the caster -- the two only come
    # apart on a card that can bounce an enemy unit, and this one cannot.
    "Retreat": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),
             Op(OP_CHANNEL, n=1)),
    ),

    # [Reaction] Draw 3.
    "Premonition": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=3),),
    ),

    # [Action] Give a unit +7 Might this turn.
    "Primal Strength": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=7),),
    ),

    # [Reaction] Give a unit -10 Might this turn.
    # No printed floor, unlike Stupefy's "to a minimum of 1" -- so the general
    # floor of 0 in 143.2.b applies and this is lethal to anything under 10.
    "Moonlight Affliction": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-10),),
    ),

    # [Action] Play four 1 Might Recruit unit tokens.
    # The reminder text spells out 806.3's ordinary destination rule, so this
    # is one location slot for all four rather than four separate choices.
    "Recruit the Vanguard": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=4, token=RECRUIT_TOKEN),),
    ),

    # [Action] Deal 2 to a unit at a battlefield.
    "Incinerate": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=2),),
    ),

    # [Action] Return a gear to its owner's hand.
    # `card_type` overrides the slot's default: gear are permanents on the
    # board like any other, so this is a unit slot pointed at a gear.
    "Factory Recall": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),),
    ),

    # [Action] Give friendly units +2 Might this turn.
    # Untargeted (355.10) and unscoped by location, so it reaches the whole
    # board including the base.
    "Decisive Strike": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=2, who=W_FRIENDLY),),
    ),

    # [Hidden] [Action] Move a unit from a battlefield to its base.
    # "a unit", not "an enemy unit" -- this retreats your own as readily as it
    # sends theirs home, which is what the card's name is about.
    "Fight or Flight": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),),
    ),

    # [Hidden] [Action] Deal 3 to a unit at a battlefield. Play a Gold gear
    # token exhausted.  The damage slot is unqualified -- "a unit", not "an
    # enemy unit" -- so it may point at your own, which is what makes this
    # playable as a Hidden answer to a unit you need dead whoever owns it.
    "Wages of Pain": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=3),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=GOLD_TOKEN)),
    ),

    # Play a 3 Might Mech unit token.  [Flow] {2 energy}{Mind rune}
    # A token spell names no destination, so the destination is the ordinary
    # one 806.3 gives any unit -- base or a battlefield you control -- and that
    # is a CHOICE, hence a TK_LOCATION slot rather than a silent default to
    # base. [Flow] is read off the card's own printed cost, not from here.
    "Iterative Design": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=MECH_TOKEN),),
    ),

    # Play two 1 Might Tentacle unit tokens from Bilgewater.  [Flow] {3 energy}
    # "from Bilgewater" names the tag the tokens carry (187.10), which the
    # Tentacle card already has -- it is not a second destination.
    "Up from the Deep": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=2, token=TENTACLE_TOKEN),),
    ),

    # [Action] Move a friendly unit and ready it.
    "Ride The Wind": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1, then_ready=True),),
    ),

    # Move an enemy unit.  Moving an enemy INTO your units stages a Combat by
    # presence (461) -- the engine already handles that, so this is removal.
    "Charm": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, locality=LOC_FREE)),
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

    # [Hidden][Reaction] Draw 2.
    "Consult the Past": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=2),),
    ),

    # [Action] Kill a unit at a battlefield.
    "Blast of Power": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Action] You may kill a gear. Draw 1.
    #
    # "You may" on a spell is 355.14's optional slot, not a resolution-time
    # choice: declining is simply choosing no target, and the draw is
    # unconditional either way. `card_type` retargets the slot at gear --
    # they are permanents on the board like any other, so this is the same
    # slot machinery rather than a parallel kind.
    "Salvage": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",), optional=True),),
        ops=(Op(OP_KILL, target=0), Op(OP_DRAW, n=1)),
    ),

    # --- trash recursion ---------------------------------------------------
    # Every card below names a card in a TRASH rather than on the board, which
    # is what TK_TRASH_CARD is for. Read the note beside it in this file before
    # adding another: the slot holds a packed (owner, card), and `who` decides
    # WHICH trash -- most of these say "your trash", but not all of them do.

    # Return up to 2 units from trashes to their owners' hands.
    #
    # **"From trashes", not "from your trash"** -- so both piles are in scope,
    # which is the whole reason `who` reaches TK_TRASH_CARD at all. And "their
    # owners' hands" is the matching half: pulling an opponent's unit out of
    # their trash hands it back to THEM. That makes the enemy-facing mode a
    # denial play rather than a theft -- you take a unit out of reach of their
    # own Soulgorger and pay them a card for it.
    "Shadows of the Past": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_ANY,
                            card_type=("Unit",), optional=True),
                 TargetSpec(kind=TK_TRASH_CARD, who=W_ANY,
                            card_type=("Unit",), optional=True)),
        ops=(Op(OP_TRASH_TO_HAND, target=0),
             Op(OP_TRASH_TO_HAND, target=1)),
    ),

    # [Action] Return a unit from your trash to your hand.
    "Morbid Return": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",)),),
        ops=(Op(OP_TRASH_TO_HAND, target=0),),
    ),

    # Play a unit from your trash, ignoring its Energy cost. (You must still
    # pay its Power cost.)
    #
    # A UNIT, not a spell, and that changes the shape completely: 337.2 resolves
    # a unit immediately, so there is no Chain Item, nothing to respond to, and
    # no destination to record afterwards. What it needs instead is a place to
    # stand, and 806.3 restricts that to your base or a Battlefield you control
    # -- `play_destination` is what stops the slot offering contested ground
    # that would be a free Conquer.
    "The Harrowing": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                            playable=True, playable_cost=COST_NO_ENERGY),
                 TargetSpec(kind=TK_LOCATION, play_destination=True,
                            locality=LOC_FREE)),
        ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                cost=COST_NO_ENERGY),),
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
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, has_keyword="Hidden",
                            optional=True),
                 TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, has_keyword="Hidden",
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
        ops=(Op(OP_EXHAUST_ALL), Op(OP_DAMAGE_ALL, n=12, at_battlefields=True)),
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
        ops=(Op(OP_DAMAGE_ALL, n=1, at_battlefields=True),),
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

    # [Reaction] Deal 2 to all enemy units in combat.
    #
    # **"In combat" is a place, not a designation.** 459 makes every unit at
    # the contested battlefield an Attacker or a Defender the moment Combat
    # begins, so "in combat" is exactly "at `showdown_bf`" -- which is why this
    # is a location-scoped sweep and not the `attacking` flag. The flag would
    # have spared every defender, and the card kills defenders.
    #
    # Untargeted (355.10), so the opponent cannot answer by making one of them
    # illegal; the only answer is to change what is standing there.
    "Cannon Barrage": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DAMAGE_ALL, n=2, at=T_COMBAT, who=W_ENEMY),),
    ),

    # [Reaction] [Repeat] {1 energy}{any rune} Give your Mechs +1 Might
    # this turn.
    #
    # [Repeat] is already machinery: `table.repeat_energy`/`repeat_power` carry
    # the additional cost and `chain.resolve_top` runs the ops a second time
    # (820.1.d), so the card only has to say what one execution does. What was
    # missing is the kin restriction -- `tag` -- because every mass Might
    # effect before this one reached all of a side's units.
    #
    # No location clause, so it reaches your Mechs at bases too.
    "Danger Zone": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=1, who=W_FRIENDLY, tag="Mech"),),
    ),

    # [Reaction] Draw 1 for each of your [Mighty] units.
    # 740.2's 5+ Might, counted live at resolution -- so a Might trick played
    # in response to this genuinely draws another card, which is the whole
    # reason the card is a Reaction.
    "Show of Strength": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=1, n_from_count=CT_MY_MIGHTY_UNITS),),
    ),

    # [Action] Give a friendly unit +1 Might this turn and [Stun] an enemy
    # unit at its location.
    #
    # "At ITS location" relates the second slot to the first, and it is a
    # LOCATION relation rather than a battlefield one: two friendly and enemy
    # units can share a base as easily as a battlefield, and REL_SAME_BF
    # compares the two locations without requiring either to be a battlefield.
    #
    # Both are targets, chosen at finalization, so growing the friendly unit
    # commits to which enemy can be stunned before the opponent responds.
    "Heroic Charge": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_ENEMY, rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_STUN, target=1)),
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
(ST_MIGHT, ST_COST_ENERGY, ST_KEYWORD, ST_UNCHOOSABLE,
 ST_NO_PLAY, ST_DAMAGE_BONUS) = range(6)
ST_NAMES = ("might", "cost_energy", "keyword", "unchoosable", "no_play",
            "damage_bonus")

# ST_DAMAGE_BONUS is Void Gate's "spells and abilities affecting units here each
# deal 1 Bonus Damage". Read in `combat.mark_damage`, which is exactly the
# spell-and-ability damage path -- combat damage writes `P_DMG` directly in the
# damage step and so is untouched, which is what the card says. "Each INSTANCE"
# is per call, and `mark_damage` is called once per instance, so the wording
# falls out rather than needing to be arranged.

# ST_NO_PLAY is Rockfall Path's "Units can't be played here" -- the first
# static that REMOVES a permission rather than granting or modifying something.
# It reaches `actions.play_destinations`, not the board scan every other kind
# uses, because the thing it applies to is not on the board yet.
#
# 806.3 already restricts a unit to its controller's base or a battlefield they
# control, and four printed permissions WIDEN that (see `PLAY_PERMISSIONS`).
# This narrows it, and it must narrow the widened set too: an [Ambush] unit is
# still a unit being played here.

# Who a static applies to.
#   SC_UNITS_HERE -- printed on a BATTLEFIELD, reaching units standing on it.
#                    "Units here" carries no ownership clause, so it reaches
#                    BOTH players (targets scope by omission); narrow with
#                    `who` when a card says "your".
SC_SELF, SC_FRIENDLY_UNITS, SC_UNITS_HERE = range(3)

# What a "for each ..." clause COUNTS. The board is the obvious source and was
# the only one; a zone is the other, and it is a different kind of number --
# Rhasa reads a pile that grows all game and never shrinks on its own, so her
# cost falls monotonically rather than swinging with the board.
CNT_NONE, CNT_BOARD, CNT_TRASH = range(3)


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
    # Narrowing for SC_FRIENDLY_UNITS. "OTHER friendly units HERE have
    # [Assault]" (Captain Farron) is both of these; "your token units have
    # [Tank]" (Lillia) is neither, and reaches the whole board.
    scope_not_self: bool = False
    scope_same_loc: bool = False
    # For ST_KEYWORD: which keyword this grants, and its value. `n` carries the
    # value the same way it carries a Might amount, so a bare keyword is n=1.
    keyword: str | None = None
    # "Units here WITH [Temporary] have [Shield]" (Black Flame Altar) -- a
    # keyword the AFFECTED unit must already have. Distinct from `keyword`
    # (what is granted) and from `per_keyword` (what is counted).
    requires_keyword: str | None = None
    # SC_UNITS_HERE only: whose units. W_ANY is the unqualified "units here",
    # which reaches both players.
    who: int = W_ANY
    # Counting clause. `per_same_loc` is "at my battlefield"; `per_friendly`
    # is the "of your units" in the same sentence.
    per_keyword: str | None = None
    per_friendly: bool = True
    per_same_loc: bool = True
    # What the "for each" clause counts. CNT_BOARD is implied whenever
    # `per_keyword` or `per_card_type` is set, so existing entries keep working
    # without saying so; CNT_TRASH is the new one.
    per: int = CNT_NONE
    per_card_type: str | None = None   # "for each gear you control"
    # CNT_TRASH only: "for each card with MY NAME in your trash" narrows the
    # pile to copies of the static's own card (Shadowblade Lurker), where the
    # bare form counts every card in it (Rhasa).
    per_same_name: bool = False
    # 356.4.e -- "to a minimum of {N energy}". The floor binds only THIS
    # discount, which is why it rides here and not on the total; see
    # `cost.order_discounts` for why that makes the ordering matter.
    floor: int = 0
    # Gate. A static that does not apply right now contributes nothing at all,
    # which for a cost discount means the card simply costs its printed price.
    cond: int = COND_NONE
    level: int = 0            # the N in COND_LEVEL's "[Level N]"


# Statics printed on a BATTLEFIELD rather than on a permanent. Kept in its own
# table because a battlefield is not a permanent: it occupies a slot
# (`state.bf_card`), has no row, no controller of its own, and cannot be killed
# -- so it can never be the SUBJECT of a static, only the source of one.
#
# Every one of these is SC_UNITS_HERE, which is the only scope a battlefield
# has: the units standing on it. "Units here" prints no ownership clause, so it
# reaches both players.
BF_STATICS: dict[str, tuple[Static, ...]] = {

    # Units here have +1 Might. (This includes attackers.)
    "Trifarian War Camp": (
        Static(ST_MIGHT, n=1, scope=SC_UNITS_HERE),
    ),

    # Units here have [Ganking].
    "Windswept Hillock": (
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_UNITS_HERE),
    ),

    # Units here with [Temporary] have [Shield].
    # The requirement is on the AFFECTED unit, which is what makes this a
    # narrow reward for a token board rather than a blanket buff.
    "Black Flame Altar": (
        Static(ST_KEYWORD, keyword="Shield", n=1, scope=SC_UNITS_HERE,
               requires_keyword="Temporary"),
    ),

    # While a unit here is defending alone, it has -2 Might.
    # Reaches BOTH players' units, like every "units here" clause, so it is as
    # much a reason not to leave your own lone defender as it is a weapon. The
    # gate is live: a second friendly unit arriving at the battlefield turns it
    # off mid-combat.
    "Forbidding Waste": (
        Static(ST_MIGHT, n=-2, scope=SC_UNITS_HERE, cond=COND_DEFENDING_ALONE),
    ),

    # Spells and abilities affecting units here each deal 1 Bonus Damage.
    # Reaches BOTH players' spells, like every unqualified "units here" clause,
    # so it makes the ground dangerous to stand on rather than being a weapon
    # for whoever controls it.
    "Void Gate": (
        Static(ST_DAMAGE_BONUS, n=1, scope=SC_UNITS_HERE),
    ),

    # Units can't be played here.
    # The one static in the pool that takes a permission away. `scope` is
    # SC_UNITS_HERE because that is who it speaks about -- units at this
    # battlefield -- even though it is read before any of them exists.
    "Rockfall Path": (
        Static(ST_NO_PLAY, scope=SC_UNITS_HERE),
    ),

    # Units here with [Tank] have +1 Might.
    # The same shape as Black Flame Altar with a different kind: the
    # requirement is on the affected unit either way, so nothing new was
    # needed to express it.
    "Kinkou Temple": (
        Static(ST_MIGHT, n=1, scope=SC_UNITS_HERE, requires_keyword="Tank"),
    ),
}


# Triggered abilities printed on a BATTLEFIELD. Separate from `ABILITIES` for
# the reason `BF_STATICS` is separate from `STATICS`: a battlefield is not a
# permanent, so it has no row for `T_SELF` to name and no controller of its own.
# Both facts are handled at the firing site (`combat._queue_bf_trigger`, which
# carries the seat) and in `resolve._slot` (which fizzles `T_SELF` and answers
# `T_HERE` with the battlefield's own location).
#
# **These fire ONCE, for the player, where a unit's fire once per unit.** "When
# you conquer here" on the ground is one trigger no matter how many units took
# it; the same words on a unit are one per unit standing there. Getting that
# backwards is the easy mistake, and it is invisible in a test with one unit.
BF_ABILITIES: dict[str, tuple[Ability, ...]] = {

    # When you conquer here, draw 1 for each other battlefield you or allies
    # control. ("Or allies" is a multiplayer clause; in a two-player game it
    # reads as "you".)
    "Seat of Power": (
        Ability(TR_CONQUER, ops=(
            Op(OP_DRAW, n=1, n_from_count=CT_MY_OTHER_BATTLEFIELDS),)),
    ),

    # When you hold here, draw 1.
    "Grove of the God-Willow": (
        Ability(TR_HOLD, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you conquer here, you may pay {1 energy} to ready your legend.
    # `optional` plus `opt_cost_energy` is 383.3.b's cost-within-instructions:
    # the choice and the payment both happen at finalization, so declining
    # removes the ability from the chain entirely (383.3.a.2).
    "Hall of Legends": (
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                ops=(Op(OP_READY_LEGEND),)),
    ),

    # At the start of each player's first Beginning Phase, that player gains
    # 1 point.
    # Fires for BOTH players, once each, on their own first Beginning Phase --
    # so it is symmetric and nets nothing, but it moves both players two points
    # closer to the Victory Score, which shortens the game for whoever is
    # ahead on tempo.
    "The Arena's Greatest": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_SCORE, n=1, cond=COND_FIRST_TURN),)),
    ),

    # When you conquer here, you may pay {1 energy} and return a unit you
    # control here to its owner's hand. If you do, play a 2 Might Sand Soldier
    # unit token here.
    #
    # Pickpocket's shape: the whole ability is one "you may", so declining
    # removes it (383.3.a.2) and accepting performs both halves -- "if you do"
    # needs no separate condition. `same_loc_as_source` is what "here" means
    # for a battlefield's own target slot, and it is also what makes 355.8
    # decline to offer the ability when nothing of yours is standing there.
    #
    # The trade is a real one: a conquered battlefield is held by the units on
    # it (190.4.c), so bouncing one to replace it with a token risks the ground
    # unless the token lands first -- which it does, both ops resolving
    # together.
    "Emperor's Dais": (
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),
                     Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SAND_SOLDIER_TOKEN))),
    ),

    # When you defend here, reveal the top card of your Main Deck. If it's a
    # spell, put it in your hand. Otherwise, recycle it.
    #
    # `pick_optional=False` because the card gives no choice: a spell GOES to
    # hand, anything else IS recycled. The look machinery still routes it
    # through an A_PICK, but with a type restriction and no opt-out there is
    # exactly one legal action either way -- a forced choice, not a decision.
    # `rest_dest` is RECYCLE rather than Diana's TOP, which is the whole
    # difference between digging and filtering.
    "Ravenbloom Conservatory": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND,
                ops=(Op(OP_LOOK_TOP, n=1, pick_optional=False,
                        pick_types=("Spell",), pick_dest=DEST_HAND,
                        rest_dest=DEST_RECYCLE),)),
    ),

    # When you conquer here, ready 2 runes at the end of this turn.
    # The only delayed effect in the pool -- one card of 937 -- so it is banked
    # on a per-seat counter that `phases.ending` pays out, rather than a general
    # delayed-trigger queue built for a single user. Delayed is the whole point:
    # readying now would refund the runes you spent taking the ground, while
    # readying at end of turn refunds them for the OPPONENT's turn, which is
    # when they matter ([[riftbound-tapping-out-costs-the-opponents-turn]]).
    "Targon's Peak": (
        Ability(TR_CONQUER,
                ops=(Op(OP_READY_RUNES, n=2, at_end_of_turn=True),)),
    ),

    # At the start of your Beginning Phase, you may kill a unit you control
    # here to draw 1. (This happens before scoring.)
    #
    # Pickpocket's shape -- one "you may" covering cost and effect, so declining
    # removes the whole ability (383.3.a.2) and accepting does both.
    #
    # **"Before scoring" is the entire card, and it is why the Beginning Phase
    # had to learn to suspend.** 315.2.a is a step and 315.2.b is a later one,
    # but `start_turn` used to run both without stopping and drain the trigger
    # queue afterwards -- so killing your last unit here banked the Hold AND
    # drew the card. Now the ability resolves first, `control_cleanup` sees an
    # empty battlefield (190.4.c) and the Hold is gone: a real trade every turn
    # rather than a free draw.
    "Dusk Rose Lab": (
        Ability(TR_BEGINNING, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_KILL, target=0), Op(OP_DRAW, n=1))),
    ),

    # When you conquer here, discard 1, then draw 1.
    # The draw is a FOLLOW-UP, not a second op: ops after a discard run before
    # the player has picked, so writing it plainly would let them pitch the
    # card they just drew. "Then" is sequencing and not a condition, so an
    # empty hand still draws -- which `OP_DISCARD_CHOOSE` handles by running
    # the follow-up inline when there is nothing to discard.
    "Zaun Warrens": (
        Ability(TR_CONQUER, ops=(
            Op(OP_DISCARD_CHOOSE, n=1, then_key=FU_DRAW_1),)),
    ),
}


# Abilities printed on a Champion Legend (103.1). In the Legend Zone from turn
# 1 and never leaving it, so unlike everything else in these tables a legend's
# ability is available on EVERY turn of the game from the first -- which is why
# most of them charge an Exhaust, and why the Awaken Phase recharging it
# (315.1.b) is what makes them engines rather than one-shots.
LEGEND_ABILITIES: dict[str, tuple[Ability, ...]] = {

    # {4 energy}, Exhaust: Play a ready 3 Might Sprite unit token with
    # [Temporary]. This ability costs {1 energy} less for each friendly unit
    # with [Temporary].
    #
    # The most-played legend in the corpus by a distance (17 of 36 decks), and
    # the discount is the whole card: a wide Temporary board pays for the next
    # Sprite, so the ability gets cheaper exactly as the deck does what it
    # wants. The scaling lives in LEGEND_STATICS, where a cost discount
    # belongs; this half is only the effect.
    "Lillia - Bashful Bloom": (
        Ability(TR_ACTIVATED, cost_energy=4, cost_exhaust=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # {1 energy}, Exhaust: Play a 1 Might Recruit unit token.
    # No location clause, so it lands at the base.
    "Viktor - Herald of the Arcane": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # At the end of your turn, ready 2 runes.
    # Not an activated ability and costs no exhaust, so it pays out every turn
    # whatever the legend did -- which is why tapping out costs this deck less
    # than any other ([[riftbound-tapping-out-costs-the-opponents-turn]]).
    "Annie - Dark Child": (
        Ability(TR_END_OF_TURN, ops=(Op(OP_READY_RUNES, n=2),)),
    ),
}


LEGEND_STATICS: dict[str, tuple[Static, ...]] = {

    # "This ability costs {1 energy} less for each friendly unit with
    # [Temporary]" -- the scaling half of Lillia - Bashful Bloom.
    "Lillia - Bashful Bloom": (
        Static(ST_COST_ENERGY, n=1, per_keyword="Temporary",
               per_friendly=True, per_same_loc=False, per=CNT_BOARD),
    ),
}


STATICS: dict[str, tuple[Static, ...]] = {

    # I have +1 Might for each of your units with [Temporary] at my battlefield.
    "Petal Pixie": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per_keyword="Temporary",
               per_friendly=True, per_same_loc=True),
    ),

    # --- [Empowered] dependent abilities (828.1.b.1) -----------------------
    # "While I have the Empowered status, this card gains '[Text]'", so each of
    # these is an ordinary self-static with COND_EMPOWERED as its gate. Read
    # live: the status can be gained mid-turn and the bonus applies the instant
    # it is.

    "Solari Sunhawk": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Deflect", n=2, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Brutal Hunter": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Ambessa, Respected and Feared": (
        Static(ST_KEYWORD, keyword="Assault", n=2, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Shadow Fiend": (
        Static(ST_KEYWORD, keyword="Assault", n=3, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),

    # Your token units have +1 Might.  No location clause: it reaches the whole
    # board, which is what makes it the payoff for a token deck.
    "Soul Shepherd": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, scope_token=True),
    ),

    # [Legion] - I cost {2 energy} less.
    # (Get the effect if you've played another card this turn.)
    #
    # A 4-drop that is a 2-drop whenever it is not the first thing you do. The
    # condition is read LIVE here rather than off a snapshot, and that is the
    # whole subtlety of [Legion]: a cost is worked out as the card is played,
    # so this card has not been counted yet and any nonzero count is "another
    # card". The op side reads the snapshot instead, because by the time an
    # ability resolves the source HAS been counted.
    "Noxus Hopeful": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_LEGION),
    ),

    # --- costs that count a zone -------------------------------------------
    # I cost {1 energy} less for each card in your trash.
    #
    # A 10-Energy unit that no one ever pays 10 for. The count only goes UP:
    # a trash is the one zone that fills as a game runs and never empties on
    # its own, so unlike a board-counting discount this one cannot be answered
    # by killing anything. It is the payoff for a deck that was filling its
    # trash anyway -- and it is why Forge of the Future recycling an opponent's
    # trash is a real answer rather than a nuisance.
    "Rhasa the Sunderer": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per=CNT_TRASH),
    ),

    # I cost {2 energy} less for each card with my name in your trash.
    #
    # "With my name", so it counts only the other copies of Shadowblade Lurker
    # -- at 3 in a deck this is at most -4, and it rewards trading the early
    # ones away. `per_same_name` is the difference between that and Rhasa.
    "Shadowblade Lurker": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, per=CNT_TRASH,
               per_same_name=True),
    ),

    # I cost {1 energy} less for each gear you control.
    #
    # A BOARD count rather than a zone one, and `per_card_type` instead of
    # `per_keyword` -- "gear" is a type, not a keyword. No location clause:
    # "you control" is the whole board, so `per_same_loc` is off.
    "Plaza Guardian": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per_card_type="Gear",
               per_friendly=True, per_same_loc=False),
    ),

    # [Level 11][>] I have +4 Might. (While you have 11+ XP, get the effect.)
    #
    # A static gated on a threshold, and read LIVE rather than snapshotted:
    # XP never resets, so there is no past moment to capture, and 143.2.a means
    # the +4 arriving can save a damaged unit exactly as losing it could kill
    # one. Eleven XP is most of a game away, which is the card.
    "Targonian Visionary": (
        Static(ST_MIGHT, n=4, scope=SC_SELF, cond=COND_LEVEL, level=11),
    ),

    # The other half of Lillia - Protector of Dreams. `scope_token` is what
    # makes it "your TOKEN units": without it she hands [Tank] to every unit
    # you control, which is a different card.
    "Lillia - Protector of Dreams": (
        Static(ST_KEYWORD, keyword="Tank", n=1, scope=SC_FRIENDLY_UNITS,
               scope_token=True),
    ),

    # --- statics that grant a KEYWORD ---------------------------------------
    # [Hunt 2] [Level 3][>] I have +1 Might and [Deflect].
    #
    # Two statics from one sentence, both gated on the same level -- "+1 Might
    # AND [Deflect]" is a Might static beside a keyword static, not one thing.
    # [Hunt 2] is absent because `abilities_for` synthesises it.
    "Mosstomper": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=3),
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=3),
    ),

    # [Hunt 2] [Level 3][>] I have +1 Might and [Ganking].
    "Gustwalker": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=3),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=3),
    ),

    # [Hunt 2] [Level 6][>] I have [Deflect] and [Ganking].
    "Master Yi - Tempered": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=6),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=6),
    ),

    # Other friendly units here have [Assault]. (+1 Might while attacking.)
    #
    # "OTHER ... HERE" is both narrowings at once: it never pumps Farron
    # himself, and it reaches only the battlefield he is standing on. Without
    # `scope_same_loc` this would buff units at the other battlefield and at
    # base, which is a different and much better card.
    "Captain Farron": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_FRIENDLY_UNITS,
               scope_not_self=True, scope_same_loc=True),
    ),

    # I can't be chosen by enemy spells and abilities.
    # Not [Deflect], which prices the choice -- this removes it. Nothing here
    # protects against damage or a sweep, neither of which chooses (355.10),
    # so a board wipe still answers it.
    "Ruin Runner": (
        Static(ST_UNCHOOSABLE, scope=SC_SELF),
    ),

    # Other friendly units here have [Shield]. Farron's shape on the defending
    # side: his own printed [Shield] and [Tank] are engine keywords and need no
    # entry, so the granted one is the whole card.
    "Taric - Protector": (
        Static(ST_KEYWORD, keyword="Shield", n=1, scope=SC_FRIENDLY_UNITS,
               scope_not_self=True, scope_same_loc=True),
    ),

    # Dr. Mundo - Expert wants exactly this shape on the Might side -- "My
    # Might is increased by the number of cards in your trash" is `Static(
    # ST_MIGHT, n=1, scope=SC_SELF, per=CNT_TRASH)` and works today. He is
    # deliberately NOT here, because his second sentence ("At the start of your
    # Beginning Phase, recycle 3 from your trash") has no Beginning Phase
    # trigger to hang on, and presence in this table is what tells
    # `decks.plays_as_printed` a card's whole text is transcribed. Half a card
    # listed here would silently inflate the coverage number.
    #
    # The combination is worth reaching, though, and `test_statics` drives it
    # directly: a static that reads a ZONE moves when nothing on the board
    # moved, and 143.2.a is continuous -- so Mundo's own recycle shrinks him by
    # 3 and can kill him where he stands.
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

    # When you play me, draw 1.
    "Cloud Drake": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Deathknell] If I died alone, draw 1.
    # 808.1 makes [Deathknell] short for "When I die, [Effect]", so the keyword
    # is TR_DEATH and the card's own text is the whole ability. "Alone" is a
    # CONDITION -- checked on resolution, nothing to target -- and the card's
    # reminder defines it: "no other friendly units here".
    "Lonely Poro": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=1, cond=COND_DIED_ALONE),)),
    ),

    # When you play me, ready ANOTHER friendly Mech. A tag restriction plus
    # `not_self` -- Bubble Bot is itself a Mech, and would otherwise be the
    # obvious pick for its own trigger.
    "Bubble Bot": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_FRIENDLY, tags=("Mech",),
                                    not_self=True),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # [Hidden] When you play me, give a unit -2 Might this turn, to a minimum
    # of 1 Might. The floor is printed on the card, stricter than 143.2.b's
    # general floor of 0, so it rides on the Op rather than being a rule.
    "Blastcone Fae": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2, floor=1),)),
    ),

    # When you play me, you may kill a gear.
    "Disarming Rake": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    optional=True),),
                ops=(Op(OP_KILL, target=0),)),
    ),

    # --- trash recursion, on a trigger -------------------------------------
    # 355.8 makes the empty-trash case free: an ability whose only slot has no
    # legal choice is never put on the Chain at all, so none of these deadlock
    # on turn one. That is already enforced centrally in `chain.fire`.

    # When you play me, return a unit from your trash to your hand.
    "Cemetery Attendant": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a spell from your trash to your hand.
    "Annie - Stubborn": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Spell",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a gear from your trash to your hand.
    "Aspiring Engineer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Gear",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a Bird, Cat, Dog, or Poro from your trash to
    # your hand. A TAG list, not a type list -- the card says nothing about
    # whether the thing it returns is a unit.
    "Starhound": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    tags=("Bird", "Cat", "Dog", "Poro")),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, you may play a spell from your trash with Energy cost
    # no more than {3 energy}, ignoring its Energy cost. Recycle that spell
    # after you play it. (You must still pay its Power cost.)
    #
    # The most-played unencoded card in the corpus, and it needs every piece of
    # the trash cluster at once: a trash slot, a cost restriction on it, an
    # alternate cost, and a third destination.
    #
    # **"Recycle that spell" is not "banish" and not "trash".** It goes to the
    # BOTTOM of Fizz's controller's own Main Deck (416.1.a), so the spell comes
    # back around and can be drawn again -- unlike [Flow], which banishes what
    # it replays. The two cards do the same thing and dispose of it differently,
    # which is exactly why the destination rides on the Chain Item rather than
    # being read off the card.
    #
    # `playable` makes the Power cost part of target LEGALITY: a spell whose
    # Power Fizz's controller cannot pay was never a legal choice.
    "Fizz - Trickster": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Spell",),
                                    max_energy=3, playable=True,
                                    playable_cost=COST_NO_ENERGY),),
                ops=(Op(OP_PLAY_FROM_TRASH, target=0, dest=DEST_RECYCLE,
                        cost=COST_NO_ENERGY),)),
    ),

    # When you play me, you may play a unit from your trash, ignoring its
    # Energy cost. (You must still pay its Power cost.)
    "Soulgorger": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                                    playable=True,
                                    playable_cost=COST_NO_ENERGY),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_NO_ENERGY),)),
    ),

    # When you play me, you may play a unit costing no more than {3 energy} and
    # no more than {any rune} from your trash, ignoring its cost.
    #
    # "Ignoring its COST", not "its Energy cost" -- both halves are waived, and
    # Soulgorger three entries up is the same card with the other wording. The
    # cost restriction is on the PRINTED cost, which is what makes the two
    # numbers meaningful at all when nothing is being paid.
    "Spectral Matron": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                                    max_energy=3, max_power=1, playable=True,
                                    playable_cost=COST_FREE),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_FREE),)),
    ),

    # [Deathknell] You may play a unit with cost no more than {3 energy} and no
    # more than {any rune} from your trash, ignoring its cost.
    #
    # Spectral Matron's ability on a death trigger instead of an entry one, so
    # it pays off trading her away -- and by then the trash is fuller.
    "Glasc Mixologist": (
        Ability(TR_DEATH, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                                    max_energy=3, max_power=1, playable=True,
                                    playable_cost=COST_FREE),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_FREE),)),
    ),

    # When I hold, you may return a unit or gear from your trash to your hand.
    # A Hold trigger, so it pays off a battlefield that survived the opponent's
    # whole turn -- and "unit or gear" is why `card_type` is a tuple.
    "Guardian of the Passage": (
        Ability(TR_HOLD, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
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

    # When you play me, play a 2 Might Sand Soldier unit token here.
    "Royal Guard": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SAND_SOLDIER_TOKEN),)),
    ),

    # [Deathknell] Play a 1 Might Bird unit token with [Deflect] to your base.
    # T_MY_BASE, not T_HERE: 808.1 fires the Deathknell as I die, and "your
    # base" is the controller's, which is where the token goes however far
    # forward I died. The Bird card carries [Deflect] itself.
    "Carrion Dredger": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=BIRD_TOKEN),)),
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
                ops=(Op(OP_MODIFY_MIGHT_ALL, n=-3, floor=1, who=W_ENEMY),)),
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

    # When a friendly unit attacks or defends alone, give it +1 Might this turn.
    #
    # **The first trigger that fires for a permanent other than its own
    # source.** Every trigger before this one was about itself -- "when I die",
    # "when I conquer" -- so C_SRC did both jobs. This gear sits at a base and
    # watches a battlefield, so the ability's source and its subject are
    # different permanents: T_SELF is the Mask, T_SUBJECT is the unit that
    # attacked, and "give IT +1" means the latter.
    #
    # A TRIGGER, not a static, and the card is worded to say so. Master Yi -
    # Wuju Bladesman's "WHILE a friendly unit defends alone, it gets +2" is a
    # static that evaporates the moment a second unit arrives; this one gives
    # +1 "this turn", so it is banked at the moment of the attack and survives
    # reinforcements, the end of the Combat, and the unit walking home.
    #
    # 740.2.a defines alone as "no other friendly units at the same location",
    # checked when the Combat begins -- part of the trigger condition, so a
    # unit that is not alone never triggers at all.
    "Mask of Foresight": (
        Ability(TR_ATTACK_OR_DEFEND, subject_alone=True,
                subject_any_friendly=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SUBJECT, n=1),)),
    ),

    # When I move, discard 1, then draw 1.
    # The mirror of Undercover Agent's "discard 2, then draw 2", and the same
    # reason the order is written down: discarding first means the card drawn
    # was never a candidate to be discarded.
    "Traveling Merchant": (
        Ability(TR_MOVE,
                ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=1))),
    ),

    # When you play me OR when I hold, look at the top 4 cards of your Main
    # Deck. You may reveal a gear from among them and draw it. Then recycle the
    # rest.
    # "or when I hold" is two triggers on one effect, which is two Ability
    # entries -- the DSL has no disjunction and does not need one. `pick_types`
    # is the "a GEAR from among them" restriction; "you may" makes it optional,
    # which it has to be anyway since four cards need contain no gear at all.
    "Ornn - Blacksmith": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_LOOK_TOP, n=4, pick_optional=True,
                        pick_types=("Gear",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),)),
        Ability(TR_HOLD,
                ops=(Op(OP_LOOK_TOP, n=4, pick_optional=True,
                        pick_types=("Gear",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),)),
    ),

    # When you play me, deal 3 to all units at battlefields.
    # `at_battlefields` is the plural clause the card actually prints -- every
    # battlefield, sparing only what sits in a base. Untargeted (355.10), and
    # unscoped by `who`, so it hits my own units too.
    "Tibbers": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DAMAGE_ALL, n=3, at_battlefields=True),)),
    ),

    # When you play me, stun a unit.
    "Solari Shieldbearer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_STUN, target=0),)),
    ),

    # [Hidden] When you play me, give me +3 Might this turn.
    "Teemo - Scout": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=3),)),
    ),

    # When I attack, ready another friendly unit.
    # `not_self` is "another": I am attacking, so I am a friendly unit at this
    # location and would otherwise be a legal choice for my own ability.
    "Twilight Reveler": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # {1 energy}, Exhaust: Move a friendly unit at a battlefield to your base.
    # T_MY_BASE, not T_OWNER_BASE: the card says "YOUR base" and the slot is
    # friendly anyway, so the two agree here -- but the words are what is
    # transcribed, and a later card saying "its base" needs the other one.
    "The Syren": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_MY_BASE),)),
    ),

    # [Deathknell] Discard 2, then draw 2.
    # Order matters and "then" is what fixes it: the discard happens first, so
    # the cards drawn are never candidates to be discarded.
    "Undercover Agent": (
        Ability(TR_DEATH,
                ops=(Op(OP_DISCARD, n=2), Op(OP_DRAW, n=2))),
    ),

    # When you play me, kill an enemy unit with 3 Might or less.
    # A RESTRICTION, not a condition (355.9.b): a 4-Might unit was never a
    # legal choice, so growing one in response does not make this fizzle -- it
    # was never pointed there. Contrast "kill a unit IF it has 3 or less".
    "Sandshifter": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, max_might=3),),
                ops=(Op(OP_KILL, target=0),)),
    ),

    # [Deathknell] Deal 4 to an enemy unit.
    # No location clause, so it reaches across the board from wherever I died.
    "Ruined Rex": (
        Ability(TR_DEATH,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_DAMAGE, target=0, n=4),)),
    ),

    # Exhaust: Give a unit -1 Might this turn, to a minimum of 1 Might.
    # A gear, so 151.2 restricts the ability to its controller's Main Phase in
    # an Open State -- which is what SPEED_MAIN already means.
    "Orb of Regret": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1, floor=1),)),
    ),

    # When you play me, kill an enemy unit.
    "Harnessed Dragon": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_KILL, target=0),)),
    ),

    # When I conquer, give a friendly unit +8 Might this turn.
    "Inviolus Vox": (
        Ability(TR_CONQUER,
                targets=(TargetSpec(who=W_FRIENDLY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=8),)),
    ),

    # --- [Empower] (827) ---------------------------------------------------
    # 827.1.c.1 -- "[Cost]: Empower this. Play only if not Empowered." The
    # "only if not Empowered" half is NOT written on each card: the action
    # layer reads it off OP_EMPOWER, because it is part of what the keyword
    # abbreviates rather than something these cards each chose to print.
    # The payoff is a STATIC gated on COND_EMPOWERED -- see STATICS below.

    # [Empower] {2 energy}. [Empowered] I have +1 Might and [Deflect 2].
    "Solari Sunhawk": (
        Ability(TR_ACTIVATED, cost_energy=2, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {3 energy}. [Empowered] I have +2 Might and [Ganking].
    "Brutal Hunter": (
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {1 energy}{Order rune}{Order rune}. [Empowered] I have
    # [Assault 2].  Two rune symbols is cost_power=2, not one.
    "Ambessa, Respected and Feared": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=2,
                ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {2 energy}{Fury rune}. [Empowered] I have [Assault 3].
    "Shadow Fiend": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {1 energy}{Order rune}.
    # [Empowered] [Deathknell] Play two 1 Might Recruit unit tokens to your
    # base. ("When I die while Empowered, get the effect.")
    # A dependent ability that is itself a TRIGGER (828.1.d), so the gate rides
    # on the OP rather than on a static -- and it is checked against the corpse:
    # by the time a Deathknell resolves the source is dead, and the status it
    # held when it died is what the card asked about.
    "Noxian Emissary": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2,
                        token=RECRUIT_TOKEN, cond=COND_EMPOWERED),)),
    ),

    # [Deathknell] Channel 1 rune exhausted.
    "Soaring Scout": (
        Ability(TR_DEATH, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # [Accelerate] [Deathknell] Channel 2 runes exhausted and draw 1.
    # The draw is unconditional here -- contrast Catalyst of Aeons, where it is
    # a consolation for coming up short.
    "Tasty Faefolk": (
        Ability(TR_DEATH, ops=(Op(OP_CHANNEL, n=2), Op(OP_DRAW, n=1))),
    ),

    # [Tank] When you play me, channel 1 rune exhausted.
    "Stormclaw Ursine": (
        Ability(TR_PLAY_ME, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # [Hidden] The next time a friendly unit would die, kill this instead.
    # Recall that unit exhausted.
    # A delayed replacement, registered as the gear resolves (337.2 puts a gear
    # on the board immediately) and consumed by the next friendly death.
    # No heal: Guardian Angel's effect text says "Heal me" where this one does
    # not (136.2.d), so a unit recalled with lethal damage still marked dies
    # again on the next continuous check. That is the card -- it answers
    # targeted removal, not damage.
    "Zhonya's Hourglass": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DEATH_GUARD),)),
    ),

    # [Vision] When I conquer, if you've played a non-token unit, a non-token
    # gear, and a spell this turn, you score 1 point.
    # [Vision] is synthesised from the keyword, so only the conquer clause is
    # written here. The trio is a CONDITION checked at resolution, not a
    # restriction: it can be satisfied (or not) after the trigger fires.
    "Swain, Visionary": (
        Ability(TR_CONQUER,
                ops=(Op(OP_SCORE, n=1, cond=COND_PLAYED_TRIO),)),
    ),

    # [Deflect] When an opponent plays a unit while I'm at a battlefield,
    # [Stun] it. They can't move it this turn.
    # `subject_enemy` flips TR_PLAY_UNIT to watch the OTHER seat, and the
    # subject is the permanent just played -- not a target, so the opponent
    # gets no say and [Deflect] never enters into it.
    #
    # "while I'm at a battlefield" is a condition on Vex, not on the unit
    # played: a Vex sitting in a base watches nothing.
    "Vex - Apathetic": (
        Ability(TR_PLAY_UNIT, subject_enemy=True, subject_at_battlefield=True,
                ops=(Op(OP_STUN, target=T_SUBJECT),
                     Op(OP_NO_MOVE, target=T_SUBJECT))),
    ),

    # When I move, draw 1, then discard 1. Then, do the following based on the
    # discarded card's type: Spell - Draw 1. Gear - Ready up to 2 runes.
    # Unit - Give me +3 Might this turn.
    #
    # The discard is a real CHOICE and that is the whole card: which card you
    # pitch is how you pick the mode. `phases.discard`'s take-the-oldest rule
    # would have chosen the mode for the player.
    "Hwei - Brooding Painter": (
        Ability(TR_MOVE,
                ops=(Op(OP_DRAW, n=1),
                     Op(OP_DISCARD_CHOOSE, branch_key=DB_HWEI))),
    ),

    # [Accelerate] [Deathknell] Recycle me to ready your runes.
    # "Recycle me" is a cost WITHIN the instructions (383.3.b) but not an
    # optional one -- the card does not say "you may" -- so it is simply the
    # first op. By the time a Deathknell resolves the card is already in the
    # trash (808.1.d.2), which is where the recycle takes it from.
    #
    # "your runes", unbounded: every spent rune readies, which is what makes
    # this a whole extra turn's worth of resources.
    "Ekko - Recurrent": (
        Ability(TR_DEATH,
                ops=(Op(OP_RECYCLE_SELF),
                     Op(OP_READY_RUNES, n=MAX_DECK))),
    ),

    # When you play me, discard 1, then draw 1.
    # "discard 1" with no choice of card, unlike Hwei -- so this is
    # `phases.discard`'s take-the-oldest rule, which is what the card means
    # when it names no chooser. Discard first: the drawn card is never a
    # candidate to be pitched.
    "Evershade Stalker": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=1))),
    ),

    # [Vision] [Action] Kill this, Exhaust: Give a unit +2 Might this turn.
    # Two costs at once (204.1.b), and [Vision] is synthesised from the
    # keyword, so only the activated ability is written here.
    "Divining Shells": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_exhaust=True,
                cost_kill_self=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),)),
    ),

    # [Accelerate] When I move, if you control 4 or fewer runes, draw 1.
    # A CONDITION checked at resolution, not a restriction: the move has
    # already happened and the rune board can change in the response window.
    "Eclipse Dragon": (
        Ability(TR_MOVE,
                ops=(Op(OP_DRAW, n=1, cond=COND_FEW_RUNES, level=4),)),
    ),

    # [Deathknell] If I didn't die alone, draw 1.
    # The mirror of Lonely Poro, reading the same F_DIED_ALONE snapshot the
    # other way round. Past tense either way: recorded at the moment of death,
    # because a priority window sits between dying and the ability resolving.
    "Loyal Poro": (
        Ability(TR_DEATH,
                ops=(Op(OP_DRAW, n=1, cond=COND_NOT_DIED_ALONE),)),
    ),

    # When I move FROM a battlefield, give me +2 Might this turn.
    # TR_MOVE's captured `ctx` is the location left behind, so this asks about
    # where the unit came from and not where it is now -- a unit walking home
    # to its base qualifies, one leaving its base does not.
    "Harpoon Squad": (
        Ability(TR_MOVE,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_CTX_BATTLEFIELD),)),
    ),

    # [Hidden] When you play me TO A BATTLEFIELD, deal 2 to an enemy unit here.
    # [Hidden] is what makes the condition reachable: a unit played from hand
    # normally lands at a base, and 811.1.d.3 puts a hidden one at the
    # battlefield it was hidden at.
    "Mischievous Marai": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_DAMAGE, target=0, n=2, cond=COND_SELF_AT_BF),)),
    ),

    # When I move to a battlefield, play a 1 Might Recruit unit token here.
    # "to a battlefield" gates on where I landed; "here" is that same place.
    "Noxian Drummer": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=RECRUIT_TOKEN, cond=COND_SELF_AT_BF),)),
    ),

    # When I move to a battlefield, give ANOTHER friendly unit +1 Might this
    # turn.  `not_self` is the "another": I am a friendly unit too.
    "Ribbon Dancer": (
        Ability(TR_MOVE,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=1,
                        cond=COND_SELF_AT_BF),)),
    ),

    # [Accelerate] When I attack, if you control 4 or fewer runes, deal 2 to
    # all enemy units here.  Three pieces that already existed: the attack-only
    # role, the rune-board count, and a sweep scoped to one location and side.
    "Renekton, Rage Fueled": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_DAMAGE_ALL, at=T_HERE, n=2, who=W_ENEMY,
                        cond=COND_FEW_RUNES, level=4),)),
    ),

    # When you play ANOTHER unit, give me +2 Might this turn.
    # `subject_not_self` is the "another": without it this would grow by 2 the
    # moment it arrived, off its own play.
    "Reluctant Leader": (
        Ability(TR_PLAY_UNIT, subject_not_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When you play me, draw 1.
    # [Deathknell] Choose an opponent. They reveal their hand. You can look at
    # their facedown cards this turn. Gain 1 XP.
    #
    # The first card whose payload is PURE INFORMATION -- nothing moves, no
    # choice is carried, and its whole value is what the policy can see
    # afterwards. "Choose an opponent" is not a choice in a two-player game
    # (there is one), so it is resolved rather than offered, the same way
    # Sabotage does it. The 0-Might reminder needs no entry: 469/470 never
    # asked about Might, so a 0-Might unit already conquers and holds.
    "Scuttle Crab": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_DEATH, ops=(Op(OP_SEE_HAND),
                               Op(OP_SEE_FACEDOWN),
                               Op(OP_GAIN_XP, n=1))),
    ),

    # When you choose or ready me, give me +1 Might this turn.
    # Two triggers on one card, both narrowed to the card itself. Awaken counts
    # as readying, so she grows once a turn for free on top of anything you
    # point at her -- and [Deflect] is an engine keyword, so it needs no entry.
    "Irelia, Fervent": (
        Ability(TR_READIED, subject_is_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
        Ability(TR_CHOSEN, subject_is_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # When you ready a friendly unit, give IT +1 Might this turn.
    # The other side of the same trigger: the subject is whatever was readied,
    # not the watcher. On a wide board Awaken fires this once per exhausted
    # unit, which is what makes it a payoff for attacking with everything.
    "Pirate's Haven": (
        Ability(TR_READIED, ops=(Op(OP_MODIFY_MIGHT, target=T_SUBJECT, n=1),)),
    ),

    # When you choose me with a spell, draw 1. An ability that chooses is still
    # a choice (355.7), so "with a spell" is a real narrowing rather than
    # flavour text.
    "Jae Medarda": (
        Ability(TR_CHOSEN, subject_is_self=True, subject_by_spell=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Reaction] [Temporary] When an OPPONENT scores, draw 1.
    # A gear rather than a unit, which the watcher does not care about --
    # `fire_watchers` walks permanents, and only statics restrict themselves to
    # units. [Temporary] caps it at one turn, so it reads the opponent's next
    # scoring window and then dies before your own Beginning Phase scores.
    "Sumpworks Map": (
        Ability(TR_OPPONENT_SCORES, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you play a GEAR, ready me. The same watcher Reluctant Leader uses,
    # pointed at the other card type -- and the card that made the missing
    # `subject_card_type` filter visible, since without it every unit watcher
    # was already firing on gear.
    "Pit Crew": (
        Ability(TR_PLAY_UNIT, subject_card_type="Gear",
                ops=(Op(OP_READY, target=T_SELF),)),
    ),

    # When another friendly unit dies, give me +2 Might this turn.
    "Spectral Centaur": (
        Ability(TR_OTHER_DIES,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When you use an activated ability of a gear, give me +1 Might this turn.
    "Prize of Progress": (
        Ability(TR_GEAR_ABILITY,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # When you discard ONE OR MORE cards, ready me and give me +1 Might this
    # turn.  "one or more" is one trigger per discard EVENT, not per card: a
    # card that pitches two fires this once.
    "Jinx - Rebel": (
        Ability(TR_DISCARD,
                ops=(Op(OP_READY, target=T_SELF),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=1))),
    ),

    # [Hunt] [Level 6] When you play me, draw 1.
    # [Hunt] is synthesised from the keyword; the draw is gated on 6+ XP, which
    # COND_LEVEL already expresses.
    "Wuju Apprentice": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_LEVEL, level=6),)),
    ),

    # When you play me, return ANOTHER unit at a battlefield to its owner's
    # hand.  Unqualified by side, so it can bounce your own -- and `not_self`
    # is the "another", since an Ambushed Bouncer is itself at a battlefield.
    "Zaunite Bouncer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    not_self=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # The first time a friendly unit dies each turn, draw 1.
    # A watcher for another's death with a once-per-turn gate. "A friendly
    # unit" includes this one, but a watcher never sees its own death -- it is
    # already gone -- so the practical reading matches TR_OTHER_DIES.
    "Wraith of Echoes": (
        Ability(TR_OTHER_DIES, once_each_turn=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # When a showdown begins here, you may pay {1 energy}. If you do,
    # [Predict], then reveal the top card of your Main Deck. If it's a spell,
    # draw it.
    #
    # "When a showdown begins HERE" is TR_ATTACK_OR_DEFEND on herself: 459
    # designates every unit at the battlefield the moment a Combat begins, so
    # a showdown starting at Diana's battlefield is exactly when she is an
    # attacker or a defender.
    #
    # Two deferred decisions in sequence, which is what `then_key` is for --
    # the Predict suspends, and its follow-up suspends again for the reveal.
    "Diana - Lunari": (
        Ability(TR_ATTACK_OR_DEFEND, optional=True, opt_cost_energy=1,
                ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP,
                        then_key=FU_DIANA_REVEAL),)),
    ),

    # When I attack, you may pay {1 energy} to give a unit here -1 Might this
    # turn.  383.3.b again: an optional COST, so the offer only appears when
    # the energy is there. "a unit here" is unqualified -- it may point at your
    # own, which is occasionally what you want against a damage check.
    "Icevale Archer": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_ANY, same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1),)),
    ),

    # When I move to a battlefield, you may move an enemy unit to that
    # battlefield.  A free "you may" (383.3.a), decided at finalization -- no
    # cost, unlike Icevale Archer directly above.
    #
    # **"THAT battlefield", not "this" -- so the destination is `T_CTX2`, the
    # one captured when she moved, and the ability does not need her alive.**
    # Written first as `T_HERE` + `COND_SELF_AT_BF`, which read her row at
    # resolution and so was really "move an enemy unit to wherever I am
    # standing". Both halves of that fail to the same response: Gust her in
    # answer to the trigger (she is 1 Might, so she is always a legal Gust) and
    # the ability resolved doing nothing. 383.2.c.2 says an ability whose
    # source has left resolves WITHOUT it -- it does not fizzle -- and 359.3.f.3
    # says the battlefield it names was pinned when it triggered. Compare
    # Noxian Drummer two entries down, whose "play a Recruit token HERE" is
    # genuinely a live read of her own square and IS meant to do nothing once
    # she is gone.
    "Irresistible Faefolk": (
        Ability(TR_MOVE, optional=True,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_CTX2,
                        cond=COND_CTX2_BATTLEFIELD),)),
    ),

    # When I hold, if there is exactly one other unit you control here, draw 1.
    # EXACTLY one -- a second friendly unit at the battlefield turns it off,
    # which is what makes it a condition rather than a threshold.
    "Shen, Scourge of Shadows": (
        Ability(TR_HOLD,
                ops=(Op(OP_DRAW, n=1, cond=COND_N_OTHERS_HERE, level=1),)),
    ),

    # When you play me, draw 1 if your other units have total Might 5 or more.
    # "OTHER units" excludes me, and the total is EFFECTIVE Might -- statics
    # and buffs count, which is the number the player can actually see.
    "Kinkou Initiate": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_OTHERS_MIGHT, level=5),)),
    ),

    # When you play me, you may kill a gear with Energy cost no more than
    # {1 energy}. If you do, play a Gold gear token exhausted.
    # A free "you may" (383.3.a) decided at finalization, so "if you do" needs
    # no separate condition -- declining removes the whole ability, and
    # accepting performs both halves.
    "Pickpocket": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    max_energy=1),),
                ops=(Op(OP_KILL, target=0),
                     Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN))),
    ),

    # When you play me, draw 1 for each of your [Mighty] units.
    # 5+ Might is Mighty, and it is EFFECTIVE Might -- statics and buffs count,
    # which is what the player sees on the board. Kadregrin is on the board by
    # the time this resolves (359.2.b), so it counts itself if it qualifies.
    "Kadregrin the Infernal": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, n_from_count=CT_MY_MIGHTY_UNITS),)),
    ),

    # When you play me, give a unit +8 Might this turn.
    "Whiteflame Protector": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=8),)),
    ),

    # When I attack, you may pay {1 energy} to move an enemy unit here to its
    # base.  383.3.b optional cost; "here" is my battlefield, and "ITS base"
    # is the moved unit's owner's, not mine.
    "Sinister Poro": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When I DEFEND, you may kill me to move an attacking unit to its base.
    # Sinister Poro's shape from the other side of the fight, and the first
    # ability whose optional cost is a body rather than runes. "An attacking
    # unit" carries no ownership clause, but 459 only designates the Attacker's
    # units as attacking, so `attacking` already scopes it to the enemy side
    # and to the contested battlefield.
    "Overzealous Fan": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND,
                optional=True, opt_cost_kill_self=True,
                targets=(TargetSpec(who=W_ANY, attacking=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # [Hidden] When you play me, you may return ANOTHER unit at a battlefield
    # with 3 Might or less to its owner's hand.
    # `max_might` is a restriction (355.9.b) read against EFFECTIVE Might and
    # re-checked at resolution (359.3.e), so growing the target during the
    # response window takes it out of range and this does nothing to it.
    "Windsinger": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    not_self=True, max_might=3),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # When another NON-RECRUIT unit you control dies, play a 1 Might Recruit
    # unit token into your base.
    # The tag exclusion is load-bearing: Viktor makes Recruits, so without it
    # each token's death would make another one, forever.
    "Viktor - Leader": (
        Ability(TR_OTHER_DIES, subject_lacks_tag="Recruit",
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # When you play me OR at the start of your Beginning Phase, play a ready
    # 3 Might Sprite unit token with [Temporary] to your base.
    # "or" is two triggers on one effect, which is two entries. The token
    # carries [Temporary] itself, so it expires through the existing path.
    "Sprite Queen": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
        Ability(TR_BEGINNING,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When I attack, give me +2 Might this turn if there is a READY enemy unit
    # here.  Exhausted enemies do not count -- the card pays you for attacking
    # into something that can still fight back.
    "Dune Drake": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_READY_ENEMY_HERE),)),
    ),

    # I can't be chosen by enemy spells and abilities unless I'm in combat.
    # When I move to a battlefield, give me +2 Might this turn.
    # The first clause is a targeting restriction and lives in
    # SAFE_UNLESS_IN_COMBAT; only the trigger is written here.
    "Akali, Silent": (
        Ability(TR_MOVE,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_SELF_AT_BF),)),
    ),

    # [Ambush] When I attack, [Stun] an enemy unit here.
    # Leona's shape exactly, and both were unreachable until the attack/defend
    # trigger learned to tell attacking from defending (459) and "here" from
    # "anywhere".
    "Vi - Peacekeeper": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_STUN, target=0),)),
    ),

    # [Shield] When I attack, stun an enemy unit here.
    "Leona, Determined": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_STUN, target=0),)),
    ),

    # [Deathknell] Deal 4 to all units at my battlefield.
    # "all units", unscoped by `who`: it takes friendly units with it, which is
    # the cost of the effect rather than an oversight. T_HERE on a death
    # trigger is the location the source died at -- 808.1 fires as I die, and
    # the row keeps its P_LOC.
    "Kog'Maw - Caustic": (
        Ability(TR_DEATH,
                ops=(Op(OP_DAMAGE_ALL, at=T_HERE, n=4),)),
    ),

    # When you play me, give a unit +3 Might this turn.
    # "a unit" is unqualified, so it may point at an enemy -- pointless here,
    # but the slot is what the card prints and W_ANY is that word's absence.
    "Field Musicians": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),)),
    ),

    # [Ambush] When you play a spell, give me +2 Might this turn.
    # TR_PLAY_SPELL fires on FINALIZATION (349), so the +2 lands while the
    # spell is still on the Chain and applies even if the spell is countered.
    "Diana, No Longer Human": (
        Ability(TR_PLAY_SPELL,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # [Ambush] When you play me, you may return a friendly unit at a
    # battlefield to its owner's hand.
    # "a friendly unit", not "another": Ambush plays me straight to a
    # battlefield, so I am one of the legal choices and bouncing myself is a
    # real (if usually bad) line. `not_self` would be a card the printer did
    # not print.
    "Grim Apothecary": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # When you play this, draw 1.
    # {1 energy}{Calm rune}, Exhaust, Kill this: Draw 1.
    # A gear with both halves: an ETB and an activated ability whose base cost
    # (204.1.b) is three things at once -- runes, an exhaust, and its own life.
    # The Power symbol is paid in the card's own domain, which `cost_power`
    # leaves to `plan_ability_cost` to read off the card.
    "Poro Snax": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1,
                cost_exhaust=True, cost_kill_self=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # --- the Gold makers (187.5) -------------------------------------------
    # All of these print "exhausted", which is `Op.ready` left False, and all
    # of them put the gear at the controller's base under 149.2.

    # When I conquer, play a Gold gear token exhausted.
    "Plundering Poro": (
        Ability(TR_CONQUER,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # [Deathknell] Play a Gold gear token exhausted.
    "Honest Broker": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When I move, play a Gold gear token exhausted.
    "Treasure Hunter": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When I hold, play two Gold gear tokens exhausted.
    "Eminent Benefactor": (
        Ability(TR_HOLD,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2,
                        token=GOLD_TOKEN),)),
    ),

    # When you play me, play four Gold gear tokens exhausted.
    "Trove Golem": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=4,
                        token=GOLD_TOKEN),)),
    ),

    # NOT transcribed: Pyke - Bloodharbor Ripper, whose "{1 energy}, Exhaust:
    # Return a friendly unit at a battlefield to its owner's hand. Play a Gold
    # gear token exhausted" is otherwise ordinary. It is a LEGEND, and the
    # engine parses Legends out of a decklist but never puts one into play, so
    # the ability could never fire -- `decks.includable` excludes the type
    # outright and the coverage gate in test_triggers catches the spec as
    # uncounted. Encode it with the rest of the Legends once they exist.

    # When I attack, deal 3 to all enemy units here.
    # T_HERE is my own location; "here" on an attack trigger is the contested
    # battlefield because that is where I must be to be attacking from it.
    "Anivia - Primal": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_DAMAGE_ALL, at=T_HERE, n=3, who=W_ENEMY),)),
    ),

    # When I attack, deal 1 to an enemy unit here.
    "Crackshot Corsair": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_DAMAGE, target=0, n=1),)),
    ),

    # When I attack or defend, give an enemy unit here -2 Might this turn, to a
    # minimum of 1 Might.  No role restriction -- this is the card that names
    # both sides, and the one the old unconditional `is_alone` gate would have
    # silently narrowed to units standing by themselves.
    "Ahri, Inquisitive": (
        Ability(TR_ATTACK_OR_DEFEND,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2, floor=1),)),
    ),

    # --- XP ---------------------------------------------------------------
    # [Hunt] is NOT transcribed on any of these: it is synthesised from the
    # keyword in `abilities_for`, because its effect is fixed by the keyword
    # rather than written on the card. Repeating it here would double it.

    # When you play me, gain 1 XP.
    "Demacian Diplomat": (
        Ability(TR_PLAY_ME, ops=(Op(OP_GAIN_XP, n=1),)),
    ),

    # [Hunt] When you play me, gain 2 XP.
    "Herald of Spring": (
        Ability(TR_PLAY_ME, ops=(Op(OP_GAIN_XP, n=2),)),
    ),

    # [Hunt] Spend 2 XP: [Buff] me.
    # (Give me a +1 Might buff if I don't have one.)
    #
    # The XP loop closed: Hunt banks it on a Score, this spends it. 702.3 caps
    # a unit at one Buff counter, which `OP_BUFF` already enforces -- so the
    # second activation is legal, costs the XP, and does nothing.
    "Crowd Favorite": (
        Ability(TR_ACTIVATED, cost_xp=2,
                ops=(Op(OP_BUFF, target=T_SELF),)),
    ),
    "Enthralling Protector": (
        Ability(TR_ACTIVATED, cost_xp=2,
                ops=(Op(OP_BUFF, target=T_SELF),)),
    ),

    # [Hidden] When you play me, you may choose a friendly unit. Move me to
    # its location and it to my original location.
    #
    # A swap, which `OP_SWAP_LOC` already does -- the interesting half is the
    # "you may". 383.3.a puts a "you may" that OPENS an effect at finalization,
    # so it is `optional` on the Ability and not an optional slot: declining
    # removes the trigger from the Chain entirely and it counts as never having
    # triggered (383.3.a.2), rather than resolving into nothing. The slot
    # itself is required, so 355.8 stops the ability firing at all when there
    # is no other friendly unit to trade places with.
    #
    # `not_self` matters here in a way it usually does not: without it "a
    # friendly unit" includes Tideturner, and swapping a unit with itself is a
    # legal-looking no-op that would still burn the trigger.
    "Tideturner": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_SWAP_LOC, target=T_SELF, target_b=0),)),
    ),

    # When you play me, give a unit [Ganking] this turn.
    "Gem Jammer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Ganking", n=1),)),
    ),

    # [Deathknell] - Draw 1.
    "Watchful Sentry": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you play a token unit, give me +1 Might this turn.
    # Your token units have [Tank].
    #
    # Both halves, and they are different mechanisms: the first is a TRIGGER
    # that banks +1 for the turn each time a token arrives, the second is a
    # continuous STATIC. The trigger watches another permanent being played, so
    # it is a watcher like Ravenbloom Student's "when you play a spell" rather
    # than an ETB -- and "give ME" means the source, not the token, so it needs
    # no subject.
    "Lillia - Protector of Dreams": (
        Ability(TR_PLAY_UNIT, subject_token=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # --- [Legion]: "get the effect if you've played another card this turn" --
    # These read the F_LEGION SNAPSHOT taken when the unit was played, not the
    # live counter. Two things would go wrong live: the unit has itself been
    # counted by the time its own ETB resolves, and the trigger sits on the
    # Chain through a priority window in which the count can move again. The
    # ability still goes on the Chain and still needs a legal target (355.8);
    # it is a conditional effect, not an optional one, so an un-Legioned copy
    # resolves and does nothing.

    # [Legion] - When you play me, give a unit +2 Might this turn.
    "Dangerous Duo": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2, cond=COND_LEGION),)),
    ),

    # [Legion] - When you play me, play two 1 Might Recruit unit tokens here.
    "Vanguard Captain": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=2,
                        token=RECRUIT_TOKEN, cond=COND_LEGION),)),
    ),

    # [Legion] - When you play me, buff me.
    # (If I don't have a buff, I get a +1 Might buff.)
    "Trifarian Gloryseeker": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_BUFF, target=T_SELF, cond=COND_LEGION),)),
    ),

    # When you play this, play a 1 Might Recruit unit token at your base.
    # Kill this: Recycle up to 4 cards from trashes.
    #
    # **"From trashes" reaches BOTH piles, and 416.1.c sends each card to its
    # own owner's deck.** That is what makes the enemy-facing half a real mode
    # rather than a rounding error: their [Flow] cards are banished on use and
    # never come back, but everything else in their trash is live ammunition for
    # a Soulgorger or a Fizz, and putting it on the bottom of their deck is the
    # only answer in the pool that does not require killing the recursion
    # engine first. Pointing it at your OWN trash is the opposite play -- it
    # refills a deck that is running out of cards.
    #
    # `T_MY_BASE`, not `T_HERE`: Gear is base-only under 149.2, but a Gear
    # played from a Facedown Zone stands at a battlefield, and the token still
    # goes to the base.
    "Forge of the Future": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=RECRUIT_TOKEN),)),
        Ability(TR_ACTIVATED, cost_kill_self=True,
                targets=tuple(TargetSpec(kind=TK_TRASH_CARD, who=W_ANY,
                                         optional=True) for _ in range(4)),
                ops=tuple(Op(OP_RECYCLE_FROM_TRASH, target=i)
                          for i in range(4))),
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

    # 187.5, the Gold gear token: "Kill this, Exhaust: [Reaction] - [Add] [A]."
    # [A] is Power of ANY Domain (135.2.e.5), so it goes to the D_ANY column of
    # the Rune Pool rather than to one domain's -- the Seal cycle above adds a
    # FIXED domain and this is the wildcard.
    #
    # Two costs, both paid at finalization: the token is killed AND exhausted,
    # which together make it a one-shot ritual rather than a rune. It is a
    # token, so it ceases to exist rather than reaching a trash (185.3).
    # `immediate` keeps it off the Chain (337.2) -- the card says so itself:
    # "Abilities that add resources can't be reacted to."
    "Gold // Buff": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                cost_kill_self=True, immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=D_ANY),)),
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

    # When I become ready, give me +2 Might this turn.
    #
    # TR_READIED is the exhausted -> ready TRANSITION, and the Awaken Phase is
    # the reliable source of one: a unit that spent the turn exhausted wakes up
    # bigger every turn ([[riftbound-awaken-counts-as-readying]]). A unit that
    # was already ready has not become ready and this does not fire, which is
    # what keeps it from being a free +2 every turn regardless.
    #
    # `subject_is_self` because `fire_watchers` walks the whole board: without
    # it the card would read "when a friendly unit becomes ready".
    "Fretful Feline": (
        Ability(TR_READIED, subject_is_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When I attack or defend, give one of your OTHER units HERE +3 Might and
    # [Tank] this turn.
    #
    # The pair is the point: [Tank] makes the target take combat damage first
    # (807) and +3 Might is what lets it survive doing so, so the two ops are
    # one effect and both point at the same slot. Yuumi herself is excluded by
    # `not_self`, and `same_loc_as_source` is "here" -- the contested
    # battlefield, since she has to be standing there to be attacking from it.
    "Yuumi - Magical Cat": (
        Ability(TR_ATTACK_OR_DEFEND,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),
                     Op(OP_GRANT_KEYWORD, target=0, keyword="Tank", n=1))),
    ),

    # [Accelerate] When I move to a battlefield, play three 1 Might Recruit
    # unit tokens here.
    #
    # "Here" on a move trigger is where she ARRIVED, which is `T_CTX2` and not
    # `T_HERE`: the trigger sits on the Chain through a response window, and if
    # she is answered before it resolves the tokens still land on the ground
    # she was moving to. COND_CTX2_BATTLEFIELD is the "to a battlefield" half --
    # a retreat to base fires nothing.
    "Corina Veraza": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, n=3, token=RECRUIT_TOKEN,
                        target=T_CTX2, cond=COND_CTX2_BATTLEFIELD),)),
    ),

    # At the end of your turn, if I'm at a battlefield, ready up to 4 friendly
    # runes.
    #
    # End of YOUR turn, so the runes come back before the opponent's -- the
    # same reason Targon's Peak defers its readying rather than performing it
    # ([[riftbound-tapping-out-costs-the-opponents-turn]]). The condition is
    # what she costs: holding ground is the price of the refund.
    "Sona, Harmonious": (
        Ability(TR_END_OF_TURN,
                ops=(Op(OP_READY_RUNES, n=4, cond=COND_SELF_AT_BF),)),
    ),

    # [Hidden] [Backline] Once each turn, when an ENEMY unit dies while I'm at
    # a battlefield, play a Gold gear token exhausted.
    #
    # The first watcher in the pool that wants the other side's deaths. A death
    # fires TR_OTHER_DIES for both seats and each watcher states which side it
    # meant, so "when another friendly unit dies" and this one are the same
    # trigger read from opposite ends.
    #
    # Both of its own clauses are about PYKE, not about the unit that died:
    # `subject_at_battlefield` is "while I'm at a battlefield", and
    # `once_each_turn` is spent only when everything else has already matched.
    "Pyke - Returned": (
        Ability(TR_OTHER_DIES, subject_enemy=True, subject_at_battlefield=True,
                once_each_turn=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When you play me OR ANOTHER DRAGON, ready up to 2 runes.
    #
    # Two abilities for one sentence, because "me" and "another Dragon" are two
    # different events: the first is TR_PLAY_ME, the second is a watcher on the
    # plays that follow. `subject_not_self` on the watcher is what keeps her own
    # arrival from paying twice.
    "Gentle Gemdragon": (
        Ability(TR_PLAY_ME, ops=(Op(OP_READY_RUNES, n=2),)),
        Ability(TR_PLAY_UNIT, subject_tag="Dragon", subject_not_self=True,
                ops=(Op(OP_READY_RUNES, n=2),)),
    ),

    # [Deathknell] If I was [Mighty], draw 2.
    #
    # Past tense, and that is the whole implementation question: 740.2 makes
    # Mighty 5+ EFFECTIVE Might, so a combat trick can supply it -- and the
    # trick expires with the turn while the Deathknell waits on the Chain. The
    # answer is snapshotted as he dies, the same way "died alone" is.
    "Unsung Hero": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=2, cond=COND_WAS_MIGHTY),)),
    ),

    # If you control fewer runes than an opponent at the start of your
    # Beginning Phase, give me +1 Might this turn.
    #
    # A catch-up clause: it compares two rune boards rather than testing a
    # threshold, so it switches off the moment you draw level. Phase-timed, so
    # it asks the question once a turn and the answer holds for that turn even
    # if the counts move afterwards.
    "Forsaken Baccai": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1,
                        cond=COND_FEWER_RUNES_THAN_OPP),)),
    ),

    # If you control fewer runes than an opponent at the start of your
    # Beginning Phase, give me +2 Might and [Ganking] this turn.
    #
    # The same clause paying out twice as much, plus the keyword that makes it
    # matter: [Ganking] lets him move battlefield-to-battlefield, so the turn
    # you are behind on runes is the turn he can reach the ground you need.
    "Oasis Raider": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_FEWER_RUNES_THAN_OPP),
                     Op(OP_GRANT_KEYWORD, target=T_SELF, keyword="Ganking",
                        n=1, cond=COND_FEWER_RUNES_THAN_OPP))),
    ),

    # --- printed optional additional costs (see PLAY_COSTS) ---------------
    # Each of these is one sentence: "you may pay X as an additional cost to
    # play me", then "when you play me, IF YOU PAID the additional cost, ...".
    # The cost is in `PLAY_COSTS` and is paid through `A_PLAY_AT_FAST`, the
    # same action [Accelerate] uses; the ability here reads the snapshot the
    # payment left. Nothing is conditional about the TRIGGER -- it fires
    # either way and the ops fizzle, which is 355.9.b's distinction between a
    # restriction and a condition, and it matters because a target is still
    # chosen for a Masa played without the rune.
    #
    # ...deal 2 to a unit at a battlefield.
    "Blast Corps Cadet": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    optional=True),),
                ops=(Op(OP_DAMAGE, target=0, n=2,
                        cond=COND_PAID_ADDITIONAL),)),
    ),

    # ...draw 1.
    "Clockwork Keeper": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_PAID_ADDITIONAL),)),
    ),

    # ...give a unit -2 Might this turn. No printed floor, so 143.2.b's general
    # floor of 0 applies rather than Stupefy's stricter minimum of 1.
    "Frostcoat Cub": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, optional=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2,
                        cond=COND_PAID_ADDITIONAL),)),
    ),

    # ...[Stun] an enemy unit at a battlefield.
    "Masa, Crashing Thunder": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True,
                                    optional=True),),
                ops=(Op(OP_STUN, target=0, cond=COND_PAID_ADDITIONAL),)),
    ),

    # [Hidden] [Ganking] ...ready me and give me +2 Might this turn.
    # Both halves are conditional, so each op carries the condition: a Pyke
    # played without the rune is an ordinary 3-Might body that entered
    # exhausted, which is the whole choice the card offers.
    "Pyke - Dockside Butcher": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_READY, target=T_SELF, cond=COND_PAID_ADDITIONAL),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_PAID_ADDITIONAL))),
    ),

    # ...buff me. 702.3 caps a unit at one Buff counter, which OP_BUFF already
    # enforces, so paying twice over two copies is not a stacking play.
    "Sea Monkey": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_BUFF, target=T_SELF,
                        cond=COND_PAID_ADDITIONAL),)),
    ),

    # Ferrous Forerunner, Carrion Dredger and Honest Broker used to be listed
    # here as deliberately absent: their Deathknells play Mech, Bird and Gold
    # tokens and `data/cards.json` shipped only Recruit and Sprite. That gap is
    # closed -- `data/tokens.json` supplies rule 187's eleven tokens -- and all
    # three are scripted above.
}


def spec_for(table, card: int) -> CardSpec | None:
    """The spec for a card id, or None if it is not implemented yet."""
    return SPECS.get(table.names[card])


# [Hunt N] -- 823: "When I conquer or hold, gain N XP." Unlike [Deathknell],
# whose effect is whatever the card says, Hunt's effect is fixed by the keyword
# and identical on every card carrying it. So it is SYNTHESISED from the
# keyword rather than transcribed twelve times: `keyword_value` already reads
# the N, and TR_CONQUER/TR_HOLD already exist because Scoring needed them.
#
# Two abilities, not one with a shared trigger: 469/470 make Conquer and Hold
# separate ways to Score, and a card can only take one of them in a turn.
def _hunt_abilities(table, card: int) -> tuple[Ability, ...]:
    n = int(table.hunt[card])
    if n <= 0:
        return ()
    return (Ability(TR_CONQUER, ops=(Op(OP_GAIN_XP, n=n),)),
            Ability(TR_HOLD, ops=(Op(OP_GAIN_XP, n=n),)))


def _vision_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Vision] (817) -- "functionally short for 'When this is played, predict'".

    817.1.b spells the whole keyword out, and Predict is already the look
    mechanic at N=1 (436.1: look at the top card, choose whether to Recycle
    it). So Vision is synthesised rather than transcribed, exactly like [Hunt]:
    its effect is fixed by the keyword instead of written on the card, and
    repeating it on each of the nine cards that print it would be nine chances
    to write it differently.

    817.1.c makes the trigger the permanent ENTERING THE BOARD, which is what
    TR_PLAY_ME already means. 817.2's "multiple instances trigger separately"
    is not reachable: no card in the pool prints Vision twice.
    """
    if not table.has(card, "Vision"):
        return ()
    return (Ability(TR_PLAY_ME,
                    ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                            pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),)


def abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every triggered ability printed on a card id.

    Transcribed entries plus the ones synthesised from keywords, so a card with
    [Hunt] and a written ability gets both without the entry repeating what the
    keyword already says.
    """
    return (ABILITIES.get(table.names[card], ())
            + _hunt_abilities(table, card)
            + _vision_abilities(table, card))


def legend_abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every ability printed on a Champion Legend.

    A third table for the third kind of non-permanent source. A legend is a
    Game Object (174) and not a Permanent (175): it has no row, no location and
    no Might, cannot be killed (174.3) and never leaves its zone (107.4.d). So
    it needs the same separation `BF_ABILITIES` needed, and for the same
    reason -- every permanent-side loop reads `perms[w, P_CARD]`.

    Unlike a permanent, a legend may print SEVERAL activated abilities and the
    player picks between them (Kha'Zix charges 1 XP for one and 2 for another),
    so the action carries the ability INDEX rather than taking the first.
    """
    return LEGEND_ABILITIES.get(table.names[card], ())


def legend_statics_for(table, card: int) -> tuple[Static, ...]:
    return LEGEND_STATICS.get(table.names[card], ())


def bf_abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every triggered ability printed on a BATTLEFIELD card id.

    A separate table and a separate lookup, for the reason `BF_STATICS` is
    separate: a battlefield is not a permanent. Every loop in the engine that
    walks "this permanent's abilities" would otherwise start finding these, and
    the failure would be silent -- a battlefield has no row for `T_SELF` to
    point at, so an op that referenced its source would read permanent 0.
    """
    return BF_ABILITIES.get(table.names[card], ())


def implemented(table) -> list[int]:
    """Card ids with a spec. The v1 spell pool grows by extending SPECS."""
    return [c for c in range(table.n) if table.names[c] in SPECS]


# --- import-time capacity check -------------------------------------------
# `state.MAX_TARGETS` sizes a numpy column, so it cannot be derived from this
# file without inverting the one-way import. What it CAN do is fail here, at
# import, the moment a card is encoded that does not fit -- rather than in an
# assert a thousand fuzz games deep, or worse, in a silent truncation. Forge of
# the Future's four "up to" slots sit exactly at the limit, so the next card
# with five will trip this on the line that adds it.
_WIDEST = max(
    [(s.n_targets, name) for name, s in SPECS.items()]
    + [(a.n_targets, name) for name, abs_ in ABILITIES.items() for a in abs_])
assert _WIDEST[0] <= MAX_TARGETS, (
    f"{_WIDEST[1]} needs {_WIDEST[0]} target slots but state.MAX_TARGETS is "
    f"{MAX_TARGETS}; raise it there (it sizes GameState.chain_targets)")

# `combat.open_showdown` queues ONE Chain Item per (watcher, subject) and
# resolution then runs every TR_ATTACK_OR_DEFEND ability on that source, so the
# trigger-time conditions are decided once for the card as a whole. That is
# exact while a card's attack/defend abilities all agree on them, which every
# card in the pool does. One that disagrees needs the condition carried on the
# Chain Item instead -- a real change, not a tweak, so it fails here rather
# than resolving an ability whose condition was never met.
# The board-wide ops are scoped by `at`/`who`/`except_target` and go through
# `resolve._sweep`, which never reads `target`. Setting it does nothing at all
# -- Anivia was written `target=T_HERE` and swept every battlefield on the
# board, which looks exactly like a correct card until you count the corpses.
_SWEEP_OPS = {OP_DAMAGE_ALL, OP_MODIFY_MIGHT_ALL, OP_KILL_ALL, OP_EXHAUST_ALL}
for _name, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_]:
    for _op in _entry.ops:
        assert not (_op.op in _SWEEP_OPS and _op.target != -1), (
            f"{_name}: {OP_NAMES[_op.op]} is scoped with `at=`, not `target=`; "
            f"`target={_op.target}` here is silently ignored")

# OP_LOOK_TOP suspends resolution: the cards come off the deck and the player
# is asked to pick through `pend_look`, which happens AFTER `resolve` has
# returned. Any op written after it would therefore run before the pick, in the
# wrong order and with the cards still in limbo. Being last is a real
# constraint, not a style rule, so it fails here rather than silently.
for _name, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_]:
    for _i, _op in enumerate(_entry.ops):
        if _op.op != OP_LOOK_TOP:
            continue
        assert _i == len(_entry.ops) - 1, (
            f"{_name}: look_top must be the last op -- resolution suspends "
            f"there, so op {_i + 1} would run before the player picks")
        assert 0 < _op.n <= MAX_LOOK, (
            f"{_name}: looks at {_op.n} cards, but state.MAX_LOOK is "
            f"{MAX_LOOK} (it sizes GameState.look_cards)")
        # A type-restricted pick can find nothing matching among the N, and the
        # player must still have a move -- the action layer adds A_PICK_NONE
        # when the filtered list is empty, so every such card must be one whose
        # text actually says "you MAY". Every printed one does.
        assert not (_op.pick_types and not _op.pick_optional), (
            f"{_name}: a type-restricted pick must be optional -- there may "
            f"be no card of that type among the {_op.n}")

# Zilean's replacement is OFFERED after the resolving card finishes, which is
# only equivalent to offering it at the moment of creation while a token op is
# its card's LAST -- otherwise the extra copy would arrive after effects that
# the printed card puts before it. Every entry satisfies this today; the one
# that does not should fail here rather than reorder a card silently.
for _name, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_]:
    for _i, _op in enumerate(_entry.ops):
        assert not (_op.op == OP_CREATE_TOKEN and _i != len(_entry.ops) - 1), (
            f"{_name}: create_token must be the last op while the token-doubler "
            f"replacement is deferred (see TOKEN_DOUBLERS)")
# This caught Guards! -- "Play a 2 Might Sand Soldier unit token. You may pay
# {Order rune} to ready it." Both Zilean's doubling and that optional cost
# defer off the same token creation, so they would queue together and
# "ready IT" stops being answerable: one token or both? Two interacting
# deferred decisions is real work, and the card is 2 deck slots, so it is
# left uncovered rather than approximated.

# Costs are read at finalization and ONLY for TR_ACTIVATED (204.1.b -- a base
# cost is what stands before the ':'). A triggered ability that carries one is
# 383.3.b's "cost within instructions" -- Overzealous Fan's "you may kill me to
# move an attacking unit", Ekko's "Recycle me to ready your runes" -- which
# nothing implements yet. Setting a cost field on one is silently ignored: the
# ability would resolve and the cost would never be paid, which reads as a
# strictly better card.
for _name, _abs in ABILITIES.items():
    for _a in _abs:
        if _a.trigger == TR_ACTIVATED:
            continue
        assert not (_a.cost_energy or _a.cost_power or _a.cost_exhaust
                    or _a.cost_kill_self or _a.cost_xp), (
            f"{_name}: a triggered ability carries a cost, which only "
            f"TR_ACTIVATED pays (383.3.b is not implemented)")

for _name, _abs in ABILITIES.items():
    _ad = [a for a in _abs if a.trigger == TR_ATTACK_OR_DEFEND]
    assert len({(a.subject_alone, a.subject_role, a.subject_any_friendly)
                for a in _ad}) <= 1, (
        f"{_name} has attack/defend abilities with different trigger-time "
        f"conditions; open_showdown cannot queue them separately")


# --- follow-up op lists (see `Op.then_key`) --------------------------------
# Filled in after the module body so they can use the same Op vocabulary the
# cards do. Index order must match the FU_* constants above.
FOLLOWUPS[FU_DIANA_REVEAL] = (
    Op(OP_LOOK_TOP, n=1, pick_optional=True, pick_types=("Spell",),
       pick_dest=DEST_HAND, rest_dest=DEST_TOP),
)

# "...then draw 1." The plainest follow-up there is, and it exists because
# ORDER is the whole point: a draw written as a second op runs before the
# player has chosen what to pitch, which lets the card they just drew be the
# card they discard.
FOLLOWUPS[FU_DRAW_1] = (Op(OP_DRAW, n=1),)


# --- behaviour features, for the observation encoder ------------------------
# `obs.py` encodes a card as its **attributes, never its id** (PLAN.md §5.2), so
# that a card the net never saw still gets a usable embedding. Stats, type,
# domains and keywords carried that alone -- and they describe the card's BODY,
# not what it DOES. Everything a card's rules text does was therefore invisible:
# 937 cards produced 642 distinct rows, and all 66 battlefields -- whose entire
# content IS rules text, with no energy, power or might to tell them apart --
# collapsed to 3.
#
# This block derives features from the SCRIPTED ABILITY ITSELF: which triggers
# it watches, which ops it runs, what its statics grant. That keeps the rule
# intact -- these are still attributes, just attributes of behaviour rather than
# of the stat line -- and it is self-maintaining, because a card scripted
# tomorrow becomes visible the moment its entry lands, with no table to update.
#
# **The visibility a card gets is exactly the behaviour that is encoded.** An
# unscripted card scores all zeros here and is still aliased against every other
# unscripted card, which is correct: the engine does not run its text either, so
# there is genuinely nothing to see. `has_scripted` is the one bit that says
# which of the two a zero row is -- a vanilla body, or text nothing executes.

_N_TRIGGERS = len(TRIGGER_NAMES)
_N_OPS = len(OP_NAMES)
_N_ST = len(ST_NAMES)
_N_SCOPE = 3

# 3 counts + triggers + ops + static kinds + static scopes
# + 2 static magnitudes + 2 static shape bits
# + 5 activation costs + optional + targets + enemy-target + is_bf
ABIL_DIM = 3 + _N_TRIGGERS + _N_OPS + _N_ST + _N_SCOPE + 2 + 2 + 5 + 1 + 1 + 1 + 1


def _clip(x: float, lo: float = -2.0, hi: float = 2.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ability_features(name: str) -> list[float]:
    """[ABIL_DIM] behaviour attributes for one card, by name.

    Every card in the pool goes through here, scripted or not -- an unscripted
    one simply comes back all zeros. Magnitudes are scaled to roughly unit range
    and clipped, since a single outlier column would otherwise dominate the
    embedding's input scale.
    """
    bf_abils = BF_ABILITIES.get(name, ())
    abils = ABILITIES.get(name, ()) + bf_abils
    bf_statics = BF_STATICS.get(name, ())
    all_statics = STATICS.get(name, ()) + bf_statics
    on_bf = bool(bf_abils or bf_statics)

    v = [0.0] * ABIL_DIM
    if not abils and not all_statics:
        return v

    o = 0
    v[o] = 1.0                                    # has_scripted
    v[o + 1] = _clip(len(abils) / 3.0)
    v[o + 2] = _clip(len(all_statics) / 3.0)
    o += 3

    for a in abils:
        v[o + a.trigger] = 1.0
    o += _N_TRIGGERS

    for a in abils:
        for op in a.ops:
            v[o + op.op] = 1.0
    o += _N_OPS

    for s in all_statics:
        v[o + s.kind] = 1.0
    o += _N_ST

    for s in all_statics:
        v[o + s.scope] = 1.0
    o += _N_SCOPE

    # Signed on purpose: a static that SUBTRACTS Might (Vex's aura) is the
    # opposite card from one that adds it, and a magnitude-only column would
    # make the two identical.
    might_n = [s.n for s in all_statics if s.kind == ST_MIGHT]
    disc_n = [s.n for s in all_statics if s.kind == ST_COST_ENERGY]
    v[o] = _clip(max(might_n, key=abs) / 3.0) if might_n else 0.0
    v[o + 1] = _clip(max(disc_n, key=abs) / 3.0) if disc_n else 0.0
    o += 2

    # A scaled static is a different kind of number from a flat one -- it grows
    # with the board or a trash and cannot be read off the card -- and a gated
    # one may contribute nothing at all right now.
    v[o] = float(any(s.per != CNT_NONE or s.per_keyword is not None
                     for s in all_statics))
    v[o + 1] = float(any(s.cond != COND_NONE for s in all_statics))
    o += 2

    act = [a for a in abils if a.trigger == TR_ACTIVATED]
    if act:
        v[o] = _clip(max(a.cost_energy for a in act) / 3.0)
        v[o + 1] = _clip(max(a.cost_power for a in act) / 3.0)
        v[o + 2] = float(any(a.cost_exhaust for a in act))
        v[o + 3] = float(any(a.cost_kill_self for a in act))
        v[o + 4] = _clip(max(a.cost_xp for a in act) / 5.0)
    o += 5

    v[o] = float(any(a.optional for a in abils))
    o += 1
    v[o] = _clip(max((len(a.targets) for a in abils), default=0) / 3.0)
    o += 1
    v[o] = float(any(t.who == W_ENEMY for a in abils for t in a.targets))
    o += 1
    # A battlefield's abilities come from tables of their own: its statics
    # reach BOTH players' units standing there, and its triggers fire once for
    # a player rather than once per permanent. Neither is true of anything
    # printed on a card that goes to the board.
    v[o] = float(on_bf)
    o += 1

    assert o == ABIL_DIM, f"{o} != {ABIL_DIM}"
    return v
