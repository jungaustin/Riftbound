"""Phase machine (rules 315-317).

Everything up to the Main Phase is forced — no player choices — so the engine
runs those steps itself and only stops to ask a pilot once Main begins.
"""

from __future__ import annotations

from .state import (AWAKEN, BEGINNING, CHANNEL, DRAW, ENDING, MAIN,
                    GameState, PlayerState, Rune)

# Points scored per battlefield Held. Some battlefields and effects alter this;
# a per-battlefield value belongs here once those cards are implemented.
POINTS_PER_HOLD = 1


def awaken(state: GameState) -> None:
    """Turn player readies everything they control (315.1.b)."""
    seat = state.active
    for rune in state.player(seat).runes:
        rune.ready = True
    for perm in state.permanents:
        if perm.controller == seat:
            perm.ready = True


def beginning(state: GameState) -> list[str]:
    """Scoring Step: the turn player Holds every battlefield they control.

    Scoring happens at the START of your turn for battlefields you ALREADY
    control (315.2.b.2) — taking one on your own turn scores nothing until you
    have held it through the opponent's turn.
    """
    seat = state.active
    log: list[str] = []
    for bf in state.battlefields:
        if bf.controller == seat:
            state.player(seat).points += POINTS_PER_HOLD
            log.append(f"held B{bf.index + 1} {bf.card.name} "
                       f"(+{POINTS_PER_HOLD})")
    state.winner = state.check_winner()
    return log


def channel(state: GameState, extra: int = 0) -> list[str]:
    """Channel 2 runes, or as many as remain (315.3.b, 315.3.b.1)."""
    p = state.player(state.active)
    drawn: list[str] = []
    for _ in range(2 + extra):
        if not p.rune_deck:
            break
        domain = p.rune_deck.pop(0)
        p.runes.append(Rune(domain=domain, ready=True))
        drawn.append(domain)
    return drawn


def draw(state: GameState) -> str | None:
    """Draw 1; an empty deck is a Burn Out and the draw still happens (315.4)."""
    p = state.player(state.active)
    if not p.deck:
        p.burned_out = True
        return None
    card = p.deck.pop(0)
    p.hand.append(card)
    return card.name


def enter_main(state: GameState) -> None:
    """Pools empty at the start of Main; only the turn player may act."""
    for p in state.players:
        p.pool.clear()
    state.phase = MAIN
    state.priority = state.active
    state.focus = None


def ending(state: GameState) -> None:
    """Heal all units, expire 'this turn' effects, empty pools (317.2)."""
    for perm in state.permanents:
        perm.damage = 0
    for p in state.players:
        p.pool.clear()
    state.phase = ENDING
    state.priority = None
    state.focus = None


def start_turn(state: GameState) -> list[str]:
    """Run Awaken through Draw, then open the Main Phase.

    The extra rune on the second player's first turn (485.7) is applied here.
    """
    log: list[str] = []
    state.phase = AWAKEN
    awaken(state)

    state.phase = BEGINNING
    log.extend(beginning(state))
    if state.winner is not None:
        return log

    state.phase = CHANNEL
    second_players_first_turn = state.active == 1 and state.turn == 1
    got = channel(state, extra=1 if second_players_first_turn else 0)
    log.append(f"channelled {', '.join(got) if got else 'nothing (rune deck empty)'}")

    state.phase = DRAW
    drawn = draw(state)
    log.append(f"drew {drawn}" if drawn else "BURNED OUT (empty Main Deck)")

    enter_main(state)
    return log


def end_turn(state: GameState) -> None:
    ending(state)
    if state.active == 1:
        state.turn += 1
    state.active = 1 - state.active
