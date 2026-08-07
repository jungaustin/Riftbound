"""Phase machine (rules 315-317) plus the two cleanups that ride on it.

The turn order is **ABCD** -- Awaken, Beginning-of-turn effects, Channel runes,
Draw -- then Main, then Ending.

`start_turn` runs all four without stopping, which is correct **only while no
trigger fires**. Rule 335 gives no priority outside the Main Phase when nothing
is on the Chain -- but 315.2.a.1 puts start-of-Beginning-Phase effects there, and
a pending Chain Item means a Closed State, which grants both players priority
(312.2.c/d). So any trigger during ABCD opens a window in which `[Reaction]`
cards -- and every live `[Hidden]` card, which gains `[Reaction]` and costs
nothing (811.1.b) -- can be played.

That lands squarely on the ordering below. Sprite Queen triggers at the start of
the Beginning Phase and Trevor Snoozebottom triggers on Hold; Sprite Call is a
free hidden reaction that replaces a garrison. So a `[Temporary]` board that
should evaporate before scoring can be re-garrisoned *in response to its own
expiry*. Keep the steps separable so a priority window drops in between any two
of them; v0 never uses one, but the Sprite package exists to break exactly this
assumption.

Two orderings in here are load-bearing and easy to get backwards:

  1. `[Temporary]` units die at the START of their controller's Beginning Phase,
     **before scoring**. Combined with 190.4.c (no units means no control), a
     board made only of Temporary tokens evaporates immediately before Hold would
     have scored. That is the conquer-vs-hold inversion, and implementing it in
     the wrong order silently hands token decks points they should never get.

  2. Hold scores in Beginning, which runs before Main. So a player banks the
     point BEFORE they get the chance to retreat during Main -- retreating costs
     the next turn's point, never the one just collected.
"""

from __future__ import annotations

import numpy as np

from rl.config import Config
from rl.engine.cardtable import CardTable
from rl.engine.state import (AWAKEN, BEGINNING, CHANNEL, DRAW, ENDING, MAIN,
                             N_BF, N_SEATS, P_ALIVE, P_CARD, P_CTRL, P_DMG,
                             P_FLAGS, P_LOC, P_MIGHT_MOD, P_READY,
                             TURN_SCOPED_FLAGS,
                             GameState, bf_loc)

POINTS_PER_HOLD = 1     # some battlefields alter this; per-battlefield later
POINTS_PER_CONQUER = 1  # confirmed: Conquer is always 1


def awaken(state: GameState) -> None:
    """Turn player readies everything they control (315.1.b)."""
    seat = state.active
    state.runes_ready[seat] += state.runes_spent[seat]
    state.runes_spent[seat] = 0
    p = state.perms[:state.n_perms]
    if state.n_perms:
        p[(p[:, P_ALIVE] == 1) & (p[:, P_CTRL] == seat), P_READY] = 1


def expire_temporary(state: GameState, table: CardTable) -> list[int]:
    """Kill the turn player's [Temporary] units (start of Beginning, pre-scoring).

    Reminder text: "Kill it at the start of its controller's Beginning Phase,
    before scoring."
    """
    seat = state.active
    killed = []
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or row[P_CTRL] != seat:
            continue
        if table.has(int(row[P_CARD]), "Temporary"):
            row[P_ALIVE] = 0
            killed.append(i)
    return killed


def control_cleanup(state: GameState) -> list[int]:
    """Rule 190.4.c -- lose Control of a battlefield you have no Units at.

    Only applies in an Open state and never while a Showdown or Combat is ongoing
    there. This is what makes "empty" and "uncontrolled" converge.
    """
    lost = []
    if not state.is_open:
        return lost
    for i in range(N_BF):
        ctrl = int(state.bf_ctrl[i])
        if ctrl < 0 or state.showdown_bf == i:
            continue
        if not state.has_units_at(bf_loc(i), ctrl):
            state.bf_ctrl[i] = -1
            state.bf_contested[i] = 0
            # 107.3.d -- facedown cards go with the battlefield.
            if state.fd_owner[i] >= 0:
                _to_trash(state, int(state.fd_owner[i]), int(state.fd_card[i]))
                state.fd_owner[i] = -1
                state.fd_card[i] = -1
                state.fd_ply[i] = -1
            lost.append(i)
    return lost


def _to_trash(state: GameState, seat: int, card: int) -> None:
    n = int(state.n_trash[seat])
    assert n < state.trash.shape[1], "trash overflow"
    state.trash[seat, n] = card
    state.n_trash[seat] = n + 1


