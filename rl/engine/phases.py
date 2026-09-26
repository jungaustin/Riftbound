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
                             GameState, bf_loc, fd_slots, is_battlefield)

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
    if table is not None:
        # Maduli the Gatekeeper -- "I can't be readied", Awaken included.
        from rl.engine.effects import NEVER_READIED
        for _i in np.flatnonzero(mine):
            if table.names[int(p[_i, P_CARD])] in NEVER_READIED:
                mine[_i] = False
    woke = np.flatnonzero(mine & (p[:, P_READY] == 0))
    p[mine, P_READY] = 1
    if table is not None and woke.size:
        from rl.engine.chain import fire_watchers
        from rl.engine.effects import TR_READIED
        for row in woke:
            fire_watchers(state, table, seat, TR_READIED, subj=int(row))


def temporary_expiring(state: GameState, table: CardTable) -> list[int]:
    """Rows of the turn player's permanents whose [Temporary] fires this turn.

    Split out of `expire_temporary` so the same filter can decide what to QUEUE
    (816 makes the expiry a triggered ability, so it goes on the Chain and can
    be responded to) and what to kill.
    """
    from rl.engine import combat
    seat = state.active
    out = []
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or row[P_CTRL] != seat:
            continue
        if not combat.perm_kw(state, table, i, "Temporary"):
            continue
        if state.is_attached(i) and table.has(int(row[P_CARD]), "Temporary"):
            if not combat.granted_kw(state, table, i, "Temporary"):
                continue
        loc = int(row[P_LOC])
        if is_battlefield(loc) and any(
                state.perms[j, P_ALIVE] == 1
                and int(state.perms[j, P_CTRL]) == seat
                and int(state.perms[j, P_LOC]) == loc
                and table.names[int(state.perms[j, P_CARD])]
                in TEMPORARY_SUPPRESSORS
                for j in range(state.n_perms)):
            continue
        out.append(i)
    return out


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
        # 718.2 -- an Attached card's printed Rules Text is Inactive, and 721.2
        # says Inactive abilities do not trigger. **722.2 uses this exact card
        # as its worked example**: "Spinning Axe is a gear with [Temporary].
        # While it's attached and its rules text is inactive, its [Temporary]
        # ability doesn't trigger."
        #
        # It has to be checked here and not in `perm_kw`, because 722.1 keeps
        # the KEYWORD visible -- the same paragraph goes on to say a spell
        # reading "destroy a gear with [Temporary]" can still choose it. The
        # keyword stays; only the expiry stops.
        #
        # A keyword GRANTED to the card is untouched by this: 135.4.b keeps
        # granted text Active while attached, so only the printed one sleeps.
        if state.is_attached(i) and table.has(int(row[P_CARD]), "Temporary"):
            if not combat.granted_kw(state, table, i, "Temporary"):
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
    for i in state.live_bfs():
        ctrl = int(state.bf_ctrl[i])
        if ctrl < 0 or state.showdown_bf == i:
            continue
        if not state.has_units_at(bf_loc(i), ctrl):
            state.bf_ctrl[i] = -1
            state.bf_contested[i] = 0
            # 107.3.d -- facedown cards go with the battlefield. Every slot
            # of it: Bandle Tree holds two.
            for k in fd_slots(i):
                if state.fd_owner[k] >= 0:
                    _to_trash(state, int(state.fd_owner[k]),
                              int(state.fd_card[k]))
                    state.fd_owner[k] = -1
                    state.fd_card[k] = -1
                    state.fd_ply[k] = -1
            lost.append(i)
    return lost


def _to_trash(state: GameState, seat: int, card: int,
              from_deck: bool = False) -> None:
    if int(state.riches_on[seat]) and not from_deck:
        state.banish_card(seat, card)       # Endless Riches
        return
    n = int(state.n_trash[seat])
    assert n < state.trash.shape[1], "trash overflow"
    state.trash[seat, n] = card
    state.n_trash[seat] = n + 1


