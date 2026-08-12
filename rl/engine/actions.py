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

from rl.config import DOMAINS, Config
from rl.engine import chain, combat, phases
from rl.engine import resolve as rsv
# Payment lives in `cost` so combat can ask about affordability without
# importing the action layer. Re-exported: callers still say A.plan_payment.
from rl.engine.cost import (MULTI_DOMAIN_POWER_IS_PERMISSIVE, accelerate_cost,
                            card_domains, pay, pay_ability_cost,
                            plan_ability_cost, plan_flow, plan_payment,
                            plan_surcharge)
from rl.engine.cardtable import CardTable
from rl.engine.effects import (ABILITY_BORROWERS, CardSpec, FOLLOWUPS,
                               TR_DISCARD,
                               TR_GEAR_ABILITY,
                               DISCARD_BRANCHES,
                               ENTERS_READY_IF, ER_DIED_IN_BEGINNING,
                               SPEED_MAIN,
                               ER_TWO_OTHERS_AT_BASE,
                               OP_EMPOWER, PERM_ENEMY, PERM_NONE,
                               PERM_OPEN, PLAY_PERMISSIONS, TR_ACTIVATED,
                               TR_PLAY_ME, TR_PLAY_SPELL, abilities_for,
                               spec_for)
from rl.engine.state import (C_ABIL, C_BOUND_BF, C_CARD, C_CTRL, C_COST,
                             F_EMPOWERED, F_LEGION, P_FLAGS,
                             PT_GEAR, PT_SPELL, PT_UNIT,
                             C_DEST, COST_FLOW, COST_NO_ENERGY,
                             COST_PRINTED, DEST_BANISH, DEST_HAND,
                             C_REPEAT, DEST_TOP, LOOK_TYPE_BIT,
                             DEST_RECYCLE,
                             C_SRC, MAIN,
                             MAX_CHAIN, MAX_PERMS, MAX_TRIGGERS, N_BF,
                             N_DOMAINS, N_SEATS, P_ALIVE, P_CARD, P_CTRL,
                             P_LOC, P_READY, GameState, base_loc, bf_loc,
                             is_battlefield)

# Action kinds. Wire format -- append only, never reorder.
# A_CANCEL is retained for wire-format stability (the enum is append-only
# and must never renumber) but is no longer offered -- see `legal_actions`.
(A_PASS, A_END_TURN, A_PLAY, A_PLAY_AT, A_DECLARE, A_ADD, A_COMMIT, A_CANCEL,
 A_RETREAT, A_TARGET, A_HIDE, A_HIDE_AT, A_PLAY_HIDDEN,
 A_ACCEPT, A_DECLINE, A_PLAY_AT_FAST, A_ORDER, A_ACTIVATE,
 A_PLAY_FLOW, A_MULLIGAN, A_MULLIGAN_DONE, A_PICK, A_PICK_NONE,
 A_PLAY_REPEAT) = range(24)

KIND_NAMES = ("pass", "end_turn", "play", "play_at", "declare", "add",
              "commit", "cancel", "retreat", "target", "hide", "hide_at",
              "play_hidden", "accept", "decline", "play_at_fast",
              "order", "activate", "play_flow", "mulligan",
              "mulligan_done", "pick", "pick_none", "play_repeat")


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
    # 822.1.b/c -- [Ambush] "adds options to locations that are valid for a
    # Unit to be played to". A battlefield where you CONTROL UNITS, which is a
    # strictly wider set than one you control: a contested battlefield with a
    # unit of yours on it qualifies, and that is the whole card. Reinforcing a
    # fight you are losing is exactly what the keyword is for.
    ambush = [bf_loc(i) for i in range(N_BF)
              if table.has(card, "Ambush")
              and state.units_at(bf_loc(i), seat).size]
    if ambush_only:
        # The Reaction half of 822.1.b is conditional: "I have [Reaction] as
        # long as I'm being played to a battlefield where you control Units."
        # So a unit played in a response window may ONLY go to an Ambush
        # destination -- it has no timing permission to reach its own base.
        return ambush
    # Printed exceptions to 806.3, one per card -- see `effects.PLAY_PERMISSIONS`
    # for what "open" and "occupied" are taken to mean, since neither is a
    # defined rules term. These ADD destinations exactly as [Ambush] does; they
    # never remove the base.
    perm = PLAY_PERMISSIONS.get(table.names[card], PERM_NONE)
    extra = []
    for i in range(N_BF):
        loc = bf_loc(i)
        if perm == PERM_OPEN and not state.seats_at(loc)[0] \
                and not state.seats_at(loc)[1]:
            extra.append(loc)
        elif perm == PERM_ENEMY and state.units_at(loc, 1 - seat).size:
            extra.append(loc)

    own = [bf_loc(i) for i in range(N_BF) if int(state.bf_ctrl[i]) == seat]
    return [base_loc(seat)] + sorted(set(own + ambush + extra))


