"""Game state, laid out for speed and for a later Rust port.

Three rules govern this file, all from PLAN.md §1.8:

  1. No Python objects in the hot loop. Cards are `u16` ids into the frozen
     `CardTable`; locations, phases and seats are small ints. Nothing here holds
     a string.
  2. Fixed-capacity arrays, never lists that grow. Overflow is a bug, asserted.
  3. `clone()` is a handful of `ndarray.copy()` calls, so search (ISMCTS later)
     and speculative rollouts stay cheap.

The deliberate departure from `sim/engine/state.py`: **runes are counts, not
objects**. Two Calm runes are interchangeable, so tracking individual `Rune`
instances with generated ids buys nothing and costs an allocation per rune plus a
non-resettable global counter. `runes_ready[seat, domain]` says everything the
rules need.
"""

from __future__ import annotations

import hashlib

import numpy as np

from rl.config import DOMAINS

# ---------------------------------------------------------------------------
# Enumerations. These are wire format -- append only, never reorder.
# ---------------------------------------------------------------------------
AWAKEN, BEGINNING, CHANNEL, DRAW, MAIN, ENDING = range(6)
PHASE_NAMES = ("Awaken", "Beginning", "Channel", "Draw", "Main", "Ending")

N_DOMAINS = len(DOMAINS)
# 135.2.e.5 -- [A], "Power of any Domain", the swirling rainbow symbol. Added
# to a Rune Pool it "can be spent to pay a Power cost of any Domain"
# (135.2.e.5.b), so it is not Power of some particular domain and cannot be
# stored as one; the Gold gear token (187.5) is what produces it.
#
# It rides as one extra COLUMN on `pool_power` rather than a separate array so
# that `clear_pools`, `GameState.__slots__`, the mirror field list and the
# state digest all keep working untouched. Payment sums the card's own domains
# and then this, and spends it LAST -- a wildcard left in the pool is worth
# more than a domain-locked one for whatever is cast next.
D_ANY = N_DOMAINS
N_POOL_DOMAINS = N_DOMAINS + 1
N_SEATS = 2
# Battlefield SLOTS. Two are chosen for the game (485.4) and always present;
# the third is a battlefield TOKEN's slot -- the Baron Pit (187.9) that Baron
# Nashor adds -- and is absent (`bf_card == -1`) until something creates it.
# Every loop that offers a battlefield as a place must ask `bf_present`.
N_BF = 3
# Facedown slots. 107.3.f gives a battlefield one, and Bandle Tree gives its
# own a second; two per ground covers both, with the extra slot simply never
# filled anywhere else.
N_FD_PER_BF = 2
N_FD = N_BF * N_FD_PER_BF
N_BF_BASE = 2

# Locations are ints. Seat s' base is `s`; battlefield i is `N_SEATS + i`.
LOC_NONE = -1
N_LOCATIONS = N_SEATS + N_BF


def base_loc(seat: int) -> int:
    return seat


def bf_loc(index: int) -> int:
    return N_SEATS + index


def is_battlefield(loc: int) -> bool:
    return loc >= N_SEATS


def bf_index(loc: int) -> int:
    return loc - N_SEATS


# --- a battlefield as an ability SOURCE -------------------------------------
# Everywhere in the engine, "the source of this ability" is a permanent row
# index. A battlefield is not a permanent -- it has no row, no controller of
# its own and cannot die -- but it does print triggered abilities ("when you
# conquer here, draw 1 for each other battlefield you control"), and those need
# to reach the Chain through the same machinery everything else uses.
#
# So a battlefield source is encoded as a row index no permanent can ever hold:
# a sentinel far below any valid row and below the -1 that means "no source".
# `fire` and `trig_controller` branch on it; nothing else has to know, because
# an index is an index. The alternative -- a parallel field marking what kind
# of source this is -- would need threading through every call site that passes
# one, and every site that forgot would silently read permanent row 0.
BF_SRC0 = -101


def bf_src(index: int) -> int:
    """The ability-source encoding for battlefield slot `index`."""
    return BF_SRC0 - index


def is_bf_src(src: int) -> bool:
    return src <= BF_SRC0


def bf_src_index(src: int) -> int:
    return BF_SRC0 - src


# --- a legend as an ability SOURCE ------------------------------------------
# Same problem as a battlefield, same shape of answer, and deliberately a
# DIFFERENT sentinel band so the two can never be confused: a legend is not a
# permanent either (175), so `LEGEND_SRC0` sits above the battlefield band and
# below any real row. Two seats, so two values.
LEGEND_SRC0 = -51


def fd_bf(slot: int) -> int:
    """The battlefield a facedown SLOT belongs to."""
    return slot // N_FD_PER_BF


def fd_slots(i: int) -> range:
    """The facedown slots at battlefield `i`, in the order they fill."""
    return range(i * N_FD_PER_BF, (i + 1) * N_FD_PER_BF)


def legend_src(seat: int) -> int:
    """The ability-source encoding for `seat`'s Champion Legend."""
    return LEGEND_SRC0 - seat


def is_legend_src(src: int) -> bool:
    return LEGEND_SRC0 - N_SEATS < src <= LEGEND_SRC0


def legend_src_seat(src: int) -> int:
    return LEGEND_SRC0 - src


# --- a DELAYED ability as a source (389-390) --------------------------------
# The third sourceless kind, and the first that is not a Game Object at all.
# "When a friendly unit is played THIS TURN, buff it" (Rally the Troops) is a
# Delayed Trigger by 390.2 -- a real Triggered Ability, not a continuous
# effect -- so when it fires it becomes its own Chain Item and is finalized
# like any other (355.5.b, and 2350's "the resulting delayed trigger").
#
# It therefore needs a source, and the spell that armed it is in the trash by
# the time it fires. So the sentinel encodes a SLOT in `state.delayed`, which
# holds the arming card's id -- exactly the shape `bf_card` and `legend` give
# the other two sentinel kinds, so `trig_card` decodes all three the same way
# and needs no table. Encoding only the seat would not be enough: one seat can
# have several delayed abilities armed at once, and the source has to say which.
#
# Its own band, below the legend one, for the reason the legend band sits below
# the battlefield one: three sentinel kinds that can never be confused.
MAX_DELAYED = 8
DELAYED_SRC0 = -71


def delayed_src(seat: int, slot: int) -> int:
    """The ability-source encoding for `seat`'s delayed ability in `slot`."""
    return DELAYED_SRC0 - (seat * MAX_DELAYED + slot)


def is_delayed_src(src: int) -> bool:
    return DELAYED_SRC0 - N_SEATS * MAX_DELAYED < src <= DELAYED_SRC0


def delayed_src_seat(src: int) -> int:
    return (DELAYED_SRC0 - src) // MAX_DELAYED


def delayed_src_slot(src: int) -> int:
    return (DELAYED_SRC0 - src) % MAX_DELAYED


# --- a card IN A TRASH as a source ----------------------------------------
# "When you discard me, ..." (Mask Mother, Flame Chompers, Scrapheap). The card
# has just reached its owner's trash and has no row, so the sentinel encodes
# the SEAT and the queue entry / Chain Item carry the CARD (as the subject on
# the queue, as C_CARD on the Chain). Its own band, between legend and delayed.
TRASH_SRC0 = -61


def trash_src(seat: int) -> int:
    return TRASH_SRC0 - seat


def is_trash_src(src: int) -> bool:
    return TRASH_SRC0 - N_SEATS < src <= TRASH_SRC0


def trash_src_seat(src: int) -> int:
    return TRASH_SRC0 - src


# Permanent columns. One int16 matrix so a clone is a single copy.
(P_CARD, P_CTRL, P_LOC, P_READY, P_DMG, P_ALIVE, P_ARRIVED, P_FLAGS,
 P_MIGHT_MOD, P_EMPOWER, P_ATTACHED_TO, P_ATTACH_TURN, P_OWNER) = range(13)
N_PERM_COLS = 13

# P_OWNER is who the card BELONGS to; `P_CTRL` is who is playing with it. They
# are the same on every card played out of its own owner's hand, which is why
# the engine used `P_CTRL` for both for a long time -- and 718.5.e/f say
# plainly that they are different things.
#
# The proxy broke the first time a card was played out of SOMEONE ELSE's zone:
# Kharox digs a unit out of the opponent's trash and plays it under his own
# control, and the per-seat conservation gate read that as a card changing
# hands. It is not: the card is still theirs, and when it dies it goes to
# THEIR trash (108.2 gives each player their own), and a recycle puts it on the
# bottom of THEIR deck (416.1.c).
#
# So every zone a permanent can leave for reads `P_OWNER`, and only what the
# card DOES on the board reads `P_CTRL`.

# P_ATTACH_TURN is the turn this card last BECAME Attached, or -1. Brutalizer:
# "If this was attached to me this turn, I have an additional +2 Might" -- a
# window that `P_ATTACHED_TO` alone cannot answer, because it says only that
# the link exists and not when it was made.
#
# A turn stamp rather than a flag, the same idiom `P_ARRIVED` and `once_used`
# use, so nothing has to remember to clear it at end of turn. It is the
# ATTACHED card's own column, not the unit's: a unit can be equipped twice in
# one turn and each sword answers for itself.

# P_ATTACHED_TO is the ROW of this card's Top-Most Card (719), or -1 when it is
# not Attached. Attachment needed no new zone and no new object: an Equipment is
# already a gear permanent with a row of its own, and 718.5 is explicit that an
# Attached card "still has all properties of being a card on the board". What it
# needs is a LINK, which is one column.
#
# Four rules ride on this column, and every one of them is a place where an
# Attached card behaves unlike the gear it otherwise is:
#
#   718.2   its printed Rules Text is INACTIVE -- its statics do not apply and
#           its abilities neither trigger nor can be activated (721.2). Spinning
#           Axe's [Temporary] stops killing it the moment it attaches, which is
#           most of why the card is playable at all.
#   718.4   its Might Bonus modulates the TOP-MOST card's Might (137.3).
#   719.3   it is at the same location, and 719.3.a moves it along.
#   719.5   when the Top-Most leaves the board it DETACHES and stays where it
#           is, rather than following the unit into a trash.
#
# 718.5.d caps it at one Top-Most card, which a single column enforces for
# free. 718.5.e/f let the two have different controllers, so `P_CTRL` is
# deliberately left alone by attaching.

# Read through `empower_count`, never directly: the FLAG is a floor on the
# COUNT, so the two can never disagree about whether a permanent is Empowered.
#
# P_EMPOWER is how many TIMES this permanent has been Empowered, not whether it
# has been. 827.1.c.1's "use only if not Empowered" caps it at one for almost
# every card in the pool, and `F_EMPOWERED` stays the boolean everything else
# reads -- but Kayle, Justified prints "I can be Empowered up to three times"
# and scales off the count, so the number has to exist somewhere.
#
# The flag is kept in sync rather than derived, because it is read in seven
# places that have no business knowing a count exists: F_EMPOWERED means
# "Empowered at least once", which is what 828.1.c asks.

# `P_MIGHT_MOD` is a signed 'this turn' modifier, cleared in the end-of-turn
# cleanup alongside TURN_SCOPED_FLAGS. It is NOT damage: rule 142.4.b makes
# lethal damage a *non-zero* amount >= Might, so reducing a unit to 0 Might
# never kills it on its own. It can still kill indirectly by dropping Might to
# meet damage already marked (143.2.a, 'if a Unit EVER has...'), which is why
# `combat.set_might_mod` re-checks lethality after every change.

# Bits in P_FLAGS. Statuses live in one column rather than one column each, so
# adding the next one costs nothing.
F_STUNNED = 1 << 0           # rule 423: the game status itself
F_NO_COMBAT_DAMAGE = 1 << 1  # 423.1.b, and any effect worded "deals no damage"
# Set on any permanent that is NOT a Unit -- Gear. Stored as a flag rather than
# looked up through the CardTable so `units_at` can filter without it: that
# method is called from `seats_at`, which decides Control and whether a Combat
# happens, and it must never count a gear as a garrison.
F_NON_UNIT = 1 << 2
# 702 -- a Buff counter. Worth +1 Might (703), at most ONE per unit (702.3),
# and removed when the unit leaves play (705). A flag rather than a count
# because one is the rule; "I can have any number of buffs" (Lee Sin) is a
# printed exception and stays unimplemented rather than being half-supported.
# NOT turn-scoped: a Buff is a counter, not a "this turn" effect.
F_BUFFED = 1 << 3
# Captured at the moment of death: were there no other friendly units at this
# unit's location? Lonely Poro's "If I died alone", and the pattern generalises
# to any Deathknell that asks about the board it left.
#
# **Recorded rather than recomputed, because it is not answerable later.**
# 808.1.d.2 puts a Deathknell on the Chain before the card reaches the Trash,
# and the Chain then takes priority passes -- so by the time the ability
# resolves, a friendly unit has had a whole response window to walk in or out
# and change an answer that "I DIED alone" already settled in the past tense.
# 359.3.f.3 is the general rule: information a trigger references is captured
# when it triggers.
F_DIED_ALONE = 1 << 4
# [Legion] was satisfied when this permanent was PLAYED -- "you've played
# another card this turn". A snapshot, like F_DIED_ALONE, and for the same
# reason: the condition is about a moment that has passed. A "[Legion] - When
# you play me" trigger sits on the Chain through a priority window, and by the
# time it resolves the turn's play count is not the one the card asked about.
# Snapshotting also sidesteps the off-by-one that reading the live counter
# invites, since by then the permanent has itself been counted.
F_LEGION = 1 << 5
# 441.1.a -- Empowered is a BINARY state: "A Game Object is Empowered or it
# isn't", and 441.1.b forbids empowering something already Empowered. A flag,
# not a count. Kayle's "I can be [Empowered] up to three times" is the printed
# exception 441.1.c.1 allows and is deliberately not supported by this bit.
#
# NOT turn-scoped: the status persists until the permanent leaves play.
F_EMPOWERED = 1 << 6

# Bits in `GameState.played_types`. "Non-token" is part of what Swain asks, and
# a token is never played FROM A HAND -- but it IS played (187), so the
# distinction has to be made here rather than assumed.
PT_UNIT, PT_GEAR, PT_SPELL = 1, 2, 4