def _return_on_hold(state: GameState, seat: int) -> None:
    """Ashe - Focused: "When they hold, return it to their hand" -- every card
    banished that way comes back out of Banishment at this seat's hold."""
    for k in range(int(state.n_hold_return[seat])):
        card = int(state.hold_return[seat, k])
        n = int(state.n_banished[seat])
        idx = [i for i in range(n) if int(state.banished[seat, i]) == card]
        if not idx:
            continue
        j = idx[-1]
        state.banished[seat, j:n - 1] = state.banished[seat, j + 1:n].copy()
        state.banished[seat, n - 1] = -1
        state.n_banished[seat] = n - 1
        h = int(state.n_hand[seat])
        if h < state.hand.shape[1]:
            state.hand[seat, h] = card
            state.n_hand[seat] = h + 1
        else:
            state.banish_card(seat, card)
    state.hold_return[seat, :] = -1
    state.n_hold_return[seat] = 0


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
    from rl.engine.chain import queue as chain_queue
    from rl.engine.effects import TR_HOLD
    seat = state.active
    gained = 0
    for i in state.live_bfs():
        if state.bf_ctrl[i] == seat and not state.bf_scored[seat, i]:
            state.bf_scored[seat, i] = 1
            _return_on_hold(state, int(seat))
            if combat.early_score_draws(state, table):
                draw_for(state, int(seat), 1)          # Otterpus
            elif combat.score_blocked_here(state, table, int(seat), i):
                pass                                   # Forgotten Monument
            else:
                gained += POINTS_PER_HOLD
            # "When I hold" fires for the units standing there, not for the
            # player -- Trevor Snoozebottom garrisons the battlefield he is
            # already holding.
            if table is not None:
                # `row_abilities`, not the card's: an attached Equipment's
                # "When I hold" is the UNIT's (718.3), and a card-level check
                # never saw it -- Trinity Force scored nothing in a real game.
                from rl.engine.effects import row_abilities, EXTRA_HOLD_HERE
                times = 1 + sum(
                    1 for u in state.units_at(bf_loc(i), seat)
                    if table.names[int(state.perms[u, P_CARD])] in EXTRA_HOLD_HERE)
                from rl.engine.effects import HOLD_CONQUER_SWAP, TR_CONQUER
                for u in state.units_at(bf_loc(i), seat):
                    if any(a.trigger == TR_HOLD
                           for a in row_abilities(state, table, int(u))):
                        for _ in range(times):     # Blue Sentinel
                            chain_queue(state, TR_HOLD, int(u), bf_loc(i))
                    # Skyfall of Areion: conquer effects are hold effects too.
                    if any(table.names[int(state.perms[g, P_CARD])]
                           in HOLD_CONQUER_SWAP
                           for g in state.attachments(int(u))) and any(
                            a.trigger == TR_CONQUER
                            for a in row_abilities(state, table, int(u))):
                        chain_queue(state, TR_CONQUER, int(u), bf_loc(i))
                # "When you hold here" is printed on the ground itself, and so
                # fires once for the holder rather than once per unit -- and
                # fires even when nothing is standing there. It cannot be:
                # holding requires units (190.4.c), which is what makes the
                # empty case unreachable rather than merely unlikely.
                for _ in range(times):
                    combat._queue_bf_trigger(state, table, TR_HOLD, i, int(seat))
                # ...and the LEGEND's "when you hold", once for the player.
                from rl.engine.chain import fire_legend
                for _ in range(times):
                    fire_legend(state, table, int(seat), TR_HOLD, bf_loc(i))
                # [Deploy] -- "When an opponent holds here, kill this." Fires
                # for the permanents of the seat that just LOST this ground,
                # which is why it cannot ride TR_HOLD: every queue above is
                # for the SCORING seat's own cards.
                from rl.engine.effects import TR_ENEMY_HOLDS_HERE
                for g in range(int(state.n_perms)):
                    if (state.perms[g, P_ALIVE] == 1
                            and int(state.perms[g, P_LOC]) == bf_loc(i)
                            and int(state.perms[g, P_CTRL]) != seat
                            and any(a.trigger == TR_ENEMY_HOLDS_HERE
                                    for a in row_abilities(state, table, int(g)))):
                        chain_queue(state, TR_ENEMY_HOLDS_HERE, int(g), bf_loc(i))
    if gained and table is not None and combat.points_blocked(state, table, int(seat)):
        gained = 0                                  # Tianna Crownguard
    if gained:
        if int(state.hold_points_ply[seat]) != int(state.ply):
            state.hold_points_ply[seat] = int(state.ply)
            state.hold_points[seat] = 0
        state.hold_points[seat] += gained
    if gained:
        state.points[seat] += gained
        # "When an opponent scores" -- one of the three sites that award a
        # point, and the only one on the Hold side.
        if table is not None:
            from rl.engine.chain import fire_watchers
            from rl.engine.effects import TR_OPPONENT_SCORES
            fire_watchers(state, table, 1 - seat, TR_OPPONENT_SCORES)
    if state.winner < 0:            # an OP_WIN stands
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
        from rl.engine.chain import fire_discarded, fire_watchers
        from rl.engine.effects import TR_DISCARD
        fire_watchers(state, table, seat, TR_DISCARD)
        fire_discarded(state, table, seat, out)
    return out