def _enters_ready(state: GameState, table: CardTable, seat: int,
                  card: int) -> bool:
    """Does this card print its own exception to 359.2.c (enter exhausted)?

    Checked as the unit is played, which is when the card asks. Xin Zhao counts
    the board at that instant -- "two or more OTHER units", and he is not on it
    yet, so every friendly unit at the base is an "other" one.
    """
    kind = ENTERS_READY_IF.get(table.names[card])
    if kind is None:
        return False
    if kind == ER_TWO_OTHERS_AT_BASE:
        return int(state.units_at(base_loc(seat), seat).size) >= 2
    if kind == ER_DIED_IN_BEGINNING:
        return bool(state.died_in_beginning[seat])
    return False


def _played_bits(table: CardTable, card: int) -> int:
    """Which of Swain's kinds this card counts as, when played.

    **A card with more than one type counts for EVERY one of them.** A gear
    unit is both a gear and a unit for Swain's "a non-token unit, a non-token
    gear, and a spell this turn", so this ORs the bits rather than picking one.
    Written as an if/elif first, which would have quietly counted such a card
    once and made the trio a card harder to complete than it is.

    No card in the current export carries two types, so nothing exercises this
    today -- which is exactly why it is worth stating: the chain was wrong in
    principle and would have stayed wrong invisibly until the set that prints
    one landed.
    """
    bits = 0
    if table.is_type(card, "Unit"):
        bits |= PT_UNIT
    if table.is_type(card, "Gear"):
        bits |= PT_GEAR
    if table.is_type(card, "Spell"):
        bits |= PT_SPELL
    return bits


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
def pack_activate(perm: int, donor: int) -> int:
    """(activating permanent, ability donor) -> one action arg."""
    if donor == perm:
        return perm
    return MAX_PERMS * (donor + 1) + perm


def unpack_activate(arg: int) -> tuple[int, int]:
    """The inverse. Returns (permanent, donor); donor == permanent if its own."""
    if arg < MAX_PERMS:
        return arg, arg
    return arg % MAX_PERMS, arg // MAX_PERMS - 1


def _look_type_bit(table: CardTable, card: int) -> int:
    """`LK_*` bit for a card's printed type, for a look's pick restriction."""
    bit = 0
    for name, b in LOOK_TYPE_BIT.items():
        if table.is_type(card, name):
            bit |= b
    return bit


