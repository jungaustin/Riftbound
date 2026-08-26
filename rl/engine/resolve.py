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

import numpy as np

from rl.config import Config
from rl.engine import phases
from rl.engine.cardtable import CardTable
from rl.engine import combat
from rl.engine.effects import (COND_ANY_TARGET_TEMPORARY, COND_DIED_ALONE,
                               COND_FROM_HAND,
                               COND_EMPOWERED, COND_PLAYED_TRIO,
                               COND_FEW_RUNES, COND_NOT_DIED_ALONE,
                               COND_CTX_BATTLEFIELD, COND_CTX2_BATTLEFIELD,
                               COND_SELF_AT_BF,
                               COND_N_OTHERS_HERE, COND_OTHERS_MIGHT,
                               CT_MY_BATTLEFIELDS, CT_MY_MIGHTY_UNITS,
                               CT_MY_OTHER_BATTLEFIELDS,
                               CT_ENEMIES_AT_TARGET, COND_READY_ENEMY_HERE,
                               COND_FIRST_TURN, COND_WAS_MIGHTY,
                               COND_FEWER_RUNES_THAN_OPP,
                               COND_PAID_ADDITIONAL,
                               COND_LEGION, COND_LEVEL, COND_NONE,
                               COND_ONLY_UNIT_THERE,
                               LOC_BOUND, OP_COUNTER, OP_DAMAGE,
                               OP_DRAW_CONTROLLER, OP_KILL,
                               OP_CREATE_TOKEN, OP_MOVE_TO,
                               OP_RETURN_TO_HAND,
                               OP_DRAW, OP_NO_SPELLS,
                               OP_MODIFY_MIGHT, OP_STUN,
                               COND_CONTROL_N_GEAR, OP_ADD_ENERGY,
                               OP_ADD_POWER, OP_BLINK, OP_BUFF,
                               OP_BUFF_ALL_AT,
                               OP_DAMAGE_ALL,
                               OP_DISCARD, OP_EXHAUST_ALL, OP_HEAL_AT,
                               OP_KILL_ALL, OP_MODIFY_MIGHT_ALL,
                               OP_READY, OP_SWAP_LOC,
                               REL_DIFFERENT_LOC, REL_NONE,
                               REL_SAME_BF, TK_BATTLEFIELD, TK_UNIT,
                               W_ANY, W_ENEMY,
                               TK_LOCATION, TK_SPELL, TK_TRASH_CARD,
                               OP_TRASH_TO_HAND, OP_PLAY_FROM_TRASH,
                               OP_PLAY_UNIT_FROM_TRASH, W_FRIENDLY,
                               OP_RECYCLE_FROM_TRASH, OP_GAIN_XP,
                               OP_LOOK_TOP, OP_EMPOWER, OP_CHANNEL,
                               OP_DEATH_GUARD, OP_REVEAL_HAND, OP_SCORE,
                               OP_EACH_KILLS_OWN, OP_NO_MOVE,
                               OP_ANY_DAMAGE_KILLS, OP_SWAP_MIGHT,
                               OP_READY_RUNES, OP_DISCARD_CHOOSE,
                               OP_READY_LEGEND,
                               FOLLOWUPS, SPEED_MAIN,
                               OP_RECYCLE_SELF,
                               OP_SEE_HAND, OP_SEE_FACEDOWN,
                               OP_GRANT_KEYWORD,
                               TR_PLAY_ME, T_COMBAT,
                               T_CTX, T_CTX2, T_HERE, T_MY_BASE,
                               T_OWNER_BASE, T_SELF, T_SUBJECT,
                               TOKEN_DOUBLERS,
                               CardSpec, Op, pack_trash, unpack_trash,
                               TargetSpec)
from rl.engine import chain
from rl.engine.state import (C_ABIL, C_CARD, C_CTRL, C_FINAL, C_UID, COST_FREE,
                             LOOK_TYPE_BIT,
                             COST_NO_ENERGY, COST_PRINTED,
                             F_BUFFED,
                             F_DIED_ALONE, F_DIED_MIGHTY,
                             F_EMPOWERED, F_LEGION, F_NO_MOVE,
                             F_PAID_ADDITIONAL,
                             GRANT_IDX, N_BF, N_SEATS, P_ALIVE,
                             PT_GEAR, PT_SPELL, PT_UNIT,
                             P_FLAGS,
                             P_CARD, P_CTRL, P_DMG, P_LOC, P_MIGHT_MOD,
                             P_READY, GameState,
                             LOC_NONE,
                             base_loc, bf_index, bf_loc,
                             bf_src_index, is_bf_src,
                             is_legend_src,
                             is_battlefield)


def source_loc(state: GameState, source: int) -> int:
    """Where an ability's source stands -- its "here". -1 if it has none.

    **The one decoder for the question**, because there are now three kinds of
    source and two places that ask. A permanent is at its row's location; a
    battlefield IS a location, and unlike a permanent's it cannot move or die,
    so it never fizzles; a legend has no location at all (107.4.b -- the Legend
    Zone is not one), and -1 is the honest answer rather than a lie that would
    put its abilities somewhere.

    Split out after `same_loc_as_source` silently excluded every battlefield
    source: it tested `source < 0`, which is true of every sentinel, so
    Emperor's Dais found no candidates for "a unit you control HERE" and 355.8
    refused to put the ability on the Chain at all. The ability simply never
    happened, with nothing to see -- a trigger that declines to fire looks the
    same as one that was never written.
    """
    if is_bf_src(source):
        return bf_loc(bf_src_index(source))
    if is_legend_src(source):
        return -1
    return int(state.perms[source, P_LOC]) if source >= 0 else -1


def deflect_cost(state: GameState, table: CardTable, seat: int,
                 chosen: list[int], spec: CardSpec | None = None) -> int:
    """Extra Power owed for choosing [Deflect] permanents (809.1.c).

    "Spells and abilities an OPPONENT controls that target me cost an amount of
    Power equal to the Deflect Value more to play, for each time they choose
    me." Three details the wording carries and a naive reading drops:

      - only an opponent's spell pays it, so targeting your own Deflect unit
        is free;
      - it is per CHOICE, so a card that targets the same unit twice pays
        twice -- which is why this sums over `chosen` rather than over the set;
      - 809.1.c.1 the Power may be of ANY domain, unlike a printed Power cost.
    """
    total = 0
    for slot, p in enumerate(chosen):
        # **A slot's value means whatever its KIND says.** A TK_LOCATION slot
        # holds 0-3, which are perfectly valid permanent ROW indices, so
        # reading every slot as a row charged a phantom surcharge for whichever
        # unit happened to sit in row 2 -- and then failed the affordability
        # assert at finalization. Only unit slots can carry a Deflect target.
        if spec is not None:
            if slot >= spec.n_targets or spec.targets[slot].kind != TK_UNIT:
                continue
        if p is None or p < 0 or p >= state.n_perms:
            continue
        if state.perms[p, P_ALIVE] != 1 or int(state.perms[p, P_CTRL]) == seat:
            continue
        total += combat.perm_kw(state, table, p, "Deflect")
    return total


def _affordable_with(state: GameState, table: CardTable, card: int, seat: int,
                     chosen: list[int], extra: int,
                     spec: CardSpec | None = None) -> bool:
    """Could `seat` still pay for `card` after choosing these targets?

    Deflect turns affordability into part of target LEGALITY: a target the
    caster cannot pay the surcharge for was never a legal choice, and offering
    it would announce a card that can never be finalized -- the same deadlock
    shape as a target dead-end.
    """
    if card < 0:
        return True
    need = deflect_cost(state, table, seat, chosen, spec) + extra
    if need <= 0:
        return True
    from rl.engine.cost import plan_surcharge
    return plan_surcharge(state, table, seat, card, need) is not None


