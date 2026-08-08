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
                               COND_NONE, COND_ONLY_UNIT_THERE,
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
                               REL_SAME_BF, TK_UNIT, W_ANY, W_ENEMY,
                               TK_LOCATION, TK_SPELL, TK_TRASH_CARD,
                               OP_TRASH_TO_HAND, OP_PLAY_FROM_TRASH,
                               W_FRIENDLY,
                               TR_PLAY_ME, T_CTX, T_HERE, T_OWNER_BASE,
                               T_SELF,
                               CardSpec, Op,
                               TargetSpec)
from rl.engine import chain
from rl.engine.state import (C_CARD, C_CTRL, C_FINAL, C_UID, COST_NO_ENERGY,
                             F_BUFFED,
                             F_DIED_ALONE,
                             N_BF, P_ALIVE, P_FLAGS,
                             P_CARD, P_CTRL, P_DMG, P_LOC, P_READY, GameState,
                             base_loc, bf_loc, is_battlefield)


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
        total += int(table.deflect[int(state.perms[p, P_CARD])])
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
             source: int = -1) -> bool:
    """Does `perm` satisfy one slot's restrictions?"""
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
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


def _spell_targets(state: GameState, table: CardTable, spec: TargetSpec,
                   chosen: list[int]) -> list[int]:
    """Chain items this slot may counter, as stable uids.

    Excludes items still Pending and the countering card itself: at the moment
    its targets are chosen it is the newest item on the chain, and a spell
    cannot counter itself.
    """
    out = []
    newest = state.n_chain - 1
    for i in range(state.n_chain):
        if i == newest or state.chain[i, C_FINAL] != 1:
            continue
        card = int(state.chain[i, C_CARD])
        if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
            continue
        if spec.max_power >= 0 and int(table.power[card]) > spec.max_power:
            continue
        uid = int(state.chain[i, C_UID])
        if uid not in chosen:
            out.append(uid)
    return out


def can_play_from_trash(state: GameState, table: CardTable, seat: int,
                        card: int, free_energy: bool) -> bool:
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
    card_spec = _spec_for(table, card)
    if card_spec is None:
        return False                       # no rules text the engine can run
    # "ignoring its Energy cost. (You must still pay its Power cost.)"
    plan = (plan_ability_cost(state, table, seat, card, 0,
                              int(table.power[card])) if free_energy
            else plan_payment(state, table, seat, card))
    if plan is None:
        return False
    # Terminates because no spell in the pool replays a spell that replays a
    # spell; two that did would recurse forever right here.
    return not card_spec.n_targets or can_be_cast(
        state, table, card_spec, seat, -1, card=card)


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
                                   spec.playable_free_energy):
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


def _trash_targets(state: GameState, table: CardTable, spec: TargetSpec,
                   seat: int, chosen: list[int]) -> list[int]:
    """Distinct cards in `seat`'s trash this slot may name (108.2.c).

    Returns CARD IDS, deduplicated: two copies of one card in an unordered zone
    are the same choice, and offering both would double the branching factor to
    describe a decision that does not exist.

    But a slot may still name a card an EARLIER slot already named, so long as
    the trash actually holds another copy -- Guerilla Warfare returning two
    Sprite Calls is legal when two are there and illegal when one is. So the
    exclusion counts copies rather than testing membership, which is the same
    duplicate bookkeeping [Flow] needed and the opposite of the `not in chosen`
    rule that unit slots use (a permanent row IS unique).
    """
    n = int(state.n_trash[seat])
    have: dict[int, int] = {}
    for i in range(n):
        c = int(state.trash[seat, i])
        have[c] = have.get(c, 0) + 1
    out: list[int] = []
    for card, count in have.items():
        if chosen.count(card) >= count:
            continue
        if _trash_card_ok(table, spec, card, state, seat):
            out.append(card)
    return sorted(out)


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
    return [base_loc(seat)] + [bf_loc(i) for i in range(N_BF)]