def _main_open(state: GameState, seat: int) -> bool:
    """Is this the ordinary main-phase window a unit is normally played in?"""
    return (state.phase == MAIN and seat == state.active
            and state.n_chain == 0 and state.showdown_bf < 0)


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
    for i in _hand_choices(state, seat):
        card = int(state.hand[seat, i])
        if not table.has(card, "Ambush") or not table.is_type(card, "Unit"):
            continue
        if not play_destinations(state, table, cfg, seat, card,
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
        card = int(row[P_CARD])
        for ab in abilities_for(table, card):
            if ab.trigger != TR_ACTIVATED:
                continue
            if not chain.speed_ok(state, cfg, seat, ab.speed):
                continue
            if ab.cost_exhaust and not row[P_READY]:
                continue
            if ab.cost_xp and int(state.xp[seat]) < ab.cost_xp:
                continue
            # 827.1.c.1 -- "[Cost]: Empower this. Play only if not Empowered."
            # The restriction is part of what the keyword abbreviates, so it is
            # read off the op rather than written on each of the ~35 cards that
            # print it. 441.1.b says the same thing from the other side: an
            # Empowered object cannot be Empowered.
            if (any(op.op == OP_EMPOWER for op in ab.ops)
                    and state.has_flag(i, F_EMPOWERED)):
                continue
            if plan_ability_cost(state, table, seat, card,
                                 ab.cost_energy, ab.cost_power) is None:
                continue
            # 355.8, same as for a card: no legal targets, no activation.
            if ab.n_targets and not rsv.can_be_cast(state, table, ab, seat,
                                                    -1, i, card):
                continue
            out.append(pack_activate(i, i))
            break

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
            for ab in abilities_for(table, dcard):
                if ab.trigger != TR_ACTIVATED or not ab.cost_exhaust:
                    continue
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
                                     ab.cost_energy, ab.cost_power) is None:
                    continue
                if ab.n_targets and not rsv.can_be_cast(state, table, ab, seat,
                                                        -1, i, dcard):
                    continue
                out.append(pack_activate(i, d))
                break
    return out


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
    if state.pend_look >= 0:
        if seat != int(state.pend_look):
            return []
        mask = int(state.look_type_mask)
        out = [Action(A_PICK, i) for i in range(int(state.n_look))
               if not mask or (mask & _look_type_bit(
                   table, int(state.look_cards[i])))]
        # "You may reveal a gear from among them" with no gear among them
        # leaves nothing to pick -- and the card said "may", so declining
        # is the whole answer. A type filter therefore always implies an
        # out, which `effects.py` asserts at import.
        if state.look_optional or not out:
            out.append(Action(A_PICK_NONE))
        assert out, "a look with nothing to pick should never have been pended"
        return out

    # Zilean's replacement: "you may play that token and an additional copy of
    # it instead." Checked before `pend_may` because both use ACCEPT/DECLINE
    # and only one can ever be live -- this one is set during a resolution that
    # has already finished, and `_advance_pending` will not start another until
    # it clears.
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
        out = [Action(A_PICK, i) for i in range(int(state.n_hand[foe]))
               if not mask or (mask & _look_type_bit(
                   table, int(state.hand[foe, i])))]
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

    # Cull the Weak: each player kills one of THEIR OWN units, in turn order.
    # Offered as A_TARGET over the chooser's own live units -- a seat with none
    # never reaches here, because `_advance_cull` skips it.
    if state.pend_cull >= 0:
        if seat != int(state.pend_cull):
            return []
        out = [Action(A_TARGET, i) for i in range(state.n_perms)
               if state.perms[i, P_ALIVE] == 1
               and int(state.perms[i, P_CTRL]) == seat
               and table.is_type(int(state.perms[i, P_CARD]), "Unit")]
        assert out, "a cull with no unit to kill should have been skipped"
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
        return [Action(A_ACCEPT), Action(A_DECLINE)]

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

    # --- mid-decision: a factored choice is open -------------------------
    if state.pend_play >= 0:
        # Normally only the turn player places a unit -- but an [Ambush] unit
        # is played in a response window, which can be the opponent's turn, so
        # the placer is whoever holds priority for that play.
        if seat != int(state.pend_play_seat):
            return []
        card = int(state.hand[seat, state.pend_play])
        dsts = play_destinations(state, table, cfg, seat, card,
                                 ambush_only=not _main_open(state, seat))
        out = [Action(A_PLAY_AT, loc) for loc in dsts]
        # 805.2 -- [Accelerate] is an Optional Additional Cost paid *as* the
        # unit is played, so it belongs to this decision rather than a later
        # one. Folding it into the destination choice keeps the pair atomic:
        # where to put it and whether to pay for haste are the same decision,
        # and splitting them would offer a second decision point with two
        # options and no new information.
        acc = accelerate_cost(table, card)
        if acc is not None and plan_payment(state, table, seat, card,
                                            acc[0], acc[1]) is not None:
            out += [Action(A_PLAY_AT_FAST, loc) for loc in dsts]
        return out

    if state.declaring:
        if seat != state.active:
            return []
        out = [Action(A_ADD, i) for i in
               combat.movable_units(state, table, cfg, state.decl_dst)]
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
                + [Action(A_PLAY, i) for i in
                   chain.playable_hand_indices(state, table, cfg, seat)]
                # 822.1.b -- an [Ambush] unit has [Reaction] while it is being
                # played to a battlefield where you control units, so it is
                # offered in the same windows a Reaction spell is.
                + [Action(A_PLAY, i) for i in
                   ambush_playable(state, table, cfg, seat)]
                # 811.6 -- a facedown card has [Reaction], so it may be played
                # into any window, including on the opponent's turn.
                + [Action(A_PLAY_HIDDEN, i) for i in
                   chain.hidden_playable(state, table, cfg, seat)]
                + [Action(A_PLAY_FLOW, i) for i in
                   chain.flow_playable(state, table, cfg, seat)])

    # --- Main Phase, Neutral Open ----------------------------------------
    # 316.5.b: only the Turn Player may act in a Neutral Open State.
    if state.phase != MAIN or seat != state.active:
        return []

    out: list[Action] = []
    for i in _hand_choices(state, seat):
        card = int(state.hand[seat, i])
        # Gear is a permanent like a unit: it is played, it goes on the board,
        # and 337.2 resolves it immediately with no Chain. The only differences
        # are where it lands (base, 149.2) and that it enters READY (359.2.d).
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            if plan_payment(state, table, seat, card) is None:
                continue
            out.append(Action(A_PLAY, i))
    for i in chain.playable_hand_indices(state, table, cfg, seat):
        out.append(Action(A_PLAY, i))
        # 820.1.c.1 -- [Repeat] is an Additional Cost paid "during the steps of
        # playing", so whether to pay it belongs to THIS decision, exactly as
        # [Accelerate] belongs to the destination choice above. Offered only
        # when the base cost plus the Repeat cost are affordable together:
        # `plan_payment`'s extra_* arguments share the overlapping-pool rule,
        # so this is max(e, p) over the combined cost, not two payments.
        card = int(state.hand[seat, i])
        re_e, re_p = int(table.repeat_energy[card]), int(table.repeat_power[card])
        if re_e >= 0 and plan_payment(state, table, seat, card,
                                      re_e, re_p) is not None:
            out.append(Action(A_PLAY_REPEAT, i))
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

    for i in range(state.n_perms):
        row = state.perms[i]
        if (row[P_ALIVE] == 1 and row[P_CTRL] == seat and row[P_READY] == 1
                and is_battlefield(int(row[P_LOC]))
                and table.is_type(int(row[P_CARD]), "Unit")):
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
    if (state.pend_slot >= 0 or state.pend_may >= 0 or state.pend_order >= 0
            or state.pend_play >= 0 or state.pend_hide >= 0 or state.declaring
            or state.pend_look >= 0 or int(state.pend_double[0]) >= 0
            or int(state.pend_reveal[0]) >= 0 or state.pend_cull >= 0
            or state.pend_discard >= 0 or is_terminal(state)):
        return {}
    log: dict = {}
    # Every queued trigger goes on the Chain BEFORE any of them is finalized:
    # 383.3.d is about the order they are *placed*, and 337.1.b then finalizes
    # oldest-first once they are all there.
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
    log.update(_advance_pending(state, table, cfg))
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
                log.update(combat.cleanup(state, table, cfg,
                                          mover=int(state.active), dst=-1))
                if state.showdown_bf >= 0:
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
        seat = int(state.priority)        # not `active`: responses happen on
        card = int(state.hand[seat, action.arg])  # the opponent's turn too
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            state.pend_play = action.arg
            state.pend_play_seat = seat
            return {}
        return _play_spell(state, table, cfg, seat, action.arg)

    if k == A_PLAY_REPEAT:
        seat = int(state.priority)
        return _play_spell(state, table, cfg, seat, action.arg, repeat=True)

    if k == A_TARGET:
        if state.pend_cull >= 0:
            return _cull_one(state, table, cfg, int(action.arg))
        return _choose_target(state, table, cfg, action.arg)

    if k == A_ACTIVATE:
        return _activate(state, table, cfg, int(state.priority), action.arg)

    if k == A_ORDER:
        state.pend_order = -1
        chain.place(state, table, cfg, action.arg)
        return {}

    if k == A_ACCEPT:
        if int(state.pend_double[0]) >= 0:
            return _resolve_double(state, table, cfg, take=True)
        return _accept_may(state, table, cfg)

    if k == A_DECLINE:
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

    if k in (A_PICK, A_PICK_NONE):
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
        phases.end_turn(state, cfg)
        if not is_terminal(state):
            return phases.start_turn(state, table, cfg)
        return {}

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
    return rsv.choosable_targets(state, table, spec, slot, seat, chosen,
                                 int(state.chain[item, C_BOUND_BF]),
                                 int(state.chain[item, C_SRC]),
                                 int(state.chain[item, C_CARD]))


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
        if spec.n_targets:
            state.pend_slot = 0
            return log
        log.update(_finalize_pending(state, table, cfg, item))
    raise AssertionError("pending chain items are not draining")


