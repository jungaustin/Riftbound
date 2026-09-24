"""Which card do I encode next, and what does it need?

    python3 rl/tools/triage.py                  # the queue, most-played first
    python3 rl/tools/triage.py --ready          # only cards needing no new op
    python3 rl/tools/triage.py --mechanism XP   # one blocking mechanism
    python3 rl/tools/triage.py --card "Sprite Mother"
    python3 rl/tools/triage.py --meta            # weight by decks/meta only

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

from rl.config import ALL_KEYWORDS
from rl.decks import decklist_files, plays_as_printed
from rl.engine.cardtable import full_table, read_decklist
from rl.engine.effects import ABILITIES, SPECS, STATICS

# Mechanisms that do not exist yet. A card mentioning one is blocked on the
# mechanism, not on transcription -- ordered so the FIRST match is the biggest
# thing standing in the card's way.

# A card that plays a token needs that token to EXIST as a card, or there is
# nothing to put on the board -- a DATA gap rather than an engine one.
#
# This used to be a hardcoded list of names (Gold, Bird, Mech, Sand Soldier,
# Reflection, Poro, Treasure) written when `cards.json` shipped only Recruit
# and Sprite. `data/tokens.json` has since added the rest of rule 187, so the
# list outlived its own truth and went on blocking 30 cards whose tokens were
# sitting in the table -- the largest phantom cluster in the queue. Poro and
# Treasure never existed at all: 187 defines exactly eleven tokens and neither
# is among them, so those two names could never have resolved.
#
# Asking the table instead means the answer tracks the data. Today it is empty.
# If a future set prints a token the export omits, this reports it again by
# itself, which is the only reason to keep the check at all.
TOKEN_PHRASE = re.compile(r"([A-Z][A-Za-z' ]*?)\s+(?:unit|gear|battlefield)\s+tokens?")
# Text noise that survives the capture: "Play a ready Reflection unit token",
# "play a 2 Might Sand Soldier unit token" -- the name is the tail.
TOKEN_NOISE = re.compile(r"^(?:[Pp]lay|[A-Za-z]+)?\s*(?:a|an|two|four|ready|\d+|Might)\s+"
                         r"|^(?:a|an|two|four|ready)\s+")

# Every bracketed token in the card text, for the check below.
_ANY_BRACKET = re.compile(r"\[([^\]]+)\]")

# Bracketed tokens that are NOT keywords and must not be reported as missing
# ones. `[>]` and `[>>]` are the dependent-keyword separators 812.1.a shows in
# "[Legion][>] [Text]" -- punctuation meaning "then", on 79 cards. `[NO TEXT]`
# is the export's own placeholder on vanilla Rune cards.
FORMATTING_BRACKETS = {">", ">>", "NO TEXT"}

# Keywords the engine DOES implement but that `ALL_KEYWORDS` does not list, so
# they have no mask bit and `unread_keywords` cannot vouch for them. `[Level
# N]` is "while you have N+ XP, get the effect" and is `COND_LEVEL`
# (`resolve.py:801`, 14 uses in `effects.py`) -- a card carrying it needs
# transcription, not a new mechanism, so reporting it as an unknown keyword
# would send a reader looking for engine work that is already done.
IMPLEMENTED_OFF_MASK = {"level"}


def unknown_keywords(table, cid: int) -> list[str]:
    """Bracketed keywords on this card that `ALL_KEYWORDS` does not list.

    **Neither existing check can see these, which is the whole point.**
    `unread_keywords` iterates `ALL_KEYWORDS`, so a keyword missing from that
    tuple has no bit and is invisible to it; and `residual_text` may or may not
    strip the bracket, so the text side cannot be trusted either way:

      [Burn 1]      IS stripped -> Shadow Order Disciple reads "you may _ to
                    give me +1 Might", a hole where a cost used to be, which
                    looks like a vanilla card rather than a blocked one.
      [Quick-Draw]  is NOT stripped, because `cardtable._BRACKET`'s character
                    class is `[A-Za-z ]` and does not include the hyphen -- so
                    it survives into residual text as literal noise instead.

    Both failure directions land here. Read from RAW text for that reason.
    This started as a hardcoded `[Burn \\d+]` pattern; generalising it caught
    [Quick-Draw] (5 cards, 3 deck slots) immediately, and will catch whatever
    the next set prints without another edit.
    """
    known = {k.lower() for k in ALL_KEYWORDS} | IMPLEMENTED_OFF_MASK
    out = []
    for m in _ANY_BRACKET.finditer(table.raw_text[cid] or ""):
        tok = m.group(1).strip()
        if tok in FORMATTING_BRACKETS:
            continue
        base = re.sub(r"\s*\d+$", "", tok)      # "[Burn 1]" -> "Burn"
        if base.lower() in known or base in FORMATTING_BRACKETS:
            continue
        if base not in out:
            out.append(base)
    return out

# What is LEFT of an Equipment card's residual text once the rune and energy
# symbols of its [Equip] cost are removed. Empty means the export gave us the
# COST of attaching and nothing about what attaching DOES.
_ONLY_SYMBOLS = re.compile(r"(?:\{[^}]*\}|[\s,.:;—-])+")


def missing_equip_data(table, cid: int) -> bool:
    """Is this an Equipment card whose EFFECT the card export omits?

    A DATA gap, not an engine one -- the same class as `missing_tokens`, and
    it is reported separately for the same reason: no amount of attach
    machinery makes B.F. Sword do anything when the only thing `cards.json`
    records about it is "[Equip] {Order rune}".

    Measured at the time of writing: **30 of the pool's 40 Equipment cards**
    carry no effect text at all, which is 23 deck slots. Every one of them is
    a stat-stick whose whole function is a Might bonus or a granted keyword
    that the export simply does not have a field for (136.2.d expects both).
    The other 10 -- Shurelya's Requiem, Last Rites, Shady Spectacles -- print
    real sentences and are ordinary `Equip` work.

    Checked against the table rather than a hardcoded name list, for the
    reason `missing_tokens` learned the hard way: if a future export adds the
    field, this stops firing by itself instead of going on blocking cards
    whose data has since arrived.
    """
    if "Equipment" not in table.tags[cid]:
        return False
    return not _ONLY_SYMBOLS.sub("", table.residual_text(cid)).strip()


def _token_key(name: str) -> str:
    """Card name -> comparable token name.

    The export decorates tokens with a back face and a collector number:
    `Gold // Buff`, `Recruit (271) // Buff`. Card TEXT says plain "Gold".
    """
    return re.sub(r"\s*\(\d+\)|\s*//.*$", "", name).strip().lower()


def missing_tokens(table, text: str) -> list[str]:
    """Token names `text` plays that no card in the table provides."""
    known = {_token_key(table.names[c]) for c in range(table.n)
             if table.is_token(c)}
    out = []
    for m in TOKEN_PHRASE.finditer(text):
        name = m.group(1).strip()
        while True:                       # peel "Play a 2 Might " one word at a time
            stripped = TOKEN_NOISE.sub("", name).strip()
            if stripped == name:
                break
            name = stripped
        if name and _token_key(name) not in known:
            out.append(name)
    return out

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
    # A "Choose one --" spell needs a real mode choice at finalization; no op
    # picks among alternative effect lists yet, so every branch is unwritten
    # even when each branch alone matches a KNOWN_CLAUSE. Checked first because
    # a modal card's individual clauses read as pure transcription otherwise --
    # Flurry of Feathers and Mesmerize both slipped through `ready` this way.
    ("Modal",       r"[Cc]hoose one\s*[—-]"),
    # "As an additional cost to play this/me, kill a [...] unit" pays with a
    # BODY, not runes -- `cost.py` has no such Cost yet, only PLAY_COSTS'
    # rune-and-energy additional costs. `[Kk]ill (a|an|target)` in KNOWN_CLAUSE
    # matches this same substring as if it were the card's EFFECT, which is
    # what let Sacrifice and Cruel Patron read as ready while paying for a
    # mechanism that does not exist.
    ("CostKill",    r"[Aa]s an additional cost to play (this|me),\s*kill a"),
    # "Counter a spell unless its controller pays {X}" is a taxed replacement,
    # not a plain OP_COUNTER -- no op lets a counter be bought off. Checked
    # before KNOWN_CLAUSE for the same reason CostKill is: "Counter a spell" is
    # a substring of the whole clause, so the crude ready check matched it and
    # missed the "unless" half entirely (Hard Bargain).
    ("TaxedEffect", r"unless (its|their|you)r? ?controller pays|unless .*pays"),
    # "When you play me FROM FACE DOWN..." restricts a TR_PLAY_ME trigger to a
    # reveal from the Facedown Zone specifically. `Ability` has no flag for it
    # -- `COND_FROM_HAND` states the opposite question ("from hand") and nothing
    # asks this one, so Evelynn - Entrancing and its kin need a new condition,
    # not just a spec entry.
    ("FromHidden",  r"from face down"),
    # "If it was an enemy unit, ... If it was a friendly unit, ..." branches on
    # who CONTROLLED a target the card just killed -- no COND reads a target's
    # controller post-resolution (COND_WAS_MIGHTY is the closest shape, and it
    # snapshots the SOURCE's own past might, not another unit's owner). One
    # card only (Blood Money) as of this writing.
    ("TargetSide",  r"[Ii]f it was an (enemy|friendly)"),
    ("Empower",     r"\[Empower"),
    ("XP",          r"\bXP\b|\[Level"),
    ("Equip",       r"\[Equip\]|\[Weaponmaster\]|Equipment|attach"),
    ("Predict",     r"\[Predict\]"),
    ("Buff",        r"\[Buff\]|\bbuffs?\b"),
    ("Trash",       r"from your trash|in your trash"),
    ("DeckManip",   r"top \d+ cards|top card|[Rr]ecycle|[Bb]anish|[Ss]huffle"),
    ("HandInfo",    r"reveal their hand|look at their|reveals? their"),
    # A plain "discard N" is `OP_DISCARD` and has been for a while -- Traveling
    # Merchant's "discard 1, then draw 1" was filed here for months while both
    # halves already existed. What is NOT implemented is discarding something
    # CHOSEN or a whole hand, and branching on what came out: Hwei reads the
    # discarded card's type, Invert Timelines empties both hands. Match those
    # instead of the bare word, the same correction MissingToken needed.
    ("Discard",     r"discards? (their|your) hand|discarded card"),
    ("Replacement", r"if you would|would be|instead"),
    ("Points",      r"\d+ points?\b"),
    # Plain "channel N rune(s)" is `OP_CHANNEL` and has been since Mobilize.
    # What is NOT implemented is channelling to a place other than the board,
    # or a channel whose count is itself conditional. Matching the bare word
    # kept Retreat filed here after both of its halves existed -- the same
    # correction MissingToken and Discard needed.
    ("Channel",     r"[Cc]hannel .*(instead|from|into)"),
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


def deck_slots(table, meta_only: bool = False) -> Counter:
    """Slot weights over one file per DECK, not one per decklist.

    `decklist_files(latest_only=True)` is the whole fix and it lives in
    `rl.decks` so the training pool and this queue cannot drift apart. Counting
    every version put Keeper of Masks at the top of the queue with 8 slots; it
    has 2, and appears in no meta deck at all.
    """
    from engine.cards import find
    slots: Counter = Counter()
    for f in decklist_files(latest_only=True, meta_only=meta_only):
        parsed = read_decklist(f)
        if len(parsed.get("MainDeck", [])) < 5:
            continue
        for sec in ("MainDeck", "Battlefields", "Battlefield", "Legend"):
            # A battlefield and a legend are deck slots too -- three and one
            # per list -- and the zone queues sort by the same weight the main
            # queue does. They cannot collide with a main-deck name: no card
            # is both.
            for count, name in parsed.get(sec, []):
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
    # Asked BEFORE the keyword check, unlike every other test here, because a
    # DATA gap outranks an engine one: these cards report "Equip", which reads
    # as "implement the keyword and they work", and they would not. There is
    # nothing in `cards.json` for the attach to grant.
    if missing_equip_data(table, cid):
        return "NoEquipData", False
    unread = [k for k in table.unread_keywords(cid)
              if k not in TRIGGER_KEYWORDS]
    if unread:
        return unread[0], False
    residual = table.residual_text(cid)
    # Asked first among the TEXT tests, and of the RAW text: a token this card
    # plays has to exist before any clause of it can be transcribed, so it
    # outranks every mechanism below.
    absent = missing_tokens(table, table.raw_text[cid])
    if absent:
        return f"NoToken:{absent[0]}", False
    for label, pat in MECHANISMS:
        if re.search(pat, residual):
            return label, False
    # After the named mechanisms, deliberately: a card whose blocker already
    # has a name keeps it. `[Level]` is not in `ALL_KEYWORDS` either, but
    # "XP" says far more about what it needs than "Kw:Level" would, and there
    # is a `--mechanism XP` batch to run. Only genuinely unnamed tokens fall
    # through to here.
    unknown = unknown_keywords(table, cid)
    if unknown:
        return f"Kw:{unknown[0]}", False
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
    ap.add_argument("--zone", choices=("main", "battlefield", "legend"),
                    default="main",
                    help="which deck the queue is for. The main deck is "
                         "Unit/Spell/Gear; a battlefield and a legend are "
                         "neither, and each has its own ability tables.")
    ap.add_argument("--meta", action="store_true",
                    help="weight by decks/meta only -- the competitive "
                         "distribution, without the repo owner's own brews")
    a = ap.parse_args(argv)

    table = full_table()
    slots = deck_slots(table, meta_only=a.meta)

    if a.card:
        cid = table.id_of(a.card)
        mech, ready = classify(table, cid)
        print(f"{a.card}\n  {table.raw_text[cid]}\n")
        meta = deck_slots(table, meta_only=True)
        print(f"  slots in decks : {slots.get(a.card, 0)}"
              f"  (meta only: {meta.get(a.card, 0)})")
        print(f"  as printed     : {plays_as_printed(table, cid)}")
        print(f"  blocked by     : {mech}")
        print(f"  ready          : {ready}")
        print(f"  residual text  : {table.residual_text(cid)!r}")
        print(f"  unread keywords: {table.unread_keywords(cid)}")
        return 0

    if a.zone in ("battlefield", "legend"):
        return _zone_queue(table, slots, a)

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


def _zone_queue(table, slots, a) -> int:
    """The queue for a zone whose cards are not main-deck cards.

    Battlefields and legends have no `SPECS` entry -- they are never played, so
    there is no card to play as printed. What "scripted" means for them is an
    entry in their own tables: `BF_ABILITIES`/`BF_STATICS` for the ground,
    `LEGEND_ABILITIES`/`LEGEND_STATICS` for the champion. Baron Pit is the one
    exception, a token battlefield whose whole text ("units can move here from
    anywhere") lives in `combat.moves_from_anywhere`.
    """
    from rl.engine.effects import (BF_ABILITIES, BF_COST_RULES,
                                   BF_DEATH_REPLACEMENT, BF_EXTRA_HIDE,
                                   BF_GRANTS_LEGEND, BF_GRANTS_UNITS,
                                   BF_IGNORE_DEFLECT, BF_PLAY_COSTS,
                                   BF_SCORE_RULES, BF_STATICS,
                                   LEGEND_ABILITIES, LEGEND_STATICS)
    kind = "Battlefield" if a.zone == "battlefield" else "Legend"
    tables = ((BF_ABILITIES, BF_STATICS) if kind == "Battlefield"
              else (LEGEND_ABILITIES, LEGEND_STATICS))
    # A battlefield whose whole text is a COST or SCORING rule has no entry in
    # either ability table -- the rule lives in its own registry, which is the
    # only place a clause about a payment or about the Victory Score can be
    # expressed. Baron Pit is the other kind: one line, in `combat`.
    ELSEWHERE = ({"Baron Pit"} | set(BF_COST_RULES) | set(BF_IGNORE_DEFLECT)
                 | set(BF_SCORE_RULES) | set(BF_GRANTS_UNITS)
                 | set(BF_GRANTS_LEGEND) | set(BF_DEATH_REPLACEMENT)
                 | set(BF_EXTRA_HIDE) | set(BF_PLAY_COSTS)
                 ) if kind == "Battlefield" else set()
    cards = [c for c in range(table.n) if table.is_type(c, kind)]
    done = [c for c in cards if table.names[c] in tables[0]
            or table.names[c] in tables[1] or table.names[c] in ELSEWHERE]
    rows = [c for c in cards if c not in set(done)]
    if a.in_decks:
        rows = [c for c in rows if slots.get(table.names[c], 0)]
    rows.sort(key=lambda c: (-slots.get(table.names[c], 0), table.names[c]))
    print(f"{len(rows)} {kind.lower()}s queued   "
          f"({len(done)}/{len(cards)} scripted)\n")
    print(f"{'slots':>5} {'card':<32} text")
    for c in rows[:a.limit]:
        txt = (table.raw_text[c] or "").replace("\n", " ")[:70]
        print(f"{slots.get(table.names[c], 0):>5} {table.names[c]:<32} {txt}")
    if len(rows) > a.limit:
        print(f"\n  ... {len(rows) - a.limit} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
