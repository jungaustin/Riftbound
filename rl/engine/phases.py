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
from rl.engine.effects import TEMPORARY_SUPPRESSORS
from rl.engine.state import (AWAKEN, BEGINNING, CHANNEL, DRAW, ENDING, MAIN,
                             N_BF, N_SEATS, P_ALIVE, P_CARD, P_CTRL, P_DMG,
                             P_FLAGS, P_LOC, P_MIGHT_MOD, P_READY,
                             TURN_SCOPED_FLAGS,
                             GameState, bf_loc, is_battlefield)

POINTS_PER_HOLD = 1     # some battlefields alter this; per-battlefield later
POINTS_PER_CONQUER = 1  # confirmed: Conquer is always 1


def awaken(state: GameState, table: CardTable | None = None) -> None:
    """Turn player readies everything they control (315.1.b).

    Awaken DOES count as readying, so "when you ready a friendly unit" fires
    here -- once per unit that was actually exhausted. The board is readied in
    one vectorised write, so the transition has to be captured before it: a
    unit that was already ready has not become ready, and firing for it would
    turn Pirate's Haven into a flat per-unit pump every turn.
    """
    seat = state.active
    state.runes_ready[seat] += state.runes_spent[seat]
    state.runes_spent[seat] = 0
    # 315.1.b readies "all GAME OBJECTS they control that are able to be
    # readied", and the Champion Legend is a Game Object (107.4.c) even though
    # it is not a Permanent (175). So the Exhaust ability nearly every legend
    # prints recharges once a turn, which is what makes it an engine rather
    # than a one-shot. Before the early return: a player with an empty board
    # still has a legend.
    state.legend_ready[seat] = 1
    p = state.perms[:state.n_perms]
    if not state.n_perms:
        return
    mine = (p[:, P_ALIVE] == 1) & (p[:, P_CTRL] == seat)
    woke = np.flatnonzero(mine & (p[:, P_READY] == 0))
    p[mine, P_READY] = 1
    if table is not None and woke.size:
        from rl.engine.chain import fire_watchers
        from rl.engine.effects import TR_READIED
        for row in woke:
            fire_watchers(state, table, seat, TR_READIED, subj=int(row))


def expire_temporary(state: GameState, table: CardTable) -> list[int]:
    """Kill the turn player's [Temporary] permanents (start of Beginning,
    pre-scoring).

    Reminder text: "Kill it at the start of its controller's Beginning Phase,
    before scoring."

    Routed through `combat._destroy` rather than clearing P_ALIVE inline. This
    used to blank the row directly, which was invisible while the only
    [Temporary] things were tokens -- 185.3 makes a token cease to exist, so
    there was nothing to trash and nothing to trigger. A [Temporary] CARD is
    different: Sprite Fountain expires every Beginning Phase and its
    [Deathknell] is the whole engine of the deck, and the card belongs in the
    trash afterwards.
    """
    from rl.engine import combat
    seat = state.active
    killed = []
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or row[P_CTRL] != seat:
            continue
        # Through `perm_kw`, so a unit GIVEN [Temporary] (Shadow's Call,
        # Fading Memories) expires exactly like one printed with it.
        if not combat.perm_kw(state, table, i, "Temporary"):
            continue
        # LeBlanc - Everywhere At Once suppresses the expiry for the turn
        # player's own Temporary permanents standing at her battlefield. A
        # base does not count -- the card says "my BATTLEFIELD".
        loc = int(row[P_LOC])
        if is_battlefield(loc) and any(
                state.perms[j, P_ALIVE] == 1
                and int(state.perms[j, P_CTRL]) == seat
                and int(state.perms[j, P_LOC]) == loc
                and table.names[int(state.perms[j, P_CARD])]
                in TEMPORARY_SUPPRESSORS
                for j in range(state.n_perms)):
            continue
        combat._destroy(state, table, i)
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


