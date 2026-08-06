#!/usr/bin/env python3
"""Set up the Lillia v7 / Darius matchup and show the four-state timing gate.

    python3 sim/run_demo.py [seed]

Renders the opening playfield for seat 0, then walks the same position through
all four states to show the legal-action list contract as timing tightens.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import (ChainItem, legal_actions, new_game, parse_deck,  # noqa: E402
                    start_turn, view_for)
from engine.cards import ACTION, REACTION  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DECK_A = ROOT / "decks/lillia-fae-fawn/v7.txt"
DECK_B = ROOT / "decks/meta/darius-fury-order.txt"


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    state = new_game(DECK_A, DECK_B, seed=seed)

    a, b = parse_deck(DECK_A), parse_deck(DECK_B)
    print(f"seat 0: {a.name}   ({a.total('main')} + champion, "
          f"{a.total('runes')} runes)")
    print(f"seat 1: {b.name}   ({b.total('main')} + champion, "
          f"{b.total('runes')} runes)")
    print(f"battlefields in play: "
          + " | ".join(f"B{bf.index + 1} {bf.card.name}"
                       for bf in state.battlefields))
    print()

    for line in start_turn(state):
        print(f"  turn 1 seat 0: {line}")
    print()
    print("=" * 72)
    print(view_for(state, 0))
    print("=" * 72)

    _timing_walk(state)
    _leak_check(state)
    return 0


def _timing_walk(state) -> None:
    """Same hand, four states — the action list must shrink monotonically."""
    print("\n### Timing gate: same position, four states\n")
    me = state.player(0)
    hand = me.hand
    tiers = {
        "plain": [c.name for c in hand if c.timing not in (ACTION, REACTION)],
        "[Action]": [c.name for c in hand if c.timing == ACTION],
        "[Reaction]": [c.name for c in hand if c.timing == REACTION],
    }
    print("  hand by tier:")
    for tier, names in tiers.items():
        print(f"    {tier:<12} {', '.join(names) or '—'}")
    print()

    scenarios = [
        ("Neutral Open", False, False),
        ("Showdown Open", True, False),
        ("Neutral Closed", False, True),
        ("Showdown Closed", True, True),
    ]
    print(f"  {'state':<18}{'allows':<28}{'plays offered':>14}")
    print("  " + "-" * 60)
    for label, showdown, closed in scenarios:
        state.showdown = showdown
        state.chain = ([ChainItem(source=me.hand[0], controller=1,
                                  description="opponent spell")] if closed else [])
        acts = legal_actions(state, 0)
        plays = sum(1 for x in acts if x.kind == "play")
        assert state.state_name == label, f"{state.state_name} != {label}"
        print(f"  {label:<18}{state.timing_note():<28}{plays:>14}")

    state.showdown = False
    state.chain = []
    print("\n  Plain spells vanish in any Showdown state; everything but")
    print("  [Reaction] vanishes once the Chain is non-empty.")


def _leak_check(state) -> None:
    """view_for must never expose the other seat's private zones."""
    print("\n### Hidden-information check\n")
    failures = []
    for seat in (0, 1):
        text = view_for(state, seat)
        hidden = state.opponent_of(seat)
        for card in hidden.hand:
            if card.name in text:
                failures.append(f"seat {seat} view leaks opp hand: {card.name}")
        for card in hidden.deck[:15]:
            if card.name in text and card not in state.player(seat).hand:
                failures.append(f"seat {seat} view leaks opp deck: {card.name}")
    for f in sorted(set(failures)):
        print(f"  LEAK  {f}")
    if not failures:
        print("  no leaks: neither seat's view contains the other's hand or deck")


if __name__ == "__main__":
    raise SystemExit(main())
