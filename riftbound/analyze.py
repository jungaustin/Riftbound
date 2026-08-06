"""Deterministic deck statistics.

Everything here is computed from card data alone, so it is always grounded.
The text-pattern buckets (removal, draw, ...) are heuristics over card text and
are labelled as such wherever they are shown to a model, so it does not present
them as authoritative.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .copies import at_least_one, cards_seen_by_turn
from .decklist import Deck
from .model import Card

# Heuristic buckets. Substring match on lowercased card text.
ROLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "removal": ("kill ", "destroy", "deals damage to", "damage to a unit", "slay"),
    "draw": ("draw ", "look at the top", "search your deck"),
    "recursion": ("from your trash", "return .* to your hand", "recycle"),
    "rune_ramp": ("ready a rune", "ready 2 runes", "additional rune", "channel"),
    "buff": ("+1 might", "+2 might", "gets +", "gains ", "shield"),
    "disruption": ("discard", "your opponent", "opponents ", "stun", "exhaust"),
    "recruit": ("recruit", "create a", "summon"),
}


@dataclass
class DeckStats:
    main_count: int
    rune_count: int
    battlefield_count: int
    identity: set[str]
    type_counts: Counter
    curve: Counter                     # energy cost -> copies
    total_curve: Counter               # energy+power -> copies (the real curve)
    avg_energy: float
    avg_total: float
    might_by_cost: dict[int, float]
    domain_pips: Counter               # domain -> copies printed in it (legality, not casting)
    rune_split: Counter
    rune_vs_demand: dict[str, dict]
    tag_counts: Counter
    role_counts: Counter
    pip_demand: Counter = field(default_factory=Counter)
    pip_flexible: Counter = field(default_factory=Counter)
    flexible_pips: int = 0
    no_power_copies: int = 0
    recycle_total: int = 0
    copy_distribution: Counter = field(default_factory=Counter)
    singletons: list[str] = field(default_factory=list)
    playsets: list[str] = field(default_factory=list)
    champion_units: list[str] = field(default_factory=list)
    signatures: list[str] = field(default_factory=list)

    def render(self) -> str:
        L = []
        L.append(f"Size: {self.main_count} main / {self.rune_count} runes / "
                 f"{self.battlefield_count} battlefields")
        L.append(f"Identity: {'+'.join(sorted(self.identity)) or 'none'}")
        L.append("Types: " + ", ".join(f"{k} {v}" for k, v in self.type_counts.most_common()))
        L.append(f"Average runes to cast: {self.avg_total:.2f} "
                 f"(avg energy {self.avg_energy:.2f})")
        L.append("Runes needed = max(energy, power), NOT energy+power: one rune can be")
        L.append("exhausted for Energy AND then recycled for Power (164.2 / 416), so")
        L.append("{2}{P1} costs 2 runes. Power's cost is ATTRITION, counted below.")
        L.append("Curve by RUNES NEEDED (runes: copies): " + ", ".join(
            f"{k}:{self.total_curve[k]}" for k in sorted(self.total_curve)))
        L.append(f"Rune attrition: {self.recycle_total} runes leave the pool if every "
                 f"copy is cast")
        L.append("  (each recycled rune must be re-channelled before it works again;")
        L.append("   that is the real price of a Power cost, not a later cast turn)")
        L.append("Runes channelled by turn (no ramp): T1 2, T2 4, T3 6, T4 8, T5 10, T6+ 12")
        L.append("  (+1 on the draw, first turn only)")
        if self.might_by_cost:
            L.append("Avg might by cost: " + ", ".join(
                f"{k}:{v:.1f}" for k, v in sorted(self.might_by_cost.items())))
        L.append("")
        L.append("Rune requirements (Power costs only — Energy is generic and needs no")
        L.append("specific rune, so a card's printed domain does NOT mean it needs that rune):")
        L.append(f"  {self.no_power_copies} of {self.main_count} main-deck copies have NO Power "
                 f"cost and are castable off any runes.")
        for d, row in sorted(self.rune_vs_demand.items()):
            flex = self.pip_flexible.get(d, 0)
            extra = f"  (+{flex} hybrid pips payable by this or another domain)" if flex else ""
            L.append(f"  {d:8} hard pips {row['pips']:3}  runes {row['runes']:2}  "
                     f"{row['ratio']}{extra}")
        L.append("")
        L.append("Heuristic roles (substring match on card text, not authoritative):")
        for k, v in self.role_counts.most_common():
            L.append(f"  {k:12} {v}")
        if self.tag_counts:
            L.append("")
            L.append("Top tags: " + ", ".join(
                f"{k} {v}" for k, v in self.tag_counts.most_common(8)))
        if self.champion_units:
            L.append("Champion units: " + ", ".join(self.champion_units))
        if self.signatures:
            L.append("Signature cards: " + ", ".join(self.signatures))
        L.append("")
        L.append("Copy distribution: " + ", ".join(
            f"{n}x -> {k} card{'s' if k != 1 else ''}"
            for n, k in sorted(self.copy_distribution.items())) or "none")
        L.append(
            f"  A 1-of in a {self.main_count}-card deck is seen by turn 5 about "
            f"{at_least_one(1, cards_seen_by_turn(5), self.main_count):.0%} of the time; "
            f"a 3-of about {at_least_one(3, cards_seen_by_turn(5), self.main_count):.0%}."
        )
        if self.singletons:
            L.append(f"Singletons ({len(self.singletons)}): " + ", ".join(self.singletons))
        L.append(f"Playsets of 3 ({len(self.playsets)}): " + ", ".join(self.playsets))
        return "\n".join(L)


def analyze(deck: Deck) -> DeckStats:
    cards: list[tuple[Card, int]] = deck.main_cards()

    type_counts = Counter()
    curve = Counter()
    total_curve = Counter()
    domain_pips = Counter()
    tag_counts = Counter()
    role_counts = Counter()
    might_sum: dict[int, list[int]] = defaultdict(list)
    pip_demand = Counter()      # hard requirement: single-domain Power
    pip_flexible = Counter()    # hybrid Power, payable by any listed domain
    flexible_pips = 0
    colourless_copies = 0       # copies with no Power cost at all
    energy_total = 0
    energy_cards = 0
    grand_total = 0
    costed_copies = 0
    recycle_total = 0          # runes that leave the pool if every copy is cast

    for c, n in cards:
        # A dual-type card counts under every type it prints, so the totals
        # can exceed the deck size. That is correct, not a bug.
        for t in c.all_types:
            type_counts[t] += n
        if c.energy is not None or (c.power or 0):
            # Runes needed = max(energy, power), NOT energy + power.
            # A rune has two independent abilities (164.2): "[E]: Add 1 Energy"
            # and "Recycle this: Add 1 Power". Recycle has no ready-state
            # requirement (416), so the SAME rune can be exhausted for Energy
            # and then recycled for Power in one turn. Paying {2}{P1} therefore
            # takes 2 runes, not 3: exhaust both for Energy, recycle one of them
            # for the Power. Power's real cost is attrition (the rune leaves
            # your pool), tracked separately below — not a higher cast cost.
            tot = max(c.energy or 0, c.power or 0)
            total_curve[tot] += n
            grand_total += tot * n
            costed_copies += n
            recycle_total += (c.power or 0) * n
        if c.energy is not None:
            curve[c.energy] += n
            energy_total += c.energy * n
            energy_cards += n
            if c.might is not None:
                might_sum[c.energy].extend([c.might] * n)
        # Rune requirements come from the POWER cost only. Energy has no
        # Domain (rule 156.1.a); Power does (156.2.a). A card printed in Fury
        # with no Power cost is castable off any runes at all, so counting it
        # as Fury demand — which an earlier version did — badly overstates how
        # coloured a deck really is.
        pow_cost = c.power or 0
        doms = sorted(c.domain_set)
        if pow_cost:
            if len(doms) == 1:
                pip_demand[doms[0]] += pow_cost * n
            elif len(doms) > 1:
                # Multi-domain cards print a hybrid symbol, payable with any one
                # of their domains (verified against card art). Counted apart so
                # it is never mistaken for a hard requirement.
                flexible_pips += pow_cost * n
                for d in doms:
                    pip_flexible[d] += pow_cost * n
        else:
            colourless_copies += n
        for d in c.domain_set:
            domain_pips[d] += n
        for t in c.tags:
            tag_counts[t] += n
        low = (c.text or "").lower()
        for role, pats in ROLE_PATTERNS.items():
            if any(p in low for p in pats):
                role_counts[role] += n

    rune_split = Counter()
    for name, n in deck.runes.items():
        for d in deck.card(name).domain_set:
            rune_split[d] += n

    rune_vs_demand = {}
    for d in sorted(deck.identity):
        pips = pip_demand.get(d, 0)
        runes = rune_split.get(d, 0)
        rune_vs_demand[d] = {
            "pips": pips,
            "runes": runes,
            "ratio": f"{pips / runes:.1f} pips per rune" if runes else "NO RUNES",
        }

    return DeckStats(
        main_count=deck.main_count,
        rune_count=deck.rune_count,
        battlefield_count=deck.battlefield_count,
        identity=deck.identity,
        type_counts=type_counts,
        curve=curve,
        total_curve=total_curve,
        avg_energy=(energy_total / energy_cards) if energy_cards else 0.0,
        avg_total=(grand_total / costed_copies) if costed_copies else 0.0,
        recycle_total=recycle_total,
        might_by_cost={k: sum(v) / len(v) for k, v in might_sum.items()},
        domain_pips=domain_pips,
        pip_demand=pip_demand,
        pip_flexible=pip_flexible,
        flexible_pips=flexible_pips,
        no_power_copies=colourless_copies,
        rune_split=rune_split,
        rune_vs_demand=rune_vs_demand,
        tag_counts=tag_counts,
        role_counts=role_counts,
        copy_distribution=Counter(deck.main.values()),
        singletons=sorted(n for n, c in deck.main.items() if c == 1),
        playsets=sorted(n for n, c in deck.main.items() if c >= 3),
        champion_units=sorted(n for n in deck.main if deck.card(n).is_champion_unit),
        signatures=sorted(n for n in deck.main if deck.card(n).is_signature),
    )