def _play_spell(state: GameState, table: CardTable, cfg: Config, seat: int,
                hand_idx: int, repeat: bool = False) -> dict:
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
    if repeat:
        # Recorded now, paid at finalization with the rest of the cost, and
        # read at resolution. 820.1.c.3 -- once only, so this is a flag and
        # never a count.
        state.chain[item, C_REPEAT] = 1
    spec = spec_for(table, card)
    assert spec is not None, f"{table.names[card]!r} has no spec"
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _choose_target(state: GameState, table: CardTable, cfg: Config,
                   perm: int) -> dict:
    item = chain.oldest_pending(state)
    assert item >= 0 and state.pend_slot >= 0, "no slot open"
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
            recycle = plan_ability_cost(state, table, seat, card,
                                        spec.cost_energy, spec.cost_power)
            assert recycle is not None, "unaffordable ability reached finalize"
            pay_ability_cost(state, table, seat, spec.cost_energy, recycle,
                             spec.cost_power, card)
            if spec.cost_exhaust:
                src = int(state.chain[item, C_SRC])
                assert state.perms[src, P_READY], "exhaust cost with no ready source"
                state.perms[src, P_READY] = 0
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
        chain.finalize(state, item)
        state.priority = seat
        return {"finalized_ability": table.names[card]}
    spec_c = spec_for(table, card)
    n_t = spec_c.n_targets if spec_c else 0
    chosen = [int(x) for x in state.chain_targets[item, :n_t]]
    # 809.1.d -- Deflect is a MANDATORY additional cost on the chooser, in
    # Power, of any domain (809.1.c.1). It is owed whether the card came from
    # hand or from hiding: 811.1.b zeroes the CARD's cost, not a surcharge
    # someone else's permanent imposes.
    extra_p = rsv.deflect_cost(state, table, seat, chosen, spec_c)
    # Planned BEFORE anything is paid: `plan_surcharge` reserves the card's own
    # Power first and allocates the surcharge from what is left, so asking it
    # after `pay` had already recycled would spend the same runes twice.
    surcharge = []
    if extra_p:
        surcharge = plan_surcharge(state, table, seat, card, extra_p)
        assert surcharge is not None, "unaffordable Deflect cost at finalization"
    cost_mode = int(state.chain[item, C_COST])
    if cost_mode == COST_FLOW:
        # 829.1.c.1 -- the Flow cost REPLACES the base cost.
        recycle = plan_flow(state, table, seat, card)
        assert recycle is not None, "unaffordable Flow cost reached finalization"
        pay_ability_cost(state, table, seat, int(table.flow_energy[card]),
                         recycle, int(table.flow_power[card]), card)
    elif cost_mode == COST_NO_ENERGY:
        # "ignoring its Energy cost. (You must still pay its Power cost.)" --
        # the reminder is on the card because the two halves are separable, and
        # the Power half is what keeps Fizz honest: a 3-Energy spell replayed
        # free still costs a rune off the board if it has a Power symbol.
        recycle = plan_ability_cost(state, table, seat, card, 0,
                                    int(table.power[card]))
        assert recycle is not None, "unaffordable Power cost reached finalization"
        pay_ability_cost(state, table, seat, 0, recycle,
                         int(table.power[card]), card)
    elif int(state.chain[item, C_BOUND_BF]) < 0:
        # 811.1.b -- a card played from Hidden ignores its cost entirely. The
        # rune was already paid when it was hidden.
        # 820.1.c.1 -- a paid [Repeat] rides along as an Additional Cost, part
        # of the SAME payment rather than a second one, so it goes through
        # `plan_payment`'s extra_* arguments and shares the overlapping-pool
        # rule: max(energy, power) over the combined cost.
        re_e = re_p = 0
        if int(state.chain[item, C_REPEAT]) == 1:
            re_e = max(0, int(table.repeat_energy[card]))
            re_p = max(0, int(table.repeat_power[card]))
        recycle = plan_payment(state, table, seat, card, re_e, re_p)
        assert recycle is not None, "unaffordable spell reached finalization"
        pay(state, table, seat, card, recycle, re_e, re_p)
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
    # "When you play a spell" -- 349 makes a card *played* at finalization, not
    # at resolution, so Ravenbloom Student grows the moment the spell is
    # committed to the Chain and keeps the Might even if it is countered.
    if table.is_type(card, "Spell"):
        for u in range(state.n_perms):
            row = state.perms[u]
            if row[P_ALIVE] != 1 or int(row[P_CTRL]) != seat:
                continue
            if chain.has_trigger(table, int(row[P_CARD]), TR_PLAY_SPELL):
                chain.queue(state, TR_PLAY_SPELL, u, int(row[P_LOC]))
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
    perm, donor = unpack_activate(perm)
    # The SPEC comes from the donor; the SOURCE stays the activating permanent.
    # For an ordinary activation the two are the same permanent. `item_spec`
    # already reads C_CARD and C_SRC independently, so a borrowed ability needs
    # nothing new on the Chain.
    card = int(state.perms[donor, P_CARD])
    idx = next(k for k, ab in enumerate(abilities_for(table, card))
               if ab.trigger == TR_ACTIVATED
               and (donor == perm or ab.cost_exhaust))
    spec = abilities_for(table, card)[idx]

    # "When you use an activated ability of a GEAR" -- Prize of Progress. Fired
    # as the ability is activated (151.2.a makes that the moment it is played),
    # not when it resolves, so a countered ability still counts as used.
    if table.is_type(card, "Gear"):
        chain.fire_watchers(state, table, seat, TR_GEAR_ABILITY, subj=perm)

    if spec.immediate:
        # 337.2 -- a resource-adding ability resolves immediately and never
        # touches the Chain, so no window opens in which the opponent could
        # answer the resource before it exists.
        recycle = plan_ability_cost(state, table, seat, card,
                                    spec.cost_energy, spec.cost_power)
        assert recycle is not None, "unaffordable ability reached _activate"
        pay_ability_cost(state, table, seat, spec.cost_energy, recycle,
                         spec.cost_power, card)
        if spec.cost_exhaust:
            state.perms[perm, P_READY] = 0
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
             bf: int) -> dict:
    """Hide the pending card facedown at `bf` for one rune (811.1.b).

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

    dom = int(np.argmax(state.runes_ready[seat]))     # pay [A]: any one rune
    assert state.runes_ready[seat, dom] > 0, "hide with no ready rune"
    state.runes_ready[seat, dom] -= 1
    state.runes_spent[seat, dom] += 1

    state.fd_owner[bf] = seat
    state.fd_card[bf] = card
    state.fd_ply[bf] = int(state.ply)
    return {"hid_at": bf}


def _play_flow(state: GameState, table: CardTable, cfg: Config, seat: int,
               trash_idx: int) -> dict:
    """829.1.b -- play a spell from the trash for its Flow cost.

    The card leaves the trash now, exactly as a hand card leaves the hand on
    announcement. Where it goes AFTER resolving is the interesting part, and
    that is `resolve_top`'s job: banished, not trashed.
    """
    card = int(state.trash[seat, trash_idx])
    n = int(state.n_trash[seat])
    state.trash[seat, trash_idx:n - 1] = state.trash[seat, trash_idx + 1:n]
    state.trash[seat, n - 1] = -1
    state.n_trash[seat] = n - 1

    item = chain.push(state, card, seat, from_hand=False, bound_bf=-1,
                      cost=COST_FLOW, dest=DEST_BANISH)
    spec = spec_for(table, card)
    assert spec is not None
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced_from_trash": table.names[card]}
    return _finalize_pending(state, table, cfg, item)


def _play_from_hidden(state: GameState, table: CardTable, cfg: Config,
                      seat: int, bf: int) -> dict:
    """Play the facedown card at `bf` for 0 energy (811.1.b).

    Its bound target slots are restricted to that battlefield (811.1.d.2.a),
    which is carried on the chain item as `C_BOUND_BF` -- free slots ignore it,
    which is why Smoke and Mirrors still reaches across the board.
    """
    card = int(state.fd_card[bf])
    assert int(state.fd_owner[bf]) == seat, "not this seat's facedown card"
    state.fd_owner[bf] = -1
    state.fd_card[bf] = -1
    state.fd_ply[bf] = -1

    item = chain.push(state, card, seat, from_hand=False, bound_bf=bf)
    spec = spec_for(table, card)
    assert spec is not None
    if spec.n_targets:
        state.pend_slot = 0
        return {"announced_from_hidden": table.names[card], "at": bf}
    return _finalize_pending(state, table, cfg, item)


def _resolve_play(state: GameState, table: CardTable, cfg: Config,
                  seat: int, loc: int, fast: bool = False) -> dict:
    """Pay for the pending card and put it on the board.

    Units enter **exhausted** unless `[Accelerate]` was paid, so a unit played to
    a Battlefield cannot move again this turn and is locked there through the
    opponent's turn. That is the commitment, and it is why playing onto an empty
    Battlefield is a different decision from moving onto one.
    """
    idx = state.pend_play
    card = int(state.hand[seat, idx])
    extra = accelerate_cost(table, card) if fast else None
    assert not fast or extra is not None, "accelerated a card without [Accelerate]"
    ee, ep = extra if extra else (0, 0)
    recycle = plan_payment(state, table, seat, card, ee, ep)
    assert recycle is not None, "unaffordable card reached _resolve_play"
    pay(state, table, seat, card, recycle, ee, ep)

    n = int(state.n_hand[seat])
    state.hand[seat, idx:n - 1] = state.hand[seat, idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1
    state.pend_play = -1
    state.pend_play_seat = -1

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
    enters_ready = fast or not is_unit or _enters_ready(state, table, seat, card)
    src = state.add_permanent(card, seat, loc, ready=enters_ready,
                              is_unit=is_unit)
    if legion:
        state.perms[src, P_FLAGS] |= F_LEGION
    # "When you play a unit" watchers -- Lillia. Queued after the permanent is
    # on the board, so a watcher that is itself the unit being played sees a
    # consistent board.
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
    state.once_used[src] = int(state.turn)
    log: dict = {}
    if take:
        row = state.add_permanent(card, seat, loc, ready=False,
                                  is_unit=bool(table.is_type(card, "Unit")))
        log["doubled"] = row
        # 187 -- the copy is PLAYED like any other token, so a watcher for
        # "when you play a token unit" sees it too. Lillia counts both.
        chain.fire_play_unit(state, table, seat, card, row)
    log.update(_advance_pending(state, table, cfg))
    return log


def _has_cullable(state: GameState, table: CardTable, seat: int) -> bool:
    return any(state.perms[i, P_ALIVE] == 1
               and int(state.perms[i, P_CTRL]) == seat
               and table.is_type(int(state.perms[i, P_CARD]), "Unit")
               for i in range(state.n_perms))


def _advance_cull(state: GameState, table: CardTable, seat_done: int) -> None:
    """Hand the cull to the next seat that actually has a unit, or end it."""
    nxt = seat_done + 1
    while nxt < N_SEATS and not _has_cullable(state, table, nxt):
        nxt += 1
    state.pend_cull = nxt if nxt < N_SEATS else -1


def _cull_one(state: GameState, table: CardTable, cfg: Config,
              perm: int) -> dict:
    """One seat's "kill one of their units", then pass to the next."""
    seat = int(state.pend_cull)
    combat.destroy(state, table, perm)
    _advance_cull(state, table, seat)
    log = {"culled": perm}
    if state.pend_cull < 0:
        log.update(_advance_pending(state, table, cfg))
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
    if key < 0 or key >= len(FOLLOWUPS) or not FOLLOWUPS[key]:
        return {}
    return rsv.resolve(state, table, cfg,
                       CardSpec(speed=SPEED_MAIN, ops=FOLLOWUPS[key]),
                       seat, [], -1, True, source=src)


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

    n = int(state.n_hand[seat])
    card = int(state.hand[seat, hand_idx])
    state.hand[seat, hand_idx:n - 1] = state.hand[seat, hand_idx + 1:n]
    state.hand[seat, n - 1] = -1
    state.n_hand[seat] = n - 1
    phases._to_trash(state, seat, card)
    # A chosen discard is still a discard, so the same watchers see it.
    chain.fire_watchers(state, table, seat, TR_DISCARD)

    log: dict = {"discarded": table.names[card]}
    branches = DISCARD_BRANCHES[key] if 0 <= key < len(DISCARD_BRANCHES) else {}
    for type_name, ops in branches.items():
        if not table.is_type(card, type_name):
            continue
        log.setdefault("branches", []).append(type_name)
        rsv.resolve(state, table, cfg, CardSpec(speed=SPEED_MAIN, ops=ops),
                    seat, [], -1, True, source=src)
    log.update(_advance_pending(state, table, cfg))
    return log


