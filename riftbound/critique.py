"""Deterministic self-audit for a built deck.

This module exists because of a specific failure: a deck was built around a
Legend chosen to subsidize one awkward requirement, then improved card by card
until other cards covered that requirement better — and the Legend stayed in,
contributing almost nothing, because nothing ever re-checked it. The validator
only knows legality. Nothing knew "this card's reason for being here expired."

Every check below answers a question that was worth asking out loud during that
iteration, and answers it with a count rather than an opinion:

  - Does the Legend still interact with enough of the deck to earn its slot?
  - Which cards satisfy more than one requirement at once?
  - Which cards interact with nothing else in the deck?
  - Are the engine's enablers at enough copies to be drawn?
  - The payoff has a condition; how many cards actually help meet it?

None of these are pass/fail. They are prompts for a decision, and each prints
the number it is based on so the reasoning can be checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .combos import RULES, find_combos, traits_of
from .copies import at_least_one, cards_seen_by_turn
from .decklist import Deck
from .model import Card

# A Legend interacting with fewer than this many copies is worth questioning.
LEGEND_RELEVANCE_FLOOR = 8

# Text that marks a conditional payoff — a card that does nothing until the
# rest of the deck sets something up.
CONDITION_PATTERNS = [
    r"if you've played",
    r"if you control \d+ or more",
    r"if you control (a|an|two|three) ",
    r"if you have \d+",
    r"while you (control|have)",
    r"if you paid",
    r"if you've spent",
    r"for each",
]


@dataclass
class Note:
    severity: str          # "flag" | "info"
    heading: str
    body: str
    number: str = ""

    def render(self) -> str:
        mark = "!" if self.severity == "flag" else "-"
        num = f"  ({self.number})" if self.number else ""
        return f"  {mark} {self.heading}{num}\n      {self.body}"


@dataclass
class Critique:
    notes: list[Note] = field(default_factory=list)

    @property
    def flags(self) -> list[Note]:
        return [n for n in self.notes if n.severity == "flag"]

    def render(self) -> str:
        L = [
            "DECK SELF-AUDIT — counts, not opinions. Each line is a question to",
            "answer, not a rule to obey. '!' means worth a decision this pass.",
            "",
        ]
        for n in self.notes:
            L.append(n.render())
        if not self.notes:
            L.append("  nothing to report")
        return "\n".join(L)


def _pays_for(legend: Card, card: Card) -> bool:
    """Does the Legend's ability plausibly apply to this card?

    Deliberately literal. A Legend that adds a rune "only to play gear" applies
    to gear WITH a Power cost and to nothing else — which is exactly the
    distinction that made a Legend look useful when it was not.
    """
    lt = (legend.text or "").lower()

    if "only to play gear" in lt or "use gear abilities" in lt:
        return card.is_a("Gear") and (card.power or 0) > 0
    if "only to play spells" in lt:
        return card.is_a("Spell") and (card.power or 0) > 0
    if "only during showdowns" in lt:
        low = (card.text or "").lower()
        return "[reaction]" in low or "[action]" in low
    if "spell that costs" in lt:
        m = re.search(r"costs? \{?(\d+)", lt)
        n = int(m.group(1)) if m else 5
        return card.is_a("Spell") and (card.energy or 0) >= n
    if "{mighty}" in lt or "[mighty]" in lt:
        return (card.might or 0) >= 5
    if "token unit" in lt or "unit token" in lt:
        return "token" in (card.text or "").lower()
    if "[temporary]" in lt:
        return "[temporary]" in (card.text or "").lower()
    if "when you empower" in lt:
        return "empower" in (card.text or "").lower()
    if "when you stun" in lt:
        return "[stun]" in (card.text or "").lower()
    if "when you play a card from anywhere other than your hand" in lt:
        low = (card.text or "").lower()
        return "[flow]" in low or "from your trash" in low or "[hidden]" in low
    if "when a buffed unit" in lt or "when you buff" in lt:
        return "buff" in (card.text or "").lower()
    if "your sand soldiers" in lt or "sand soldier" in lt:
        return "sand soldier" in (card.text or "").lower()
    if "when you play a unit, gear, or activated ability with energy cost" in lt:
        m = re.search(r"cost \{?(\d+)", lt)
        n = int(m.group(1)) if m else 7
        return (card.energy or 0) >= n
    return False


def legend_relevance(deck: Deck) -> Note:
    legend = deck.legend
    if legend is None:
        return Note("flag", "No Legend", "Nothing to audit.")

    hits = [(c, n) for c, n in deck.main_cards() if _pays_for(legend, c)]
    copies = sum(n for _, n in hits)

    if copies == 0:
        # Either the Legend is passive/always-on, or it is doing nothing.
        passive = not re.search(r"exhaust:|\{?\d+ energy\}?,", (legend.text or "").lower())
        if passive:
            return Note(
                "info", "Legend is passive",
                f"{legend.name} has no activated cost, so it applies on its own "
                f"terms rather than to specific cards. Judge it on whether its "
                f"effect matches the deck's plan, not on a card count.",
            )
        return Note(
            "flag", "Legend interacts with nothing",
            f"{legend.name} has an activated ability but no card in this deck "
            f"matches what it pays for. Either the deck drifted away from the "
            f"reason this Legend was chosen, or the wrong Legend is in the slot.",
            "0 of %d copies" % deck.main_count,
        )

    sev = "flag" if copies < LEGEND_RELEVANCE_FLOOR else "info"
    detail = ", ".join(f"{n}x {c.name}" for c, n in sorted(hits, key=lambda t: -t[1])[:6])
    body = f"Cards its ability can actually apply to: {detail}."
    if sev == "flag":
        body += (
            f" Below {LEGEND_RELEVANCE_FLOOR} copies, a Legend is usually a "
            f"leftover from an earlier version of the plan. Ask what it is still "
            f"buying, and what a different Legend would buy instead."
        )
    return Note(sev, "Legend relevance", body, f"{copies} of {deck.main_count} copies")


def multi_role_cards(deck: Deck) -> Note:
    """Cards that satisfy more than one requirement at once.

    Card efficiency of this kind is what turned a three-card combo turn into a
    one-card turn, and it is the thing most worth hunting for deliberately.
    """
    wins = []
    for c, n in deck.main_cards():
        reasons = []
        if len(c.all_types) > 1:
            reasons.append(f"counts as {' and '.join(c.all_types)}")
        low = (c.text or "").lower()
        if c.is_a("Spell") and re.search(r"(play a unit|plays? it)", low) and "token" not in low:
            reasons.append("a spell that also plays a unit")
        if re.search(r"draw \d", low) and (c.energy or 9) <= 2 and c.is_a("Unit"):
            reasons.append("a body that replaces itself")
        if reasons:
            wins.append(f"{n}x {c.name} ({'; '.join(reasons)})")
    if not wins:
        return Note(
            "info", "No multi-role cards",
            "Nothing here covers two requirements at once. If the deck has a "
            "payoff with multiple conditions, look for cards that satisfy more "
            "than one of them — that is where the tempo is.",
        )
    return Note("info", "Multi-role cards", "\n      ".join(wins), f"{len(wins)} found")


def orphans(deck: Deck) -> Note:
    """Cards with no detected interaction with anything else in the deck."""
    cards = [deck.card(n) for n in deck.main]
    findings = find_combos(cards, deck.legend, limit_per_rule=999)
    involved = {name for f in findings for name in f.cards}
    loners = sorted(
        f"{deck.main[c.name]}x {c.name}"
        for c in cards
        if c.name not in involved
    )
    if not loners:
        return Note("info", "No orphans", "Every card interacts with something else detected.")
    # Removal and card draw are supposed to work without help. Only flag when
    # the orphans are something else — a card included for synergy that has none.
    import re as _re
    standalone = _re.compile(
        r"kill|deal \d|-\d+ might|counter|\[stun\]|draw \d|look at the top", _re.I
    )
    synergy_orphans = [
        c for c in cards
        if c.name not in involved and not standalone.search(c.text or "")
    ]
    sev = "flag" if len(synergy_orphans) > len(cards) * 0.3 else "info"
    return Note(
        sev, "Orphan cards",
        "No detected interaction with the rest of the deck: "
        + ", ".join(loners)
        + ". Removal and card draw are supposed to stand alone; that part is "
        "fine. The ones worth questioning are those included for synergy that "
        "have none: "
        + (", ".join(c.name for c in synergy_orphans) or "none"),
        f"{len(loners)} of {len(cards)} distinct cards",
    )


def enabler_redundancy(deck: Deck) -> list[Note]:
    """Are the cards the engine depends on at enough copies to be drawn?"""
    cards = [deck.card(n) for n in deck.main]
    findings = find_combos(cards, deck.legend, limit_per_rule=999)
    counts: dict[str, int] = {}
    for f in findings:
        for name in f.cards:
            if name in deck.main:
                counts[name] = counts.get(name, 0) + 1

    notes = []
    hot = sorted(counts.items(), key=lambda kv: -kv[1])[:4]
    for name, links in hot:
        n = deck.main[name]
        seen = at_least_one(n, cards_seen_by_turn(5), deck.main_count)
        if n < 3:
            notes.append(Note(
                "flag", f"Key piece at {n} copies: {name}",
                f"It interacts with {links} other cards in this deck, which makes "
                f"it an engine piece, but you only see it {seen:.0%} of the time by "
                f"turn 5. Going to 3 raises that to "
                f"{at_least_one(3, cards_seen_by_turn(5), deck.main_count):.0%}. "
                f"If the deck wants this card, run it.",
                f"{seen:.0%} by T5",
            ))
    return notes


def payoff_conditions(deck: Deck) -> list[Note]:
    """For each conditional payoff, count what supports it."""
    notes = []
    for c, n in deck.main_cards():
        low = (c.text or "").lower()
        if not any(re.search(p, low) for p in CONDITION_PATTERNS):
            continue
        if (c.energy or 0) < 4:      # cheap conditionals are not the deck's plan
            continue

        support = 0
        if "non-token gear" in low or "gear" in low:
            support += sum(k for name, k in deck.main.items() if deck.card(name).is_a("Gear"))
        if "played a" in low and "spell" in low:
            support += sum(k for name, k in deck.main.items() if deck.card(name).is_a("Spell"))
        notes.append(Note(
            "info", f"Conditional payoff: {n}x {c.name}",
            f"'{c.text[:110]}...' — this does nothing until the condition is met. "
            f"State plainly which cards in the deck meet it and how many copies, "
            f"and whether that is enough to rely on.",
            f"{support} supporting copies" if support else "",
        ))
    return notes


def failure_point(deck: Deck) -> Note:
    """Name the single thing that, if it does not happen, the deck loses."""
    cards = [deck.card(n) for n in deck.main]
    interaction = sum(
        k for name, k in deck.main.items()
        if re.search(
            r"kill|deal \d|-\d+ might|counter (a|an|enemy)|\[stun\]|stun a|"
            r"return .{0,60}to (its|their) owners?'? hands?|move an enemy",
            (deck.card(name).text or "").lower(),
        )
    )
    return Note(
        "info", "Interaction density",
        f"{interaction} of {deck.main_count} copies can remove, shrink, bounce, "
        f"stun or counter something. If the deck's payoff requires winning a "
        f"combat or resolving a spell, this is the number that decides whether it "
        f"gets there. Compare it against what the plan needs.",
        f"{interaction}/{deck.main_count}",
    )


_ABILITY_RUNE = re.compile(r"\{(body|calm|chaos|fury|mind|order|any) rune\}")


def ability_rune_costs(deck: Deck) -> Note:
    """Runes demanded by ability costs, which the Power-pip metric cannot see.

    `analyze` counts Power costs only, because those are the printed cost of
    playing a card. Empower costs, Equip costs and activated abilities also
    demand runes, and a deck full of them is more colour-hungry than its pip
    count suggests.
    """
    tally: dict[str, int] = {}
    detail = []
    for c, n in deck.main_cards():
        found = _ABILITY_RUNE.findall((c.text or "").lower())
        if not found:
            continue
        # a card's Power cost is already counted by analyze; only ability text
        # inside [Empower]/[Equip]/activated costs shows up here
        for dom in found:
            tally[dom.capitalize()] = tally.get(dom.capitalize(), 0) + n
        detail.append(f"{n}x {c.name} ({', '.join(found)})")
    if not tally:
        return Note("info", "No ability rune costs", "Nothing demands runes outside its printed cost.")
    return Note(
        "info", "Ability rune costs (NOT counted in the pip metric)",
        "These runes are demanded by Empower / Equip / activated abilities, not by "
        "Power costs, so the pips-per-rune figure understates how colour-hungry "
        "this deck is: "
        + ", ".join(f"{k} {v}" for k, v in sorted(tally.items(), key=lambda kv: -kv[1]))
        + ". Sources: " + "; ".join(detail[:8]),
    )


# Runes available by turn with no ramp (315.3.b; +1 on the draw, 485.7/486.7),
# capped by the 12-card Rune Deck.
def runes_by_turn(turn: int, on_play: bool = True) -> int:
    return min(12, turn * 2 + (0 if on_play else 1))


def castable_turn(deck: Deck) -> Note:
    """When each cost bracket comes online, and whether the top end is reachable.

    Runes needed = max(energy, power), NOT energy + power. A rune has two
    independent abilities (164.2) and Recycle has no ready-state requirement
    (416), so one rune can be exhausted for Energy and then recycled for Power
    in the same turn. {2}{P1} is a 2-rune play. Power costs attrition (the rune
    leaves the pool until re-channelled), not a later cast turn.
    """
    brackets: dict[int, int] = {}
    for c, n in deck.main_cards():
        total = max(c.energy or 0, c.power or 0)
        brackets[total] = brackets.get(total, 0) + n

    lines = []
    for cost in sorted(brackets):
        turn = next((t for t in range(1, 8) if runes_by_turn(t) >= cost), None)
        when = f"turn {turn}" if turn else "NOT REACHABLE without ramp"
        lines.append(f"cost {cost} ({brackets[cost]} copies) -> {when} on the play")

    unreachable = sum(
        n for cost, n in brackets.items() if cost > 12
    )
    sev = "flag" if unreachable else "info"
    body = "\n      ".join(lines)
    if unreachable:
        body += (
            f"\n      {unreachable} copies cost more than the 12 runes you can "
            f"channel in a whole game. They need channel ramp or cost reduction, "
            f"and without it they are dead cards."
        )
    return Note(sev, "When each cost comes online (runes needed = max(energy, power))", body)


def critique(deck: Deck) -> Critique:
    notes: list[Note] = [
        legend_relevance(deck),
        multi_role_cards(deck),
        orphans(deck),
        failure_point(deck),
        castable_turn(deck),
        ability_rune_costs(deck),
    ]
    notes += enabler_redundancy(deck)
    notes += payoff_conditions(deck)
    return Critique(notes)
