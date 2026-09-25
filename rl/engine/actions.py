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

from rl.config import ALL_KEYWORDS, CARD_TYPES, DOMAINS, Config
from rl.engine import chain, combat, phases
from rl.engine import resolve as rsv
# Payment lives in `cost` so combat can ask about affordability without
# importing the action layer. Re-exported: callers still say A.plan_payment.
from rl.engine.cost import (MULTI_DOMAIN_POWER_IS_PERMISSIVE, accelerate_cost, effective_energy,
                            pending_leftover,
                            flow_energy, repeat_cost, base_flow, flow_grant_index,
                            printed_add_cost,
                            ability_energy, card_domains, pay,
                            effective_power, pay_ability_cost,
                            plan_ability_cost, plan_flow, plan_payment,
                            plan_surcharge, plan_wild_power, pay_wild_power)
from rl.engine.cardtable import CardTable
from rl.engine.effects import (TOKEN_DOUBLERS, COND_NONE, PLAY_COST_NEEDS_SPELL, PLAY_COSTS_XP, DB_TO_DECK,
                               DB_ENERGY_DAMAGE, OP_DAMAGE, Op, TargetSpec, LOC_FREE,
                               Ability, TR_STUN, TR_SECOND_DRAW, TR_RECYCLED,
                               TR_RUNE_RECYCLED, TR_BANISHED, TR_PLAY_NONHAND,
                               appended_abilities,
                               NONHAND_ACCELERATE,
                               AMT_ENERGY_TO_ANY, AMT_ANY_TO_ENERGY, AMOUNT_CAP,
                               PLAY_COSTS_LEGEND, TRASH_TAG_DISCOUNT, TRASH_UNIT_PLAY, EQUIP_LESS_CHOSEN_MIGHT, OP_ATTACH, unpack_trash, TK_TRASH_CARD,
                               PLAY_COSTS_DISCARD, ADD_COST_REDUCERS,
                               CHOSEN_DISCOUNT, ENTERS_READY_AT_BF,
                               PAID_XP_DISCOUNT,
                               CULL_KILL_OWN, CULL_RETURN_ANY, CULL_KEEP_OWN,
                               CULL_MOVE_OWN_TO, KD_KILLED_COST, KD_POWER_EACH,
                               PAID_COST_ENTERS_READY, PLAY_ONLY_CONQUERED,
                               empower_limit,
                               play_from_look_cost,
                               row_abilities,
                               legend_abilities_for,
                               ABILITY_BORROWERS, CardSpec, FOLLOWUPS,
                               TR_DISCARD,
                               TR_GEAR_ABILITY,
                               DISCARD_BRANCHES,
                               ENTERS_READY_IF, ENTERS_EXHAUSTED,
                               ER_DIED_IN_BEGINNING, ER_ALWAYS, ER_ANOTHER_DRAGON,
                               SPEED_MAIN,
                               ER_TWO_OTHERS_AT_BASE, ER_LEVEL_3,
                               OP_EMPOWER, PERM_ENEMY, PERM_NONE,
                               PERM_ATTACK, PERM_OCCUPIED_ENEMY, PERM_ENEMY_ALONE, ST_PLAY_ENEMY_ALONE,
                               PERM_OPEN, PLAY_PERMISSIONS,
                               PLAY_TO_COST_KILL_LOC, TR_ACTIVATED,
                               TK_UNIT, TK_MODE, TR_CHOSEN,
                               TR_PLAY_ME, TR_PLAY_SPELL,
                               TR_PLAY_FROM_HIDDEN, TR_HIDE, abilities_for,
                               spec_for)

# Which target-slot kinds hold a PERMANENT ROW. TK_UNIT covers units and gear
# alike (a `card_type` on the spec narrows it); every other kind holds a
# location, a Chain uid, or a packed card id, none of which is a row.
_PERM_SLOT_KINDS = frozenset({TK_UNIT})
from rl.engine.state import (F_BUFFED, C_UID, C_PLAY_SPELL, C_SPENT_E, C_ABIL, C_BOUND_BF, C_CARD, C_CTRL, C_COST, C_CTX2, D_ANY, C_OWNER, P_ATTACHED_TO, P_OWNER,
                             C_COST_KILL, C_SUBJ,
                             F_EMPOWERED, F_FROM_HIDDEN, F_LEGION,
                             P_EMPOWER,
                             F_PAID_ADDITIONAL,
                             P_FLAGS,
                             PT_GEAR, PT_SPELL, PT_UNIT,
                             C_DEST, COST_FLOW, COST_NO_ENERGY, COST_FREE,
                             COST_PRINTED, DEST_BANISH, DEST_HAND,
                             C_REPEAT, DEST_TOP, LOOK_TYPE_BIT,
                             DEST_RECYCLE, DEST_TRASH,
                             C_SRC, MAIN, ENDING,
                             MAX_CHAIN, MAX_HAND, MAX_PERMS, MAX_TRIGGERS, N_BF,
                             N_DOMAINS, N_SEATS, P_ALIVE, P_CARD, P_CTRL,
                             P_LOC, P_READY, GameState, base_loc, bf_loc,
                             legend_src, legend_src_seat, is_legend_src,
                             fd_bf, fd_slots, N_FD,
                             is_battlefield)

# Action kinds. Wire format -- append only, never reorder.
# A_CANCEL is retained for wire-format stability (the enum is append-only
# and must never renumber) but is no longer offered -- see `legal_actions`.
(A_PASS, A_END_TURN, A_PLAY, A_PLAY_AT, A_DECLARE, A_ADD, A_COMMIT, A_CANCEL,
 A_RETREAT, A_TARGET, A_HIDE, A_HIDE_AT, A_PLAY_HIDDEN,
 A_ACCEPT, A_DECLINE, A_PLAY_AT_FAST, A_ORDER, A_ACTIVATE,
 A_PLAY_FLOW, A_MULLIGAN, A_MULLIGAN_DONE, A_PICK, A_PICK_NONE,
 A_PLAY_REPEAT, A_PLAY_BOTH) = range(25)

KIND_NAMES = ("pass", "end_turn", "play", "play_at", "declare", "add",
              "commit", "cancel", "retreat", "target", "hide", "hide_at",
              "play_hidden", "accept", "decline", "play_at_fast",
              "order", "activate", "play_flow", "mulligan",
              "mulligan_done", "pick", "pick_none", "play_repeat",
              "play_both")


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

def bf_paid_destination(state: GameState, table: CardTable, seat: int,
                        card: int) -> tuple[int, tuple[int, int]] | None:
    """A battlefield this card may be played to by paying the GROUND's cost.

    Dragon Roost: "any player may pay {any rune}{any rune} as an additional
    cost to play a Dragon. If they do, they play it to this battlefield." The
    cost and the destination are one decision, so this is a destination with a
    price rather than a second optional-cost offer -- and a Dragon that also
    prints [Accelerate] can still pay for that on top.

    Returns (location, (extra energy, extra power)), or None. The
    affordability check is here because the destination must not be offered at
    a price the player cannot pay: `_resolve_play` asserts it can.
    """
    from rl.engine.effects import BF_PLAY_COSTS
    for i in state.live_bfs():
        bcard = int(state.bf_card[i])
        if bcard < 0:
            continue
        rule = BF_PLAY_COSTS.get(table.names[bcard])
        if rule is None:
            continue
        if rule.get("tag") and rule["tag"] not in table.tags[card]:
            continue
        if not rule.get("any_player") and int(state.bf_ctrl[i]) != seat:
            continue
        extra = (int(rule.get("energy", 0)), int(rule.get("power", 0)))
        if plan_payment(state, table, seat, card, extra[0], extra[1]) is None:
            continue
        if combat.bf_forbids_play(state, table, bf_loc(i)):
            continue
        return bf_loc(i), extra
    return None


def play_destinations(state: GameState, table: CardTable, cfg: Config,
                      seat: int, card: int,
                      ambush_only: bool = False) -> list[int]:
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
    # Mageseeker Warden: "opponents can only play units to their base".
    if combat.base_only_plays(state, table, seat):
        return [] if ambush_only else [base_loc(seat)]
    # Perched Grimwyrm: "Play me only to a battlefield you conquered this turn.
    # (You can't play me anywhere else.)" -- replaces 806.3's set outright.
    if table.names[card] in PLAY_ONLY_CONQUERED:
        return [bf_loc(b) for b in state.live_bfs()
                if int(state.bf_conquered_ply[seat, b]) == int(state.ply)
                and not combat.bf_forbids_play(state, table, bf_loc(b))
                and not ambush_only]
    # 822.1.b/c -- [Ambush] "adds options to locations that are valid for a
    # Unit to be played to". A battlefield where you CONTROL UNITS, which is a
    # strictly wider set than one you control: a contested battlefield with a
    # unit of yours on it qualifies, and that is the whole card. Reinforcing a
    # fight you are losing is exactly what the keyword is for.
    ambush = [bf_loc(i) for i in state.live_bfs()
              if table.has(card, "Ambush")
              and state.units_at(bf_loc(i), seat).size]

    # Printed exceptions to 806.3, one per card -- see `effects.PLAY_PERMISSIONS`
    # for what "open" and "occupied" are taken to mean, since neither is a
    # defined rules term. These ADD destinations exactly as [Ambush] does; they
    # never remove the base.
    perm = PLAY_PERMISSIONS.get(table.names[card], PERM_NONE)
    # ...and the same exception granted by a PERMANENT instead of printed on
    # the card being played: Miss Fortune - Buccaneer's "Friendly units may be
    # played to open battlefields". The registry above is keyed by the played
    # card's name and can never see a grant from the board, so the two sources
    # are unioned rather than one replacing the other -- a unit that prints its
    # own permission and stands next to her keeps both.
    open_granted = (perm == PERM_OPEN
                    or combat.grants_open_play(state, table, seat))
    extra = []
    for i in state.live_bfs():
        loc = bf_loc(i)
        if open_granted and not state.seats_at(loc)[0] \
                and not state.seats_at(loc)[1]:
            extra.append(loc)
        elif perm == PERM_ENEMY and state.units_at(loc, 1 - seat).size:
            extra.append(loc)
        elif (perm == PERM_OCCUPIED_ENEMY and int(state.bf_ctrl[i]) == 1 - seat
              and any(state.seats_at(loc))):
            extra.append(loc)
        elif perm == PERM_ATTACK and int(state.showdown_bf) == i \
                and int(state.attacker) == seat:
            extra.append(loc)
        elif ((perm == PERM_ENEMY_ALONE
               or combat.grants_play_kind(state, table, seat,
                                          ST_PLAY_ENEMY_ALONE))
              and int(state.units_at(loc, 1 - seat).size) == 1):
            # Arachnoid Horror -- "an occupied battlefield if an enemy unit is
            # alone there": exactly one unit of the opponent's.
            extra.append(loc)

    # Stalking Wolf's "you may play me to ITS BATTLEFIELD" -- `state.
    # pend_kill_play_loc` was set the instant the cost_kill target died
    # (`_choose_unit_cost_kill_target`), so by the time this destination
    # choice opens the location is already known. Unconditional, unlike
    # [Ambush]'s destinations: the reminder text spells out that no ally
    # needs to already be there. Only a battlefield qualifies -- a unit
    # killed at a base grants nothing, matching "battlefield" over "location".
    if table.names[card] in PLAY_TO_COST_KILL_LOC:
        loc = int(state.pend_kill_play_loc)
        if loc >= 0 and is_battlefield(loc):
            extra.append(loc)

    # ...and a destination the GROUND sells (Dragon Roost). Offered to either
    # player, since the card says "any player", and only at a price they can
    # actually pay -- `_resolve_play` charges it when this location is chosen.
    paid = bf_paid_destination(state, table, seat, card)
    if paid is not None:
        extra.append(paid[0])

    if ambush_only:
        # The Reaction half of 822.1.b is conditional: "I have [Reaction] as
        # long as I'm being played to a battlefield where you control Units."
        # So a unit played in a response window may ONLY go to an Ambush
        # destination -- it has no timing permission to reach its own base.
        #
        # **A printed permission on a card that HAS Ambush widens that window
        # too.** 822.1.d: Ambush also appears as a verb, and "in such a case
        # the verb is taken to mean 'play with the permissions of the Ambush
        # keyword'" -- the rulebook's own worked example is Rengar, Trophy
        # Hunter, whose text "expands the normal permissions of the Ambush
        # keyword to include battlefields where there are enemy units". The
        # timing rides along with the destination, because it is one keyword
        # being widened rather than a separate grant.
        #
        # Gated on the card actually having Ambush, which is what keeps this
        # from handing Reaction speed to Ocean Drake and the two Scouts: their
        # permissions are ordinary 806.3 exceptions with no timing clause, so
        # they stay main-phase plays. Rengar is the only one of the four that
        # has the keyword.
        if not table.has(card, "Ambush"):
            return []
        # A printed permission widens 806.3; Rockfall Path narrows it, and it
        # narrows the widened set too. An [Ambush] unit is still a unit being
        # played there.
        return [loc for loc in sorted(set(ambush + extra))
                if not combat.bf_forbids_play(state, table, loc)]

    own = [bf_loc(i) for i in state.live_bfs() if int(state.bf_ctrl[i]) == seat]
    return [base_loc(seat)] + [
        loc for loc in sorted(set(own + ambush + extra))
        if not combat.bf_forbids_play(state, table, loc)]


def _permanent_enters_ready(state: GameState, table: CardTable, seat: int,
                           card: int, is_unit: bool) -> bool:
    """See `combat.permanent_enters_ready`; kept so call sites read the same."""
    return combat.permanent_enters_ready(state, table, seat, card, is_unit)


def _enters_ready(state: GameState, table: CardTable, seat: int,
                  card: int) -> bool:
    """See `combat.permanent_enters_ready` (the unit half)."""
    return combat.permanent_enters_ready(state, table, seat, card, True)


def _played_bits(table: CardTable, card: int) -> int:
    """See `combat.played_bits`."""
    return combat.played_bits(table, card)


# Heimerdinger - Inventor: "I have all Exhaust abilities of all friendly
# legends, units, and gear." An A_ACTIVATE has always been identified by its
# permanent alone, because `_activate` takes the FIRST activated ability and no
# card in the pool has two. Heimerdinger holds many at once, so the action has
# to say WHICH -- and a borrowed ability is identified by the permanent it came
# from.
#
# Packed rather than given a second Action field: `Action.arg` is wire format
# and every consumer reads it as one int. A plain row stays a plain row, so
# nothing that already exists changes meaning; only the borrowed case is
# encoded, and `arg >= MAX_PERMS` is the tag.
def pack_activate(perm: int, donor: int, k: int = 0) -> int:
    """(activating permanent, ability donor, ability index) -> one action arg.

    `k` indexes the permanent's activated abilities. It used to not exist,
    because the comment below `unpack_activate` asserted that "a permanent
    prints at most one activated ability" -- true of the pool as scripted, and
    false of the pool as printed. Legion Marauder's [Empower] prints two costs
    ("pay EITHER"), which 827.1.c.1 expands into two abilities; Tools of Empire
    prints an [Empower] and an Exhaust ability. `activatable` used to `break`
    after the first, so the second was simply unreachable -- a card on the
    board that could not do half of what it says.

    Encoded as a band ABOVE the legend band so that every arg that already had
    a meaning keeps it: k == 0 is the bare row it always was.
    """
    if donor != perm:
        assert k == 0, "a borrowed ability is selected by its Exhaust cost, " \
                       "not by index -- see `activatable`"
        return MAX_PERMS * (donor + 1) + perm
    if k == 0:
        return perm
    return PERM_ACT_K0 + (k - 1) * MAX_PERMS + perm


def recycle_cost_choices(state: GameState, table: CardTable, seat: int,
                         card_type: str = "") -> list[int]:
    """Trash indices `seat` may recycle to pay a "Recycle N from your trash"
    cost, identical cards collapsed.

    Collapsed because 108.2.c makes the trash unordered: two copies of the same
    card are interchangeable, and offering both widens the branching factor
    without adding a decision. `card_type` is Assembly Rig's "recycle a UNIT".
    Tokens never reach a trash (185.3), so there is nothing to exclude there.
    """
    seen: set[int] = set()
    out: list[int] = []
    for i in range(int(state.n_trash[seat])):
        c = int(state.trash[seat, i])
        if c in seen or (card_type and not table.is_type(c, card_type)):
            continue
        seen.add(c)
        out.append(i)
    return out


def _recycle_affordable(state: GameState, table: CardTable, seat: int,
                        n: int, card_type: str = "") -> bool:
    """Are there N cards (of `card_type`) in the trash to pay with?

    Counts COPIES, not the collapsed choices: three identical cards pay a
    recycle-3 cost even though they are one choice.
    """
    return sum(1 for i in range(int(state.n_trash[seat]))
               if not card_type
               or table.is_type(int(state.trash[seat, i]), card_type)) >= n


def pick_card(state: GameState, arg: int) -> int:
    """The card an `A_PICK` arg names right now, or -1 if nothing is pending.

    **`A_PICK` has five offer sites and its arg means something different at
    each**: an index into the payer's trash for a recycle COST, into a TRASH
    being dug (whoever owns it), into the look buffer, into
    the OPPONENT's hand, or into your own. `legal_actions` picks between them by
    which `pend_*` is live, and anything decoding the arg has to make the
    identical choice -- so it is made once, here, and the order below mirrors
    `legal_actions` exactly.

    This is the same failure `open_slot_kind` exists to prevent, and it landed
    a third time: the observation encoder knew about the look buffer and the
    reveal but not about Hwei's discard, so it read a hand index into a
    five-card look buffer. That is an IndexError when the hand is longer and a
    silently wrong card when it is shorter -- and the fuzz cannot see either,
    because it never builds an observation.
    """
    if arg < 0:
        return -1
    if state.pend_cost_recycle >= 0:
        payer = int(state.chain[int(state.pend_cost_recycle), C_CTRL])
        assert arg < int(state.n_trash[payer]), "pick arg past the trash"
        return int(state.trash[payer, arg])
    if state.pend_grave >= 0:
        owner = int(state.pend_grave_owner)
        assert arg < int(state.n_trash[owner]), "pick arg past the trash"
        return int(state.trash[owner, arg])
    if state.pend_look >= 0:
        assert arg < int(state.n_look), "pick arg past the look buffer"
        return int(state.look_cards[arg])
    if int(state.pend_reveal[0]) >= 0:
        foe = int(state.pend_reveal[1])
        assert arg < int(state.n_hand[foe]), "pick arg past the revealed hand"
        return int(state.hand[foe, arg])
    if state.pend_discard >= 0:
        who = int(state.pend_discard)
        assert arg < int(state.n_hand[who]), "pick arg past the discarding hand"
        return int(state.hand[who, arg])
    if state.pend_hand_play >= 0:
        who = int(state.pend_hand_play)
        assert arg < int(state.n_hand[who]), "pick arg past the playing hand"
        return int(state.hand[who, arg])
    if state.rp_seat >= 0 and state.rp_from_sarc and int(state.rp_card) < 0:
        return int(state.sarc_cards[int(state.rp_seat), arg])
    if state.dj_seat >= 0:
        s_ = int(state.dj_seat)
        if int(state.dj_cat) in (0, 1):
            return int(state.perms[arg, P_CARD])
        if int(state.dj_cat) == 3:
            return int(state.hand[s_, arg])
        return -1
    if state.pend_name >= 0:
        v = int(state.name_opts[arg])
        if int(state.name_kind) in (1, 2):
            return v                             # the spell / unit card itself
        return -1
    return -1


def unpack_activate(arg: int) -> tuple[int, int, int]:
    """The inverse. Returns (permanent, donor, ability index).

    `donor == permanent` for an ordinary activation. Never call this on a
    LEGEND activation -- ask `is_legend_activate` first. A legend's arg lives
    in its own band and decodes to an ability index, not to rows; run through
    here it would come back as two plausible-looking permanent indices.
    """
    assert not is_legend_activate(arg), (
        "a legend activation carries an ability index, not a (perm, donor) pair")
    if arg < MAX_PERMS:
        return arg, arg, 0
    if arg >= PERM_ACT_K0:
        rest = arg - PERM_ACT_K0
        perm = rest % MAX_PERMS
        return perm, perm, rest // MAX_PERMS + 1
    return arg % MAX_PERMS, arg // MAX_PERMS - 1, 0


# A legend activation reuses `A_ACTIVATE` because it IS one -- 151.2 makes no
# distinction, and giving it a second action kind would fork the whole
# targeting and finalization path for a source that behaves identically once it
# is on the Chain. The arg says which ability instead of which row: the legend
# is always the acting seat's own (107.4.d fixes it in place, so there is no
# choosing between legends).
#
# The band starts above every value the (perm, donor) pair can produce, which
# for donor == MAX_PERMS - 1 and perm == MAX_PERMS - 1 is
# MAX_PERMS*(MAX_PERMS+1)-1. It is CLOSED rather than open-ended, because the
# own-ability-index band sits above it.
LEGEND_ACT0 = MAX_PERMS * (MAX_PERMS + 1)
# A reserve rather than a measurement: the widest legend in the pool prints one
# activated ability, and sizing the band to that would make the next printing
# silently collide with a permanent's arg. `pack_legend_activate` asserts.
MAX_LEGEND_ACT = 8
# Own ability #k of a permanent, for k >= 1. See `pack_activate`.
PERM_ACT_K0 = LEGEND_ACT0 + MAX_LEGEND_ACT


def pack_legend_activate(k: int) -> int:
    """The k-th activated ability of the acting seat's own legend."""
    assert k < MAX_LEGEND_ACT, (
        f"legend ability index {k} is past the reserved band; raise "
        f"MAX_LEGEND_ACT (it sits below PERM_ACT_K0)")
    return LEGEND_ACT0 + k


def is_legend_activate(arg: int) -> bool:
    return LEGEND_ACT0 <= arg < PERM_ACT_K0


def legend_ability_index(arg: int) -> int:
    return arg - LEGEND_ACT0


def _look_type_bit(table: CardTable, card: int) -> int:
    """`LK_*` bit for a card's printed type, for a look's pick restriction."""
    bit = 0
    for name, b in LOOK_TYPE_BIT.items():
        if table.is_type(card, name):
            bit |= b
    return bit


def optional_add_cost(table: CardTable, card: int) -> tuple[int, int] | None:
    """The one optional additional cost a card may be played with, or None.

    [Accelerate] (805.1.a) and a printed "you may pay X as an additional cost"
    are the same kind of thing paid at the same moment, and `A_PLAY_AT_FAST`
    carries both. **No card in the pool prints both**, which the assert pins:
    if one ever does, the action space needs two offers rather than one and
    silently dropping the second would be a card that cannot be played as
    printed.
    """
    acc = accelerate_cost(table, card)
    printed = printed_add_cost(table, card)
    if table.names[card] in PLAY_COSTS_XP:
        # Paid in XP, so no runes on top -- a DISCOUNT when that is what it
        # buys (Poppy), which rides the same extra-cost argument negatively.
        printed = (-PAID_XP_DISCOUNT.get(table.names[card], 0), 0)
    if table.names[card] in PLAY_COSTS_DISCARD:
        printed = (-PLAY_COSTS_DISCARD[table.names[card]], 0)
    if table.names[card] in PLAY_COSTS_LEGEND:
        printed = (0, 0)
    assert acc is None or printed is None, (
        f"{table.names[card]!r} prints two optional additional costs; "
        f"A_PLAY_AT_FAST can only offer one")
    return acc if acc is not None else printed


def _hand_spell_actions(state: GameState, table: CardTable, cfg: Config,
                        seat: int) -> list[Action]:
    """A_PLAY / A_PLAY_REPEAT for the spells in hand -- the same offer in a
    Neutral Open and in a Closed window (a Showdown is where Syndra's granted
    [Repeat] lives)."""
    out: list[Action] = []
    for i in chain.playable_hand_indices(state, table, cfg, seat):
        _sc = spec_for(table, int(state.hand[seat, i]))
        if has_spell_opt_cost(_sc):
            _card = int(state.hand[seat, i])
            _plain, _paid = spell_opt_cost_options(state, table, seat,
                                                   _card, _sc)
            if _plain:
                out.append(Action(A_PLAY, i))
            if _paid:
                out.append(Action(A_PLAY_REPEAT, i))
            # A card can carry BOTH a printed optional additional cost and a
            # [Repeat]. Never on the same printed card (asserted in
            # `accelerate_or_play_cost`), but The Academy GRANTS one: "give your
            # next spell this turn [Repeat] equal to its base cost". 820.1.c.1
            # makes them two additional costs of the same play, so paying both
            # is a FOURTH option rather than a choice between them -- Meditation
            # under The Academy draws 2 + 1 (RiftJudge #10271) and Call to
            # Glory's spent buff does not buy off the Repeat's own {3 energy}
            # (RiftJudge #10272).
            if _paid:
                _re, _rp = _repeat_extra(state, table, seat, _card)
                _rp += int(_sc.opt_cost_power)
                # Paying the optional cost may itself buy off the card's own
                # cost (Call to Glory), in which case only the additional costs
                # have to be affordable.
                _plan = (plan_ability_cost if _sc.paid_ignores_cost
                         else plan_payment)
                if _re >= 0 and _plan(state, table, seat, _card,
                                      _re, _rp) is not None:
                    out.append(Action(A_PLAY_BOTH, i))
            continue
        out.append(Action(A_PLAY, i))
        # 820.1.c.1 -- [Repeat] is an Additional Cost paid "during the steps of
        # playing", so whether to pay it belongs to THIS decision, exactly as
        # [Accelerate] belongs to the destination choice above. Offered only
        # when the base cost plus the Repeat cost are affordable together:
        # `plan_payment`'s extra_* arguments share the overlapping-pool rule,
        # so this is max(e, p) over the combined cost, not two payments.
        card = int(state.hand[seat, i])
        re_e, re_p = _repeat_extra(state, table, seat, card)
        if re_e >= 0 and plan_payment(
                state, table, seat, card, re_e, re_p) is not None:
            out.append(Action(A_PLAY_REPEAT, i))
    return out


