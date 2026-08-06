"""Legal action enumeration.

The pilot can only ever return an index into the list this module builds, so
every rules restriction that matters is enforced here rather than trusted to the
pilot. Two filters gate every play:

  timing — the card's tier must be allowed by the current four-state
  cost   — the player must be able to actually pay

Both must pass. A card failing only the timing filter is the interesting case,
and `unplayable_reason` reports which filter rejected it so the renderer can
show a ✗ that means "wrong moment" rather than "too expensive".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import Card
from .state import GameState, PlayerState

# Power symbols on a multi-domain card: this engine lets each symbol be paid by
# a rune of ANY of the card's domains. The card data records a domain list and a
# power count but not the per-symbol breakdown, so a stricter reading (one
# symbol per domain) cannot be distinguished from the data alone. Permissive is
# the safer default: it never blocks a play a human could make. Verify against
# card images before trusting results that hinge on a multi-domain power cost.
# In the Lillia v7 / Darius matchup exactly one card is affected: Lilting
# Lullaby (2E+2P, Calm/Mind).
MULTI_DOMAIN_POWER_IS_PERMISSIVE = True


@dataclass(frozen=True)
class Payment:
    """Which runes to exhaust for Energy and recycle for Power."""
    exhaust: tuple[str, ...] = ()   # rune ids -> 1 Energy each
    recycle: tuple[str, ...] = ()   # rune ids -> 1 Power each, leaves play

    def describe(self) -> str:
        bits = []
        if self.exhaust:
            bits.append(f"exhaust {len(self.exhaust)}")
        if self.recycle:
            bits.append(f"recycle {len(self.recycle)}")
        return ", ".join(bits) or "free"


@dataclass(frozen=True)
class Action:
    kind: str                      # play | move | pass
    description: str
    card: Card | None = None
    source_id: str | None = None
    target: str | None = None
    payment: Payment | None = None

    def render(self) -> str:
        cost = f"  ({self.payment.describe()})" if self.payment else ""
        return f"{self.description}{cost}"


def plan_payment(player: PlayerState, card: Card) -> Payment | None:
    """Cheapest rune assignment for a card's cost, or None if unaffordable.

    Energy is generic — any rune exhausts for 1 (163.1.a). Power is
    domain-bound — a rune recycled for Power produces Power of its own domain
    (164.2.b.1) and leaves play. So Power runes must be chosen first from the
    matching domains, and whatever is left covers Energy.
    """
    need_energy = max(0, card.energy - player.pool.energy)
    floating = sum(v for d, v in player.pool.power.items()
                   if not card.domains or d in card.domains)
    need_power = max(0, card.power - floating)

    ready = list(player.ready_runes)

    recycle: list[str] = []
    if need_power:
        if not card.domains:
            return None  # a Power cost with no domain is unpayable
        matching = [r for r in ready if r.domain in card.domains]
        if len(matching) < need_power:
            return None
        # Prefer recycling the domain we hold most of, to keep scarce domains.
        by_scarcity = sorted(
            matching,
            key=lambda r: -sum(1 for x in ready if x.domain == r.domain),
        )
        chosen = by_scarcity[:need_power]
        recycle = [r.id for r in chosen]
        ready = [r for r in ready if r.id not in set(recycle)]

    if len(ready) < need_energy:
        return None
    return Payment(exhaust=tuple(r.id for r in ready[:need_energy]),
                   recycle=tuple(recycle))


def timing_ok(state: GameState, card: Card) -> bool:
    return card.timing in state.playable_timings()


def unplayable_reason(state: GameState, player: PlayerState,
                      card: Card) -> str | None:
    """None if playable now, else a short reason. Timing is reported first."""
    if not timing_ok(state, card):
        return f"timing: {card.timing_label()} not playable in {state.state_name}"
    if plan_payment(player, card) is None:
        return "cost: not enough runes"
    return None


def _unit_destinations(state: GameState, seat: int) -> list[str]:
    return [f"base:{seat}"] + [bf.key for bf in state.battlefields]


def _location_label(state: GameState, key: str, seat: int) -> str:
    if key.startswith("base:"):
        return "your base" if key == f"base:{seat}" else "their base"
    idx = int(key.split(":")[1])
    return f"B{idx + 1} {state.battlefields[idx].card.name}"


def legal_actions(state: GameState, seat: int) -> list[Action]:
    """Every action `seat` may legally take right now.

    Returns only `pass` when the player lacks Priority. Focus without Priority
    is a real state in which waiting is the only legal move (313.4).
    """
    out: list[Action] = []
    if state.winner is not None or state.priority != seat:
        return [Action(kind="pass", description="pass")]

    player = state.player(seat)

    for card in _unique(player.hand):
        if not timing_ok(state, card):
            continue
        payment = plan_payment(player, card)
        if payment is None:
            continue
        if card.is_unit:
            for dest in _unit_destinations(state, seat):
                out.append(Action(
                    kind="play", card=card, target=dest, payment=payment,
                    description=(f"play {card.name} "
                                 f"-> {_location_label(state, dest, seat)}"),
                ))
        else:
            out.append(Action(
                kind="play", card=card, payment=payment,
                description=f"play {card.name} ({card.type})",
            ))

    # Movement is only legal in a Neutral Open state on your own turn; it is a
    # discretionary action, not a card play, so no timing tier applies.
    if state.is_open and state.is_neutral and state.active == seat:
        for perm in state.at(f"base:{seat}", seat) + [
            p for bf in state.battlefields for p in state.at(bf.key, seat)
        ]:
            if not perm.ready or not perm.card.is_unit:
                continue
            for dest in _unit_destinations(state, seat):
                if dest == perm.location:
                    continue
                out.append(Action(
                    kind="move", source_id=perm.id, target=dest,
                    description=(f"move {perm.card.name} "
                                 f"-> {_location_label(state, dest, seat)}"),
                ))

    out.append(Action(kind="pass", description="pass"))
    return out


def _unique(cards: list[Card]) -> list[Card]:
    """Collapse duplicate copies — three identical cards are one choice."""
    seen: dict[str, Card] = {}
    for c in cards:
        seen.setdefault(c.name, c)
    return list(seen.values())


def only_pass(actions: list[Action]) -> bool:
    """True when the engine should auto-pass instead of asking a pilot.

    This is what takes a game from 400+ decisions to roughly 200 — most
    Closed-State priority windows are ones where the player holds no [Reaction]
    and therefore has nothing it could legally do.
    """
    return len(actions) == 1 and actions[0].kind == "pass"