def _matches(state: GameState, table: CardTable, spec: TargetSpec, perm: int,
             seat: int, chosen: list[int], bound_bf: int,
             source: int = -1, parent: CardSpec | None = None) -> bool:
    """Does `perm` satisfy one slot's restrictions?"""
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
        return False
    # "I can't be chosen by enemy spells and abilities" (Ruin Runner). A
    # prohibition rather than a surcharge -- [Deflect] makes you pay, this
    # makes the unit not a legal choice at all, so it never reaches the slot.
    if combat.unchoosable_by(state, table, perm, seat):
        return False
    card = int(row[P_CARD])
    # `card_type` overrides the kind's default. A TK_UNIT slot means "a unit"
    # unless the card says otherwise -- Salvage kills a GEAR, and gear are
    # permanents on the board like any other, so they need the same slot rather
    # than a parallel target kind.
    if spec.card_type:
        if not any(table.is_type(card, t) for t in spec.card_type):
            return False
    elif spec.kind == TK_UNIT and not table.is_type(card, "Unit"):
        return False
    # A tag whitelist -- Bubble Bot's "another friendly Mech". Tags carry no
    # rules of their own; they exist only to be named like this.
    if spec.tags and not any(t in table.tags[card] for t in spec.tags):
        return False
    if spec.not_self and perm == source:
        return False          # "another unit" -- never the ability's own source

    ctrl, loc = int(row[P_CTRL]), int(row[P_LOC])
    if spec.who == W_FRIENDLY and ctrl != seat:
        return False
    if spec.who == W_ENEMY and ctrl == seat:
        return False

    # "an enemy unit HERE" on a unit's own ability -- the source's location.
    # Distinct from `rel`/`rel_to`, which can only relate a slot to an earlier
    # SLOT and so cannot say this at all; and from `at_battlefield`, which says
    # "at SOME battlefield" and would let Crackshot Corsair shoot across the
    # board. With no source (a spell), there is no "here" and nothing matches.
    if spec.same_loc_as_source and source_loc(state, source) != loc:
        return False

    if spec.lacks_keyword and combat.perm_kw(state, table, perm,
                                            spec.lacks_keyword):
        return False
    if spec.at_battlefield and not is_battlefield(loc):
        return False
    # "a unit at a base" -- unqualified, so EITHER base. `who` narrows it to
    # one side when the card says so; without that this would silently mean
    # "your base" and Rocket Barrage could never hit anything worth hitting.
    if spec.at_base and is_battlefield(loc):
        return False
    # "with 3 Might or less" asks what the unit's Might IS, not what its corner
    # prints -- `combat.might` is the single read path, and reading the table
    # here let a 2-Might body pumped to 7 stay a legal choice. Because
    # `_matches` runs again at resolution (359.3.e), the effective reading also
    # makes the restriction re-check correctly: pumping the target during the
    # response window takes it out of range.
    if spec.max_might >= 0 and combat.might(state, table, perm) > spec.max_might:
        return False
    # "an enemy unit with LESS Might than" an earlier slot's choice. Strictly
    # less, and both sides effective, so a static or a buff on either unit
    # moves the line. Re-checked at resolution like any other restriction.
    if 0 <= spec.less_might_than < len(chosen):
        other = chosen[spec.less_might_than]
        if other < 0 or combat.might(state, table, perm) >= combat.might(
                state, table, other):
            return False
    # "a gear with Energy cost no more than {1 energy}" -- the same restriction
    # `_trash_card_ok` already applied to a card in a pile, now on the board.
    if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
        return False
    # "an enemy Chaos unit or gear" -- the target's own printed domain.
    if spec.domain >= 0 and not (int(table.domain_mask[card]) >> spec.domain & 1):
        return False
    # 459 -- the Attacker's units at the contested battlefield are the
    # attacking ones. Outside a Showdown nobody is attacking, so the slot is
    # empty and the card is simply unplayable (355.8).
    if spec.attacking and not (
            state.showdown_bf >= 0
            and ctrl == int(state.attacker)
            and loc == bf_loc(int(state.showdown_bf))):
        return False

    # 811.1.d.2.a -- a bound slot may only reach the battlefield the card was
    # hidden at. `bound_bf` is -1 when the card was not played from hiding, in
    # which case locality never applies.
    if bound_bf >= 0 and spec.locality == LOC_BOUND and loc != bf_loc(bound_bf):
        return False

    # "another unit" relative to an earlier SLOT, with no location clause.
    if 0 <= spec.distinct_from < len(chosen) and perm == chosen[spec.distinct_from]:
        return False

    if spec.rel != REL_NONE and 0 <= spec.rel_to < len(chosen):
        other = chosen[spec.rel_to]
        if other < 0:
            return False
        # **What the referenced slot HOLDS decides how to read it.** "another
        # unit at a different location" points at a unit row; Crescent Strike's
        # "an enemy unit THERE" points at a battlefield slot, which holds a
        # location. Reading a location as a permanent row silently compares
        # against whatever unit happens to sit in row 0-3 -- a valid index and
        # the wrong question.
        ref_kind = (parent.targets[spec.rel_to].kind
                    if parent is not None and spec.rel_to < parent.n_targets
                    else TK_UNIT)
        if ref_kind in (TK_BATTLEFIELD, TK_LOCATION):
            other_loc = other
        else:
            if perm == other:
                return False               # "another unit" is never the same one
            other_loc = int(state.perms[other, P_LOC])
        if spec.rel == REL_SAME_BF and loc != other_loc:
            return False
        if spec.rel == REL_DIFFERENT_LOC and loc == other_loc:
            return False
    return True


def _spell_targets(state: GameState, table: CardTable, spec: TargetSpec,
                   seat: int, chosen: list[int]) -> list[int]:
    """Chain items this slot may counter, as stable uids.

    Excludes items still Pending and the countering card itself: at the moment
    its targets are chosen it is the newest item on the chain, and a spell
    cannot counter itself.

    **A unit is not a spell, and neither is an ability.** Units never appear
    here at all -- 337.2 resolves them immediately at finalization, so they
    never become a Chain Item and there is nothing to counter. Abilities DO sit
    on the Chain (383.3), and eleven of the thirteen counter cards in the pool
    say "Counter a spell" and mean only that; just Not So Fast and Repulse say
    "spell or ability". So the slot has to opt IN to reaching abilities, and
    the default excludes them.

    The cost restrictions come off the printed card, which is meaningful for a
    spell and meaningless for an ability -- Defy's "costs no more than
    {4 energy}" would otherwise be measured against the ability's SOURCE card,
    a number the ability never had.
    """
    out = []
    newest = state.n_chain - 1
    for i in range(state.n_chain):
        if i == newest or state.chain[i, C_FINAL] != 1:
            continue
        is_ability = int(state.chain[i, C_ABIL]) >= 0
        if is_ability and not spec.chain_abilities:
            continue
        ctrl = int(state.chain[i, C_CTRL])
        if spec.who == W_FRIENDLY and ctrl != seat:
            continue
        if spec.who == W_ENEMY and ctrl == seat:
            continue
        card = int(state.chain[i, C_CARD])
        if not is_ability:
            if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
                continue
            if spec.max_power >= 0 and int(table.power[card]) > spec.max_power:
                continue
        if spec.chooses_friendly_perm and not _chose_friendly_perm(
                state, table, i, seat):
            continue
        uid = int(state.chain[i, C_UID])
        if uid not in chosen:
            out.append(uid)
    return out


def _chose_friendly_perm(state: GameState, table: CardTable, item: int,
                         seat: int) -> bool:
    """Did Chain Item `item` choose a unit or gear controlled by `seat`?

    Read off that item's own recorded targets. **A slot's value means whatever
    its KIND says** -- a location slot holds 0-3 and a counterspell slot holds
    a Chain uid, both of which are valid permanent ROW indices and neither of
    which is a permanent. So this consults the source's spec and skips every
    slot that is not a unit slot; the same trap `deflect_cost` documents, and
    it would misfire in exactly the same way.
    """
    src_spec = chain.item_spec(state, table, item)
    if src_spec is None:
        return False
    for slot in range(src_spec.n_targets):
        if src_spec.targets[slot].kind != TK_UNIT:
            continue
        p = int(state.chain_targets[item, slot])
        if p < 0 or p >= state.n_perms:
            continue
        if state.perms[p, P_ALIVE] == 1 and int(state.perms[p, P_CTRL]) == seat:
            return True
    return False


def can_play_from_trash(state: GameState, table: CardTable, seat: int,
                        card: int, cost_mode: int) -> bool:
    """Could `seat` play this card out of their trash right now?

    **Asked twice, and the second time is the one that matters.** At
    finalization it is a target restriction: it stops the player choosing a
    card that could never be played. At resolution it is re-asked, because a
    full priority window sits between the two -- Fizz's ability finalizes,
    the opponent responds, and only then does the ability resolve and try to
    play what it named.

    Two real-deck fuzz deadlocks came from having only the first check.
    Seed 45 replayed Rebuke ("return a unit at a battlefield") onto a board
    with no unit at a battlefield; seed 1995 replayed Gust after its only legal
    target had been answered in that very window. Both left a spell Pending
    with an empty option list, which is a deadlock rather than a fizzle.

    359.3.e.14.a says a card that cannot legally choose all its targets cannot
    be played, so the honest outcome is that the play simply does not happen.
    """
    from rl.engine.cost import plan_ability_cost, plan_payment
    from rl.engine.effects import spec_for as _spec_for
    # **A unit is playable whether or not its text is encoded; a spell is not.**
    # 337.2 resolves a unit immediately and it simply stands there, so a unit
    # with rules text the DSL cannot express is still a perfectly good unit --
    # real decks are full of them and the engine plays them from hand every
    # game. A SPELL with no spec has nothing to do on resolution, so playing it
    # would be a no-op that spent a card, and it has target slots that could
    # dead-end. Requiring a spec of both made The Harrowing able to reanimate
    # nothing at all.
    is_unit = bool(table.is_type(card, "Unit"))
    card_spec = None if is_unit else _spec_for(table, card)
    if not is_unit and card_spec is None:
        return False                       # no rules text the engine can run
    # "ignoring its Energy cost. (You must still pay its Power cost.)"
    if cost_mode == COST_FREE:
        plan = []                          # "ignoring its cost": nothing to pay
    elif cost_mode == COST_NO_ENERGY:
        plan = plan_ability_cost(state, table, seat, card, 0,
                                 int(table.power[card]))
    else:
        plan = plan_payment(state, table, seat, card)
    if plan is None:
        return False
    # Terminates because no spell in the pool replays a spell that replays a
    # spell; two that did would recurse forever right here.
    return card_spec is None or not card_spec.n_targets or can_be_cast(
        state, table, card_spec, seat, -1, card=card)


