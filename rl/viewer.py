"""Text replay viewer -- PLAN.md Phase 2.3, the brief's M3.

Two jobs, and the second one is the important one.

**Debugging.** A 233-decision game that ends 8-6 is unreadable as a dict. This
renders it as a board plus an annotated decision log.

**A specification of what a policy may see.** `view()` takes a `seat` and shows
*only* what that seat legitimately knows: their own hand, both trashes, deck
counts but not deck contents, and the Facedown Zone as a public slot with a
private card (107.3.f) -- you see *that* a card is hidden and whose it is, never
which card, unless it is yours.

That makes this file the reference for the observation encoder. If the viewer
shows it at `seat`, the policy may encode it; if it does not, encoding it is an
information leak. Keeping the rule in one readable place beats rediscovering it
inside a tensor layout -- a leak there is invisible and inflates every result
that follows.

This used to note the value head as a deliberate exception that saw everything.
That is no longer the default: `value_sym` sees exactly what this viewer shows
and drives learning, while the privileged `value_priv` is a detached diagnostic
(`nets.RiftboundNet.values`). So the rule here now has no exception -- which is
the point, since a stale spec is how `play.py` came to call a method that no
longer existed.
"""

from __future__ import annotations

import numpy as np

from rl.config import DOMAINS, Config
from rl.engine import actions as A
from rl.engine import game
from rl.engine.cardtable import CardTable
from rl.engine.state import (F_STUNNED, N_BF, N_SEATS, P_ALIVE, P_CARD, P_CTRL,
                             P_DMG, P_FLAGS, P_LOC, P_READY, PHASE_NAMES,
                             GameState, base_loc, bf_index, bf_loc, fd_slots,
                             is_battlefield)


def _who(value: int, seat: int) -> str:
    if value < 0:
        return "none"
    return "you" if value == seat else "opp"


def _unit(state: GameState, table: CardTable, i: int) -> str:
    row = state.perms[i]
    card = int(row[P_CARD])
    bits = [f"{table.names[card]}", f"{int(table.might[card])}M"]
    bits.append("ready" if row[P_READY] else "exhausted")
    if row[P_DMG]:
        bits.append(f"{int(row[P_DMG])} dmg")
    if row[P_FLAGS] & F_STUNNED:
        bits.append("STUNNED")
    for kw in ("Tank", "Backline", "Temporary", "Ganking", "Shield"):
        if table.has(card, kw):
            bits.append(f"[{kw}]")
    return "  ".join(bits)


def _side(state: GameState, table: CardTable, loc: int, seat: int) -> list[str]:
    out = []
    for s in range(N_SEATS):
        idxs = state.units_at(loc, s)
        label = "you" if s == seat else "opp"
        if idxs.size:
            for i in idxs:
                out.append(f"       {label}: {_unit(state, table, int(i))}")
    return out or ["       (empty)"]


def _runes(state: GameState, seat: int) -> str:
    ready = state.runes_ready[seat]
    spent = state.runes_spent[seat]
    parts = [f"{DOMAINS[d][:2]}{int(ready[d])}/{int(ready[d] + spent[d])}"
             for d in range(len(DOMAINS)) if ready[d] or spent[d]]
    return (" ".join(parts) or "none") + f"   (deck {int(state.rune_left[seat])})"


