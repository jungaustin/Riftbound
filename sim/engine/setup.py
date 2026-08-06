"""Game setup — deterministic given a seed.

Determinism is what makes seed-based replay work: log `(seed, decks, versions)`
and any heuristic game can be reproduced exactly instead of stored. See the
logging tiers in sim/REFEREE.md.
"""

from __future__ import annotations

import random
from pathlib import Path

from .cards import Card, must_find
from .decklist import Decklist, parse_deck
from .state import (BATTLEFIELDS_1V1, MAIN, RUNE_DECK_SIZE, AWAKEN,
                    Battlefield, GameState, PlayerState)

OPENING_HAND = 4     # rule 116
MULLIGAN_MAX = 2     # rule 117.1


class DeckError(ValueError):
    pass


def _validate(deck: Decklist) -> None:
    if not deck.legend or not deck.champion:
        raise DeckError(f"{deck.name}: missing Legend or Champion")
    # The Chosen Champion counts toward the 40 minimum (103.2) but starts in the
    # Champion Zone, so a legal list shows 39.
    listed = deck.total("main")
    if listed + 1 < 40:
        raise DeckError(f"{deck.name}: {listed} listed + 1 Champion < 40")
    if deck.total("runes") != RUNE_DECK_SIZE:
        raise DeckError(f"{deck.name}: {deck.total('runes')} runes, need "
                        f"{RUNE_DECK_SIZE}")
    if deck.total("battlefields") < 3:
        raise DeckError(f"{deck.name}: needs 3 battlefields")


def _rune_domain(name: str) -> str:
    return name.replace("Rune", "").strip()


def build_player(seat: int, deck: Decklist, rng: random.Random) -> PlayerState:
    _validate(deck)
    cards = [must_find(n) for n in deck.expand("main")]
    rng.shuffle(cards)
    runes = [_rune_domain(n) for n in deck.expand("runes")]
    rng.shuffle(runes)
    return PlayerState(
        seat=seat,
        name=deck.name,
        legend=must_find(deck.legend),
        champion=must_find(deck.champion),
        deck=cards,
        rune_deck=runes,
    )


def _pick_battlefield(deck: Decklist, rng: random.Random) -> Card:
    """Each player brings 3 and ONE is chosen at random at setup (485.5)."""
    return must_find(rng.choice(deck.expand("battlefields")))


def mulligan(player: PlayerState, rng: random.Random, keep: int | None = None) -> None:
    """Set aside up to 2, draw that many, then Recycle the set-aside (117).

    Recycled main-deck cards go to the bottom of the Main Deck, so they are not
    removed from the game — a mulliganed card can still be drawn later.
    """
    n = MULLIGAN_MAX if keep is None else min(keep, MULLIGAN_MAX)
    if n <= 0:
        return
    aside = [player.hand.pop() for _ in range(min(n, len(player.hand)))]
    for _ in aside:
        if player.deck:
            player.hand.append(player.deck.pop(0))
    player.deck.extend(aside)


def new_game(deck_a: Path | Decklist, deck_b: Path | Decklist, *,
             seed: int = 0, game_id: str | None = None,
             do_mulligan: bool = False) -> GameState:
    rng = random.Random(seed)
    a = deck_a if isinstance(deck_a, Decklist) else parse_deck(deck_a)
    b = deck_b if isinstance(deck_b, Decklist) else parse_deck(deck_b)

    players = (build_player(0, a, rng), build_player(1, b, rng))
    battlefields = [
        Battlefield(card=_pick_battlefield(d, rng), index=i)
        for i, d in enumerate((a, b))
    ]
    assert len(battlefields) == BATTLEFIELDS_1V1

    for p in players:
        for _ in range(OPENING_HAND):
            if p.deck:
                p.hand.append(p.deck.pop(0))
        if do_mulligan:
            mulligan(p, rng)

    return GameState(
        players=players,
        battlefields=battlefields,
        turn=1,
        active=0,
        phase=AWAKEN,
        priority=None,
        seed=seed,
        game_id=game_id or f"g{seed:04d}",
    )
