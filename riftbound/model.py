"""Normalized card model shared by every stage of the pipeline."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field, asdict
from typing import Any

DOMAINS = ["Body", "Calm", "Chaos", "Fury", "Mind", "Order"]
COLORLESS = "Colorless"

# Printing variants that do not change the card for gameplay purposes. A name's
# trailing "(...)" is stripped only when it matches one of these, so a real card
# named "Something (Foo)" would survive intact.
VARIANT_SUFFIXES = {
    "alternate art",
    "overnumbered",
    "signature",
    "metal",
    "starter",
    "launch exclusive",
    "gg ez",
    "ultimate",
}

_PAREN = re.compile(r"\s*\(([^)]*)\)\s*$")

# Card text ships with icon placeholders. Left as-is they burn attention on
# markup the model has to decode; expanded they read as plain rules language.
_ICON = re.compile(r":rb_([a-z0-9_]+):")
_ICON_WORDS = {
    "might": "Might",
    "exhaust": "Exhaust",
    "rune_rainbow": "{any rune}",
}


def _icon_sub(m: re.Match) -> str:
    key = m.group(1)
    if key in _ICON_WORDS:
        return _ICON_WORDS[key]
    if key.startswith("energy_"):
        return "{" + key.split("_", 1)[1] + " energy}"
    if key.startswith("rune_"):
        return "{" + key.split("_", 1)[1].capitalize() + " rune}"
    return "{" + key.replace("_", " ") + "}"


def normalize_text(text: str) -> str:
    """Expand icon placeholders and collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"[ \t]+", " ", _ICON.sub(_icon_sub, html.unescape(text))).strip()


def loose_key(name: str) -> str:
    """Collapse spelling variants to one key.

    Vendetta reprints render champion names with a comma where earlier sets
    used a hyphen ("Lux, Crownguard" vs "Lux - Crownguard"). Those are the
    same card, and treating them as two would let a deck run six copies.
    """
    return "".join(ch for ch in canonical_name(name).lower() if ch.isalnum())


def canonical_name(name: str) -> str:
    """Strip printing-variant suffixes so all printings collapse to one card.

    >>> canonical_name("Poppy - Paragon (Alternate Art)")
    'Poppy - Paragon'
    """
    out = name.strip()
    while True:
        m = _PAREN.search(out)
        if not m:
            return out
        inner = m.group(1).strip().lower()
        if inner in VARIANT_SUFFIXES or inner.isdigit():
            out = out[: m.start()].strip()
        else:
            return out


@dataclass
class Card:
    id: str
    name: str
    riftbound_id: str
    set_id: str
    collector_number: int | None
    type: str                       # primary printed type (first on the type line)
    supertype: str | None
    rarity: str | None
    domains: list[str]
    energy: int | None
    power: int | None
    might: int | None
    tags: list[str]
    text: str
    flavour: str | None = None
    image_url: str | None = None
    printings: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    # Full printed type line. Riftbound has dual-type cards (Patched Porobot
    # is 'Unit Gear'), and the API's classification.type reports only the
    # first, so this is recovered from the card's accessibility text.
    types: list[str] = field(default_factory=list)

    @property
    def all_types(self) -> list[str]:
        return self.types or [self.type]

    def is_a(self, t: str) -> bool:
        """True if `t` appears anywhere on the printed type line.

        Use this instead of `card.type == "Gear"` — a dual-type card satisfies
        both, and every 'count your gear' effect cares.
        """
        return t in self.all_types

    @property
    def type_line(self) -> str:
        return " ".join(self.all_types)

    # -- gameplay predicates, keyed off printed supertype rather than the
    # -- API's metadata.signature flag, which marks printing variants.
    @property
    def is_signature(self) -> bool:
        return self.supertype == "Signature"

    @property
    def is_champion_unit(self) -> bool:
        return self.is_a("Unit") and self.supertype == "Champion"

    @property
    def is_legend(self) -> bool:
        return self.is_a("Legend")

    @property
    def is_token(self) -> bool:
        return self.supertype == "Token"

    @property
    def is_basic_rune(self) -> bool:
        return self.is_a("Rune")

    @property
    def domain_set(self) -> set[str]:
        return {d for d in self.domains if d != COLORLESS}

    def legal_under(self, identity: set[str]) -> bool:
        """Rule 103.1.b.4: every printed domain must appear in the identity."""
        return self.domain_set <= identity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Card":
        return cls(**d)

    def compact(self, with_flavour: bool = False) -> str:
        """One dense line. This is the format the model actually reads."""
        stats = []
        if self.energy is not None:
            stats.append(f"E{self.energy}")
        if self.power is not None:
            stats.append(f"P{self.power}")
        if self.might is not None:
            stats.append(f"M{self.might}")
        bits = [
            self.name,
            self.type_line + (f"/{self.supertype}" if self.supertype else ""),
            "+".join(self.domains) or "-",
            " ".join(stats) or "-",
            ",".join(self.tags) or "-",
            (self.text or "").replace("\n", " ") or "-",
        ]
        if with_flavour and self.flavour:
            bits.append(f'"{self.flavour}"')
        return " | ".join(bits)


def render_pool(cards: list[Card], header: str = "") -> str:
    lines = [
        "# name | type | domains | stats | tags | text",
        "# stats: E=energy cost, P=power(rune) cost, M=might",
    ]
    if header:
        lines.insert(0, header)
    lines += [c.compact() for c in cards]
    return "\n".join(lines)


# 133.8.b: "Tags used to link Legends, Champion Units, and Signature cards are
# known as Champion Tags." A species or faction tag is NOT a Champion Tag even
# when a Legend prints it, so it can never satisfy 103.2.a.2 (Chosen Champion)
# or 103.2.d.2 (Signature cards).
#
# Derived from the card pool rather than guessed: a genuine Champion Tag never
# co-occurs with two or more OTHER legend tags on a champion unit. Exactly one
# tag fails that test -- Yordle, which sits on 35 cards and co-occurs with
# Kennen, Poppy, Rumble, Teemo and Vex. Only one Legend of 49 prints it
# (Yordle, Kennen - Heart of the Tempest), which is why the bug hid for so long.
#
# Re-derive after any new set: python3 riftbound/tools/derive_champion_tags.py
NON_CHAMPION_TAGS = frozenset({"Yordle"})


def champion_tags(tags) -> set[str]:
    """The Champion Tags among `tags` (133.8.b)."""
    return set(tags or ()) - NON_CHAMPION_TAGS
