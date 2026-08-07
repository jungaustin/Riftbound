"""Real decklists -> playable decks, with every approximation made visible.

The engine implements 17 spells and no unit text, so most real decks contain
cards it cannot fully play. There are three honest options and only one of them
is usable:

  drop them      the deck shrinks below 39 and stops being the same deck
  refuse         nothing is evaluable until the pool is complete
  **approximate** keep the size and shape, and report exactly what was faked

A deck is faked in **two different ways**, and conflating them is what made the
old coverage number wrong:

  substituted    the card is gone, replaced by a different card. Spells with no
                 DSL spec and all Gear -- the engine has nothing to resolve.
  approximated   the card is present with the right cost, domain and body, but
                 printed text or keywords the engine never reads. Every unit
                 with rules text is in here.

`coverage` counts only cards played **as printed**, so it now excludes the
second category. It previously did not: `v1_legal` accepted any card whose
keywords were in the v1 scope target and whose text ran under 90 characters,
which counted 317 of 327 unit slots as covered while executing none of their
text. Reported coverage fell from ~54% to the low 30s when this was fixed --
the decks did not get worse, the number got honest.

**A deck at 50% coverage is a proxy, not that deck**, and any evaluation of it
is a statement about the proxy. That caveat has to travel with the number,
which is why `DeckLoad` carries all three counts rather than a bare list of
card ids.
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
from rl.engine.effects import ABILITIES, SPECS  # noqa: E402

_DOMAIN_ID = {d.lower(): i for i, d in enumerate(DOMAINS)}


@dataclass
class DeckLoad:
    name: str
    main: list[int]                 # card ids, length = printed deck size
    runes: list[int]                # domain ids
    battlefields: list[int]         # card ids, in printed order
    coverage: float                 # fraction played as printed
    substituted: dict = field(default_factory=dict)   # printed name -> count
    # Kept in the deck, but with printed behaviour the engine ignores. This is
    # the category the old coverage number hid: the card is *there*, its cost
    # and body are right, and the text that makes it worth playing does
    # nothing. Tracked separately from `substituted` because the two fail
    # differently -- a substitution changes the deck, an approximation changes
    # the card.
    approximated: dict = field(default_factory=dict)   # printed name -> count
    missing: list[str] = field(default_factory=list)  # names not in the table

    def report(self) -> str:
        def top(d):
            return ", ".join(f"{n}x{c}" for n, c in
                             sorted(d.items(), key=lambda t: -t[1])[:4])
        return (f"{self.name}: {len(self.main)} cards, coverage "
                f"{self.coverage:.0%}"
                + (f", substituted {sum(self.substituted.values())} "
                   f"({top(self.substituted)})" if self.substituted else "")
                + (f", approximated {sum(self.approximated.values())} "
                   f"({top(self.approximated)})" if self.approximated else "")
                + (f", MISSING {self.missing}" if self.missing else ""))


def includable(table: CardTable, cid: int) -> bool:
    """Can this card sit in a deck without the engine choking on it?

    A **unit** always can. Every unit is a body with a cost, a domain and a
    Might, and the engine plays those correctly whether or not it executes the
    card's text -- so keeping Lillia as a vanilla 3-Might Calm body is strictly
    closer to the real deck than swapping her for a different 3-drop. Tokens
    are the exception: 185.3 makes them non-cards that only effects create.

    A **spell** cannot. Without a DSL spec there is nothing to resolve, so it
    has to be substituted. Gear likewise, until Gear exists at all.
    """
    if table.is_type(cid, "Unit"):
        return not table.is_token(cid)
    if table.is_type(cid, "Spell"):
        return table.names[cid] in SPECS
    return False


def plays_as_printed(table: CardTable, cid: int) -> bool:
    """Does the engine execute **everything** this card says?

    The honest coverage question, and it is stricter than `includable` by a
    long way. This used to be `table.v1_legal(cid)` -- keywords in the v1 scope
    target plus text under 90 characters -- which counted 317 of 327 unit slots
    as covered while ignoring their rules text entirely. "When you play me,
    draw 1." is 25 characters. So is most of what makes a unit worth playing.

    Two exact checks replace the length heuristic:

      residual_text    anything printed beyond keywords needs a DSL spec
      unread_keywords  a keyword nothing consults is not being played
    """
    if not includable(table, cid):
        return False
    if table.is_type(cid, "Spell"):
        return True                       # a spec transcribes the whole text
    if table.unread_keywords(cid):
        return False
    # Presence in ABILITIES means the same thing presence in SPECS does: the
    # card's whole text is transcribed. Cards with one implemented ability and
    # one unimplemented one (Scuttle Crab: an ETB draw and a Deathknell) are
    # deliberately absent, so this stays an allowlist rather than a guess.
    return not table.residual_text(cid) or table.names[cid] in ABILITIES


def _pool(table: CardTable) -> tuple[list[int], list[int]]:
    """Substitution pools -- what a missing card may be replaced *with*.

    Deliberately `plays_as_printed`, not `includable`: a substitute is already
    an approximation, and picking one whose own text is ignored would stack a
    second silent approximation on top of the first.
    """
    units = [c for c in range(table.n)
             if table.is_type(c, "Unit") and plays_as_printed(table, c)]
    spells = [c for c in range(table.n)
              if table.is_type(c, "Spell") and plays_as_printed(table, c)]
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
    approx: dict[str, int] = {}
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
        if includable(table, cid):
            # The card itself goes in either way; the only question is whether
            # it counts as covered.
            main.extend([cid] * count)
            if plays_as_printed(table, cid):
                as_printed += count
            else:
                approx[name] = approx.get(name, 0) + count
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
                    approximated=approx, missing=missing)


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
