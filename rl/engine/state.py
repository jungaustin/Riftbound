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
N_BF = 2  # battlefields in play (rule 485.4); each player chose one

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


def legend_src(seat: int) -> int:
    """The ability-source encoding for `seat`'s Champion Legend."""
    return LEGEND_SRC0 - seat


def is_legend_src(src: int) -> bool:
    return LEGEND_SRC0 - N_SEATS < src <= LEGEND_SRC0


def legend_src_seat(src: int) -> int:
    return LEGEND_SRC0 - src


# Permanent columns. One int16 matrix so a clone is a single copy.
(P_CARD, P_CTRL, P_LOC, P_READY, P_DMG, P_ALIVE, P_ARRIVED, P_FLAGS,
 P_MIGHT_MOD) = range(9)
N_PERM_COLS = 9

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
TURN_SCOPED_FLAGS = F_STUNNED | F_NO_COMBAT_DAMAGE | F_NO_MOVE  # NOT F_NON_UNIT

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
    C_CTX, C_COST, C_DEST, C_SUBJ, C_REPEAT, C_CTX2 = range(14)
N_CHAIN_COLS = 14

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
MAX_TARGETS = 4

# Showdown steps (PLAN.md Phase 1.3).
SD_NONE, SD_PRIORITY, SD_DAMAGE, SD_CLEANUP = range(4)