def _repeat_extra(state: GameState, table: CardTable, seat: int,
                  card: int) -> tuple[int, int]:
    """The (energy, power) a paid [Repeat] would ADD to this play, with
    discounts and already-banked leftovers applied -- or (-1, -1) when the
    card has no [Repeat] available to it right now."""
    re_e, re_p = repeat_cost(state, table, seat, card)
    if re_e < 0:
        return -1, -1
    re_e, re_p = reduced_add_cost(state, table, seat, (re_e, re_p))
    _le, _lp = pending_leftover(state, table, seat, card)
    return max(0, re_e - _le), max(0, re_p - _lp)


def has_spell_opt_cost(spec) -> bool:
    """Does this spell print an optional additional cost (A_PLAY_REPEAT)?"""
    return spec is not None and bool(
        (spec.cost_kill is not None and spec.cost_kill_optional)
        or spec.opt_cost_discard or spec.opt_cost_power or spec.opt_cost_xp)


def spell_opt_cost_options(state: GameState, table: CardTable, seat: int,
                           card: int, spec) -> tuple[bool, bool]:
    """(may play without paying, may play paying) for such a spell."""
    castable = rsv.can_be_cast(state, table, spec, seat, -1, card=card)
    plain = castable and plan_payment(state, table, seat, card) is not None
    paid = castable
    if spec.paid_targets:
        paid = rsv.can_be_cast(state, table,
                               spec._replace(targets=spec.paid_targets),
                               seat, -1, card=card)
    if spec.opt_cost_xp and int(state.xp[seat]) < spec.opt_cost_xp:
        paid = False
    if spec.cost_kill is not None and not rsv.cost_kill_targets(
            state, table, spec, seat):
        paid = False
    if spec.opt_cost_discard and int(state.n_hand[seat]) - 1 < spec.opt_cost_discard:
        paid = False
    if paid and not spec.paid_ignores_cost:
        e, p = reduced_add_cost(state, table, seat, (0, spec.opt_cost_power))
        paid = plan_payment(state, table, seat, card, e, p) is not None
    return plain, paid


def reduced_add_cost(state: GameState, table: CardTable, seat: int,
                     cost: tuple[int, int]) -> tuple[int, int]:
    """Ezreal, Prodigy -- each copy takes {1 energy} or {any rune} off an
    optional additional cost (Energy first; Power when there is no Energy)."""
    e, p = cost
    for i in range(state.n_perms):
        if (state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == seat
                and table.names[int(state.perms[i, P_CARD])] in ADD_COST_REDUCERS):
            if e > 0:
                e -= 1
            elif p > 0:
                p -= 1
    # Marai Spire: "while you control this battlefield, friendly [Repeat]
    # costs cost {1 energy} less" -- the same shape from the ground.
    from rl.engine.cost import repeat_discount
    for amount, _floor in repeat_discount(state, table, seat):
        e = max(0, e - amount)
    return e, p


def _main_open(state: GameState, seat: int) -> bool:
    """Is this the ordinary main-phase window a unit is normally played in?"""
    return (state.phase == MAIN and seat == state.active
            and state.n_chain == 0 and state.showdown_bf < 0)


_PRINTED_SPEED: dict[int, int] = {}


def printed_permanent_speed(table: CardTable, card: int) -> int:
    """SPEED_* a unit or gear's own printed [Reaction]/[Action] grants, or -1.

    Read from the keyword with its reminder text ("[Reaction] (Play any
    time..."), because that is the card-level keyword. "[Reaction][>]" on the
    same card is an ABILITY's speed (Dragonsoul Sage), not permission to play
    the card at that speed.
    """
    got = _PRINTED_SPEED.get(card)
    if got is None:
        import re
        from rl.engine.effects import SPEED_ACTION, SPEED_REACTION
        text = table.raw_text[card]
        got = (SPEED_REACTION if re.search(r"\[Reaction\] \(Play", text)
               else SPEED_ACTION if re.search(r"\[Action\] \(Play", text)
               else -1)
        _PRINTED_SPEED[card] = got
    return got


def fast_permanents_playable(state: GameState, table: CardTable, cfg: Config,
                             seat: int) -> list[int]:
    """Hand indices of units/gear whose PRINTED [Reaction] or [Action] lets
    them be played into the current response window (813.3.a, 806.1.b).

    Janna - Savior, Rengar - Pouncing, Shen - Kinkou and Sumpworks Map. Only
    [Ambush] units were ever offered here, so a Janna in hand could not answer
    anything -- the one thing she is printed to do (RiftJudge #11239, #11312).
    Their destinations are the ordinary ones (base, a battlefield you control,
    and any printed permission); the keyword changes when, not where.
    """
    if cfg.units_only or state.no_cards[seat]:
        return []
    out = []
    # 3 champion cards print [Reaction]; 108.3.d plays them "as normal", so the
    # keyword still decides when and the Champion Zone only decides from where.
    for i in _hand_choices(state, seat) + champion_source(state, table, cfg, seat):
        card = played_card(state, seat, i)
        if not (table.is_type(card, "Unit") or table.is_type(card, "Gear")):
            continue
        speed = printed_permanent_speed(table, card)
        if speed < 0 or table.has(card, "Ambush"):
            continue
        if not chain.speed_ok(state, cfg, seat, speed):
            continue
        if not play_destinations(state, table, cfg, seat, card):
            continue
        if plan_payment(state, table, seat, card) is None:
            continue
        out.append(i)
    return out


def ambush_playable(state: GameState, table: CardTable, cfg: Config,
                    seat: int) -> list[int]:
    """Hand indices of [Ambush] units playable into the current window.

    Affordability and a legal destination are both required: 822.1.b grants
    Reaction speed only "as long as I'm being played to a battlefield where you
    control Units", so with no such battlefield there is no permission and the
    card is simply not offered.
    """
    if cfg.units_only:
        return []
    out = []
    # 7 of the champion cards print [Ambush], and 822.1.b's permission is about
    # the card being played, not about where it is played FROM.
    for i in _hand_choices(state, seat) + champion_source(state, table, cfg, seat):
        card = played_card(state, seat, i)
        if not table.has(card, "Ambush") or not table.is_type(card, "Unit"):
            continue
        spec = spec_for(table, card)
        if (spec is not None and spec.cost_kill is not None
                and not spec.cost_kill_optional):
            # 820 -- an unpayable REQUIRED cost is the same deadlock this
            # function already refuses for a missing destination.
            if not rsv.can_play_with_cost_kill(state, table, spec, seat):
                continue
            # `play_destinations` reads `pend_kill_play_loc`, which is only
            # ever set WHILE this exact play's cost is being paid -- it is
            # -1 here, since no pend_play/pend_kill_play decision can be open
            # at the same time `legal_actions` reaches this function. So a
            # card whose ONLY destination comes from `PLAY_TO_COST_KILL_LOC`
            # (Stalking Wolf, with no ally already at any battlefield) needs
            # a HYPOTHETICAL check instead: does killing SOME legal target
            # open a battlefield destination? Real ambush destinations (ally
            # presence) still count too, via the ordinary call below.
            dynamic = table.names[card] in PLAY_TO_COST_KILL_LOC and any(
                is_battlefield(int(state.perms[p, P_LOC]))
                for p in rsv.cost_kill_targets(state, table, spec, seat))
            if not dynamic and not play_destinations(
                    state, table, cfg, seat, card, ambush_only=True):
                continue
        elif not play_destinations(state, table, cfg, seat, card,
                                   ambush_only=True):
            continue
        if plan_payment(state, table, seat, card) is None:
            continue
        out.append(i)
    return out


def activatable(state: GameState, table: CardTable, cfg: Config,
                seat: int) -> list[int]:
    """Permanent rows whose activated ability `seat` may use right now (151)."""
    if cfg.units_only:
        return []
    out: list[int] = []
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or int(row[P_CTRL]) != seat:
            continue
        card = state.eff_card(i)
        # Enumerated, not first-match: a permanent may print more than one
        # activated ability and they are genuinely different choices --
        # Legion Marauder's two [Empower] costs are the card's whole decision.
        # 721.2 -- an Inactive ability "cannot be activated". That the
        # reading is right is confirmed by [Weaponmaster], which exists to
        # re-attach an Equipment "even if it's already attached" (821.1.b):
        # the keyword would be pointless if the card's own [Equip] were
        # still available to it while Attached.
        _own = abilities_for(table, card) if not state.is_attached(i) else ()
        _app = appended_abilities(state, table, i)
        for k, ab in enumerate(row_abilities(state, table, i)):
            if ab.trigger != TR_ACTIVATED:
                continue
            # An appended ability (Dominus's grant) is costed off its own card.
            acard = card if k < len(_own) else int(_app[k - len(_own)][0])
            if not chain.speed_ok(state, cfg, seat, ab.speed):
                continue
            if ab.cost_exhaust and not row[P_READY]:
                continue
            if ab.unattached_only and state.is_attached(i):
                continue
            # 441.2 -- "Disempower this, Exhaust: ...". You cannot spend a
            # status you do not hold, so the ability is not offered at all
            # until the permanent has been Empowered. That is what makes these
            # four cards a cycle rather than a repeatable engine: the status
            # has to be bought back through [Empower] between uses.
            if ab.cost_disempower_self and not state.empower_count(i):
                continue
            # "Spend my buff" -- same shape: no Buff, nothing to spend.
            if ab.cost_spend_buff_self and not state.has_flag(i, F_BUFFED):
                continue
            if ab.cost_discard and _discard_cost_rows(
                    state, table, seat, ab) is None:
                continue
            # "Use only if you've chosen an enemy unit this turn and only once
            # each turn" (Hungry Wolf).
            if ab.once_each_turn and int(state.once_used[i]) == int(state.ply):
                continue
            if ab.cond != COND_NONE and not chain.ability_cond_holds(
                    state, table, ab, seat, i, int(row[P_LOC])):
                continue
            if ab.cost_xp and int(state.xp[seat]) < ab.cost_xp:
                continue
            # "[Level N] ... Use this ability only while you have N+ XP."
            if ab.min_xp and int(state.xp[seat]) < ab.min_xp:
                continue
            if ab.use_at_battlefield and not is_battlefield(int(row[P_LOC])):
                continue
            # 3956 -- a recycle cost needs the cards to be there. Unpayable
            # means not activatable, or the ability would reach the Chain and
            # sit on `pend_cost_recycle` with nothing left to choose.
            if ab.cost_recycle_trash and not _recycle_affordable(
                    state, table, seat, ab.cost_recycle_trash,
                    ab.cost_recycle_type):
                continue
            # 827.1.c.1 -- "[Cost]: Empower this. Play only if not Empowered."
            # The restriction is part of what the keyword abbreviates, so it is
            # read off the op rather than written on each of the ~35 cards that
            # print it. 441.1.b says the same thing from the other side: an
            # Empowered object cannot be Empowered.
            # 827.1.c.1 -- "use only if not Empowered", read off the op
            # rather than written on each of the ~35 cards that print it.
            # Kayle, Justified raises the cap to three and omits the
            # restriction from her reminder text, so the limit is a card
            # property and the COUNT is what it is checked against.
            if (any(op.op == OP_EMPOWER for op in ab.ops)
                    and state.empower_count(i) >= empower_limit(table, card)):
                continue
            # 820 -- an unpayable REQUIRED cost means the ability is not
            # activatable at all, the same rule `ambush_playable` applies to a
            # card that prints one. Without this the ability would reach the
            # Chain and then sit on `pend_cost_kill` with nothing to choose.
            if (ab.cost_kill is not None
                    and not rsv.cost_kill_targets(state, table, ab, seat, -1)):
                continue
            state.empower_src = i        # Risen Altar asks where it stands
            _plan = plan_ability_cost(state, table, seat, acard,
                                      ability_energy(state, table, seat, acard,
                                                     ab.cost_energy, ab),
                                      ab.cost_power)
            state.empower_src = -1
            if _plan is None:
                continue
            # 355.8, same as for a card: no legal targets, no activation.
            if ab.n_targets and not rsv.can_be_cast(state, table, ab, seat,
                                                    -1, i, card):
                continue
            out.append(pack_activate(i, i, k))

    # Heimerdinger - Inventor: "I have all Exhaust abilities of all friendly
    # legends, units, and gear." He HAS them, so the ability is his: the
    # Exhaust cost taps HIM, not the donor, and the donor's own readiness is
    # irrelevant. That is the whole card -- one exhaust reused across the board.
    for i in range(state.n_perms):
        if (state.perms[i, P_ALIVE] != 1
                or int(state.perms[i, P_CTRL]) != seat
                or table.names[int(state.perms[i, P_CARD])] not in ABILITY_BORROWERS
                or not state.perms[i, P_READY]):
            continue
        for d in range(state.n_perms):
            if d == i or state.perms[d, P_ALIVE] != 1:
                continue
            if int(state.perms[d, P_CTRL]) != seat:
                continue
            dcard = int(state.perms[d, P_CARD])
            # ...and an Attached donor lends nothing, for the same reason.
            for ab in row_abilities(state, table, d):
                if ab.trigger != TR_ACTIVATED or not ab.cost_exhaust:
                    continue
                # "Use my abilities only while I'm at a battlefield" is a
                # SEPARATE clause of the donor's text, not part of the ability
                # he has (FAQ 650/9851, RiftJudge #12424) -- so it travels with
                # neither of them: Heimerdinger uses Renata's exhaust ability
                # from his base, whether or not she is standing on one. It used
                # to be re-read as "while I'M at a battlefield", which made the
                # borrowed copy unusable exactly where the card is played.
                if not chain.speed_ok(state, cfg, seat, ab.speed):
                    continue
                if ab.cost_xp and int(state.xp[seat]) < ab.cost_xp:
                    continue
                # A borrowed [Empower] would Empower HEIMERDINGER, so the
                # once-only check reads his status, not the donor's.
                if (any(op.op == OP_EMPOWER for op in ab.ops)
                        and state.has_flag(i, F_EMPOWERED)):
                    continue
                if plan_ability_cost(state, table, seat, dcard,
                                     ability_energy(state, table, seat, dcard,
                                                    ab.cost_energy, ab),
                                     ab.cost_power) is None:
                    continue
                if ab.n_targets and not rsv.can_be_cast(state, table, ab, seat,
                                                        -1, i, dcard):
                    continue
                out.append(pack_activate(i, d))
                break

    # The Champion Legend. Every ability is offered by INDEX rather than
    # first-match, because a legend may print several and they are genuinely
    # different choices (Kha'Zix charges 1 XP for one and 2 for another).
    lcard = int(state.legend[seat])
    if lcard >= 0:
        from rl.engine.effects import legend_abilities_live
        for k, (_lc, _ki, ab) in enumerate(
                legend_abilities_live(state, table, seat)):
            if ab.trigger != TR_ACTIVATED:
                continue
            if not chain.speed_ok(state, cfg, seat, ab.speed):
                continue
            # The legend exhausts itself to pay, and 315.1.b readies it each
            # Awaken -- so this is a once-per-turn gate, not a once-per-game.
            if ab.cost_exhaust and not state.legend_ready[seat]:
                continue
            if ab.cost_xp and int(state.xp[seat]) < ab.cost_xp:
                continue
            # 441.2 -- "Disempower me, ...": a status the legend does not hold
            # is an unpayable cost, so the ability is not offered at all.
            if ab.cost_disempower_self and not state.src_empowered(
                    legend_src(seat)):
                continue
            # 827.1.c.1 -- "[Empower] ... use only if not Empowered".
            if (any(op.op == OP_EMPOWER for op in ab.ops)
                    and state.src_empowered(legend_src(seat))):
                continue
            # "[Level N] >" and the rest of the ability conditions, asked with
            # the legend as the source so "[Empowered] >" reads `legend_emp`.
            if ab.cond != COND_NONE and not chain.ability_cond_holds(
                    state, table, ab, seat, legend_src(seat)):
                continue
            if ab.min_xp and int(state.xp[seat]) < ab.min_xp:
                continue
            if plan_ability_cost(state, table, seat, _lc,
                                 ability_energy(state, table, seat, _lc,
                                                ab.cost_energy, ab),
                                 ab.cost_power) is None:
                continue
            if ab.n_targets and not rsv.can_be_cast(state, table, ab, seat, -1,
                                                    legend_src(seat), _lc):
                continue
            out.append(pack_legend_activate(k))
    return out


# 108.3.d -- "The Chosen Champion can be played from here as normal, following
# the rules of Playing a Card." A second SOURCE ZONE for a play, not a second
# kind of play: the cost, the timing, the destination choice, [Accelerate] and
# every trigger behave exactly as they do from hand.
#
# Modelled as an out-of-range hand index rather than a new action kind, because
# "as normal" means it must flow through the SAME code -- `_resolve_play`,
# `play_destinations`, `plan_payment`, `permanent_play_allowed`. A separate
# action kind would have meant a parallel play path, and the way those drift is
# exactly what `_resolve_play_from_hidden` had to be written around.
#
# `MAX_HAND` is safe as the sentinel: a real index is always < `n_hand`, and
# `n_hand` can never exceed `MAX_HAND`.
CHAMPION_SRC = MAX_HAND


def played_card(state: GameState, seat: int, idx: int) -> int:
    """The card a play index names, in hand or in the Champion Zone."""
    if idx == CHAMPION_SRC:
        return int(state.champion[seat])
    return int(state.hand[seat, idx])


