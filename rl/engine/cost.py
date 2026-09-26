"""Rune payment (rules 163, 164, 416).

**A card's rune requirement is max(energy, power), not the sum.** A Basic Rune
has two independent abilities (164.2): exhaust for 1 Energy, or Recycle for 1
Power of its domain. **Recycling has no ready requirement**, so a rune already
exhausted for Energy this turn can still be recycled for Power -- one physical
rune paying both halves. `sim/engine/actions.py:93` gets this wrong by removing
recycled runes from the ready pool before checking Energy; do not copy it.

The real cost of Power is *attrition*: the rune goes to the bottom of the Rune
Deck (416.1.b) and must be re-channelled at 2/turn, so the board shrinks.

Split out of `actions.py` so `combat.py` can ask "could this seat pay for a
Reaction right now?" without importing the action layer, which imports it.
"""

from __future__ import annotations

import numpy as np

from rl.engine.cardtable import CardTable
from rl.engine.state import (P_ALIVE, P_CTRL, P_CARD, P_LOC, D_ANY, N_DOMAINS,
                             bf_loc,
                             N_RESTRICT, RK_GEAR, RK_SHOWDOWN, RK_SPELL,
                             RK_UNIT, GameState)


def wild(state: GameState, seat: int) -> int:
    """Floating [A] -- Power of any Domain (135.2.e.5.b), usable for any cost."""
    return int(state.pool_power[seat, D_ANY])


def _restriction_ok(state: GameState, table: CardTable, seat: int, card: int,
                    kind: int, is_ability: bool) -> bool:
    """May a resource restricted to `kind` pay for THIS card or ability?

    135.2.e.4 lets an [Add] narrow what it produced, and every such clause in
    the pool names either a card type or a game state:

      RK_SPELL     "only to play spells"                -- a card, not an ability
      RK_SHOWDOWN  "spend only during showdowns"        -- about the moment
      RK_GEAR      "to play gear or use gear abilities" -- either, if it is gear
      RK_UNIT      "to play units or activated abilities of units"
    """
    if card < 0:
        return False
    if kind == RK_SPELL:
        return not is_ability and bool(table.is_type(card, "Spell"))
    if kind == RK_SHOWDOWN:
        return int(state.showdown_bf) >= 0
    if kind == RK_GEAR:
        return bool(table.is_type(card, "Gear"))
    if kind == RK_UNIT:
        return bool(table.is_type(card, "Unit"))
    return False


def restricted_pools(state: GameState, table: CardTable, seat: int, card: int,
                     is_ability: bool) -> tuple[int, int]:
    """(Energy, wildcard Power) from restricted pools this payment may use."""
    e = p = 0
    for kind in range(N_RESTRICT):
        if not _restriction_ok(state, table, seat, card, kind, is_ability):
            continue
        e += int(state.pool_rstr_e[seat, kind])
        p += int(state.pool_rstr_p[seat, kind])
    return e, p


def spend_restricted(state: GameState, table: CardTable, seat: int, card: int,
                     is_ability: bool, energy: int,
                     power: int) -> tuple[int, int]:
    """Take up to `energy`/`power` from the pools this payment may reach.

    Returns what is still owed. Spent BEFORE the general pool and before any
    rune is touched: a restricted resource is the one that expires unused, so
    a player would always spend it first, and no rule makes the order a choice.
    """
    for kind in range(N_RESTRICT):
        if not _restriction_ok(state, table, seat, card, kind, is_ability):
            continue
        use = min(max(0, energy), int(state.pool_rstr_e[seat, kind]))
        state.pool_rstr_e[seat, kind] -= use
        energy -= use
        usep = min(max(0, power), int(state.pool_rstr_p[seat, kind]))
        state.pool_rstr_p[seat, kind] -= usep
        power -= usep
    return max(0, energy), max(0, power)


# Power symbols on a multi-domain card: each symbol may be paid by a rune of ANY
# of the card's domains. The card data records a domain list and a power count
# but not the per-symbol breakdown, so a stricter reading cannot be
# distinguished from the data alone. Permissive never blocks a play a human
# could make; verify against card images before trusting a result that hinges on
# a multi-domain Power cost.
MULTI_DOMAIN_POWER_IS_PERMISSIVE = True