def score_holds(state: GameState, cfg: Config) -> int:
    """Scoring Step -- the turn player Holds each battlefield they control.

    Scores for battlefields ALREADY controlled at the start of your turn
    (315.2.b.2); taking one on your own turn scores via Conquer instead.

    Rule 469.2 restricts this to Battlefields "they did not yet Score this
    turn", and 470 caps a player at one Score per Battlefield per turn by either
    method. The flag matters even at the Beginning Phase, because it is what
    stops a Battlefield lost and retaken later in the same turn from paying
    twice.
    """
    seat = state.active
    gained = 0
    for i in range(N_BF):
        if state.bf_ctrl[i] == seat and not state.bf_scored[seat, i]:
            state.bf_scored[seat, i] = 1
            gained += POINTS_PER_HOLD
    if gained:
        state.points[seat] += gained
    state.winner = state.check_winner(cfg.victory_score)
    return gained


def channel(state: GameState, extra: int = 0) -> list[int]:
    """Channel 2 runes, or as many as remain (315.3.b).

    An empty Rune Deck is not a loss condition -- it just means every rune is
    already on the board. Recycled runes come back through here, so a Power-heavy
    turn shows up as a smaller rune board two turns later rather than as a
    missed cast.
    """
    seat = state.active
    got = []
    for _ in range(2 + extra):
        dom = state.channel_one(seat)
        if dom < 0:
            break
        got.append(dom)
    return got


def draw(state: GameState, n: int = 1) -> list[int]:
    """Draw n; an empty Main Deck is a Burn Out and the draw still happens (315.4)."""
    seat = state.active
    drawn = []
    for _ in range(n):
        ptr = int(state.deck_ptr[seat])
        if ptr >= int(state.n_deck[seat]):
            state.burned_out[seat] = 1
            break
        card = int(state.deck[seat, ptr])
        state.deck_ptr[seat] = ptr + 1
        h = int(state.n_hand[seat])
        assert h < state.hand.shape[1], "hand overflow"
        state.hand[seat, h] = card
        state.n_hand[seat] = h + 1
        drawn.append(card)
    return drawn


def enter_main(state: GameState) -> None:
    """Pools empty at the start of Main (167); only the turn player may act."""
    state.clear_pools()
    state.phase = MAIN
    state.priority = state.active
    state.focus = -1


def heal_board(state: GameState) -> None:
    """Clear all marked damage everywhere.

    Runs at combat cleanup AND at end of turn. Board-wide, not limited to the
    contested battlefield -- an easy detail to get wrong, and the reason chip
    damage is worth exactly zero.
    """
    if state.n_perms:
        state.perms[:state.n_perms, P_DMG] = 0


def ending(state: GameState) -> None:
    """Heal all units, expire 'this turn' effects, empty pools (317.2).

    Stun clears here specifically -- 423.1.a.2, "step 3d of the end of turn
    cleanup" -- and this runs at the end of EVERY turn, so a Stun only ever
    blanks a unit for the turn it was applied on. It is a combat trick with a
    one-turn window, not a lasting debuff: stun on your turn to survive your own
    attack, or at Action speed on theirs to blank an attacker mid-Showdown.
    """
    heal_board(state)
    if state.n_perms:
        state.perms[:state.n_perms, P_FLAGS] &= ~TURN_SCOPED_FLAGS
        state.perms[:state.n_perms, P_MIGHT_MOD] = 0   # 'this turn' buffs
    state.no_spells[:] = 0          # 'this turn' play restrictions
    state.clear_pools()
    state.phase = ENDING
    state.priority = -1
    state.focus = -1


def start_turn(state: GameState, table: CardTable, cfg: Config) -> dict:
    """Run Awaken through Draw, then open Main. Returns a small log dict."""
    log: dict = {}
    state.bf_scored[:] = 0   # rule 470 is per turn, and this is the new turn
    state.phase = AWAKEN
    awaken(state)

    state.phase = BEGINNING
    # Order matters -- see module docstring.
    log["temporary_died"] = expire_temporary(state, table)
    log["control_lost"] = control_cleanup(state)
    log["held"] = score_holds(state, cfg)
    if state.winner >= 0:
        return log

    state.phase = CHANNEL
    second_players_first_turn = state.active == 1 and state.turn == 1
    log["channelled"] = channel(
        state, extra=cfg.second_player_bonus_runes if second_players_first_turn else 0)

    state.phase = DRAW
    log["drew"] = draw(state)

    enter_main(state)
    return log


def end_turn(state: GameState, cfg: Config) -> None:
    ending(state)
    control_cleanup(state)
    state.ply += 1
    if state.active == 1:
        state.turn += 1
    state.active = 1 - state.active
    if state.turn > cfg.turn_cap:
        state.truncated = True
