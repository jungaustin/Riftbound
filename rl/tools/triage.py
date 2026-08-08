"""Which card do I encode next, and what does it need?

    python3 rl/tools/triage.py                  # the queue, most-played first
    python3 rl/tools/triage.py --ready          # only cards needing no new op
    python3 rl/tools/triage.py --mechanism XP   # one blocking mechanism
    python3 rl/tools/triage.py --card "Sprite Mother"

Encoding the pool card-by-card in alphabetical order thrashes: consecutive
cards want unrelated mechanisms, so each one pays the cost of understanding a
mechanism that the next one throws away. This orders the work instead by

  1. **deck slots** -- a card in the corpus is worth more than one that is not,
     because deck evaluation is the deliverable, and
  2. **blocking mechanism** -- so a batch shares its rules reading.

`ready` is the useful column: it means every clause of the card matched an op
the DSL already has, so it is transcription rather than design. That set is
where a session should start, and it is far larger than it looks -- roughly
half the pool needs no new mechanism at all.

The classifier is deliberately crude and errs toward "not ready". A card it
mislabels ready costs one wasted look; a card it mislabels blocked just waits.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rl.decks import plays_as_printed
from rl.engine.cardtable import full_table, read_decklist
from rl.engine.effects import ABILITIES, SPECS, STATICS

# Mechanisms that do not exist yet. A card mentioning one is blocked on the
# mechanism, not on transcription -- ordered so the FIRST match is the biggest
# thing standing in the card's way.
# Token cards the effect would have to instantiate. `data/cards.json` only
# ships Recruit and Sprite, so a card that plays a Gold, Bird, Mech, Sand
# Soldier or Reflection token cannot be encoded at all -- there is nothing to
# put on the board. This is a DATA gap, not an engine one, and it was giving
# false "ready" flags on nine deck cards.
MISSING_TOKENS = r"(Gold|Bird|Mech|Sand Soldier|Reflection|Poro|Treasure)\b[^.]*token"

# Ability keywords whose TRIGGER the DSL already has. 808.1 makes [Deathknell]
# short for "When I die, [Effect]" and the effect is the card's own text, so the
# keyword is not itself the blocker -- the card is ready exactly when that text
# is expressible, which the residual check below decides.
#
# `config.ABILITY_KEYWORDS` also lists Vision and Hunt, and those are NOT here:
# no TR_ for either exists yet, so a card carrying one is genuinely blocked and
# should say so rather than being offered as transcription.
TRIGGER_KEYWORDS = {"Deathknell"}

MECHANISMS = [
    ("MissingToken", MISSING_TOKENS),
    ("Empower",     r"\[Empower"),
    ("XP",          r"\bXP\b|\[Level"),
    ("Equip",       r"\[Equip\]|\[Weaponmaster\]|Equipment|attach"),
    ("Predict",     r"\[Predict\]"),
    ("Buff",        r"\[Buff\]|\bbuffs?\b"),
    ("Trash",       r"from your trash|in your trash"),
    ("DeckManip",   r"top \d+ cards|top card|[Rr]ecycle|[Bb]anish|[Ss]huffle"),
    ("HandInfo",    r"reveal their hand|look at their|reveals? their"),
    ("Discard",     r"discard"),
    ("Replacement", r"if you would|would be|instead"),
    ("Points",      r"\d+ points?\b"),
    ("Channel",     r"[Cc]hannel"),
    ("Control",     r"[Tt]ake control"),
]

# Clauses the DSL can already express. Matching ALL of a card's text against
# these is what "ready" means.
KNOWN_CLAUSE = [
    r"[Dd]raw \d+",
    r"[Kk]ill (a|an|target)",
    r"[Dd]eal \d+ to",
    r"[Ss]tun",
    r"[Gg]ive .*[+-]\d+ [Mm]ight",
    r"[Rr]eturn .* to (its|their) owner'?s? hand",
    r"[Mm]ove .* to",
    r"[Cc]ounter a spell",
    r"[Pp]lay (a|two|four) .*token",
    r"[Rr]eady (a|an|another|up to)",
    r"[Hh]eal",
]


def deck_slots(table) -> Counter:
    from engine.cards import find
    slots: Counter = Counter()
    for f in sorted(Path("decks").rglob("*.txt")):
        parsed = read_decklist(f)
        if len(parsed.get("MainDeck", [])) < 5:
            continue
        for count, name in parsed.get("MainDeck", []):
            card = find(name)
            if card is not None:
                slots[card.name] += count
    return slots


def classify(table, cid: int) -> tuple[str, bool]:
    """(blocking mechanism or '-', ready-to-transcribe).

    A card is blocked by an unimplemented KEYWORD or by unimplemented TEXT, and
    the two need different evidence:

      - keywords are asked of `unread_keywords`, the engine's own record of
        what it never consults. Asking the text instead means a keyword whose
        reminder is stripped from `residual_text` disappears entirely --
        [Empower] and [Predict] print nothing but their own reminder, so Noxian
        Emissary and Eclipse both read as pure transcription when they are not.
      - text is asked of `residual_text`, never `raw_text`. A keyword's
        REMINDER describes the keyword, and once the engine implements it the
        reminder is no longer a statement about work left to do. [Flow] prints
        "(You may play this from your trash for its flow cost)", which filed
        eleven ordinary spells -- Brittle Steel's "Kill a gear", Onslaught's
        "+6 Might" -- under a trash-recursion mechanism none of them touch.

    Both readings were wrong in opposite directions, and each one hid roughly a
    dozen cards.
    """
    unread = [k for k in table.unread_keywords(cid)
              if k not in TRIGGER_KEYWORDS]
    if unread:
        return unread[0], False
    residual = table.residual_text(cid)
    for label, pat in MECHANISMS:
        if re.search(pat, residual):
            return label, False
    if not residual:
        return "-", True                     # keywords only
    # Ready iff every sentence matches something the DSL can already say.
    parts = [p for p in re.split(r"[.\n]", residual) if p.strip()]
    ready = all(any(re.search(k, p) for k in KNOWN_CLAUSE) for p in parts)
    return "-", ready


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ready", action="store_true",
                    help="only cards needing no new mechanism or op")
    ap.add_argument("--mechanism", help="filter to one blocking mechanism")
    ap.add_argument("--card", help="explain a single card")
    ap.add_argument("--in-decks", action="store_true",
                    help="only cards that appear in decks/")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args(argv)

    table = full_table()
    slots = deck_slots(table)

    if a.card:
        cid = table.id_of(a.card)
        mech, ready = classify(table, cid)
        print(f"{a.card}\n  {table.raw_text[cid]}\n")
        print(f"  slots in decks : {slots.get(a.card, 0)}")
        print(f"  as printed     : {plays_as_printed(table, cid)}")
        print(f"  blocked by     : {mech}")
        print(f"  ready          : {ready}")
        print(f"  residual text  : {table.residual_text(cid)!r}")
        print(f"  unread keywords: {table.unread_keywords(cid)}")
        return 0

    rows = []
    for cid in range(table.n):
        if table.is_token(cid) or plays_as_printed(table, cid):
            continue
        if not any(table.is_type(cid, t) for t in ("Unit", "Spell", "Gear")):
            continue
        mech, ready = classify(table, cid)
        n = slots.get(table.names[cid], 0)
        if a.ready and not ready:
            continue
        if a.mechanism and mech != a.mechanism:
            continue
        if a.in_decks and not n:
            continue
        rows.append((n, ready, mech, cid))

    rows.sort(key=lambda r: (-r[0], not r[1], r[2], table.names[r[3]]))
    done = len(SPECS) + len(ABILITIES) + len(STATICS)
    print(f"{len(rows)} cards queued   ({done} specs written so far)\n")
    print(f"{'slots':>5} {'rdy':>4} {'blocked by':<12} {'card':<30} text")
    for n, ready, mech, cid in rows[:a.limit]:
        txt = table.residual_text(cid).replace("\n", " ")[:58]
        print(f"{n:>5} {'yes' if ready else '':>4} {mech:<12} "
              f"{table.names[cid]:<30} {txt}")
    if len(rows) > a.limit:
        print(f"\n  ... {len(rows) - a.limit} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