# ---------------------------------------------------------------------------
# Cost modification. `effective_energy` is the entry point; everything below
# explains why it is shaped the way it is. Read this before adding a discount.
#
# Implemented so far: discounts a card prints on ITSELF ("I cost {1 energy}
# less for each card in your trash"). Not yet: discounts other permanents grant
# ("Your spells cost {1 energy} less"), Power-side discounts, and the
# "{1 energy} OR {any rune} less" choice described below.
# ---------------------------------------------------------------------------
# 356.1 lets the player "apply base cost modifications in any order", and the
# order genuinely changes the answer, because 356.4.e says "if a discount
# applies a minimum cost, that minimum applies only to that discount". A floored
# discount used FIRST, then an unfloored one, lands below the floor:
#
#     Sky Splitter costs 8 Energy and reduces its own cost by the highest Might
#     among units you control (7). Eager Apprentice reduces spell Energy by 1,
#     to a minimum of 1.
#         Apprentice first:   8 -> 7, then Sky Splitter's own -> 0
#         Sky Splitter first: 8 -> 1, then Apprentice, floored -> 1
#
# **But the ordering is SOLVED, not chosen -- do not put it in the action
# space.** Applying discounts in descending order of floor is optimal, always.
# A floor only binds once the cost is already low, so spending the floored
# discounts while the cost is still high extracts their full value, and the
# unfloored ones then drive the remainder to zero. Verified by brute force
# against exhaustive permutation over 200k random cases: zero shortfall, where
# the naive ascending order loses up to 3. The project owner's point, and it is
# the difference between a decision the agent must learn and arithmetic the
# engine should just do -- exposing it would inflate the branching factor to
# let the policy rediscover a sort.
#
# **The decision that IS real is which component a discount hits.** Several
# cards read "{1 energy} *or* {any rune} less" (Irelia - Graceful, Ezreal
# Prodigy), and Energy and Power are not interchangeable: Energy exhausts a
# rune that comes back next turn, while Power RECYCLES it to the bottom of the
# Rune Deck (416.1.b), to be re-channelled at 2/turn. Cutting Power is
# attrition avoided; cutting Energy is only tempo, and often nothing at all,
# since the rune requirement is max(energy, power) and trimming the smaller
# component can change no rune count whatsoever. That choice is contextual,
# so it is the one that belongs to the agent.
#
# Two more rules from the same section, easy to miss:
#
#   356.4.d    a discount on TOTAL cost must be applied after every discount on
#              a single component. A rules constraint on the sort, not a choice.
#   356.4.f.1  an Optional Additional Cost counts as *paid* if the player chose
#              to pay it, "no matter how much the player actually paid" -- so a
#              discounted-to-zero [Accelerate] still makes the unit enter ready.
#              `_resolve_play` already keys readiness off the CHOICE rather than
#              the amount, which is what keeps that true for free.