# Vex - Apathetic: "They can't move it this turn." A movement restriction, not
# a status the rules name -- so it is turn-scoped like [Stun]'s, and cleared by
# the same end-of-turn sweep.
F_NO_MOVE = 1 << 7
# "[Deathknell] - If I was [Mighty], draw 2" (Unsung Hero). Past tense, and
# the same snapshot problem F_DIED_ALONE has: 808.1.d.2 queues the Deathknell
# before the card reaches the Trash and the Chain then takes priority passes,
# so by resolution the row's Might modifiers have been cleared and every buff
# that made it Mighty is gone. 740.2 defines Mighty as 5+ EFFECTIVE Might, so
# the answer has to be taken while the unit is still standing.
F_DIED_MIGHTY = 1 << 8
# "When you play me, IF YOU PAID THE ADDITIONAL COST, ...". Six cards print an
# optional additional cost in runes and then a trigger that asks whether it was
# paid; the payment happens as the card is played and the trigger resolves a
# priority window later, so like F_LEGION it is recorded on the row rather than
# re-derived. [Accelerate] needs no flag because what it buys -- entering ready
# -- is visible on the board.
F_PAID_ADDITIONAL = 1 << 9
# "When you play me FROM FACE DOWN, ..." (Evelynn - Entrancing, Tornado
# Warrior). Recorded on the row for the same reason F_LEGION and
# F_PAID_ADDITIONAL are: the play trigger resolves a priority window after the
# card left its Facedown Zone, and by then nothing else remembers where it
# came from.
#
# It ALSO does a second job, and that one outlives the trigger: 811.1.d.2
# binds a hidden permanent's *play effect* targets to the battlefield it was
# hidden at, and `chain.place` reads this flag to set `C_BOUND_BF`. Scoped to
# TR_PLAY_ME there, because the rule says "a play effect" -- a later
# [Deathknell] or move trigger on the same permanent is unrestricted.
F_FROM_HIDDEN = 1 << 10
# "When I die IN COMBAT" (Draven - Audacious). Snapshotted as the unit dies,
# for the reason F_DIED_MIGHTY is: the Deathknell asks a past-tense question
# at resolution, by which time the Combat may be over and `showdown_bf`
# cleared. Only a real Combat counts -- a Non-Combat Showdown (the Mournful
# Witness distinction) is not "combat".
F_DIED_IN_COMBAT = 1 << 11
# "If I haven't been dealt damage this turn" (Affectionate Poro). Set wherever
# damage is MARKED, so healing the damage away does not unset it -- the question
# is whether the event happened. Turn-scoped.
F_DAMAGED_TURN = 1 << 12
# "It can't be chosen by enemy spells and abilities this turn" (Twilight
# Shroud). The one-turn, one-unit form of Ruin Runner's static. Turn-scoped.
F_UNCHOOSABLE_TURN = 1 << 13
# "When a unit you control BECOMES [Mighty]" is a transition, so the last
# reading is kept on the row (it moves with the row through compaction).
# F_MIGHT_SEEN says a reading exists: a unit entering with 5+ Might sets the
# baseline instead of firing. F_WAS_MIGHTY is bit 15 -- negative in int16.
F_MIGHT_SEEN = 1 << 14
F_WAS_MIGHTY = -(1 << 15)

# Restricted resource pools -- what an [Add] said its Energy/Power may pay for.
RK_SPELL, RK_SHOWDOWN, RK_GEAR, RK_UNIT = range(4)
N_RESTRICT = 4

# `GameState.eot_kind` -- what happens to a row at the end of the turn.
EOT_NONE, EOT_DISEMPOWER, EOT_EMPOWER, EOT_REVERT_CONTROL = range(4)

# Keywords an effect can GRANT to a permanent. Values, not bits: [Assault 3]
# and [Assault 2] are different grants, and 807.1.b.2 calls the number the
# Assault Value. A valueless keyword grants 1.
#
# 807.1.c makes [Assault X] "functionally short for 'while I am an attacker, I
# have +X Might'", so a granted instance is an additional ability rather than a
# replacement and the values ADD. Nothing in the pool currently stacks one onto
# a printed instance, so this is a reading rather than an observed rule.
GRANTABLE = ("Assault", "Shield", "Deflect", "Ganking", "Tank", "Backline",
             "Temporary")
GRANT_IDX = {k: i for i, k in enumerate(GRANTABLE)}
N_GRANTABLE = len(GRANTABLE)

# Statuses that expire during the end-of-turn cleanup (423.1.a.2, 317.2).
# F_LEGION is deliberately NOT here: it records what was true when the
# permanent was played and stays true for as long as it is on the board.
TURN_SCOPED_FLAGS = (F_STUNNED | F_NO_COMBAT_DAMAGE | F_NO_MOVE
                     | F_DAMAGED_TURN | F_UNCHOOSABLE_TURN)  # NOT F_NON_UNIT

# Capacities. Generous enough that overflow means a real bug, small enough that
# cloning stays cheap.
MAX_PERMS = 48
MAX_DECK = 60
# **Derived, not chosen.** This was 20, and 20 is not a rules number: Riftbound
# has no maximum hand size, so there is nothing to derive it from except "every
# card that could be in a hand came out of a deck". It held right up until a
# real-deck fuzz at victory 8 reached a hand of 23 on seed 1756 -- ordinary
# play, a draw-heavy list and a random agent with no reason to spend cards --
# and asserted `hand overflow` 1,756 games in. The engine must never assert on
# a state the rules permit; only card objects bound it, and those all come from
# the Main Deck.
MAX_HAND = MAX_DECK
MAX_TRASH = 80
MAX_BANISHED = 60   # 108.6 -- one Banishment per player, unordered, public
# Triggers waiting to be put on the Chain. A trigger fires from wherever the
# game action happens -- deep inside combat damage, inside a Cleanup -- and at
# those moments the Chain must stay empty, because `is_open` is `n_chain == 0`
# and a Cleanup refuses to run in a Closed State. Pushing directly from
# `_destroy` would therefore block the very Cleanup that finishes the Combat.
# So a trigger is QUEUED where it fires and drained at the next safe point.
MAX_TRIGGERS = 32

# Chain capacity, DERIVED. This was 16 and overflowed the moment a trigger
# could fire per spell played: three Ravenbloom Students ("when you play a
# spell, give me +1 Might") plus a five-deep spell chain is 11 abilities and 5
# spells, which is legal and is exactly what a random game produced.
#
# The bound: every spell on the chain came from a hand, so spells are capped by
# both hands together, and abilities are capped by the trigger queue that feeds
# them. A hand-picked headroom number would have to be re-picked every time a
# new trigger type lands -- and would announce itself by crashing a training
# run rather than by failing a test.
MAX_CHAIN = 2 * MAX_HAND + MAX_TRIGGERS
RUNE_RING = 16   # >= rune_deck_size; recycled runes cycle back through it

# Chain columns (rules 337-340).
#
# `C_FINAL` is the Pending/Finalized split from 337.1: an item is appended
# Pending, and Finalizing it (choosing targets, paying costs) is a separate step
# that does NOT pass priority. `C_BOUND_BF` is the battlefield a [Hidden] card
# was played from, which binds its bound target slots (811.1.d.2.a); -1 means it
# was played from hand and nothing is bound.
# `C_ABIL`, `C_SRC` and `C_CTX` are what make a Chain Item able to be a
# TRIGGERED ABILITY rather than a card. 383.3: "a Triggered Ability behaves like
# an Activated Ability and is placed on the Chain" -- same Finalize, same
# targeting, same priority windows -- so it shares this row rather than getting
# a parallel mechanism.
#
#   C_ABIL  index into the source card's ability tuple, or -1 for "a card"
#   C_SRC   the permanent row the ability came from: what "me" and "here" mean
#   C_CTX   one captured int, usually a location. 359.3.f.3 -- information a
#           trigger references is captured WHEN IT TRIGGERS, not when it
#           resolves, so Lillia's "play a Sprite there" remembers where she
#           moved from even if she has moved again by the time it resolves.
#   C_CTX2  a SECOND captured location, because a Move has two of them and
#           card text distinguishes them by word. On a move trigger C_CTX is
#           the location LEFT and C_CTX2 the location ARRIVED AT:
#               "there"           -> C_CTX   (Lillia's Sprite, the origin)
#               "that battlefield"-> C_CTX2  (Irresistible Faefolk)
#               "here"/"this"     -> T_HERE, a live read of the source's own
#                                    row, which is the destination while the
#                                    source is still standing on it
#           The first two survive the source being removed mid-Chain; the
#           third does not, and 383.2.c.2 says that is correct -- "this
#           battlefield" has no referent once the permanent naming it is gone,
#           while "that battlefield" was pinned when the trigger fired.
#   C_COST  which cost this play pays -- see COST_* below
#   C_DEST  where the card goes when it leaves the Chain -- see DEST_* below
#
# **The two are separate columns because they vary independently.** They began
# as one flag, `C_FLOW`, which was fine while [Flow] was the only card that
# changed either -- it changes both, paying an alternate cost (829.1.c.1) and
# banishing afterwards (829.1.b). Then Fizz - Trickster arrived: "play a spell
# from your trash, ignoring its Energy cost. Recycle that spell after you play
# it" -- a third cost and a third destination, in a combination Flow never
# produces. One flag would have had to become an enum of whole card behaviours,
# which is the shape that stops composing at exactly four cards.
C_CARD, C_CTRL, C_FINAL, C_FROM_HAND, C_BOUND_BF, C_UID, C_ABIL, C_SRC, \
    C_CTX, C_COST, C_DEST, C_SUBJ, C_REPEAT, C_CTX2, C_COST_KILL, \
    C_OWNER, C_SPENT_E, C_PLAY_SPELL = range(18)
N_CHAIN_COLS = 18
# C_SPENT_E: the Energy paid to play this spell, noted at finalization -- the
# only moment it is known -- for "when you play a spell, if you spent {4 energy}
# or more" watchers, which do not fire until it RESOLVES (419.4.a).
# C_PLAY_SPELL: 1 on a spell whose "when you play" watchers are owed at
# resolution; a countered spell leaves the Chain without them (419.4.a.1).
# C_OWNER: the seat whose card this is, when that is not the controller --
# Blind Fury casts the OPPONENT's top card, which still goes to its owner's
# trash (-1 means the controller).

# C_COST_KILL: the CARD ID killed to pay a printed "as an additional cost to
# play this, kill a [...]" (820), or -1 for a card with none. The permanent's
# card id, not its row -- captured before the kill, never read off a dead
# row afterward (the same caution `dead_source` exists for elsewhere), and
# what Heedless Resurrection's own effect needs: "play a unit that costs no
# more than the KILLED unit" reads this card's printed Energy/Power.
# Chosen through the same A_TARGET slot-filling UI `chain_targets` uses, but
# stored separately -- it is never one of `spec.targets`, so an Op's `target`
# index never has to account for it. Paid at the choice itself (see
# `actions._choose_cost_kill_target`), the same moment `cost_kill_self` pays
# for an ability's own cost.

# C_REPEAT: 1 if this item's [Repeat] cost was paid as it was played (820).
# Orthogonal to C_COST, which says WHICH cost was paid (printed, Flow, free):
# Repeat is paid ON TOP of whichever that was, and buys one extra execution
# of the ops at resolution -- 820.1.c.3, once only, never a loop.

# C_SUBJ is the permanent a trigger fired *for*, which is not the same as
# C_SRC, the permanent the ability is printed on. Every trigger so far has been
# about its own source -- "when I die", "when I conquer" -- so the two
# coincided and one column did both jobs. Mask of Foresight watches from a
# base while somebody ELSE attacks: the source is the gear and the subject is
# the unit, and the effect is "give IT +1 Might".

# What a Chain Item pays on finalization.
COST_PRINTED = 0     # the corner cost, or nothing at all if played from Hidden
COST_FLOW = 1        # 829.1.c.1 -- the Flow cost REPLACES the base cost
COST_NO_ENERGY = 2   # "ignoring its Energy cost"; the Power cost still stands
COST_FREE = 3        # "ignoring its cost" -- both halves waived

# Where the card goes when it leaves the Chain. Three real destinations, and
# only one of them gives the card back -- see `GameState.recycle_card`.
DEST_TRASH = 0
DEST_BANISH = 1      # 829.1.b.1, [Flow]
DEST_RECYCLE = 2     # 416.1.a, bottom of the owner's own Main Deck
# Only a look-at-the-top effect uses this one: "Put 1 into your hand". A Chain
# Item never ends up in a hand, so it is not a `C_DEST` value in practice --
# it shares the enum because it answers the same question, "where does the
# card go", and one vocabulary beats two.
DEST_HAND = 3
# 436.1 -- [Predict] is "look at the top card and choose whether to Recycle
# it", so the card you DON'T recycle goes back where it came from. That is a
# fourth destination and not the same as any of the others: the deck's top, not
# its bottom. 436.1.a keeps the order of multiple returned cards up to the
# player; with the pool's only Predict being Predict 1, order never arises, so
# they go back in the order they came off.
DEST_TOP = 4

# How many cards a single "look at the top N" may hold. The widest in the pool
# is 5 (Promising Future, Wild Claw, Reinforce); sized from the cards rather
# than guessed, and asserted at import in `effects.py`.
MAX_LOOK = 5

# Which card types a look may PICK: "you may reveal a gear from among them"
# (Ornn), "a unit from among them" (Ivern, Rift Herald, Reinforce). A mask
# rather than a list because it has to live in a numpy scalar on the state, and
# 0 means "no restriction" -- which is what most looks print.
LK_UNIT, LK_SPELL, LK_GEAR = 1, 2, 4
LOOK_TYPE_BIT = {"Unit": LK_UNIT, "Spell": LK_SPELL, "Gear": LK_GEAR}

# `C_UID` is a stable per-item id. Chain *indices* shift whenever an item is
# removed, so a counterspell that stored an index could hit the wrong item
# after something below it resolved. Targets store the uid instead.

# Target slots stored per chain item. Two is enough for every card in the first
# batch; overflow is asserted rather than silently truncated.
MAX_TARGETS = 6

# Showdown steps (PLAN.md Phase 1.3).
# SD_CONQUER is the 466.6 suspension: Control has been established and its
# Conquer triggers are on the Chain, but 466.7 has NOT run yet, so the Combat is
# still in progress and the Attacker/Defender designations are still on. Safe to
# append -- `showdown_step` is in `obs.OBS_UNREAD` and `mirror`'s UNCHANGED set,
# so no observation or checkpoint depends on how many values it has.
SD_NONE, SD_PRIORITY, SD_DAMAGE, SD_CLEANUP, SD_CONQUER = range(5)


class BoardOverflow(AssertionError):
    """More permanent rows in one turn than `MAX_PERMS`.

    **A capacity limit, raised as its own type so a training run can survive
    it.** Rows are only reclaimed by `compact_permanents`, which is safe only at
    end of turn (most of the per-row arrays it does NOT remap are either reset
    there or ply-stamped stale by then), so the cap is really on rows CREATED in
    one turn rather than on permanents alive at once. Measured at victory 8:
    random play peaks at 33 rows against a mean of 13, so the cap has headroom
    for the rules -- what exceeds it is a policy assembling a token engine, or a
    productive loop the game has no shortcut rule for (see BACKLOG item 9).

    `env.step` catches this and ends the episode as a truncation, the same way
    `decision_cap` does: a livelock or a runaway should cost one episode, not a
    seven-hour run. It subclasses `AssertionError` so the fuzz -- which does NOT
    catch it -- still fails loudly, because there the overflow is a finding.

    The state is left mid-mutation when this is raised, so the only safe thing to
    do with that episode is discard it. Nothing reads the position afterwards
    except the point totals, which are already written.
    """


