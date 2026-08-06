"""How many copies to run: hypergeometric draw odds for a 40-card Riftbound deck.

Riftbound opens on 4 cards (rule 116) and draws 1 per turn (591.2.a; the player
going first skips their first draw, 646.7). That opening hand is small by TCG
standards, which is exactly why copy counts matter more here than in games that
open on 7 — a 1-of is close to invisible in the early game.

These are draw odds only. They tell you how often you SEE a card, not whether
seeing it is good, so they bound the decision rather than making it.
"""

from __future__ import annotations

from math import comb

OPENING_HAND = 4
DECK_SIZE = 40


def at_least_one(copies: int, cards_seen: int, deck_size: int = DECK_SIZE) -> float:
    """P(at least 1 copy among `cards_seen` cards drawn from `deck_size`)."""
    if copies <= 0 or cards_seen <= 0:
        return 0.0
    cards_seen = min(cards_seen, deck_size)
    misses = comb(deck_size - copies, cards_seen) if deck_size - copies >= cards_seen else 0
    return 1.0 - misses / comb(deck_size, cards_seen)


def exactly(copies: int, cards_seen: int, k: int, deck_size: int = DECK_SIZE) -> float:
    if k > copies or k > cards_seen:
        return 0.0
    return (
        comb(copies, k)
        * comb(deck_size - copies, cards_seen - k)
        / comb(deck_size, cards_seen)
    )


def cards_seen_by_turn(turn: int, on_play: bool = True) -> int:
    """Cards seen by the start of `turn`'s main phase, no card draw effects."""
    draws = max(0, turn - 1) if on_play else turn
    return OPENING_HAND + draws


def table(deck_size: int = DECK_SIZE, turns=(1, 3, 5, 8)) -> str:
    rows = ["copies | " + " | ".join(f"by T{t}" for t in turns) + " | opening hand"]
    rows.append("-" * len(rows[0]))
    for copies in (1, 2, 3):
        cells = []
        for t in turns:
            seen = cards_seen_by_turn(t)
            cells.append(f"{at_least_one(copies, seen, deck_size):.0%}")
        opener = at_least_one(copies, OPENING_HAND, deck_size)
        rows.append(f"{copies:^6} | " + " | ".join(f"{c:>6}" for c in cells) + f" | {opener:.0%}")
    return "\n".join(rows)


def doctrine(deck_size: int = DECK_SIZE) -> str:
    """Prompt fragment: the numbers, plus how to reason from them."""
    return f"""\
## Copy-count doctrine (1 vs 2 vs 3)

Riftbound opens on {OPENING_HAND} cards and draws 1 per turn. In a {deck_size}-card
deck, the odds of having seen at least one copy are:

{table(deck_size)}

Read those numbers before choosing a count:

- **Run 3** when the deck does not function without the card, or wants it as
  early as possible: the Chosen Champion's support, the core engine piece, your
  primary removal, cheap enablers. A 3-of is in your opening hand ~28% of the
  time and reliably online by mid-game. If the deck's plan collapses when you
  don't draw it, 3 is not a preference, it is a requirement.
- **Run 2** for cards that are strong but redundant with something else, awkward
  in multiples (legendary-style "Unique" effects, expensive finishers you only
  need one of), or situational enough that a second is fine but a third would
  clog. Two is also the honest answer for a card you want but cannot afford to
  draw early.
- **Run 1** only with a specific reason. Valid reasons: the card is genuinely
  Unique or otherwise dead in multiples; it is a high-cost singleton finisher
  you will find via card draw; you have a tutor that fetches it. A 1-of you
  merely "like" is a mistake: you see it by turn 5 only about {at_least_one(1, cards_seen_by_turn(5), deck_size):.0%} of the time,
  so it does nothing in most games while still taking a slot.

The trap to avoid: a deck full of 1-ofs and 2-ofs looks flexible and plays
inconsistently. Prefer fewer distinct effects at higher counts. If you cannot
justify a 1-of in one sentence, make it a 3-of or cut it.

For every card in the list, state the count and, when it is not 3, why not.
"""