def order_discounts(discounts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort (amount, floor) discounts into the order that minimises the cost.

    Descending floor. See the note above for why this is exact rather than a
    heuristic. Kept as a function rather than a comment so the first
    cost-reducing card has something correct to call instead of inventing an
    ordering at the call site.
    """
    return sorted(discounts, key=lambda d: -d[1])


def apply_discounts(cost: int, discounts: list[tuple[int, int]]) -> int:
    """Least cost reachable from `cost` (356.1 + 356.4.e). Never increases it."""
    for amount, floor in order_discounts(discounts):
        cost = min(cost, max(cost - amount, floor))
    return cost


def energy_discounts(state: GameState, table: CardTable, seat: int,
                     card: int) -> list[tuple[int, int]]:
    """(amount, floor) Energy discounts that apply to `seat` playing `card`.

    Only the card's OWN statics for now -- "I cost {1 energy} less for each
    card in your trash". Those are the ones that can be read without a board
    presence, which matters because the card is still in hand: it is not a
    permanent, so `static_might`'s "walk the board" approach cannot see it.
    Discounts printed on OTHER permanents ("Your spells cost {1 energy} less")
    are a second source and are not implemented yet.

    A LEGEND's discount comes from its own table and applies to its own
    activated ability ("this ability costs {1 energy} less for each friendly
    unit with [Temporary]"). Same shape, same self-scope -- the only difference
    is which table the static was written in, so it is unioned here rather than
    given a parallel function that would drift.
    """
    from rl.engine.effects import ST_COST_ENERGY
    return _self_discounts(state, table, seat, card, ST_COST_ENERGY)


def power_discounts(state: GameState, table: CardTable, seat: int,
                    card: int) -> list[tuple[int, int]]:
    """(amount, floor) POWER discounts that apply to `seat` playing `card`.

    `energy_discounts`' other half. Kept as its own list rather than folded
    into that one because 356.4.d applies discounts per COMPONENT: "costs
    {1 energy}{any rune} less" is a reduction of Energy AND a reduction of
    Power, and each runs `apply_discounts` over its own floor ordering.
    """
    from rl.engine.effects import ST_COST_POWER
    return _self_discounts(state, table, seat, card, ST_COST_POWER)


def pending_leftover(state: GameState, table: CardTable, seat: int,
                     card: int) -> tuple[int, int]:
    """What the one-shot "your next card costs less" promise has LEFT after the
    card's own cost, to take off its additional costs.

    356.4 discounts the total cost, and a [Repeat] is part of it: Astral
    Heron's [2][A][A] on a 1+[A] Bellows Breath paid with its 1+[A] Repeat
    makes the whole play free (RiftJudge #11670).
    """
    pe, pp = int(state.next_discount[seat, 0]), int(state.next_discount[seat, 1])
    if not (pe or pp):
        return 0, 0
    state.next_discount[seat, :] = 0
    try:
        base_e = effective_energy(state, table, seat, card)
        base_p = effective_power(state, table, seat, card)
    finally:
        state.next_discount[seat, 0], state.next_discount[seat, 1] = pe, pp
    return max(0, pe - base_e), max(0, pp - base_p)


def pending_discount(state: GameState, seat: int, power: bool) -> list[tuple[int, int]]:
    """The one-shot "your next card costs {...} less" promise, as a discount.

    Astral Heron's, and the only cost modification in this file with no source
    on the board to read it off: it is held on the PLAYER (`next_discount`) and
    is spent by the next card played. Shaped as a (amount, floor) pair so it
    sorts into `order_discounts` alongside the printed ones and obeys 356.4.e
    like any other -- it prints no minimum, hence floor 0.

    Deliberately applied in `effective_energy`/`effective_power` rather than in
    `energy_discounts`, which activated abilities also read: the Heron says
    "your next CARD", and an ability is not a card.
    """
    n = int(state.next_discount[seat, 1 if power else 0])
    return [(n, 0)] if n else []


def _increases(state: GameState, table: CardTable, seat: int, card: int,
               kind: int) -> int:
    """356.3 -- the total by which other permanents RAISE this cost.

    A flat sum: increases have no floor and no ordering question, which is
    exactly why the rules can apply them in one step before discounts.
    """
    total = sum(amount for amount, _floor
                in _board_cost_mods(state, table, seat, card, kind))
    # ...and the card's OWN printed increase ("you may play me for {Mind
    # rune}" adds Power to Jhin - Meticulous Killer).
    from rl.engine.combat import static_applies
    from rl.engine.effects import SC_SELF, statics_for
    for st in statics_for(table, card):
        if st.kind == kind and st.scope == SC_SELF and static_applies(
                state, st, seat, table=table):
            total += st.n
    return total


def _board_cost_mods(state: GameState, table: CardTable, seat: int,
                     card: int, kind: int) -> list[tuple[int, int]]:
    """Cost modifiers OTHER permanents apply to `seat` playing `card`.

    The second source `energy_discounts` documented as missing. Unlike every
    other static scope, these are about a card that is not on the board at all
    -- it is still in hand -- so they filter by card TYPE rather than by
    anything about a permanent.

    Both directions live here because they differ only in WHOSE permanent
    grants them: `SC_YOUR_CARDS` on my own permanent modifies my cards
    ("your spells cost less"), and `SC_ENEMY_CARDS` on the opponent's modifies
    mine ("opponents' spells cost more"). Walking the whole board once and
    asking each static who it speaks for is what keeps the two from drifting.

    The gate is asked of the GRANTING permanent's controller, not of `seat`:
    "while I'm in combat" is about the permanent printing the effect, and for
    an enemy-facing static those are different players.
    """
    from rl.engine.combat import static_applies, static_count
    from rl.engine.effects import SC_ENEMY_CARDS, SC_YOUR_CARDS, statics_for
    out: list[tuple[int, int]] = []
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        ctrl = int(state.perms[i, P_CTRL])
        src_card = int(state.perms[i, P_CARD])
        for st in statics_for(table, src_card):
            if st.kind != kind:
                continue
            if st.scope == SC_YOUR_CARDS:
                if ctrl != seat:
                    continue
            elif st.scope == SC_ENEMY_CARDS:
                if ctrl == seat:
                    continue
            else:
                continue
            if st.applies_to_type and not table.is_type(card,
                                                        st.applies_to_type):
                continue
            if st.applies_to_tag and st.applies_to_tag not in table.tags[card]:
                continue
            if not static_applies(state, st, ctrl, i, table=table):
                continue
            amount = st.n * static_count(state, table, st, ctrl,
                                         int(state.perms[i, P_LOC]), src_card,
                                         i)
            if amount:
                out.append((amount, st.floor))
    return out


def _self_discounts(state: GameState, table: CardTable, seat: int,
                    card: int, kind: int) -> list[tuple[int, int]]:
    """The shared walk. `kind` picks which component is being discounted."""
    from rl.engine.combat import static_applies, static_count
    from rl.engine.effects import (SC_SELF, legend_statics_for, statics_for)
    out: list[tuple[int, int]] = _board_cost_mods(state, table, seat, card,
                                                  kind)
    for st in statics_for(table, card) + legend_statics_for(table, card):
        if st.kind != kind or st.scope != SC_SELF:
            continue
        # One gate predicate for costs and for Might, so a card cannot be half
        # on. [Legion] reading `cards_played` LIVE is the deliberate part: a
        # cost is worked out as the card is played, so this card has not been
        # counted yet and any nonzero count is "another card". The OP side
        # reads a snapshot instead, because by then it has been.
        if not static_applies(state, st, seat, table=table):
            continue
        # The card is in hand, so it has no location; a self-discount that
        # counted "at my battlefield" would be meaningless and none print it.
        amount = st.n * static_count(state, table, st, seat, -1, card)
        if amount:
            out.append((amount, st.floor))
    return out


def _up_kinds():
    from rl.engine.effects import ST_COST_ENERGY_UP, ST_COST_POWER_UP
    return ST_COST_ENERGY_UP, ST_COST_POWER_UP


# True while a play from somewhere other than the hand is being costed -- the
# only time `effects.NONHAND_DISCOUNT` applies (Void Drone).
NONHAND = [False]


class nonhand:
    def __enter__(self):
        self.prev = NONHAND[0]
        NONHAND[0] = True

    def __exit__(self, *exc):
        NONHAND[0] = self.prev


def bf_cost_rules(state: GameState, table: CardTable, seat: int, kind: str):
    """(rule, battlefield index) for every ground rule of `kind` in play.

    A battlefield's cost clause is not a static: it asks about the PAYMENT --
    which type is being played, whether it is the first this turn, whether the
    spell chooses a unit standing there. `control` narrows it to the ground's
    controller, and `here` means the rule only speaks about that battlefield's
    own units, which the caller checks because only it knows what was chosen.
    """
    from rl.engine.effects import BF_COST_RULES
    for i in state.live_bfs():
        card_i = int(state.bf_card[i])
        if card_i < 0:
            continue
        rule = BF_COST_RULES.get(table.names[card_i])
        if rule is None or rule["kind"] != kind:
            continue
        if rule.get("control") and int(state.bf_ctrl[i]) != seat:
            continue
        yield rule, i


def _bf_card_discount(state: GameState, table: CardTable, seat: int,
                      card: int) -> list[tuple[int, int]]:
    """Ornn's Forge: "the first friendly non-token gear played each turn costs
    {1 energy} less". Read, not spent -- the stamp moves when the card is
    actually paid for (`note_bf_first_use`), so asking twice about the same
    play gives the same answer."""
    out = []
    for rule, i in bf_cost_rules(state, table, seat, "card"):
        if rule.get("card_type") and not table.is_type(card,
                                                       rule["card_type"]):
            continue
        if rule.get("nontoken") and table.is_token(card):
            continue
        if rule.get("first_each_turn") and int(
                state.bf_first_use[seat, i]) == int(state.ply):
            continue
        out.append((rule["n"], 0))
    return out


def note_bf_first_use(state: GameState, table: CardTable, seat: int,
                      card: int, is_ability: bool) -> None:
    """Spend a "first ... each turn" ground discount, at the moment of payment.

    Separate from reading it, because affordability is asked many times per
    decision and the discount may only be used once.
    """
    for rule, i in bf_cost_rules(state, table, seat,
                                 "ability" if is_ability else "card"):
        if not rule.get("first_each_turn"):
            continue
        if rule.get("card_type") and not table.is_type(card,
                                                       rule["card_type"]):
            continue
        if rule.get("nontoken") and table.is_token(card):
            continue
        if int(state.bf_first_use[seat, i]) != int(state.ply):
            state.bf_first_use[seat, i] = int(state.ply)
            return


def _bf_ability_discount(state: GameState, table: CardTable, seat: int,
                         card: int) -> list[tuple[int, int]]:
    """Piltovan Forge: the first friendly GEAR ability each turn costs 1 less."""
    out = []
    for rule, i in bf_cost_rules(state, table, seat, "ability"):
        if rule.get("card_type") and not table.is_type(card,
                                                       rule["card_type"]):
            continue
        if rule.get("first_each_turn") and int(
                state.bf_first_use[seat, i]) == int(state.ply):
            continue
        out.append((rule["n"], 0))
    return out


def effective_energy(state: GameState, table: CardTable, seat: int,
                     card: int) -> int:
    """The Energy `card` actually costs `seat` right now.

    **Never read `table.energy[card]` at a call site** -- the same rule
    `combat.might` states for Might, and for the same reason. A cost discount
    that `plan_payment` applies and `pay` does not is not a rounding error: the
    card is offered as affordable and then underflows the rune payment.
    """
    # 356.3 then 356.4, in that order and never the other way: an increase
    # applied after a discount could be undone by that discount's floor, and
    # `apply_discounts` is deliberately one-way.
    base = int(table.energy[card]) + _increases(state, table, seat, card,
                                                _up_kinds()[0])
    spell_promise = int(state.next_spell_discount[seat])
    if (int(state.free_gear_ply[seat]) == int(state.ply)
            and table.is_type(card, "Gear") and int(table.energy[card]) <= 7):
        return 0                    # Jayce, Man of Progress: ignore its Energy
    # Vaults of Helia, held this turn: non-token units cost {1 energy} more.
    if (int(state.unit_tax_ply[seat]) == int(state.ply)
            and table.is_type(card, "Unit") and not table.is_token(card)):
        base += 1
    if NONHAND[0]:
        from rl.engine.effects import NONHAND_DISCOUNT
        if table.names[card] in NONHAND_DISCOUNT:
            base -= min(base, NONHAND_DISCOUNT[table.names[card]])
    return apply_discounts(base, energy_discounts(state, table, seat, card)
                           + pending_discount(state, seat, power=False)
                           + _bf_card_discount(state, table, seat, card)
                           + ([(spell_promise, 0)] if spell_promise
                              and table.is_type(card, "Spell") else []))


def effective_power(state: GameState, table: CardTable, seat: int,
                    card: int) -> int:
    """The Power `card` actually costs `seat` right now.

    **Never read `table.power[card]` at a payment site** -- the same rule
    `effective_energy` states, and it was being broken everywhere because the
    Power side had no discounts to honour. It does now, and a discount that
    `plan_payment` applies while `pay` does not offers the card as affordable
    and then underflows the rune payment.

    Targeting restrictions are the deliberate exception and still read the
    printed value: "counter a spell that costs {1 power} or less" asks about
    the card, not about what its controller happened to pay.
    """
    return apply_discounts(_power_before_discounts(state, table, seat, card),
                           power_discounts(state, table, seat, card)
                           + pending_discount(state, seat, power=True))


def _power_before_discounts(state: GameState, table: CardTable, seat: int,
                            card: int) -> int:
    base = int(table.power[card]) + _increases(state, table, seat, card,
                                               _up_kinds()[1])
    # Mystic Vortex: "during showdowns HERE, cards with [Reaction] cost
    # {any rune} more to play. (Hidden cards have [Reaction].)" A tax, so it
    # is added before any discount is applied, the order 356.3/356.4 fix.
    if int(state.showdown_bf) >= 0:
        for rule, i in bf_cost_rules(state, table, seat, "reaction"):
            if rule.get("here") and int(state.showdown_bf) != i:
                continue
            if table.has(card, "Reaction"):
                base += rule["n"]
    return base


def surcharge_after_power_discounts(state: GameState, table: CardTable,
                                    seat: int, card: int, extra: int) -> int:
    """A Power surcharge (Deflect) after the card's own Power discounts.

    356.4 discounts the TOTAL cost, and Deflect is an additional cost of the
    same play, so a "{any rune} less" the card's printed Power could not use
    reduces the surcharge instead (Vex - Cheerless, RiftJudge #11184). The
    pending one-shot discount (Astral Heron) is left to its own bookkeeping.
    """
    if extra <= 0:
        return extra
    base = _power_before_discounts(state, table, seat, card)
    ds = power_discounts(state, table, seat, card)
    return apply_discounts(base + extra, ds) - apply_discounts(base, ds)


def ability_energy(state: GameState, table: CardTable, seat: int, card: int,
                   energy: int, ab=None) -> int:
    """The Energy an ACTIVATED ability actually costs `seat` right now.

    `effective_energy`'s counterpart for a cost that is not the card's printed
    one (204.1.b). Lillia - Bashful Bloom is the first thing in the pool that
    discounts its own ability -- "this ability costs {1 energy} less for each
    friendly unit with [Temporary]" -- and `plan_ability_cost` took the raw
    number, so the discount was simply not applied.

    **Called at the activation sites, not inside plan/pay.** Both of those are
    shared with the [Flow] path, which computes its own cost, and a discount
    applied inside them would be applied twice there. Computing it once here
    and handing the same number to plan and to pay is what keeps the two in
    agreement -- the failure `effective_energy`'s docstring describes, where a
    discount one half honours and the other does not offers the ability as
    affordable and then underflows the rune payment.
    """
    disc = energy_discounts(state, table, seat, card)
    # The ability's OWN printed discount (827.1.c's cost is per card): "This
    # ability costs {1 energy} less for each rune you control" (Frostcoat
    # Mother), "...{3 energy} less if you control 4 or fewer runes" (Baccai
    # Sandspinner). On the Ability, not a card static, because a card static
    # would discount playing the card too.
    if ab is not None:
        runes = int(state.runes_in_play(seat).sum())
        if ab.energy_less_per_rune:
            disc = disc + [(ab.energy_less_per_rune * runes, 0)]
        at_most, amount = ab.energy_less_if_runes_at_most
        if amount and runes <= at_most:
            disc = disc + [(amount, 0)]
    disc = disc + _bf_ability_discount(state, table, seat, card)
    # Risen Altar: "[Empower] costs of your units HERE cost {1 energy} or
    # {any rune} less". The ability is the one the keyword abbreviates
    # (827.1.c.1), so it is recognised by its op rather than by a name, and
    # "here" is read off the unit that is empowering -- which the caller knows
    # and this does not, so the source row rides on `ab`'s behalf through
    # `state.empower_src`.
    if ab is not None and any(getattr(o, "op", -1) == _op_empower()
                              for o in ab.ops):
        src = int(state.empower_src)
        if src >= 0 and state.perms[src, P_ALIVE] == 1:
            loc = int(state.perms[src, P_LOC])
            for rule, i in bf_cost_rules(state, table, seat, "empower"):
                if not rule.get("here") or loc == bf_loc(i):
                    disc = disc + [(rule["n"], 0)]
    return apply_discounts(energy, disc)


def _op_empower():
    from rl.engine.effects import OP_EMPOWER
    return OP_EMPOWER


def repeat_discount(state: GameState, table: CardTable,
                    seat: int) -> list[tuple[int, int]]:
    """Marai Spire: "friendly [Repeat] costs cost {1 energy} less"."""
    return [(rule["n"], 0)
            for rule, _i in bf_cost_rules(state, table, seat, "repeat")]


def card_domains(table: CardTable, card: int) -> list[int]:
    mask = int(table.domain_mask[card])
    return [d for d in range(N_DOMAINS) if mask >> d & 1]


def accelerate_cost(table: CardTable, card: int) -> tuple[int, int] | None:
    """The [Accelerate] additional cost, or None if the card lacks it.

    805.1.a -- "As you play me, you may pay [1][C] as an additional cost. If
    you do, I enter ready." One Energy and one Power, where the Power must
    match one of the unit's own domains (805.1.a.1) or any domain if it has
    none (805.1.a.2). `plan_payment` handles that second case.
    """
    if not table.has(card, "Accelerate"):
        return None
    return (1, 1)


def printed_add_cost(table: CardTable, card: int) -> tuple[int, int] | None:
    """The card's own printed optional additional cost, or None.

    Separate from `accelerate_cost` because the two buy different things -- one
    entering ready (805.6), the other a clause in the card's text -- but both
    are Optional Additional Costs paid as the card is played (805.2), so they
    share `A_PLAY_AT_FAST` and the same `plan_payment` call.
    """
    from rl.engine.effects import PLAY_COSTS
    return PLAY_COSTS.get(table.names[card])


def plan_payment(state: GameState, table: CardTable, seat: int, card: int,
                 extra_energy: int = 0,
                 extra_power: int = 0) -> list[int] | None:
    """Which domains to recycle for Power, or None if the card is unaffordable.

    Energy is generic (163.1.a) and comes from exhausting ready runes. Power is
    domain-bound (163.2) and comes from recycling, which may take an already
    exhausted rune -- so the two requirements are checked against *overlapping*
    pools, and a card needs max(energy, power) runes rather than their sum.

    `extra_energy`/`extra_power` are Optional Additional Costs -- currently only
    [Accelerate]. They are part of the same payment, not a second one, so they
    share the overlapping-pool rule: a unit costing {2 energy} accelerated for
    {1 energy}{1 power} needs max(3, 1) = 3 runes, not 4.
    """
    rstr_e, rstr_p = restricted_pools(state, table, seat, card, False)
    need_e = max(0, effective_energy(state, table, seat, card) + extra_energy
                 - int(state.pool_energy[seat]) - rstr_e)
    if need_e > state.total_ready_runes(seat):
        return None

    need_p = effective_power(state, table, seat, card) + extra_power
    if need_p <= 0:
        return []
    # 135.2.e.6.b -- "A [C] shorthand on a card with no Domain is processed as
    # [A] instead", so a domainless card's own printed Power cost is payable by
    # a rune of ANY domain. 805.1.a.2 says the same thing for a domainless unit
    # paying [Accelerate]'s Power, so the two collapse into one line.
    #
    # **This used to refuse a printed Power cost outright**, on the reasoning
    # that a domainless card could name no domain to pay in. Nothing caught it
    # because no such card existed -- Neeko, Blending In is the first Colorless
    # card in the pool with a Power cost, and she was unaffordable in every
    # deck, which is the opposite of what being Colorless is for. `pay` below
    # had always done it the right way (`card_domains(...) or every domain`),
    # so the affordability check and the payment disagreed.
    doms = card_domains(table, card) or list(range(N_DOMAINS))

    floating = (sum(int(state.pool_power[seat, d]) for d in doms)
                + wild(state, seat) + rstr_p)
    need_p = max(0, need_p - floating)
    if need_p == 0:
        return []

    # Recycle from the domain held most, keeping scarce domains available.
    in_play = state.runes_in_play(seat)
    avail = sorted(doms, key=lambda d: (-int(in_play[d]), d))
    picks: list[int] = []
    left = {d: int(in_play[d]) for d in doms}
    for _ in range(need_p):
        best = max(avail, key=lambda d: (left[d], -d))
        if left[best] <= 0:
            return None
        left[best] -= 1
        picks.append(best)
    return picks


def plan_flow(state: GameState, table: CardTable, seat: int,
              card: int) -> list[int] | None:
    """Payment plan for a card's [Flow] cost, or None if unaffordable.

    829.1.c.1 -- the Flow cost REPLACES the base cost, so this cannot go
    through `plan_payment`, which reads the printed corner. Power is still
    domain-bound to the card as usual; only the amount changes.
    """
    fe, fp = base_flow(state, table, seat, card)
    if fe < 0:
        return None
    return plan_ability_cost(state, table, seat, card,
                             flow_energy(state, table, seat, card), fp)


def flow_grant_index(state: GameState, seat: int, card: int) -> int:
    """The live grant slot letting `seat` play `card` from the trash, or -1."""
    for k in range(state.flow_grant_card.shape[1]):
        if int(state.flow_grant_card[seat, k]) == card and int(
                state.flow_grant_ply[seat, k]) in (-2, int(state.ply)):
            return k
    return -1


def flow_uses_grant(state: GameState, table: CardTable, seat: int,
                    card: int) -> bool:
    """Is the GRANTED [Flow] the cost this play would use?

    829.1.c.3 -- a printed [Flow] and a granted one (Kennen, Storm of Shuriken:
    "give a spell in your trash [Flow] equal to its cost") are two instances of
    the keyword on the same spell, and "the controller picks which one to
    apply". Only one price is offered rather than both, and it is the cheaper
    one: the choice exists to be taken when it helps (RiftJudge #12563), and a
    player never picks the dearer of two costs for the same effect.
    """
    k = flow_grant_index(state, seat, card)
    if k < 0:
        return False
    fe = int(table.flow_energy[card])
    if fe < 0:
        return True                       # no printed Flow: the grant IS it
    printed = fe + int(table.flow_power[card])
    return int(state.flow_grant_e[seat, k]) + int(state.flow_grant_p[seat, k]) \
        < printed


def base_flow(state: GameState, table: CardTable, seat: int,
              card: int) -> tuple[int, int]:
    """(energy, power) to play `card` from the trash: its printed [Flow], or a
    granted one (Kennen, Death from Below); (-1, -1) if neither."""
    fe, fp = int(table.flow_energy[card]), int(table.flow_power[card])
    k = flow_grant_index(state, seat, card)
    if k >= 0 and flow_uses_grant(state, table, seat, card):
        return int(state.flow_grant_e[seat, k]), int(state.flow_grant_p[seat, k])
    if fe >= 0:
        return fe, fp
    if k < 0:
        if int(state.riches_on[seat]) and table.is_type(card, "Spell"):
            return int(table.energy[card]), int(table.power[card])  # Endless Riches
        return -1, -1
    return int(state.flow_grant_e[seat, k]), int(state.flow_grant_p[seat, k])


def repeat_cost(state: GameState, table: CardTable, seat: int,
                card: int) -> tuple[int, int]:
    """(energy, power) of `card`'s [Repeat] for `seat` now, or (-1, -1).

    Printed first; otherwise granted -- Syndra - Transcendent in a showdown
    ("your spells have [Repeat] {2 energy}{Chaos rune}") or Temporal Portal's
    promise ("the next spell you play this turn [Repeat] equal to its cost").
    Only one Repeat instance is modelled, so a granted one never adds to a
    printed one.
    """
    e, p = int(table.repeat_energy[card]), int(table.repeat_power[card])
    if e >= 0 or not table.is_type(card, "Spell"):
        return e, p
    from rl.engine.effects import SHOWDOWN_REPEAT
    from rl.engine.state import P_ALIVE, P_CARD, P_CTRL, P_LOC, bf_loc
    if int(state.next_spell_repeat_ply[seat]) == int(state.ply):
        return int(table.energy[card]), int(table.power[card])
    if int(state.showdown_bf) >= 0:
        here = bf_loc(int(state.showdown_bf))
        for i in range(state.n_perms):
            if (state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == seat
                    and int(state.perms[i, P_LOC]) == here):
                got = SHOWDOWN_REPEAT.get(table.names[int(state.perms[i, P_CARD])])
                if got:
                    return got
    return -1, -1


def flow_energy(state: GameState, table: CardTable, seat: int, card: int) -> int:
    """The Energy a [Flow] play costs `seat` right now.

    Stargazer: "Spells with [Flow] you play from your trash cost {2 energy}
    less, to a minimum of {1 energy}." -- per Stargazer, each with its floor.
    """
    from rl.engine.effects import FLOW_DISCOUNTERS
    from rl.engine.state import P_ALIVE, P_CARD, P_CTRL
    fe = base_flow(state, table, seat, card)[0]
    disc = []
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1 or int(state.perms[i, P_CTRL]) != seat:
            continue
        got = FLOW_DISCOUNTERS.get(table.names[int(state.perms[i, P_CARD])])
        if got:
            disc.append(got)
    return apply_discounts(fe, disc)


def plan_surcharge(state: GameState, table: CardTable, seat: int, card: int,
                   power: int, reserved: list[int] | None = None) -> list[int] | None:
    """Domains to recycle for a Deflect surcharge on top of `card`'s own cost.

    809.1.c.1 is explicit that **this Power may be of any Domain**, unlike the
    card's printed Power -- "a Fury spell targets an Order unit with Deflect;
    the Power used to pay can be any Domain". So it cannot go through
    `plan_payment`'s `extra_power`, which allocates within the CARD's domains
    and would refuse a payment the rules allow.

    Returns the surcharge's own recycles, or None if the seat cannot cover both
    this and the card's printed cost from the same rune board.
    """
    # `reserved` is what the card's OWN cost will take off the board. Pass it
    # when that is already known -- an additional cost ([Repeat], a mode, a
    # paid optional) makes the printed cost the wrong reservation, and the
    # surcharge then picked a domain the payment was about to recycle
    # ("no rune of that domain" at finalization, real-deck fuzz seed 672,
    # Bellows Breath with its [Repeat] paid). `()` means "already paid".
    base = plan_payment(state, table, seat, card) if reserved is None else reserved
    if base is None:
        return None
    if power <= 0:
        return []
    left = {d: int(n) for d, n in enumerate(state.runes_in_play(seat))}
    for d in base:                       # the card's own Power is spoken for
        left[d] -= 1
    picks: list[int] = []
    for _ in range(power):
        best = max(range(N_DOMAINS), key=lambda d: (left[d], -d))
        if left[best] <= 0:
            return None
        left[best] -= 1
        picks.append(best)
    return picks


def plan_wild_power(state: GameState, seat: int, n: int) -> list[int] | None:
    """Which runes to recycle to pay an [A] cost of `n`, or None if unpayable.

    **[A] is POWER, not Energy.** A rune's two abilities are separate (164.2):
    exhausting adds {1} Energy, and only RECYCLING adds Power. So "pay [A]"
    costs the rune itself -- it goes to the bottom of the Rune Deck (416.1.b)
    and has to be re-channelled -- where an Energy cost only taps it for the
    turn. Getting this wrong makes every [Hidden] card a rune cheaper than it
    prints, and [Hidden] is on 40+ cards in the pool.

    Any floating Power pays it whatever its domain: [A] is the permissive side
    of the match (163.2.b), so a Fury Power satisfies it exactly as [A] Power
    would satisfy a Fury cost. That is why this sums the whole pool row rather
    than reading one column, and why it can recycle a rune of any domain.
    """
    if n <= 0:
        return []
    need = max(0, n - int(state.pool_power[seat].sum()))
    if need == 0:
        return []
    # Recycling has no ready requirement (164.2.b), so an already-exhausted
    # rune is a legal source -- `runes_in_play`, not `runes_ready`.
    left = {d: int(v) for d, v in enumerate(state.runes_in_play(seat))}
    picks: list[int] = []
    for _ in range(need):
        best = max(range(N_DOMAINS), key=lambda d: (left[d], -d))
        if left[best] <= 0:
            return None
        left[best] -= 1
        picks.append(best)
    return picks


def pay_wild_power(state: GameState, seat: int, n: int,
                   recycle: list[int]) -> None:
    """Spend an [A] cost planned by `plan_wild_power`.

    Whatever the recycles do not cover came from the pool, exactly as in
    `pay_ability_cost` -- `plan_wild_power` counts floating Power toward
    affordability, so a shorter recycle list means the pool owes the rest.
    """
    from_pool = max(0, n - len(recycle))
    if from_pool:
        # Domain-locked Power first, [A] last. The wildcard is the only Power
        # that pays for anything, so it is the last thing to spend on a cost
        # that any Power already satisfies.
        for d in list(range(N_DOMAINS)) + [D_ANY]:
            use = min(from_pool, int(state.pool_power[seat, d]))
            state.pool_power[seat, d] -= use
            state.note_power_spent(seat, use)
            from_pool -= use
        assert from_pool == 0, "wild Power payment underflow"
    for dom in recycle:
        state.recycle_rune(seat, dom)


def _ability_domains(table: CardTable, card: int) -> list[int]:
    """Domains an ability's Power may be paid in: the source's own, or any for
    a card whose ability costs print {any rune} (`ANY_RUNE_ABILITY_COSTS`)."""
    from rl.engine.effects import ANY_RUNE_ABILITY_COSTS
    if table.names[card] in ANY_RUNE_ABILITY_COSTS:
        return list(range(N_DOMAINS))
    return card_domains(table, card) or list(range(N_DOMAINS))


def plan_ability_cost(state: GameState, table: CardTable, seat: int, card: int,
                      energy: int, power: int) -> list[int] | None:
    """Same as `plan_payment` but for a cost that is NOT a card's printed one.

    An activated ability's base cost is written before the ':' (204.1.b) and
    has nothing to do with what the permanent cost to play. Its Power is paid
    in the source's own domains, which is what the printed symbols mean.
    """
    rstr_e, rstr_p = restricted_pools(state, table, seat, card, True)
    need_e = max(0, energy - int(state.pool_energy[seat]) - rstr_e)
    if need_e > state.total_ready_runes(seat):
        return None
    if power <= 0:
        return []
    doms = _ability_domains(table, card)
    floating = (sum(int(state.pool_power[seat, d]) for d in doms)
                + wild(state, seat) + rstr_p)
    need_p = max(0, power - floating)
    if need_p == 0:
        return []
    in_play = state.runes_in_play(seat)
    left = {d: int(in_play[d]) for d in doms}
    picks: list[int] = []
    for _ in range(need_p):
        best = max(doms, key=lambda d: (left[d], -d))
        if left[best] <= 0:
            return None
        left[best] -= 1
        picks.append(best)
    return picks


def pay_ability_cost(state: GameState, table: CardTable, seat: int,
                     energy: int, recycle: list[int],
                     power: int = 0, card: int = -1) -> None:
    """Pay an activated ability's or a [Flow] cost's runes.

    `power`/`card` exist because the matching `plan_ability_cost` counts
    FLOATING Power toward affordability -- so a cost partly covered by the pool
    comes back with fewer recycles than it has Power symbols, and the remainder
    has to come out of the pool here. Without that the pool was never debited:
    one floating Power paid for every Flow spell in the turn, over and over.
    `plan_*` returning [] means the pool covered all of it, not that it was free.
    """
    energy, from_pool_p = spend_restricted(state, table, seat, card, True,
                                           energy, max(0, power - len(recycle)))
    need_e = max(0, energy - int(state.pool_energy[seat]))
    state.pool_energy[seat] = max(0, int(state.pool_energy[seat]) - energy)
    for _ in range(need_e):
        dom = int(np.argmax(state.runes_ready[seat]))
        assert state.runes_ready[seat, dom] > 0, "energy payment underflow"
        state.runes_ready[seat, dom] -= 1
        state.runes_spent[seat, dom] += 1
    # Whatever the recycles did not cover was paid from the pool. Same order as
    # `pay`: domain-locked Power first, [A] last.
    from_pool = from_pool_p
    if from_pool:
        doms = _ability_domains(table, card) if card >= 0 else list(range(N_DOMAINS))
        for d in list(doms) + [D_ANY]:
            use = min(from_pool, int(state.pool_power[seat, d]))
            state.pool_power[seat, d] -= use
            state.note_power_spent(seat, use)
            from_pool -= use
    for dom in recycle:
        state.recycle_rune(seat, dom)


def pay(state: GameState, table: CardTable, seat: int, card: int,
        recycle: list[int], extra_energy: int = 0,
        extra_power: int = 0) -> None:
    """Exhaust for Energy, then recycle for Power. Order matters.

    Exhausting first is what makes one rune pay both halves: the recycle step
    can then take a rune that was just spent on Energy.
    """
    total_e = effective_energy(state, table, seat, card) + extra_energy
    total_p = effective_power(state, table, seat, card) + extra_power
    total_e, total_p = spend_restricted(state, table, seat, card, False,
                                        total_e, total_p)
    need_e = max(0, total_e - int(state.pool_energy[seat]))
    state.pool_energy[seat] = max(0, int(state.pool_energy[seat]) - total_e)
    for _ in range(need_e):
        dom = int(np.argmax(state.runes_ready[seat]))
        assert state.runes_ready[seat, dom] > 0, "energy payment underflow"
        state.runes_ready[seat, dom] -= 1
        state.runes_spent[seat, dom] += 1

    need_p = total_p
    doms = card_domains(table, card) or list(range(N_DOMAINS))
    # Domain-locked Power first, then [A]. A wildcard pays for anything, so
    # spending it while a matching domain rune is sitting right there would
    # throw away the only Power in the pool that the NEXT card might need.
    for d in list(doms) + [D_ANY]:
        use = min(need_p, int(state.pool_power[seat, d]))
        state.pool_power[seat, d] -= use
        state.note_power_spent(seat, use)
        need_p -= use
    for dom in recycle:
        state.recycle_rune(seat, dom)