def _take_played_card(state: GameState, seat: int, idx: int) -> None:
    """Remove a card that is being played from whichever zone it came from.

    108.3.c keeps it from coming back: the Champion Zone is emptied and only
    108.3.c.1 (an explicit instruction, into an empty zone) can refill it.
    """
    if idx == CHAMPION_SRC:
        state.champion[seat] = -1
        return
    n = int(state.n_hand[seat])
    state.hand[seat, idx:n - 1] = state.hand[seat, idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1


def champion_source(state: GameState, table: CardTable, cfg: Config,
                    seat: int) -> list[int]:
    """`[CHAMPION_SRC]` when this seat has a Chosen Champion still in its zone.

    Every Chosen Champion in the pool is a Unit (161 champion cards; the nine
    that also report "Legend" are Legend cards, which 103.2 keeps out of the
    Main Deck and so out of this slot). So the champion only ever needs the
    unit/gear play paths, never the spell Chain -- which is why this returns an
    index list to fold into those loops rather than duplicating them.
    """
    card = int(state.champion[seat])
    # **Not gated on `cfg.units_only`.** The two reaction-speed callers below
    # bail on that flag before they ever reach here, because Reaction windows
    # are a v1 thing -- but a champion is a UNIT, and units are precisely what
    # `units_only` allows. Copying that guard in here made the champion
    # unplayable in the v0 curriculum, and the corpus decks it matters for are
    # exactly the ones a v0 run trains on.
    if card < 0 or state.no_cards[seat]:
        return []
    return [CHAMPION_SRC]


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

    # --- 117: the Mulligan, before the first turn -------------------------
    # In turn order, and it is the first decision either player makes -- so it
    # is checked before every other pending state rather than after.
    if state.pend_mull >= 0:
        if seat != int(state.pend_mull):
            return []
        out = []
        if bin(int(state.mull_mask)).count("1") < phases.MULLIGAN_MAX:
            out += [Action(A_MULLIGAN, i)
                    for i in range(int(state.n_hand[seat]))
                    if not (int(state.mull_mask) >> i & 1)]
        # 117.1 is "UP TO two", so stopping is always legal -- including
        # immediately, which is the choice to keep the opening hand.
        out.append(Action(A_MULLIGAN_DONE))
        return out

    # --- mid-damage: who dies to combat damage (465.2.c.2) ----------------
    # The assigning player chooses, one kill at a time, from the lowest
    # ordering tier that still holds a live target -- which is what makes
    # `[Tank]` and `[Backline]` mean anything. Only opened when the pool cannot
    # cover every target: with enough damage to wipe the board there is nothing
    # to decide and `combat.damage_step` never suspends.
    #
    # `A_PICK_NONE` stops early, and it is not a formality: killing a unit can
    # be actively bad when its death is what its controller wants (a
    # [Deathknell] payoff, a death trigger that draws). Declining leaves the
    # rest of the pool unspent, which costs nothing -- non-lethal damage heals
    # at the Resolution Step anyway.
    if state.pend_dmg >= 0:
        if seat != int(state.pend_dmg):
            return []
        out = [Action(A_PICK, i)
               for i in combat.dmg_legal_kills(state, table, seat)]
        assert out, "an assignment with no affordable target should not open"
        return out + [Action(A_PICK_NONE)]

    # --- mid-death: Altar of Blood offers to buy a death back -------------
    # 136.2.d -- a replacement is applied INSTEAD of the event, so this is
    # asked before the unit dies and not after. The sweep that was killing it
    # is stopped (`combat.enforce_lethal`, `combat.advance_combat`), which is
    # what makes "would die" answerable at all.
    if state.pend_altar >= 0:
        if seat != int(state.perms[int(state.pend_altar), P_CTRL]):
            return []
        return [Action(A_ACCEPT), Action(A_DECLINE)]

    # --- mid-decision: a printed additional-cost kill target is open ------
    # 820 -- chosen (and, at finalization, paid) before the card's own effect
    # targets. `chain.playable_hand_indices` already proved SOME legal choice
    # here leads to a fully playable card; `choosable_cost_kill_targets` is
    # what keeps the player from then picking a DIFFERENT one that deadlocks
    # a later slot (Heedless Resurrection's trash unit is capped by whichever
    # permanent pays this cost). No decline is offered: unlike an ordinary
    # optional slot, this is a REQUIRED cost (Sacrifice has no "you may").
    # "Recycle N from your trash:" -- one pick per recycle owed. Required, so no
    # decline: the ability was only offered because the cards were there.
    if state.pend_cost_recycle >= 0:
        item = int(state.pend_cost_recycle)
        if int(state.chain[item, C_CTRL]) != seat:
            return []
        spec = chain.item_spec(state, table, item)
        out = [Action(A_PICK, i) for i in recycle_cost_choices(
            state, table, seat, spec.cost_recycle_type)]
        assert out, "a recycle cost with nothing to recycle should not open"
        return out

    if state.pend_cost_kill >= 0:
        item = int(state.pend_cost_kill)
        if int(state.chain[item, C_CTRL]) != seat:
            return []
        spec = chain.item_spec(state, table, item)
        opts = [Action(A_TARGET, p) for p in rsv.choosable_cost_kill_targets(
            state, table, spec, seat, int(state.chain[item, C_BOUND_BF]),
            int(state.chain[item, C_SRC]), int(state.chain[item, C_CARD]))]
        assert opts, ("an unpayable cost_kill reached a pending decision: "
                      f"{table.names[int(state.chain[item, C_CARD])]}")
        return opts

    # --- mid-decision: a target slot is open ------------------------------
    # Targets are chosen one slot at a time -- the same add-one loop as a Move
    # declaration, which is why that machinery was written generically. Each
    # slot's options depend on the slots already filled (Facebreaker's "at the
    # same battlefield"), so they cannot be enumerated as a product.
    if state.pend_slot >= 0:
        item = chain.oldest_pending(state)
        if item < 0 or int(state.chain[item, C_CTRL]) != seat:
            return []
        opts = [Action(A_TARGET, p) for p in _slot_options(state, table, item)]
        # 355.14 -- an "up to N" slot may be left empty, so skipping is a real
        # choice and not merely the absence of one. `arg = -1` is the skip;
        # `resolve` already reads a -1 slot as "no target" and fizzles just the
        # ops that wanted it.
        spec = chain.item_spec(state, table, item)
        if spec.targets[int(state.pend_slot)].optional:
            opts.append(Action(A_TARGET, -1))
        # A REQUIRED slot whose options have all disappeared takes the same
        # skip, because the alternative is no legal action at all.
        #
        # 355.8 is checked at PLACEMENT -- `chain.fire` refuses to push an
        # ability with no legal target -- and that was the only check, so the
        # gap was a target that was legal when the trigger fired and gone by
        # the time it resolved. Found by the v1 fuzz on seed 565: Yuumi
        # ("when I attack or defend, give one of your OTHER units HERE +3
        # Might") triggered on defence beside Overzealous Fan, which then paid
        # its own optional cost by killing itself. Yuumi was placed last so she
        # resolved first (383.3.d), alone at her battlefield, with a required
        # slot and an empty option list -- and `legal_actions` returned nothing
        # while `acting_seat` still named her controller.
        #
        # An ability that can no longer do what it triggered to do simply does
        # nothing, which is what a -1 slot already means here. Deliberately
        # narrow: it fizzles the ops that wanted this target rather than
        # removing the whole item, so an unrelated op in the same ability still
        # happens. Nothing in the pool currently pairs a targeted op with an
        # untargeted one in one ability; if something does, this is the line
        # that needs revisiting.
        if not opts:
            opts.append(Action(A_TARGET, -1))
        return opts

    # 383.3.a -- a Triggered Ability whose effect BEGINS with "you may" is
    # accepted or declined at FINALIZATION, before targets are chosen. That
    # timing is the whole point: declining removes it from the chain and it
    # counts as never having triggered (383.3.a.2), so it cannot be responded
    # to and it never sees the board it would have changed. A "you may" later
    # in the text is a different thing, decided on resolution (383.3.a.3).
    # "Look at the top N cards... put 1 into your hand and recycle the rest."
    # Checked before everything else for the same reason the mulligan is: the
    # cards are off the deck and in no zone, so nothing else may happen until
    # they land somewhere.
    # Nested INSIDE the look: Nocturne has been taken out of the buffer and is
    # waiting on a destination, so this has to be asked before the look's own
    # pick or the player would be offered two unrelated decisions at once.
    if state.pend_play_look >= 0:
        seat_l = int(state.pend_look)
        if seat != seat_l:
            return []
        card = int(state.look_cards[state.pend_play_look])
        return [Action(A_PLAY_AT, loc) for loc in
                play_destinations(state, table, cfg, seat_l, card)]

    if state.pend_look >= 0:
        if seat != int(state.pend_look):
            return []
        mask = int(state.look_type_mask)
        out = [Action(A_PICK, i) for i in range(int(state.n_look))
               if (not mask or (mask & _look_type_bit(
                   table, int(state.look_cards[i]))))
               and int(table.energy[int(state.look_cards[i])])
               >= int(state.look_min_energy)
               and (int(state.look_max_might) == -1
                    or int(table.might[int(state.look_cards[i])])
                    <= int(state.look_max_might))]
        # "You may reveal a gear from among them" with no gear among them
        # leaves nothing to pick -- and the card said "may", so declining
        # is the whole answer. A type filter therefore always implies an
        # out, which `effects.py` asserts at import.
        if state.look_optional or not out:
            out.append(Action(A_PICK_NONE))
        assert out, "a look with nothing to pick should never have been pended"
        # "...and see me, you may play me for {any rune}" -- Nocturne. An extra
        # action offered alongside the pick rather than instead of it: the
        # permission is his, and the look's own instruction still has to be
        # carried out afterwards on whatever is left. `A_PLAY`'s arg is a LOOK
        # INDEX here, exactly as `A_PICK`'s is -- see `pick_card`.
        #
        # It is offered independently of `look_type_mask`: that mask restricts
        # what the LOOKING card lets you pick, and says nothing about a
        # permission printed on the card being looked at.
        for i in range(int(state.n_look)):
            n = play_from_look_cost(table, int(state.look_cards[i]))
            if state.no_cards[seat] or n < 0:
                continue        # 349 -- this is a play like any other
            if plan_wild_power(state, seat, n) is not None:
                out.append(Action(A_PLAY, i))
        return out

    # Zilean's replacement: "you may play that token and an additional copy of
    # it instead." Checked before `pend_may` because both use ACCEPT/DECLINE
    # and only one can ever be live -- this one is set during a resolution that
    # has already finished, and `_advance_pending` will not start another until
    # it clears.
    # Hard Bargain: "counter a spell UNLESS its controller pays {N}". Asked of
    # the spell's controller -- who is usually the OPPONENT of the player whose
    # card is resolving, and is the only decision here that works that way.
    #
    # Before `pend_double` and `pend_may` for the same reason those two are
    # ordered against each other: all three speak ACCEPT/DECLINE, and only one
    # can be live at a time because `_advance_pending` refuses to start
    # anything new while any of them is set.
    #
    # Affordability was settled when the op suspended -- a seat that cannot pay
    # is countered outright rather than asked -- so ACCEPT is always genuinely
    # available here.
    if state.pend_tax >= 0:
        if seat != int(state.pend_tax):
            return []
        return [Action(A_ACCEPT), Action(A_DECLINE)]
    if state.pend_ask >= 0:
        if seat != int(state.pend_ask):
            return []
        return [Action(A_ACCEPT), Action(A_DECLINE)]

    if int(state.pend_double[0]) >= 0:
        src = int(state.pend_double[0])
        if seat != int(state.perms[src, P_CTRL]):
            return []
        return [Action(A_ACCEPT), Action(A_DECLINE)]

    # Sabotage: pick a card out of the revealed hand. Candidates are read live
    # off the opponent's hand, filtered by the printed type restriction
    # ("a non-unit card"). With no legal card there is nothing to choose and
    # the effect simply does nothing, so a decline is always available.
    if int(state.pend_reveal[0]) >= 0:
        if seat != int(state.pend_reveal[0]):
            return []
        foe = int(state.pend_reveal[1])
        mask = int(state.look_type_mask)
        # 383.3.b -- an optional COST, so the pick is only offered when it can
        # actually be paid. Declining always can be, and costs nothing: the
        # reveal already happened and the card says "IF YOU DO", so a seat
        # short of XP simply sees the hand and takes nothing.
        afford = int(state.xp[seat]) >= int(state.pend_reveal_xp)
        dom = int(state.look_domain)
        out = [Action(A_PICK, i) for i in range(int(state.n_hand[foe]))
               if afford and (not mask or (mask & _look_type_bit(
                   table, int(state.hand[foe, i]))))
               and (dom < 0 or int(table.domain_mask[int(state.hand[foe, i])]) >> dom & 1)]
        if not (state.reveal_hold_return and out):
            out.append(Action(A_PICK_NONE))
        return out

    # "...banish it, then play it": where (a permanent) or whether it can be
    # cast (a spell). Declining is only offered when nothing is legal.
    if state.rp_seat >= 0:
        if seat != int(state.rp_seat):
            return []
        return rplay_options(state, table, cfg)

    # An effect playing a card from hand: first which card, then (for a unit
    # with a choice of battlefields) where.
    if state.pend_hand_play >= 0:
        if seat != int(state.pend_hand_play):
            return []
        if int(state.hp_pick) >= 0:
            c = int(state.hand[seat, int(state.hp_pick)])
            return [Action(A_PLAY_AT, loc)
                    for loc in _hand_play_dests(state, table, seat, c)]
        out = [Action(A_PICK, j) for j in hand_play_choices(state, table, seat)]
        if state.hp_optional or not out:
            out.append(Action(A_PICK_NONE))
        return out

    # Hwei: "discard 1" where WHICH card decides the mode, so it is a real
    # decision rather than `phases.discard`'s take-the-oldest rule.
    if state.pend_discard >= 0:
        if seat != int(state.pend_discard):
            return []
        out = [Action(A_PICK, i) for i in range(int(state.n_hand[seat]))]
        assert out, "a discard choice with an empty hand should not have pended"
        return out

    # Divine Judgment.
    if state.dj_seat >= 0:
        if seat != int(state.dj_seat):
            return []
        return [Action(A_PICK, v) for v in dj_candidates(state, table)]

    # "Name a tag / a spell."
    if state.pend_name >= 0:
        if seat != int(state.pend_name):
            return []
        return [Action(A_PICK, k) for k in range(int(state.n_name_opts))]

    # Mystic Reversal / Rebuttal.
    if state.steal_seat >= 0:
        if seat != int(state.steal_seat):
            return []
        if int(state.steal_stage) in (1, 2):
            return [Action(A_ACCEPT), Action(A_DECLINE)]
        return [Action(A_TARGET, v) for v in _steal_slot_options(state, table)]

    # "Pay any amount of ...": which amount.
    if state.pend_amount >= 0:
        if seat != int(state.pend_amount):
            return []
        return [Action(A_PICK, k) for k in range(amount_max(state, table) + 1)]

    # "Deal N split among ...": one point at a time.
    if state.pend_split >= 0:
        if seat != int(state.pend_split):
            return []
        return [Action(A_TARGET, i) for i in split_candidates(state, table)]

    # Cull the Weak: each player kills one of THEIR OWN units, in turn order.
    # Offered as A_TARGET over the chooser's own live units -- a seat with none
    # never reaches here, because `_advance_cull` skips it.
    if state.pend_cull >= 0:
        if seat != int(state.pend_cull):
            return []
        out = [Action(A_TARGET, i)
               for i in _cull_candidates(state, table, seat)]
        assert out, "a per-player choice with no candidate should have been skipped"
        if int(state.pend_cull_mode) == CULL_RETURN_ANY:
            out.append(Action(A_TARGET, -1))      # "may"
        return out

    # Kharox: "Then you may do this: Choose a unit in their trash and play it,
    # ignoring its cost." Offered as A_PICK over the named trash, read LIVE --
    # the pile was filled by the Burn that ran a moment ago, which is the whole
    # reason this is a mid-resolution choice and not a target slot.
    #
    # "You may", so A_PICK_NONE is always available; and with nothing legal in
    # the pile it is the only option, which is the same shape a type-restricted
    # look takes.
    if state.pend_grave >= 0:
        if seat != int(state.pend_grave):
            return []
        owner = int(state.pend_grave_owner)
        out = [Action(A_PICK, i) for i in range(int(state.n_trash[owner]))
               if table.is_type(int(state.trash[owner, i]), "Unit")
               and not table.is_token(int(state.trash[owner, i]))]
        out.append(Action(A_PICK_NONE))
        return out

    if state.pend_may >= 0:
        item = int(state.pend_may)
        if int(state.chain[item, C_CTRL]) != seat:
            return []
        # 383.3.b -- an optional COST, not just an optional effect. Accepting
        # is only offered when it can actually be paid; declining always is.
        spec = chain.item_spec(state, table, item)
        if spec.opt_cost_energy or spec.opt_cost_power:
            card = int(state.chain[item, C_CARD])
            if plan_ability_cost(state, table, seat, card,
                                 spec.opt_cost_energy,
                                 spec.opt_cost_power) is None:
                return [Action(A_DECLINE)]
        if spec.opt_cost_exhaust_self:
            src = int(state.chain[item, C_SRC])
            # "You may EXHAUST ME to ..." on a legend (Vex - Gloomist, Fiora -
            # Grand Duelist, Volibear): the champion exhausts, and 315.1.b
            # readies it again at the next Awaken, so this is a once-a-turn
            # gate rather than a one-shot.
            ready = (int(state.legend_ready[legend_src_seat(src)])
                     if is_legend_src(src)
                     else src >= 0 and state.perms[src, P_ALIVE] == 1
                     and state.perms[src, P_READY] == 1)
            if not ready:
                return [Action(A_DECLINE)]
        if spec.opt_cost_banish_self:
            src = int(state.chain[item, C_SRC])
            if not (src >= 0 and state.perms[src, P_ALIVE] == 1):
                return [Action(A_DECLINE)]
        if spec.opt_cost_xp and int(state.xp[seat]) < spec.opt_cost_xp:
            return [Action(A_DECLINE)]
        if spec.opt_cost_discard and int(state.n_hand[seat]) < spec.opt_cost_discard:
            return [Action(A_DECLINE)]
        return [Action(A_ACCEPT), Action(A_DECLINE)]

    # 355.11.b -- where a scattered group settles. Offered as locations, the
    # same A_TARGET shape a location slot uses, so no new action kind is needed.
    if state.pend_group_loc >= 0:
        if seat != int(state.pend_group_loc):
            return []
        return [Action(A_TARGET, int(state.group_loc_opts[i]))
                for i in range(int(state.n_group_loc))
                if int(state.group_loc_opts[i]) >= 0]

    # 383.3.d -- simultaneous triggers, and their controller picks the order
    # they go on the Chain. Not cosmetic: the Chain resolves newest-first, so
    # the one placed LAST resolves FIRST.
    if state.pend_order >= 0:
        if seat != int(state.pend_order):
            return []
        return [Action(A_ORDER, i)
                for i in chain.orderable(state, table, seat)]

    if state.pend_hide >= 0:
        if seat != state.active:
            return []
        _, spots = chain.hideable(state, table, cfg, seat)
        return [Action(A_HIDE_AT, i) for i in spots]

    # 820, for a UNIT/GEAR: the printed kill cost is chosen before `pend_play`
    # opens (Cruel Patron). No decline is offered -- a REQUIRED cost, and
    # `legal_actions`'s hand-play offering already proved a target exists.
    if state.pend_kill_play >= 0:
        if seat != int(state.pend_kill_play_seat):
            return []
        card = int(state.hand[seat, int(state.pend_kill_play)])
        spec = spec_for(table, card)
        if spec.cost_kill_discount:
            opts = [Action(A_TARGET, p) for p in
                    _kill_discount_options(state, table, seat, card, spec)]
            if plan_payment(state, table, seat, card, -int(state.kill_disc_e),
                            -int(state.kill_disc_p)) is not None:
                opts.append(Action(A_DECLINE))
            assert opts, "a kill-discount play with no way to pay"
            return opts
        opts = [Action(A_TARGET, p) for p in rsv.choosable_cost_kill_targets(
            state, table, spec, seat)]
        if spec.cost_kill_optional:
            return opts + [Action(A_DECLINE)]
        assert opts, "an unpayable cost_kill reached a pending decision"
        return opts

    # --- mid-decision: a factored choice is open -------------------------
    if state.pend_play >= 0:
        # Normally only the turn player places a unit -- but an [Ambush] unit
        # is played in a response window, which can be the opponent's turn, so
        # the placer is whoever holds priority for that play.
        if seat != int(state.pend_play_seat):
            return []
        card = played_card(state, seat, int(state.pend_play))
        fast = printed_permanent_speed(table, card) >= 0 and chain.speed_ok(
            state, cfg, seat, printed_permanent_speed(table, card))
        dsts = play_destinations(state, table, cfg, seat, card,
                                 ambush_only=not (_main_open(state, seat) or fast))
        out = [Action(A_PLAY_AT, loc) for loc in dsts]
        # 805.2 -- [Accelerate] is an Optional Additional Cost paid *as* the
        # unit is played, so it belongs to this decision rather than a later
        # one. Folding it into the destination choice keeps the pair atomic:
        # where to put it and whether to pay for haste are the same decision,
        # and splitting them would offer a second decision point with two
        # options and no new information.
        # A card's own printed optional additional cost rides the SAME action:
        # 805.2 makes both this and [Accelerate] a cost paid as the card is
        # played, so both belong to this decision. What they buy differs and
        # `_resolve_play` decides that; here they are one offer.
        acc = optional_add_cost(table, card)
        if acc is not None:
            acc = reduced_add_cost(state, table, seat, acc)
        if (acc is not None
                and (table.names[card] not in PLAY_COSTS_DISCARD
                     or int(state.n_hand[seat]) >= 2)
                and (table.names[card] not in PLAY_COST_NEEDS_SPELL
                     or int(state.spells_played[seat]) > 0)
                and int(state.xp[seat]) >= PLAY_COSTS_XP.get(table.names[card], 0)
                and (table.names[card] not in PLAY_COSTS_LEGEND
                     or (int(state.legend[seat]) >= 0
                         and int(state.legend_ready[seat])))
                and plan_payment(state, table, seat, card,
                                 acc[0], acc[1]) is not None):
            out += [Action(A_PLAY_AT_FAST, loc) for loc in dsts]
        return out

    if state.declaring:
        if seat != state.active:
            return []
        out = [Action(A_ADD, i) for i in
               combat.movable_units(state, table, cfg, state.decl_dst)]
        _tax = combat.move_tax(state, table, seat, int(state.decl_dst))
        if _tax and state.decl_mask:
            # Mageseeker Investigator: each unit beyond the first costs [A].
            _n = bin(int(state.decl_mask)).count("1")
            if plan_wild_power(state, seat, _tax * _n) is None:
                out = []
        if state.decl_mask:
            out.append(Action(A_COMMIT))
        # **A_CANCEL is deliberately NOT offered.** `decl_dst`/`decl_mask` are a
        # scratchpad for a half-built Move, not game state, so DECLARE -> ADD ->
        # CANCEL wrote to it and erased it: a bit-identical state reached in
        # three actions, for free, any number of times. A trained policy that
        # mildly preferred those actions did exactly that -- 430 decisions per
        # turn, episodes of 500+ decisions across 3.5 turns, and a third of
        # them truncated. ~50,000 fuzz games never found it because a random
        # agent eventually rolls COMMIT or END_TURN and escapes.
        #
        # There is no such thing as cancelling a declaration in the rules
        # anyway: you either moved units or you did not. Picking some up and
        # putting them back is thinking, not a game action, and it should not
        # have been in the action space. Committing to a destination once you
        # name one is the real decision.
        #
        # This branch cannot be empty: `move_destinations` only offers a
        # destination that has a movable unit, so there is always an ADD, and
        # after one ADD there is always a COMMIT.
        assert out, "a declaration with no way out would deadlock the turn"
        return out

    # --- Closed State: a Chain exists, so both players get priority -------
    # 310.2 / 310.4 and 312.2.c-d. This is the same window whether or not a
    # Showdown is running -- 342.1 says a spell played in a Showdown creates a
    # Chain as normal, so there is deliberately only one priority loop.
    if state.n_chain > 0 or state.showdown_bf >= 0:
        if seat != state.priority:
            return []
        return ([PASS]
                + _hand_spell_actions(state, table, cfg, seat)
                # 822.1.b -- an [Ambush] unit has [Reaction] while it is being
                # played to a battlefield where you control units, so it is
                # offered in the same windows a Reaction spell is.
                # ...but not while a "can't play cards" lock is up: an
                # Ambush unit is still a card being played.
                + ([] if state.no_cards[seat] else
                   [Action(A_PLAY, i) for i in
                    ambush_playable(state, table, cfg, seat)])
                + [Action(A_PLAY, i) for i in
                   fast_permanents_playable(state, table, cfg, seat)]
                # 811.6 -- a facedown card has [Reaction], so it may be played
                # into any window, including on the opponent's turn.
                + [Action(A_PLAY_HIDDEN, i) for i in
                   chain.hidden_playable(state, table, cfg, seat)]
                + [Action(A_PLAY_FLOW, i) for i in
                   chain.flow_playable(state, table, cfg, seat)]
                # 151.2 -- an activated ability is used like a card is played,
                # so one with [Reaction] (a Gold token cashing itself in) or
                # [Action] (Akali - Rogue Assassin pulling a unit out of the
                # fight) belongs in this window too. `activatable` already
                # asks `speed_ok`, which is what keeps a Main-phase-only
                # ability out of it -- this list simply never consulted it,
                # and every Reaction-speed ability in the pool was dead.
                + [Action(A_ACTIVATE, p)
                   for p in activatable(state, table, cfg, seat)])

    # --- Main Phase, Neutral Open ----------------------------------------
    # 316.5.b: only the Turn Player may act in a Neutral Open State.
    if state.phase != MAIN or seat != state.active:
        return []

    out: list[Action] = []
    # "Opponents can't play cards this turn" (Brynhir). `chain`'s three gates
    # cover every SPELL path; permanents are played through this loop instead,
    # so the wider lock has to be stated here too or a unit would walk straight
    # past it. `no_spells` deliberately does NOT appear here: Lilting Lullaby
    # stops spells and says nothing about units.
    # 108.3.d folds the Champion Zone in as one more source for this same loop,
    # so the champion is gated by exactly the checks a unit in hand is.
    for i in ([] if state.no_cards[seat]
              else _hand_choices(state, seat)
              + champion_source(state, table, cfg, seat)):
        card = played_card(state, seat, i)
        # Gear is a permanent like a unit: it is played, it goes on the board,
        # and 337.2 resolves it immediately with no Chain. The only differences
        # are where it lands (base, 149.2) and that it enters READY (359.2.d).
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            _ks = spec_for(table, card)
            if plan_payment(state, table, seat, card) is None and not (
                    _ks is not None and _ks.cost_kill_discount
                    and _kill_discount_options(state, table, seat, card, _ks)):
                continue
            if not combat.permanent_play_allowed(state, table, seat, card):
                continue
            # 820 -- Cruel Patron's printed "kill a [...] as an additional
            # cost to play me". An unpayable REQUIRED cost is the same
            # deadlock `chain.playable_hand_indices` catches for a spell.
            spec = spec_for(table, card)
            if (spec is not None and not spec.cost_kill_optional
                    and not rsv.can_play_with_cost_kill(
                        state, table, spec, seat)):
                continue
            out.append(Action(A_PLAY, i))
    out += _hand_spell_actions(state, table, cfg, seat)
    hide_cards, _ = chain.hideable(state, table, cfg, seat)
    for i in hide_cards:
        out.append(Action(A_HIDE, i))
    for i in chain.hidden_playable(state, table, cfg, seat):
        out.append(Action(A_PLAY_HIDDEN, i))
    for i in chain.flow_playable(state, table, cfg, seat):
        out.append(Action(A_PLAY_FLOW, i))

    out += [Action(A_ACTIVATE, p) for p in activatable(state, table, cfg, seat)]

    for loc in combat.move_destinations(state, table, cfg):
        out.append(Action(A_DECLARE, loc))

    # **Through `can_move`, because a retreat IS a Move.** This loop used to
    # check ready/unit/at-a-battlefield itself and never asked `can_move` --
    # whose own comment promised that Vex's "they can't move it this turn"
    # blocks "every ordinary Move including the retreat home". It did not: a
    # Vex-locked unit was offered A_RETREAT and walked out of the lock. Asking
    # the one movement predicate also means every future restriction ("I can't
    # move to base") applies to retreating without a second copy here.
    for i in range(state.n_perms):
        row = state.perms[i]
        if (row[P_ALIVE] == 1 and row[P_CTRL] == seat
                and is_battlefield(int(row[P_LOC]))
                and combat.can_move(state, table, cfg, i, base_loc(seat))):
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


def _mid_decision(state: GameState) -> bool:
    """Is a player partway through a decision (or the game over)?"""
    return bool(
        state.pend_slot >= 0 or state.pend_may >= 0 or state.pend_order >= 0
        or state.pend_group_loc >= 0
        or state.pend_play >= 0 or state.pend_hide >= 0 or state.declaring
        or state.pend_look >= 0 or int(state.pend_double[0]) >= 0
        or int(state.pend_reveal[0]) >= 0 or state.pend_cull >= 0
        or state.pend_grave >= 0
        or state.pend_discard >= 0 or state.pend_cost_kill >= 0
        or state.pend_cost_recycle >= 0
        or state.pend_tax >= 0 or state.pend_ask >= 0
        or state.pend_hand_play >= 0 or state.rp_seat >= 0
        or state.pend_split >= 0 or state.pend_amount >= 0
        or state.steal_seat >= 0 or state.pend_name >= 0
        or state.dj_seat >= 0 or state.pend_altar >= 0
        or state.pend_kill_play >= 0 or state.pend_dmg >= 0
        or is_terminal(state))


def flush_player_events(state: GameState, table: CardTable) -> None:
    """Turn the deferred per-player event counters into queued watchers.

    These four events are counted where they happen -- deep inside a payment,
    or in a zone change with no card table in scope -- and become watchers
    here. Once per event, not once per batch: recycling two runes for one cost
    is two recycles (416.1.b).

    **Which abilities are eligible is decided by the board as this runs**, so
    it has to run before anything can put a NEW permanent down: an ability that
    did not exist when the event happened never triggered on it. That is why
    `_finish_rplay` calls it before an effect plays a card -- 354.3 holds that
    play until the effect that started it has finished resolving, so a unit
    arriving out of Dazzling Aurora is not on the board for the recycle that
    revealed it and its "when you recycle" ability stays silent (#6683).
    """
    for _s in range(N_SEATS):
        if (int(state.draw_ply[_s]) == int(state.ply)
                and int(state.draw_count[_s]) >= 2
                and int(state.second_draw_ply[_s]) != int(state.ply)):
            state.second_draw_ply[_s] = int(state.ply)
            chain.fire_watchers(state, table, _s, TR_SECOND_DRAW)
        if int(state.recycled_n[_s]):
            state.recycled_n[_s] = 0
            chain.fire_watchers(state, table, _s, TR_RECYCLED)
        for _n in range(int(state.rune_recycled_n[_s])):
            chain.fire_watchers(state, table, _s, TR_RUNE_RECYCLED)
        state.rune_recycled_n[_s] = 0
        for _n in range(int(state.banished_n[_s])):
            chain.fire_watchers(state, table, _s, TR_BANISHED)
        state.banished_n[_s] = 0


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
    if _mid_decision(state):
        return {}
    combat.scan_might_transitions(state, table, cfg)
    flush_player_events(state, table)
    log: dict = _run_pending_repeat(state, table, cfg)
    # The deferred [Repeat] pass can itself stop for a decision (a second Hard
    # Bargain tax). Placing queued triggers on top of that left a "you may"
    # pointing at a Chain index the tax's counter then shifted away -- a stall
    # with nobody able to act (fuzz seed 420, once 419.4.a queued Abandoned
    # Hall's trigger at resolution).
    if _mid_decision(state):
        return log
    # **Drain, clean up, and drain again.** The Cleanup at the bottom is itself
    # a trigger site -- 323.4 queues Deathknells and 383.4.c.2.a the Conquer
    # abilities of the units that just took the ground -- so a single pass
    # leaves whatever the Cleanup fired sitting in the queue with nothing left
    # to place it. `end_turn` then trips `compact_permanents`, which refuses to
    # renumber rows a queued trigger still points at.
    #
    # It converges in two passes: once a trigger is on the Chain the state is
    # Closed, `_settle_after_decision` declines to clean up, and nothing new is
    # queued. The bound is generous rather than 2 so that a genuine cycle
    # announces itself instead of looping.
    for _ in range(MAX_TRIGGERS + 1):
        # Every queued trigger goes on the Chain BEFORE any of them is
        # finalized: 383.3.d is about the order they are *placed*, and 337.1.b
        # then finalizes oldest-first once they are all there.
        for _ in range(MAX_TRIGGERS + 1):
            if not state.n_trig:
                break
            seat = chain.next_placer(state)
            opts = chain.orderable(state, table, seat)
            if len(opts) > 1:
                state.pend_order = seat
                return log
            chain.place(state, table, cfg, opts[0])
        else:
            raise AssertionError("the trigger queue is not draining")
    # ...and then a Cleanup, for the same "one central place" reason. 319.3-319.5
    # owe one after a Pending Item is added to the Chain, after it is finalized,
    # and after any item leaves the Chain "for any reason" -- and DECLINING a
    # "you may" is one of those reasons (383.3.a.2). The A_PASS path runs a
    # Cleanup after it resolves something, so every route that ends by
    # resolving was covered and every route that ends by *removing* an item
    # was not: declining the last trigger on the Chain left the board in an
    # Open State with a staged Combat and nothing to initiate it.
    #
    # It only surfaced once `cleanup` started deferring while triggers are
    # queued (323.12 needs a Neutral Open State). Before that, the Move's own
    # Cleanup had already opened the Showdown before the trigger existed, so
    # the missing one had nothing left to do.
        log.update(_settle_after_decision(state, table, cfg))
        if not state.n_trig:
            return _resume_phase(state, table, cfg, log)
    raise AssertionError("the Cleanup keeps queueing triggers")


def _finish_turn(state: GameState, table: CardTable, cfg: Config) -> dict:
    """The cleanup half of ending a turn, once nothing is left on the Chain.

    Reached directly when no end-of-turn ability fired, and through
    `_resume_phase` when one did -- so the two paths cannot drift.
    """
    phases.end_turn(state, cfg, table)
    if not is_terminal(state):
        return phases.start_turn(state, table, cfg)
    return {}


def _resume_phase(state: GameState, table: CardTable, cfg: Config,
                  log: dict) -> dict:
    """Finish a turn suspended mid-Beginning-Phase, if one is (315.2).

    `phases.start_turn` stops after the Beginning Step whenever it put anything
    on the Chain, because the Scoring Step is a LATER step and must not run
    until those abilities have resolved. This is the other half: the Chain is
    empty again, so the turn carries on into scoring, channel and draw.

    Guarded on the Chain AND the trigger queue both being empty. Resuming with
    either non-empty would score in the middle of the step it is supposed to
    follow -- the exact bug this split exists to fix, reintroduced one level
    down.

    **And on no Showdown being open.** A Combat is not on the Chain and queues
    no trigger while it runs, so neither of those two guards can see one. An
    [Action] spell may be played during the Ending Phase, and Moonfall ("move
    up to one enemy unit to that battlefield") initiates a Combat when it
    resolves -- so the Chain went empty, this resumed, and `end_turn` reached
    `compact_permanents` with a Showdown still open, which is the assertion
    that caught it. Found by the real-deck fuzz on seed 90.

    Nothing else has to change to un-stick it: the Showdown is resolved by
    ordinary player actions, and every action ends in `_settle`, which calls
    this again once the Combat has closed.
    """
    if (state.pend_phase < 0 or state.n_chain or state.n_trig
            or state.showdown_bf >= 0):
        return log
    if is_terminal(state):
        state.pend_phase = -1
        return log
    if int(state.pend_phase) == ENDING:
        # The other suspension: the Ending Phase's triggers have resolved, so
        # the cleanup that could not run while they were queued runs now.
        state.pend_phase = -1
        log.update(_finish_turn(state, table, cfg))
        if state.n_trig or state.n_chain:
            log.update(_settle(state, table, cfg))
        return log
    log.update(phases.resume_turn(state, table, cfg))
    # Resuming is itself a trigger site: scoring a Hold fires TR_HOLD and the
    # "when an opponent scores" watchers, and the Draw Step can end the game.
    # So settle again rather than leaving those queued for the next action --
    # the same reason `_settle` drains twice around its Cleanup.
    if state.n_trig or state.n_chain:
        log.update(_settle(state, table, cfg))
    return log


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
                showdown_before = int(state.showdown_bf)
                from_trigger = bool(state.chain_from_trigger)
                log.update(combat.cleanup(state, table, cfg,
                                          mover=int(state.active), dst=-1))
                if showdown_before >= 0 and not from_trigger:
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
                    #
                    # **Both of 340.2.a's own conditions are now checked, and
                    # each of them was letting Focus pass when the rule says it
                    # does not.**
                    #
                    #   "If this occurs DURING a Showdown" -- one that was
                    #   already running when the Chain emptied. A Showdown that
                    #   the following Cleanup *opens* is beginning, not
                    #   continuing, so 345/464.2.d applies instead and Focus
                    #   goes to the player who applied Contested. Testing
                    #   `showdown_bf` after the Cleanup could not tell those
                    #   apart, so every newly-opened Showdown started with the
                    #   wrong player holding Focus.
                    #
                    #   "and the chain wasn't initiated by a triggered ability"
                    #   -- the Irresistible Faefolk line is exactly that: her
                    #   move trigger opened the Chain, so Focus does not pass at
                    #   all. (The rule's other exemption, an ability that Adds
                    #   resources, is not modelled -- no [Add] ability is
                    #   scripted yet. This is where it goes.)
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
        # Nocturne's permission rides this action with a LOOK-BUFFER index --
        # the same arg-means-what-the-offer-site-says trick `A_PICK` uses, and
        # unambiguous because a look suspends every ordinary play offer.
        if state.pend_look >= 0:
            state.pend_play_look = int(action.arg)
            return {}
        seat = int(state.priority)        # not `active`: responses happen on
        # `played_card`, because 108.3.d lets `arg` be `CHAMPION_SRC`.
        card = played_card(state, seat, int(action.arg))  # opponent's turn too
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            # 820 -- Cruel Patron prints "kill a [...] as an additional cost
            # to play me". Chosen (and paid) before `pend_play` opens, since a
            # printed destination permission (Stalking Wolf) can depend on it.
            spec = spec_for(table, card)
            if spec is not None and spec.cost_kill is not None:
                state.pend_kill_play = action.arg
                state.pend_kill_play_seat = seat
                return {}
            state.pend_play = action.arg
            state.pend_play_seat = seat
            return {}
        return _play_spell(state, table, cfg, seat, action.arg)

    if k == A_PLAY_REPEAT:
        seat = int(state.priority)
        return _play_spell(state, table, cfg, seat, action.arg, repeat=True)

    if k == A_PLAY_BOTH:
        seat = int(state.priority)
        return _play_spell(state, table, cfg, seat, action.arg, repeat=True,
                           both=True)

    if k == A_TARGET:
        if state.pend_group_loc >= 0:
            return _finish_group_loc(state, table, cfg, int(action.arg))
        if state.steal_seat >= 0:
            return _steal_choose(state, table, cfg, int(action.arg))
        if state.pend_split >= 0:
            return _split_one(state, table, cfg, int(action.arg))
        if state.pend_cull >= 0:
            return _cull_one(state, table, cfg, int(action.arg))
        if state.pend_cost_kill >= 0:
            return _choose_cost_kill_target(state, table, cfg, action.arg)
        if state.pend_kill_play >= 0:
            return _choose_unit_cost_kill_target(state, table, cfg, action.arg)
        if state.rp_seat >= 0:
            return _pay_rplay_cost_kill(state, table, cfg, int(action.arg))
        return _choose_target(state, table, cfg, action.arg)

    if k == A_ACTIVATE:
        return _activate(state, table, cfg, int(state.priority), action.arg)

    if k == A_ORDER:
        state.pend_order = -1
        chain.place(state, table, cfg, action.arg)
        return {}

    if k in (A_ACCEPT, A_DECLINE) and state.pend_altar >= 0:
        log = _answer_altar(state, table, cfg, k == A_ACCEPT)
        # The Combat was stopped mid-death; this is what starts it again.
        if state.showdown_bf >= 0:
            log.update(combat.advance_combat(state, table, cfg))
        log.update(_settle_after_decision(state, table, cfg))
        return log

    if k in (A_ACCEPT, A_DECLINE) and state.steal_seat >= 0:
        return _answer_steal(state, table, cfg, k == A_ACCEPT)

    if k in (A_ACCEPT, A_DECLINE) and state.rp_seat >= 0:
        return _finish_rplay(state, table, cfg, -1 if k == A_ACCEPT else -2)

    if k == A_ACCEPT:
        if state.pend_tax >= 0:
            return _finish_tax(state, table, cfg, pay=True)
        if state.pend_ask >= 0:
            return _finish_ask(state, table, cfg, yes=True)
        if int(state.pend_double[0]) >= 0:
            return _resolve_double(state, table, cfg, take=True)
        return _accept_may(state, table, cfg)

    if k == A_DECLINE:
        if state.pend_kill_play >= 0:
            return _choose_unit_cost_kill_target(state, table, cfg, -1)
        if state.pend_tax >= 0:
            return _finish_tax(state, table, cfg, pay=False)
        if state.pend_ask >= 0:
            return _finish_ask(state, table, cfg, yes=False)
        if int(state.pend_double[0]) >= 0:
            return _resolve_double(state, table, cfg, take=False)
        return _decline_may(state, table, cfg)

    if k == A_HIDE:
        state.pend_hide = action.arg
        return {}

    if k == A_HIDE_AT:
        return _hide_at(state, table, cfg, seat, action.arg)

    if k == A_MULLIGAN:
        state.mull_mask |= 1 << int(action.arg)
        return {}

    if k == A_MULLIGAN_DONE:
        return _finish_mulligan(state, table, cfg)

    # Combat damage assignment (465.2.c.2). Before every other `A_PICK` site:
    # the arg is a PERMANENT ROW here, not a buffer index, and a suspended
    # assignment blocks all the other offers anyway.
    if k in (A_PICK, A_PICK_NONE) and state.pend_dmg >= 0:
        return _assign_damage_pick(
            state, table, cfg, int(action.arg) if k == A_PICK else -1)

    if k == A_PICK and state.dj_seat >= 0:
        return dj_pick(state, table, cfg, int(action.arg))

    if k == A_PICK and state.pend_name >= 0:
        src = int(state.name_src)
        if src >= 0 and state.perms[src, P_ALIVE] == 1:
            state.named[src] = int(state.name_opts[int(action.arg)])
            host = int(state.perms[src, P_ATTACHED_TO])
            if int(state.name_kind) == 2 and host >= 0:
                state.copy_of[host] = int(state.name_opts[int(action.arg)])
                state.copy_via[host] = src
        state.pend_name, state.name_src, state.n_name_opts = -1, -1, 0
        state.name_opts[:] = -1
        return _settle_after_decision(state, table, cfg)

    if k == A_PICK and state.rp_seat >= 0 and int(state.rp_card) < 0:
        state.rp_card = int(state.sarc_cards[int(state.rp_seat), int(action.arg)])
        return {}

    if k == A_PICK and state.pend_amount >= 0:
        return _finish_amount(state, table, cfg, int(action.arg))

    if k in (A_PICK, A_PICK_NONE) and state.pend_hand_play >= 0:
        if k == A_PICK_NONE:
            return _finish_hand_play(state, table, cfg, -1, -1)
        seat_h = int(state.pend_hand_play)
        c = int(state.hand[seat_h, int(action.arg)])
        dests = (_hand_play_dests(state, table, seat_h, c)
                 if table.is_type(c, "Unit") or table.is_type(c, "Gear") else [-1])
        if len(dests) == 1:
            return _finish_hand_play(state, table, cfg, int(action.arg), dests[0])
        state.hp_pick = int(action.arg)
        return {}

    if k in (A_PICK, A_PICK_NONE):
        if state.pend_cost_recycle >= 0:
            return _pay_cost_recycle(state, table, cfg, int(action.arg))
        if state.pend_grave >= 0:
            return _finish_dig(state, table, cfg,
                               int(action.arg) if k == A_PICK else -1)
        if state.pend_discard >= 0:
            return _finish_discard(state, table, cfg, int(action.arg))
        if int(state.pend_reveal[0]) >= 0:
            return _finish_reveal(state, table, cfg,
                                  int(action.arg) if k == A_PICK else -1)
        return _finish_look(state, table, cfg,
                            int(action.arg) if k == A_PICK else -1)

    if k == A_PLAY_FLOW:
        return _play_flow(state, table, cfg, int(state.priority), action.arg)

    if k == A_PLAY_HIDDEN:
        return _play_from_hidden(state, table, cfg, int(state.priority),
                                 action.arg)

    # **The placer is not always the turn player.** An [Ambush] unit is played
    # in a response window, which may be the opponent's turn, so the seat that
    # announced the play is the one holding priority for it -- reading
    # `state.active` here paid for the card out of the wrong hand and then
    # sliced an empty array.
    if k in (A_PLAY_AT, A_PLAY_AT_FAST):
        if state.rp_seat >= 0:
            return _finish_rplay(state, table, cfg, int(action.arg),
                                 fast=(k == A_PLAY_AT_FAST))
        if state.pend_hand_play >= 0 and int(state.hp_pick) >= 0:
            return _finish_hand_play(state, table, cfg, int(state.hp_pick),
                                     int(action.arg))
        if state.pend_play_look >= 0:
            return _resolve_play_from_look(state, table, cfg, action.arg)
        return _resolve_play(state, table, cfg, int(state.pend_play_seat),
                             action.arg, fast=(k == A_PLAY_AT_FAST))

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
        # 317 -- "at the end of your turn" abilities go on the Chain first and
        # take a real priority window, exactly as the Beginning Step's do
        # (315.2). If any fired, the turn SUSPENDS here and `_resume_phase`
        # runs the cleanup once the Chain is empty; the alternative is a
        # cleanup that compacts rows a queued trigger is still pointing at.
        #
        # Nothing suspends when nothing triggered, which is every turn in v0.
        phases.fire_end_of_turn(state, table)
        if state.n_trig or state.n_chain:
            state.phase = ENDING
            state.pend_phase = ENDING
            return _settle(state, table, cfg)
        return _finish_turn(state, table, cfg)

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
    # C_COST_KILL is the card THIS play already killed to pay its own
    # printed cost (820), or -1 -- Heedless Resurrection's trash-unit slot
    # reads it through `capped_by_cost_kill`.
    rsv.COST_KILL_PAID[0] = int(state.chain[item, C_COST_KILL]) >= 0
    rsv.TARGET_SUBJ[0] = int(state.chain[item, C_SUBJ])
    try:
        opts = rsv.choosable_targets(state, table, spec, slot, seat, chosen,
                                     int(state.chain[item, C_BOUND_BF]),
                                     int(state.chain[item, C_SRC]),
                                     int(state.chain[item, C_CARD]),
                                     int(state.chain[item, C_COST_KILL]))
        # 809.1.c again, from the offering side: an ability may not choose a
        # [Deflect] unit its controller cannot pay the surcharge for -- unless
        # that is the only choice it has, which `fire` already let onto the
        # Chain and which must therefore stay answerable.
        if int(state.chain[item, C_ABIL]) >= 0 and len(opts) > 1:
            _card = int(state.chain[item, C_CARD])
            _keep = [o for o in opts
                     if not rsv.deflect_cost(state, table, seat, chosen + [o], spec)
                     or plan_surcharge(state, table, seat, _card,
                                       rsv.deflect_cost(state, table, seat,
                                                        chosen + [o], spec),
                                       reserved=()) is not None]
            if _keep:
                opts = _keep
        # A spell affordable ONLY through its choice-dependent discount
        # (Undying Loyalty) may only make a choice that earns it.
        card = int(state.chain[item, C_CARD])
        if (slot == 0 and int(state.chain[item, C_ABIL]) < 0
                and table.names[card] in TRASH_TAG_DISCOUNT
                and int(state.chain[item, C_COST]) == 0
                and plan_payment(state, table, seat, card) is None):
            ok = set(chain.tag_discount_targets(state, table, seat, card, spec))
            opts = [o for o in opts if o in ok]
        return opts
    finally:
        rsv.COST_KILL_PAID[0] = False
        rsv.TARGET_SUBJ[0] = -1


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
        # 820 -- a printed "kill a [...]" cost is chosen and paid BEFORE the
        # ability's own targets, exactly as it is for a card that prints one.
        # An OPTIONAL one is only paid through A_PLAY_REPEAT (C_REPEAT 2); a
        # card put on the Chain by an effect (Void Rush) plays it unpaid.
        # Already PAID when C_COST_KILL is set: an Altar of Blood offer on the
        # unit being killed suspends the play between paying and choosing
        # targets, and answering it lands back here (fuzz seed 250, Heedless
        # Resurrection). Asking again charged the cost a second time.
        if spec.cost_kill is not None and (
                not getattr(spec, "cost_kill_optional", False)
                or int(state.chain[item, C_REPEAT]) in (2, 3)) \
                and int(state.chain[item, C_COST_KILL]) < 0:
            state.pend_cost_kill = item
            return log
        if spec.n_targets:
            if state.pend_slot < 0:
                state.pend_slot = 0
            return log
        log.update(_finalize_pending(state, table, cfg, item))
    raise AssertionError("pending chain items are not draining")


def _play_spell(state: GameState, table: CardTable, cfg: Config, seat: int,
                hand_idx: int, repeat: bool = False,
                both: bool = False) -> dict:
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
    if repeat:
        # Recorded now, paid at finalization with the rest of the cost, and
        # read at resolution. 820.1.c.3 -- once only, so this is a flag and
        # never a count. 2 is a printed OPTIONAL additional cost instead
        # (Ruthless Strike), which buys a clause rather than a second pass.
        # 3 -- BOTH the printed optional additional cost and the [Repeat]
        # (A_PLAY_BOTH). Every reader asks `in (1, 3)` for "this repeats" and
        # `in (2, 3)` for "the optional cost was paid".
        state.chain[item, C_REPEAT] = (
            3 if both else 2 if has_spell_opt_cost(spec) else 1)
    # 820 -- a printed additional cost is chosen and paid before the card's
    # own effect targets: `chain.playable_hand_indices` already refused to
    # offer this card at all if the cost has no legal target.
    if spec.cost_kill is not None and (repeat or not spec.cost_kill_optional):
        state.pend_cost_kill = item
        return {"announced": table.names[card]}
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _pay_cost_recycle(state: GameState, table: CardTable, cfg: Config,
                      trash_idx: int) -> dict:
    """Recycle one chosen card from the trash toward a cost (3956).

    416.1.c -- a recycled card goes to the bottom of its OWNER's deck, and a
    "your trash" cost only ever reads the payer's own pile, so the payer is the
    owner here.

    When the last recycle is paid the ability continues exactly as
    `_choose_cost_kill_target` continues after its kill: to its own targets if
    it has any, otherwise straight to finalization.
    """
    item = int(state.pend_cost_recycle)
    seat = int(state.chain[item, C_CTRL])
    card = int(state.trash[seat, trash_idx])
    assert rsv.take_from_trash(state, seat, card), "recycle cost lost its card"
    state.recycle_card(seat, card)
    state.pend_cost_recycle_n -= 1
    log = {"cost_recycled": table.names[card]}
    if int(state.pend_cost_recycle_n) > 0:
        return log
    state.pend_cost_recycle = -1
    spec = chain.item_spec(state, table, item)
    if spec.n_targets:
        state.pend_slot = 0
        return log
    log.update(_finalize_pending(state, table, cfg, item))
    log.update(_advance_pending(state, table, cfg))
    return log


def _choose_cost_kill_target(state: GameState, table: CardTable, cfg: Config,
                             perm: int) -> dict:
    """820 -- pay a card's printed "kill a [...]" additional cost.

    Killed here, at the choice itself, the same moment `_accept_may` pays an
    ability's `opt_cost_kill_self` -- both are a cost committed to as soon as
    it is chosen, not deferred to finalization the way rune payment is. There
    is no window between choice and finalization here (nothing else can act
    while `pend_cost_kill` is open), so the two orderings are equivalent; this
    one is simply the established pattern.
    """
    item = int(state.pend_cost_kill)
    assert perm >= 0, "cost_kill is a REQUIRED cost; there is no decline"
    # Captured BEFORE the kill: Heedless Resurrection's "costs no more than
    # the KILLED unit" needs the card id, and a dead permanent's row is never
    # the read path (the same caution `dead_source` exists for elsewhere).
    state.chain[item, C_COST_KILL] = int(state.perms[perm, P_CARD])
    state.pend_cost_kill = -1
    spec = chain.item_spec(state, table, item)
    if getattr(spec, "cost_exhaust_unit", False):
        state.chain[item, C_CTX2] = int(state.perms[perm, P_LOC])
        state.perms[perm, P_READY] = 0
    elif getattr(spec, "cost_spend_buff", False):
        chain.spend_buff(state, table, int(state.chain[item, C_CTRL]), perm)
    elif getattr(spec, "cost_return", False):
        combat.return_to_hand(state, table, perm)
    else:
        # 428.1.a.1 -- an Active Kill is one taken "when instructed by a game
        # effect OR AS A COST", so a kill paid as a spell's additional cost is
        # still that spell killing the unit: Immortal Phoenix in the trash sees
        # Sacrifice's cost (RiftJudge #10252). Only a SPELL's cost counts --
        # Atakhan's kill is a unit's cost and no spell killed anything.
        prev = combat.KILLER[:]
        combat.KILLER[:] = [
            int(state.chain[item, C_CTRL]),
            int(state.chain[item, C_ABIL]) < 0
            and bool(table.is_type(int(state.chain[item, C_CARD]), "Spell"))]
        try:
            combat.destroy(state, table, perm)
        finally:
            combat.KILLER[:] = prev
    if spec.n_targets:
        state.pend_slot = 0
        return {"cost_kill": perm}
    log = _finalize_pending(state, table, cfg, item)
    if getattr(spec, "immediate", False):
        # 337.2 -- a resource add never waits on the Chain: resolved now,
        # before anyone could respond (Malzahar - Fanatic).
        log.update(chain.resolve_top(state, table, cfg))
        log.update(_settle_after_decision(state, table, cfg))
        log["cost_kill"] = perm
        return log
    log.update(_advance_pending(state, table, cfg))
    log["cost_kill"] = perm
    return log


def _kill_discount_options(state: GameState, table: CardTable, seat: int,
                           card: int, spec) -> list[int]:
    """Friendly units whose death as this unit's cost is worth offering: for
    Atakhan any legal one (while nothing is killed yet) that leaves the play
    payable; for Commander Ledros any while a Power symbol is left to take
    off, provided SOME number of kills makes the play payable."""
    de, dp = int(state.kill_disc_e), int(state.kill_disc_p)
    cands = rsv.cost_kill_targets(state, table, spec, seat)
    if spec.cost_kill_discount == KD_KILLED_COST:
        if de or dp:
            return []
        return [p for p in cands if plan_payment(
            state, table, seat, card,
            -int(table.energy[int(state.perms[p, P_CARD])]),
            -int(table.power[int(state.perms[p, P_CARD])])) is not None]
    left = int(table.power[card]) - dp
    if left <= 0 or not cands:
        return []
    best = min(len(cands), left)
    if plan_payment(state, table, seat, card, -de, -(dp + best)) is None:
        return []
    return list(cands)


def _choose_unit_cost_kill_target(state: GameState, table: CardTable,
                                  cfg: Config, perm: int) -> dict:
    """820, for a UNIT/GEAR whose own play prints the kill cost (Cruel Patron)
    -- `_choose_cost_kill_target`'s counterpart for a card that never reaches
    the Chain (337.2), so there is no chain item to record this on or to
    finalize. Paying it simply unblocks the ordinary `pend_play` destination
    choice that follows every unit/gear play.
    """
    idx, seat = int(state.pend_kill_play), int(state.pend_kill_play_seat)
    # No champion prints a kill-cost today, so `CHAMPION_SRC` cannot reach
    # here -- but the index is the same one `A_PLAY` carried, so it is read
    # the same way rather than left as a trap for the first one that does.
    spec = spec_for(table, played_card(state, seat, idx))
    assert perm >= 0 or spec.cost_kill_optional, \
        "cost_kill is a REQUIRED cost; there is no decline"
    if spec.cost_kill_discount and perm >= 0:
        killed = int(state.perms[perm, P_CARD])
        if spec.cost_kill_discount == KD_KILLED_COST:
            state.kill_disc_e += int(table.energy[killed])
            state.kill_disc_p += int(table.power[killed])
        else:
            state.kill_disc_p += 1
        state.pend_kill_play_loc = int(state.perms[perm, P_LOC])
        if spec.cost_spend_buff:
            chain.spend_buff(state, table, seat, perm)   # Kraken Hunter
        else:
            combat.destroy(state, table, perm)
        card = played_card(state, seat, idx)
        if (spec.cost_kill_discount == KD_POWER_EACH
                and _kill_discount_options(state, table, seat, card, spec)):
            return {"cost_kill": perm}           # "any number": keep choosing
        state.pend_kill_play = -1
        state.pend_kill_play_seat = -1
        state.pend_play = idx
        state.pend_play_seat = seat
        return {"cost_kill": perm}
    state.pend_kill_play = -1
    state.pend_kill_play_seat = -1
    state.pend_play = idx
    state.pend_play_seat = seat
    if perm < 0:
        return {"cost_kill": None}
    # Captured BEFORE the kill: Stalking Wolf's "play me to ITS BATTLEFIELD"
    # (`effects.PLAY_TO_COST_KILL_LOC`) needs where the target stood, and a
    # dead permanent's P_LOC is no longer a location anyone should read.
    # It also records that an OPTIONAL one was paid (`_resolve_play`).
    state.pend_kill_play_loc = int(state.perms[perm, P_LOC])
    if spec.cost_return:
        combat.return_to_hand(state, table, perm)
    else:
        combat.destroy(state, table, perm)
    return {"cost_kill": perm}


def _choose_target(state: GameState, table: CardTable, cfg: Config,
                   perm: int) -> dict:
    item = chain.oldest_pending(state)
    assert item >= 0 and state.pend_slot >= 0, "no slot open"
    # 355.7 -- this is the moment something is CHOSEN, and the only one, so it
    # is where "when you choose ..." watchers fire. Gated on the slot's kind:
    # the arg is a permanent row only for a permanent slot, and reading a
    # location or a Chain uid as a row is the mistake `open_slot_kind` exists
    # to prevent. A declined optional slot (-1) chooses nothing.
    kind = chain.open_slot_kind(state, table)
    if kind == TK_MODE and perm >= 0:
        base = chain.item_spec(state, table, item)
        src = int(state.chain[item, C_SRC])
        if getattr(base, "modes_once_per_turn", False) and src >= 0:
            if int(state.mode_used_ply[src]) != int(state.ply):
                state.mode_used_ply[src] = int(state.ply)
                state.mode_used_mask[src] = 0
            state.mode_used_mask[src] |= 1 << perm
    if perm >= 0 and kind in _PERM_SLOT_KINDS:
        if int(state.perms[perm, P_CTRL]) != int(state.chain[item, C_CTRL]) \
                and table.is_type(int(state.perms[perm, P_CARD]), "Unit"):
            _who = int(state.chain[item, C_CTRL])
            if int(state.chose_enemy_ply[_who]) != int(state.ply):
                state.chose_enemy_n[_who] = 0     # a count, per turn
            state.chose_enemy_ply[_who] = int(state.ply)
            state.chose_enemy_n[_who] += 1
        chain.fire_watchers(state, table, int(state.chain[item, C_CTRL]),
                            TR_CHOSEN, subj=int(perm),
                            by_spell=int(state.chain[item, C_ABIL]) < 0)
        # ...and the ground the chosen unit is standing on (The Dreaming Tree).
        _cl = int(state.perms[perm, P_LOC])
        if is_battlefield(_cl):
            from rl.engine.state import P_DMG, bf_index as _bf_index
            combat._queue_bf_trigger(state, table, TR_CHOSEN, _bf_index(_cl),
                                     int(state.chain[item, C_CTRL]),
                                     subj=int(perm))
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
        spec = chain.item_spec(state, table, item)
        if spec.trigger == TR_ACTIVATED:
            # 204.1.b -- the base cost is what stands before the ':'.
            # Discounted ONCE and handed to both halves, so the number that
            # said "affordable" is the number that gets paid.
            state.empower_src = int(state.chain[item, C_SRC])
            e = ability_energy(state, table, seat, card, spec.cost_energy, spec)
            state.empower_src = -1
            if (table.names[card] in EQUIP_LESS_CHOSEN_MIGHT
                    and any(o.op == OP_ATTACH for o in spec.ops)):
                # Hextech Gauntlets: less by the chosen unit's Might.
                _u = int(state.chain_targets[item, 0])
                if _u >= 0 and state.perms[_u, P_ALIVE] == 1:
                    e = max(0, e - combat.might(state, table, _u))
            recycle = plan_ability_cost(state, table, seat, card,
                                        e, spec.cost_power)
            assert recycle is not None, "unaffordable ability reached finalize"
            pay_ability_cost(state, table, seat, e, recycle,
                             spec.cost_power, card)
            if spec.cost_exhaust:
                src = int(state.chain[item, C_SRC])
                # A legend exhausts in its own zone -- it has no `perms` row,
                # and 107.4.d keeps it out of one.
                if is_legend_src(src):
                    who = legend_src_seat(src)
                    assert state.legend_ready[who], \
                        "exhaust cost with an already-exhausted legend"
                    state.legend_ready[who] = 0
                else:
                    assert state.perms[src, P_READY], \
                        "exhaust cost with no ready source"
                    state.perms[src, P_READY] = 0
            # 441.2 -- "Disempower this" stands before the ':', so it is a
            # COST and is paid HERE, at finalization, not when the ability
            # resolves. **This is the second of two payment sites and they are
            # not interchangeable**: a targetless ability with a rune cost goes
            # on the Chain and pays here, while `_activate`'s inline path pays
            # for the ones that never reach it. Paying at only one of them let
            # Questionable Tome draw a card and keep its Empower.
            #
            # A legend holds the status in `legend_emp` rather than on a row
            # (441 applies it to any Game Object), so the source decides which
            # store is spent.
            if spec.cost_disempower_self:
                src2 = int(state.chain[item, C_SRC])
                paid = (state.src_disempower(src2) if is_legend_src(src2)
                        else src2 >= 0 and state.disempower(src2))
                assert paid, "disempower cost finalized with no status"
            if spec.cost_discard:
                _pay_discard_cost(state, table, seat, spec)
            if spec.cost_spend_buff_self:
                src2 = int(state.chain[item, C_SRC])
                assert src2 >= 0 and state.has_flag(src2, F_BUFFED), (
                    "spend-buff cost finalized with no buff")
                chain.spend_buff(state, table, seat, src2)
            if spec.cost_xp:
                assert state.xp[seat] >= spec.cost_xp, "XP cost underflow"
                state.xp[seat] -= spec.cost_xp
            if spec.cost_kill_self:
                # 204.1.b -- "Kill this" stands before the ':', so it is a COST
                # and is paid now, at finalization. The source is therefore
                # already dead while the ability sits on the Chain waiting to
                # resolve, and the opponent's response window happens over its
                # corpse. Routed through `combat.destroy` rather than clearing
                # P_ALIVE inline so the card reaches its trash and any
                # [Deathknell] on it fires -- a kill is a kill (427.2.a).
                src = int(state.chain[item, C_SRC])
                assert state.perms[src, P_ALIVE], "kill cost with no live source"
                combat.destroy(state, table, src)
        # 809.1.c -- "Spells and ABILITIES an opponent controls that choose me
        # cost {any rune} more." An ability pays the Deflect surcharge exactly
        # as a card does; it is mandatory, it is Power of any domain, and it is
        # owed for each time the ability chooses the unit. This used to be
        # charged at the card path only, so Ahri, Inquisitive's attack trigger
        # and Overzealous Fan's defend trigger chose a [Deflect] unit for free.
        #
        # Unaffordable is possible here in a way it is not for a card: a
        # triggered ability is not offered, it happens, and `_slot_options`
        # only drops the targets it cannot pay for while another choice remains
        # (355.8 would otherwise keep the ability off the Chain entirely). When
        # the choice was forced, the surcharge simply goes unpaid rather than
        # deadlocking a mandatory trigger.
        _n_t = spec.n_targets if spec is not None else 0
        _chosen = [int(x) for x in state.chain_targets[item, :_n_t]]
        _extra = rsv.deflect_cost(state, table, seat, _chosen, spec)
        if _extra:
            _sur = plan_surcharge(state, table, seat, card, _extra, reserved=())
            if _sur is not None:
                for _dom in _sur:
                    state.recycle_rune(seat, _dom)
        chain.finalize(state, item)
        state.priority = seat
        return {"finalized_ability": table.names[card]}
    spec_c = chain.item_spec(state, table, item)
    n_t = spec_c.n_targets if spec_c else 0
    chosen = [int(x) for x in state.chain_targets[item, :n_t]]
    # 809.1.d -- Deflect is a MANDATORY additional cost on the chooser, in
    # Power, of any domain (809.1.c.1). It is owed whether the card came from
    # hand or from hiding: 811.1.b zeroes the CARD's cost, not a surcharge
    # someone else's permanent imposes.
    extra_p = rsv.deflect_cost(state, table, seat, chosen, spec_c)
    if extra_p:
        from rl.engine.cost import surcharge_after_power_discounts
        extra_p = surcharge_after_power_discounts(state, table, seat, card, extra_p)
    cost_mode = int(state.chain[item, C_COST])
    paid_opt = int(state.chain[item, C_REPEAT]) in (2, 3) and spec_c is not None
    paid_free = paid_opt and spec_c.paid_ignores_cost
    # Energy actually paid to play this card, read BEFORE paying (the payment
    # spends the discounts it is computed from). "If you've spent {4 energy} or
    # more to play a spell" (Prepared Neophyte, Revna) asks exactly this.
    if cost_mode == COST_FLOW:
        spent_e = flow_energy(state, table, seat, card)
    elif (cost_mode in (COST_NO_ENERGY, COST_FREE)
          or int(state.chain[item, C_BOUND_BF]) >= 0):
        spent_e = 0
    elif paid_free:
        spent_e = 0
    else:
        spent_e = effective_energy(state, table, seat, card) + (
            max(0, repeat_cost(state, table, seat, card)[0])
            if int(state.chain[item, C_REPEAT]) in (1, 3) else 0)
    if cost_mode == COST_FLOW:
        # 829.1.c.1 -- the Flow cost REPLACES the base cost.
        recycle = plan_flow(state, table, seat, card)
        assert recycle is not None, "unaffordable Flow cost reached finalization"
        _fe, _fp = base_flow(state, table, seat, card)
        pay_ability_cost(state, table, seat, flow_energy(state, table, seat, card),
                         recycle, _fp, card)
        from rl.engine.cost import flow_uses_grant
        if flow_uses_grant(state, table, seat, card):
            _k = flow_grant_index(state, seat, card)
            if _k >= 0:
                state.flow_grant_card[seat, _k] = -1     # a granted play, spent
    elif cost_mode == COST_FREE:
        pass                               # paid (or free) before it was pushed
    elif cost_mode == COST_NO_ENERGY:
        # "ignoring its Energy cost. (You must still pay its Power cost.)" --
        # the reminder is on the card because the two halves are separable, and
        # the Power half is what keeps Fizz honest: a 3-Energy spell replayed
        # free still costs a rune off the board if it has a Power symbol.
        # `effective_power`, not the printed value: "you must still pay its
        # Power cost" means the cost it actually has, discounts included.
        _p = effective_power(state, table, seat, card)
        recycle = plan_ability_cost(state, table, seat, card, 0, _p)
        assert recycle is not None, "unaffordable Power cost reached finalization"
        pay_ability_cost(state, table, seat, 0, recycle, _p, card)
    elif int(state.chain[item, C_BOUND_BF]) < 0:
        # 811.1.b -- a card played from Hidden ignores its cost entirely. The
        # rune was already paid when it was hidden.
        # 820.1.c.1 -- a paid [Repeat] rides along as an Additional Cost, part
        # of the SAME payment rather than a second one, so it goes through
        # `plan_payment`'s extra_* arguments and shares the overlapping-pool
        # rule: max(energy, power) over the combined cost.
        re_e = re_p = 0
        _le, _lp = pending_leftover(state, table, seat, card)
        if int(state.chain[item, C_REPEAT]) in (1, 3):
            _rc = repeat_cost(state, table, seat, card)
            re_e, re_p = reduced_add_cost(state, table, seat,
                                          (max(0, _rc[0]), max(0, _rc[1])))
            _used_p = min(re_p, _lp)
            re_e, re_p = max(0, re_e - _le), max(0, re_p - _lp)
            _lp -= _used_p
        # ...and whatever Power it still has left pays a Deflect surcharge,
        # which is an additional cost of the same play (RiftJudge #11855).
        extra_p = max(0, extra_p - _lp)
        _td = TRASH_TAG_DISCOUNT.get(table.names[card])
        if _td is not None and spec_c is not None:
            for _slot_i, _t in enumerate(chosen):
                if (_slot_i < spec_c.n_targets and _t >= 0
                        and spec_c.targets[_slot_i].kind == TK_TRASH_CARD
                        and any(tg in table.tags[unpack_trash(_t)[1]]
                                for tg in _td[1])):
                    re_e -= _td[0]
                    break
        _mc = getattr(spec_for(table, card), "mode_costs", ()) if int(
            state.chain[item, C_ABIL]) < 0 else ()
        if _mc and 0 <= int(state.chain_targets[item, 0]) < len(_mc):
            # Curtain Call: the [Repeat] costs its chosen combination takes.
            re_e += _mc[int(state.chain_targets[item, 0])][0]
            re_p += _mc[int(state.chain_targets[item, 0])][1]
        if paid_opt and spec_c.opt_cost_power:
            # ADDED to whatever a paid [Repeat] already owes: with C_REPEAT 3
            # both additional costs are part of the one payment (820.1.c.1).
            _oe, _op = reduced_add_cost(state, table, seat,
                                        (0, spec_c.opt_cost_power))
            re_e, re_p = re_e + _oe, re_p + _op
        if paid_opt and spec_c.opt_cost_xp:
            assert int(state.xp[seat]) >= spec_c.opt_cost_xp, "XP cost underflow"
            state.xp[seat] -= spec_c.opt_cost_xp
        if paid_opt and spec_c.opt_cost_discard:
            _pay_discard_cost(state, table, seat,
                              Ability(TR_ACTIVATED,
                                      cost_discard=spec_c.opt_cost_discard))
        # Irelia - Graceful: "Your spells that choose me cost {1 energy} or
        # {any rune} less" -- one reduction per Irelia CHOSEN, counted by the
        # unit and not by the slot. A [Repeat] fills a second set of slots with
        # the same Irelia, and 820.1.c.1 makes both additional cost and base
        # cost one payment for one spell -- so her static applies once to it,
        # not once per repetition (RiftJudge #7074). Two Irelias chosen by the
        # same spell are two ability instances and do each reduce it.
        _irelias = set()
        for _slot_i, _t in enumerate(chosen):
            if (spec_c is not None and _slot_i < spec_c.n_targets
                    and spec_c.targets[_slot_i].kind == TK_UNIT and _t >= 0
                    and _t < state.n_perms and int(state.perms[_t, P_CTRL]) == seat
                    and table.names[int(state.perms[_t, P_CARD])] in CHOSEN_DISCOUNT):
                _irelias.add(int(_t))
        for _ in _irelias:
            if effective_energy(state, table, seat, card) + re_e > 0:
                re_e -= 1
            else:
                re_p -= 1
        # Sandswept Tomb: "each spell that chooses one or more units here that
        # are friendly to it costs {any rune} less". Once for the spell, not
        # once per unit -- "one or more" is the condition, not a count.
        from rl.engine.cost import bf_cost_rules as _bfcr
        if spec_c is not None and table.is_type(card, "Spell"):
            for _rule, _i in _bfcr(state, table, seat, "choose"):
                if any(_t >= 0 and _t < state.n_perms
                       and _si < spec_c.n_targets
                       and spec_c.targets[_si].kind == TK_UNIT
                       and int(state.perms[_t, P_CTRL]) == seat
                       and int(state.perms[_t, P_LOC]) == bf_loc(_i)
                       for _si, _t in enumerate(chosen)):
                    re_p -= _rule["n"]
                    break
        if not paid_free:
            recycle = plan_payment(state, table, seat, card, re_e, re_p)
            assert recycle is not None, "unaffordable spell reached finalization"
            pay(state, table, seat, card, recycle, re_e, re_p)
        elif re_e or re_p:
            # "If you do, ignore this SPELL's cost" buys off the card's own
            # cost and nothing else: another additional cost of the same play
            # is still owed, so a [Repeat] granted by The Academy still costs
            # its {3 energy} (RiftJudge #10272).
            recycle = plan_ability_cost(state, table, seat, card, re_e, re_p)
            assert recycle is not None, "unaffordable [Repeat] reached finalization"
            pay_ability_cost(state, table, seat, re_e, recycle, re_p, card)
    # Planned AFTER the card's own cost has been paid, so it allocates from
    # what is actually left rather than from a reservation that guessed at the
    # printed cost -- a paid [Repeat] or mode cost recycles more than that, and
    # the surcharge then named a domain that was already gone (real-deck fuzz
    # seed 672). The board here has the payment's recycles removed and its
    # exhausts still standing, which is exactly what may still be recycled
    # (164.2.b).
    if extra_p:
        surcharge = plan_surcharge(state, table, seat, card, extra_p, reserved=())
        assert surcharge is not None, "unaffordable Deflect cost at finalization"
        for dom in surcharge:
            state.recycle_rune(seat, dom)
    chain.finalize(state, item)
    # 349 -- the card is PLAYED now. [Legion] asks whether another card was
    # played this turn, so the count has to move at the same instant the rules
    # say the card was played, and not at resolution: a countered spell was
    # still played, and still turns Legion on for what follows.
    state.cards_played[seat] += 1
    if not table.is_token(card):
        state.played_types[seat] |= _played_bits(table, card)
    is_spell = bool(table.is_type(card, "Spell"))
    chain.card_played(state, table, seat, card, completed=not is_spell)
    # "When you play a spell" -- 419.4.a fires it when the play is COMPLETED by
    # resolution, not here, and a countered spell never fires it at all
    # (419.4.a.1). The item carries what those watchers will need to ask.
    # The counts above stay here: 419.4.b has non-triggered checks ([Legion])
    # read finalization, so a countered spell still counts for them.
    if is_spell:
        state.chain[item, C_PLAY_SPELL] = 1
        state.chain[item, C_SPENT_E] = min(int(spent_e), 32000)
        if not table.is_token(card):
            state.spells_played[seat] += 1
        if spent_e >= 4:
            state.big_spell_ply[seat] = int(state.ply)
        # Raging Firebrand's promise is spent by this spell, paid or not --
        # and so are Temporal Portal's and Ravenborn Tome's.
        state.next_spell_discount[seat] = 0
        state.next_spell_repeat_ply[seat] = -1
        if int(state.next_spell_bonus_ply[seat]) == int(state.ply):
            state.next_spell_bonus_ply[seat] = -1
            state.bonus_uid[seat] = int(state.chain[item, C_UID])
    # 337.1.a: the caster keeps priority, so they may respond to their own card.
    state.priority = seat
    return {"finalized": table.names[card],
            "targets": [int(x) for x in
                        state.chain_targets[item, :spec_for(table, card).n_targets]]}


def _activate(state: GameState, table: CardTable, cfg: Config, seat: int,
              perm: int) -> dict:
    """Put an activated ability on the Chain (151.2.a: like playing a card).

    Costs are paid at finalization, not here, exactly as a spell's are -- so an
    ability whose targets all become illegal before it finalizes is never paid
    for.
    """
    if is_legend_activate(perm):
        return _activate_legend(state, table, cfg, seat,
                                legend_ability_index(perm))
    perm, donor, k = unpack_activate(perm)
    # The SPEC comes from the donor; the SOURCE stays the activating permanent.
    # For an ordinary activation the two are the same permanent. `item_spec`
    # already reads C_CARD and C_SRC independently, so a borrowed ability needs
    # nothing new on the Chain.
    card = state.eff_card(donor)
    if donor == perm:
        # The arg carries the index, so two abilities on one permanent are two
        # distinguishable actions rather than one that always picks the first.
        idx = k
    else:
        # A BORROWED ability is selected by its Exhaust cost instead --
        # Heimerdinger has "all Exhaust abilities", so the cost is the filter
        # and there is nothing for an index to choose between. No card in the
        # pool prints two Exhaust abilities; if one does, this picks the first
        # and the assert in `pack_activate` is where that starts being wrong.
        idx = next(j for j, ab in enumerate(abilities_for(table, card))
                   if ab.trigger == TR_ACTIVATED and ab.cost_exhaust)
    _own = abilities_for(table, card)
    if donor == perm and idx >= len(_own):
        # An appended ability (Dominus's grant): its own card and index.
        card, idx = (int(x) for x in
                     appended_abilities(state, table, perm)[idx - len(_own)][:2])
        spec = appended_abilities(state, table, perm)[k - len(_own)][2]
    else:
        spec = abilities_for(table, card)[idx]
    assert spec.trigger == TR_ACTIVATED, (
        f"A_ACTIVATE named ability {idx} of {table.names[card]!r}, "
        f"which is not an activated ability")

    if spec.once_each_turn:
        state.once_used[perm] = int(state.ply)
    # "When you use an activated ability of a GEAR" -- Prize of Progress. Fired
    # as the ability is activated (151.2.a makes that the moment it is played),
    # not when it resolves, so a countered ability still counts as used.
    if table.is_type(card, "Gear"):
        chain.fire_watchers(state, table, seat, TR_GEAR_ABILITY, subj=perm)

    if spec.immediate and spec.cost_kill is None:
        # 337.2 -- a resource-adding ability resolves immediately and never
        # touches the Chain, so no window opens in which the opponent could
        # answer the resource before it exists.
        state.empower_src = perm
        e = ability_energy(state, table, seat, card, spec.cost_energy, spec)
        state.empower_src = -1
        recycle = plan_ability_cost(state, table, seat, card, e,
                                    spec.cost_power)
        assert recycle is not None, "unaffordable ability reached _activate"
        pay_ability_cost(state, table, seat, e, recycle,
                         spec.cost_power, card)
        if spec.cost_exhaust:
            state.perms[perm, P_READY] = 0
        # Paid at finalization like every other cost, so the status is already
        # gone when the ops run -- nothing in them may ask whether the source
        # is Empowered (383.2.c.2).
        if spec.cost_disempower_self:
            paid = state.disempower(perm)
            assert paid, "disempower cost reached _activate with no status"
        if spec.cost_discard:
            _pay_discard_cost(state, table, seat, spec)
        if spec.cost_spend_buff_self:
            assert state.has_flag(perm, F_BUFFED), "spend-buff with no buff"
            chain.spend_buff(state, table, seat, perm)
        ctx_loc = int(state.perms[perm, P_LOC])
        if spec.cost_xp:
            assert state.xp[seat] >= spec.cost_xp, "XP cost underflow"
            state.xp[seat] -= spec.cost_xp
        if spec.cost_kill_self:
            combat.destroy(state, table, perm)
        log = rsv.resolve(state, table, cfg, spec, seat, [], -1, False,
                          source=perm, ctx=ctx_loc)
        log["activated"] = table.names[card]
        return log

    item = chain.push(state, card, seat, from_hand=False, abil=idx, src=perm,
                      ctx=int(state.perms[perm, P_LOC]))
    # 820 -- a printed "kill a [...]" cost is chosen and paid before the
    # ability's own targets, and before it finalizes. Checked ahead of
    # `n_targets` for that reason, and ahead of the finalize below because an
    # ability with a cost and no targets (Escaped Grayback) would otherwise
    # finalize here and never stop to be paid for -- `_advance_pending` only
    # ever sees items that are still Pending.
    if spec.cost_kill is not None:
        state.pend_cost_kill = item
        return {"activated": table.names[card]}
    # 3956 -- chosen and paid before the ability's own targets, in the same
    # place and for the same reason as `cost_kill`: an ability with this cost
    # and no targets (Garbage Grabber) would otherwise finalize right here and
    # never stop to be paid for.
    if spec.cost_recycle_trash:
        state.pend_cost_recycle = item
        state.pend_cost_recycle_n = spec.cost_recycle_trash
        return {"activated": table.names[card]}
    if spec.n_targets:
        state.pend_slot = 0
        return {"activated": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _activate_legend(state: GameState, table: CardTable, cfg: Config,
                     seat: int, idx: int) -> dict:
    """Activate the seat's own Champion Legend (151.2, 107.4).

    The permanent path in `_activate` cannot be reused as-is: every line of it
    reads a `perms` row for the card, the exhaust flag and the context location,
    and a legend has none of those. What it DOES share is everything after the
    Chain -- targeting, finalization and resolution all work off `C_CARD` and
    `C_SRC`, and the legend source sentinel is just another `C_SRC`.

    `ctx` is -1 rather than a location: 107.4.b says the Legend Zone is not a
    location, so there is no "here" for the ability to have captured.
    """
    from rl.engine.effects import legend_abilities_live
    live = legend_abilities_live(state, table, seat)
    assert idx < len(live), "legend ability index out of range"
    card, _own_idx, spec = live[idx]
    idx = _own_idx

    if spec.immediate:
        # 337.2 -- the [Add] family resolves without touching the Chain.
        e = ability_energy(state, table, seat, card, spec.cost_energy, spec)
        recycle = plan_ability_cost(state, table, seat, card, e,
                                    spec.cost_power)
        assert recycle is not None, "unaffordable legend ability reached activate"
        pay_ability_cost(state, table, seat, e, recycle,
                         spec.cost_power, card)
        if spec.cost_exhaust:
            state.legend_ready[seat] = 0
        if spec.cost_disempower_self:
            paid = state.src_disempower(legend_src(seat))
            assert paid, "disempower cost reached a legend with no status"
        if spec.cost_xp:
            state.xp[seat] -= spec.cost_xp
        log = rsv.resolve(state, table, cfg, spec, seat, [], -1, False,
                          source=legend_src(seat), ctx=-1)
        log["activated"] = table.names[card]
        return log

    item = chain.push(state, card, seat, from_hand=False, abil=idx,
                      src=legend_src(seat), ctx=-1)
    if spec.n_targets:
        state.pend_slot = 0
        return {"activated": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _accept_may(state: GameState, table: CardTable, cfg: Config) -> dict:
    """383.3.a -- perform the optional Triggered Ability: carry on finalizing."""
    item = int(state.pend_may)
    state.pend_may = -1
    spec = chain.item_spec(state, table, item)
    if spec.opt_cost_energy or spec.opt_cost_power:
        card = int(state.chain[item, C_CARD])
        recycle = plan_ability_cost(state, table, seat_of := int(
            state.chain[item, C_CTRL]), card,
            spec.opt_cost_energy, spec.opt_cost_power)
        assert recycle is not None, "unaffordable optional cost was offered"
        pay_ability_cost(state, table, seat_of, spec.opt_cost_energy, recycle,
                         spec.opt_cost_power, card)
    # "You may KILL ME to ..." -- paid here, before targets are chosen, because
    # it is a cost and not the first op. The source is dead for the rest of the
    # ability, which 383.2.c.2 already handles.
    if spec.opt_cost_exhaust_self:
        src = int(state.chain[item, C_SRC])
        if is_legend_src(src):
            who = legend_src_seat(src)
            assert int(state.legend_ready[who]) == 1, (
                "an optional exhaust cost offered on an exhausted legend")
            state.legend_ready[who] = 0
        else:
            assert src >= 0 and state.perms[src, P_READY] == 1, (
                "an optional exhaust cost offered on an exhausted source")
            state.perms[src, P_READY] = 0
    if spec.opt_cost_discard:
        phases.discard(state, table, int(state.chain[item, C_CTRL]),
                       spec.opt_cost_discard)
    if spec.opt_cost_xp:
        who = int(state.chain[item, C_CTRL])
        assert int(state.xp[who]) >= spec.opt_cost_xp, "optional XP cost underflow"
        state.xp[who] -= spec.opt_cost_xp
    if spec.opt_cost_banish_self:
        src = int(state.chain[item, C_SRC])
        assert src >= 0 and state.perms[src, P_ALIVE] == 1, (
            "an optional banish cost offered with no source")
        combat.banish(state, table, src)
    if spec.opt_cost_kill_self:
        src = int(state.chain[item, C_SRC])
        assert src >= 0, "an optional kill-self cost with no source to kill"
        combat.destroy(state, table, src)
    # "You may [Burn 1] to ..." -- a cost paid in cards, at the same moment the
    # kill above is paid. Running the deck out while paying is a Burn Out
    # (431.2) and costs a point, which `phases.burn` handles.
    if spec.opt_cost_burn:
        # The controller read fresh, not the walrus above: that one is bound
        # only inside the rune-cost branch, and a card can print this cost
        # without printing that one.
        phases.burn(state, int(state.chain[item, C_CTRL]), spec.opt_cost_burn)
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
             slot: int) -> dict:
    """Hide the pending card in facedown `slot` for one rune (811.1.b).

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

    # 811.1.b's cost is [A] -- one POWER of any Domain, which a rune pays by
    # being RECYCLED (164.2.b), not by being exhausted. Hiding therefore costs
    # the rune outright; it is not a tap that comes back next turn. See
    # `cost.plan_wild_power`.
    # ...unless Guerilla Warfare has made hiding free for the turn (#6655).
    if int(state.free_hide_ply[seat]) != int(state.ply):
        recycle = plan_wild_power(state, seat, 1)
        assert recycle is not None, "unaffordable Hide reached _hide_at"
        pay_wild_power(state, seat, 1, recycle)

    state.fd_owner[slot] = seat
    state.fd_card[slot] = card
    state.fd_ply[slot] = int(state.ply)
    # "When you hide a card, ready me" (Katarina - Reckless). Hiding opens no
    # Chain of its own (811.1.c.2), but a triggered ability it causes is an
    # ordinary Chain Item like any other -- the restriction is on the Hide,
    # not on what watches it.
    chain.fire_watchers(state, table, seat, TR_HIDE)
    return {"hid_at": fd_bf(slot)}


def _play_flow(state: GameState, table: CardTable, cfg: Config, seat: int,
               trash_idx: int) -> dict:
    """829.1.b -- play a spell from the trash for its Flow cost.

    The card leaves the trash now, exactly as a hand card leaves the hand on
    announcement. Where it goes AFTER resolving is the interesting part, and
    that is `resolve_top`'s job: banished, not trashed.
    """
    card = int(state.trash[seat, trash_idx])
    got = TRASH_UNIT_PLAY.get(table.names[card])
    if got is None and int(state.riches_on[seat]) and (
            table.is_type(card, "Unit") or table.is_type(card, "Gear")):
        got = (int(table.energy[card]), 0)       # Endless Riches: its own cost
    if got is not None:
        # A unit: it waits in the trash while the destination is chosen.
        state.rp_seat, state.rp_owner, state.rp_card = seat, seat, card
        state.rp_cost = COST_PRINTED
        state.rp_discount = int(table.energy[card]) - got[0]
        state.rp_power, state.rp_zone = got[1], 1
        state.rp_here, state.rp_empower, state.rp_from_sarc = -1, 0, 0
        return {"announced_from_trash": table.names[card]}
    n = int(state.n_trash[seat])
    state.trash[seat, trash_idx:n - 1] = state.trash[seat, trash_idx + 1:n]
    state.trash[seat, n - 1] = -1
    state.n_trash[seat] = n - 1

    # 829.1.b's banish is [Flow]'s; Death from Below's bare permission to
    # replay itself sends it back to the trash (`flow_grant_banish`).
    _k = flow_grant_index(state, seat, card) if int(table.flow_energy[card]) < 0 else -1
    _dest = (DEST_BANISH if _k < 0 or int(state.flow_grant_banish[seat, _k])
             else DEST_TRASH)
    item = chain.push(state, card, seat, from_hand=False, bound_bf=-1,
                      cost=COST_FLOW, dest=_dest)
    spec = spec_for(table, card)
    assert spec is not None
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced_from_trash": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _play_from_hidden(state: GameState, table: CardTable, cfg: Config,
                      seat: int, slot: int) -> dict:
    """Play the facedown card in `slot` for 0 energy (811.1.b).

    The argument is a facedown SLOT, and `fd_bf` turns it into the battlefield
    the card was hidden at -- which is what binds its targets and where a
    permanent lands. Bandle Tree is why the two are no longer the same number.

    Its bound target slots are restricted to that battlefield (811.1.d.2.a),
    which is carried on the chain item as `C_BOUND_BF` -- free slots ignore it,
    which is why Smoke and Mirrors still reaches across the board.

    **A PERMANENT takes the other path entirely.** 337.2 keeps units and gear
    off the Chain, so one played from hiding goes straight onto the board --
    and 811.1.d.1 says where: the battlefield it was hidden at, with no
    destination choice at all (811.1.d.1.a extends that to gear, overriding
    the base-only rule). That is strictly simpler than the hand path, which
    has to offer `pend_play`.
    """
    bf = fd_bf(slot)
    card = int(state.fd_card[slot])
    assert int(state.fd_owner[slot]) == seat, "not this seat's facedown card"
    state.fd_owner[slot] = -1
    state.fd_card[slot] = -1
    state.fd_ply[slot] = -1

    # "When you play a card from face down, ..." (Black Market Broker,
    # Katarina - Reckless, Ember Monk). The watchers say "a card", so they
    # cover a spell and a permanent alike -- but 419.4.a decides WHEN, and the
    # two paths differ: 337.2 resolves a permanent as it finalizes, so its play
    # is complete right here, while a spell's is not complete until it resolves
    # and is never complete if it is countered (419.4.a.1, RiftJudge #8491).
    # The spell path therefore defers both to `chain.spell_resolved`, which is
    # where every other "when you play" watcher already waits.
    if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
        chain.fire_watchers(state, table, seat, TR_PLAY_FROM_HIDDEN)
        # The Facedown Zone is "anywhere other than your hand" too (811.1.a
        # moved the card out of the hand when it was hidden).
        chain.fire_watchers(state, table, seat, TR_PLAY_NONHAND)
        return _resolve_play_from_hidden(state, table, cfg, seat, card, bf)

    item = chain.push(state, card, seat, from_hand=False, bound_bf=bf)
    spec = spec_for(table, card)
    assert spec is not None
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced_from_hidden": table.names[card], "at": bf}
    return _finalize_pending(state, table, cfg, item)


def _resolve_play_from_hidden(state: GameState, table: CardTable, cfg: Config,
                              seat: int, card: int, bf: int) -> dict:
    """Put a permanent played from hiding onto its bound battlefield.

    `_resolve_play`'s counterpart for the Facedown Zone. It cannot share that
    function: this card was never in hand, so there is no hand index to
    remove, and 811.1.b waives the cost entirely rather than discounting it.
    What it must keep in step is everything AFTER the card lands -- the
    [Legion] snapshot, the played-type bits, the play-unit watchers and the
    TR_PLAY_ME trigger all behave exactly as they do from hand (811.2:
    "abilities and instructions of hidden cards other than the choices listed
    above function as normal").
    """
    loc = bf_loc(bf)
    is_unit = bool(table.is_type(card, "Unit"))
    legion = bool(state.cards_played[seat])
    state.cards_played[seat] += 1
    if not table.is_token(card):
        state.played_types[seat] |= _played_bits(table, card)
    chain.card_played(state, table, seat, card, completed=False)
    # 359.2.c/d as usual -- units enter exhausted, gear ready. [Accelerate] is
    # not reachable here: it is an optional ADDITIONAL cost paid as the card is
    # played (805.2), and 811.1.b waives the base cost without offering one.
    enters_ready = (_permanent_enters_ready(state, table, seat, card, is_unit)
                    or table.names[card] in ENTERS_READY_AT_BF)   # always a bf
    loc = combat.baron_pit_entry(state, table, card, loc)   # Baron Nashor
    src = state.add_permanent(card, seat, loc, ready=enters_ready,
                              is_unit=is_unit)
    if legion:
        state.perms[src, P_FLAGS] |= F_LEGION
    # What makes "when you play me FROM FACE DOWN" answerable, and what binds
    # this permanent's play-effect targets to `bf` (811.1.d.2) -- see
    # `chain.place`.
    state.perms[src, P_FLAGS] |= F_FROM_HIDDEN
    chain.fire_nth_card(state, table, seat, card)   # 419.4.a: once it is on the board
    chain.fire_play_unit(state, table, seat, card, src)
    if chain.has_trigger(table, card, TR_PLAY_ME):
        chain.queue(state, TR_PLAY_ME, src, loc)
        return {"played_from_hidden": table.names[card], "at": loc}
    return combat.cleanup(state, table, cfg, mover=seat, dst=loc)


def _answer_altar(state: GameState, table: CardTable, cfg: Config,
                  pay: bool) -> dict:
    """Altar of Blood's replacement, taken or declined.

    Paying replaces the death outright (136.2.d), so nothing about the unit
    dying happens: no Deathknell, nothing reaches a trash, and "when another
    friendly unit dies" never fires. What it gets instead is the card's three
    instructions in order -- healed, exhausted, recalled -- and a Recall is not
    a Move (456.1), so no move trigger fires and it does not conquer anything
    on the way home.

    Declining kills it for real. The per-row stamp set when the offer was made
    is what keeps `_destroy` from asking the same question again.
    """
    from rl.engine.cost import pay_wild_power, plan_wild_power
    from rl.engine.effects import BF_DEATH_REPLACEMENT
    from rl.engine.state import P_DMG, bf_index
    perm = int(state.pend_altar)
    state.pend_altar = -1
    if perm < 0 or state.perms[perm, P_ALIVE] != 1:
        return {}
    seat = int(state.perms[perm, P_CTRL])
    loc = int(state.perms[perm, P_LOC])
    card = int(state.bf_card[bf_index(loc)]) if is_battlefield(loc) else -1
    cost = BF_DEATH_REPLACEMENT.get(table.names[card], 0) if card >= 0 else 0
    if not pay or not cost:
        combat._destroy(state, table, perm)
        return {"altar": "declined"}
    plan = plan_wild_power(state, seat, cost)
    assert plan is not None, "an unaffordable Altar offer was accepted"
    pay_wild_power(state, seat, cost, plan)
    state.perms[perm, P_DMG] = 0
    state.perms[perm, P_READY] = 0
    state.set_location(perm, base_loc(seat))
    return {"altar": "paid", "saved": perm}


def _assign_damage_pick(state: GameState, table: CardTable, cfg: Config,
                        perm: int) -> dict:
    """Record one combat-damage kill, or stop assigning (`perm` < 0).

    465.2.c.2 -- the player dealing the damage chooses who dies. Collected one
    unit at a time rather than as a subset, which keeps the action space the
    size of the board instead of 2**board, and makes the ordering keywords fall
    out for free: `combat.dmg_legal_kills` only ever offers the lowest tier
    that still holds a live target.

    Nothing reaches the board here. Both seats' choices are held in
    `pend_dmg_kills` until every seat has answered, because 465.3 deals the
    damage simultaneously -- marking the first seat's kills now would let the
    second answer while reading them.
    """
    seat = int(state.pend_dmg)
    if perm >= 0:
        assert perm in combat.dmg_legal_kills(state, table, seat), \
            "damage assignment picked an illegal target"
        n = int(state.pend_dmg_n_kill[seat])
        state.pend_dmg_kills[seat, n] = perm
        state.pend_dmg_n_kill[seat] = n + 1
    else:
        # Declining ends THIS seat's assignment, not the whole step.
        state.pend_dmg_done[seat] = 1
    state.pend_dmg = -1
    log = combat.advance_combat(state, table, cfg,
                               {"combat_at": int(state.showdown_bf)}) \
        if state.showdown_bf >= 0 else {}
    if state.showdown_bf < 0:
        # That Combat finished -- resolve any Combat still staged at the other
        # battlefield, exactly as the Showdown-Step resume does.
        log.update(combat.cleanup(state, table, cfg, mover=-1, dst=-1))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _resolve_play(state: GameState, table: CardTable, cfg: Config,
                  seat: int, loc: int, fast: bool = False) -> dict:
    """Pay for the pending card and put it on the board.

    Units enter **exhausted** unless `[Accelerate]` was paid, so a unit played to
    a Battlefield cannot move again this turn and is locked there through the
    opponent's turn. That is the commitment, and it is why playing onto an empty
    Battlefield is a different decision from moving onto one.
    """
    idx = state.pend_play
    card = played_card(state, seat, idx)
    extra = optional_add_cost(table, card) if fast else None
    assert not fast or extra is not None, \
        "paid an optional additional cost on a card that prints none"
    ee, ep = reduced_add_cost(state, table, seat, extra) if extra else (0, 0)
    # Dragon Roost: choosing the ground it sells IS choosing to pay for it, so
    # the cost rides the destination rather than the `fast` flag -- and it adds
    # to whatever `fast` bought, because they buy different things.
    _paid_dst = bf_paid_destination(state, table, seat, card)
    if _paid_dst is not None and loc == _paid_dst[0]:
        ee += _paid_dst[1][0]
        ep += _paid_dst[1][1]
    ee -= int(state.kill_disc_e)
    ep -= int(state.kill_disc_p)
    state.kill_disc_e = state.kill_disc_p = 0
    # WHICH cost was paid decides what it bought. [Accelerate] buys entering
    # ready (805.6); a printed one buys a clause in the card's own text, read
    # later through `F_PAID_ADDITIONAL`. Both are `fast`, and conflating them
    # would have every one of these six units enter ready as well.
    accelerated = fast and (accelerate_cost(table, card) is not None
                            or table.names[card] in PAID_COST_ENTERS_READY)
    recycle = plan_payment(state, table, seat, card, ee, ep)
    assert recycle is not None, "unaffordable card reached _resolve_play"
    pay(state, table, seat, card, recycle, ee, ep)
    if (int(state.free_gear_ply[seat]) == int(state.ply)
            and table.is_type(card, "Gear") and int(table.energy[card]) <= 7):
        state.free_gear_ply[seat] = -1          # Jayce's promise, spent
    if fast and table.names[card] in PLAY_COSTS_LEGEND:
        assert int(state.legend_ready[seat]), "exhausting an exhausted legend"
        state.legend_ready[seat] = 0
    if fast and table.names[card] in PLAY_COSTS_XP:
        xp_cost = PLAY_COSTS_XP[table.names[card]]
        assert int(state.xp[seat]) >= xp_cost, "XP additional cost underflow"
        state.xp[seat] -= xp_cost

    _take_played_card(state, seat, idx)
    state.pend_play = -1
    state.pend_play_seat = -1
    if fast and table.names[card] in PLAY_COSTS_DISCARD:
        # "Discard 1" -- ANOTHER card, so only after this one has left the
        # hand (discarding first once threw away the card being played).
        assert int(state.n_hand[seat]) >= 1, "discard cost with an empty hand"
        phases.discard(state, table, seat, 1)
    # Consumed: `play_destinations` must never read a stale location from a
    # PAST play once this one has landed, or a later probe of Stalking Wolf's
    # destinations (e.g. `ambush_playable` deciding whether to offer it at
    # all) would credit a battlefield nothing was just killed at.
    _ks = spec_for(table, card)
    paid_kill = bool(_ks is not None and _ks.cost_kill_optional
                     and int(state.pend_kill_play_loc) >= 0)
    state.pend_kill_play_loc = -1

    # 359.2.c -- units enter exhausted, unless [Accelerate] was paid. 805.6 is
    # precise that this is a REPLACEMENT: the unit "does not enter exhausted and
    # then become ready", so nothing that watches for a unit becoming ready
    # fires (805.6.a). Passing `ready=True` rather than readying afterwards is
    # what implements that distinction.
    #
    # 359.2.d -- non-unit Gear enters READY at its controller's base instead.
    is_unit = bool(table.is_type(card, "Unit"))
    # Counted BEFORE the permanent enters, so the [Legion] snapshot taken by
    # `add_permanent` asks "another card", not "any card including me". 337.2
    # gives a unit no finalization step to hang this on, so this is the moment
    # the card is played.
    legion = bool(state.cards_played[seat])
    state.cards_played[seat] += 1
    # A token IS played (187) but is never a "non-token unit"; Swain's clause
    # asks for the non-token kind, so tokens are excluded here rather than at
    # the point the condition is read.
    if not table.is_token(card):
        state.played_types[seat] |= _played_bits(table, card)
    chain.card_played(state, table, seat, card, completed=False)
    enters_ready = (accelerated
                    or _permanent_enters_ready(state, table, seat, card, is_unit)
                    or (table.names[card] in ENTERS_READY_AT_BF
                        and is_battlefield(loc)))
    loc = combat.baron_pit_entry(state, table, card, loc)   # Baron Nashor
    src = state.add_permanent(card, seat, loc, ready=enters_ready,
                              is_unit=is_unit)
    if legion:
        state.perms[src, P_FLAGS] |= F_LEGION
    # Snapshotted for the same reason [Legion] is: "when you play me, IF YOU
    # PAID the additional cost" resolves a priority window later, and by then
    # nothing else records that the payment happened.
    if fast and accelerate_cost(table, card) is None:
        state.perms[src, P_FLAGS] |= F_PAID_ADDITIONAL
    if paid_kill:
        state.perms[src, P_FLAGS] |= F_PAID_ADDITIONAL
    # "When you play a unit" watchers -- Lillia. Queued after the permanent is
    # on the board, so a watcher that is itself the unit being played sees a
    # consistent board.
    chain.fire_nth_card(state, table, seat, card)   # 419.4.a: once it is on the board
    chain.fire_play_unit(state, table, seat, card, src)

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


def _resolve_play_from_look(state: GameState, table: CardTable, cfg: Config,
                            loc: int) -> dict:
    """Banish Nocturne out of the look buffer and play him for [A] (108.6).

    The third zone a permanent can be played from, after hand and Facedown, and
    the only one where the play happens *inside* another decision: `pend_look`
    stays set throughout, so `_settle_after_decision`'s own `pend_look < 0`
    guard correctly defers the Cleanup to `_finish_look`. A unit arriving on
    contested ground therefore stages its Combat now and initiates it once the
    rest of the buffer has landed, which is the same ordering a token played
    by a resolving spell already gets.

    **He leaves the buffer, so the look's instruction never reaches him.**
    "Put the rest into your trash" is carried out on what is left; a Nocturne
    that was played is not among the rest. Compacting is what makes that true
    for `_finish_look`, which sends every remaining slot somewhere.
    """
    seat = int(state.pend_look)
    i = int(state.pend_play_look)
    card = int(state.look_cards[i])
    n_wild = play_from_look_cost(table, card)
    assert n_wild >= 0, "played a card from a look that prints no permission"

    # 811.1.b's cost and this one are the same symbol: [A] is POWER, so a rune
    # is RECYCLED, not exhausted. `plan_wild_power` gated the offer; re-planning
    # here rather than carrying the plan keeps the payment reading off the board
    # as it stands now.
    recycle = plan_wild_power(state, seat, n_wild)
    assert recycle is not None, "unaffordable look-play reached resolution"
    pay_wild_power(state, seat, n_wild, recycle)

    n = int(state.n_look)
    state.look_cards[i:n - 1] = state.look_cards[i + 1:n]
    state.look_cards[n - 1] = -1
    state.n_look = n - 1
    state.pend_play_look = -1
    # The errata's step that the printed card does not have: he is BANISHED
    # first, and the play happens out of Banishment (108.6) rather than out of
    # the look buffer. Written and popped rather than skipped, so the zone the
    # card is played from is the one the card names -- anything that comes to
    # watch a banish will find the transition here instead of a card that
    # teleported from a buffer to the board.
    state.banish_card(seat, card)
    state.n_banished[seat] -= 1
    state.banished[seat, int(state.n_banished[seat])] = -1
    # A look that held nothing but him has nothing left to ask about. Clearing
    # `pend_look` here rather than leaving an empty buffer pending is what stops
    # `legal_actions` hitting its "a look with nothing to pick" assert.
    if state.n_look == 0:
        state.pend_look = -1

    # Everything below is `_resolve_play`'s tail, and for the same reasons --
    # see there. What differs is only where the card came from and what it cost.
    is_unit = bool(table.is_type(card, "Unit"))
    legion = bool(state.cards_played[seat])
    state.cards_played[seat] += 1
    if not table.is_token(card):
        state.played_types[seat] |= _played_bits(table, card)
    chain.card_played(state, table, seat, card, completed=False)
    enters_ready = (_permanent_enters_ready(state, table, seat, card, is_unit)
                    or (table.names[card] in ENTERS_READY_AT_BF
                        and is_battlefield(loc)))
    loc = combat.baron_pit_entry(state, table, card, loc)   # Baron Nashor
    src = state.add_permanent(card, seat, loc, ready=enters_ready,
                              is_unit=is_unit)
    if legion:
        state.perms[src, P_FLAGS] |= F_LEGION
    chain.fire_nth_card(state, table, seat, card)   # 419.4.a: once it is on the board
    chain.fire_play_unit(state, table, seat, card, src)
    if chain.has_trigger(table, card, TR_PLAY_ME):
        chain.queue(state, TR_PLAY_ME, src, loc)
    log = {"played_from_look": table.names[card], "at": loc}
    # If he emptied the buffer the look is over and `_finish_look` will never
    # run, so its two tail steps have to happen here instead: the card's own
    # follow-up ("...then draw 1"), and the settle -- without which a Combat
    # his arrival staged sits uninitiated and 460/461 is violated. With cards
    # still in the buffer both are deferred by design, the settle by its own
    # `pend_look` guard and the follow-up by not being called at all.
    if state.pend_look < 0:
        log.update(_run_followup(state, table, cfg, seat))
    log.update(_settle_after_decision(state, table, cfg))
    return log


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


def _finish_mulligan(state: GameState, table: CardTable, cfg: Config) -> dict:
    """Perform this seat's Mulligan, then hand off or begin the game (117)."""
    seat = int(state.pend_mull)
    chosen = [i for i in range(int(state.n_hand[seat]))
              if int(state.mull_mask) >> i & 1]
    recycled = phases.mulligan(state, seat, chosen)
    state.mull_mask = 0
    if seat + 1 < N_SEATS:
        state.pend_mull = seat + 1
        return {"mulliganed": [table.names[c] for c in recycled]}
    # 118 -- both players are done, so the First Player takes their turn.
    state.pend_mull = -1
    state.active = 0
    log = phases.start_turn(state, table, cfg)
    log["mulliganed"] = [table.names[c] for c in recycled]
    return log


def _discard_cost_rows(state: GameState, table: CardTable, seat: int,
                       ab) -> list[int] | None:
    """Hand indices a "Discard N [type]" cost would take, or None if short.

    The oldest matching cards: which card is a real choice the action space
    does not offer yet, the same approximation `phases.discard` makes."""
    idx = [j for j in range(int(state.n_hand[seat]))
           if not ab.cost_discard_type
           or table.is_type(int(state.hand[seat, j]), ab.cost_discard_type)]
    return idx[:ab.cost_discard] if len(idx) >= ab.cost_discard else None


def _pay_discard_cost(state: GameState, table: CardTable, seat: int, ab) -> None:
    rows = _discard_cost_rows(state, table, seat, ab)
    assert rows is not None, "a discard cost reached payment unaffordable"
    cards = []
    for j in sorted(rows, reverse=True):
        n = int(state.n_hand[seat])
        c = int(state.hand[seat, j])
        state.hand[seat, j:n - 1] = state.hand[seat, j + 1:n]
        state.hand[seat, n - 1] = -1
        state.n_hand[seat] = n - 1
        phases._to_trash(state, seat, c)
        cards.append(c)
    chain.fire_watchers(state, table, seat, TR_DISCARD)
    chain.fire_discarded(state, table, seat, cards)


def _hand_play_cost(state: GameState, table: CardTable, seat: int, card: int):
    """(energy extra, power extra) passed to `plan_payment` for an effect play,
    or None when the play costs nothing at all."""
    mode = int(state.hp_cost)
    if mode == COST_FREE:
        return None
    if mode == COST_NO_ENERGY:
        return (-effective_energy(state, table, seat, card), 0)
    return (-int(state.hp_discount), 0)


def _rplay_extra(state: GameState, table: CardTable, seat: int, card: int):
    """(energy, power) extra for `plan_payment`, or None when free."""
    mode = int(state.rp_cost)
    if mode == COST_FREE:
        return None
    if mode == COST_NO_ENERGY:
        return (-effective_energy(state, table, seat, card), 0)
    return (-int(state.rp_discount), int(state.rp_power))


def _rplay_affordable(state: GameState, table: CardTable, seat: int,
                      card: int) -> bool:
    extra = _rplay_extra(state, table, seat, card)
    return extra is None or plan_payment(state, table, seat, card,
                                         extra[0], extra[1]) is not None


def _rplay_dests(state: GameState, table: CardTable, seat: int,
                 card: int) -> list[int]:
    if not table.is_type(card, "Unit"):
        return [base_loc(seat)]                       # gear lands at base (149.2)
    out = [base_loc(seat)] + [
        bf_loc(b) for b in state.live_bfs() if int(state.bf_ctrl[b]) == seat
        and not combat.bf_forbids_play(state, table, bf_loc(b))]
    here = int(state.rp_here)
    if here >= 0 and here not in out:
        out.append(here)                             # "you may play it here"
    return out


def _rplay_ok(state: GameState, table: CardTable, seat: int, card: int) -> bool:
    return (_rplay_affordable(state, table, seat, card)
            and bool(_rplay_dests(state, table, seat, card)))


def dj_candidates(state: GameState, table: CardTable) -> list[int]:
    """What the Divine Judgment chooser may still keep in this category."""
    s_, cat = int(state.dj_seat), int(state.dj_cat)
    if cat in (0, 1):
        kind = "Unit" if cat == 0 else "Gear"
        return [i for i in range(state.n_perms)
                if state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == s_
                and table.is_type(int(state.perms[i, P_CARD]), kind)
                and not int(state.dj_keep[i])]
    if cat == 2:
        have = state.runes_in_play(s_)
        return [d for d in range(len(have))
                if int(have[d]) > int(state.dj_rune_keep[s_, d])]
    return [j for j in range(int(state.n_hand[s_])) if not int(state.dj_hand_keep[s_, j])]


def _dj_kept(state: GameState, table: CardTable) -> int:
    s_, cat = int(state.dj_seat), int(state.dj_cat)
    if cat in (0, 1):
        kind = "Unit" if cat == 0 else "Gear"
        return sum(1 for i in range(state.n_perms)
                   if state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == s_
                   and table.is_type(int(state.perms[i, P_CARD]), kind)
                   and int(state.dj_keep[i]))
    if cat == 2:
        return int(state.dj_rune_keep[s_].sum())
    return int(state.dj_hand_keep[s_].sum())


def _dj_settle_category(state: GameState, table: CardTable) -> None:
    """Skip categories (and seats) with no real choice; finish when done."""
    while state.dj_seat >= 0:
        cands = dj_candidates(state, table)
        if _dj_kept(state, table) < 2 and cands and not (
                _dj_kept(state, table) + len(cands) <= 2):
            return                                  # a real choice to make
        for v in cands:                             # keep all that remain
            if _dj_kept(state, table) >= 2:
                break
            _dj_keep_one(state, v)
        state.dj_cat += 1
        if int(state.dj_cat) > 3:
            nxt = 1 - int(state.dj_seat)
            if nxt == int(state.dj_first):
                _dj_finish(state, table)
                return
            state.dj_seat, state.dj_cat = nxt, 0


def _dj_keep_one(state: GameState, v: int) -> None:
    s_, cat = int(state.dj_seat), int(state.dj_cat)
    if cat in (0, 1):
        state.dj_keep[v] = 1
    elif cat == 2:
        state.dj_rune_keep[s_, v] += 1
    else:
        state.dj_hand_keep[s_, v] = 1


def dj_begin(state: GameState, table: CardTable, seat: int) -> None:
    state.dj_seat, state.dj_first, state.dj_cat = seat, seat, 0
    state.dj_keep[:] = 0
    state.dj_rune_keep[:] = 0
    state.dj_hand_keep[:] = 0
    _dj_settle_category(state, table)


def dj_pick(state: GameState, table: CardTable, cfg: Config, v: int) -> dict:
    _dj_keep_one(state, v)
    if _dj_kept(state, table) >= 2:
        state.dj_cat += 1
        if int(state.dj_cat) > 3:
            nxt = 1 - int(state.dj_seat)
            if nxt == int(state.dj_first):
                _dj_finish(state, table)
                return _settle_after_decision(state, table, cfg)
            state.dj_seat, state.dj_cat = nxt, 0
    _dj_settle_category(state, table)
    if state.dj_seat < 0:
        return _settle_after_decision(state, table, cfg)
    return {"kept": v}


def _dj_finish(state: GameState, table: CardTable) -> None:
    """Recycle everything not kept, for both players."""
    state.dj_seat = -1
    for i in range(state.n_perms):
        c = int(state.perms[i, P_CARD])
        if (state.perms[i, P_ALIVE] == 1 and not int(state.dj_keep[i])
                and (table.is_type(c, "Unit") or table.is_type(c, "Gear"))):
            owner = int(state.perms[i, P_OWNER])
            combat.queue_leaves_board(state, table, i)
            state.perms[i, P_ALIVE] = 0
            if not table.is_token(c):
                state.recycle_card(owner, c)
    for s_ in range(N_SEATS):
        have = state.runes_in_play(s_).copy()
        for d in range(len(have)):
            for _ in range(int(have[d]) - int(state.dj_rune_keep[s_, d])):
                state.recycle_rune(s_, d)
        n = int(state.n_hand[s_])
        keep = [int(state.hand[s_, j]) for j in range(n) if int(state.dj_hand_keep[s_, j])]
        gone = [int(state.hand[s_, j]) for j in range(n) if not int(state.dj_hand_keep[s_, j])]
        state.hand[s_, :] = -1
        state.hand[s_, :len(keep)] = keep
        state.n_hand[s_] = len(keep)
        for c in gone:
            state.recycle_card(s_, c)
    state.dj_keep[:] = 0
    state.dj_rune_keep[:] = 0
    state.dj_hand_keep[:] = 0
    state.dj_first, state.dj_cat = -1, 0


def pf_open_look(state: GameState, seat: int) -> bool:
    """Promising Future: `seat` looks at its top 5 and banishes one."""
    ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
    take = min(5, end - ptr)
    if take <= 0:
        return False
    state.look_cards[:] = -1
    state.look_cards[:take] = state.deck[seat, ptr:ptr + take]
    state.n_look = take
    state.deck_ptr[seat] = ptr + take
    state.look_pick_dest, state.look_rest_dest = DEST_BANISH, DEST_RECYCLE
    state.look_optional, state.look_multi = 0, 0
    state.look_min_energy, state.look_type_mask = 0, 0
    state.pend_look = seat
    state.rp_armed = 2
    return True


def pf_advance(state: GameState, table: CardTable, done_seat: int) -> None:
    """The next step of Promising Future after `done_seat` finished one."""
    first = int(state.pf_first)
    other = 1 - first
    if int(state.pf_stage) == 1:
        if done_seat == first and pf_open_look(state, other):
            return
        state.pf_stage = 2
    pf_try_play(state, table)


def pf_try_play(state: GameState, table: CardTable) -> None:
    """Open the next Promising Future play once nothing else is being decided
    (a spell just cast from it chooses its targets first)."""
    if int(state.pf_stage) != 2 or state.rp_seat >= 0 or state.pend_slot >= 0 \
            or state.pend_cost_kill >= 0 or state.pend_may >= 0 \
            or chain.oldest_pending(state) >= 0 or chain.decision_open(state):
        return
    first = int(state.pf_first)
    for s_ in (1 - first, first):         # "starting with the next player"
        c = int(state.pf_cards[s_])
        state.pf_cards[s_] = -1
        if c >= 0:
            state.rp_seat, state.rp_owner, state.rp_card = s_, s_, c
            state.rp_cost, state.rp_discount, state.rp_power = COST_NO_ENERGY, 0, 0
            state.rp_here, state.rp_empower, state.rp_zone = -1, 0, 0
            state.rp_from_sarc = 0
            return
    state.pf_stage, state.pf_first = 0, -1


def _rplay_accel_ok(state: GameState, table: CardTable, seat: int, card: int) -> bool:
    """[Accelerate] on a non-hand unit play -- the unit's own, or Rek'Sai's grant.

    820.1 again (RiftJudge #6973): "plays it, ignoring its cost" pays off the
    printed Energy and Power, and an OPTIONAL additional cost is still there to
    be paid if the player wants it. Every printed [Accelerate] in the pool costs
    {1 energy} plus one rune of the unit's own domain, which is exactly the +1/+1
    `_finish_rplay` charges for `fast` -- so the offer is the whole fix.

    Crescent Guardian is deliberately NOT here: its readiness rides a
    `PLAY_COSTS` entry with a different cost and a condition of its own.
    """
    if not table.is_type(card, "Unit"):
        return False
    if not table.has(card, "Accelerate") and not any(
            state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == seat
            and table.names[int(state.perms[i, P_CARD])] in NONHAND_ACCELERATE
            for i in range(state.n_perms)):
        return False
    extra = _rplay_extra(state, table, seat, card) or (0, 0)
    return plan_payment(state, table, seat, card, extra[0] + 1,
                        extra[1] + 1) is not None


def rplay_options(state: GameState, table: CardTable, cfg: Config) -> list[Action]:
    seat, card = int(state.rp_seat), int(state.rp_card)
    if state.rp_from_sarc and card < 0:
        # Cursed Sarcophagus: which of the units banished with it.
        out = [Action(A_PICK, k) for k in range(int(state.n_sarc[seat]))
               if _rplay_ok(state, table, seat, int(state.sarc_cards[seat, k]))]
        return out or [Action(A_DECLINE)]
    out: list[Action] = []
    if _rplay_affordable(state, table, seat, card):
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            # 820.1 -- "ignoring its cost" buys off the printed Energy and
            # Power and nothing else, so a MANDATORY additional cost is still
            # owed (RiftJudge #7056). Asked first, and the card is not offered
            # at all when it cannot be paid (355.8), which is how the spell
            # branch below has always read it.
            _ck = spec_for(table, card)
            if (_ck is not None and _ck.cost_kill is not None
                    and not _ck.cost_kill_optional and not int(state.rp_kill)):
                opts = rsv.choosable_cost_kill_targets(state, table, _ck, seat, -1,
                                                       card=card)
                return ([Action(A_TARGET, p) for p in opts] if opts
                        else [Action(A_DECLINE)])
            out = [Action(A_PLAY_AT, loc)
                   for loc in _rplay_dests(state, table, seat, card)]
            if _rplay_accel_ok(state, table, seat, card):
                out += [Action(A_PLAY_AT_FAST, loc)
                        for loc in _rplay_dests(state, table, seat, card)]
        else:
            spec = spec_for(table, card)
            if spec is not None and (
                    rsv.can_be_cast(state, table, spec, seat, -1, card=card)
                    if spec.cost_kill_optional else
                    rsv.can_play_with_cost_kill(state, table, spec, seat, -1,
                                                card=card)):
                out = [Action(A_ACCEPT)]
    return out or [Action(A_DECLINE)]


def _pay_rplay_cost_kill(state: GameState, table: CardTable, cfg: Config,
                         perm: int) -> dict:
    """Pay the mandatory additional cost of a card being played from outside
    the hand, before its destination is chosen (820.1, RiftJudge #7056).

    `rp_kill` rather than a pending field of its own: the whole decision lives
    inside the reveal-play that `rp_seat` already holds open, and clearing it
    is `_finish_rplay`'s job along with the rest of the rp_* block. `rp_here`
    is set to where the killed unit stood, which is what Stalking Wolf's
    "you may play me to ITS battlefield" reads.
    """
    seat, card = int(state.rp_seat), int(state.rp_card)
    spec = spec_for(table, card)
    assert spec is not None and spec.cost_kill is not None, \
        "a reveal play with no kill cost was asked to pay one"
    state.rp_kill = 1
    if int(state.rp_here) < 0:
        state.rp_here = int(state.perms[perm, P_LOC])
    if spec.cost_return:
        combat.return_to_hand(state, table, perm)
    else:
        combat.destroy(state, table, perm)
    # The card may have been the only thing keeping its own destination legal
    # (a unit killed at the battlefield it was the lone ally at), so the
    # options are simply recomputed at the next `legal_actions`.
    return {"cost_kill": perm}


def _finish_group_loc(state: GameState, table: CardTable, cfg: Config,
                      loc: int) -> dict:
    """355.11.b -- the controller has named where the scattered group settles.

    The resolution that asked was suspended before any of its ops ran, so
    `rsv.run_resume` simply starts it again with `group_loc` set: every member of
    the group at `loc` is affected and the rest are not.
    """
    state.pend_group_loc = -1
    state.group_loc = int(loc)
    state.group_loc_opts[:] = -1
    state.n_group_loc = 0
    log: dict = {"group_loc": int(loc)}
    log.update(rsv.run_resume(state, table, cfg))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _finish_rplay(state: GameState, table: CardTable, cfg: Config,
                  choice: int, fast: bool = False) -> dict:
    """Play the banished card: `choice` a location (a permanent), -1 cast it
    (a spell), -2 it cannot be played and stays banished."""
    seat, card, owner = int(state.rp_seat), int(state.rp_card), int(state.rp_owner)
    # Before the card lands: whatever the effect did on its way here (recycling
    # the cards it revealed, banishing them) happened while this card was still
    # in the deck, so it must not be one of the watchers. See
    # `flush_player_events`.
    flush_player_events(state, table)
    empower = bool(state.rp_empower)
    extra = _rplay_extra(state, table, seat, card) if card >= 0 else None
    if fast:
        extra = ((extra or (0, 0))[0] + 1, (extra or (0, 0))[1] + 1)
    zone, sarc = int(state.rp_zone), bool(state.rp_from_sarc)
    state.rp_seat = state.rp_card = state.rp_owner = -1
    state.rp_here = -1
    state.rp_empower = 0
    state.rp_kill = 0
    state.rp_zone = state.rp_power = state.rp_from_sarc = 0
    log: dict = {}
    if choice != -2 and card >= 0:
        if zone == 1:
            rsv.take_from_trash(state, owner, card)
        else:
            n = int(state.n_banished[owner])
            k = max(i for i in range(n) if int(state.banished[owner, i]) == card)
            state.banished[owner, k:n - 1] = state.banished[owner, k + 1:n].copy()
            state.banished[owner, n - 1] = -1
            state.n_banished[owner] = n - 1
        if sarc:
            m = int(state.n_sarc[seat])
            j = [i for i in range(m) if int(state.sarc_cards[seat, i]) == card][0]
            state.sarc_cards[seat, j:m - 1] = state.sarc_cards[seat, j + 1:m].copy()
            state.sarc_cards[seat, m - 1] = -1
            state.n_sarc[seat] = m - 1
        if extra is not None:
            recycle = plan_payment(state, table, seat, card, extra[0], extra[1])
            assert recycle is not None, "unaffordable reveal play reached payment"
            pay(state, table, seat, card, recycle, extra[0], extra[1])
        if choice == -1:
            # A spell: paid here, then onto the Chain like any other play
            # from outside the hand (its targets are chosen next).
            chain.push(state, card, seat, from_hand=False, bound_bf=-1,
                       cost=COST_FREE, owner=owner if owner != seat else -1)
            log["cast_from_reveal"] = table.names[card]
        else:
            row = combat.record_effect_play(state, table, seat, card, choice,
                                            owner)
            if fast:
                state.perms[row, P_READY] = 1        # 805.6: enters ready
            if empower:
                # "Then you may do this: Empower it." Taken whenever offered.
                rsv.resolve(state, table, cfg,
                            CardSpec(speed=SPEED_MAIN, ops=(Op(OP_EMPOWER),)),
                            seat, [], -1, True, source=row)
            log["played_from_reveal"] = table.names[card]
    log.update(_settle_after_decision(state, table, cfg))
    return log


def hand_play_choices(state: GameState, table: CardTable, seat: int) -> list[int]:
    """Hand indices an OP_PLAY_FROM_HAND may play right now."""
    out = []
    for j in range(int(state.n_hand[seat])):
        c = int(state.hand[seat, j])
        is_perm = table.is_type(c, "Unit") or table.is_type(c, "Gear")
        if not is_perm:
            spec_c = spec_for(table, c) if state.hp_spells else None
            if spec_c is None or not rsv.can_play_with_cost_kill(
                    state, table, spec_c, seat, -1, card=c):
                continue
        if state.hp_types and not (int(state.hp_types) & _look_type_bit(table, c)):
            continue
        if int(state.hp_tag) == 1 and "Equipment" not in table.tags[c]:
            continue
        if int(state.hp_kw) >= 0 and not table.has(c, ALL_KEYWORDS[int(state.hp_kw)]):
            continue
        if int(state.hp_max_energy) >= 0 and int(table.energy[c]) > int(state.hp_max_energy):
            continue
        extra = _hand_play_cost(state, table, seat, c)
        if extra is not None and plan_payment(state, table, seat, c,
                                              extra[0], extra[1]) is None:
            continue
        if is_perm and not _hand_play_dests(state, table, seat, c):
            continue
        out.append(j)
    return out


def _hand_play_dests(state: GameState, table: CardTable, seat: int, card: int) -> list[int]:
    if not table.is_type(card, "Unit"):
        return [base_loc(seat)]                       # gear lands at base (149.2)
    d = int(state.hp_dest)
    if d == -1:
        return [base_loc(seat)]
    if d == -2:
        return [bf_loc(b) for b in state.live_bfs() if int(state.bf_ctrl[b]) == seat
                and not combat.bf_forbids_play(state, table, bf_loc(b))]
    return [d]


def _finish_hand_play(state: GameState, table: CardTable, cfg: Config,
                      pick: int, loc: int) -> dict:
    """Play the chosen hand card for an OP_PLAY_FROM_HAND (349: a play)."""
    seat = int(state.pend_hand_play)
    state.pend_hand_play = -1
    state.hp_pick = -1
    log: dict = {}
    if pick >= 0:
        card = int(state.hand[seat, pick])
        extra = _hand_play_cost(state, table, seat, card)
        if extra is not None:
            recycle = plan_payment(state, table, seat, card, extra[0], extra[1])
            assert recycle is not None, "unaffordable hand play reached payment"
            pay(state, table, seat, card, recycle, extra[0], extra[1])
        n = int(state.n_hand[seat])
        state.hand[seat, pick:n - 1] = state.hand[seat, pick + 1:n]
        state.hand[seat, n - 1] = -1
        state.n_hand[seat] = n - 1
        state.hp_kw, state.hp_spells = -1, 0
        if not (table.is_type(card, "Unit") or table.is_type(card, "Gear")):
            # A spell (Ava Achiever): cast free; its targets come next.
            chain.push(state, card, seat, from_hand=True, bound_bf=-1,
                       cost=COST_FREE)
            state.hp_attach = -1
            log["cast_from_hand"] = table.names[card]
            log.update(_settle_after_decision(state, table, cfg))
            return log
        row = combat.record_effect_play(state, table, seat, card, loc, seat)
        att = int(state.hp_attach)
        if (att >= 0 and state.perms[att, P_ALIVE] == 1
                and "Equipment" in table.tags[card]):
            state.attach(row, att)
            rsv._queue_equipped(state, table, att)
        log["played_from_hand"] = table.names[card]
    state.hp_attach = -1
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _finish_ask(state: GameState, table: CardTable, cfg: Config,
                yes: bool) -> dict:
    """Answer an OP_ASK: run the chosen follow-up for the caster.

    Cleared before running, so a follow-up that asks again (Card Sharp asks
    you, then the opponent) sets its own question without this one erasing it.
    """
    key = int(state.pend_ask_yes if yes else state.pend_ask_no)
    caster, subj = int(state.pend_ask_caster), int(state.pend_ask_subj)
    card = int(state.pend_ask_card)
    state.pend_ask = state.pend_ask_caster = -1
    state.pend_ask_yes = state.pend_ask_no = state.pend_ask_subj = -1
    state.pend_ask_card = -1
    log: dict = {"answered": bool(yes)}
    if 0 <= key < len(FOLLOWUPS) and FOLLOWUPS[key]:
        if subj < 0 or state.perms[subj, P_ALIVE] == 1:
            log.update(rsv.resolve(state, table, cfg,
                                   CardSpec(speed=SPEED_MAIN, ops=FOLLOWUPS[key]),
                                   caster, [], -1, True, subj=subj, card=card))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _finish_tax(state: GameState, table: CardTable, cfg: Config,
                pay: bool) -> dict:
    """Answer "counter a spell unless its controller pays {N}".

    The counter lives HERE rather than in the op, because `resolve` does not
    halt at a pending decision -- it sets the flag and runs the rest of the op
    list. A counter written as the next op would fire before the answer, which
    is the bug OP_DISCARD_CHOOSE documents.

    The UID is resolved fresh: `chain.counter` already returns None for an item
    that is gone, which is the normal outcome when two players answer the same
    spell (359.3.e). Paying for an item that vanished would be paying for
    nothing, so the payment is skipped in that case too -- they are not charged
    to protect a spell no longer there.
    """
    seat = int(state.pend_tax)
    uid = int(state.pend_tax_uid)
    cost = int(state.pend_tax_cost)
    state.pend_tax = -1
    state.pend_tax_uid = -1
    state.pend_tax_cost = 0

    log: dict = {}
    i = chain.index_of_uid(state, uid)
    if i < 0:
        log["tax_moot"] = seat            # already off the Chain
    elif pay:
        card = int(state.chain[i, C_CARD])
        recycle = plan_ability_cost(state, table, seat, card, cost, 0)
        assert recycle is not None, (
            "an unaffordable tax should have countered outright rather than "
            "reaching a decision")
        pay_ability_cost(state, table, seat, cost, recycle, 0, card)
        log["tax_paid"] = seat
    else:
        log["countered_ctrl"] = int(state.chain[i, C_CTRL])
        name = chain.counter(state, table, uid)
        if name is not None:
            log["countered_spell"] = name
    log.update(_settle(state, table, cfg))
    return log


def _resolve_double(state: GameState, table: CardTable, cfg: Config,
                    take: bool) -> dict:
    """Answer Zilean's "you may play ... an additional copy of it instead".

    The once-each-turn stamp is spent whether or not the copy is taken: the
    replacement was applied to this token play either way, and 820-style "you
    may" costs nothing to decline only when the card says so. Zilean's does
    not -- "Once each turn" gates the OPPORTUNITY, and this was it.
    """
    src, card, loc = (int(x) for x in state.pend_double)
    seat = int(state.perms[src, P_CTRL])
    state.pend_double[:] = (-1, -1, -1)
    state.once_used[src] = int(state.ply)
    log: dict = {}
    if take:
        row = state.add_permanent(
            card, seat, loc,
            ready=bool(table.is_type(card, "Unit"))
            and combat.granted_enters_ready(state, table, seat, card),
            is_unit=bool(table.is_type(card, "Unit")))
        log["doubled"] = row
        # 187 -- the copy is PLAYED like any other token, so a watcher for
        # "when you play a token unit" sees it too. Lillia counts both.
        chain.fire_play_unit(state, table, seat, card, row)
    # 360-style replacement effects apply one at a time, and a second Zilean
    # modifies the already-modified play: each adds ONE copy, so two Zileans
    # turn one token into three (RiftJudge #10154). Offered in turn, and the
    # follow-up waits until every one has been answered.
    for z in range(state.n_perms):
        zr = state.perms[z]
        if (z != src and zr[P_ALIVE] == 1 and int(zr[P_CTRL]) == seat
                and is_battlefield(int(zr[P_LOC]))
                and table.names[int(zr[P_CARD])] in TOKEN_DOUBLERS
                and int(state.once_used[z]) != int(state.ply)):
            state.pend_double[:] = (z, card, loc)
            return log
    log.update(_run_followup(state, table, cfg, seat))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _cull_candidates(state: GameState, table: CardTable, seat: int) -> list[int]:
    """Rows `seat` may choose in the per-player walk's current mode."""
    want = CARD_TYPES[int(state.pend_cull_type)]
    any_side = int(state.pend_cull_mode) == CULL_RETURN_ANY
    dest = int(state.pend_cull_dest)
    moving = int(state.pend_cull_mode) == CULL_MOVE_OWN_TO
    return [i for i in range(state.n_perms)
            if state.perms[i, P_ALIVE] == 1
            and (any_side or int(state.perms[i, P_CTRL]) == seat)
            and table.is_type(int(state.perms[i, P_CARD]), want)
            and not (int(state.pend_cull_mode) == CULL_KILL_OWN and dest >= 0
                     and int(state.perms[i, P_LOC]) != dest)
            and not (moving and (dest < 0 or int(state.perms[i, P_LOC]) == dest
                                 or combat.unmovable_by(state, table, i, seat)
                                 or (not is_battlefield(dest)
                                     and combat.cant_move_to_base(state, table, i))))]


def _has_cullable(state: GameState, table: CardTable, seat: int) -> bool:
    return bool(_cull_candidates(state, table, seat))


def first_cull_seat(state: GameState, table: CardTable, start: int) -> int:
    """The first seat, in turn order from `start`, with something to choose."""
    for k in range(N_SEATS):
        s = (start + k) % N_SEATS
        if s != int(state.pend_cull_skip) and _has_cullable(state, table, s):
            return s
    return -1


def _advance_cull(state: GameState, table: CardTable, seat_done: int) -> None:
    """Hand the walk to the next seat that has a choice, or end it.

    **Round from the FIRST seat, not up to seat N-1.** This used to count
    upward from the resolving seat and stop at `N_SEATS`, so when seat 1 cast
    Cull the Weak only seat 1 ever killed anything.
    """
    first = int(state.pend_cull_first)
    nxt = (seat_done + 1) % N_SEATS
    while nxt != first and (nxt == int(state.pend_cull_skip)
                            or not _has_cullable(state, table, nxt)):
        nxt = (nxt + 1) % N_SEATS
    state.pend_cull = -1 if nxt == first else nxt
    if state.pend_cull < 0 and int(state.pend_cull_mode) == CULL_KEEP_OWN:
        finish_keep_cull(state, table)


def finish_keep_cull(state: GameState, table: CardTable) -> None:
    """Cataclysmic Duel's "Kill the rest", once every seat has chosen."""
    kept = {int(k) for k in state.pend_cull_keep if int(k) >= 0}
    want = CARD_TYPES[int(state.pend_cull_type)]
    doomed = [i for i in range(state.n_perms)
              if state.perms[i, P_ALIVE] == 1 and i not in kept
              and table.is_type(int(state.perms[i, P_CARD]), want)]
    for i in doomed:
        combat.destroy(state, table, i)
    state.pend_cull_keep[:] = -1


def _finish_dig(state: GameState, table: CardTable, cfg: Config,
                idx: int) -> dict:
    """Play the chosen unit out of a trash, or decline (Kharox).

    `idx` indexes the OWNER's trash, which is not always the chooser's -- "in
    THEIR trash" digs in the opponent's pile, and 108.2 makes every trash
    public, so naming a card there leaks nothing.

    The card is played, not conjured: 349 makes this a play, so it counts for
    [Legion], fires "when you play a unit" watchers, and runs its own
    TR_PLAY_ME. What it skips is the cost, which the card waives outright.

    **The player who PLAYS it controls it**, not the owner whose trash it came
    from. 416.1.c's "recycle to the owner's deck" is about where a card GOES;
    a card played from a zone is played by whoever the effect says, and the
    effect says "you".
    """
    seat = int(state.pend_grave)
    owner = int(state.pend_grave_owner)
    loc = int(state.pend_grave_dest)
    state.pend_grave = -1
    state.pend_grave_owner = -1
    state.pend_grave_dest = -1

    log: dict = {}
    if idx >= 0:
        card = int(state.trash[owner, idx])
        if rsv.take_from_trash(state, owner, card):
            legion = bool(state.cards_played[seat])
            state.cards_played[seat] += 1
            if not table.is_token(card):
                state.played_types[seat] |= _played_bits(table, card)
            chain.card_played(state, table, seat, card, completed=False)
            # **Controlled by the digger, OWNED by whoever's trash it was.**
            # "You may play it" says who plays it; it does not make the card
            # theirs. When it dies it goes back to its owner's trash (108.2),
            # which is also what keeps the per-seat conservation gate honest --
            # that gate caught this the first time round, counting by
            # controller and reading a card as having changed hands.
            src = state.add_permanent(
                card, seat, loc,
                ready=_enters_ready(state, table, seat, card), is_unit=True,
                owner=owner)
            if legion:
                state.perms[src, P_FLAGS] |= F_LEGION
            chain.fire_nth_card(state, table, seat, card)   # 419.4.a: once it is on the board
            chain.fire_play_unit(state, table, seat, card, src)
            if chain.has_trigger(table, card, TR_PLAY_ME):
                chain.queue(state, TR_PLAY_ME, src, loc)
            log["dug"] = table.names[card]
    log.update(_run_followup(state, table, cfg, seat))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def steal_control(state: GameState, table: CardTable, seat: int, uid: int) -> None:
    """Gain control of the Chain Item `uid`; then ask about new choices."""
    i = chain.index_of_uid(state, uid)
    old = int(state.chain[i, C_CTRL])
    if int(state.chain[i, C_OWNER]) < 0 and old != seat:
        state.chain[i, C_OWNER] = old            # its zones stay its owner's
    state.chain[i, C_CTRL] = seat
    sp = chain.item_spec(state, table, i)
    if sp is not None and sp.n_targets:
        state.steal_stage = 2
    else:
        state.steal_seat, state.steal_uid, state.steal_stage = -1, -1, 0


def _steal_slot_options(state: GameState, table: CardTable) -> list[int]:
    i = chain.index_of_uid(state, int(state.steal_uid))
    sp = chain.item_spec(state, table, i)
    k, seat = int(state.steal_slot), int(state.steal_seat)
    chosen = [int(x) for x in state.steal_targets[:k]]
    opts = rsv.choosable_targets(state, table, sp, k, seat, chosen,
                                 int(state.chain[i, C_BOUND_BF]),
                                 int(state.chain[i, C_SRC]),
                                 int(state.chain[i, C_CARD]))
    if sp.targets[k].optional or not opts:
        opts = list(opts) + [-1]
    return opts


def _answer_steal(state: GameState, table: CardTable, cfg: Config,
                  yes: bool) -> dict:
    seat, uid, stage = int(state.steal_seat), int(state.steal_uid), int(state.steal_stage)
    log: dict = {}
    if chain.index_of_uid(state, uid) < 0:
        state.steal_seat, state.steal_uid, state.steal_stage = -1, -1, 0
        log.update(_settle_after_decision(state, table, cfg))
        return log
    if stage == 1:
        if yes:
            recycle = plan_wild_power(state, seat, 1)
            assert recycle is not None, "Rebuttal's {any rune} became unpayable"
            pay_wild_power(state, seat, 1, recycle)
            steal_control(state, table, seat, uid)
            log["stole"] = uid
        else:
            state.steal_seat, state.steal_uid, state.steal_stage = -1, -1, 0
            log["countered_spell"] = chain.counter(state, table, uid)
    elif yes:
        state.steal_stage, state.steal_slot = 3, 0
        state.steal_targets[:] = -1
        return {"new_choices": uid}
    else:
        state.steal_seat, state.steal_uid, state.steal_stage = -1, -1, 0
    if state.steal_seat < 0:
        log.update(_settle_after_decision(state, table, cfg))
    return log


def _steal_choose(state: GameState, table: CardTable, cfg: Config,
                  value: int) -> dict:
    i = chain.index_of_uid(state, int(state.steal_uid))
    sp = chain.item_spec(state, table, i)
    k = int(state.steal_slot)
    state.steal_targets[k] = value
    if k + 1 < sp.n_targets:
        state.steal_slot = k + 1
        return {"new_choice": value}
    state.chain_targets[i, :sp.n_targets] = state.steal_targets[:sp.n_targets]
    state.steal_seat, state.steal_uid, state.steal_stage = -1, -1, 0
    state.steal_slot = 0
    state.steal_targets[:] = -1
    log = {"new_choices_made": True}
    log.update(_settle_after_decision(state, table, cfg))
    return log


def amount_max(state: GameState, table: CardTable) -> int:
    """The most the pending "pay any amount" can pay, capped."""
    seat, kind = int(state.pend_amount), int(state.amt_kind)
    if kind == AMT_ENERGY_TO_ANY:
        have = int(state.pool_energy[seat]) + int(state.runes_ready[seat].sum())
    else:
        have = int(state.pool_power[seat].sum()) + int(state.runes_in_play(seat).sum())
    return max(0, min(AMOUNT_CAP, have))


def _finish_amount(state: GameState, table: CardTable, cfg: Config,
                   k: int) -> dict:
    seat, kind, loc = int(state.pend_amount), int(state.amt_kind), int(state.amt_loc)
    spell = bool(state.amt_spell)
    state.pend_amount, state.amt_loc, state.amt_spell = -1, -1, 0
    log: dict = {"amount": k}
    if k > 0 and kind == AMT_ENERGY_TO_ANY:
        need = max(0, k - int(state.pool_energy[seat]))
        state.pool_energy[seat] = max(0, int(state.pool_energy[seat]) - k)
        for _ in range(need):
            dom = int(np.argmax(state.runes_ready[seat]))
            state.runes_ready[seat, dom] -= 1
            state.runes_spent[seat, dom] += 1
        state.pool_power[seat, D_ANY] += k
    elif k > 0:
        recycle = plan_wild_power(state, seat, k)
        assert recycle is not None, "an unpayable amount was offered"
        pay_wild_power(state, seat, k, recycle)
        if kind == AMT_ANY_TO_ENERGY:
            state.pool_energy[seat] += k
        elif loc >= 0:
            prev = combat.KILLER[:]
            combat.KILLER[:] = [seat, spell]
            try:
                for i in list(state.units_at(loc, 1 - seat)):
                    combat.mark_damage(state, table, int(i), k, seat)
            finally:
                combat.KILLER[:] = prev
    log.update(_settle_after_decision(state, table, cfg))
    return log


def split_candidates(state: GameState, table: CardTable) -> list[int]:
    """Enemy units that may take the next point of a split."""
    seat, loc = int(state.pend_split), int(state.split_loc)
    # Splitting damage CHOOSES the units that take it (355.14), so "I can't be
    # chosen by enemy spells and abilities" keeps Baron Nashor out of Alpha
    # Strike's split (RiftJudge #9940).
    return [i for i in range(state.n_perms)
            if state.perms[i, P_ALIVE] == 1
            and int(state.perms[i, P_CTRL]) != seat
            and not combat.unchoosable_by(state, table, i, seat)
            and table.is_type(int(state.perms[i, P_CARD]), "Unit")
            and (int(state.perms[i, P_LOC]) == loc if loc >= 0
                 else is_battlefield(int(state.perms[i, P_LOC])))]


def _split_one(state: GameState, table: CardTable, cfg: Config,
               perm: int) -> dict:
    """Hand one point of a split to `perm`; deal them all once none remain."""
    state.split_alloc[perm] += 1
    state.split_left -= 1
    log: dict = {"split_to": perm}
    if int(state.split_left) > 0 and split_candidates(state, table):
        return log
    seat = int(state.pend_split)
    state.pend_split = -1
    state.split_left = 0
    kills = 0
    prev = combat.KILLER[:]
    combat.KILLER[:] = [seat, bool(state.split_spell)]
    try:
        for i in range(state.n_perms):
            amt = int(state.split_alloc[i])
            if amt and state.perms[i, P_ALIVE] == 1:
                if combat.mark_damage(state, table, i, amt, seat):
                    kills += 1
    finally:
        combat.KILLER[:] = prev
    state.split_alloc[:] = 0
    if state.split_xp and kills:
        state.xp[seat] += kills
        state.xp_gained_ply[seat] = int(state.ply)
    state.split_xp = state.split_spell = 0
    state.split_loc = -1
    log["split_kills"] = kills
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _cull_one(state: GameState, table: CardTable, cfg: Config,
              perm: int) -> dict:
    """One seat's choice in the per-player walk, then pass to the next."""
    seat = int(state.pend_cull)
    mode = int(state.pend_cull_mode)
    if mode == CULL_KILL_OWN:
        # The kill is the SPELL's, however the unit was chosen: "when you kill
        # a unit with a spell" sees a Cull the Weak (RiftJudge #10402).
        _prev = combat.KILLER[:]
        combat.KILLER[:] = [int(state.cull_spell_seat), True]
        try:
            combat.destroy(state, table, perm)
        finally:
            combat.KILLER[:] = _prev
    elif mode == CULL_RETURN_ANY:
        if perm >= 0:
            combat.return_to_hand(state, table, perm)
    elif mode == CULL_KEEP_OWN:
        state.pend_cull_keep[seat] = perm
    elif mode == CULL_MOVE_OWN_TO and perm >= 0:
        dest = int(state.pend_cull_dest)
        combat.queue_move_trigger(state, table, perm,
                                  int(state.perms[perm, P_LOC]), dest)
        state.set_location(perm, dest)
    _advance_cull(state, table, seat)
    if state.pend_cull < 0:
        state.pend_cull_dest = -1
    log = {"culled": perm}
    if state.pend_cull < 0:
        log.update(_settle_after_decision(state, table, cfg))
    return log


def _run_pending_repeat(state: GameState, table: CardTable,
                        cfg: Config) -> dict:
    """A [Repeat] whose first pass suspended (Called Shot's look, Hard
    Bargain's tax): its second pass, once no decision is open."""
    pf_try_play(state, table)
    if int(state.pend_repeat_card) < 0 or chain.decision_open(state):
        return {}
    card, who = int(state.pend_repeat_card), int(state.pend_repeat_seat)
    spec = spec_for(table, card)
    tg = [int(x) for x in state.pend_repeat_tgts[:spec.n_targets]]
    bound, hand = int(state.pend_repeat_bound), bool(state.pend_repeat_hand)
    state.pend_repeat_card = state.pend_repeat_seat = -1
    state.pend_repeat_tgts[:] = -1
    state.pend_repeat_bound, state.pend_repeat_hand = -1, 0
    # As in `chain.resolve_top`: the optional additional cost was paid once, by
    # the play, so the second pass runs as though it had not been paid.
    state.resolving_paid = 0
    return {"repeated": rsv.resolve(state, table, cfg, spec, who, tg, bound,
                                    hand, card=card)}


def _settle_after_decision(state: GameState, table: CardTable,
                           cfg: Config) -> dict:
    """Finish a deferred decision: drain pending items, then CLEAN UP.

    The cleanup is the part that is easy to miss. `_advance_pending` only
    finalizes Chain items; the Cleanup that initiates a staged Combat lives on
    the A_PASS path, which runs after IT resolves something. A decision
    resolving is a different path -- and a decision can absolutely put a unit
    on contested ground: Zilean's extra token arrives at a battlefield where
    the opponent already stands.

    Without this, 460/461 is violated -- units from both seats at a battlefield
    in an Open State with no Combat -- which is exactly what the invariant
    caught in a real-deck fuzz at victory 8.

    Only once everything else has settled: a follow-up decision may still be
    open, and a Cleanup during one would be premature.
    """
    log = _run_pending_repeat(state, table, cfg)
    log.update(_advance_pending(state, table, cfg))
    if (state.n_chain == 0 and state.n_trig == 0
            and state.pend_look < 0 and state.pend_discard < 0
            and state.pend_grave < 0
            and state.pend_cull < 0 and state.pend_may < 0
            and state.pend_tax < 0 and state.pend_ask < 0
            and state.pend_hand_play < 0 and state.rp_seat < 0
            and state.pend_split < 0 and state.pend_amount < 0
            and state.steal_seat < 0 and state.pend_name < 0
            and state.dj_seat < 0 and state.pend_altar < 0
            and state.pend_dmg < 0
            and int(state.pend_double[0]) < 0
            and int(state.pend_reveal[0]) < 0
            and not is_terminal(state)):
        log.update(combat.cleanup(state, table, cfg,
                                  mover=int(state.active), dst=-1))
    return log


def _run_followup(state: GameState, table: CardTable, cfg: Config,
                  seat: int) -> dict:
    """Run the ops queued to follow a deferred decision, if any.

    The ops may suspend again -- that is the point. Each handler calls this
    instead of assuming its decision was the last thing the card had to say,
    which is what lets Diana Predict and THEN reveal.

    Cleared before running, so a follow-up that suspends can set its own
    without being overwritten by this one.
    """
    key, src = int(state.pend_then[0]), int(state.pend_then[1])
    state.pend_then[:] = (-1, -1)
    log: dict = {}
    if 0 <= key < len(FOLLOWUPS) and FOLLOWUPS[key]:
        log = rsv.resolve(state, table, cfg,
                          CardSpec(speed=SPEED_MAIN, ops=FOLLOWUPS[key]),
                          seat, [], -1, True, source=src)
    return log


def _finish_discard(state: GameState, table: CardTable, cfg: Config,
                    hand_idx: int) -> dict:
    """Discard the chosen card, then run the branch its TYPE selects.

    A card with more than one type takes EVERY matching branch -- a gear unit
    is both, so it would draw AND ready runes. Checked independently rather
    than as an if/elif, the same rule as Swain's trio.
    """
    seat = int(state.pend_discard)
    key = int(state.pend_discard_ops)
    src = int(state.pend_discard_src)
    state.pend_discard = -1
    state.pend_discard_ops = -1
    state.pend_discard_src = -1
    tgt = int(state.pend_discard_tgt)
    state.pend_discard_tgt = -1

    n = int(state.n_hand[seat])
    card = int(state.hand[seat, hand_idx])
    state.hand[seat, hand_idx:n - 1] = state.hand[seat, hand_idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1
    if key == DB_TO_DECK:
        # Not a discard: "put a card from your hand on the top or bottom of
        # your Main Deck". Which end is asked as a one-card look -- pick puts
        # it on top, none recycles it -- and any follow-up waits for that.
        state.look_cards[:] = -1
        state.look_cards[0] = card
        state.n_look = 1
        state.look_pick_dest = DEST_TOP
        state.look_rest_dest = DEST_RECYCLE
        state.look_optional = 1
        state.look_multi = 0
        state.look_min_energy = 0
        state.look_type_mask = 0
        state.pend_look = seat
        return {"to_deck": table.names[card]}
    phases._to_trash(state, seat, card)
    # A chosen discard is still a discard, so the same watchers see it.
    chain.fire_watchers(state, table, seat, TR_DISCARD)
    chain.fire_discarded(state, table, seat, [card])

    log: dict = {"discarded": table.names[card]}
    if key == DB_ENERGY_DAMAGE and tgt >= 0 and state.perms[tgt, P_ALIVE] == 1:
        # "Deal its Energy cost as damage" -- the printed Energy, Power ignored.
        rsv.resolve(state, table, cfg,
                    CardSpec(speed=SPEED_MAIN,
                             targets=(TargetSpec(locality=LOC_FREE),),
                             ops=(Op(OP_DAMAGE, target=0,
                                     n=int(table.energy[card])),)),
                    seat, [tgt], -1, True, source=src)
    branches = DISCARD_BRANCHES[key] if 0 <= key < len(DISCARD_BRANCHES) else {}
    for type_name, ops in branches.items():
        if not table.is_type(card, type_name):
            continue
        log.setdefault("branches", []).append(type_name)
        rsv.resolve(state, table, cfg, CardSpec(speed=SPEED_MAIN, ops=ops),
                    seat, [], -1, True, source=src)
    # "Discard 1, THEN draw 1" -- the part that must not run until the card is
    # actually gone. A type-keyed branch cannot express it, because it happens
    # whatever was discarded.
    log.update(_run_followup(state, table, cfg, seat))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _finish_reveal(state: GameState, table: CardTable, cfg: Config,
                   pick: int) -> dict:
    """Send the chosen card out of the revealed hand to `look_pick_dest`.

    Everything not chosen stays in hand untouched; only the one card moves.

    **The destination is read, not assumed.** This recycled unconditionally
    while `OP_REVEAL_HAND` was setting `look_pick_dest` and nothing consulted
    it -- invisible while Sabotage ("recycle that card") was the only card
    using the op, and silently wrong the moment Mindsplitter ("they DISCARD
    that card") arrived, which would have recycled instead.

    Recycle goes to the card's OWNER's deck, not the chooser's -- 416.1.c is
    explicit that each player recycles to their own Main Deck regardless of who
    was instructed to perform it. A discard is likewise performed BY its owner,
    so it fires their discard watchers, exactly as `_finish_discard` does for a
    discard the owner chose themselves.
    """
    chooser = int(state.pend_reveal[0])
    foe = int(state.pend_reveal[1])
    dest = int(state.look_pick_dest)
    xp_cost = int(state.pend_reveal_xp)
    state.pend_reveal[:] = (-1, -1)
    state.pend_reveal_xp = 0
    log: dict = {}
    n = int(state.n_hand[foe])
    if 0 <= pick < n:
        # Paid only when a card is actually chosen -- "you may pay 2 XP TO
        # CHOOSE", so declining costs nothing. The offer site already refused
        # the pick to a seat that cannot afford it.
        if xp_cost:
            assert int(state.xp[chooser]) >= xp_cost, "XP cost underflow"
            state.xp[chooser] -= xp_cost
            log["paid_xp"] = xp_cost
        card = int(state.hand[foe, pick])
        state.hand[foe, pick:n - 1] = state.hand[foe, pick + 1:n]
        state.hand[foe, n - 1] = -1
        state.n_hand[foe] = n - 1
        if int(state.reveal_play_loc) >= 0:
            # Bone Skewer: THEY play it, free, there -- and it is stunned.
            row = combat.record_effect_play(state, table, foe, card,
                                            int(state.reveal_play_loc), foe,
                                            free_costs=True)
            if state.stun(row):
                chain.fire_watchers(state, table, chooser, TR_STUN, subj=row)
            log["played_for_them"] = table.names[card]
        elif dest == DEST_TRASH:
            phases._to_trash(state, foe, card)
            # "They discard that card" -- a discard, so the discard watchers
            # see it. Fired for the seat DOING the discarding, which is the
            # opponent, not the player who chose the card.
            chain.fire_watchers(state, table, foe, TR_DISCARD)
            chain.fire_discarded(state, table, foe, [card])
            log["discarded"] = table.names[card]
        elif dest == DEST_BANISH:
            state.banish_card(foe, card)
            if state.reveal_hold_return:
                k = int(state.n_hold_return[foe])
                assert k < state.hold_return.shape[1], "hold-return overflow"
                state.hold_return[foe, k] = card
                state.n_hold_return[foe] = k + 1
            log["banished"] = table.names[card]
        else:
            assert dest == DEST_RECYCLE, (
                f"OP_REVEAL_HAND has no path for destination {dest}")
            state.recycle_card(foe, card)
            log["sabotaged"] = table.names[card]
    state.reveal_hold_return = 0
    state.reveal_play_loc = -1
    # Every other deferred decision runs its card's follow-up ops here and this
    # one did not, so a `then_key` on OP_REVEAL_HAND silently did nothing.
    #
    # **Conditional on a card actually being chosen**, because the only card
    # using it puts the follow-up inside an "IF YOU DO": Insightful
    # Investigator reads "you may pay 2 XP to choose a card. If you do, they
    # discard that card AND DRAW 1" -- so declining owes them no draw. That is
    # the opposite of `OP_DISCARD_CHOOSE`, where "then draw 1" is sequencing
    # and runs even on an empty hand; a reveal card that wants the sequencing
    # reading would need that stated rather than inherited.
    #
    # Run for the CHOOSER, which is what `seat` means everywhere else; an op
    # that has to act on the revealer says so with `who=W_ENEMY`.
    if 0 <= pick < n:
        log.update(_run_followup(state, table, cfg, chooser))
    else:
        state.pend_then[:] = (-1, -1)
    log.update(_settle_after_decision(state, table, cfg))
    return log


def _finish_look(state: GameState, table: CardTable, cfg: Config,
                 pick: int) -> dict:
    """Send the picked card and the rest to their destinations.

    `pick` is an index into the look buffer, or -1 for "I choose none" on a
    card whose choice is optional. The cards have been off the deck since the
    op ran, so every one of them must land somewhere here -- the buffer is
    emptied unconditionally.

    416.1.c: a Recycle goes to the card's OWNER's deck, and the only player who
    can be looking at their own deck's top is that owner, so `seat` is both.
    """
    seat = int(state.pend_look)
    n = int(state.n_look)
    picked = int(state.look_cards[pick]) if 0 <= pick < n else -1
    # "You may reveal a unit from among them" reveals only the one chosen, and
    # "as I'm revealed" (Undertitan) answers to that (RiftJudge #12051).
    from rl.engine.effects import LOOK_REVEAL_PICK
    if picked >= 0 and int(state.look_reveal) == LOOK_REVEAL_PICK:
        _rl: dict = {"resolved": []}
        rsv._run_revealed_abilities(state, table, cfg, seat, picked, _rl)

    # 436.1.a -- "Recycles any number of them". A multi pick moves exactly the
    # chosen card and leaves the look open over what remains, so the next
    # decision is the same question with one fewer card; A_PICK_NONE is
    # "done", and falls through to send the rest to `look_rest_dest`.
    if state.look_multi and picked >= 0:
        dest = int(state.look_pick_dest)
        state.look_cards[pick:n - 1] = state.look_cards[pick + 1:n]
        state.look_cards[n - 1] = -1
        state.n_look = n - 1
        if dest == DEST_RECYCLE:
            state.recycle_card(seat, picked)
        elif dest == DEST_BANISH:
            state.banish_card(seat, picked)
        elif dest == DEST_HAND:
            h = int(state.n_hand[seat])
            assert h < state.hand.shape[1], "hand overflow from a look"
            state.hand[seat, h] = picked
            state.n_hand[seat] = h + 1
        else:
            assert dest == DEST_TRASH, f"multi pick has no path for {dest}"
            phases._to_trash(state, seat, picked, from_deck=True)
        log = {"picked": table.names[picked]}
        if int(state.n_look) > 0:
            return log
        # Took every card: nothing left to put back, so finish as if "done".
        n, pick, picked = 0, -1, -1

    def send(card: int, dest: int) -> None:
        if card < 0:
            return
        if dest == DEST_HAND:
            h = int(state.n_hand[seat])
            assert h < state.hand.shape[1], "hand overflow from a look"
            state.hand[seat, h] = card
            state.n_hand[seat] = h + 1
        elif dest == DEST_RECYCLE:
            state.recycle_card(seat, card)
        elif dest == DEST_BANISH:
            b = int(state.n_banished[seat])
            state.banished[seat, b] = card
            state.n_banished[seat] = b + 1
        else:
            t = int(state.n_trash[seat])
            state.trash[seat, t] = card
            state.n_trash[seat] = t + 1

    # 436.1 -- whatever goes back on TOP is written first, in the order it came
    # off, so the deck reads the same as before for anything not recycled. This
    # runs before the other destinations because it rewinds `deck_ptr`, and a
    # card sent elsewhere must not be sitting in the rewound span.
    top = [int(state.look_cards[i]) for i in range(n)
           if (int(state.look_pick_dest) if i == pick
               else int(state.look_rest_dest)) == DEST_TOP]
    if top:
        ptr = int(state.deck_ptr[seat]) - len(top)
        if ptr >= 0:
            for k, card in enumerate(top):
                state.deck[seat, ptr + k] = card
            state.deck_ptr[seat] = ptr
        else:
            # A card that did not come off this deck (Altar of Memories puts
            # one from hand back) may find nothing drawn to rewind over.
            for card in reversed(top):
                state.put_on_top(seat, card)

    for i in range(n):
        card = int(state.look_cards[i])
        dest = int(state.look_pick_dest) if i == pick else int(state.look_rest_dest)
        if dest == DEST_TOP:
            continue                       # already written back above
        send(card, dest)
    state.look_cards[:] = -1
    state.n_look = 0
    state.pend_look = -1
    state.look_reveal = 0
    state.look_multi = 0
    state.look_max_might = -1
    state.look_last_pick = picked
    if state.rp_armed == 2:
        # Promising Future: this seat's pick is set aside; next look or plays.
        state.rp_armed = 0
        state.pf_cards[seat] = picked
        pf_advance(state, table, seat)
    elif state.rp_armed:
        # OP_REVEAL_PLAY: the pick was banished; now it is played.
        state.rp_armed = 0
        if picked >= 0:
            state.rp_card, state.rp_owner, state.rp_seat = picked, seat, seat
    log = {"picked": table.names[picked] if picked >= 0 else None}
    if int(state.resume_kind):
        # Void Hatchling's peek is answered: the reveal it paused, now.
        log.update(rsv.run_resume(state, table, cfg))
    # A follow-up may be queued -- and may suspend again, in which case
    # `_advance_pending` below correctly does nothing until it resolves.
    log.update(_run_followup(state, table, cfg, seat))
    log.update(_settle_after_decision(state, table, cfg))
    return log


def acting_seat(state: GameState) -> int:
    """Which seat is being asked to choose, or -1 if none is."""
    if is_terminal(state):
        return -1
    if state.pend_mull >= 0:
        return int(state.pend_mull)
    # Combat damage assignment: the seat DEALING the damage chooses, which is
    # the opposite of Altar of Blood below -- tested first because a suspended
    # assignment happens before any death it goes on to cause.
    if state.pend_dmg >= 0:
        return int(state.pend_dmg)
    # Altar of Blood asks the dying unit's CONTROLLER, who is not necessarily
    # the player whose combat damage killed it.
    if state.pend_altar >= 0:
        return int(state.perms[int(state.pend_altar), P_CTRL])
    if state.pend_look >= 0:
        # `pend_play_look` is nested inside this, and belongs to the same seat,
        # so one test covers both -- `legal_actions` picks which question.
        return int(state.pend_look)
    if int(state.pend_double[0]) >= 0:
        return int(state.perms[int(state.pend_double[0]), P_CTRL])
    if int(state.pend_reveal[0]) >= 0:
        return int(state.pend_reveal[0])
    if state.steal_seat >= 0:
        return int(state.steal_seat)
    if state.pend_name >= 0:
        return int(state.pend_name)
    if state.dj_seat >= 0:
        return int(state.dj_seat)
    if state.pend_split >= 0:
        return int(state.pend_split)
    if state.pend_amount >= 0:
        return int(state.pend_amount)
    if state.pend_cull >= 0:
        return int(state.pend_cull)
    if state.pend_grave >= 0:
        return int(state.pend_grave)
    if state.pend_discard >= 0:
        return int(state.pend_discard)
    if state.pend_tax >= 0:
        return int(state.pend_tax)
    if state.pend_ask >= 0:
        return int(state.pend_ask)
    if state.pend_hand_play >= 0:
        return int(state.pend_hand_play)
    if state.rp_seat >= 0:
        return int(state.rp_seat)
    if state.pend_cost_recycle >= 0:
        return int(state.chain[int(state.pend_cost_recycle), C_CTRL])
    if state.pend_cost_kill >= 0:
        return int(state.chain[int(state.pend_cost_kill), C_CTRL])
    if state.pend_kill_play >= 0:
        return int(state.pend_kill_play_seat)
    if state.pend_slot >= 0:
        item = chain.oldest_pending(state)
        if item >= 0:
            return int(state.chain[item, C_CTRL])
    if state.pend_may >= 0:
        return int(state.chain[int(state.pend_may), C_CTRL])
    if state.pend_group_loc >= 0:
        return int(state.pend_group_loc)
    if state.pend_order >= 0:
        return int(state.pend_order)
    if state.n_chain > 0 or state.showdown_bf >= 0:
        return int(state.priority)
    return int(state.active)
