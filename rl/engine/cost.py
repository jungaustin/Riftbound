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
from rl.engine.state import N_DOMAINS, GameState


# Power symbols on a multi-domain card: each symbol may be paid by a rune of ANY
# of the card's domains. The card data records a domain list and a power count
# but not the per-symbol breakdown, so a stricter reading cannot be
# distinguished from the data alone. Permissive never blocks a play a human
# could make; verify against card images before trusting a result that hinges on
# a multi-domain Power cost.
MULTI_DOMAIN_POWER_IS_PERMISSIVE = True


# ---------------------------------------------------------------------------
# NOT IMPLEMENTED YET, and the design is already decided -- read this before
# adding the first cost-reducing card.
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
    need_e = int(table.energy[card]) + extra_energy - int(state.pool_energy[seat])
    need_e = max(0, need_e)
    if need_e > state.total_ready_runes(seat):
        return None

    need_p = int(table.power[card]) + extra_power
    if need_p <= 0:
        return []
    doms = card_domains(table, card)
    if not doms:
        # 805.1.a.2 -- a domainless unit may pay Accelerate's Power with a rune
        # of ANY domain. A *printed* Power cost with no domain stays unpayable.
        if int(table.power[card]) > 0 or extra_power <= 0:
            return None
        doms = list(range(N_DOMAINS))

    floating = sum(int(state.pool_power[seat, d]) for d in doms)
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
    fe, fp = int(table.flow_energy[card]), int(table.flow_power[card])
    if fe < 0:
        return None
    return plan_ability_cost(state, table, seat, card, fe, fp)


def plan_surcharge(state: GameState, table: CardTable, seat: int, card: int,
                   power: int) -> list[int] | None:
    """Domains to recycle for a Deflect surcharge on top of `card`'s own cost.

    809.1.c.1 is explicit that **this Power may be of any Domain**, unlike the
    card's printed Power -- "a Fury spell targets an Order unit with Deflect;
    the Power used to pay can be any Domain". So it cannot go through
    `plan_payment`'s `extra_power`, which allocates within the CARD's domains
    and would refuse a payment the rules allow.

    Returns the surcharge's own recycles, or None if the seat cannot cover both
    this and the card's printed cost from the same rune board.
    """
    base = plan_payment(state, table, seat, card)
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


def plan_ability_cost(state: GameState, table: CardTable, seat: int, card: int,
                      energy: int, power: int) -> list[int] | None:
    """Same as `plan_payment` but for a cost that is NOT a card's printed one.

    An activated ability's base cost is written before the ':' (204.1.b) and
    has nothing to do with what the permanent cost to play. Its Power is paid
    in the source's own domains, which is what the printed symbols mean.
    """
    need_e = max(0, energy - int(state.pool_energy[seat]))
    if need_e > state.total_ready_runes(seat):
        return None
    if power <= 0:
        return []
    doms = card_domains(table, card) or list(range(N_DOMAINS))
    floating = sum(int(state.pool_power[seat, d]) for d in doms)
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
                     energy: int, recycle: list[int]) -> None:
    """Pay an activated ability's rune cost."""
    need_e = max(0, energy - int(state.pool_energy[seat]))
    state.pool_energy[seat] = max(0, int(state.pool_energy[seat]) - energy)
    for _ in range(need_e):
        dom = int(np.argmax(state.runes_ready[seat]))
        assert state.runes_ready[seat, dom] > 0, "energy payment underflow"
        state.runes_ready[seat, dom] -= 1
        state.runes_spent[seat, dom] += 1
    for dom in recycle:
        state.recycle_rune(seat, dom)


def pay(state: GameState, table: CardTable, seat: int, card: int,
        recycle: list[int], extra_energy: int = 0,
        extra_power: int = 0) -> None:
    """Exhaust for Energy, then recycle for Power. Order matters.

    Exhausting first is what makes one rune pay both halves: the recycle step
    can then take a rune that was just spent on Energy.
    """
    total_e = int(table.energy[card]) + extra_energy
    need_e = max(0, total_e - int(state.pool_energy[seat]))
    state.pool_energy[seat] = max(0, int(state.pool_energy[seat]) - total_e)
    for _ in range(need_e):
        dom = int(np.argmax(state.runes_ready[seat]))
        assert state.runes_ready[seat, dom] > 0, "energy payment underflow"
        state.runes_ready[seat, dom] -= 1
        state.runes_spent[seat, dom] += 1

    need_p = int(table.power[card]) + extra_power
    doms = card_domains(table, card) or list(range(N_DOMAINS))
    for d in doms:
        use = min(need_p, int(state.pool_power[seat, d]))
        state.pool_power[seat, d] -= use
        need_p -= use
    for dom in recycle:
        state.recycle_rune(seat, dom)