def burn_out(state: GameState, seat: int) -> dict:
    """431.2 -- what actually happens when a player cannot draw.

    This used to be `state.burned_out[seat] = 1` and nothing else. The flag was
    set, exposed to the observation, and read by no rule: a player who emptied
    their deck simply stopped drawing, for free and for the rest of the game.
    Both of the consequences that make decking a real cost were missing.

      431.2.b  the trash is recycled into the Main Deck, RANDOMIZED
      431.2.c  an opponent gains 1 point -- forced at two seats

    431.2.d then completes the action that caused it, which is why `draw`
    retries rather than giving up.

    No win check here. 431.3.c.1 says the point can win the game immediately,
    and it does -- through the same `check_winner` every other scoring path
    uses. Calling it here as well would score the game from inside a draw,
    which is the one place the rest of the engine assumes it never happens.

    Repeated burn-outs terminate by 431.3.a: each one hands over a point, so an
    empty deck AND trash runs the opponent to the Victory Score rather than
    looping forever.
    """
    state.burned_out[seat] = 1
    n = int(state.n_trash[seat])
    cards = [int(c) for c in state.trash[seat, :n]]
    state.trash[seat, :n] = -1
    state.n_trash[seat] = 0
    # 431.2.b's reminder is explicit that simultaneous recycles are randomized,
    # and it matters: an ordered recycle would make the trash a tutor.
    #
    # A state built directly (a test fixture) has no `rng` -- only `new_game`
    # sets one -- so fall back to a fixed generator rather than crashing. A
    # real game always brings its own seeded rng, so replay determinism is
    # unaffected either way.
    rng = state.rng if state.rng is not None else np.random.default_rng(0)
    rng.shuffle(cards)
    for c in cards:
        state.recycle_card(seat, c)
    state.points[1 - seat] += 1
    return {"burned_out": seat, "burn_recycled": len(cards)}


def burn(state: GameState, seat: int, n: int) -> list[int]:
    """[Burn N] -- put the top N of `seat`'s Main Deck into their trash.

    Self-mill, and the one keyword that can hand an opponent a point: running
    the deck out mid-burn is a Burn Out (431.2) exactly as running it out
    mid-draw is, so this takes the same path rather than silently milling zero.

    Shared by `OP_BURN` and by the "you may [Burn 1] to ..." optional cost,
    because a burn paid as a cost is the same game action as a burn performed
    as an effect.
    """
    milled: list[int] = []
    for _ in range(n):
        ptr = int(state.deck_ptr[seat])
        if ptr >= int(state.n_deck[seat]):
            burn_out(state, seat)
            ptr = int(state.deck_ptr[seat])
            if ptr >= int(state.n_deck[seat]):
                continue
        card = int(state.deck[seat, ptr])
        state.deck_ptr[seat] = ptr + 1
        _to_trash(state, seat, card, from_deck=True)
        milled.append(card)
    return milled


