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


def plan_payment(state: GameState, table: CardTable, seat: int,
                 card: int) -> list[int] | None:
    """Which domains to recycle for Power, or None if the card is unaffordable.

    Energy is generic (163.1.a) and comes from exhausting ready runes. Power is
    domain-bound (163.2) and comes from recycling, which may take an already
    exhausted rune -- so the two requirements are checked against *overlapping*
    pools, and a card needs max(energy, power) runes rather than their sum.
    """
    need_e = int(table.energy[card]) - int(state.pool_energy[seat])
    need_e = max(0, need_e)
    if need_e > state.total_ready_runes(seat):
        return None

    need_p = int(table.power[card])
    if need_p <= 0:
        return []
    doms = card_domains(table, card)
    if not doms:
        return None      # a Power cost with no domain is unpayable

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
        recycle: list[int]) -> None:
    """Exhaust for Energy, then recycle for Power. Order matters.

    Exhausting first is what makes one rune pay both halves: the recycle step
    can then take a rune that was just spent on Energy.
    """
    need_e = max(0, int(table.energy[card]) - int(state.pool_energy[seat]))
    state.pool_energy[seat] = max(
        0, int(state.pool_energy[seat]) - int(table.energy[card]))
    for _ in range(need_e):
        dom = int(np.argmax(state.runes_ready[seat]))
        assert state.runes_ready[seat, dom] > 0, "energy payment underflow"
        state.runes_ready[seat, dom] -= 1
        state.runes_spent[seat, dom] += 1

    need_p = int(table.power[card])
    for d in card_domains(table, card):
        use = min(need_p, int(state.pool_power[seat, d]))
        state.pool_power[seat, d] -= use
        need_p -= use
    for dom in recycle:
        state.recycle_rune(seat, dom)


