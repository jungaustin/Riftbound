"""Rules access: a small always-on constitution, plus grep into the full text.

The full Core Rules run ~48k tokens. Injecting them into every call crowds out
the card pool for no benefit, so the distilled constitution ships in the prompt
and the full text stays behind `lookup()` for edge cases.
"""

from __future__ import annotations

import re
from pathlib import Path

CONSTITUTION = """\
# Riftbound deck construction (Core Rules 2025-06-02, section 103)

A deck consists of:
- 1 Champion Legend. It sets the deck's Domain Identity (103.1.b).
- A Main Deck of at least 40 cards, which INCLUDES the 1 Chosen Champion unit
  (103.2). Units, Gear and Spells go here.
- A Rune Deck of exactly 12 rune cards (103.3.a).
- Battlefields: count is set by the Mode of Play (103.4.a); 3 is standard 1v1.

Domain Identity (103.1.b.3-4):
- A single-domain card is legal in an identity containing that domain.
- A multi-domain card is legal only in an identity containing ALL of its domains.
- Colorless cards are legal in any identity.
- This applies to the Main Deck, the Rune Deck, and Battlefields.

Chosen Champion (103.2.a):
- Must be a champion unit (type Unit, supertype Champion) whose champion tag
  matches a tag on the Champion Legend.
- Signature units are NOT champion units and cannot be the Chosen Champion.
- It counts toward the 40-card main deck, and toward the 3-copy limit: you may
  run 2 more copies of it in the deck.

Copies (103.2.b):
- Up to 3 copies of the same NAMED card in the main deck.
- Cards with different names are different cards even for the same character:
  3x "Yasuo, Remorseful" plus 3x "Yasuo, Windrider" is legal.

Signature cards (103.2.d):
- At most 3 signature cards TOTAL in the deck, regardless of name.
- All of them must carry the champion tag matching the Champion Legend.

THE RUNE ECONOMY — READ THIS BEFORE SAYING WHAT TURN ANYTHING HAPPENS:
- You channel 2 runes every Channel Phase (315.3.b). The player going SECOND
  channels 1 extra on their first turn only (485.7 / 486.7).
- The Rune Deck is exactly 12, so you are fully channelled by turn 6 and gain
  nothing after that without effects that channel extra.
- A Basic Rune has TWO INDEPENDENT abilities (164.2):
    [E]: Add 1 Energy          -> exhaust it; renewable, it readies next turn
    Recycle this: Add 1 Power  -> the rune goes to the BOTTOM of the Rune Deck

- *** RUNES NEEDED TO CAST = max(energy, power). NOT energy + power. ***
  The Recycle ability's cost is ONLY "Recycle this" — no exhaust requirement,
  and Recycle (416) is just "put it on the bottom of the Rune Deck". So a rune
  ALREADY EXHAUSTED for Energy can still be recycled for Power in the same
  turn. One physical rune produces both.
    {2}{P1} costs 2 runes, not 3 -> castable on TURN 1.
    {2}{P2} costs 2 runes, not 4.
    {1}{P1} costs 1 rune.
  Getting this wrong makes every Power card look a full turn slower than it is.

- A POWER COST IS STILL MORE EXPENSIVE THAN ITS ENERGY NUMBER SUGGESTS — but
  the extra cost is ONGOING, not a later cast turn. For {2}{P1} you exhaust two
  runes for Energy and then recycle one of those same runes for the Power. It
  ties up 2 runes this turn (the same as any 2-drop), but that recycled rune is
  gone from EVERY following turn until you re-channel it at 2/turn. So:
      Cast turn  -> max(energy, power). Power does NOT delay you.
      Every turn after -> each Power pip you spent shrinks your rune board.
  Play a {2}{P1} card on turn 1 and you have 3 runes on turn 2, not 4; play it
  on turn 2 and you have 5 on turn 3, not 6.
- Read the comparison this way: a {2}{P1} card is EASIER to cast than a plain
  {3} (2 runes vs 3) and MORE expensive to have cast (you are down a rune
  afterwards). Power front-loads access and back-loads cost — an asset to tempo
  decks, a real drag on long-game decks. Before a Power-heavy turn, ask what
  next turn's rune count will be.

- Runes available by turn, with no ramp:

    turn        1    2    3    4    5    6+
    on the play 2    4    6    8   10   12
    on the draw 3    5    7    9   11   12

- Read max(energy, power) against that table. A 5-energy card is a TURN 3 play,
  not a late-game one. Anything needing more than 12 runes is unreachable
  without channel ramp, which is why ramp decks run extra-channel effects.
- Ability costs (Empower, Equip, activated abilities) also demand runes and are
  NOT part of a card's printed Power cost. Budget for them separately.

CASTABLE IS NOT THE SAME AS CORRECT — TAPPING OUT HAS A PRICE:
- Only the Turn Player readies, and only on their own turn (315.1.b, 415.3.a).
  A rune you exhaust during YOUR Main Phase stays exhausted through your
  OPPONENT'S entire turn and returns at your next Awaken Phase. Every point of
  spending is a two-turn commitment, not a one-turn one.
- So emptying your rune pool SURRENDERS the opponent's turn. Counterspells,
  combat tricks, Hidden flips and Ambush units are all blank with no runes
  available. A deck holding nine reaction cards that taps out every turn is a
  deck holding nine dead cards.
- A card that ENTERS EXHAUSTED or has no enter-the-board impact costs double:
  you pay the runes, you give up the defensive posture, and you get nothing
  back until your next turn. Rate those BELOW their stat line. "It's castable
  on turn 3" is a fact about the curve, not a recommendation.
- Therefore a perfectly-filled curve is often a trap. Spending your exact rune
  count every turn maximises deployment and minimises defence. Build and play
  for SLACK: decide how many runes you want live on the opponent's turn
  (roughly the cost of your most important reaction, plus one), then spend the
  rest.
- The per-turn question is never "what is the biggest thing I can afford?" It
  is "does this development beat the interaction I give up by casting it?"
  Sometimes yes — you cannot contest battlefields without bodies, and a turn
  spent holding runes for a trick that never comes is also a wasted turn.
  Sometimes an unimpressive turn that leaves three runes live wins the game.

Stats on cards:
- Energy (E) is the generic cost. Power (P) is the rune cost. Might (M) is the
  unit's combat statistic.

Costs and runes — READ THIS BEFORE REASONING ABOUT RUNE COUNTS:
- Energy has NO domain (rule 156.1.a). Any rune can pay an Energy cost.
- Power HAS a domain (rule 156.2.a), matching the card's own domain.
- Therefore a card's printed domain does NOT mean it needs that colour of rune.
  A card printed in Fury with no Power cost is castable off any runes at all.
  Only the Power cost constrains your rune deck.
- Roughly half of all playable cards have no Power cost whatsoever.
- Multi-domain cards print a hybrid Power symbol, payable with a rune of any one
  of their listed domains.
- So when you judge rune consistency, count PIPS (Power symbols), not cards.
  A deck with 20 Fury cards but only 5 Fury pips barely needs Fury runes.
"""