def draw(state: GameState, n: int = 1) -> list[int]:
    """Draw n; an empty Main Deck is a Burn Out and the draw still happens (315.4)."""
    seat = state.active
    drawn = []
    for _ in range(n):
        ptr = int(state.deck_ptr[seat])
        if ptr >= int(state.n_deck[seat]):
            burn_out(state, seat)
            ptr = int(state.deck_ptr[seat])
            if ptr >= int(state.n_deck[seat]):
                # Deck AND trash both empty, so 431.2.d has nothing to
                # complete. `continue`, not `break`: 431.3.a is explicit that
                # the player burns out REPEATEDLY, one point to an opponent
                # each time, so "draw 3" into an empty deck and trash hands
                # over three. Still bounded -- the loop runs `n` times, and
                # 431.3.a's own termination is the opponent reaching the
                # Victory Score.
                continue
        card = int(state.deck[seat, ptr])
        state.deck_ptr[seat] = ptr + 1
        h = int(state.n_hand[seat])
        assert h < state.hand.shape[1], "hand overflow"
        state.hand[seat, h] = card
        state.n_hand[seat] = h + 1
        drawn.append(card)
        if int(state.draw_ply[seat]) != int(state.ply):
            state.draw_ply[seat] = int(state.ply)
            state.draw_count[seat] = 0
        state.draw_count[seat] += 1
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
    # Blue Sentinel's promise lands after the pools empty (167), or it would
    # be wiped the instant it arrived.
    from rl.engine.state import D_ANY
    _seat = int(state.active)
    if int(state.pending_add_any[_seat]):
        state.pool_power[_seat, D_ANY] += int(state.pending_add_any[_seat])
        state.pending_add_any[_seat] = 0
    if table is not None:
        # "At the start of your Main Phase" -- queued here, placed by the
        # action layer's settle like every other trigger.
        from rl.engine.chain import queue as _q
        from rl.engine.effects import TR_MAIN_START, row_abilities
        for _i in range(state.n_perms):
            if (state.perms[_i, P_ALIVE] == 1
                    and int(state.perms[_i, P_CTRL]) == _seat
                    and any(a.trigger == TR_MAIN_START
                            for a in row_abilities(state, table, _i))):
                _q(state, TR_MAIN_START, _i, int(state.perms[_i, P_LOC]))
    state.phase = MAIN
    # **That Cleanup can open a Showdown, and the Showdown owns priority.**
    # 345/464.2.d hand both priority and Focus to the seat that applied
    # Contested, which `open_showdown` has just done -- so overwriting them
    # with the Main-Phase defaults is not a reset, it is a corruption. It left
    # `focus` at -1 with a Showdown live, `chain.after_resolution` then flipped
    # -1 to 2 and back to -1 forever, and `acting_seat` returned -1: a position
    # that is not terminal and that nobody can act in. The driver loop exits,
    # and the game is scored as undecided with no truncation to show for it.
    if state.showdown_bf < 0:
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


def _end_of_turn_reversals(state: GameState) -> None:
    """"...at end of turn" undos armed this turn (`GameState.eot_kind`).

    Sanction / Tornado Warrior flip Empowered back; Hostile Takeover hands a
    unit back to its OWNER and recalls it to their base (a recall, not a move).
    An Empower restored here does not fire "when I become Empowered" watchers:
    the Ending Phase has no priority window left to resolve them in.
    """
    from rl.engine.state import (EOT_DISEMPOWER, EOT_EMPOWER,
                                 EOT_REVERT_CONTROL, F_EMPOWERED, P_EMPOWER,
                                 P_OWNER, base_loc)
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1 or int(state.eot_ply[i]) != int(state.ply):
            continue
        kind = int(state.eot_kind[i])
        if kind == EOT_DISEMPOWER:
            state.disempower(i)
        elif kind == EOT_EMPOWER and not state.empower_count(i):
            state.perms[i, P_EMPOWER] += 1
            state.set_flag(i, F_EMPOWERED)
        elif kind == EOT_REVERT_CONTROL:
            owner = int(state.perms[i, P_OWNER])
            state.perms[i, P_CTRL] = owner
            state.set_location(i, base_loc(owner))
        state.eot_ply[i] = -1


