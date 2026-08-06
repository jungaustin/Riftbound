"""Riftbound simulation engine.

The engine is the source of truth. It holds full state, enumerates every legal
action, and applies whichever one a pilot picks. A pilot only ever sees
`render.view_for(state, seat)` and can only ever reply with an index into the
list the engine built, so it cannot cheat, misplay a timing window, or read the
opponent's hand — those are structural guarantees, not conventions.
"""

from .actions import Action, Payment, legal_actions, only_pass, plan_payment
from .cards import ACTION, PLAIN, REACTION, Card, find, must_find
from .decklist import Decklist, parse_deck
from .render import view_for
from .setup import DeckError, new_game
from .state import (BATTLEFIELDS_1V1, VICTORY_SCORE, Battlefield, ChainItem,
                    GameState, Permanent, PlayerState, Rune)
from .turn import end_turn, start_turn

__all__ = [
    "Action", "Payment", "legal_actions", "only_pass", "plan_payment",
    "ACTION", "PLAIN", "REACTION", "Card", "find", "must_find",
    "Decklist", "parse_deck", "view_for", "DeckError", "new_game",
    "BATTLEFIELDS_1V1", "VICTORY_SCORE", "Battlefield", "ChainItem",
    "GameState", "Permanent", "PlayerState", "Rune",
    "end_turn", "start_turn",
]