def _pay_trash_play(state: GameState, table: CardTable, seat: int, card: int,
                    cost_mode: int) -> None:
    """Charge for a card played out of the trash, per its cost mode."""
    from rl.engine.cost import pay, pay_ability_cost, plan_ability_cost, \
        plan_payment
    if cost_mode == COST_FREE:
        return                             # "ignoring its cost"
    if cost_mode == COST_NO_ENERGY:
        recycle = plan_ability_cost(state, table, seat, card, 0,
                                    int(table.power[card]))
        assert recycle is not None, "unaffordable Power cost reached the play"
        pay_ability_cost(state, table, seat, 0, recycle,
                         int(table.power[card]), card)
        return
    recycle = plan_payment(state, table, seat, card)
    assert recycle is not None, "unaffordable card reached the play"
    pay(state, table, seat, card, recycle)


def _trash_card_ok(table: CardTable, spec: TargetSpec, card: int,
                   state: GameState | None = None, seat: int = -1) -> bool:
    """Does one card in the trash satisfy a TK_TRASH_CARD slot's restrictions?"""
    if spec.card_type and not any(table.is_type(card, t) for t in spec.card_type):
        return False
    if spec.playable:
        # A card about to be PLAYED needs more than a matching type. Everything
        # that makes a card unplayable from hand makes it an illegal CHOICE
        # here, because choosing it announces a spell that then cannot be
        # finalized -- and an unfinalizable spell sits Pending with an empty
        # option list, which is a deadlock rather than a fizzle.
        #
        # Found by the real-deck fuzz on seed 45: Fizz replayed Rebuke ("return
        # a unit at a battlefield to its owner's hand") onto a board with no
        # unit at any battlefield, 291 steps in.
        if state is None:
            from rl.engine.effects import spec_for as _spec_for
            return _spec_for(table, card) is not None
        if not can_play_from_trash(state, table, seat, card,
                                   spec.playable_cost):
            return False
    if spec.tags and not any(t in table.tags[card] for t in spec.tags):
        return False
    if spec.has_keyword and not table.has(card, spec.has_keyword):
        return False
    if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
        return False
    if spec.max_power >= 0 and int(table.power[card]) > spec.max_power:
        return False
    return True


def _trash_seats(spec: TargetSpec, seat: int) -> tuple[int, ...]:
    """Which trashes a slot may draw from -- the pile(s) `spec.who` names.

    An unqualified "from trashes" reaches both piles. That is not a generosity
    the engine grants; it is what the card omits to restrict, the same way an
    unqualified "a unit" may be pointed at your own.
    """
    if spec.who == W_FRIENDLY:
        return (seat,)
    if spec.who == W_ENEMY:
        return tuple(s for s in range(N_SEATS) if s != seat)
    return (seat,) + tuple(s for s in range(N_SEATS) if s != seat)


def _trash_targets(state: GameState, table: CardTable, spec: TargetSpec,
                   seat: int, chosen: list[int]) -> list[int]:
    """Distinct cards in the trashes this slot may name (108.2.c).

    Returns values packed by `pack_trash`, deduplicated: two copies of one card
    in an unordered zone are the same choice, and offering both would double the
    branching factor to describe a decision that does not exist. Two copies in
    DIFFERENT trashes are not the same choice, which is why the owner is part of
    the packed value and part of the key counted below.

    But a slot may still name a card an EARLIER slot already named, so long as
    the trash actually holds another copy -- Guerilla Warfare returning two
    Sprite Calls is legal when two are there and illegal when one is. So the
    exclusion counts copies rather than testing membership, which is the same
    duplicate bookkeeping [Flow] needed and the opposite of the `not in chosen`
    rule that unit slots use (a permanent row IS unique).
    """
    have: dict[int, int] = {}
    for owner in _trash_seats(spec, seat):
        for i in range(int(state.n_trash[owner])):
            key = pack_trash(owner, int(state.trash[owner, i]))
            have[key] = have.get(key, 0) + 1
    out: list[int] = []
    for key, count in have.items():
        if chosen.count(key) >= count:
            continue
        if _trash_card_ok(table, spec, unpack_trash(key)[1], state, seat):
            out.append(key)
    return sorted(out)


def take_from_trash(state: GameState, owner: int, card: int) -> bool:
    """Remove one copy of `card` from `owner`'s trash. False if it is not there.

    Any copy will do -- 108.2.c makes the zone unordered, so the copies are
    interchangeable and there is no "which one" to get right. The caller checks
    the return value because the trash it was promised at finalization is not
    the trash it gets at resolution: a whole priority window stands between.
    """
    n = int(state.n_trash[owner])
    idx = next((i for i in range(n) if int(state.trash[owner, i]) == card), -1)
    if card < 0 or idx < 0:
        return False
    state.trash[owner, idx:n - 1] = state.trash[owner, idx + 1:n]
    state.trash[owner, n - 1] = -1
    state.n_trash[owner] = n - 1
    return True


def _location_targets(state: GameState, spec: TargetSpec, seat: int,
                      bound_bf: int) -> list[int]:
    """Locations this slot may name.

    811.1.d.1/d.3 -- a hidden permanent, and a unit played by a hidden spell,
    must go to the battlefield the card was hidden at. A slot marked LOC_FREE
    ignores that, which is what lets Ride The Wind move a unit anywhere while
    Sprite Call's token is pinned.
    """
    if bound_bf >= 0 and spec.locality == LOC_BOUND:
        return [bf_loc(bound_bf)]
    if spec.play_destination:
        # 806.3 -- a Unit may only be PLAYED to your base or a Battlefield you
        # control. A movement destination is any location; a play destination
        # is not, and offering the difference would let The Harrowing drop a
        # unit onto contested ground without ever fighting for it. Same
        # restriction `actions.play_destinations` enforces for a card from
        # hand, and for the same reason.
        return ([base_loc(seat)]
                + [bf_loc(i) for i in range(N_BF)
                   if int(state.bf_ctrl[i]) == seat])
    # **Which bases this slot reaches.** A location is a base or a battlefield,
    # and there are two bases. `who` picks them the same way it picks a unit's
    # controller, so "a unit at a base" can reach the far side.
    #
    # The default is W_FRIENDLY rather than W_ANY, and that is a rules answer
    # rather than caution: every location slot written so far is a DESTINATION
    # -- a Move or a token placement -- and no card in the pool sends anything
    # to the opponent's base. Movement is base<->battlefield with a unit going
    # to ITS OWN base (`T_OWNER_BASE`), so offering the enemy base as somewhere
    # to move to would invent a play the game does not have.
    if spec.who == W_ENEMY:
        bases = [base_loc(1 - seat)]
    elif spec.who == W_ANY:
        bases = [base_loc(seat), base_loc(1 - seat)]
    else:
        bases = [base_loc(seat)]
    return bases + [bf_loc(i) for i in range(N_BF)]


def _battlefield_targets(state: GameState, table: CardTable, spec: TargetSpec,
                         seat: int, bound_bf: int,
                         chosen: list[int]) -> list[int]:
    """Battlefields this slot may name, as LOCATIONS.

    A battlefield slot returns the same encoding a TK_LOCATION slot does, so an
    op that moves or damages "there" needs no idea which kind of slot chose it.
    The difference is only in what may be chosen: never a base.

    `who` reads as CONTROL here, because that is what the cards say -- "a
    battlefield you control" (Resonating Strike) against the unqualified "a
    battlefield" (Crescent Strike). An uncontrolled battlefield is neither
    player's, so W_ENEMY excludes it as well as excluding your own.
    """
    if bound_bf >= 0 and spec.locality == LOC_BOUND:
        return [bf_loc(bound_bf)]
    out = []
    for i in range(N_BF):
        ctrl = int(state.bf_ctrl[i])
        if spec.who == W_FRIENDLY and ctrl != seat:
            continue
        if spec.who == W_ENEMY and (ctrl == seat or ctrl < 0):
            continue
        # "a battlefield where you have units" (Moonfall). A restriction on the
        # battlefield, checked when it is chosen -- and re-checked at
        # resolution, where the units may already be gone.
        if spec.needs_own_units and state.units_at(bf_loc(i), seat).size == 0:
            continue
        loc = bf_loc(i)
        if loc not in chosen:
            out.append(loc)
    return out


def legal_targets(state: GameState, table: CardTable, spec: CardSpec, slot: int,
                  seat: int, chosen: list[int], bound_bf: int,
                  source: int = -1, card: int = -1) -> list[int]:
    """Values that may fill `slot`. Their meaning depends on the slot's kind:
    a permanent row, a chain uid (TK_SPELL), or a location (TK_LOCATION)."""
    t = spec.targets[slot]
    if t.kind == TK_BATTLEFIELD:
        return _battlefield_targets(state, table, t, seat, bound_bf, chosen)
    if t.kind == TK_LOCATION:
        return _location_targets(state, t, seat, bound_bf)
    if t.kind == TK_SPELL:
        return _spell_targets(state, table, t, seat, chosen)
    if t.kind == TK_TRASH_CARD:
        return _trash_targets(state, table, t, seat, chosen)
    return [i for i in range(state.n_perms)
            if i not in chosen
            and _matches(state, table, t, i, seat, chosen, bound_bf, source,
                         parent=spec)
            # 809 -- an unaffordable Deflect surcharge makes it not a choice.
            and _affordable_with(state, table, card, seat, chosen,
                                 combat.perm_kw(state, table, i, "Deflect")
                                 if int(state.perms[i, P_CTRL]) != seat else 0,
                                 spec)]