def _finish_reveal(state: GameState, table: CardTable, cfg: Config,
                   pick: int) -> dict:
    """Recycle the chosen card out of the revealed hand (416.1.c).

    The card goes to its OWNER's deck, not the chooser's -- 416.1.c is explicit
    that each player recycles to their own Main Deck regardless of who was
    instructed to perform the Recycle. Everything not chosen stays in hand
    untouched; only the one card moves.
    """
    foe = int(state.pend_reveal[1])
    state.pend_reveal[:] = (-1, -1)
    log: dict = {}
    n = int(state.n_hand[foe])
    if 0 <= pick < n:
        card = int(state.hand[foe, pick])
        state.hand[foe, pick:n - 1] = state.hand[foe, pick + 1:n]
        state.hand[foe, n - 1] = -1
        state.n_hand[foe] = n - 1
        state.recycle_card(foe, card)
        log["sabotaged"] = table.names[card]
    log.update(_advance_pending(state, table, cfg))
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
        assert ptr >= 0, "put-back underflows the deck"
        for k, card in enumerate(top):
            state.deck[seat, ptr + k] = card
        state.deck_ptr[seat] = ptr

    for i in range(n):
        card = int(state.look_cards[i])
        dest = int(state.look_pick_dest) if i == pick else int(state.look_rest_dest)
        if dest == DEST_TOP:
            continue                       # already written back above
        send(card, dest)
    state.look_cards[:] = -1
    state.n_look = 0
    state.pend_look = -1
    log = {"picked": table.names[picked] if picked >= 0 else None}
    # A follow-up may be queued -- and may suspend again, in which case
    # `_advance_pending` below correctly does nothing until it resolves.
    log.update(_run_followup(state, table, cfg, seat))
    log.update(_advance_pending(state, table, cfg))
    return log


def acting_seat(state: GameState) -> int:
    """Which seat is being asked to choose, or -1 if none is."""
    if is_terminal(state):
        return -1
    if state.pend_mull >= 0:
        return int(state.pend_mull)
    if state.pend_look >= 0:
        return int(state.pend_look)
    if int(state.pend_double[0]) >= 0:
        return int(state.perms[int(state.pend_double[0]), P_CTRL])
    if int(state.pend_reveal[0]) >= 0:
        return int(state.pend_reveal[0])
    if state.pend_cull >= 0:
        return int(state.pend_cull)
    if state.pend_discard >= 0:
        return int(state.pend_discard)
    if state.pend_slot >= 0:
        item = chain.oldest_pending(state)
        if item >= 0:
            return int(state.chain[item, C_CTRL])
    if state.pend_may >= 0:
        return int(state.chain[int(state.pend_may), C_CTRL])
    if state.pend_order >= 0:
        return int(state.pend_order)
    if state.n_chain > 0 or state.showdown_bf >= 0:
        return int(state.priority)
    return int(state.active)