def score_holds(state: GameState, cfg: Config, table: CardTable | None = None) -> int:
    """Scoring Step -- the turn player Holds each battlefield they control.

    Scores for battlefields ALREADY controlled at the start of your turn
    (315.2.b.2); taking one on your own turn scores via Conquer instead.

    Rule 469.2 restricts this to Battlefields "they did not yet Score this
    turn", and 470 caps a player at one Score per Battlefield per turn by either
    method. The flag matters even at the Beginning Phase, because it is what
    stops a Battlefield lost and retaken later in the same turn from paying
    twice.
    """
    from rl.engine import combat
    from rl.engine.chain import has_trigger, queue as chain_queue
    from rl.engine.effects import TR_HOLD
    seat = state.active
    gained = 0
    for i in range(N_BF):
        if state.bf_ctrl[i] == seat and not state.bf_scored[seat, i]:
            state.bf_scored[seat, i] = 1
            gained += POINTS_PER_HOLD
            # "When I hold" fires for the units standing there, not for the
            # player -- Trevor Snoozebottom garrisons the battlefield he is
            # already holding.
            if table is not None:
                for u in state.units_at(bf_loc(i), seat):
                    if has_trigger(table, int(state.perms[u, P_CARD]), TR_HOLD):
                        chain_queue(state, TR_HOLD, int(u), bf_loc(i))
                # "When you hold here" is printed on the ground itself, and so
                # fires once for the holder rather than once per unit -- and
                # fires even when nothing is standing there. It cannot be:
                # holding requires units (190.4.c), which is what makes the
                # empty case unreachable rather than merely unlikely.
                combat._queue_bf_trigger(state, table, TR_HOLD, i, int(seat))
    if gained:
        state.points[seat] += gained
        # "When an opponent scores" -- one of the three sites that award a
        # point, and the only one on the Hold side.
        if table is not None:
            from rl.engine.chain import fire_watchers
            from rl.engine.effects import TR_OPPONENT_SCORES
            fire_watchers(state, table, 1 - seat, TR_OPPONENT_SCORES)
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


def draw_for(state: GameState, seat: int, n: int = 1) -> list[int]:
    """Draw for a specific seat. `draw` is turn-player-only; the Final Point
    restriction (471.1.b) makes a non-turn-player draw possible."""
    prev = state.active
    state.active = seat
    try:
        return draw(state, n)
    finally:
        state.active = prev


def discard(state: GameState, table: CardTable, seat: int,
            n: int = 1) -> list[int]:
    """Discard `n` from `seat`'s hand, oldest first.

    Which card to discard is a real choice on many cards, but nothing in the
    pool yet lets the player pick -- Lunar Boon simply says "discard 1". Taking
    the oldest keeps it deterministic; the day a card says "discard a card of
    your choice" this becomes a decision point rather than a rule here.
    """
    out = []
    for _ in range(n):
        h = int(state.n_hand[seat])
        if h <= 0:
            break
        card = int(state.hand[seat, 0])
        state.hand[seat, 0:h - 1] = state.hand[seat, 1:h]
        state.hand[seat, h - 1] = -1
        state.n_hand[seat] = h - 1
        _to_trash(state, seat, card)
        out.append(card)
    # "When you discard ONE OR MORE cards" -- one trigger for the event, not
    # one per card, so this fires after the loop and only if anything moved.
    if out:
        from rl.engine.chain import fire_watchers
        from rl.engine.effects import TR_DISCARD
        fire_watchers(state, table, seat, TR_DISCARD)
    return out


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


def enter_main(state: GameState, table: CardTable | None = None,
               cfg: Config | None = None) -> None:
    """Pools empty at the start of Main (167); only the turn player may act.

    A Cleanup also happens here. A Combat can be *staged* (461) during the
    opponent's turn by a Reaction that moves a unit, and a Cleanup could not run
    at the time -- 321 forbids one while Chain Items are resolving. Nothing else
    would initiate it, so a staged combat could survive across the turn
    boundary. This is an Open State, which is where Cleanups belong.
    """
    if table is not None and cfg is not None:
        from rl.engine import combat
        combat.cleanup(state, table, cfg, mover=-1, dst=-1)
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


# 116 -- "Players each draw 4." This was 5, which is a Magic reflex rather than
# a Riftbound rule, and it made every opening hand 25% larger than the real one.
STARTING_HAND = 4
# 117.1 -- "A player may choose up to two cards in their hand."
MULLIGAN_MAX = 2