def view(state: GameState, table: CardTable, cfg: Config, seat: int,
         actions=None) -> str:
    """The board as `seat` may legitimately see it."""
    L: list[str] = []
    P = L.append
    foe = 1 - seat

    active = "YOU" if state.active == seat else "OPP"
    P(f"=== turn {state.turn} | active {active} | "
      f"{PHASE_NAMES[state.phase]} ===")
    P(f"SCORE    you {int(state.points[seat])}  opp {int(state.points[foe])}"
      f"   (first to {cfg.victory_score})")
    st = ("Showdown" if state.showdown_bf >= 0 else "Neutral")
    P(f"STATE    {st} {'Closed' if not state.is_open else 'Open'}"
      f"   priority: {_who(int(state.priority), seat)}")
    if state.showdown_bf >= 0:
        P(f"         showdown at B{state.showdown_bf + 1}, "
          f"attacker: {_who(int(state.attacker), seat)}")
    if state.declaring:
        P(f"         declaring a move to "
          f"B{bf_index(state.decl_dst) + 1}: {state.declared()}")
    P("")

    P("--- BATTLEFIELDS ---")
    for i in state.live_bfs():
        card = int(state.bf_card[i])
        name = table.names[card] if card >= 0 else "?"
        scored = [s for s in range(N_SEATS) if state.bf_scored[s, i]]
        P(f"[B{i + 1}] {name:<32} control: {_who(int(state.bf_ctrl[i]), seat)}"
          f"  contested: {'yes' if state.bf_contested[i] else 'no'}"
          + (f"  scored: {[_who(s, seat) for s in scored]}" if scored else ""))
        L.extend(_side(state, table, bf_loc(i), seat))
        # 107.3.f: the zone is public, the card is not.
        shown = []
        for k in fd_slots(i):
            owner = int(state.fd_owner[k])
            if owner < 0:
                continue
            shown.append(table.names[int(state.fd_card[k])] if owner == seat
                         else "opponent's, face down")
        P(f"       facedown: {', '.join(shown) if shown else '-'}")
    P("")

    for s, label in ((seat, "YOUR BASE"), (foe, "OPPONENT BASE")):
        P(f"--- {label} ---")
        idxs = state.units_at(base_loc(s), s)
        if idxs.size:
            for i in idxs:
                P(f"       {_unit(state, table, int(i))}")
        else:
            P("       (empty)")
        P(f"       runes: {_runes(state, s)}")
    P("")

    n = int(state.n_hand[seat])
    P(f"--- YOUR HAND ({n}) ---")
    for j in range(n):
        c = int(state.hand[seat, j])
        pay = A.plan_payment(state, table, seat, c)
        mark = "+" if pay is not None else "-"
        cost = f"{int(table.energy[c])}E"
        if table.power[c]:
            cost += f"+{int(table.power[c])}P"
        might = f"  {int(table.might[c])}M" if table.might[c] >= 0 else ""
        P(f"  {mark} [{j}] {table.names[c]:<30} {cost}{might}")
    if not n:
        P("  (empty)")
    # Counts only -- never contents. This is the line most likely to be
    # loosened by accident, and doing so leaks hidden information.
    P(f"--- OPPONENT: {int(state.n_hand[foe])} cards in hand, "
      f"{int(state.n_deck[foe] - state.deck_ptr[foe])} in deck ---")
    P(f"--- YOUR DECK: {int(state.n_deck[seat] - state.deck_ptr[seat])} "
      f"| trash you {int(state.n_trash[seat])} opp {int(state.n_trash[foe])} ---")

    if actions is not None:
        P("")
        P("--- LEGAL ACTIONS ---")
        for k, act in enumerate(actions):
            P(f"  {k:3d}. {describe(act, state, table, seat)}")
    return "\n".join(L)


def describe(act, state: GameState, table: CardTable, seat: int) -> str:
    """One action, in words."""
    k, arg = act.kind, act.arg
    if k == A.A_PASS:
        return "pass"
    if k == A.A_END_TURN:
        return "end turn"
    if k == A.A_PLAY:
        if arg == A.CHAMPION_SRC:      # 108.3.d, from the Champion Zone
            return f"play {table.names[int(state.champion[seat])]} (champion)"
        return f"play {table.names[int(state.hand[seat, arg])]}"
    if k == A.A_PLAY_AT:
        return f"  ...to {_loc_name(arg, seat)}"
    if k == A.A_DECLARE:
        return f"declare move -> {_loc_name(arg, seat)}"
    if k == A.A_ADD:
        return f"  ...add {table.names[int(state.perms[arg, P_CARD])]}"
    if k == A.A_COMMIT:
        return "  ...COMMIT (units arrive, showdown if contested)"
    if k == A.A_CANCEL:
        return "  ...cancel"
    if k == A.A_RETREAT:
        return f"retreat {table.names[int(state.perms[arg, P_CARD])]} to base"
    return repr(act)


