"""Frozen, compiled card table -- the engine's only view of card data.

The deck builder's `sim/engine/cards.py` does name normalization, icon expansion
and fuzzy lookup. That work is real and is not duplicated here: this module
imports it, runs it ONCE at startup, and freezes the result into parallel numpy
arrays. Nothing in the hot loop ever touches a `Card` object, a string, or a
dict.

This is the "Rust-shaped Python" rule from PLAN.md §1.8. Cards are `u16` indices
into these arrays. Porting this file to Rust later should be a transliteration,
not a redesign -- so: fixed-width columns, integer ids, no per-call allocation.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sim"))

from engine.cards import Card, card_index, find  # noqa: E402  (path set above)

sys.path.insert(0, str(ROOT))
from rl.config import (ALL_KEYWORDS, CARD_TYPES, DOMAINS,  # noqa: E402
                       ENGINE_KEYWORDS, TIER1_KEYWORDS)

def _raw_cards() -> list[dict]:
    """Every raw card dict: `cards.json` plus the rulebook token supplement.

    `data/tokens.json` holds the tokens rule 187 defines that the card export
    omits -- it ships only the Recruit and Sprite printings, while cards in the
    corpus create Gold, Bird, Mech, Sand Soldier and Reflection tokens. They
    are a separate file so `cards.json` can be regenerated upstream without
    losing them, and because they are transcribed from the rules rather than
    exported from anywhere.
    """
    import json
    out = list(json.loads((ROOT / "data" / "cards.json").read_text())["cards"])
    extra = ROOT / "data" / "tokens.json"
    if extra.exists():
        have = {c["name"] for c in out}
        for raw in json.loads(extra.read_text())["cards"]:
            if raw["name"] not in have:
                out.append(raw)
    return out


def _token_names() -> set[str]:
    """Names of Token cards.

    `sim/engine/cards.Card` does not carry `supertype`, and tokens matter to the
    engine: 185.3 says a token leaving the board ceases to exist rather than
    going to a hand or trash, so a bounce spell must not put one in hand.
    """
    return {c["name"] for c in _raw_cards()
            if (c.get("supertype") or "").lower() == "token"}


_TOKEN_NAMES = None

_BRACKET = re.compile(r"\[([A-Za-z ]+)\]")
_REMINDER = re.compile(r"\([^)]*\)")

_KW_BIT = {kw: i for i, kw in enumerate(ALL_KEYWORDS)}
_TYPE_ID = {t: i for i, t in enumerate(CARD_TYPES)}
_DOMAIN_BIT = {d: i for i, d in enumerate(DOMAINS)}

TIER1_MASK = 0
for _kw in TIER1_KEYWORDS:
    TIER1_MASK |= 1 << _KW_BIT[_kw]

# Text longer than this, after stripping reminder text, is a card whose rules
# text almost certainly needs more than keywords + a few DSL primitives.
COMPLEX_TEXT_CHARS = 90


# A bracketed token, optionally with a numeric value: [Assault 2], [Shield 3].
_KW_TOKEN = re.compile(r"\[([A-Za-z][A-Za-z ]*?)\s*\d*\]")
# Things that may sit between owned keywords in the leading run without ending
# it: whitespace, an em dash, a cost like {1 energy}, an ability marker [>].
_KW_FILLER = re.compile(r"\s+|[—-]|\{[^}]*\}|\[>+\]")


def keyword_mask(text: str) -> int:
    """Bitmask of the keywords a card actually **has**.

    Not "keywords appearing in the text", which is what this used to be and is
    a different set. Card text mentions keywords it does not have, constantly:

        Petal Pixie   "I have +1 Might for each of your units with [Temporary]
                       at my battlefield."
        Fading Memories  "Give a unit at a battlefield or a gear [Temporary]."
        Block         "Give a unit [Shield 3] and [Tank] this turn."

    Petal Pixie was therefore flagged `[Temporary]` and would have been killed
    at the start of every Beginning Phase -- a 32-slot card in the corpus,
    silently unplayable. The old version also scanned reminder text, so
    [Ambush]'s own reminder ("You may play me as a [Reaction]...") granted
    Reaction to every Ambush card.

    Two signals separate having from mentioning, and a keyword needs either:

      1. It is in the **leading run** of bracketed tokens, before any prose.
         This is how nearly every card prints its keywords.
      2. It is **immediately followed by its reminder text** -- `[Ganking] (I
         can move from battlefield to battlefield.)` on Atakhan, whose
         keywords come after a sentence of additional cost. Immediately
         matters: "give it [Temporary]. (Kill it at...)" has a sentence break
         first and is a grant, not a possession.

    Conservative by construction. A keyword this misses is treated as not
    implemented, which understates coverage; a keyword it wrongly grants
    changes how the engine plays the card.
    """
    raw = text or ""
    mask = 0

    # (1) the leading run, scanned on text with reminders stripped.
    t = body_text(raw)
    i = 0
    while i < len(t):
        m = _KW_FILLER.match(t, i)
        if m and m.end() > i:
            i = m.end()
            continue
        m = _KW_TOKEN.match(t, i)
        if not m:
            break
        bit = _KW_BIT.get(m.group(1))
        if bit is not None:
            mask |= 1 << bit
        i = m.end()

    # (2) anywhere, if its own reminder text follows immediately.
    for m in _KW_TOKEN.finditer(raw):
        if raw[m.end():m.end() + 2].lstrip().startswith("("):
            bit = _KW_BIT.get(m.group(1))
            if bit is not None:
                mask |= 1 << bit
    return mask


def keyword_value(text: str, keyword: str) -> int:
    """The X in "[Shield 3]", or 1 when the card has it bare, or 0 if absent.

    814.1.b.3 / 807.1.b.3: "if X is omitted, it is presumed to be 1." Only
    counts keywords the card actually HAS -- `keyword_mask` decides that, so a
    spell that GRANTS "[Shield 3] this turn" does not gain Shield itself.
    """
    bit = _KW_BIT.get(keyword)
    if bit is None or not (keyword_mask(text) >> bit & 1):
        return 0
    m = re.search(rf"\[{keyword}\s*(\d*)\]", text or "")
    return int(m.group(1)) if (m and m.group(1)) else 1


def body_text(text: str) -> str:
    """Rules text with reminder text stripped -- the part we must implement."""
    return _REMINDER.sub("", text or "").strip()


@dataclass(frozen=True)
class CardTable:
    """Parallel arrays, indexed by card id. Immutable after construction."""

    names: tuple[str, ...]
    # Printed rules text, kept for the coverage metric only. Strings never
    # enter the hot loop -- this is read at deck-load and analysis time, the
    # same as `names`.
    raw_text: tuple[str, ...]
    energy: np.ndarray        # int16
    power: np.ndarray         # int16
    might: np.ndarray         # int16, -1 for non-units
    type_id: np.ndarray       # int8, index into CARD_TYPES
    domain_mask: np.ndarray   # uint8, bit per DOMAINS
    kw_mask: np.ndarray       # uint32, bit per ALL_KEYWORDS
    # Keyword VALUES. [Shield 3] and [Assault 2] carry a number the bitmask
    # cannot hold, and "if X is omitted, it is presumed to be 1" (814.1.b.3,
    # 807.1.b.3). Dense int16 columns rather than a dict because `might` reads
    # them on every call.
    shield: np.ndarray        # int16, 0 = no [Shield]
    assault: np.ndarray       # int16, 0 = no [Assault]
    text_len: np.ndarray      # int16, reminder text stripped
    token: np.ndarray         # bool, supertype == Token (185.3)

    @property
    def n(self) -> int:
        return len(self.names)

    def id_of(self, name: str) -> int:
        return self._index[name]

    def has(self, cid: int, keyword: str) -> bool:
        return bool(self.kw_mask[cid] >> _KW_BIT[keyword] & 1)

    def is_type(self, cid: int, type_name: str) -> np.ndarray | bool:
        return self.type_id[cid] == _TYPE_ID[type_name]

    def is_token(self, cid: int) -> bool:
        """185.3 -- a token that leaves the board ceases to exist rather than
        moving to a hand, deck or trash."""
        return bool(self.token[cid])

    def in_v1_scope(self, cid: int) -> bool:
        """Every keyword is in the v1 scope target and the text is short.

        **This is a scope filter, not a completeness claim.** It was called
        `v1_legal`, which read as "the engine plays this card correctly", and
        `decks.py` believed it: 317 of 327 unit slots counted as covered turned
        out to have rules text nothing executes, because 90 characters is
        plenty of room for "When you play me, draw 1." Use `residual_text` and
        `plays_as_printed` for the honest question. This one only selects
        cheap vanilla bodies for the v0 pool.
        """
        extra = int(self.kw_mask[cid]) & ~TIER1_MASK
        return extra == 0 and int(self.text_len[cid]) <= COMPLEX_TEXT_CHARS

    def residual_text(self, cid: int) -> str:
        """What the card says once reminder text and keywords are removed.

        Non-empty means there is printed behaviour beyond the keyword flags,
        and therefore something the DSL has to express. Exact, where a text
        length threshold is a guess.
        """
        return _BRACKET.sub("", body_text(self.raw_text[cid])).strip(" .—-\n\t")

    def unread_keywords(self, cid: int) -> list[str]:
        """Keywords on this card that the engine never consults."""
        return [k for k in ALL_KEYWORDS
                if (int(self.kw_mask[cid]) >> _KW_BIT[k] & 1)
                and k not in ENGINE_KEYWORDS]

    def features(self) -> np.ndarray:
        """[n, D] float32 attribute matrix for the network's card embeddings.

        Attributes, never one-hot card ids -- so an unseen card gets a sensible
        embedding instead of an untrained row (brief §5, PLAN.md §5.2).
        """
        n = self.n
        cols = [
            self.energy.astype(np.float32) / 5.0,
            self.power.astype(np.float32) / 3.0,
            np.maximum(self.might, 0).astype(np.float32) / 5.0,
            (self.might >= 0).astype(np.float32),          # is a unit at all
            # 185.3 -- a token that leaves the board ceases to exist. Bouncing
            # one destroys it outright rather than being tempo, and it never
            # returns to a hand or deck, so "is this a token" changes what a
            # board unit is worth. Tokens are never in a decklist, so this is
            # the only way the policy can know.
            self.token.astype(np.float32),
        ]
        onehot_type = np.zeros((n, len(CARD_TYPES)), np.float32)
        onehot_type[np.arange(n), self.type_id] = 1.0
        dom = ((self.domain_mask[:, None] >> np.arange(len(DOMAINS))) & 1)
        kw = ((self.kw_mask[:, None] >> np.arange(len(ALL_KEYWORDS))) & 1)
        return np.concatenate(
            [np.stack(cols, 1), onehot_type, dom.astype(np.float32),
             kw.astype(np.float32)], axis=1)

    def __post_init__(self):
        object.__setattr__(self, "_index", {n: i for i, n in enumerate(self.names)})


def _rows(cards: list[Card]) -> CardTable:
    global _TOKEN_NAMES
    if _TOKEN_NAMES is None:
        _TOKEN_NAMES = _token_names()
    _tokens = _TOKEN_NAMES
    n = len(cards)
    tbl = CardTable(
        names=tuple(c.name for c in cards),
        raw_text=tuple(c.text or "" for c in cards),
        energy=np.array([c.energy for c in cards], np.int16),
        power=np.array([c.power for c in cards], np.int16),
        might=np.array([c.might if c.might is not None else -1 for c in cards], np.int16),
        type_id=np.array([_TYPE_ID.get(c.type, 0) for c in cards], np.int8),
        domain_mask=np.array(
            [sum(1 << _DOMAIN_BIT[d] for d in c.domains if d in _DOMAIN_BIT)
             for c in cards], np.uint8),
        kw_mask=np.array([keyword_mask(c.text) for c in cards], np.uint32),
        shield=np.array([keyword_value(c.text, "Shield") for c in cards], np.int16),
        assault=np.array([keyword_value(c.text, "Assault") for c in cards], np.int16),
        text_len=np.array([len(body_text(c.text)) for c in cards], np.int16),
        token=np.array([c.name in _tokens for c in cards], bool),
    )
    assert tbl.n == n
    return tbl


def full_table() -> CardTable:
    """Every card in `data/cards.json` plus the rulebook tokens, compiled."""
    from engine.cards import _to_card
    cards = dict(card_index())
    for raw in _raw_cards():
        if raw["name"] not in {c.name for c in cards.values()}:
            cards[raw["name"]] = _to_card(raw)
    return _rows(sorted(cards.values(), key=lambda c: c.name))


def pool_table(names: list[str]) -> tuple[CardTable, list[str]]:
    """Compile a restricted pool. Returns (table, unresolved names).

    Unresolved names are returned rather than raised so a deck can be inspected
    before it is required to be complete.
    """
    cards, missing = [], []
    for nm in names:
        c = find(nm)
        (cards.append(c) if c is not None else missing.append(nm))
    seen, uniq = set(), []
    for c in cards:
        if c.name not in seen:
            seen.add(c.name)
            uniq.append(c)
    return _rows(sorted(uniq, key=lambda c: c.name)), missing


# ---------------------------------------------------------------------------
# Decklist reading -- both formats present in decks/ ("2x Name" and "2 Name")
# ---------------------------------------------------------------------------
_DECK_LINE = re.compile(r"^\s*(\d+)\s*x?\s+(.+?)\s*$")
_SECTION = re.compile(r"^\s*([A-Za-z ]+):\s*(.*)$")


def read_decklist(path: Path) -> dict[str, list[tuple[int, str]]]:
    """Parse a decklist into {section: [(count, name), ...]}.

    Handles both layouts in `decks/`: a bare `Legend:` header with entries on
    following lines, and `Legend: Name` inline on one line.
    """
    out: dict[str, list[tuple[int, str]]] = {}
    section = "MainDeck"
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _SECTION.match(line)
        if m and not _DECK_LINE.match(line):
            section = m.group(1).strip().replace(" ", "")
            out.setdefault(section, [])
            if m.group(2).strip():
                out[section].append((1, m.group(2).strip()))
            continue
        d = _DECK_LINE.match(line)
        if d:
            out.setdefault(section, []).append((int(d.group(1)), d.group(2).strip()))
    return out