def ending(state: GameState) -> None:
    """Heal all units, expire 'this turn' effects, empty pools (317.2).

    Stun clears here specifically -- 423.1.a.2, "step 3d of the end of turn
    cleanup" -- and this runs at the end of EVERY turn, so a Stun only ever
    blanks a unit for the turn it was applied on. It is a combat trick with a
    one-turn window, not a lasting debuff: stun on your turn to survive your own
    attack, or at Action speed on theirs to blank an attacker mid-Showdown.
    """
    # Delayed "ready N runes at the end of this turn" (Targon's Peak), paid
    # out before the pools empty. Both seats, not just the turn player: a
    # Reaction can start a Combat on the opponent's turn, so the promise can
    # belong to whoever is not taking it.
    for _seat in range(N_SEATS):
        _owed = int(state.pending_ready_runes[_seat])
        if _owed:
            state.pending_ready_runes[_seat] = 0
            for _dom in np.argsort(-state.runes_spent[_seat]):
                if _owed <= 0:
                    break
                _take = min(_owed, int(state.runes_spent[_seat, _dom]))
                state.runes_spent[_seat, _dom] -= _take
                state.runes_ready[_seat, _dom] += _take
                _owed -= _take
    # 317.1 before 317.2.b -- "at end of turn" happens in the Ending Step, and
    # the heal is the Expiration Step's. `fire_end_of_turn` normally applies
    # these already (with a lethal check); this is the fallback for a caller
    # that ends a turn without it.
    _end_of_turn_reversals(state)
    heal_board(state)
    if state.n_perms:
        state.perms[:state.n_perms, P_FLAGS] &= ~TURN_SCOPED_FLAGS
        state.perms[:state.n_perms, P_MIGHT_MOD] = 0   # 'this turn' buffs
    state.no_spells[:] = 0          # 'this turn' play restrictions
    state.no_cards[:] = 0           # ...and the wider one
    # 390.2 -- a Delayed Ability is active only for its stated window, and
    # every one in the pool so far says "this turn". 359.3.e.16 is the matching
    # rule from the other side: a delayed ability whose duration has already
    # ended does not fire.
    state.delayed[:, :] = -1
    state.cards_played[:] = 0       # [Legion] counts within one turn
    state.cards_completed[:] = 0    # ...and so do "your Nth card" triggers
    state.spells_played[:] = 0      # ...and so does Crumbling Sands
    state.next_spell_discount[:] = 0  # ...and Raging Firebrand's promise
    state.next_discount[:, :] = 0   # ...and so does the Heron's promise
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
    from rl.engine import combat
    from rl.engine.chain import fire_watchers
    from rl.engine.effects import TR_BEGINNING
    fire_watchers(state, table, int(state.active), TR_BEGINNING)
    # ...and the battlefields, which watch the phase for the turn player the
    # same way a permanent does. "At the start of EACH player's Beginning
    # Phase" needs no side clause: this runs once per turn, for whoever is
    # taking it, so both players are covered by both of their turns.
    for _i in state.live_bfs():
        combat._queue_bf_trigger(state, table, TR_BEGINNING, _i,
                                 int(state.active))
    # The legend's own "at the start of your Beginning Phase" (Jinx - Loose
    # Cannon) is already queued: `fire_watchers` above asks the champion after
    # the permanents. Queueing it again here drew her two cards.

    # 816 -- [Temporary] is a triggered ability ("kill me at the start of my
    # controller's Beginning Phase, before scoring"), so it goes on the Chain
    # with a real priority window rather than expiring silently: FAQ #6571 /
    # #5523 let a player answer a Sprite's expiry (RiftJudge #12570). The kill
    # itself happens when the Chain Item resolves, which is still before the
    # Scoring Step -- `resume_turn` runs that only once the Chain is empty.
    #
    # `expire_temporary` stays as the fallback: nothing triggers while
    # `units_only` is set (v0's whole claim), and a permanent that is GIVEN
    # [Temporary] during the response window has no trigger of its own.
    if not cfg.units_only:
        from rl.engine.effects import TR_TEMPORARY
        from rl.engine.chain import queue as _queue
        for _t in temporary_expiring(state, table):
            _queue(state, TR_TEMPORARY, _t, int(state.perms[_t, P_LOC]))

    # **315.2.a is a step, and 315.2.b is a LATER one.** Anything the Beginning
    # Step put on the Chain has to resolve -- through real priority windows --
    # before the Scoring Step runs. So if a trigger fired, the turn SUSPENDS
    # here and `actions._settle` resumes it once the Chain is empty.
    #
    # This used to run straight on to the scoring and let the trigger queue
    # drain afterwards, which put every start-of-Beginning ability *after* the
    # scoring it is printed to precede. Dusk Rose Lab is where that stops being
    # academic: "you may kill a unit you control here to draw 1 (this happens
    # before scoring)" banked the Hold and drew the card, when the whole cost
    # of the card is giving up the garrison to draw.
    #
    # Nothing suspends when nothing triggered, which is every turn in v0 --
    # so the goldens are untouched by this.
    if state.n_trig or state.n_chain:
        state.pend_phase = BEGINNING
        return log
    return resume_turn(state, table, cfg, log)