class GameState:
    """Mutable game state. Treat every array as private to the engine."""

    __slots__ = (
        "perms", "n_perms",
        "hand", "n_hand", "deck", "deck_ptr", "n_deck", "trash", "n_trash",
        "decklist", "n_decklist", "deck_known",
        "runes_ready", "runes_spent", "rune_deck", "rune_head", "rune_left",
        "pool_energy", "pool_power",
        "bf_card", "bf_ctrl", "bf_contested", "bf_contester",
        "fd_owner", "fd_card", "fd_ply",
        "bf_scored",
        "banished", "n_banished",
        "chain", "n_chain", "chain_targets", "pend_slot", "chain_uid",
        "pend_may", "pend_cost_kill", "pend_cost_recycle",
        "pend_cost_recycle_n", "trig", "n_trig", "pend_order",
        "chain_from_trigger",
        "points", "burned_out", "no_spells", "no_cards",
        "delayed", "cards_played", "cards_completed", "spells_played", "xp",
        "n_attached",
        "unit_died_ply", "discarded_ply", "no_effect_damage_ply",
        "chose_enemy_ply", "big_spell_ply", "look_min_energy", "look_domain",
        "look_reveal",
        "bf_conquered_ply",
        "buff_bonus_ply", "buff_bonus_n", "next_unit_ready_ply", "extra_turns",
        "hold_points_ply", "hold_points", "power_spent_ply", "power_spent",
        "excess_ply", "excess_amt", "excess_attacking",
        "next_spell_bonus_ply", "next_spell_repeat_ply", "bonus_uid",
        "resolving_bonus", "resolving_paid",
        "pend_repeat_card", "pend_repeat_seat", "pend_repeat_tgts",
        "rp_seat", "rp_card", "rp_owner", "rp_cost", "rp_discount",
        "rp_here", "rp_empower", "rp_armed", "rp_kill",
        "look_max_might", "look_last_pick", "reveal_hold_return", "last_token",
        "reveal_play_loc", "draw_ply", "draw_count", "second_draw_ply",
        "pend_cull_dest", "pend_split", "split_left", "split_loc",
        "split_xp", "split_spell", "split_alloc", "bf_prev_ctrl", "bf_replaced", "bf_first_use", "empower_src",
        "victory_bonus", "unit_tax_ply", "free_hide_ply", "pend_altar", "altar_ply",
        "pend_guard", "guard_cands", "n_guard_cands",
        "pend_repl", "repl_pick", "repl_ply",
        "pend_dmg", "pend_dmg_pool", "pend_dmg_bf", "pend_dmg_targets",
        "pend_dmg_n_tgt", "pend_dmg_kills", "pend_dmg_n_kill", "pend_dmg_done",
        "show_off_perm", "show_off_card", "show_off_ply", "pend_show_off",
        "pool_rstr_e", "pool_rstr_p", "recycled_n", "rune_recycled_n",
        "banished_n", "chose_enemy_n", "legend_pile", "legend_pile_n",
        "pend_amount", "amt_kind",
        "amt_loc", "amt_spell", "free_gear_ply", "armory_ply", "last_burned",
        "hp_kw", "hp_spells", "flow_grant_card", "flow_grant_e",
        "flow_grant_p", "flow_grant_ply", "flow_grant_banish",
        "rp_zone", "rp_power", "rp_from_sarc", "sarc_cards", "n_sarc",
        "kill_disc_e", "kill_disc_p", "steal_seat", "steal_uid", "steal_stage",
        "steal_slot", "steal_targets", "move_from", "move_to", "extra_buffs",
        "tag_grant", "named", "pend_name", "name_kind", "name_src",
        "name_opts", "n_name_opts", "copy_of", "copy_via", "last_token_n",
        "copy_pending", "granted_card", "granted_ply", "grenade_ply", "ctrl_link",
        "zero_cards", "zero_owner", "n_zero", "resume_kind", "resume_card",
        "resume_idx", "resume_op", "resume_seat", "resume_src", "resume_ctx",
        "resume_ctx2", "resume_subj", "resume_hand", "resume_bound",
        "resume_tgts", "pend_group_loc", "group_loc_opts", "n_group_loc",
        "group_loc", "pf_stage", "pf_first", "pf_cards", "dj_seat",
        "dj_first", "dj_cat", "dj_keep", "dj_rune_keep", "dj_hand_keep",
        "riches_on",
        "grenade_hits",
        "hold_return", "n_hold_return",
        "pend_repeat_bound", "pend_repeat_hand",
        "next_spell_discount",
        "units_enter_ready_turn", "xp_gained_ply",
        "next_discount",
        "victory_score",
        "kw_grant", "kw_grant_turn",
        "legend", "champion", "champion_reg", "legend_ready", "legend_emp",
        "legend_once",
        "equip_played_ply",
        "pending_ready_runes",
        "pending_add_any",
        "pend_phase",
        "turn", "ply", "active", "phase", "priority", "focus",
        "showdown_bf", "showdown_step", "showdown_combat",
        "attacker", "passes",
        "decl_dst", "decl_mask", "pend_play", "pend_play_seat",
        "pend_kill_play", "pend_kill_play_seat", "pend_kill_play_loc",
        "pend_tax", "pend_tax_uid", "pend_tax_cost",
        "pend_hand_play", "hp_types", "hp_tag", "hp_max_energy", "hp_cost",
        "hp_discount", "hp_dest", "hp_attach", "hp_optional", "hp_pick",
        "pend_ask", "pend_ask_caster", "pend_ask_yes", "pend_ask_no",
        "pend_ask_subj", "pend_ask_card",
        "pend_hide", "pend_mull", "mull_mask",
        "look_cards", "n_look", "pend_look", "pend_play_look",
        "look_pick_dest", "look_rest_dest", "look_optional", "look_multi",
        "look_type_mask", "death_guard",
        "once_used", "desig", "desig_seat", "death_shield_ply", "guillotine_ply",
        "mark_ply", "mark_slot", "mark_seat", "move_ply", "move_count",
        "mode_used_ply", "mode_used_mask", "eot_ply", "eot_kind",
        "base_might_ply", "base_might_val", "shield_ply", "shield_amt",
        "block_next_ply", "foe_dmg", "might_hi", "conquer_ply",
        "double_dmg_ply", "banish_death_ply",
        "combat_might_ply", "combat_might_val",
        "pend_double", "pend_reveal", "pend_reveal_xp",
        "played_types",
        "saw_hand", "saw_fd",
        "pend_cull", "pend_cull_type", "pend_cull_first", "pend_cull_skip",
        "cull_spell_seat",
        "pend_cull_mode", "pend_cull_keep", "died_in_beginning",
        "any_damage_kills",
        "pend_discard", "pend_discard_ops", "pend_discard_src",
        "pend_discard_tgt",
        "pend_grave", "pend_grave_owner", "pend_grave_dest",
        "pend_then",
        "winner", "truncated",
        "rng",
    )

    def __init__(self) -> None:
        self.perms = np.zeros((MAX_PERMS, N_PERM_COLS), np.int16)
        self.n_perms = 0

        self.hand = np.full((N_SEATS, MAX_HAND), -1, np.int16)
        self.n_hand = np.zeros(N_SEATS, np.int16)
        self.deck = np.full((N_SEATS, MAX_DECK), -1, np.int16)
        self.deck_ptr = np.zeros(N_SEATS, np.int16)   # next card to draw
        self.n_deck = np.zeros(N_SEATS, np.int16)     # cards originally dealt
        # The deck as **registered**, in the order it was submitted, never
        # shuffled and never mutated by play. `deck` cannot stand in for it:
        # the drawn prefix is dead space that `recycle` compacts away (see
        # `put_on_bottom`), so by mid-game the original 40 are unrecoverable.
        #
        # This is a decklist, not a library. Reading it as a MULTISET is
        # legitimate information whenever the list is known -- a registered
        # decklist is public in a match after game 1, and at top level a
        # Legend already implies most of it. Reading it in ORDER would be a
        # leak, because that is the draw order nobody may see. `obs.py`
        # therefore encodes counts per distinct card and never a position,
        # which is also what keeps `test_env`'s deck-order perturbation
        # invisible.
        self.decklist = np.full((N_SEATS, MAX_DECK), -1, np.int16)
        self.n_decklist = np.zeros(N_SEATS, np.int16)
        # Is THIS seat's decklist known to its opponent? Set per episode, not
        # by play. 1 for the Bo3 games 2-3 case where the list has been seen,
        # 0 for game 1 against a stranger. Randomized during training so the
        # policy develops both the explicit path and the read-it-from-play
        # path -- see `config.deck_known_prob`.
        self.deck_known = np.zeros(N_SEATS, np.int8)
        self.trash = np.full((N_SEATS, MAX_TRASH), -1, np.int16)
        self.n_trash = np.zeros(N_SEATS, np.int16)
        # 108.6 -- Banishment. A separate zone from the trash and NOT a
        # recoverable one, which is the whole point: [Flow] plays a spell from
        # the trash and then banishes it (829.1.b), and without somewhere else
        # for it to go it would land back in the trash and be replayable every
        # turn forever. Public information (108.6.e), unordered (108.6.d).
        self.banished = np.full((N_SEATS, MAX_BANISHED), -1, np.int16)
        self.n_banished = np.zeros(N_SEATS, np.int16)

        # Runes are fungible within a domain -- counts, not objects.
        self.runes_ready = np.zeros((N_SEATS, N_DOMAINS), np.int16)
        self.runes_spent = np.zeros((N_SEATS, N_DOMAINS), np.int16)
        # Rune Deck as a ring buffer: Recycle returns a rune to it (416.1.b), so
        # it is not a one-way stack. `rune_head` is the next rune to channel and
        # `rune_left` how many remain; a recycled rune is written at the tail.
        self.rune_deck = np.full((N_SEATS, RUNE_RING), -1, np.int8)  # domain ids
        self.rune_head = np.zeros(N_SEATS, np.int16)
        self.rune_left = np.zeros(N_SEATS, np.int16)

        # Rune Pool -- emptied at Main start and turn end (rule 167).
        self.pool_energy = np.zeros(N_SEATS, np.int16)
        # N_POOL_DOMAINS, not N_DOMAINS: the last column is [A] (see D_ANY).
        self.pool_power = np.zeros((N_SEATS, N_POOL_DOMAINS), np.int16)

        self.bf_card = np.full(N_BF, -1, np.int16)
        self.bf_ctrl = np.full(N_BF, -1, np.int8)      # -1 = uncontrolled
        self.bf_contested = np.zeros(N_BF, np.int8)
        # 190.3.a -- the SEAT that applied Contested to each battlefield, or -1.
        # `bf_contested` is the same fact as a bool and is kept in lock step
        # with it; this column exists because 464.2.c.1 designates the Attacker
        # as "the player whose unit(s) applied the Contested status", which a
        # flag cannot answer. The engine used to answer it with "whoever moved
        # most recently", which inverts the roles whenever the second arrival
        # is a reinforcement rather than the aggressor -- an [Ambush] unit
        # dropped in to defend ground the opponent just took became the
        # Attacker, and took [Assault] and the 466.1.a.2 Recall with it.
        self.bf_contester = np.full(N_BF, -1, np.int8)
        # Facedown Zone: max occupancy 1 (107.3.b); public zone, private card
        # (107.3.f). Only the battlefield's controller may occupy it (107.3.c).
        # 107.3.f -- ONE facedown card per battlefield, and Bandle Tree's whole
        # text is the exception ("you may hide an additional card here"). So
        # the zone is `N_FD_PER_BF` slots per battlefield rather than one, and
        # `chain.hideable` decides how many of them a given ground opens.
        # Flat rather than 2-D: every site here holds ONE facedown card, and
        # `fd_bf` is the only place that has to know a slot is not a
        # battlefield index.
        self.fd_owner = np.full(N_FD, -1, np.int8)
        self.fd_card = np.full(N_FD, -1, np.int16)
        # 811.1.b: "Beginning on the NEXT turn, this gains [Reaction]". So a
        # card hidden this turn cannot be played this turn. `ply` is a
        # monotone count of turn transitions and `fd_ply` records the ply the
        # card was hidden at; it is live once `ply` has moved past it.
        #
        # A plain ply counter rather than (turn, active): the latter encodes a
        # seat, which would break the canonicalization test in mirror.py.
        self.fd_ply = np.full(N_FD, -1, np.int16)
        # Rule 470: a player may Score a given Battlefield only once per turn,
        # by either method. Reset for both seats at the start of every turn.
        self.bf_scored = np.zeros((N_SEATS, N_BF), np.int8)

        self.chain = np.full((MAX_CHAIN, N_CHAIN_COLS), -1, np.int16)
        self.n_chain = 0
        # Targets chosen at Finalization, per chain item. Re-checked at
        # resolution (359.3.e) rather than trusted, because the window between
        # the two is exactly where a response lands.
        self.chain_targets = np.full((MAX_CHAIN, MAX_TARGETS), -1, np.int16)
        # Slot currently being filled for the item being finalized, or -1.
        self.pend_slot = -1
        # Chain index of an optional Triggered Ability awaiting its controller's
        # yes/no at finalization (383.3.a). -1 when nothing is waiting.
        self.pend_may = -1
        # Chain index of a Pending item awaiting its printed "kill a [...] as
        # an additional cost" target (820) -- see C_COST_KILL. Checked before
        # `pend_slot`'s ordinary target-slot loop: the cost is chosen first,
        # same as any other cost is paid before an effect's own targets.
        self.pend_cost_kill = -1
        # "Recycle N from your trash:" as a cost (3956). The chain ITEM being
        # paid for, and how many recycles it still owes. One pick per card
        # rather than one choice of a set, because the trash is unordered and
        # identical cards collapse (108.2.c) -- so each pick is a real choice
        # between distinct cards and N of them compose into the set.
        self.pend_cost_recycle = -1
        self.pend_cost_recycle_n = 0
        # [trigger kind, source permanent row, captured context int,
        #  subject permanent row, second captured context int,
        #  controlling seat or -1]
        #
        # The source is USUALLY a permanent row, and then the last column stays
        # -1 and the controller is read off that row. A BATTLEFIELD has no row
        # (see `bf_src`), so for one of those the seat has to be carried: "when
        # you conquer here" belongs to the conqueror, and by the time the queue
        # drains, `bf_ctrl` may already have moved on.
        # [trigger, source, captured location, subject, ctx2, controlling seat,
        # STEP STAMP]. The stamp groups triggers that became Pending at the
        # same moment: 383.3.d lets a player order their SIMULTANEOUS triggers,
        # but two triggers from different steps of one action are not
        # simultaneous and the earlier step's goes on the Chain first (464.2.b
        # before 464.2.e -- a showdown-begins trigger is placed under the
        # attack triggers, so the attack trigger resolves FIRST, RiftJudge
        # #10254). `chain.queue` stamps it and `chain.next_placer` only ever
        # offers the lowest stamp still queued.
        self.trig = np.full((MAX_TRIGGERS, 7), -1, np.int16)
        self.n_trig = 0
        # Seat currently choosing the order to place its simultaneous triggers
        # on the Chain (383.3.d). -1 when nobody is being asked.
        self.pend_order = -1
        self.chain_uid = 0        # monotone; next id for a chain item
        # 340.2.a -- was the CURRENT chain started by a triggered ability?
        # The rule turns on how the chain began, and by the time it empties the
        # item that began it is gone, so it is recorded as the chain is opened.
        self.chain_from_trigger = 0

        self.points = np.zeros(N_SEATS, np.int16)
        self.burned_out = np.zeros(N_SEATS, np.int8)
        # Lilting Lullaby: "its controller can't play spells this turn".
        # Turn-scoped, cleared in the end-of-turn cleanup.
        # 194.3 -- the score this game is played to. A per-game constant, but
        # it has to live on the STATE rather than only in `Config`, because
        # cards read it: "if an opponent's score is within 3 points of the
        # Victory Score" (Find Your Center, Leona - Zealot) is evaluated deep
        # inside `combat.static_applies`, which has no `cfg` and cannot be
        # given one without threading it through `combat.might` and every
        # caller of it.
        #
        # Defaults to the RULES value. `game.new_game` overwrites it from
        # `cfg.victory_score`, which is what the curriculum anneals (5 -> 8),
        # so a card that keys on it tracks the game actually being played
        # rather than the one the rulebook describes.
        self.victory_score = 8
        self.no_spells = np.zeros(N_SEATS, np.int8)
        # "Opponents can't play CARDS this turn" (Brynhir Thundersong).
        # Strictly wider than `no_spells`, which is Lilting Lullaby's "can't
        # play SPELLS": this one stops units and gear too, and 349 makes a
        # play a play whatever zone it comes out of, so it stops a Flow play
        # from the trash and a play back out of the Facedown Zone as well.
        #
        # It does NOT stop HIDING. 811.1.c.1 is explicit that Hide is not a
        # subset of Play, so a player locked out by this can still put a card
        # face down -- which is most of what the lock leaves them.
        self.no_cards = np.zeros(N_SEATS, np.int8)
        # Delayed Abilities currently armed for each seat (389-390), as the
        # CARD IDS that armed them, -1 for an empty slot. Cleared in the
        # end-of-turn cleanup beside `no_spells`, because every delayed ability
        # in the pool so far names "this turn" as its window (390.2).
        #
        # Card ids rather than a bitmask, so `trig_card` can decode a delayed
        # source with nothing but the state -- the same way it decodes a
        # battlefield from `bf_card` and a legend from `legend`.
        #
        # Arming the same card twice really does create two delayed abilities,
        # and both fire. That is a no-op for Rally the Troops, whose payload is
        # a Buff and 426.1.b.1 caps a unit at one -- but it is the rule, and
        # collapsing duplicates here would be wrong for the first delayed
        # ability whose effect stacks.
        self.delayed = np.full((N_SEATS, MAX_DELAYED), -1, np.int16)
        # Cards each seat has PLAYED this turn (349: played means finalized, or
        # resolved for a unit). [Legion] asks "have you played another card this
        # turn", and ten cards in the pool ask it. Reset in the Ending Phase
        # with the other turn-scoped state.
        # How many rows are currently Attached (719). A DENORMALISED count of
        # `P_ATTACHED_TO >= 0`, kept only so `attachments` can skip the scan on
        # a board with no Equipment -- which is most boards, and which the
        # profiler showed was costing a quarter of the engine's runtime.
        #
        # Denormalised state is a liability, so `invariants.check` recomputes
        # it every call rather than trusting the four writers to agree.
        self.n_attached = 0
        # "Units you play this turn enter ready" (Confront): the turn number the
        # promise was made on, per seat, or -1. A turn stamp rather than a flag,
        # so nothing has to remember to clear it.
        self.units_enter_ready_turn = np.full(N_SEATS, -1, np.int16)
        # "If you've gained XP this turn" (Wily Newtfish): the player turn each
        # seat last GAINED XP on, or -1. Spending XP does not touch it.
        self.xp_gained_ply = np.full(N_SEATS, -1, np.int16)
        self.cards_played = np.zeros(N_SEATS, np.int16)
        # Plays COMPLETED this turn, per seat. Not `cards_played`: 419.4.b has
        # non-triggered checks ([Legion], Battering Ram) count FINALIZED cards,
        # but 419.4.a fires "when you play your Nth card" only once the play
        # is completed by resolution, and a countered card never completes
        # (419.4.a.1). A spell countered first is still card 1 for Legion but
        # is no card at all for Astral Heron, whose first card is whichever
        # finishes resolving first (RiftJudge #12337, #12538).
        self.cards_completed = np.zeros(N_SEATS, np.int16)
        # SPELLS played this turn, per seat -- "if an opponent has played
        # another spell this turn" (Crumbling Sands). `played_types` only says
        # whether one was, and the card needs "another".
        self.spells_played = np.zeros(N_SEATS, np.int16)
        # Player-turn stamps, per seat, or -1: the turn a unit CONTROLLED by
        # that seat last died (Spoils of War, Towering Pairofant), and the turn
        # that seat last discarded (Raging Soul).
        self.unit_died_ply = np.full(N_SEATS, -1, np.int16)
        self.discarded_ply = np.full(N_SEATS, -1, np.int16)
        # "Prevent all spell and ability damage this turn" (Unyielding
        # Spirit): the player turn it was cast on, or -1. Global, not per seat.
        self.no_effect_damage_ply = -1
        # Per-seat player-turn stamps: the turn that seat last CHOSE an enemy
        # unit (Hungry Wolf), and the turn it last spent {4 energy}+ on one
        # spell (Prepared Neophyte).
        self.chose_enemy_ply = np.full(N_SEATS, -1, np.int16)
        # (seat, battlefield) -> the player turn that seat last CONQUERED it,
        # or -1 (Perched Grimwyrm). Not `bf_scored`, which a hold also sets.
        self.bf_conquered_ply = np.full((N_SEATS, N_BF), -1, np.int16)
        # "Buffs give an additional +1 Might to friendly units this turn"
        # (Stand United): the ply, per seat, or -1.
        self.buff_bonus_ply = np.full(N_SEATS, -1, np.int16)
        # How many Stand Uniteds are live this turn: each is its own duration
        # effect, so two give buffs +2 (RiftJudge #10500).
        self.buff_bonus_n = np.zeros(N_SEATS, np.int16)
        # "The next unit you play this turn enters ready" (Sun Disc): ply.
        self.next_unit_ready_ply = np.full(N_SEATS, -1, np.int16)
        # "Take a turn after this one" (Time Warp): extra turns owed per seat.
        self.extra_turns = np.zeros(N_SEATS, np.int8)
        # Points scored from HOLDING this turn, per seat, with the ply
        # (Needlessly Large Yordle).
        self.hold_points_ply = np.full(N_SEATS, -1, np.int16)
        self.hold_points = np.zeros(N_SEATS, np.int8)
        # Power SPENT this turn, per seat with its ply (Sivir - Mercenary).
        # "If you assigned 3 or more EXCESS damage" (Yeti Brawler, Tryndamere,
        # Sivir - Ambitious): combat damage a seat assigned beyond lethal once
        # every enemy unit had taken lethal, with the ply and whether that seat
        # was the attacker. No rule defines the term; this is its plain
        # reading, recorded by `combat._assign`.
        self.excess_ply = np.full(N_SEATS, -1, np.int16)
        self.excess_amt = np.zeros(N_SEATS, np.int16)
        self.excess_attacking = np.zeros(N_SEATS, np.int8)
        self.power_spent_ply = np.full(N_SEATS, -1, np.int16)
        self.power_spent = np.zeros(N_SEATS, np.int8)
        # "The next spell you play this turn deals 1 Bonus Damage" (Ravenborn
        # Tome) / "...has [Repeat] equal to its cost" (Temporal Portal): the
        # ply each promise was made on, spent by the next spell.
        self.next_spell_bonus_ply = np.full(N_SEATS, -1, np.int16)
        self.next_spell_repeat_ply = np.full(N_SEATS, -1, np.int16)
        # The Chain uid carrying a Ravenborn Tome bonus, per seat, and the bonus
        # live while that item resolves.
        self.bonus_uid = np.full(N_SEATS, -1, np.int16)
        self.resolving_bonus = 0
        # The spell now resolving paid its optional additional cost (C_REPEAT
        # 2) -- what COND_PAID_ADDITIONAL reads for a card with no row.
        self.resolving_paid = 0
        # A [Repeat] whose first pass suspended (Called Shot's look): the
        # second pass runs once that decision is answered.
        self.pend_repeat_card = -1
        self.pend_repeat_seat = -1
        self.pend_repeat_tgts = np.full(MAX_TARGETS, -1, np.int16)
        self.pend_repeat_bound = -1
        self.pend_repeat_hand = 0
        # "...banish it, then play it" (Reinforce, Dazzling Aurora): the card
        # sits in `rp_owner`'s Banishment while `rp_seat` decides where it
        # goes. `rp_armed` is a look whose pick will open this decision; the
        # cost mode, Energy discount, "here" location and "then empower it"
        # ride along from the op.
        self.rp_seat = -1
        self.rp_card = -1
        self.rp_owner = -1
        self.rp_cost = 0
        self.rp_discount = 0
        self.rp_here = -1
        self.rp_empower = 0
        self.rp_armed = 0
        # 820.1 -- a card played from outside the hand still owes any MANDATORY
        # additional cost it prints (Cruel Patron's kill, Legion Quartermaster's
        # gear). 1 once that kill has been made for the card in `rp_card`, so
        # the destination question that follows is asked only afterwards --
        # which is also the order the hand path uses, because Stalking Wolf's
        # destination depends on where the killed unit stood.
        self.rp_kill = 0
        # Baited Hook's pick ceiling (printed Might), -1 none.
        self.look_max_might = -1
        # The card the last look picked, for a follow-up that asks about it.
        self.look_last_pick = -1
        # The first row the last token creation made (Guards!'s "ready it").
        self.last_token = -1
        # Bone Skewer: where the revealer plays the picked unit, or -1.
        self.reveal_play_loc = -1
        # Cards drawn this turn per seat (Frigid Jewel's "second card").
        self.draw_ply = np.full(N_SEATS, -1, np.int16)
        self.draw_count = np.zeros(N_SEATS, np.int16)
        self.second_draw_ply = np.full(N_SEATS, -1, np.int16)
        # CULL_MOVE_OWN_TO's destination location, or -1.
        self.pend_cull_dest = -1
        # OP_SPLIT_DAMAGE: who hands out the points, how many remain, where
        # (a location, or -1 for any battlefield), and the running allocation.
        self.pend_split = -1
        self.split_left = 0
        self.split_loc = -1
        self.split_xp = 0
        self.split_spell = 0
        self.split_alloc = np.zeros(MAX_PERMS, np.int16)
        # Who controlled each battlefield before its last conquest (-1 none).
        self.bf_prev_ctrl = np.full(N_BF, -1, np.int8)
        # The battlefield card a Brush token REPLACED, so Brush's own "when you
        # score here, you may replace this with the battlefield it replaced"
        # has something to put back (Ivern - Green Father). -1 is "this slot is
        # the card it was dealt".
        self.bf_replaced = np.full(N_BF, -1, np.int16)
        # "The FIRST friendly ... each turn costs {1 energy} less" (Ornn's
        # Forge, Piltovan Forge). Per seat and per battlefield, because two
        # such grounds would each give their own discount.
        self.bf_first_use = np.full((N_SEATS, N_BF), -1, np.int16)
        # The permanent whose ability is being COSTED right now, or -1. Read by
        # `cost.ability_energy` for a ground rule that asks where the source is
        # standing (Risen Altar's "[Empower] costs of your units HERE"); the
        # activation sites set it around the cost computation. Not game state
        # in the rules sense, which is why it is cleared as soon as it is used.
        self.empower_src = -1
        # "Increase the points needed to win the game by 1" (Aspirant's
        # Climb). Kept on the state rather than in the Config, because it comes
        # from a battlefield in play and the Config is the same object for
        # every game in a batch. `check_winner` adds it.
        self.victory_bonus = 0
        # "Your non-token units cost {1 energy} more to play THIS TURN" (Vaults
        # of Helia, paid by the player who held it). A turn stamp, so it lifts
        # by itself.
        self.unit_tax_ply = np.full(N_SEATS, -1, np.int16)
        # "You can hide cards ignoring costs THIS TURN" (Guerilla Warfare).
        # 811.1.b's price for hiding is {any rune}, paid by recycling one, and
        # this stamp is what lets a hide skip it -- the same self-lifting idiom.
        self.free_hide_ply = np.full(N_SEATS, -1, np.int16)
        # Altar of Blood -- the unit whose death its controller is being asked
        # to pay to replace, or -1. A death REPLACEMENT that charges a cost has
        # to be a decision taken at the moment of death (136.2.d), so the sweep
        # that was killing it stops here and `actions` asks.
        self.pend_altar = -1
        # 372 -- the dying permanent whose Replacement Effect ORDER its
        # controller is being asked to pick, or -1. `repl_pick` is the kind they
        # chose (a `combat.RK_*`) per row, and `repl_ply` the ply stamp that
        # makes that answer stick for the instant it takes the caller to come
        # back round and kill the unit for real. The same shape as `pend_altar`
        # / `altar_ply`, and for the same reason: `_destroy` suspends by simply
        # returning without killing.
        # 373 -- ONE replacement, several simultaneous deaths it could apply
        # to: "they must decide which event to apply Zhonya's Hourglass to
        # first" is the rule's own worked example. The SEAT being asked, or -1.
        #
        # The candidates have to be STORED, not recomputed. The first version
        # recomputed them from marked lethal damage, which is wrong for
        # `destroy()` -- 428's kill outright marks no damage, so the unit dying
        # was missing from its own candidate list while any unrelated unit
        # sitting at lethal damage mid-sweep was in it. The batch is the truth
        # and it is a local, so it is captured here at the moment of suspension.
        #
        # No `guard_pick` to go with these: the answer is carried out
        # immediately, and healing the chosen unit is what takes it out of the
        # sweep that comes back round.
        self.pend_guard = -1
        self.guard_cands = np.full(MAX_PERMS, -1, np.int16)
        self.n_guard_cands = 0
        self.pend_repl = -1
        self.repl_pick = np.full(MAX_PERMS, -1, np.int8)
        self.repl_ply = np.full(MAX_PERMS, -1, np.int16)
        # ...and the per-row stamp that keeps the same death from being offered
        # twice: declining has to stick for the instant it takes the caller to
        # come back round and kill the unit for real.
        self.altar_ply = np.full(MAX_PERMS, -1, np.int16)

        # --- Combat damage assignment (465.2.c), when the PLAYER assigns ------
        #
        # 465.2.c.2 gives the choice of which units die to the player dealing
        # the damage, and `[Tank]` / `[Backline]` exist to constrain exactly
        # that choice -- so an engine that picks for them makes both keywords
        # strategically inert. `combat.solve_kills` still answers it whenever
        # there is nothing to decide (the pool covers every target, so wiping
        # the board is forced) or when `cfg.engine_solves_damage_assignment`
        # pins the old behaviour; these slots carry the case that is a real
        # decision.
        #
        # `pend_dmg` is the seat currently choosing, or -1. Both seats may owe
        # a choice in the same damage step, and they are asked one after the
        # other -- but **nothing either picks is applied until both are done**,
        # because 465 deals damage simultaneously. Writing the first seat's
        # kills to the board before asking the second would let the second
        # answer while knowing the first's choice, which is information the
        # real game never gives.
        self.pend_dmg = -1
        # The damage each seat still has left to spend, and the battlefield the
        # assignment is happening at. The pools are computed once against the
        # pre-damage board (`might_for_pool`) and then drawn down, so a unit
        # that dies mid-assignment still contributed its full Might.
        self.pend_dmg_pool = np.zeros(N_SEATS, np.int16)
        self.pend_dmg_bf = -1
        # Per seat: the candidate enemy rows, and the rows chosen to kill so
        # far. Rows, not cards -- mirroring keeps rows in place.
        self.pend_dmg_targets = np.full((N_SEATS, MAX_PERMS), -1, np.int16)
        self.pend_dmg_n_tgt = np.zeros(N_SEATS, np.int16)
        self.pend_dmg_kills = np.full((N_SEATS, MAX_PERMS), -1, np.int16)
        self.pend_dmg_n_kill = np.zeros(N_SEATS, np.int16)
        # Which seats have finished choosing. A seat whose assignment was
        # forced (or solved by the engine) is marked done without being asked,
        # so the damage step can tell "nothing to do" from "not asked yet".
        self.pend_dmg_done = np.zeros(N_SEATS, np.int8)

        # --- [Show Off] (RAD) ------------------------------------------------
        # "[Show Off] a unit. (As you play this, you may reveal a unit from
        # your hand or pick a friendly unit.)"
        #
        # An as-you-play choice whose RESULT later text reads back -- Primordial
        # Roar's "if you showed off a unit, deal damage equal to that unit's
        # Might". So unlike [Predict] the answer has to outlive the decision,
        # and unlike an optional additional cost it is not enough to record
        # THAT it happened: the card needs to know WHICH unit.
        #
        # Two sources, so two slots, and exactly one of them is set:
        #   `show_off_perm` -- a permanent ROW, for "pick a friendly unit".
        #                      Its Might is read live at resolution, so a buff
        #                      gained in between counts.
        #   `show_off_card` -- a CARD id, for "reveal a unit from your hand".
        #                      The card stays in hand; only its identity is
        #                      public, and a card in hand has no buffs, so its
        #                      Might is the printed one.
        #
        # **`show_off_card` is public information and the encoder must show it
        # to BOTH seats.** Revealing is the price you pay for showing off from
        # hand, and an opponent who cannot see it is being denied something the
        # table saw. `saw_hand` is no help: that is a whole-hand reveal, and
        # this is one card.
        self.show_off_perm = np.full(N_SEATS, -1, np.int16)
        self.show_off_card = np.full(N_SEATS, -1, np.int16)
        self.show_off_ply = np.full(N_SEATS, -1, np.int16)
        # The seat currently being asked, or -1. Opened while the card is being
        # played and closed before it resolves.
        self.pend_show_off = -1
        # Energy that may only pay for spells (Lux, Crownguard); pools empty
        # with the rest.
        # Energy and Power that may only be spent on certain things (135.2.e.4
        # lets an effect restrict what it adds). One column per restriction:
        #   RK_SPELL     "only to play spells"        (Lux, Crownguard; Kai'Sa)
        #   RK_SHOWDOWN  "only during showdowns"      (Diana - Scorn of the Moon)
        #   RK_GEAR      "gear, or gear abilities"    (Ornn - Fire Below...)
        #   RK_UNIT      "units, or unit abilities"   (Renekton)
        # Kept apart from `pool_energy`/`pool_power` rather than flagged on
        # them, because the general pool is spent by everything and these are
        # spent FIRST only by the payments that qualify -- `cost.plan_payment`
        # asks which columns this payment may reach.
        self.pool_rstr_e = np.zeros((N_SEATS, N_RESTRICT), np.int16)
        self.pool_rstr_p = np.zeros((N_SEATS, N_RESTRICT), np.int16)
        # Cards recycled to each Main Deck since the last settle (Karma).
        self.recycled_n = np.zeros(N_SEATS, np.int16)
        # The same deferred-event idiom for two more player events, both of
        # which happen deep inside a payment or a zone change where no table is
        # in scope: a RUNE recycled (Sivir - Battle Mistress) and a card
        # BANISHED by its owner (Zed - Master of Shadows). `actions._settle`
        # turns the count into watcher triggers and clears it.
        self.rune_recycled_n = np.zeros(N_SEATS, np.int16)
        self.banished_n = np.zeros(N_SEATS, np.int16)
        # How many times this seat has chosen an enemy unit or gear THIS turn
        # (Ezreal - Prodigal Explorer asks for twice). Paired with
        # `chose_enemy_ply`, which says which turn the count belongs to.
        self.chose_enemy_n = np.zeros(N_SEATS, np.int16)
        # Cards banished WITH a legend, which is a different thing from being
        # in Banishment: Jhin - Virtuoso pays out at four and puts those four
        # back, so which ones they were has to be remembered. Four slots,
        # because four is what the card counts to.
        self.legend_pile = np.full((N_SEATS, 4), -1, np.int16)
        self.legend_pile_n = np.zeros(N_SEATS, np.int16)
        # OP_PAY_ANY_AMOUNT: who picks, which kind, the battlefield (a
        # location) for a damage kind, and whether a spell is dealing it.
        self.pend_amount = -1
        self.amt_kind = 0
        self.amt_loc = -1
        self.amt_spell = 0
        self.free_gear_ply = np.full(N_SEATS, -1, np.int16)
        self.armory_ply = np.full(MAX_PERMS, -1, np.int16)
        self.last_burned = -1
        # OP_PLAY_FROM_HAND's keyword filter (ALL_KEYWORDS index, -1 none) and
        # whether spells qualify.
        self.hp_kw = -1
        self.hp_spells = 0
        # Granted plays from the trash, per seat: the card, its (energy, power),
        # the turn it lasts (-2 until used) and whether it banishes after.
        self.flow_grant_card = np.full((N_SEATS, 4), -1, np.int16)
        self.flow_grant_e = np.zeros((N_SEATS, 4), np.int16)
        self.flow_grant_p = np.zeros((N_SEATS, 4), np.int16)
        self.flow_grant_ply = np.full((N_SEATS, 4), -1, np.int16)
        self.flow_grant_banish = np.zeros((N_SEATS, 4), np.int16)
        # Reveal-play extras: which zone the card waits in (0 Banishment, 1
        # trash), Power added to its cost, and whether it is still to be
        # chosen from `sarc_cards` (Cursed Sarcophagus).
        self.rp_zone = 0
        self.rp_power = 0
        self.rp_from_sarc = 0
        self.sarc_cards = np.full((N_SEATS, 8), -1, np.int16)
        self.n_sarc = np.zeros(N_SEATS, np.int16)
        # Discount bought by the unit play's kill costs so far (Atakhan).
        self.kill_disc_e = 0
        self.kill_disc_p = 0
        # OP_STEAL_SPELL: who decides, which Chain Item (uid), and the stage --
        # 1 pay-or-counter, 2 make new choices?, 3 choosing them slot by slot.
        self.steal_seat = -1
        self.steal_uid = -1
        self.steal_stage = 0
        self.steal_slot = 0
        self.steal_targets = np.full(MAX_TARGETS, -1, np.int16)
        # Each row's last Move, both ends (locations); and buffs beyond the
        # first on a MULTI_BUFF unit (moved with the row on compaction).
        self.move_from = np.full(MAX_PERMS, -1, np.int16)
        self.move_to = np.full(MAX_PERMS, -1, np.int16)
        self.extra_buffs = np.zeros(MAX_PERMS, np.int16)
        # A granted tag per row (index into effects.GRANTABLE_TAGS, -1 none).
        self.tag_grant = np.full(MAX_PERMS, -1, np.int16)
        # What each row named (a tag-vocab index or a card id), and the open
        # naming decision: who, which kind, for which row, and the options.
        self.named = np.full(MAX_PERMS, -1, np.int16)
        self.pend_name = -1
        self.name_kind = 0
        self.name_src = -1
        self.name_opts = np.full(8, -1, np.int16)
        self.n_name_opts = 0
        # "Becomes a copy of" (Mirror Image, Keeper of Masks, Shady Spectacles):
        # the card whose printed characteristics the row now has, and the
        # Equipment row it lasts only while attached through (-1: for good).
        self.copy_of = np.full(MAX_PERMS, -1, np.int16)
        self.copy_via = np.full(MAX_PERMS, -1, np.int16)
        # How many tokens the last token creation made (rows from last_token).
        self.last_token_n = 0
        # The card a following "becomes a copy of" will copy, or -1.
        self.copy_pending = -1
        # A spell's ability given to the row this turn (Dominus).
        self.granted_card = np.full(MAX_PERMS, -1, np.int16)
        self.granted_ply = np.full(MAX_PERMS, -1, np.int16)
        # Times Dancing Grenade has dealt damage this turn.
        self.grenade_ply = -1
        # "You control it until I leave the board" (Akshan): the row whose
        # leaving hands this permanent back, or -1.
        self.ctrl_link = np.full(MAX_PERMS, -1, np.int16)
        # Units banished with The Zero Drive, per its controller: card, owner.
        self.zero_cards = np.full((N_SEATS, 8), -1, np.int16)
        self.zero_owner = np.full((N_SEATS, 8), -1, np.int16)
        self.n_zero = np.zeros(N_SEATS, np.int16)
        # A resolution paused mid-way (Void Hatchling's peek): where its spec
        # comes from (1 spell, 2 ability, 3 Equipment ability, 4 follow-up
        # key), the op to resume at, and everything `resolve` was called with.
        self.resume_kind = 0
        self.resume_card = -1
        self.resume_idx = -1
        self.resume_op = 0
        self.resume_seat = -1
        self.resume_src = -1
        self.resume_ctx = -1
        self.resume_ctx2 = -1
        self.resume_subj = -1
        self.resume_hand = 0
        self.resume_bound = -1
        self.resume_tgts = np.full(MAX_TARGETS, -1, np.int16)
        # 355.11.b -- "up to three units at the SAME location" (Bellows Breath)
        # whose units a response has scattered. The spell does not fizzle: its
        # controller names ONE of the locations they are now at, and only what
        # they chose there is affected. `pend_group_loc` is the seat being asked,
        # `group_loc_opts` the locations they may name, and `group_loc` the one
        # they named -- consumed by the resolution that resumes. See
        # `resolve._resolve`'s group block and `actions._finish_group_loc`.
        self.pend_group_loc = -1
        self.group_loc_opts = np.full(MAX_TARGETS, -1, np.int16)
        self.n_group_loc = 0
        self.group_loc = -1
        # Promising Future's walk: 1 looks, 2 plays; who started; each seat's
        # banished pick.
        self.pf_stage = 0
        self.pf_first = -1
        self.pf_cards = np.full(N_SEATS, -1, np.int16)
        # Divine Judgment's walk: the choosing seat, who went first, the
        # category (0 units, 1 gear, 2 runes, 3 hand) and what is kept.
        self.dj_seat = -1
        self.dj_first = -1
        self.dj_cat = 0
        self.dj_keep = np.zeros(MAX_PERMS, np.int8)
        self.dj_rune_keep = np.zeros((N_SEATS, N_DOMAINS), np.int8)
        self.dj_hand_keep = np.zeros((N_SEATS, MAX_HAND), np.int8)
        # Endless Riches each seat controls: trash-bound cards are banished
        # instead, the Draw Phase is skipped, and the trash is playable.
        self.riches_on = np.zeros(N_SEATS, np.int8)
        self.grenade_hits = 0
        # Ashe - Focused: the pending reveal's pick is mandatory and returns;
        # the cards waiting, per OWNER, for that owner's next hold.
        self.reveal_hold_return = 0
        self.hold_return = np.full((N_SEATS, 8), -1, np.int16)
        self.n_hold_return = np.zeros(N_SEATS, np.int16)
        self.big_spell_ply = np.full(N_SEATS, -1, np.int16)
        # "The next spell you play this turn costs {5 energy} less" (Raging
        # Firebrand): Energy, per seat, spent by the next SPELL and cleared at
        # end of turn. Not `next_discount`, which any card spends.
        self.next_spell_discount = np.zeros(N_SEATS, np.int16)
        # "Your NEXT card costs {2 energy}{any rune}{any rune} less" -- Astral
        # Heron. (energy, power) per seat: a one-shot discount that belongs to
        # the PLAYER rather than to any card, which is what makes it unlike
        # every other cost modification in `cost.py`. Those are read off a
        # permanent that is still standing; this one is a promise with no
        # source left to ask.
        #
        # Spent by the next card PLAYED, not by the next card paid for: "your
        # next card" names the card, so one played for free (811.1.b) consumes
        # it too. Cleared at the end of the turn alongside `cards_played` --
        # the promise is made and meant to be used inside one turn, and letting
        # it survive would have a Heron trigger on turn 3 discount a card on
        # turn 5.
        self.next_discount = np.zeros((N_SEATS, 2), np.int16)
        # Experience. Gained by [Hunt] on a Score and by cards that say so,
        # spent by "Spend N XP" costs. **Not turn-scoped** -- it accumulates
        # across the game, which is what makes [Level 11] reachable at all.
        self.xp = np.zeros(N_SEATS, np.int16)
        # Keywords granted to a permanent, indexed by GRANT_IDX. Two arrays
        # because the pool grants both ways: Shadow's Call's [Temporary] lasts
        # until the unit leaves, while Cleave's [Assault 3] is "this turn".
        #
        # **Parallel to `perms`, so anything that moves a row must move these
        # too.** `compact_permanents` renumbers rows at end of turn, and a
        # grant array left behind would hand one unit's [Assault 3] to whatever
        # unit landed on its index -- silently, and only on long turns.
        self.kw_grant = np.zeros((MAX_PERMS, N_GRANTABLE), np.int16)
        self.kw_grant_turn = np.zeros((MAX_PERMS, N_GRANTABLE), np.int16)
        # 107.4 -- the Legend Zone. The Champion Legend is a Game Object (174)
        # but explicitly NOT a Permanent (175): it has no location, cannot be
        # killed (174.3) or moved (174.4), and never leaves the zone (107.4.d).
        # So it gets fields of its own rather than a `perms` row, which would
        # make it answer to "kill a unit" and every board sweep in the pool.
        self.legend = np.full(N_SEATS, -1, np.int16)
        # **Zone occupancy**, cleared when the champion is played (108.3.d).
        self.champion = np.full(N_SEATS, -1, np.int16)
        # **Registered identity**, never cleared. 108.3.e makes the Chosen
        # Champion public, and it STAYS public once played -- it is then on the
        # board or in a trash, both public zones, and it was on the registered
        # decklist either way. So "which champion did this player choose" is a
        # standing fact about the deck, while `champion` above is only "is it
        # still in the zone".
        #
        # The two were one field until 108.3.d made the card playable, and
        # conflating them silently undid the deck-conditioning work: the moment
        # a player cast their champion, the archetype signature the encoder
        # reads went blank and the policy lost half of what told it which deck
        # it was piloting. See [[rl-deck-conditioning-and-public-archetype]].
        self.champion_reg = np.full(N_SEATS, -1, np.int16)
        # A legend CAN be exhausted, which is the cost most of them charge
        # ("Exhaust: [Add] {1 energy}"), and 315.1.b readies "all Game Objects
        # they control that are able to be readied" -- so the Awaken Phase
        # readies it exactly as it readies a unit. Starts ready.
        self.legend_ready = np.ones(N_SEATS, np.int16)
        # 441 -- a legend can hold the [Empowered] status like any other Game
        # Object (Zed - Master of Shadows, Mel, Ambessa - Matriarch of War all
        # empower themselves and spend it), and it is binary (441.1.a). A seat
        # column rather than a row flag, for the same reason `legend_ready` is.
        self.legend_emp = np.zeros(N_SEATS, np.int16)
        # "The first time each turn" on a LEGEND's watcher. Per seat, because
        # the legend is the seat's -- the row-indexed `once_used` has no row to
        # use here.
        self.legend_once = np.full(N_SEATS, -1, np.int16)
        # "Use only if you've played an Equipment this turn" (Azir - Emperor of
        # the Sands). A player-turn stamp, the same idiom as `big_spell_ply`:
        # the question is about the turn, not about a card still on the board.
        self.equip_played_ply = np.full(N_SEATS, -1, np.int16)
        # "Ready 2 runes AT THE END OF THIS TURN" (Targon's Peak). A delayed
        # effect, and the only one in the whole pool -- one card of 937 -- so
        # it is a per-seat counter applied in `ending` rather than a general
        # delayed-trigger queue built for a single user. It is a real piece of
        # state either way: the runes are promised the moment the battlefield
        # is conquered, which is what makes tapping out that turn cheap
        # ([[riftbound-tapping-out-costs-the-opponents-turn]]).
        self.pending_ready_runes = np.zeros(N_SEATS, np.int16)
        # "[Add] {any rune} at the start of your next Main Phase" (Blue
        # Sentinel): [A] owed to each seat, paid by `phases.enter_main`.
        self.pending_add_any = np.zeros(N_SEATS, np.int16)
        # 315.2 -- the turn is SUSPENDED partway through the Beginning Phase.
        #
        # The Beginning Step (315.2.a) puts start-of-phase effects on the Chain,
        # and the Scoring Step (315.2.b) is a separate, LATER step. So a trigger
        # there must fully resolve -- through real priority windows -- before
        # anything Holds. `start_turn` used to run both steps straight through
        # and drain the trigger queue afterwards, which put every
        # start-of-Beginning ability after the scoring it is supposed to
        # precede. Dusk Rose Lab is the card that makes it visible: "kill a unit
        # you control here to draw 1 (this happens before scoring)" banked the
        # Hold AND drew the card, instead of trading one for the other.
        #
        # -1 when the turn is running normally, which is always in v0: nothing
        # triggers there, so nothing ever suspends and the golden replays are
        # untouched.
        self.pend_phase = -1

        self.turn = 1
        # **`turn` is a ROUND and `ply` is a player's TURN.** `turn` only moves
        # when the second seat ends, so it names both players' turns in a round
        # at once; `ply` moves at every end of turn. Every "this turn" stamp
        # must use `ply` -- keyed on `turn`, "once each turn" silently covered
        # the opponent's following turn too (Nasus, Pyke - Returned, Zilean),
        # Brutalizer's "attached this turn" lasted through the opponent's turn,
        # and a hand revealed on your turn stayed visible through theirs.
        # `turn` is right only for round-scoped questions: "your first turn"
        # (COND_FIRST_TURN), the turn cap, and reporting.
        self.ply = 0        # monotone; incremented at every end of turn
        self.active = 0
        self.phase = MAIN
        self.priority = 0
        self.focus = -1
        self.showdown_bf = -1
        self.showdown_step = SD_NONE
        # 1 while the open Showdown is a Combat Showdown, 0 while it is the
        # plain kind 344.2 opens at a battlefield only one player has units at.
        # They share every mechanism except the ending: 348.1 sends one on to
        # the damage step, 348.2 closes the other by establishing Control.
        self.showdown_combat = 0
        self.attacker = -1   # seat that applied Contested (464.2.c.1)
        self.passes = 0      # consecutive passes in the current priority loop

        # In-progress Move declaration (PLAN.md §1.3.a). One destination, a
        # bitmask over permanent rows, committed as a single group.
        self.decl_dst = -1
        self.decl_mask = 0
        # Hand index of a card whose location choice is still open, or -1. The
        # second factored decision point; target selection joins these later.
        self.pend_play = -1
        # **Whose hand `pend_play` indexes.** It used to be implicitly the turn
        # player, which held while only the turn player could announce a unit.
        # [Ambush] broke that: 822.1.b gives a unit [Reaction] speed, so it is
        # announced in a response window that may be the opponent's turn, and a
        # bare index is then ambiguous between two hands of different lengths.
        self.pend_play_seat = -1
        # Hand index of a UNIT/GEAR whose printed "kill a [...] as an
        # additional cost" (820) is still open, or -1. 337.2 gives a unit no
        # Chain item to hang C_COST_KILL on, so this pair mirrors `pend_play`/
        # `pend_play_seat` instead -- chosen (and paid, immediately) BEFORE
        # `pend_play` opens, since Stalking Wolf's destination depends on it.
        self.pend_kill_play = -1
        self.pend_kill_play_seat = -1
        # The LOCATION the cost_kill target stood at, captured just before it
        # is killed -- Stalking Wolf's "you may play me to ITS BATTLEFIELD"
        # reads this once `pend_play` opens. -1 for any card without that
        # printed permission; harmless to leave set between plays, since only
        # a name in `effects.PLAY_TO_COST_KILL_LOC` ever reads it, and it is
        # always overwritten fresh immediately before such a card's own
        # destination choice opens.
        self.pend_kill_play_loc = -1
        # "Counter a spell UNLESS its controller pays {N}" (Hard Bargain) --
        # the seat being asked to pay, or -1 when nobody is.
        #
        # A decision handed to the OTHER player in the middle of someone else's
        # spell resolving, which is why it needs its own pending field rather
        # than riding the target machinery: by the time it is asked, Hard
        # Bargain has already chosen its target and is executing.
        self.pend_tax = -1
        # "...unless its controller has you draw 2" / "each opponent may play a
        # Gold" / "its owner places it on the top or bottom" -- another player
        # answers ACCEPT or DECLINE, and FOLLOWUPS[yes] or [no] then runs for
        # the CASTER, with the asked-about permanent as the subject.
        # "Play a unit from your hand ..." as an EFFECT (Here to Help, Rift
        # Herald, Rell - Magnetic): the seat choosing, the printed limits on
        # the card, how it is paid, and where it lands. `hp_pick` is the hand
        # index already chosen while a destination is still to be picked.
        self.pend_hand_play = -1
        self.hp_types = 0            # LK_* mask, 0 = any
        self.hp_tag = -1             # 1 = must be Equipment, else unused
        self.hp_max_energy = -1
        self.hp_cost = 0             # COST_PRINTED / COST_FREE / COST_NO_ENERGY
        self.hp_discount = 0         # Energy off a COST_PRINTED play
        self.hp_dest = -1            # -1 base, -2 a battlefield you control, else loc
        self.hp_attach = -1          # row to attach an Equipment to, or -1
        self.hp_optional = 0
        self.hp_pick = -1
        self.pend_ask = -1           # seat being asked
        self.pend_ask_caster = -1    # seat the follow-up ops resolve for
        self.pend_ask_yes = -1       # FOLLOWUPS key on ACCEPT (-1 none)
        self.pend_ask_no = -1        # FOLLOWUPS key on DECLINE (-1 none)
        self.pend_ask_subj = -1      # permanent row the follow-ups name
        self.pend_ask_card = -1      # the card asking, for the observation
        # The Chain UID of the spell that gets countered if they refuse. A
        # uid, never a chain ROW: the row moves as items above it resolve, and
        # the whole point of this decision is that a priority window's worth of
        # Chain activity can sit between the ask and the answer.
        self.pend_tax_uid = -1
        # What refusing costs them, in energy. Carried rather than re-read from
        # the card, because [Repeat] can execute the same op twice and the
        # second execution must ask for its own payment.
        self.pend_tax_cost = 0
        # Hand index of a card whose Hide destination is still open, or -1.
        self.pend_hide = -1
        # 117 -- the seat performing its Mulligan, or -1 once both are done.
        # A bitmask of hand indices rather than a list, exactly like
        # `decl_mask`: the choice is a SET of up to two cards, and a mask makes
        # "already chosen" a test rather than a scan.
        self.pend_mull = -1
        self.mull_mask = 0

        # "Look at the top N cards of your Main Deck..." -- a choice made
        # DURING resolution, not at finalization, so it is not targeting
        # (355.10: no count is announced and the opponent cannot respond to
        # it). The cards sit here, off the deck and in no other zone, until
        # the choice is made -- which is why `fuzz.cards_owned` has to count
        # this buffer or conservation fires on a healthy game.
        self.look_cards = np.full(MAX_LOOK, -1, np.int16)
        self.n_look = 0
        self.pend_look = -1        # the seat choosing, or -1
        self.look_pick_dest = DEST_HAND
        self.look_rest_dest = DEST_RECYCLE
        self.look_optional = 0     # may the player pick nothing?
        self.look_multi = 0        # may they pick REPEATEDLY? (436.1.a)
        self.look_type_mask = 0    # 0 = any type; see LK_* above
        self.look_min_energy = 0   # Fate Weaver's "Energy cost 4 or more"
        self.look_reveal = 0       # effects.LOOK_REVEAL_*: is the pick revealed?
        self.look_domain = -1      # Decree of Strength's "a Mind card"

        # "When you look at cards from the top of your deck (and don't draw
        # them) and see me, you may play me for {any rune}" -- Nocturne,
        # Horrifying. A buffer index (not a hand index), or -1: the card is
        # being played out of the LOOK BUFFER, and the destination choice is
        # still to come. A sub-decision NESTED inside the look, so `pend_look`
        # stays set the whole time and nothing settles until both are done.
        self.pend_play_look = -1

        # Zhonya's Hourglass: "The next time a friendly unit would die, kill
        # this instead." A DELAYED REPLACEMENT -- registered when the gear
        # resolves and consumed by the next friendly death, so it is the row of
        # the guarding permanent per seat, or -1 for none.
        #
        # It replaces the death, NOT its cause. Zhonya's does not say "heal",
        # where Guardian Angel's effect text explicitly does (136.2.d), so a
        # unit recalled with lethal damage still marked dies again on the very
        # next 143.2.a check. That is why the card reads as anti-REMOVAL rather
        # than anti-damage.
        self.death_guard = np.full(N_SEATS, -1, np.int16)

        # "Once each turn" on a PERMANENT's ability -- the turn number it was
        # last used, per permanent row, or -1. A turn stamp rather than a flag
        # so nothing has to remember to reset it, and per ROW rather than per
        # seat because two copies of the card each get their own use.
        self.once_used = np.full(MAX_PERMS, -1, np.int16)
        # 459/464.2.c -- has this row already been handed its Attacker or
        # Defender designation in the CURRENT Showdown? Cleared by
        # `combat.open_showdown`, so it needs no id of its own, and never
        # survives a compaction (which asserts no Showdown is open). A unit
        # that walks into an ongoing Combat is designated in the next Cleanup
        # (323.2.a) and its "when I attack" fires then -- this is how the
        # newcomers are told apart from the units already fighting.
        self.desig = np.zeros(MAX_PERMS, np.int8)
        # ...and which SEATS have held a role in this Showdown at all. A unit
        # that walks out loses its designation (323.2.c) and is designated
        # afresh if it comes back, so `desig` alone cannot say whether a player
        # has already defended here -- and the battlefield's own "when you
        # defend here" fires once for the PLAYER. Cleared with `desig`.
        self.desig_seat = np.zeros(N_SEATS, np.int8)
        # Per-ROW player-turn stamps for one-turn replacement effects, same
        # idiom as `once_used`: "the next time it would die this turn, heal it,
        # exhaust it, and recall it instead" (Tactical Retreat, Highlander) and
        # "kill it the next time it takes damage this turn" (Noxian Guillotine).
        # Spent by clearing to -1.
        self.death_shield_ply = np.full(MAX_PERMS, -1, np.int16)
        self.guillotine_ply = np.full(MAX_PERMS, -1, np.int16)
        # "When IT dies / wins a combat this turn, ..." (Siphoning Strike,
        # Deadly Flourish, Grim Resolve): a Delayed Ability about ONE unit. The
        # ply it was marked on, and the delayed slot of the marking seat that
        # holds the card -- the seat is `mark_seat`. -1 when unmarked.
        self.mark_ply = np.full(MAX_PERMS, -1, np.int16)
        self.mark_slot = np.full(MAX_PERMS, -1, np.int8)
        self.mark_seat = np.full(MAX_PERMS, -1, np.int8)
        # Moves this player-turn, per ROW: (ply, count). Yasuo - Windrider's
        # "the third time I move in a turn", Kayn - Unleashed's "moved twice".
        self.move_ply = np.full(MAX_PERMS, -1, np.int16)
        self.move_count = np.zeros(MAX_PERMS, np.int8)
        # Modes this ROW's ability chose this turn, as a bitmask with its ply:
        # "Choose one you've not chosen this turn" (Udyr - Wildman, Aphelios).
        self.mode_used_ply = np.full(MAX_PERMS, -1, np.int16)
        self.mode_used_mask = np.zeros(MAX_PERMS, np.int8)
        # End-of-turn reversals, per ROW with the ply they were set on:
        # EOT_DISEMPOWER / EOT_EMPOWER (Sanction, Tornado Warrior) and
        # EOT_REVERT_CONTROL (Hostile Takeover -- lose control, recall).
        self.eot_ply = np.full(MAX_PERMS, -1, np.int16)
        self.eot_kind = np.zeros(MAX_PERMS, np.int8)
        # "Its base Might becomes 5 this turn" (Dragon Form): ply and value.
        self.base_might_ply = np.full(MAX_PERMS, -1, np.int16)
        self.base_might_val = np.zeros(MAX_PERMS, np.int16)
        # One-turn damage modifiers on a ROW: a Prevent Value ("prevent the
        # next 7", Ki Barrier), a whole-next-instance prevent (Counter Strike),
        # doubling (Lotus Trap), and "if it would die this turn, banish it
        # instead" (Smite).
        #
        # The Prevent Value is a SUM: two Ki Barriers are two Prevent actions
        # and 437.5.a counts "the Prevent Value of all Prevent Actions on a
        # Unit" (RiftJudge #12071). Counter Strike's prevent is not a value --
        # it eats one instance whatever its size -- so it has its own stamp
        # rather than a sentinel in the sum that a Ki Barrier would overwrite.
        # The ply this ROW last took part in a Conquer (Blighted Battleaxe's
        # "if I didn't conquer this turn").
        self.conquer_ply = np.full(MAX_PERMS, -1, np.int16)
        self.shield_ply = np.full(MAX_PERMS, -1, np.int16)
        self.shield_amt = np.zeros(MAX_PERMS, np.int16)
        self.block_next_ply = np.full(MAX_PERMS, -1, np.int16)
        # 1 if some of the damage marked on this ROW was dealt by an opponent
        # of its controller. Elder Dragon's "any amount of YOUR damage is
        # enough to kill enemy units" is a continuous lethal rule, so it must
        # reach damage that was already on a unit when the Dragon arrived
        # (RiftJudge #12102) -- which means remembering whose damage it was.
        # Reset whenever damage is marked on an undamaged row, so a heal needs
        # no bookkeeping of its own.
        self.foe_dmg = np.zeros(MAX_PERMS, np.int8)
        # Renekton, Brute's "when my Might BECOMES 10 or more": -1 not yet seen
        # by `combat.scan_might_transitions`, else 0/1 for below/at-or-above
        # the threshold at the last scan. A state, not an event, is what a
        # plain ">= 10" check reads (RiftJudge #11768).
        self.might_hi = np.full(MAX_PERMS, -1, np.int8)
        self.double_dmg_ply = np.full(MAX_PERMS, -1, np.int16)
        self.banish_death_ply = np.full(MAX_PERMS, -1, np.int16)
        # +Might "this combat" (Fiora - Peerless): counts while the row is in
        # a combat during the stamped turn.
        self.combat_might_ply = np.full(MAX_PERMS, -1, np.int16)
        self.combat_might_val = np.zeros(MAX_PERMS, np.int16)

        # Zilean - Time Mage: "if you would play a token unit ... you may play
        # that token and an additional copy of it INSTEAD." A replacement whose
        # choice is offered once the resolving card has finished -- every
        # token-creating op in the pool is its card's last, which `effects.py`
        # asserts, so deferring the extra copy changes no ordering.
        # (source row, token card, location), or -1s for none pending. The
        # SEAT is not stored: it is the source's controller, and deriving it
        # keeps this array free of anything a seat swap would have to rewrite
        # except the location.
        self.pend_double = np.full(3, -1, np.int16)

        # Sabotage: "Choose an opponent. They reveal their hand. Choose a
        # non-unit card from it, and recycle that card." (chooser, revealer),
        # or -1s. The revealed hand is NOT copied anywhere -- the candidates
        # are hand indices read live, and the only lasting effect is the one
        # card that moves. What the chooser *remembers* of the rest is not
        # modelled; see the note on Scuttle Crab, which is pure information and
        # therefore needs the observation to change rather than the board.
        self.pend_reveal = np.full(2, -1, np.int16)
        # "You may pay 2 XP to CHOOSE a card from their hand" (Insightful
        # Investigator) -- 383.3.b's cost within instructions, priced on the
        # pick rather than on the ability. The reveal happens either way; only
        # the choice costs. 0 means the pick is free, which is what Sabotage
        # and Mindsplitter print.
        self.pend_reveal_xp = 0
        # Standing permission to see hidden information, as a TURN STAMP per
        # seat: `saw_hand[s] == turn` means seat s may read its opponent's
        # hand right now. A stamp rather than a flag, so nothing has to
        # remember to clear it at end of turn -- the same idiom `once_used`
        # and `kw_grant_turn` use.
        #
        # These are the only two things that widen what the POLICY may see.
        # Everything else the observation hides stays hidden, and the critic
        # is unaffected either way -- it already sees the whole state.
        self.saw_hand = np.full(N_SEATS, -1, np.int16)
        self.saw_fd = np.full(N_SEATS, -1, np.int16)

        # Which KINDS of card each seat has played this turn -- Swain asks for
        # "a non-token unit, a non-token gear, and a spell this turn", which
        # `cards_played` (a bare count) cannot answer. A bitmask of PT_*,
        # cleared alongside `cards_played` in the end-of-turn cleanup.
        #
        # Set at the moment the card is PLAYED (349), the same instant
        # `cards_played` moves, so a countered spell still counts -- it was
        # played.
        self.played_types = np.zeros(N_SEATS, np.int16)

        # Cull the Weak: "Each player kills one of their units." A sequential
        # per-seat choice like the Mulligan -- the seat currently choosing, or
        # -1. Each player picks from their OWN units, so there is no target
        # slot: the opponent chooses their own casualty, not the caster.
        self.pend_cull = -1

        # Shadow Watcher: "If a friendly unit died during YOUR Beginning Phase
        # this turn, I enter ready." Past tense and phase-scoped, so it cannot
        # be recomputed later -- by the time the card is played the phase is
        # over. Recorded when the death happens, cleared with the turn.
        self.died_in_beginning = np.zeros(N_SEATS, np.int8)

        # Imperial Decree: "When any unit takes damage this turn, kill it."
        # A turn-scoped modifier on what counts as lethal, affecting BOTH
        # players' units -- "any unit", not "any enemy unit". Cleared with the
        # turn like the other this-turn effects.
        # Which card TYPE the open "each player kills one of their [...]"
        # asks for, as an index into `config.CARD_TYPES`. 0 is Unit, which is
        # what Cull the Weak wants and what this used to be hardcoded to in
        # four separate places -- the resolve-time skip-ahead, the action
        # offer, `_has_cullable` and the pass-to-next-seat walk. Acceptable
        # Losses asks for Gear, and a hardcoded type in four places is the
        # shape that goes wrong on exactly the card that differs.
        self.pend_cull_type = 0
        # The per-player walk's shape. `pend_cull_first` is the seat it started
        # at (it ends on coming back round); `pend_cull_skip` a seat left out
        # ("each OTHER player", King's Edict) or -1; `pend_cull_mode` a CULL_*
        # from effects; `pend_cull_keep` the unit each seat chose to KEEP
        # (Cataclysmic Duel), per seat, or -1.
        self.pend_cull_first = -1
        # Whose spell or ability set this walk up. "Each player kills one of
        # their units" is still the SPELL's kill, so Immortal Phoenix sees it
        # (RiftJudge #10402).
        self.cull_spell_seat = -1
        self.pend_cull_skip = -1
        self.pend_cull_mode = 0
        self.pend_cull_keep = np.full(N_SEATS, -1, np.int16)
        self.any_damage_kills = 0

        # Hwei: "draw 1, then discard 1. Then, do the following based on the
        # discarded card's TYPE". `phases.discard` takes the oldest card and
        # says so in its docstring -- "the day a card says 'discard a card of
        # your choice' this becomes a decision point rather than a rule here".
        # This is that day, and Hwei is the reason: WHICH card you pitch is how
        # you pick which of the three modes you get, so taking the oldest would
        # not be a simplification, it would be choosing the card's mode for it.
        #
        # The seat choosing, or -1. `pend_discard_ops` holds the branch to run
        # once the type is known -- see `effects.DISCARD_BRANCHES`.
        # "Then you may do this: Choose a unit in their trash and play it"
        # (Kharox). A trash pick made DURING resolution rather than at
        # finalization, because the pile it reads was filled by an earlier op
        # of the same card -- Kharox burns three off the opponent's deck and
        # then digs in what he just buried.
        #
        # A target slot cannot express that: 355.8 chooses every target before
        # the card resolves, so a slot would read the trash as it stood BEFORE
        # the burn, and would refuse the play outright against an empty one.
        # Same reasoning as `pend_look` (355.10) -- it is a choice, not a
        # target, and the opponent cannot respond to it.
        #
        # `pend_grave` is the seat CHOOSING, `pend_grave_owner` whose trash is
        # being read; the two differ on every card that digs in an opponent's
        # pile. `pend_grave_dest` is a location, because a unit played this way
        # still needs somewhere to land (806.3).
        self.pend_grave = -1
        self.pend_grave_owner = -1
        self.pend_grave_dest = -1
        self.pend_discard = -1
        self.pend_discard_ops = -1
        # The permanent whose ability this is -- Hwei's Unit branch says
        # "give ME +3 Might", and by then resolution has returned.
        self.pend_discard_src = -1
        # The unit a DB_ENERGY_DAMAGE discard will hit (Get Excited!), a row.
        self.pend_discard_tgt = -1

        # Chained deferred decisions. A suspending op ("look at the top N",
        # "play a token", "reveal their hand") had to be its card's LAST,
        # because resolution returns at that point and anything after it would
        # run before the player had chosen. `pend_then` lifts that: it names a
        # FOLLOW-UP op list in `effects.FOLLOWUPS` to run once the decision
        # comes back, and those ops may suspend again -- which is what chains
        # them. Diana Predicts, then reveals; Guards! makes a token, then
        # offers to pay to ready it.
        #
        # (followup key, source permanent), or -1s. Ints only, so the state
        # digest and `clone` keep working -- the same rule the discard branch
        # key learned the hard way.
        self.pend_then = np.full(2, -1, np.int16)


        self.winner = -1
        self.truncated = False
        self.rng: np.random.Generator | None = None

    # ---- cloning ---------------------------------------------------------

    def clone(self) -> "GameState":
        s = GameState.__new__(GameState)
        for name in GameState.__slots__:
            v = getattr(self, name)
            setattr(s, name, v.copy() if isinstance(v, np.ndarray) else v)
        return s

    def state_hash(self) -> int:
        """Stable digest over everything that defines the position.

        Used to prove determinism: same seed twice must produce an identical
        hash trace. Excludes `rng`, which is an object, not state.

        **blake2b, not the builtin `hash()`.** Python salts the hashing of
        bytes per process (PYTHONHASHSEED), so `hash()` produced a value that
        was consistent *within* one run and meaningless across runs. Every
        comparison in the test suite happens inside a single process, so the
        determinism checks were sound -- but the printed number could not be
        recorded as a regression fingerprint, which is most of why you would
        want one. This digest can.
        """
        parts = []
        for name in GameState.__slots__:
            if name == "rng":
                continue
            v = getattr(self, name)
            # 8 bytes, not 4: `decl_mask` is a bitmask over MAX_PERMS rows.
            parts.append(v.tobytes() if isinstance(v, np.ndarray)
                         else int(v).to_bytes(8, "little", signed=True))
        return int.from_bytes(
            hashlib.blake2b(b"".join(parts), digest_size=8).digest(),
            "little", signed=True)

    # ---- the four states (rules 308-310) ---------------------------------

    @property
    def is_open(self) -> bool:
        """Open iff no Chain exists (309.2)."""
        return self.n_chain == 0

    @property
    def is_neutral(self) -> bool:
        """Neutral iff no Showdown or Combat is in progress (308.2)."""
        return self.showdown_bf < 0

    # ---- permanents ------------------------------------------------------

    def banish_card(self, seat: int, card: int) -> None:
        """Put a card into `seat`'s Banishment (108.6). Out of the game."""
        n = int(self.n_banished[seat])
        assert n < self.banished.shape[1], "banishment overflow"
        self.banished[seat, n] = card
        self.n_banished[seat] = n + 1
        self.banished_n[seat] += 1

    def unbanish(self, seat: int, card: int) -> bool:
        """Take one copy of `card` back out of `seat`'s Banishment.

        Banishment is "out of the game" (108.6) and almost nothing returns from
        it -- Jhin - Virtuoso is the card that does, and he names exactly the
        four he put there. False if it is not in there, which means something
        else moved it and the caller must not mint a copy.
        """
        n = int(self.n_banished[seat])
        for k in range(n):
            if int(self.banished[seat, k]) == card:
                self.banished[seat, k:n - 1] = self.banished[seat, k + 1:n]
                self.banished[seat, n - 1] = -1
                self.n_banished[seat] = n - 1
                return True
        return False

    def eff_card(self, perm: int) -> int:
        """The card whose printed characteristics row `perm` has: its own, or
        the one it is a copy of (while any Equipment granting that stays on)."""
        c = int(self.copy_of[perm])
        if c >= 0:
            via = int(self.copy_via[perm])
            if via == -1 or (via >= 0 and self.perms[via, P_ALIVE] == 1
                             and int(self.perms[via, P_ATTACHED_TO]) == perm):
                return c
        return int(self.perms[perm, P_CARD])

    def bf_present(self, i: int) -> bool:
        """Is battlefield slot `i` on the board? The chosen two always are."""
        return i < N_BF_BASE or int(self.bf_card[i]) >= 0

    def live_bfs(self) -> list[int]:
        return [i for i in range(N_BF) if self.bf_present(i)]

    def put_on_top(self, seat: int, card: int) -> None:
        """Put a card on TOP of `seat`'s Main Deck (Keeper's Verdict)."""
        ptr = int(self.deck_ptr[seat])
        if ptr > 0:
            self.deck[seat, ptr - 1] = card
            self.deck_ptr[seat] = ptr - 1
            return
        n = int(self.n_deck[seat])
        assert n < self.deck.shape[1], "main deck overflow putting a card on top"
        self.deck[seat, 1:n + 1] = self.deck[seat, 0:n].copy()
        self.deck[seat, 0] = card
        self.n_deck[seat] = n + 1

    def recycle_card(self, seat: int, card: int) -> None:
        """Put a card on the BOTTOM of `seat`'s Main Deck (416.1.a).

        **Three destinations, three different meanings** -- worth stating
        together because the words are easy to swap and only one of them is
        recoverable:

            trash      the discard pile. Still a zone cards come back FROM
                       ([Flow], "play a unit from your trash").
            recycle    bottom of the owner's own deck (416.1.a). Not removal at
                       all -- the card is live again the moment it is drawn.
            banish     the Banishment (108.6). Gone for the rest of the game;
                       what [Flow] does to a card it just played.

        Runes recycle to the RUNE Deck, not this one (416.1.b, 161.2.b) -- that
        is `recycle_rune`, deliberately a separate method, because they are
        separate zones and a rune in the Main Deck would be undrawable.

        416.1.c: each player recycles to their OWN Main Deck regardless of who
        was instructed to perform the Recycle, so `seat` is the card's owner and
        never the effect's controller.

        Tokens must not reach here: a token in any zone other than the board
        ceases to exist (186), so recycling one is plain removal. The check
        belongs at the call site, which is where the `CardTable` is.
        """
        n = int(self.n_deck[seat])
        if n >= self.deck.shape[1]:
            # The drawn prefix is dead space -- `deck_ptr` only ever moves
            # forward -- so reclaim it before calling the deck full. Without
            # this, a deck that recycles more than MAX_DECK minus its opening
            # size over a long game overflows while most of the array holds
            # cards that were drawn ten turns ago.
            ptr = int(self.deck_ptr[seat])
            assert ptr > 0, "main deck overflow with nothing drawn to reclaim"
            live = n - ptr
            self.deck[seat, :live] = self.deck[seat, ptr:n]
            self.deck[seat, live:] = -1
            self.n_deck[seat] = live
            self.deck_ptr[seat] = 0
            n = live
        self.deck[seat, n] = card
        self.n_deck[seat] = n + 1
        self.recycled_n[seat] += 1

    def compact_permanents(self) -> None:
        """Drop dead rows and renumber the live ones.

        `add_permanent` only appends, so without this `n_perms` counts every
        permanent the game has **ever had**, not the ones on the board. That is
        an unbounded growth tied to game length rather than to board size:
        measured over 250 real-deck games at victory 8, rows reached 47 against
        a peak of 19 live, and long games hit `MAX_PERMS overflow` while the
        board was nearly empty. Raising the cap only moves the failure further
        out, and every card that makes tokens moves it back in.

        **Row indices are stored outside `perms`** -- chain targets, an
        ability's `C_SRC`, and `decl_mask` are all row numbers -- so renumbering
        is only safe with no Chain, no open declaration and no Showdown. The
        end of a turn is the one moment all three hold, and the preconditions
        are asserted rather than trusted.
        """
        assert self.n_chain == 0, \
            "compacting with a live Chain would silently repoint its targets"
        assert self.n_trig == 0, \
            "compacting with queued triggers would repoint their sources"
        assert not self.declaring and self.decl_mask == 0, \
            "compacting mid-declaration would repoint decl_mask"
        assert self.showdown_bf < 0, "compacting during a Showdown"
        k = 0
        remap = {}
        for i in range(self.n_perms):
            if self.perms[i, P_ALIVE] == 1:
                remap[i] = k
                if k != i:
                    self.perms[k] = self.perms[i]
                    # Moved with the row, not left behind. See the note on
                    # `kw_grant`: these are parallel arrays and a row index is
                    # the only thing tying them together.
                    self.kw_grant[k] = self.kw_grant[i]
                    self.kw_grant_turn[k] = self.kw_grant_turn[i]
                    self.extra_buffs[k] = self.extra_buffs[i]
                    self.tag_grant[k] = self.tag_grant[i]
                    self.named[k] = self.named[i]
                    self.copy_of[k] = self.copy_of[i]
                    self.copy_via[k] = self.copy_via[i]
                    self.ctrl_link[k] = self.ctrl_link[i]
                    self.move_from[k] = self.move_from[i]
                    self.move_to[k] = self.move_to[i]
                    self.altar_ply[k] = self.altar_ply[i]
                    self.foe_dmg[k] = self.foe_dmg[i]
                    self.might_hi[k] = self.might_hi[i]
                k += 1
        self.perms[k:self.n_perms] = 0
        self.kw_grant[k:self.n_perms] = 0
        self.kw_grant_turn[k:self.n_perms] = 0
        self.extra_buffs[k:self.n_perms] = 0
        self.tag_grant[k:self.n_perms] = -1
        self.named[k:self.n_perms] = -1
        self.copy_of[k:self.n_perms] = -1
        self.copy_via[k:self.n_perms] = -1
        self.ctrl_link[k:self.n_perms] = -1
        self.move_from[k:self.n_perms] = -1
        self.move_to[k:self.n_perms] = -1
        self.foe_dmg[k:self.n_perms] = 0
        self.might_hi[k:self.n_perms] = -1
        self.n_perms = k
        # **`P_ATTACHED_TO` is a row index living INSIDE `perms`** -- the one
        # case the warning above does not cover, because it survives the move
        # rather than being stored elsewhere. Renumbering without remapping it
        # would silently re-point every Equipment at whatever now occupies its
        # old Top-Most card's row.
        #
        # A Top-Most card that died is not in `remap`, so its Equipment detaches
        # here. That agrees with 719.5, which detaches on the Top-Most leaving
        # the board -- `detach_all` does it at the moment of death, and this is
        # the backstop for anything that took a row out without going through it.
        for i in range(k):
            up = int(self.perms[i, P_ATTACHED_TO])
            if up >= 0:
                self.perms[i, P_ATTACHED_TO] = remap.get(up, -1)
            via = int(self.copy_via[i])
            if via >= 0:
                self.copy_via[i] = remap.get(via, -2)   # -2: its gear is gone
            lk = int(self.ctrl_link[i])
            if lk >= 0:
                self.ctrl_link[i] = remap.get(lk, -1)
        # Recomputed rather than adjusted: this loop both renumbers and DROPS
        # links (a Top-Most card that died is not in `remap`), and the rows
        # beyond `k` were zeroed to -1 above. Counting once here is cheaper
        # than reasoning about which of those changed the total.
        self.n_attached = int((self.perms[:k, P_ATTACHED_TO] >= 0).sum())

    def add_permanent(self, card: int, ctrl: int, loc: int,
                      ready: bool = True, is_unit: bool = True,
                      owner: int | None = None) -> int:
        if self.n_perms >= MAX_PERMS:
            raise BoardOverflow(
                f"MAX_PERMS overflow ({MAX_PERMS} rows). Rows are compacted at "
                f"end of turn, so this is more permanents in ONE turn than the "
                f"cap, not an accumulation across the game.")
        i = self.n_perms
        row = self.perms[i]
        row[P_CARD] = card
        row[P_CTRL] = ctrl
        # Defaults to the controller, which is right for every card played out
        # of its own owner's hand -- i.e. almost all of them. Only a card
        # played from a zone belonging to someone else has to say otherwise.
        row[P_OWNER] = ctrl if owner is None else owner
        row[P_LOC] = loc
        row[P_READY] = int(ready)
        row[P_DMG] = 0
        row[P_ALIVE] = 1
        row[P_ARRIVED] = self.ply
        row[P_FLAGS] = 0 if is_unit else F_NON_UNIT
        row[P_MIGHT_MOD] = 0
        # **-1, not 0.** `compact_permanents` clears freed rows with `= 0`, and
        # 0 is a perfectly good row index -- so a row that is not written here
        # reads as "Attached to row 0". Every other column has a zero that means
        # nothing; this one does not.
        row[P_ATTACHED_TO] = -1
        row[P_ATTACH_TURN] = -1
        # A reused row must not inherit the last occupant's grants.
        self.kw_grant[i] = 0
        self.kw_grant_turn[i] = 0
        self.might_hi[i] = -1
        self.n_perms = i + 1
        return i

    # ---- attachment (716-719, 818) --------------------------------------

    def attach(self, card_row: int, top: int) -> None:
        """Link `card_row` to `top` (434.1), which becomes its Top-Most Card.

        718.5.d allows only one Top-Most card at a time, so re-attaching an
        Equipment that is already attached simply moves it -- which is what
        [Weaponmaster] means by "even if it's already attached".

        719.3 puts the two at the same location, and this is where that starts
        holding: the Equipment is dragged to the unit rather than the unit to
        the Equipment. 149.2 normally pins gear to its controller's base, and
        attaching is the one thing that overrides it.
        """
        assert card_row != top, "a card cannot be attached to itself"
        assert self.perms[top, P_ALIVE] == 1, "attaching to a dead card"
        # 434.1.g -- "Attaching a card to its current Top-Most Card will not
        # have any effect", and 434.1.h adds that nothing additional happens
        # when an effect instructs it. So this does NOT restamp P_ATTACH_TURN:
        # re-equipping Brutalizer to the unit already wearing it must not renew
        # its "attached to me this turn" +2.
        if int(self.perms[card_row, P_ATTACHED_TO]) == top:
            return
        if int(self.perms[card_row, P_ATTACHED_TO]) < 0:
            self.n_attached += 1     # re-attaching an attached card is a MOVE
        self.perms[card_row, P_ATTACHED_TO] = top
        self.perms[card_row, P_ATTACH_TURN] = self.ply
        self.perms[card_row, P_LOC] = int(self.perms[top, P_LOC])

    def detach(self, card_row: int) -> None:
        """Unlink `card_row` from its Top-Most Card (718.1).

        The card stays exactly where it is, on the board and at the location it
        was dragged to -- 719.5 is explicit that detaching leaves it "in their
        current zones". Its printed Rules Text goes Active again the instant
        this runs, which is how a detached Spinning Axe starts killing itself
        at the next Beginning Phase.
        """
        if int(self.perms[card_row, P_ATTACHED_TO]) >= 0:
            self.n_attached -= 1
        self.perms[card_row, P_ATTACHED_TO] = -1

    def attachments(self, top: int) -> list[int]:
        """Live rows Attached to `top` (719). Empty when it is not Top-Most.

        **This is the hottest function in the engine when Equipment is on the
        board**, because every board walk that reads statics, keywords or
        abilities asks it once per row -- so a board scan is O(rows) calls of
        O(rows) work. Profiling a 40-game deck fuzz put the naive version at
        27% of total runtime, on boards that were mostly empty of Equipment.
        `n_attached` is what makes the common case free: no attachments
        anywhere means no row can be Attached to anything, and the scan is
        skipped outright rather than run and found empty.
        """
        if self.n_attached <= 0:
            return []
        return [i for i in range(self.n_perms)
                if self.perms[i, P_ALIVE] == 1
                and int(self.perms[i, P_ATTACHED_TO]) == top]

    def is_attached(self, perm: int) -> bool:
        """718 -- is this card linked to a Top-Most Card right now?

        The question 721/722 hang on: an Attached card's printed Rules Text is
        Inactive, so every walk that reads a permanent's statics or abilities
        has to ask this first.
        """
        return int(self.perms[perm, P_ATTACHED_TO]) >= 0

    def set_location(self, perm: int, loc: int) -> None:
        """Put `perm` at `loc`, dragging anything Attached to it (719.3.a).

        **Every write to `P_LOC` after a permanent enters goes through here.**
        719.3 says a Top-Most Card and its Attached cards are at the same
        location, and 719.3.a moves them together -- so a location write that
        skips this leaves an Equipment standing at a battlefield its unit has
        walked away from. There were six such writes before attachment existed
        (a move, two recalls, a retreat, `OP_MOVE_TO` and `OP_SWAP_LOC`), and
        patching six call sites one at a time is how the seventh gets missed.

        718.5.c is the same rule read from the other side: Attached cards
        cannot be moved SEPARATELY, so nothing should ever call this on one
        directly. It is not asserted, because `OP_SWAP_LOC`-style effects
        legitimately reach a row without knowing what it is, and silently
        dragging the pair is the right answer there too.
        """
        self.perms[perm, P_LOC] = loc
        for i in self.attachments(perm):
            self.perms[i, P_LOC] = loc

    def detach_all(self, top: int) -> list[int]:
        """719.5 -- everything Attached to `top` detaches as it leaves the board.

        Returns the rows that detached. They stay on the board: the rule moves
        only the Top-Most card to a non-board zone, and says the Attached cards
        remain "in their current zones". A killed unit therefore drops its
        Equipment on the floor rather than dragging it into the trash, which is
        what makes Equipment recoverable and is the whole reason a gear is a
        permanent in its own right instead of a modifier on a unit.

        719.5.a lets the controller choose the ORDER, which matters only once
        something in the pool triggers on Detaching. Nothing does yet, so this
        detaches in row order rather than opening a decision that has no
        consequence.
        """
        rows = self.attachments(top)
        for i in rows:
            self.detach(i)
        return rows

    def stun(self, perm: int) -> bool:
        """Apply Stun. Returns False if it was already Stunned (423.1.a.1).

        The return value is load-bearing: "when you stun an enemy unit" triggers
        (Eclipse Herald) must NOT fire on a redundant stun.
        """
        if self.perms[perm, P_FLAGS] & F_STUNNED:
            return False
        self.perms[perm, P_FLAGS] |= F_STUNNED | F_NO_COMBAT_DAMAGE
        return True

    def disempower(self, perm: int) -> bool:
        """441.2 -- take the Empowered status away. False if it had none.

        The exact inverse of what `OP_EMPOWER` sets, and it has to move BOTH
        halves: `P_EMPOWER` is the count and `F_EMPOWERED` the boolean seven
        other places read, and the flag is a floor on the count, so clearing
        one without the other leaves them disagreeing about whether the
        permanent is Empowered at all.

        The return value is load-bearing the same way `stun`'s is: Disempowering
        something that is not Empowered is a no-op, and a no-op must not be
        paid for as a cost.
        """
        if not self.empower_count(perm):
            return False
        self.perms[perm, P_EMPOWER] = max(
            0, int(self.perms[perm, P_EMPOWER]) - 1)
        if not int(self.perms[perm, P_EMPOWER]):
            self.clear_flag(perm, F_EMPOWERED)
        return True

    def src_empowered(self, src: int) -> bool:
        """Is this ABILITY SOURCE Empowered -- a permanent row or a legend?

        441 applies the status to any Game Object, and a legend is one: Zed -
        Master of Shadows, Mel and Ambessa all empower themselves and spend it
        again. A legend has no row, so its status lives in `legend_emp`, and
        every "[Empowered] >" gate reads through here rather than indexing
        `perms` with a sentinel (which is a valid index from the END of the
        array, and would answer about an unrelated unit).
        """
        if is_legend_src(src):
            return bool(int(self.legend_emp[legend_src_seat(src)]))
        return src >= 0 and bool(self.empower_count(src))

    def src_empower(self, src: int) -> bool:
        """Give the source the status. False if it already had it (441.1.b)."""
        seat = legend_src_seat(src)
        grew = not int(self.legend_emp[seat])
        self.legend_emp[seat] = 1
        return grew

    def src_disempower(self, src: int) -> bool:
        """Spend a legend's Empowered status (441.2). False if it had none."""
        seat = legend_src_seat(src)
        if not int(self.legend_emp[seat]):
            return False
        self.legend_emp[seat] = 0
        return True

    def empower_count(self, perm: int) -> int:
        """How many times `perm` is Empowered (827/828).

        **The flag is a floor on the count.** `F_EMPOWERED` is read in seven
        places as "Empowered at all", and `P_EMPOWER` was added later for the
        one card that scales off the number. Anything that sets the flag
        without the column -- a test fixture, a future effect that grants the
        status directly -- would otherwise read as Empowered by one measure and
        not by the other, and the activation gate would offer a second Empower
        on a permanent that already has it. Taking the max removes that whole
        class of disagreement instead of relying on every writer to update both.
        """
        n = int(self.perms[perm, P_EMPOWER])
        return max(n, 1 if self.has_flag(perm, F_EMPOWERED) else 0)

    def has_flag(self, perm: int, flag: int) -> bool:
        return bool(self.perms[perm, P_FLAGS] & flag)

    def set_flag(self, perm: int, flag: int) -> None:
        self.perms[perm, P_FLAGS] |= flag

    def clear_flag(self, perm: int, flag: int) -> None:
        self.perms[perm, P_FLAGS] &= ~flag

    def live(self) -> np.ndarray:
        """Boolean mask over permanent rows that are still on the board."""
        return self.perms[:self.n_perms, P_ALIVE] == 1

    def units_at(self, loc: int, seat: int | None = None) -> np.ndarray:
        """Indices of live **Units** at `loc`, optionally filtered by seat.

        Genuinely units, not permanents. It returned every permanent while
        every permanent was a unit, and the name was true by accident; Gear
        made it false. `seats_at` is built on this and decides Control (190.4)
        and whether a Combat happens, so a gear counted here would garrison a
        battlefield and defend it.
        """
        p = self.perms[:self.n_perms]
        m = ((p[:, P_ALIVE] == 1) & (p[:, P_LOC] == loc)
             & ((p[:, P_FLAGS] & F_NON_UNIT) == 0))
        if seat is not None:
            m &= p[:, P_CTRL] == seat
        return np.flatnonzero(m)

    def permanents_at(self, loc: int, seat: int | None = None) -> np.ndarray:
        """Indices of live permanents at `loc`, Units and Gear alike."""
        p = self.perms[:self.n_perms]
        m = (p[:, P_ALIVE] == 1) & (p[:, P_LOC] == loc)
        if seat is not None:
            m &= p[:, P_CTRL] == seat
        return np.flatnonzero(m)

    def has_units_at(self, loc: int, seat: int) -> bool:
        return self.units_at(loc, seat).size > 0

    def seats_at(self, loc: int) -> tuple[bool, bool]:
        """(seat 0 has units here, seat 1 has units here)."""
        return self.has_units_at(loc, 0), self.has_units_at(loc, 1)

    # ---- move declaration (PLAN.md §1.3.a) -------------------------------

    @property
    def declaring(self) -> bool:
        return self.decl_dst >= 0

    def declared(self) -> list[int]:
        """Permanent rows currently in the pending Move declaration."""
        m, out, i = self.decl_mask, [], 0
        while m:
            if m & 1:
                out.append(i)
            m >>= 1
            i += 1
        return out

    def clear_declaration(self) -> None:
        self.decl_dst = -1
        self.decl_mask = 0

    # ---- runes -----------------------------------------------------------

    def total_ready_runes(self, seat: int) -> int:
        return int(self.runes_ready[seat].sum())

    def runes_in_play(self, seat: int) -> np.ndarray:
        """Per-domain count of runes on the board, ready or exhausted.

        This is the pool Power draws from. Recycling has no ready requirement
        (164.2.b), so an exhausted rune is still a legal Power source -- which is
        why a card's rune requirement is max(energy, power), not the sum.
        """
        return self.runes_ready[seat] + self.runes_spent[seat]

    def channel_one(self, seat: int, ready: bool = True) -> int:
        """Pop the next rune from the Rune Deck, or -1 if it is empty.

        430.4.a's two-per-turn arrive READY. Almost every card that channels
        extra says "channel N runes EXHAUSTED" instead -- the rune joins the
        board but cannot be spent until it readies next turn, which is what
        stops those cards from being pure acceleration.
        """
        if self.rune_left[seat] <= 0:
            return -1
        h = int(self.rune_head[seat])
        dom = int(self.rune_deck[seat, h])
        self.rune_head[seat] = (h + 1) % RUNE_RING
        self.rune_left[seat] -= 1
        if ready:
            self.runes_ready[seat, dom] += 1
        else:
            self.runes_spent[seat, dom] += 1
        return dom

    def note_power_spent(self, seat: int, n: int) -> None:
        """Count Power paid this turn (every rune recycle is a payment)."""
        if n <= 0:
            return
        if int(self.power_spent_ply[seat]) != int(self.ply):
            self.power_spent_ply[seat] = int(self.ply)
            self.power_spent[seat] = 0
        self.power_spent[seat] = min(100, int(self.power_spent[seat]) + n)

    def recycle_rune(self, seat: int, domain: int) -> None:
        """Return a rune of `domain` to the bottom of the Rune Deck (416.1.b).

        Spends an exhausted rune first: exhausted runes are already used up this
        turn, so recycling one costs strictly less than recycling a ready one.
        """
        self.note_power_spent(seat, 1)
        self.rune_recycled_n[seat] += 1      # 416.1.b, and Sivir watches it
        if self.runes_spent[seat, domain] > 0:
            self.runes_spent[seat, domain] -= 1
        else:
            assert self.runes_ready[seat, domain] > 0, "no rune of that domain"
            self.runes_ready[seat, domain] -= 1
        assert self.rune_left[seat] < RUNE_RING, "rune ring overflow"
        tail = (int(self.rune_head[seat]) + int(self.rune_left[seat])) % RUNE_RING
        self.rune_deck[seat, tail] = domain
        self.rune_left[seat] += 1

    def clear_pools(self) -> None:
        self.pool_energy[:] = 0
        self.pool_rstr_e[:] = 0
        self.pool_rstr_p[:] = 0
        self.pool_power[:] = 0

    # ---- scoring ---------------------------------------------------------

    def check_winner(self, victory_score: int) -> int:
        """Winner at a cleanup, or -1 (rules 194.2, 194.2.a).

        A tie on points at or above the Victory Score is not a win -- play
        continues until one player has strictly more (194.2.b).
        """
        victory_score += int(self.victory_bonus)
        qualified = [s for s in range(N_SEATS) if self.points[s] >= victory_score]
        if not qualified:
            return -1
        best = max(int(self.points[s]) for s in qualified)
        leaders = [s for s in qualified if self.points[s] == best]
        return leaders[0] if len(leaders) == 1 else -1