class GameState:
    """Mutable game state. Treat every array as private to the engine."""

    __slots__ = (
        "perms", "n_perms",
        "hand", "n_hand", "deck", "deck_ptr", "n_deck", "trash", "n_trash",
        "runes_ready", "runes_spent", "rune_deck", "rune_head", "rune_left",
        "pool_energy", "pool_power",
        "bf_card", "bf_ctrl", "bf_contested", "bf_contester",
        "fd_owner", "fd_card", "fd_ply",
        "bf_scored",
        "banished", "n_banished",
        "chain", "n_chain", "chain_targets", "pend_slot", "chain_uid",
        "pend_may", "trig", "n_trig", "pend_order", "chain_from_trigger",
        "points", "burned_out", "no_spells", "cards_played", "xp",
        "kw_grant", "kw_grant_turn",
        "legend", "champion", "legend_ready", "pending_ready_runes",
        "turn", "ply", "active", "phase", "priority", "focus",
        "showdown_bf", "showdown_step", "showdown_combat",
        "attacker", "passes",
        "decl_dst", "decl_mask", "pend_play", "pend_play_seat",
        "pend_hide", "pend_mull", "mull_mask",
        "look_cards", "n_look", "pend_look",
        "look_pick_dest", "look_rest_dest", "look_optional",
        "look_type_mask", "death_guard",
        "once_used", "pend_double", "pend_reveal", "played_types",
        "saw_hand", "saw_fd",
        "pend_cull", "died_in_beginning", "any_damage_kills",
        "pend_discard", "pend_discard_ops", "pend_discard_src",
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
        self.fd_owner = np.full(N_BF, -1, np.int8)
        self.fd_card = np.full(N_BF, -1, np.int16)
        # 811.1.b: "Beginning on the NEXT turn, this gains [Reaction]". So a
        # card hidden this turn cannot be played this turn. `ply` is a
        # monotone count of turn transitions and `fd_ply` records the ply the
        # card was hidden at; it is live once `ply` has moved past it.
        #
        # A plain ply counter rather than (turn, active): the latter encodes a
        # seat, which would break the canonicalization test in mirror.py.
        self.fd_ply = np.full(N_BF, -1, np.int16)
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
        # [trigger kind, source permanent row, captured context int,
        #  subject permanent row, second captured context int,
        #  controlling seat or -1]
        #
        # The source is USUALLY a permanent row, and then the last column stays
        # -1 and the controller is read off that row. A BATTLEFIELD has no row
        # (see `bf_src`), so for one of those the seat has to be carried: "when
        # you conquer here" belongs to the conqueror, and by the time the queue
        # drains, `bf_ctrl` may already have moved on.
        self.trig = np.full((MAX_TRIGGERS, 6), -1, np.int16)
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
        self.no_spells = np.zeros(N_SEATS, np.int8)
        # Cards each seat has PLAYED this turn (349: played means finalized, or
        # resolved for a unit). [Legion] asks "have you played another card this
        # turn", and ten cards in the pool ask it. Reset in the Ending Phase
        # with the other turn-scoped state.
        self.cards_played = np.zeros(N_SEATS, np.int16)
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
        self.champion = np.full(N_SEATS, -1, np.int16)
        # A legend CAN be exhausted, which is the cost most of them charge
        # ("Exhaust: [Add] {1 energy}"), and 315.1.b readies "all Game Objects
        # they control that are able to be readied" -- so the Awaken Phase
        # readies it exactly as it readies a unit. Starts ready.
        self.legend_ready = np.ones(N_SEATS, np.int16)
        # "Ready 2 runes AT THE END OF THIS TURN" (Targon's Peak). A delayed
        # effect, and the only one in the whole pool -- one card of 937 -- so
        # it is a per-seat counter applied in `ending` rather than a general
        # delayed-trigger queue built for a single user. It is a real piece of
        # state either way: the runes are promised the moment the battlefield
        # is conquered, which is what makes tapping out that turn cheap
        # ([[riftbound-tapping-out-costs-the-opponents-turn]]).
        self.pending_ready_runes = np.zeros(N_SEATS, np.int16)

        self.turn = 1
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
        self.look_type_mask = 0    # 0 = any type; see LK_* above

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
        self.pend_discard = -1
        self.pend_discard_ops = -1
        # The permanent whose ability this is -- Hwei's Unit branch says
        # "give ME +3 Might", and by then resolution has returned.
        self.pend_discard_src = -1

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
        for i in range(self.n_perms):
            if self.perms[i, P_ALIVE] == 1:
                if k != i:
                    self.perms[k] = self.perms[i]
                    # Moved with the row, not left behind. See the note on
                    # `kw_grant`: these are parallel arrays and a row index is
                    # the only thing tying them together.
                    self.kw_grant[k] = self.kw_grant[i]
                    self.kw_grant_turn[k] = self.kw_grant_turn[i]
                k += 1
        self.perms[k:self.n_perms] = 0
        self.kw_grant[k:self.n_perms] = 0
        self.kw_grant_turn[k:self.n_perms] = 0
        self.n_perms = k

    def add_permanent(self, card: int, ctrl: int, loc: int,
                      ready: bool = True, is_unit: bool = True) -> int:
        assert self.n_perms < MAX_PERMS, (
            f"MAX_PERMS overflow ({MAX_PERMS} rows). Rows are compacted at "
            f"end of turn, so this is more permanents in ONE turn than the "
            f"cap, not an accumulation across the game.")
        i = self.n_perms
        row = self.perms[i]
        row[P_CARD] = card
        row[P_CTRL] = ctrl
        row[P_LOC] = loc
        row[P_READY] = int(ready)
        row[P_DMG] = 0
        row[P_ALIVE] = 1
        row[P_ARRIVED] = self.turn
        row[P_FLAGS] = 0 if is_unit else F_NON_UNIT
        row[P_MIGHT_MOD] = 0
        # A reused row must not inherit the last occupant's grants.
        self.kw_grant[i] = 0
        self.kw_grant_turn[i] = 0
        self.n_perms = i + 1
        return i

    def stun(self, perm: int) -> bool:
        """Apply Stun. Returns False if it was already Stunned (423.1.a.1).

        The return value is load-bearing: "when you stun an enemy unit" triggers
        (Eclipse Herald) must NOT fire on a redundant stun.
        """
        if self.perms[perm, P_FLAGS] & F_STUNNED:
            return False
        self.perms[perm, P_FLAGS] |= F_STUNNED | F_NO_COMBAT_DAMAGE
        return True

    def has_flag(self, perm: int, flag: int) -> bool:
        return bool(self.perms[perm, P_FLAGS] & flag)

    def set_flag(self, perm: int, flag: int) -> None:
        self.perms[perm, P_FLAGS] |= flag

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

    def recycle_rune(self, seat: int, domain: int) -> None:
        """Return a rune of `domain` to the bottom of the Rune Deck (416.1.b).

        Spends an exhausted rune first: exhausted runes are already used up this
        turn, so recycling one costs strictly less than recycling a ready one.
        """
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
        self.pool_power[:] = 0

    # ---- scoring ---------------------------------------------------------

    def check_winner(self, victory_score: int) -> int:
        """Winner at a cleanup, or -1 (rules 194.2, 194.2.a).

        A tie on points at or above the Victory Score is not a win -- play
        continues until one player has strictly more (194.2.b).
        """
        qualified = [s for s in range(N_SEATS) if self.points[s] >= victory_score]
        if not qualified:
            return -1
        best = max(int(self.points[s]) for s in qualified)
        leaders = [s for s in qualified if self.points[s] == best]
        return leaders[0] if len(leaders) == 1 else -1