def resume_turn(state: GameState, table: CardTable, cfg: Config,
                log: dict | None = None) -> dict:
    """Finish a turn suspended in the Beginning Step (see `start_turn`).

    Called by `actions._settle` once the Chain and the trigger queue are both
    empty. Idempotent in the sense that matters: `pend_phase` is cleared first,
    so a Cleanup that runs during the Scoring Step cannot re-enter it.
    """
    log = {} if log is None else log
    state.pend_phase = -1
    state.phase = BEGINNING

    # Order matters -- see module docstring.
    #
    # v0 only. With triggers on, every [Temporary] that was on the board when
    # the Beginning Phase STARTED has already been queued and resolved, and
    # 816.1.c makes that start the whole trigger condition -- so a Sprite that
    # arrived in answer to the expiry (a hidden Sprite Call) does not expire
    # this turn and is there to Hold. Sweeping every Temporary here killed it
    # too (Austin's judge call A1).
    log["temporary_died"] = (expire_temporary(state, table) if cfg.units_only
                             else [])
    log["control_lost"] = control_cleanup(state)
    log["held"] = score_holds(state, cfg, table)
    if state.winner >= 0:
        return log

    state.phase = CHANNEL
    second_players_first_turn = state.active == 1 and state.turn == 1
    from rl.engine import combat as _cmb
    log["channelled"] = channel(
        state, extra=(cfg.second_player_bonus_runes if second_players_first_turn
                      else 0) + _cmb.channel_count(state, table) - 2)

    state.phase = DRAW
    # Endless Riches: "Skip your Draw Phase."
    log["drew"] = [] if int(state.riches_on[state.active]) else draw(state)

    enter_main(state, table, cfg)
    return log


def fire_end_of_turn(state: GameState, table: CardTable) -> None:
    """Queue "at the end of your turn" abilities for the turn player (317).

    **Not fired inside `end_turn`, and that is the whole shape of it.** These
    are triggered abilities, so 383.3 puts them on the Chain with a priority
    window -- but `end_turn` runs straight into `compact_permanents`, which
    asserts the trigger queue is empty because compaction repoints the very
    rows a queued trigger holds. Draining inline would skip the window; leaving
    them queued trips the assert.

    So the Ending Phase splits the same way the Beginning Phase already does
    (315.2): this queues, the action layer drains the Chain through real
    priority, and `actions._resume_phase` runs the cleanup afterwards. The turn
    player's own turn is what "your turn" means, so nothing fires on the
    opponent's.

    A legend is not a permanent and has no row to walk, so it is asked
    separately -- the same split `_queue_bf_trigger` makes for battlefields.
    """
    from rl.engine import combat
    from rl.engine.chain import fire_watchers
    from rl.engine.effects import TR_END_OF_TURN
    seat = int(state.active)
    # "Disempower it at end of turn" (Tornado Warrior, Sanction) and Hostile
    # Takeover's hand-back are Ending Step effects (317.1), so they land
    # BEFORE the Expiration Step heals (317.2.b). Damage marked outside combat
    # is still there, so a Steel Paws losing its +7 dies to the 2 a Shuriken
    # Flip left on it (Austin's judge call A3) -- and 143.2.a is checked now,
    # while any Deathknell it fires can still use this step's Chain.
    _end_of_turn_reversals(state)
    combat.enforce_lethal(state, table)
    # The legend is asked inside `fire_watchers` now (it walks the seat's
    # permanents and then its champion), so this is one call and not two --
    # it used to queue Annie - Dark Child a second time here, and she readied
    # four runes instead of two.
    fire_watchers(state, table, seat, TR_END_OF_TURN)


def end_turn(state: GameState, cfg: Config, table: CardTable | None = None) -> None:
    ending(state)
    control_cleanup(state)
    # Reclaim dead permanent rows. Only safe here: the turn ends in a Neutral
    # Open State, so nothing outside `perms` is holding a row index. See
    # `GameState.compact_permanents`.
    state.compact_permanents()
    state.ply += 1
    if int(state.extra_turns[state.active]) > 0:
        # Time Warp -- "Take a turn after this one": the same player goes
        # again, and the round does not advance.
        state.extra_turns[state.active] -= 1
    else:
        if state.active == 1:
            state.turn += 1
        state.active = 1 - state.active
    if state.turn > cfg.turn_cap:
        state.truncated = True
