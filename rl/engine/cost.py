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