def legal_targets(state: GameState, table: CardTable, spec: CardSpec, slot: int,
                  seat: int, chosen: list[int], bound_bf: int,
                  source: int = -1, card: int = -1) -> list[int]:
    """Values that may fill `slot`. Their meaning depends on the slot's kind:
    a permanent row, a chain uid (TK_SPELL), or a location (TK_LOCATION)."""
    t = spec.targets[slot]
    if t.kind == TK_LOCATION:
        return _location_targets(state, t, seat, bound_bf)
    if t.kind == TK_SPELL:
        return _spell_targets(state, table, t, chosen)
    if t.kind == TK_TRASH_CARD:
        return _trash_targets(state, table, t, seat, chosen)
    return [i for i in range(state.n_perms)
            if i not in chosen
            and _matches(state, table, t, i, seat, chosen, bound_bf, source)
            # 809 -- an unaffordable Deflect surcharge makes it not a choice.
            and _affordable_with(state, table, card, seat, chosen,
                                 int(table.deflect[int(state.perms[i, P_CARD])])
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
                     dead_source: int = -1) -> bool:
    if op.cond == COND_NONE:
        return True
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
        return any(table.has(int(state.perms[t, P_CARD]), "Temporary")
                   for t in targets if t >= 0)
    raise ValueError(f"unknown condition {op.cond}")


def _slot(state: GameState, still_legal: list[int], idx: int, source: int,
          ctx: int) -> int:
    """Decode an op's target index, including the pseudo-slots.

    A spell's ops address chosen targets by slot. A unit ability also has to
    say "me", "here" and "there" -- none of which are choices, so none of which
    can be slots. Decoding them in one place means every op that takes a target
    understands them without knowing they exist.
    """
    if idx == T_SELF:
        return source
    if idx == T_HERE:
        return int(state.perms[source, P_LOC]) if source >= 0 else -1
    if idx == T_CTX:
        return ctx

    return still_legal[idx] if 0 <= idx < len(still_legal) else -1


def resolve(state: GameState, table: CardTable, cfg: Config, spec: CardSpec,
            seat: int, targets: list[int], bound_bf: int,
            from_hand: bool, source: int = -1, ctx: int = -1) -> dict:
    """Apply a finalized card's or ability's ops. Returns a log dict.

    Targets are re-checked here, not trusted from finalization: the window
    between the two is exactly where a response lands (359.3.e).

    `source` and `ctx` are the two things a triggered ability knows and a spell
    does not: the permanent it is printed on, and the location captured when it
    triggered (359.3.f.3). Both are -1 for a card.
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
        if spec.targets[slot].kind == TK_LOCATION:
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
            # [Flow], only the first slot may still have it.
            need = chosen_so_far.count(t) + 1
            ok = t >= 0 and int(np.count_nonzero(
                state.trash[seat, :int(state.n_trash[seat])] == t)) >= need
        else:
            ok = (t >= 0 and _matches(state, table, spec.targets[slot], t, seat,
                                      chosen_so_far, bound_bf, source))
        still_legal.append(t if ok else -1)
        chosen_so_far.append(t if ok else -1)

    # 359.3.e.5/e.6 -- if every target is gone, the whole thing is countered.
    if spec.n_targets and all(t < 0 for t in still_legal):
        log["countered"] = True
        return log

    for op in spec.ops:
        if not _condition_holds(state, table, op, still_legal, from_hand,
                                seat, source, ctx, dead_source):
            log["fizzled"].append(op.op)
            continue

        if op.op == OP_DRAW:
            log["drew"] = phases.draw(state, op.n)
            log["resolved"].append(op.op)
            continue

        a = _slot(state, still_legal, op.target, source, ctx)
        if op.target != -1 and a < 0:
            log["fizzled"].append(op.op)      # this target specifically is gone
            continue

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
            if op.target_b == T_OWNER_BASE:
                # "to its base" -- the base of whoever controls THIS op's own
                # target, so an enemy unit goes home rather than to ours, and
                # a card moving two units sends each to the right place.
                dst = base_loc(int(state.perms[a, P_CTRL])) if a >= 0 else -1
            else:
                dst = _slot(state, still_legal, op.target_b, source, ctx)
            if dst < 0:
                log["fizzled"].append(op.op)
                continue
            combat.queue_move_trigger(state, table, a, int(state.perms[a, P_LOC]))
            state.perms[a, P_LOC] = dst
            if op.then_ready:
                state.perms[a, P_READY] = 1
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
            # `a` is a CARD, not a permanent row -- see the TK_TRASH_CARD note
            # in effects.py. Any copy will do, since 108.2.c makes the trash
            # unordered and the copies interchangeable.
            n = int(state.n_trash[seat])
            idx = next((i for i in range(n)
                        if int(state.trash[seat, i]) == a), -1)
            if a < 0 or idx < 0:
                log["fizzled"].append(op.op)
                continue
            state.trash[seat, idx:n - 1] = state.trash[seat, idx + 1:n]
            state.trash[seat, n - 1] = -1
            state.n_trash[seat] = n - 1
            h = int(state.n_hand[seat])
            assert h < state.hand.shape[1], "hand overflow"
            state.hand[seat, h] = a
            state.n_hand[seat] = h + 1
            log.setdefault("from_trash", []).append(table.names[a])
        elif op.op == OP_PLAY_FROM_TRASH:
            # 349 -- this PLAYS the card. It is not moved to the board and it is
            # not resolved here: it goes on the Chain as a new Pending Item and
            # takes its own priority windows, which is why the opponent can
            # counter what Fizz digs up. `actions._advance_pending` picks it up
            # after this resolution finishes (340.3).
            n = int(state.n_trash[seat])
            idx = next((i for i in range(n)
                        if int(state.trash[seat, i]) == a), -1)
            # Re-checked HERE, not just at finalization -- a priority window
            # stood between the two and the board has moved. See
            # `can_play_from_trash`.
            if (a < 0 or idx < 0
                    or not can_play_from_trash(state, table, seat, a, True)):
                log["fizzled"].append(op.op)
                continue
            state.trash[seat, idx:n - 1] = state.trash[seat, idx + 1:n]
            state.trash[seat, n - 1] = -1
            state.n_trash[seat] = n - 1
            chain.push(state, a, seat, from_hand=False, bound_bf=-1,
                       cost=COST_NO_ENERGY, dest=op.dest)
            log.setdefault("played_from_trash", []).append(table.names[a])
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
            if combat.set_might_mod(state, table, a, op.n, op.floor):
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
        elif op.op == OP_DISCARD:
            log["discarded"] = phases.discard(state, seat, op.n)
        elif op.op == OP_KILL_ALL:
            for i in range(state.n_perms):
                r = state.perms[i]
                if r[P_ALIVE] == 1 and table.is_type(int(r[P_CARD]), "Unit"):
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
            # "Deal N to all units at battlefields" -- untargeted (355.10) and
            # indiscriminate: it hits the caster's units too.
            for i in range(state.n_perms):
                r = state.perms[i]
                if r[P_ALIVE] != 1 or not is_battlefield(int(r[P_LOC])):
                    continue
                if not table.is_type(int(r[P_CARD]), "Unit"):
                    continue
                if combat.mark_damage(state, table, i, op.n):
                    log.setdefault("killed", []).append(i)
        elif op.op == OP_MODIFY_MIGHT_ALL:
            # "give enemy units -3 Might this turn" -- no count, no choice, so
            # not targets (355.10) and no slot. It reaches every enemy unit on
            # the board, and each one gets the same 143.2.a re-check a single
            # Might change would.
            for i in range(state.n_perms):
                r = state.perms[i]
                if r[P_ALIVE] != 1 or int(r[P_CTRL]) == seat:
                    continue
                if not table.is_type(int(r[P_CARD]), "Unit"):
                    continue
                if combat.set_might_mod(state, table, i, op.n, op.floor):
                    log.setdefault("killed_by_might", []).append(i)
        elif op.op == OP_READY:
            state.perms[a, P_READY] = 1
            log.setdefault("readied", []).append(a)
        elif op.op == OP_SWAP_LOC:
            b = _slot(state, still_legal, op.target_b, source, ctx)
            if b < 0:
                log["fizzled"].append(op.op)
                continue
            la, lb = int(state.perms[a, P_LOC]), int(state.perms[b, P_LOC])
            combat.queue_move_trigger(state, table, a, la)
            combat.queue_move_trigger(state, table, b, lb)
            state.perms[a, P_LOC], state.perms[b, P_LOC] = lb, la
            log["swapped"] = (a, b)
        else:
            raise ValueError(f"unknown op {op.op}")
        log["resolved"].append(op.op)
    return log