def _can_complete(state: GameState, table: CardTable, spec: CardSpec, slot: int,
                  seat: int, chosen: list[int], bound_bf: int,
                  source: int = -1, card: int = -1) -> bool:
    """Can slots `slot`..end still all be filled, given `chosen` so far?

    Backtracking, not greedy. Greedy is wrong here: Facebreaker's slots are
    coupled, so committing to the *first* friendly unit can leave the enemy slot
    empty while a different friendly unit would have worked. That was a real
    deadlock -- the enumerator offered a slot-0 choice with no slot-1 follow-up,
    and the player was then to act with an empty action list.
    """
    if slot >= spec.n_targets:
        return True
    if spec.targets[slot].optional:
        # 355.14 -- "up to N" may be satisfied with fewer, so an optional slot
        # can always be completed by skipping it. Without this the whole card
        # would be unplayable when the board is too empty to fill it.
        return _can_complete(state, table, spec, slot + 1, seat, chosen + [-1],
                             bound_bf, source, card)
    return any(
        _can_complete(state, table, spec, slot + 1, seat, chosen + [p], bound_bf,
                      source, card)
        for p in legal_targets(state, table, spec, slot, seat, chosen, bound_bf,
                               source, card))


def choosable_targets(state: GameState, table: CardTable, spec: CardSpec,
                      slot: int, seat: int, chosen: list[int],
                      bound_bf: int, source: int = -1,
                      card: int = -1) -> list[int]:
    """Targets for `slot` that do not dead-end the slots after it.

    359.3.e.14.a says a card whose targets cannot all be chosen legally cannot
    be played. That applies *per choice*, not only up front: picking a target
    that makes a later slot unfillable is itself an illegal choice, because it
    would leave a card that can never be finalized.
    """
    return [p for p in legal_targets(state, table, spec, slot, seat, chosen,
                                     bound_bf, source, card)
            if _can_complete(state, table, spec, slot + 1, seat, chosen + [p],
                             bound_bf, source, card)]


def can_be_cast(state: GameState, table: CardTable, spec: CardSpec, seat: int,
                bound_bf: int, source: int = -1, card: int = -1) -> bool:
    """Is there any legal way to fill every slot? (359.3.e.14.a)"""
    return _can_complete(state, table, spec, 0, seat, [], bound_bf, source, card)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _condition_holds(state: GameState, table: CardTable, op: Op,
                     targets: list[int], from_hand: bool, seat: int = -1,
                     source: int = -1, ctx: int = -1,
                     dead_source: int = -1, ctx2: int = -1) -> bool:
    if op.cond == COND_NONE:
        return True
    if op.cond == COND_LEVEL:
        # "[Level N] - while you have N+ XP, get the effect." Continuous and
        # read live: XP never resets, so unlike [Legion] there is no past
        # moment to snapshot, and a level gained mid-chain legitimately turns
        # the effect on.
        return seat >= 0 and int(state.xp[seat]) >= op.level
    if op.cond == COND_LEGION:
        # 822 -- "get the effect if you've played another card this turn",
        # snapshotted onto the source when it was played. Read live, this would
        # be wrong twice over: the source has itself been counted by now, and a
        # "[Legion] - When you play me" trigger sits on the Chain through a
        # priority window in which the count can move again.
        return source >= 0 and bool(
            int(state.perms[source, P_FLAGS]) & F_LEGION)
    if op.cond == COND_PLAYED_TRIO:
        # All three kinds this turn. `played_types` is set as each card is
        # played, so this asks about the turn's history rather than the board.
        return seat >= 0 and int(state.played_types[seat]) & (
            PT_UNIT | PT_GEAR | PT_SPELL) == (PT_UNIT | PT_GEAR | PT_SPELL)
    if op.cond == COND_NOT_DIED_ALONE:
        # Same snapshot as COND_DIED_ALONE, read the other way. `dead_source`,
        # because by now the source is a corpse and `source` has been blanked.
        return dead_source >= 0 and not (
            int(state.perms[dead_source, P_FLAGS]) & F_DIED_ALONE)
    if op.cond == COND_FIRST_TURN:
        # `state.turn` counts ROUNDS, advancing after the second seat's turn,
        # so BOTH players' first Beginning Phase falls on turn 1.
        return int(state.turn) == 1
    if op.cond == COND_CTX_BATTLEFIELD:
        return ctx >= 0 and is_battlefield(ctx)
    if op.cond == COND_CTX2_BATTLEFIELD:
        return ctx2 >= 0 and is_battlefield(ctx2)
    if op.cond == COND_SELF_AT_BF:
        who = source if source >= 0 else dead_source
        return who >= 0 and is_battlefield(int(state.perms[who, P_LOC]))
    if op.cond == COND_READY_ENEMY_HERE:
        who = source if source >= 0 else dead_source
        if who < 0:
            return False
        loc, mine = int(state.perms[who, P_LOC]), int(state.perms[who, P_CTRL])
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) != mine
                   and int(state.perms[i, P_LOC]) == loc
                   and state.perms[i, P_READY] == 1
                   and table.is_type(int(state.perms[i, P_CARD]), "Unit")
                   for i in range(state.n_perms))
    if op.cond == COND_N_OTHERS_HERE:
        who = source if source >= 0 else dead_source
        if who < 0:
            return False
        loc, ctrl = int(state.perms[who, P_LOC]), int(state.perms[who, P_CTRL])
        n = sum(1 for i in range(state.n_perms)
                if i != who and state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) == ctrl
                and int(state.perms[i, P_LOC]) == loc
                and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
        return n == op.level
    if op.cond == COND_OTHERS_MIGHT:
        who = source if source >= 0 else dead_source
        if who < 0 or seat < 0:
            return False
        total = sum(combat.might(state, table, i)
                    for i in range(state.n_perms)
                    if i != who and state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == seat
                    and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
        return total >= op.level
    if op.cond == COND_PAID_ADDITIONAL:
        # "When you play me, IF YOU PAID the additional cost, ...". Recorded on
        # the row as the card was played, because the payment is a moment that
        # has passed by the time this trigger resolves -- the same reading
        # [Legion] needs. `dead_source` too: the unit can be answered in the
        # response window and the clause is still about what was paid.
        who = source if source >= 0 else dead_source
        return who >= 0 and bool(
            int(state.perms[who, P_FLAGS]) & F_PAID_ADDITIONAL)
    if op.cond == COND_WAS_MIGHTY:
        # 740.2 -- Mighty is 5+ Might, and "I WAS Mighty" asks about the moment
        # of death. Reads the flag `combat._destroy` recorded then, for the same
        # reason COND_DIED_ALONE does: the Deathknell resolves a priority window
        # later, over a row whose buffs may already have been cleared.
        return dead_source >= 0 and bool(
            int(state.perms[dead_source, P_FLAGS]) & F_DIED_MIGHTY)
    if op.cond == COND_FEWER_RUNES_THAN_OPP:
        # "If you control FEWER runes than an opponent" -- both boards counted
        # the way COND_FEW_RUNES counts one: ready plus spent, because an
        # exhausted rune is still controlled.
        if seat < 0:
            return False
        mine = int(state.runes_ready[seat].sum() + state.runes_spent[seat].sum())
        other = 1 - seat
        theirs = int(state.runes_ready[other].sum()
                     + state.runes_spent[other].sum())
        return mine < theirs
    if op.cond == COND_FEW_RUNES:
        # "If you control N or fewer runes." Runes on the BOARD -- ready plus
        # spent -- because an exhausted rune is still controlled; the ones left
        # in the rune deck are not.
        return seat >= 0 and int(state.runes_ready[seat].sum()
                                 + state.runes_spent[seat].sum()) <= op.level
    if op.cond == COND_EMPOWERED:
        # 828.1.d -- an [Empowered] dependent ability that is a TRIGGER is
        # active while its source holds the status. Read on the source, and
        # `dead_source` matters: Noxian Emissary's payload is a [Deathknell],
        # so by resolution the source is already a corpse and `source` alone
        # would be -1. The status it held when it died is what the card asks
        # about (359.3.f.3), and the flag is still on the dead row.
        who = source if source >= 0 else dead_source
        return who >= 0 and bool(int(state.perms[who, P_FLAGS]) & F_EMPOWERED)
    if op.cond == COND_DIED_ALONE:
        # Lonely Poro: "If I died alone", where its own reminder defines alone
        # as "no other friendly units here". Past tense, and that decides the
        # implementation: read the flag `combat._destroy` recorded at the
        # moment of death rather than counting the board now. A Deathknell sits
        # on the Chain through a full priority window (808.1.d.2), so "now" is
        # a board a response has had every chance to change.
        #
        # Reads `dead_source`, not `source`: `resolve` blanks a source that is
        # no longer on the board (383.2.c.2), and a Deathknell's source is
        # always exactly that.
        return dead_source >= 0 and bool(
            int(state.perms[dead_source, P_FLAGS]) & F_DIED_ALONE)
    if op.cond == COND_FROM_HAND:
        return from_hand
    if op.cond == COND_ONLY_UNIT_THERE:
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        if a < 0:
            return False
        loc, ctrl = int(state.perms[a, P_LOC]), int(state.perms[a, P_CTRL])
        return state.units_at(loc, ctrl).size == 1
    if op.cond == COND_CONTROL_N_GEAR:
        # "if you control N or more OTHER gear" -- the source itself does not
        # count, which is what `floor` carries here as the threshold.
        n = sum(1 for i in range(state.n_perms)
                if state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) == seat
                and i != source
                and table.is_type(int(state.perms[i, P_CARD]), "Gear"))
        return n >= int(op.floor or 0)
    if op.cond == COND_ANY_TARGET_TEMPORARY:
        return any(combat.perm_kw(state, table, t, "Temporary")
                   for t in targets if t >= 0)
    raise ValueError(f"unknown condition {op.cond}")


