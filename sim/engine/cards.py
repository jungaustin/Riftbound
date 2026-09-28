"""Card database: loading, normalization, cost and timing.

Canonical home for card lookup. `make_brief.py` imports from here rather than
re-deriving any of it, so a fix to name matching or icon expansion lands in one
place.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DOMAINS = ("Body", "Calm", "Chaos", "Fury", "Mind", "Order")

_ICON = re.compile(r":rb_([a-z0-9_]+):")
_PAREN = re.compile(r"\s*\(([^)]*)\)\s*$")
VARIANT_SUFFIXES = {
    "alternate art", "overnumbered", "signature", "metal",
    "starter", "launch exclusive", "gg ez", "ultimate",
}

# Play-timing tiers, nested: each grants everything above it (rules 155, 159.2,
# 308.1.a, 309.1.a). Ordered weakest to strongest.
PLAIN, ACTION, REACTION = "plain", "action", "reaction"


def _icon_sub(m: re.Match) -> str:
    key = m.group(1)
    if key in ("might", "exhaust"):
        return key.capitalize()
    if key == "rune_rainbow":
        return "{any rune}"
    if key.startswith("energy_"):
        return "{" + key.split("_", 1)[1] + " energy}"
    if key.startswith("rune_"):
        return "{" + key.split("_", 1)[1].capitalize() + " rune}"
    return "{" + key.replace("_", " ") + "}"


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", _ICON.sub(_icon_sub, html.unescape(text))).strip()


def canonical_name(name: str) -> str:
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


def loose_key(name: str) -> str:
    return "".join(c for c in canonical_name(name).lower() if c.isalnum())


@dataclass(frozen=True)
class Card:
    name: str
    type: str
    domains: tuple[str, ...]
    energy: int
    power: int
    might: int | None
    text: str
    timing: str
    tags: tuple[str, ...] = ()
    # 178.1 -- the FULL printed type line. `type` is only the first word of it,
    # and Patched Porobot ("Unit Gear") is both types for every rule that asks.
    types: tuple[str, ...] = ()

    @property
    def all_types(self) -> tuple[str, ...]:
        return self.types or (self.type,)

    @property
    def is_unit(self) -> bool:
        return self.type == "Unit"

    @property
    def is_spell(self) -> bool:
        return self.type == "Spell"

    @property
    def is_gear(self) -> bool:
        return self.type == "Gear"

    def cost_str(self) -> str:
        bits = []
        if self.energy:
            bits.append(f"{self.energy}E")
        if self.power:
            bits.append(f"{self.power}P")
        return "+".join(bits) or "0"

    def timing_label(self) -> str:
        return {PLAIN: "—", ACTION: "[Action]", REACTION: "[Reaction]"}[self.timing]


def _timing_of(text: str) -> str:
    # Reaction wins when both appear: it strictly supersets Action (159.2.b.1).
    if "[Reaction]" in text:
        return REACTION
    if "[Action]" in text:
        return ACTION
    return PLAIN


def _to_card(raw: dict) -> Card:
    text = raw.get("text") or ""
    return Card(
        name=canonical_name(raw["name"]),
        type=raw.get("type") or "?",
        domains=tuple(raw.get("domains") or ()),
        energy=raw.get("energy") or 0,
        power=raw.get("power") or 0,
        might=raw.get("might"),
        text=normalize_text(text),
        timing=_timing_of(text),
        tags=tuple(raw.get("tags") or ()),
        types=tuple(raw.get("types") or ()),
    )


@lru_cache(maxsize=1)
def card_index() -> dict[str, Card]:
    """Every card by loose name.

    **Gated on `riftbound.upcoming` like the other two corpus readers.** This
    one is easy to miss: `find()` below is what `rl/decks.py` resolves every
    decklist name through, so leaving it ungated would let a list naming an
    unreleased card resolve cleanly and only fail later, in `pool_table`, as a
    missing row. The errata overlay is deliberately NOT applied here -- this
    index predates it and `rl/engine/cardtable` stopped using it for exactly
    that reason -- so this adds the upcoming cards and nothing else.
    """
    import sys
    sys.path.insert(0, str(ROOT))
    from riftbound import upcoming
    data = json.loads((ROOT / "data" / "cards.json").read_text())
    index: dict[str, Card] = {}
    for raw in [*data["cards"], *upcoming.extra_cards()]:
        index.setdefault(loose_key(raw["name"]), _to_card(raw))
    return index


def find(name: str) -> Card | None:
    """Look up a card by name, tolerating a missing race/type prefix.

    Some printings carry one ("Yordle, Kennen - Heart of the Tempest") while
    decklists commonly omit it ("Kennen, Heart of the Tempest"). Falls back to a
    suffix match, but only when exactly one card matches — an ambiguous suffix
    returns None rather than guessing, so a wrong card can never silently enter
    a deck.
    """
    index = card_index()
    key = loose_key(name)
    exact = index.get(key)
    if exact is not None:
        return exact
    matches = [c for k, c in index.items() if k.endswith(key)]
    return matches[0] if len(matches) == 1 else None


class UnknownCard(KeyError):
    pass


def must_find(name: str) -> Card:
    card = find(name)
    if card is None:
        raise UnknownCard(name)
    return card
