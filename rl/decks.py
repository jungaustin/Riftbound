"""Real decklists -> playable decks, with the substitutions made visible.

The engine implements 14 spells and vanilla units, so most real decks contain
cards it cannot play. There are three honest options and only one of them is
usable:

  drop them      the deck shrinks below 39 and stops being the same deck
  refuse         nothing is evaluable until the pool is complete
  **substitute** keep the size and shape, and report exactly what was faked

This module substitutes, and every result it produces carries its own
`coverage` number. **A deck at 50% coverage is a proxy, not that deck**, and any
evaluation of it is a statement about the proxy. That caveat has to travel with
the number, which is why `DeckLoad` is a dataclass carrying both rather than a
bare list of card ids.

Substitution picks the closest implemented card of the same type by cost, so the
curve and the unit/spell balance survive even when the specific effects do not.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sim"))
from engine.cards import find  # noqa: E402

from rl.config import DOMAINS  # noqa: E402
from rl.engine.cardtable import CardTable, read_decklist  # noqa: E402
from rl.engine.effects import SPECS  # noqa: E402

_DOMAIN_ID = {d.lower(): i for i, d in enumerate(DOMAINS)}


@dataclass
class DeckLoad:
    name: str
    main: list[int]                 # card ids, length = printed deck size
    runes: list[int]                # domain ids
    battlefields: list[int]         # card ids, in printed order
    coverage: float                 # fraction played as printed
    substituted: dict = field(default_factory=dict)   # printed name -> count
    missing: list[str] = field(default_factory=list)  # names not in the table

    def report(self) -> str:
        top = sorted(self.substituted.items(), key=lambda t: -t[1])[:4]
        return (f"{self.name}: {len(self.main)} cards, coverage "
                f"{self.coverage:.0%}"
                + (f", substituted {sum(self.substituted.values())} "
                   f"({', '.join(f'{n}x{c}' for n, c in top)})"
                   if self.substituted else "")
                + (f", MISSING {self.missing}" if self.missing else ""))


def playable(table: CardTable, cid: int) -> bool:
    """Can the engine actually play this card as printed?"""
    if table.is_type(cid, "Unit"):
        return bool(table.v1_legal(cid)) and not table.is_token(cid)
    return table.names[cid] in SPECS


def _pool(table: CardTable) -> tuple[list[int], list[int]]:
    units = [c for c in range(table.n)
             if table.is_type(c, "Unit") and playable(table, c)]
    spells = [c for c in range(table.n)
              if table.is_type(c, "Spell") and playable(table, c)]
    return units, spells


def _closest(table: CardTable, pool: list[int], want: int) -> int:
    """Nearest implemented card by domain first, then cost.

    Domain leads because the rune deck is what gives a deck its identity: an
    off-colour substitute is often uncastable and dilutes exactly the archetype
    signal the substitution is supposed to preserve. Cost breaks ties so the
    curve still survives.
    """
    e, p = int(table.energy[want]), int(table.power[want])
    mask = int(table.domain_mask[want])
    return min(pool, key=lambda c: (
        0 if (int(table.domain_mask[c]) & mask) else 1,      # shares a domain
        abs(int(table.energy[c]) - e) + abs(int(table.power[c]) - p),
        int(table.energy[c]), c))


def load_deck(path: Path, table: CardTable) -> DeckLoad:
    """Read a decklist and make it playable, recording every substitution."""
    parsed = read_decklist(Path(path))
    units, spells = _pool(table)

    main: list[int] = []
    subs: dict[str, int] = {}
    missing: list[str] = []
    as_printed = 0

    for count, name in parsed.get("MainDeck", []):
        card = find(name)
        cid = table._index.get(card.name) if card else None
        if cid is None:
            missing.append(name)
            main.extend([_closest(table, units, units[0])] * count)
            subs[name] = subs.get(name, 0) + count
            continue
        if playable(table, cid):
            main.extend([cid] * count)
            as_printed += count
            continue
        pool = spells if table.is_type(cid, "Spell") else units
        # Gear has no implementation at all yet, so it becomes a unit -- the
        # least wrong option, and counted as a substitution either way.
        main.extend([_closest(table, pool or units, cid)] * count)
        subs[name] = subs.get(name, 0) + count

    runes: list[int] = []
    for count, name in parsed.get("Runes", []):
        dom = name.lower().replace(" rune", "").strip()
        if dom in _DOMAIN_ID:
            runes.extend([_DOMAIN_ID[dom]] * count)
    if not runes:
        runes = [0] * 12

    bfs: list[int] = []
    for count, name in parsed.get("Battlefields", []):
        card = find(name)
        cid = table._index.get(card.name) if card else None
        if cid is not None:
            bfs.extend([cid] * count)

    total = len(main) or 1
    return DeckLoad(name=Path(path).parent.name + "/" + Path(path).stem,
                    main=main, runes=runes, battlefields=bfs,
                    coverage=as_printed / total, substituted=subs,
                    missing=missing)


def load_all(table: CardTable, root: Path | None = None) -> list[DeckLoad]:
    root = root or (ROOT / "decks")
    out = []
    for f in sorted(Path(root).rglob("*.txt")):
        d = load_deck(f, table)
        if len(d.main) >= 10:
            out.append(d)
    return out


def matchup(a: DeckLoad, b: DeckLoad, rune_size: int = 12,
            n_bf: int = 2) -> tuple[list, list, list]:
    """Two DeckLoads as `game.new_game` arguments.

    Each player brings battlefields and one goes into play (486.5); with N_BF=2
    that is one from each deck. A deck missing battlefield entries falls back to
    the other's, so a partial list never blocks a matchup.
    """
    decks = [list(a.main), list(b.main)]
    runes = [(a.runes * 3)[:rune_size], (b.runes * 3)[:rune_size]]
    pool = (a.battlefields or b.battlefields)
    other = (b.battlefields or a.battlefields)
    bfs = [pool[0], (other[1] if len(other) > 1 else other[0])][:n_bf]
    return decks, runes, bfs