def _sweep(state: GameState, table: CardTable, op: Op, seat: int,
           still_legal: list[int], source: int, ctx: int,
           subj: int = -1, ctx2: int = -1) -> list[int]:
    """Live unit rows a board-wide op reaches, after its scoping clauses.

    The mass effects in the pool are rarely as broad as "all units": they say
    "enemy units", or "units there", or "each OTHER enemy unit there". None of
    those are targets under 355.10 -- there is no count and no choice, so the
    opponent cannot respond by making one of them illegal -- but they are still
    restrictions, and applying them here keeps the sweep in one place instead
    of one `continue` chain per op.

    **An unscoped op reaches the whole board, bases included.** "Give enemy
    units -3 Might" has no location clause and means all of them; the mass
    DAMAGE cards happen to print "at battlefields", which is `at_battlefields`
    and belongs to the card rather than to the op. Defaulting to battlefields
    would have quietly spared every unit sitting at a base.
    """
    where = (_slot(state, still_legal, op.at, source, ctx,
                   seat, subj, ctx2)
             if op.at != -1 else -1)
    spare = (_slot(state, still_legal, op.except_target, source, ctx,
                   seat, subj, ctx2)
             if op.except_target != -1 else -1)
    # A sweep that NAMES a location and cannot find one reaches nothing. The
    # location goes missing in two ordinary ways -- the source of an `at=T_HERE`
    # ability died in the response window (383.2.c.2), and `T_COMBAT` is asked
    # outside a Showdown -- and in both the card's own words scope it to a place
    # that is not there. Falling through to the unscoped branch instead turned
    # "deal 4 to all enemy units HERE" into a board wipe, which is the one
    # answer that is never right.
    if op.at != -1 and where < 0:
        return []
    out = []
    for i in range(state.n_perms):
        r = state.perms[i]
        if r[P_ALIVE] != 1 or i == spare:
            continue
        if not table.is_type(int(r[P_CARD]), "Unit"):
            continue
        if op.tag and op.tag not in table.tags[int(r[P_CARD])]:
            continue
        loc = int(r[P_LOC])
        if where >= 0:
            if loc != where:
                continue
        elif op.at_battlefields and not is_battlefield(loc):
            continue
        ctrl = int(r[P_CTRL])
        if op.who == W_FRIENDLY and ctrl != seat:
            continue
        if op.who == W_ENEMY and ctrl == seat:
            continue
        out.append(i)
    return out


def _slot(state: GameState, still_legal: list[int], idx: int, source: int,
          ctx: int, seat: int = -1, subj: int = -1, ctx2: int = -1) -> int:
    """Decode an op's target index, including the pseudo-slots.

    A spell's ops address chosen targets by slot. A unit ability also has to
    say "me", "here" and "there" -- none of which are choices, so none of which
    can be slots. Decoding them in one place means every op that takes a target
    understands them without knowing they exist.
    """
    if idx == T_SELF:
        # A battlefield IS the source but has no permanent row, so "me" is not
        # a thing an op can point at. -1 rather than the sentinel: every op
        # downstream treats -1 as "no target" and fizzles, which is the right
        # answer, where the sentinel would be read as a row index.
        return -1 if (is_bf_src(source) or is_legend_src(source)) else source
    if idx == T_HERE:
        return source_loc(state, source)
    if idx == T_CTX:
        return ctx
    if idx == T_CTX2:
        return ctx2
    if idx == T_MY_BASE:
        return base_loc(seat) if seat >= 0 else -1
    if idx == T_SUBJECT:
        return subj
    if idx == T_COMBAT:
        # 459 -- the contested battlefield. `showdown_bf` is the battlefield
        # INDEX, not a location, and the two are different numbers; conflating
        # them would point "in combat" at a base.
        bf = int(state.showdown_bf)
        return bf_loc(bf) if bf >= 0 else LOC_NONE

    return still_legal[idx] if 0 <= idx < len(still_legal) else -1