_SECTION = re.compile(r"^(\d{3}(?:\.\d+)*(?:\.[a-z](?:\.\d+)*)?)\.\s")


def constitution() -> str:
    return CONSTITUTION


def full_text(data_dir: Path) -> str:
    p = data_dir / "rules.txt"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Generate it with:\n"
            f"  pdftotext -layout reference/Riftbound-Core-Rules-*.pdf data/rules.txt"
        )
    return p.read_text()


def lookup(data_dir: Path, query: str, context: int = 6, limit: int = 40) -> str:
    """Grep the full rules. Use for keyword definitions and edge-case timing."""
    lines = full_text(data_dir).splitlines()
    pat = re.compile(re.escape(query), re.I) if not _is_regex(query) else re.compile(query, re.I)
    out: list[str] = []
    hits = 0
    for i, line in enumerate(lines):
        if pat.search(line):
            hits += 1
            if hits > limit:
                out.append(f"... (more than {limit} matches, refine the query)")
                break
            lo, hi = max(0, i - context), min(len(lines), i + context + 1)
            out.append("\n".join(lines[lo:hi]))
            out.append("---")
    return "\n".join(out) if out else f"No rules text matches {query!r}."


def section(data_dir: Path, number: str) -> str:
    """Return rule `number` and everything nested under it, e.g. "103"."""
    lines = full_text(data_dir).splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        m = _SECTION.match(line.strip())
        if m:
            num = m.group(1)
            if num == number or num.startswith(number + "."):
                started = True
            elif started and not num.startswith(number):
                break
        if started:
            out.append(line)
    return "\n".join(out).rstrip() or f"No rule numbered {number}."


def _is_regex(s: str) -> bool:
    return any(ch in s for ch in ".*+[](){}|^$\\")
