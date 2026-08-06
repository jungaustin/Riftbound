"""Decklist parsing.

Canonical home — `make_brief.py` and `normalize_decks.py` both import from here.

All decklists in this repo were normalized to one format by
`sim/normalize_decks.py`, but the parser still accepts the older imported
dialect ("Legend:" on its own line, "3 Name" without the x) so a freshly pasted
netdeck works without a manual conversion step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS = [("main", "Main Deck:"), ("battlefields", "Battlefields:"),
            ("runes", "Runes:"), ("sideboard", "Sideboard:")]

_HEADERS = [
    ("maindeck", "main"), ("main deck", "main"),
    ("battlefield", "battlefields"), ("rune", "runes"),
    ("sideboard", "sideboard"), ("legend", "legend"), ("champion", "champion"),
]


@dataclass
class Decklist:
    name: str
    legend: str | None = None
    champion: str | None = None
    main: list[tuple[int, str]] = field(default_factory=list)
    battlefields: list[tuple[int, str]] = field(default_factory=list)
    runes: list[tuple[int, str]] = field(default_factory=list)
    sideboard: list[tuple[int, str]] = field(default_factory=list)

    def section(self, key: str) -> list[tuple[int, str]]:
        return getattr(self, key)

    def total(self, key: str) -> int:
        return sum(c for c, _ in self.section(key))

    def expand(self, key: str) -> list[str]:
        return [name for count, name in self.section(key) for _ in range(count)]

    def comparable(self) -> dict:
        return {"legend": self.legend, "champion": self.champion,
                **{k: sorted(self.section(k)) for k, _ in SECTIONS}}


def parse_deck(path: Path) -> Decklist:
    deck = Decklist(name=f"{path.parent.name}/{path.stem}")
    section: str | None = None
    pending: str | None = None

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            head, _, rest = line.partition(":")
            key = head.strip().lower()
            match = next((t for pre, t in _HEADERS if key.startswith(pre)), None)
            if match:
                rest = rest.strip()
                if match in ("legend", "champion"):
                    if rest:
                        setattr(deck, match, re.sub(r"^\d+\s*[xX]?\s+", "", rest))
                        pending = None
                    else:
                        pending = match
                else:
                    section, pending = match, None
                continue

        m = re.match(r"^(\d+)\s*[xX]?\s+(.+)$", line)
        if not m:
            continue
        count, name = int(m.group(1)), m.group(2).strip()
        if pending:
            setattr(deck, pending, name)
            pending = None
        elif section:
            deck.section(section).append((count, name))

    # A name listed twice means the sum, not two separate entries.
    for key, _ in SECTIONS:
        merged: dict[str, int] = {}
        for count, name in deck.section(key):
            merged[name] = merged.get(name, 0) + count
        setattr(deck, key, [(c, n) for n, c in merged.items()])
    return deck