def mulligan(state: GameState, seat: int, indices) -> list[int]:
    """117 -- set aside up to two cards, draw that many, then Recycle them.

    **The order is set-aside -> draw -> recycle, and it is not cosmetic.**
    117.2 draws before 117.3 recycles, so the cards going to the bottom cannot
    be among the ones drawn to replace them. Recycling first would let a player
    redraw the exact card they just put back -- vanishingly unlikely with a full
    deck, certain with a nearly empty one, and wrong either way.

    Returns the card ids that were recycled.
    """
    idxs = sorted(set(int(i) for i in indices), reverse=True)
    assert len(idxs) <= MULLIGAN_MAX, (
        f"117.1 allows up to {MULLIGAN_MAX} cards, got {len(idxs)}")
    assert all(0 <= i < int(state.n_hand[seat]) for i in idxs), \
        "mulligan index outside the hand"

    # Set aside: out of the hand, but NOT yet into the deck.
    aside = []
    for i in idxs:
        n = int(state.n_hand[seat])
        aside.append(int(state.hand[seat, i]))
        state.hand[seat, i:n - 1] = state.hand[seat, i + 1:n]
        state.hand[seat, n - 1] = -1
        state.n_hand[seat] = n - 1

    prev, state.active = int(state.active), seat
    draw(state, len(aside))
    state.active = prev

    for card in aside:
        state.recycle_card(seat, card)
    return aside


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
    state.cards_played[:] = 0       # [Legion] counts within one turn
    state.played_types[:] = 0       # ...and so does Swain's trio
    state.died_in_beginning[:] = 0  # ...and Shadow Watcher's window
    state.any_damage_kills = 0      # ...and Imperial Decree
    if state.n_perms:
        state.kw_grant_turn[:state.n_perms] = 0   # "[Assault 3] this turn"
    state.clear_pools()
    state.phase = ENDING
    state.priority = -1
    state.focus = -1


def start_turn(state: GameState, table: CardTable, cfg: Config) -> dict:
    """Run Awaken through Draw, then open Main. Returns a small log dict."""
    log: dict = {}
    state.bf_scored[:] = 0   # rule 470 is per turn, and this is the new turn
    state.phase = AWAKEN
    awaken(state, table)

    state.phase = BEGINNING
    # "At the start of your Beginning Phase" -- fired before the [Temporary]
    # expiry and the Hold scoring, which is the order the phase runs in and the
    # order Sprite Queen depends on: her token arrives, then anything that
    # expires does.
    from rl.engine.chain import fire_watchers
    from rl.engine.effects import TR_BEGINNING
    fire_watchers(state, table, int(state.active), TR_BEGINNING)

    # Order matters -- see module docstring.
    log["temporary_died"] = expire_temporary(state, table)
    log["control_lost"] = control_cleanup(state)
    log["held"] = score_holds(state, cfg, table)
    if state.winner >= 0:
        return log

    state.phase = CHANNEL
    second_players_first_turn = state.active == 1 and state.turn == 1
    log["channelled"] = channel(
        state, extra=cfg.second_player_bonus_runes if second_players_first_turn else 0)

    state.phase = DRAW
    log["drew"] = draw(state)

    enter_main(state, table, cfg)
    return log


# TR_END_OF_TURN is DELIBERATELY not fired here. "At the end of your turn" is
# a triggered ability, so it belongs on the Chain with a priority window -- but
# `ending` runs straight into `compact_permanents`, which asserts no trigger is
# queued (compaction repoints the rows a queued trigger holds). Firing it here
# and draining it inline would skip the window; firing it and leaving it queued
# trips the assert. Doing it properly needs a pending end-of-turn state so the
# action layer can drain the Chain before the cleanup, which is a phase-machine
# change rather than a card. Sona, Harmonious is the only card waiting on it.
def end_turn(state: GameState, cfg: Config, table: CardTable | None = None) -> None:
    ending(state)
    control_cleanup(state)
    # Reclaim dead permanent rows. Only safe here: the turn ends in a Neutral
    # Open State, so nothing outside `perms` is holding a row index. See
    # `GameState.compact_permanents`.
    state.compact_permanents()
    state.ply += 1
    if state.active == 1:
        state.turn += 1
    state.active = 1 - state.active
    if state.turn > cfg.turn_cap:
        state.truncated = True