def resolve(state: GameState, table: CardTable, cfg: Config, spec: CardSpec,
            seat: int, targets: list[int], bound_bf: int,
            from_hand: bool, source: int = -1, ctx: int = -1,
            subj: int = -1, ctx2: int = -1) -> dict:
    """Apply a finalized card's or ability's ops. Returns a log dict.

    Targets are re-checked here, not trusted from finalization: the window
    between the two is exactly where a response lands (359.3.e).

    `source` and `ctx` are the two things a triggered ability knows and a spell
    does not: the permanent it is printed on, and the location captured when it
    triggered (359.3.f.3). Both are -1 for a card.

    `ctx2` is the second captured location a Move produces. `ctx` is where the
    unit came FROM and `ctx2` where it went TO, and printed text picks between
    them by word -- see `state.C_CTX2`. Neither is a live read, so both outlive
    the source; `T_HERE` is the live one and is meant to fizzle.
    """
    log: dict = {"resolved": [], "fizzled": []}

    # 383.2.c.2 -- an ability whose source left the board cannot reference it.
    # Sprite Mother's "here" has no meaning once she is dead, and dereferencing
    # a dead row would silently place the token at her last location.
    #
    # `dead_source` keeps the row anyway, for the one thing a dead source is
    # still the authority on: what was recorded ABOUT its death. A Deathknell's
    # source is dead by definition, so blanking it outright would make
    # "if I died alone" unanswerable on the only card that asks.
    dead_source = source
    if source >= 0 and state.perms[source, P_ALIVE] != 1:
        source = -1

    still_legal: list[int] = []
    chosen_so_far: list[int] = []
    for slot, t in enumerate(targets):
        if spec.targets[slot].kind == TK_BATTLEFIELD:
            # Re-checked, unlike a plain location: "a battlefield you control"
            # and "where you have units" are both things a response window can
            # take away.
            ok = t >= 0 and t in _battlefield_targets(
                state, table, spec.targets[slot], seat, bound_bf, [])
        elif spec.targets[slot].kind == TK_LOCATION:
            ok = t >= 0
        elif spec.targets[slot].kind == TK_SPELL:
            # Still legal iff the item is still on the chain. If someone else
            # countered it first, this one fizzles (359.3.e).
            ok = t >= 0 and chain.index_of_uid(state, t) >= 0
        elif spec.targets[slot].kind == TK_TRASH_CARD:
            # Still legal iff a copy is still there -- and iff no EARLIER slot
            # of this same card has already spoken for the last one. Two slots
            # naming the same card were legal at finalization because two copies
            # existed; if one has since been played out of the trash with
            # [Flow], only the first slot may still have it. Counted in the
            # OWNER's pile, which the packed value names -- the same card in the
            # other player's trash is a different choice and does not stand in.
            need = chosen_so_far.count(t) + 1
            if t < 0:
                ok = False
            else:
                owner, card_t = unpack_trash(t)
                ok = int(np.count_nonzero(
                    state.trash[owner, :int(state.n_trash[owner])]
                    == card_t)) >= need
        else:
            ok = (t >= 0 and _matches(state, table, spec.targets[slot], t, seat,
                                      chosen_so_far, bound_bf, source,
                                      parent=spec))
        still_legal.append(t if ok else -1)
        chosen_so_far.append(t if ok else -1)

    # 359.3.e.5/e.6 -- if every target is gone, the whole thing is countered.
    if spec.n_targets and all(t < 0 for t in still_legal):
        log["countered"] = True
        return log

    for op in spec.ops:
        if not _condition_holds(state, table, op, still_legal, from_hand,
                                seat, source, ctx, dead_source, ctx2):
            log["fizzled"].append(op.op)
            continue

        if op.op == OP_DRAW:
            n = op.n
            if op.n_from_count == CT_MY_BATTLEFIELDS:
                n = op.n * sum(1 for i in range(N_BF)
                               if int(state.bf_ctrl[i]) == seat)
            elif op.n_from_count == CT_MY_OTHER_BATTLEFIELDS:
                # "Other" than the source's own. `source` is a battlefield here
                # (Seat of Power), so exclude its slot directly.
                mine = bf_src_index(source) if is_bf_src(source) else -1
                n = op.n * sum(1 for i in range(N_BF)
                               if i != mine and int(state.bf_ctrl[i]) == seat)
            elif op.n_from_count == CT_MY_MIGHTY_UNITS:
                # 5+ Might is Mighty, read as EFFECTIVE Might so statics and
                # buffs count -- the number on the board, not the corner.
                n = op.n * sum(1 for i in range(state.n_perms)
                               if state.perms[i, P_ALIVE] == 1
                               and int(state.perms[i, P_CTRL]) == seat
                               and table.is_type(int(state.perms[i, P_CARD]), "Unit")
                               and combat.might(state, table, i) >= 5)
            log["drew"] = phases.draw_for(state, seat, n) if n else []
            log["resolved"].append(op.op)
            continue

        a = _slot(state, still_legal, op.target, source, ctx,
                  seat, subj, ctx2)
        if op.target != -1 and a < 0:
            log["fizzled"].append(op.op)      # this target specifically is gone
            continue

        # "+Might equal to its Might" -- read off another slot at RESOLUTION,
        # so it counts buffs and statics rather than the printed number, and it
        # must be read before any op in this same card kills that unit.
        amount = op.n
        if op.n_from_count == CT_ENEMIES_AT_TARGET and a >= 0:
            # "+2 Might FOR EACH enemy unit there" -- `n` is the rate, and
            # "there" is the chosen unit's location, not the source's.
            loc = int(state.perms[a, P_LOC])
            amount = op.n * sum(
                1 for i in range(state.n_perms)
                if state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) != seat
                and int(state.perms[i, P_LOC]) == loc
                and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
        if op.n_from_might >= 0:
            ref = _slot(state, still_legal, op.n_from_might, source, ctx, seat,
                        subj)
            amount = (combat.might(state, table, ref)
                      if ref >= 0 and state.perms[ref, P_ALIVE] == 1 else 0)
        if op.op == OP_CREATE_TOKEN:
            # 811.1.d.3 -- a hidden spell that plays a unit must play it at
            # that battlefield. That is enforced by the slot's LOC_BOUND
            # locality, so the player chooses freely from hand and is pinned
            # from hiding, with no special case here.
            card = table.id_of(op.token)
            loc = a if a >= 0 else base_loc(seat)
            made = [state.add_permanent(card, seat, loc, ready=op.ready,
                                        is_unit=bool(table.is_type(card, "Unit")))
                    for _ in range(op.n)]
            log["tokens"] = made
            # 187 -- a token is PLAYED, so "when you play a token unit" sees it.
            # Missing this would have made Lillia blind to the token deck she
            # exists to reward.
            if table.is_type(card, "Unit"):
                for _row in made:
                    chain.fire_play_unit(state, table, seat, card, _row)
            # Zilean - Time Mage: "Once each turn, if you would play a TOKEN
            # UNIT while I'm AT A BATTLEFIELD, you may play that token and an
            # additional copy of it instead." Offered rather than applied --
            # the extra body can break an "alone" clause (740.2.a), so it is a
            # real choice and not a strictly better one.
            #
            # The offer is deferred to after this resolution finishes, which
            # costs no ordering: every token-creating op in the pool is its
            # card's last, asserted at import in `effects.py`.
            if table.is_type(card, "Unit") and state.pend_double[0] < 0:
                for z in range(state.n_perms):
                    zr = state.perms[z]
                    if (zr[P_ALIVE] == 1 and int(zr[P_CTRL]) == seat
                            and is_battlefield(int(zr[P_LOC]))
                            and table.names[int(zr[P_CARD])] in TOKEN_DOUBLERS
                            and int(state.once_used[z]) != int(state.turn)):
                        state.pend_double[:] = (z, card, loc)
                        break
            # No cleanup here: 321 forbids one while Chain Items are resolving.
            # Arriving units stage a Combat by presence (461); it is initiated
            # by the cleanup the action layer runs once the Chain empties.
        elif op.op == OP_DAMAGE:
            # 143.2.a -- marking damage kills as soon as it is non-zero and at
            # least the unit's current Might. Same continuous check as a Might
            # reduction; combat.mark_damage owns it so there is one code path.
            if combat.mark_damage(state, table, a, op.n):
                log.setdefault("killed", []).append(a)
        elif op.op == OP_KILL:
            combat.destroy(state, table, a)
            log.setdefault("killed", []).append(a)
        elif op.op == OP_DRAW_CONTROLLER:
            # The TARGET's controller draws, not the caster.
            owner = int(state.perms[a, P_CTRL])
            log["drew_opponent"] = phases.draw_for(state, owner, op.n)
        elif op.op == OP_MOVE_TO:
            if op.loc_of_target >= 0:
                # "that enemy unit's battlefield" -- the LOCATION of a unit
                # chosen in another slot. Reading the slot as a destination
                # directly would use its permanent ROW as a location id.
                ref = _slot(state, still_legal, op.loc_of_target, source, ctx,
                            seat, subj, ctx2)
                dst = int(state.perms[ref, P_LOC]) if ref >= 0 else -1
            elif op.target_b == T_OWNER_BASE:
                # "to its base" -- the base of whoever controls THIS op's own
                # target, so an enemy unit goes home rather than to ours, and
                # a card moving two units sends each to the right place.
                dst = base_loc(int(state.perms[a, P_CTRL])) if a >= 0 else -1
            else:
                dst = _slot(state, still_legal, op.target_b, source, ctx,
                            seat, subj, ctx2)
            if dst < 0:
                log["fizzled"].append(op.op)
                continue
            combat.queue_move_trigger(state, table, a,
                                      int(state.perms[a, P_LOC]), dst)
            state.perms[a, P_LOC] = dst
            if op.then_ready:
                woke = int(state.perms[a, P_READY]) == 0
                state.perms[a, P_READY] = 1
                if woke:
                    from rl.engine.effects import TR_READIED
                    chain.fire_watchers(state, table,
                                        int(state.perms[a, P_CTRL]),
                                        TR_READIED, subj=a)
            log["moved"] = (a, dst)
            # Staged, not initiated -- see the note in OP_CREATE_TOKEN.
        elif op.op == OP_RETURN_TO_HAND:
            owner = int(state.perms[a, P_CTRL])
            card = int(state.perms[a, P_CARD])
            state.perms[a, P_ALIVE] = 0
            # 185.3 -- a token that leaves the board ceases to exist; it does
            # not go to a hand. Only real cards bounce.
            if not table.is_token(card):
                h = int(state.n_hand[owner])
                assert h < state.hand.shape[1], "hand overflow"
                state.hand[owner, h] = card
                state.n_hand[owner] = h + 1
            log.setdefault("returned", []).append(a)
        elif op.op == OP_TRASH_TO_HAND:
            # `a` is a packed (owner, card), not a permanent row -- see the
            # TK_TRASH_CARD note in effects.py.
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            # To the OWNER's hand, not the caster's. Shadows of the Past says
            # "to their owners' hands" and means it: raising an opponent's unit
            # hands it back to them, which is why the card is a symmetric
            # rebuild and not a theft.
            h = int(state.n_hand[owner])
            assert h < state.hand.shape[1], "hand overflow"
            state.hand[owner, h] = card
            state.n_hand[owner] = h + 1
            log.setdefault("from_trash", []).append(table.names[card])
        elif op.op == OP_RECYCLE_FROM_TRASH:
            # 416.1.c -- "each player recycles to their own Main Deck",
            # regardless of who was instructed to perform the Recycle. So this
            # reads the owner off the packed target rather than using `seat`;
            # Forge of the Future recycling an opponent's card puts it on the
            # bottom of THEIR deck, which is a mill answer rather than a steal.
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            state.recycle_card(owner, card)
            log.setdefault("recycled", []).append(table.names[card])
        elif op.op == OP_PLAY_FROM_TRASH:
            # 349 -- this PLAYS the card. It is not moved to the board and it is
            # not resolved here: it goes on the Chain as a new Pending Item and
            # takes its own priority windows, which is why the opponent can
            # counter what Fizz digs up. `actions._advance_pending` picks it up
            # after this resolution finishes (340.3).
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            assert owner == seat, "playing from another player's trash"
            # Re-checked HERE, not just at finalization -- a priority window
            # stood between the two and the board has moved. See
            # `can_play_from_trash`.
            if not can_play_from_trash(state, table, seat, card, op.cost):
                log["fizzled"].append(op.op)
                continue
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            chain.push(state, card, seat, from_hand=False, bound_bf=-1,
                       cost=op.cost, dest=op.dest)
            log.setdefault("played_from_trash", []).append(table.names[card])
        elif op.op == OP_PLAY_UNIT_FROM_TRASH:
            # A unit, not a spell, so 337.2 resolves it IMMEDIATELY -- no chain
            # item, nothing to respond to, and therefore no destination to
            # record. It goes on the board instead, which is why this needs a
            # location where `OP_PLAY_FROM_TRASH` needs a `dest`.
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            assert owner == seat, "playing from another player's trash"
            if not can_play_from_trash(state, table, seat, card, op.cost):
                log["fizzled"].append(op.op)
                continue
            dst = _slot(state, still_legal, op.target_b, source, ctx,
                        seat, subj, ctx2)
            # The destination was chosen at finalization and a response window
            # has passed since. If that Battlefield is no longer this seat's,
            # 806.3 no longer permits it -- but the base always does, and the
            # play itself is not optional, so it lands there rather than
            # fizzling a card the player already committed to.
            if dst < 0 or (is_battlefield(dst)
                           and int(state.bf_ctrl[bf_index(dst)]) != seat):
                dst = base_loc(seat)
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            _pay_trash_play(state, table, seat, card, op.cost)
            # 359.2.c -- it enters exhausted, exactly as if played from hand.
            src2 = state.add_permanent(card, seat, dst, ready=False,
                                       is_unit=True)
            if chain.has_trigger(table, card, TR_PLAY_ME):
                chain.queue(state, TR_PLAY_ME, src2, dst)
            log.setdefault("played_from_trash", []).append(table.names[card])
        elif op.op == OP_GRANT_KEYWORD:
            # 143.2.a again: granting [Shield 3] can only ever help, but
            # granting [Temporary] schedules a death and granting nothing at
            # all is still a legal resolution. The Might-relevant keywords go
            # through `combat.might` on the next read, so no re-check is owed
            # here -- Assault and Shield only apply during a Combat, and
            # `combat_role_bonus` is derived rather than stored.
            idx = GRANT_IDX.get(op.keyword)
            assert idx is not None, f"{op.keyword!r} is not grantable"
            arr = state.kw_grant_turn if op.grant_this_turn else state.kw_grant
            arr[a, idx] += max(1, amount)
            log.setdefault("granted", []).append((a, op.keyword))
        elif op.op == OP_GAIN_XP:
            # A player resource, not a permanent's. It has no cap and does not
            # reset, which is what makes [Level 11] reachable.
            state.xp[seat] += op.n
            log["xp"] = int(state.xp[seat])
        elif op.op == OP_COUNTER:
            # Record the controller BEFORE removing the item -- Lilting
            # Lullaby's second op ("its controller can't play spells this
            # turn") runs after the item is already off the chain.
            i = chain.index_of_uid(state, a)
            if i >= 0:
                log["countered_ctrl"] = int(state.chain[i, C_CTRL])
            name = chain.counter(state, table, a)
            if name is None:
                log["fizzled"].append(op.op)   # already countered by someone else
                continue
            log["countered_spell"] = name
        elif op.op == OP_NO_SPELLS:
            i = chain.index_of_uid(state, a)
            if i >= 0:
                state.no_spells[int(state.chain[i, C_CTRL])] = 1
            else:
                # The item was countered by this same card a moment ago, so its
                # controller is read from the log rather than the chain.
                ctrl = log.get("countered_ctrl")
                if ctrl is not None:
                    state.no_spells[ctrl] = 1
        elif op.op == OP_MODIFY_MIGHT:
            # May kill, but only by meeting damage already marked (143.2.a).
            # Never by reduction alone -- lethal damage must be non-zero.
            if combat.set_might_mod(state, table, a, amount, op.floor):
                log.setdefault("killed_by_might", []).append(a)
        elif op.op == OP_STUN:
            # `stun` returns False on a redundant stun (423.1.a.1), which
            # "when you stun an enemy unit" triggers must not fire on.
            log["stunned"] = log.get("stunned", [])
            if state.stun(a):
                log["stunned"].append(a)
        elif op.op == OP_BLINK:
            # 427 -- Banish, then the OWNER plays it again. Not a kill
            # (427.2.a), so nothing is trashed and no [Deathknell] fires.
            row = state.perms[a]
            bcard, bctrl = int(row[P_CARD]), int(row[P_CTRL])
            dst = base_loc(bctrl) if op.to_base else int(row[P_LOC])
            combat.banish(state, table, a)
            if table.is_token(bcard):
                # 186 -- a token in any non-board zone ceases to exist, so it
                # never comes back. Banishing a token is straight removal.
                log.setdefault("banished", []).append(a)
                log["resolved"].append(op.op)
                continue
            new = state.add_permanent(
                bcard, bctrl, dst, ready=False,
                is_unit=bool(table.is_type(bcard, "Unit")))
            # It returns as a NEW object: no damage, no Buff (705), no "this
            # turn" modifiers, and it was *played*, so its own entry triggers
            # fire for its owner.
            if chain.has_trigger(table, bcard, TR_PLAY_ME):
                chain.queue(state, TR_PLAY_ME, new, dst)
            log["blinked"] = (a, new)
        elif op.op == OP_BUFF:
            # 426.1.b.1 -- a unit that already has a Buff does not get another,
            # and 426.1.c is explicit that it can still be CHOSEN for the
            # effect. So this is not a targeting restriction; it simply does
            # nothing on an already-buffed unit.
            if not (state.perms[a, P_FLAGS] & F_BUFFED):
                state.perms[a, P_FLAGS] |= F_BUFFED
                log.setdefault("buffed", []).append(a)
        elif op.op == OP_BUFF_ALL_AT:
            for i in state.units_at(a):
                if not (state.perms[i, P_FLAGS] & F_BUFFED):
                    state.perms[i, P_FLAGS] |= F_BUFFED
                    log.setdefault("buffed", []).append(int(i))
        elif op.op == OP_ADD_ENERGY:
            state.pool_energy[seat] += op.n
        elif op.op == OP_ADD_POWER:
            state.pool_power[seat, op.domain] += op.n
        elif op.op == OP_RECYCLE_SELF:
            # "Recycle me." A Deathknell resolves with its card already in the
            # trash (808.1.d.2 puts the ability on the Chain before the card
            # moves), so this lifts it back out of the pile rather than off the
            # board. 416.1.c -- to its OWNER's deck, which for a Deathknell is
            # the seat whose trash it is sitting in.
            # `dead_source`, not `source`: 383.2.c.2 blanks a source that has
            # left the board, and a Deathknell's source is dead by definition.
            # "Recycle ME" is one of the few things a corpse is still the
            # authority on -- it names a card, not a board position -- so this
            # reads the row that was kept for exactly that purpose.
            who = source if source >= 0 else dead_source
            if who >= 0:
                card = int(state.perms[who, P_CARD])
                n = int(state.n_trash[seat])
                for k in range(n - 1, -1, -1):        # newest first: it is
                    if int(state.trash[seat, k]) == card:   # the one just added
                        state.trash[seat, k:n - 1] = state.trash[seat, k + 1:n]
                        state.trash[seat, n - 1] = -1
                        state.n_trash[seat] = n - 1
                        if not table.is_token(card):
                            state.recycle_card(seat, card)
                        log["recycled_self"] = table.names[card]
                        break
        elif op.op == OP_DISCARD_CHOOSE:
            # Suspend for the player to pick WHICH card. The branch its type
            # selects is applied by `actions._finish_discard`.
            #
            # **Anything that must happen AFTER the discard goes in `then_key`,
            # not in a following op.** Resolution does not stop here -- it sets
            # the pending decision and carries on down the op list -- so Zaun
            # Warrens' "discard 1, THEN draw 1" written as two ops drew first
            # and made the fresh card discardable, which is the opposite of
            # what it says. The follow-up runs from `_finish_discard`, once the
            # card is actually gone.
            if int(state.n_hand[seat]) > 0:
                state.pend_discard = seat
                state.pend_discard_ops = op.branch_key
                state.pend_discard_src = source
                if op.then_key >= 0:
                    state.pend_then[:] = (op.then_key, source)
                log["discard_choice"] = seat
            else:
                # An empty hand discards nothing -- but "then draw 1" is
                # sequencing, not a condition, so the follow-up still runs.
                # Inline rather than deferred: there is no decision to wait for.
                log["discard_choice"] = -1
                if op.then_key >= 0 and FOLLOWUPS[op.then_key]:
                    _sub = resolve(state, table, cfg,
                                   CardSpec(speed=SPEED_MAIN,
                                            ops=FOLLOWUPS[op.then_key]),
                                   seat, [], -1, True, source=source)
                    log["resolved"].extend(_sub["resolved"])
        elif op.op == OP_READY_LEGEND:
            # "Ready your legend" (Hall of Legends). A legend is a Game Object
            # that exhausts to pay for its own ability, so readying it buys a
            # second use in one turn -- and the cards that say it are all
            # optional and all cost something, which is the tell that a second
            # activation is meant to be worth paying for.
            #
            # A no-op on a legend that is already ready, and on a seat with no
            # legend at all (a random-pool deal has none). Neither is an error:
            # 415 readies what is able to be readied and says nothing about the
            # rest.
            log["readied_legend"] = bool(state.legend[seat] >= 0
                                         and not state.legend_ready[seat])
            if state.legend[seat] >= 0:
                state.legend_ready[seat] = 1
        elif op.op == OP_READY_RUNES and op.at_end_of_turn:
            # "Ready 2 runes AT THE END OF THIS TURN" (Targon's Peak). Banked
            # rather than performed: `phases.ending` pays it out. The promise
            # is what the card is worth -- it is made the moment the
            # battlefield is conquered, so the runes spent taking it come back
            # before the opponent's turn rather than after.
            state.pending_ready_runes[seat] += op.n
            log["ready_runes_pending"] = op.n
        elif op.op == OP_READY_RUNES:
            # "Ready up to N runes." A rune readies by moving from spent back
            # to ready -- the same direction the Awaken Phase moves them, just
            # bounded. "Up to" and there is nothing to choose between: runes of
            # a domain are interchangeable (which is why they are counts and
            # not objects), so readying the most-held domain first is not a
            # choice being taken away from anyone.
            left = op.n
            for dom in np.argsort(-state.runes_spent[seat]):
                if left <= 0:
                    break
                take = min(left, int(state.runes_spent[seat, dom]))
                state.runes_spent[seat, dom] -= take
                state.runes_ready[seat, dom] += take
                left -= take
            log["readied_runes"] = op.n - left
        elif op.op == OP_SWAP_MIGHT:
            b = _slot(state, still_legal, op.target_b, source, ctx,
                      seat, subj, ctx2)
            if b < 0 or a == b or state.perms[b, P_ALIVE] != 1:
                log["fizzled"].append(op.op)
                continue
            # Swap the EFFECTIVE Mights, which is what the card says -- statics
            # and buffs included, not the printed corners. Expressed through
            # the turn-scoped modifier, so it expires with the turn and
            # `set_might_mod` re-checks lethality for both (143.2.a): swapping
            # a big unit's Might onto a damaged small one can kill it at once.
            ma = combat.might(state, table, a)
            mb = combat.might(state, table, b)
            if ma != mb:
                combat.set_might_mod(state, table, a,
                                     int(state.perms[a, P_MIGHT_MOD]) + mb - ma)
                combat.set_might_mod(state, table, b,
                                     int(state.perms[b, P_MIGHT_MOD]) + ma - mb)
            log["swapped_might"] = (a, b)
        elif op.op == OP_ANY_DAMAGE_KILLS:
            state.any_damage_kills = 1
            log["any_damage_kills"] = True
        elif op.op == OP_NO_MOVE:
            # "They can't move it this turn." Turn-scoped, cleared by the same
            # end-of-turn sweep as [Stun].
            if a >= 0 and state.perms[a, P_ALIVE] == 1:
                state.set_flag(a, F_NO_MOVE)
                log["no_move"] = a
        elif op.op == OP_EACH_KILLS_OWN:
            # Open the sequential choice; the action layer walks the seats.
            # Starting with the resolving player, which is the turn order the
            # rules default to for "each player".
            # Skip straight past any seat with no unit to kill -- "each
            # player kills one of their units" asks nothing of a player who
            # has none, and an empty decision point would deadlock the turn.
            nxt = seat
            while nxt < N_SEATS and not any(
                    state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == nxt
                    and table.is_type(int(state.perms[i, P_CARD]), "Unit")
                    for i in range(state.n_perms)):
                nxt += 1
            state.pend_cull = nxt if nxt < N_SEATS else -1
            log["cull"] = int(state.pend_cull)
        elif op.op == OP_SCORE:
            # "You score N points." Straight onto the score; the winner check
            # is a Cleanup concern (194.2) and happens on its own.
            state.points[seat] += op.n
            log["scored_points"] = op.n
            from rl.engine.effects import TR_OPPONENT_SCORES
            chain.fire_watchers(state, table, 1 - seat, TR_OPPONENT_SCORES)
        elif op.op == OP_REVEAL_HAND:
            # The opponent reveals; the caster then chooses. Nothing is copied
            # out of the hand -- `pend_reveal` names the two seats and the
            # action layer reads the candidates live, so a card that leaves the
            # hand in between simply is not offered.
            foe = 1 - seat
            state.pend_reveal[:] = (seat, foe)
            state.look_pick_dest = op.pick_dest
            state.look_type_mask = 0
            for _t in op.pick_types:
                state.look_type_mask |= LOOK_TYPE_BIT[_t]
            log["revealed"] = int(state.n_hand[foe])
        elif op.op == OP_SEE_HAND:
            # "They reveal their hand." A standing permission rather than a
            # choice, so unlike OP_REVEAL_HAND nothing is picked and nothing
            # moves -- the only effect is on what the observation shows.
            #
            # **This is an approximation, and a deliberate one.** A reveal is
            # instantaneous in the rules; the information then lives in the
            # opponent's MEMORY, which the engine has no concept of. Modelled
            # as visibility for the rest of the turn: less than perfect recall
            # (a human remembers past this turn) and slightly more within it
            # (a card drawn after the reveal is also seen). The alternative --
            # snapshotting the revealed ids -- models a memory nothing else in
            # the engine has, and would still have to pick a duration.
            state.saw_hand[seat] = int(state.turn)
            log["saw_hand"] = 1 - seat
        elif op.op == OP_SEE_FACEDOWN:
            # "You can look at their facedown cards this turn" -- explicitly
            # turn-scoped on the card itself, so no approximation here.
            state.saw_fd[seat] = int(state.turn)
            log["saw_facedown"] = 1 - seat
        elif op.op == OP_DEATH_GUARD:
            # Register the delayed replacement on its controller. One at a
            # time: a second Zhonya's simply overwrites, which is right because
            # each says "the NEXT time" and only one death can be the next one.
            if source >= 0:
                state.death_guard[seat] = source
                log["death_guard"] = source
        elif op.op == OP_CHANNEL:
            # 430.1 -- take runes off the top of the Rune Deck onto the board.
            # 430.4.b is the permission these cards use; the two-per-turn of
            # 430.4.a is `phases.channel` and is a different thing.
            got = []
            for _ in range(op.n):
                dom = state.channel_one(seat, ready=op.ready_runes)
                if dom < 0:
                    break                      # an empty Rune Deck, not a loss
                got.append(dom)
            log["channelled"] = got
            if op.draw_if_short and len(got) < op.n:
                # "If you couldn't channel N this way, draw 1" -- the
                # consolation is for coming up SHORT, so it pays out on a
                # partial channel as well as on none at all.
                log["drew"] = phases.draw_for(state, seat, op.draw_if_short)
        elif op.op == OP_EMPOWER:
            # 827.1.b -- Empower "Empowers the source of the ability", and
            # 827.1.b.1 is explicit that the source is NOT a target. So this
            # never reads a slot: it always acts on the permanent the ability
            # is printed on. 441.1.b/c make re-empowering a no-op, which
            # setting a flag already is.
            if source >= 0 and state.perms[source, P_ALIVE] == 1:
                state.set_flag(source, F_EMPOWERED)
                log["empowered"] = source
        elif op.op == OP_DISCARD:
            log["discarded"] = phases.discard(state, table, seat, op.n)
        elif op.op == OP_LOOK_TOP:
            # "Look at the top N cards of your Main Deck." The cards come off
            # the deck NOW and the player picks among them afterwards, through
            # `pend_look` in the action layer -- the same suspend-and-ask shape
            # as the mulligan, because the choice is made during resolution and
            # so cannot go through the target machinery (355.10).
            #
            # Between the two the cards are in NO zone. That is faithful (they
            # are being looked at, not held) but it means `cards_owned` has to
            # count the buffer, and it means this op must be the LAST one on
            # its card -- an op after it would run before the player had
            # chosen. `effects.py` asserts that at import.
            ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
            take = min(op.n, end - ptr)
            state.n_look = take
            state.look_cards[:] = -1
            for k in range(take):
                state.look_cards[k] = state.deck[seat, ptr + k]
            state.deck_ptr[seat] = ptr + take
            state.look_pick_dest = op.pick_dest
            state.look_rest_dest = op.rest_dest
            state.look_optional = int(op.pick_optional)
            state.look_type_mask = 0
            for _t in op.pick_types:
                state.look_type_mask |= LOOK_TYPE_BIT[_t]
            # An empty deck makes this a no-op rather than a stuck decision.
            state.pend_look = seat if take else -1
            if take:
                state.pend_then[:] = (op.then_key, source)
            log["looked"] = take
        elif op.op == OP_KILL_ALL:
            # "Kill all gear" is the same sweep as "kill all units" with one
            # word changed, so the TYPE is a field rather than a second op.
            # Defaults to Unit, which is what every existing entry meant.
            want = op.card_type or "Unit"
            for i in range(state.n_perms):
                r = state.perms[i]
                if r[P_ALIVE] == 1 and table.is_type(int(r[P_CARD]), want):
                    combat.destroy(state, table, i)
                    log.setdefault("killed", []).append(i)
        elif op.op == OP_EXHAUST_ALL:
            for i in range(state.n_perms):
                r = state.perms[i]
                if (r[P_ALIVE] == 1 and int(r[P_CTRL]) == seat
                        and table.is_type(int(r[P_CARD]), "Unit")):
                    r[P_READY] = 0
        elif op.op == OP_HEAL_AT:
            # "heal your units here" -- removes marked damage (no rule allows
            # healing to kill, so no 143.2.a re-check is needed).
            for i in state.units_at(a, seat):
                state.perms[i, P_DMG] = 0
            log["healed_at"] = a
        elif op.op == OP_DAMAGE_ALL:
            # "Deal N to all units at battlefields" -- untargeted (355.10) and,
            # unscoped, indiscriminate: it hits the caster's units too.
            # `_sweep` narrows it to one location, one side, or everything but
            # an already-chosen unit, which is what Crescent Strike's "1 to
            # each OTHER enemy unit there" needs.
            for i in _sweep(state, table, op, seat, still_legal, source, ctx,
                            subj, ctx2):
                if combat.mark_damage(state, table, i, op.n):
                    log.setdefault("killed", []).append(i)
        elif op.op == OP_MODIFY_MIGHT_ALL:
            # "give enemy units -3 Might this turn" -- no count, no choice, so
            # not targets (355.10) and no slot. Each unit it reaches gets the
            # same 143.2.a re-check a single Might change would.
            for i in _sweep(state, table, op, seat, still_legal, source, ctx,
                            subj, ctx2):
                if combat.set_might_mod(state, table, i, op.n, op.floor):
                    log.setdefault("killed_by_might", []).append(i)
        elif op.op == OP_READY:
            woke = int(state.perms[a, P_READY]) == 0
            state.perms[a, P_READY] = 1
            log.setdefault("readied", []).append(a)
            if woke:
                from rl.engine.effects import TR_READIED
                chain.fire_watchers(state, table, int(state.perms[a, P_CTRL]),
                                    TR_READIED, subj=a)
        elif op.op == OP_SWAP_LOC:
            b = _slot(state, still_legal, op.target_b, source, ctx,
                      seat, subj, ctx2)
            if b < 0:
                log["fizzled"].append(op.op)
                continue
            la, lb = int(state.perms[a, P_LOC]), int(state.perms[b, P_LOC])
            combat.queue_move_trigger(state, table, a, la, lb)
            combat.queue_move_trigger(state, table, b, lb, la)
            state.perms[a, P_LOC], state.perms[b, P_LOC] = lb, la
            log["swapped"] = (a, b)
        else:
            raise ValueError(f"unknown op {op.op}")
        log["resolved"].append(op.op)
    return log
