"""Parse, hydrate, and serialize decklists.

Accepts the loose text people actually paste. Sections are optional: card types
come from the database, so `3x Jinx - Loose Cannon` lands in the main deck and
`6x Fury Rune` lands in the rune deck without being told.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .db import AmbiguousCard, CardDB, CardNotFound
from .model import Card

_COUNT = re.compile(r"^\s*(?:(\d+)\s*[xX]?\s+|\s*)(.+?)\s*$")
_SECTION = re.compile(
    r"^\s*(legend|champion|chosen champion|main ?deck|main|deck|rune ?deck|runes?|"
    r"battlefields?|side ?board|sb|rune ?pool)\s*[:\-]?\s*(\d+)?\s*$",
    re.I,
)
_COMMENT = re.compile(r"^\s*(#|//)")


@dataclass
class Deck:
    name: str = "Untitled"
    legend: Card | None = None
    champion: Card | None = None
    main: Counter = field(default_factory=Counter)  # Card.name -> count
    runes: Counter = field(default_factory=Counter)
    battlefields: Counter = field(default_factory=Counter)
    # Sideboards are excluded from every legality count, but kept: they are
    # the clearest statement of what a pilot expects to face.
    sideboard: Counter = field(default_factory=Counter)
    _index: dict[str, Card] = field(default_factory=dict)

    def card(self, name: str) -> Card:
        return self._index[name]

    def main_cards(self) -> list[tuple[Card, int]]:
        return [(self._index[n], c) for n, c in self.main.most_common()]

    @property
    def main_count(self) -> int:
        """Main-deck size. The Chosen Champion is part of the 40 (rule 103.2)."""
        return sum(self.main.values())

    @property
    def rune_count(self) -> int:
        return sum(self.runes.values())

    @property
    def battlefield_count(self) -> int:
        return sum(self.battlefields.values())

    @property
    def sideboard_count(self) -> int:
        return sum(self.sideboard.values())

    @property
    def identity(self) -> set[str]:
        return self.legend.domain_set if self.legend else set()

    def to_text(self) -> str:
        out = [f"# {self.name}"]
        if self.legend:
            out.append(f"Legend:\n1 {self.legend.name}")
        if self.champion:
            out.append(f"\nChampion:\n1 {self.champion.name}")
        out.append("\nMainDeck:")
        for c, n in sorted(
            self.main_cards(), key=lambda t: (t[0].type, t[0].energy or 0, t[0].name)
        ):
            # The Chosen Champion's zone copy is declared under Champion:, so
            # only surplus main-deck copies are listed here.
            if self.champion and c.name == self.champion.name:
                if n > 1:
                    out.append(f"{n - 1} {c.name}")
                continue
            out.append(f"{n} {c.name}")
        out.append("\nBattlefields:")
        for n, c in self.battlefields.most_common():
            out.append(f"{c} {n}")
        out.append("\nRune Pool:")
        for n, c in self.runes.most_common():
            out.append(f"{c} {n}")
        if self.sideboard:
            out.append("\nSideboard:")
            for n, c in self.sideboard.most_common():
                out.append(f"{c} {n}")
        return "\n".join(out)


class DecklistError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Could not resolve decklist:\n  - " + "\n  - ".join(problems))


def parse(text: str, db: CardDB, name: str = "Untitled") -> Deck:
    deck = Deck(name=name)
    problems: list[str] = []
    section: str | None = None

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or _COMMENT.match(line):
            if line.startswith("#") and deck.name == "Untitled" and lineno == 1:
                deck.name = line.lstrip("#").strip() or "Untitled"
            continue

        sec = _SECTION.match(line)
        if sec:
            section = sec.group(1).lower()
            continue

        # "Legend: Foo" / "Champion: Bar" inline form
        if ":" in line:
            head, _, tail = line.partition(":")
            key = head.strip().lower()
            if key in ("legend", "champion", "chosen champion") and tail.strip():
                try:
                    card = db.get(tail.strip())
                except (CardNotFound, AmbiguousCard) as e:
                    problems.append(f"line {lineno}: {e}")
                    continue
                _assign_singleton(deck, key, card, lineno, problems)
                # Rule 103.2: the Chosen Champion is one of the 40. It is
                # declared outside the main block, so it has to be added here
                # or every deck using the inline form comes up one card short.
                if key in ("champion", "chosen champion") and deck.champion is card:
                    deck.main[card.name] += 1
                continue

        m = _COUNT.match(line)
        if not m:
            problems.append(f"line {lineno}: cannot parse {raw!r}")
            continue
        count = int(m.group(1)) if m.group(1) else 1
        cardname = m.group(2)

        try:
            card = db.get(cardname)
        except (CardNotFound, AmbiguousCard) as e:
            problems.append(f"line {lineno}: {e}")
            continue

        deck._index[card.name] = card

        if section in ("legend",) or card.is_legend:
            _assign_singleton(deck, "legend", card, lineno, problems)
        elif section in ("champion", "chosen champion") and deck.champion is None:
            _assign_singleton(deck, "champion", card, lineno, problems)
            deck.main[card.name] += count
        elif section in ("sideboard", "side board", "sb"):
            deck.sideboard[card.name] += count
        elif card.is_basic_rune or section in ("rune deck", "runedeck", "rune", "runes",
                                       "rune pool", "runepool"):
            deck.runes[card.name] += count
        elif card.is_a("Battlefield") or section in ("battlefield", "battlefields"):
            deck.battlefields[card.name] += count
        else:
            deck.main[card.name] += count

    if problems:
        raise DecklistError(problems)

    # If no Champion was declared, infer it: the champion unit matching the
    # Legend's tag. Only unambiguous cases are inferred.
    if deck.champion is None and deck.legend is not None:
        tags = set(deck.legend.tags)
        cands = [
            deck._index[n]
            for n in deck.main
            if deck._index[n].is_champion_unit and tags & set(deck._index[n].tags)
        ]
        if len(cands) == 1:
            deck.champion = cands[0]

    return deck


def _assign_singleton(deck: Deck, key: str, card: Card, lineno: int, problems: list[str]):
    field_name = "legend" if key == "legend" else "champion"
    existing = getattr(deck, field_name)
    if existing is not None and existing.name != card.name:
        problems.append(
            f"line {lineno}: two {field_name}s declared "
            f"({existing.name} and {card.name})"
        )
        return
    deck._index[card.name] = card
    setattr(deck, field_name, card)