def _loc_name(loc: int, seat: int) -> str:
    """Relative to `seat`, who is the one acting -- so a transcript of both
    players reads consistently rather than flipping perspective each line."""
    if is_battlefield(loc):
        return f"B{bf_index(loc) + 1}"
    return "own base" if loc == base_loc(seat) else "enemy base"


def play_and_log(table: CardTable, cfg: Config, state: GameState, agents,
                 boards_every: int = 0) -> str:
    """Run a game, returning an annotated transcript.

    `boards_every` > 0 also dumps a full board view every N decisions, from the
    perspective of whoever is to act -- so the transcript never contains
    anything that seat could not see.
    """
    L: list[str] = []
    seen = (-1, -1)   # (turn, active) -- a new header only when either changes
    step = 0
    while not A.is_terminal(state):
        seat = A.acting_seat(state)
        if seat < 0:
            break
        legal = A.legal_actions(state, table, cfg, seat)
        if not legal:
            break

        if (state.turn, int(state.active)) != seen:
            seen = (state.turn, int(state.active))
            L.append(f"\n===== turn {state.turn} | "
                     f"seat {state.active} to move | "
                     f"score {state.points.tolist()} =====")

        if boards_every and step % boards_every == 0:
            L.append(view(state, table, cfg, seat, legal))

        act = agents[seat](state, table, cfg, seat, legal)
        before = state.points.copy()
        log = A.apply(state, table, cfg, act)
        L.append(f"  s{seat}: {describe(act, state, table, seat).strip()}")

        for note in _annotate(log, before, state):
            L.append(f"        -> {note}")
        step += 1

    L.append(f"\n===== result: "
             + ("draw/truncated" if state.winner < 0
                else f"seat {state.winner} wins")
             + f" {state.points.tolist()} in {state.turn} turns, "
               f"{step} decisions =====")
    return "\n".join(L)


def _annotate(log: dict, before: np.ndarray, state: GameState) -> list[str]:
    """Turn an engine log dict into readable consequences."""
    out = []
    if not isinstance(log, dict):
        return out
    if log.get("temporary_died"):
        out.append(f"[Temporary] units died: {len(log['temporary_died'])}")
    if log.get("control_lost"):
        out.append(f"lost control of {log['control_lost']} (no units, 190.4.c)")
    if log.get("held"):
        # `end turn` runs the NEXT player's start-of-turn, so a Hold logged
        # here belongs to whoever is active now, not to whoever just acted.
        out.append(f"seat {int(state.active)} HOLDS for {log['held']}")
    if log.get("drew") == []:
        out.append("BURNED OUT (empty deck)")
    if "combat_at" in log:
        for r in log.get("rounds", []):
            k = r.get("killed", ((), ()))
            out.append(f"combat at B{log['combat_at'] + 1}: pools "
                       f"{r.get('pools')}, killed {len(k[0])}/{len(k[1])}")
        if log.get("recalled"):
            out.append(f"attackers RECALLED ({len(log['recalled'])}) -- "
                       f"a defender survived (466.1.a.2)")
    for who, kind in log.get("scored", []):
        out.append(f"seat {who} CONQUERS (+1)")
    delta = state.points - before
    if delta.any():
        out.append(f"score {before.tolist()} -> {state.points.tolist()}")
    return out


if __name__ == "__main__":
    import sys
    from rl.agents.greedy import greedy_agent
    from rl.engine.cardtable import full_table
    from rl.tests.fuzz import make_game

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    tbl, conf = full_table(), Config().at_victory_score(8)
    g = make_game(tbl, conf, seed)
    rng = np.random.default_rng(seed)
    print(play_and_log(tbl, conf, g, [greedy_agent(rng), game.random_agent(rng)],
                       boards_every=0))
