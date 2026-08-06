"""`view_for(state, seat)` — the only channel between engine and pilot.

Every private zone belonging to the other seat is reduced to a count here. This
is the one function that has to be right for the simulation to mean anything:
if it leaks, both pilots are playing open-handed and no result transfers to a
real game. See sim/PLAYFIELD.md.
"""

from __future__ import annotations

from .actions import Action, legal_actions, unplayable_reason
from .cards import Card
from .state import VICTORY_SCORE, Battlefield, GameState, Permanent


def _perm_line(p: Permanent) -> str:
    bits = [f"{p.might} might", "ready" if p.ready else "exhausted"]
    if p.damage:
        bits.append(f"{p.damage} dmg")
    if p.temporary:
        bits.append("Temporary")
    return f"{p.card.name} ({', '.join(bits)})"


def _side(state: GameState, key: str, seat: int, indent: str = "     ") -> list[str]:
    out = []
    for label, who in (("you", seat), ("opp", 1 - seat)):
        perms = state.at(key, who)
        if perms:
            out.append(f"{indent}{label}: {_perm_line(perms[0])}")
            out.extend(f"{indent}     {_perm_line(p)}" for p in perms[1:])
        else:
            out.append(f"{indent}{label}: —")
    return out


def _facedown(bf: Battlefield, seat: int) -> str:
    if bf.facedown is None:
        return "empty"
    owner, card = bf.facedown
    # Facedown cards are private even though the zone is public (107.3.f).
    return f"your {card.name}" if owner == seat else "opp has 1 card facedown here"


def _control(bf: Battlefield, seat: int) -> str:
    if bf.controller is None:
        return "none"
    return "YOU" if bf.controller == seat else "OPP"


def view_for(state: GameState, seat: int,
             actions: list[Action] | None = None) -> str:
    me, opp = state.player(seat), state.opponent_of(seat)
    actions = legal_actions(state, seat) if actions is None else actions
    L: list[str] = []
    A = L.append

    who = "YOU" if state.active == seat else "OPP"
    A(f"=== RIFTBOUND | game {state.game_id} | turn {state.turn} "
      f"| active: {who} | phase: {state.phase} ===")
    A(f"STATE    {state.state_name}")
    A(f"         playable now: {state.timing_note()}")
    A(f"SCORE    you {me.points}  |  opp {opp.points}"
      f"          (first to {VICTORY_SCORE} wins)")
    if state.chain:
        A("CHAIN    (top resolves first)")
        for i, item in enumerate(reversed(state.chain), 1):
            owner = "you" if item.controller == seat else "opp"
            A(f"  {i}. [{owner}] {item.source.name} — {item.description}")
    else:
        A("CHAIN    (empty)")
    A(f"PRIORITY {_seat_label(state.priority, seat)}")
    A(f"FOCUS    {_seat_label(state.focus, seat)}")
    A("")

    A("--- BATTLEFIELDS ---")
    for bf in state.battlefields:
        A(f"[B{bf.index + 1}] {bf.card.name:<34} control: {_control(bf, seat)}"
          f"  contested: {'yes' if bf.contested else 'no'}")
        L.extend(_side(state, bf.key, seat))
        A(f"     facedown: {_facedown(bf, seat)}")
    A("")

    A("--- YOUR BASE ---")
    L.extend(_base_block(state, seat, seat))
    A("")
    A("--- OPPONENT BASE ---")
    L.extend(_base_block(state, 1 - seat, seat))
    A("")

    A(f"--- YOUR HAND ({len(me.hand)}) ---")
    if not me.hand:
        A("  (empty)")
    for card in sorted(me.hand, key=lambda c: (c.energy, c.name)):
        reason = unplayable_reason(state, me, card)
        mark = "✓" if reason is None else "✗"
        might = f"{card.might} might  " if card.might is not None else ""
        A(f"  {mark} {card.name}  ·  {card.cost_str()}  ·  {card.type}  ·  "
          f"{card.timing_label()}  {might}")
        if card.text:
            A(f"      {card.text}")
        if reason:
            A(f"      ✗ {reason}")
    A("")

    A("--- TRASH ---")
    A(f"you ({len(me.trash)}):  {_names(me.trash)}")
    A(f"opp ({len(opp.trash)}):  {_names(opp.trash)}")
    A("")
    A(f"--- DECKS ---")
    A(f"you {len(me.deck)} remaining | opp {len(opp.deck)} remaining "
      f"| opp hand {len(opp.hand)}")
    A("")

    A("--- LEGAL ACTIONS ---")
    for i, act in enumerate(actions, 1):
        A(f"{i:3d}. {act.render()}")
    return "\n".join(L)


def _seat_label(value: int | None, seat: int) -> str:
    if value is None:
        return "none"
    return "you" if value == seat else "opp"


def _base_block(state: GameState, owner: int, viewer: int) -> list[str]:
    p = state.player(owner)
    key = f"base:{owner}"
    ready = len(p.ready_runes)
    out = [
        f"runes    ready {ready} | exhausted {len(p.runes) - ready} "
        f"| rune deck {len(p.rune_deck)}",
        f"pool     {p.pool.energy} energy, {p.pool.total_power()} power"
        + (f" ({_power_str(p.pool.power)})" if p.pool.total_power() else ""),
    ]
    units = [x for x in state.at(key, owner) if x.card.is_unit]
    gear = [x for x in state.at(key, owner) if x.card.is_gear]
    out.append(f"units    {'; '.join(_perm_line(u) for u in units) or '—'}")
    out.append(f"gear     {'; '.join(g.card.name for g in gear) or '—'}")
    out.append(f"legend   {p.legend.name}")
    out.append(f"champion {_champion_where(state, owner)}")
    return out


def _champion_where(state: GameState, seat: int) -> str:
    p = state.player(seat)
    if p.champion_in_zone:
        return "in Champion Zone (deployable, not drawn)"
    for perm in state.permanents:
        if perm.controller == seat and perm.card.name == p.champion.name:
            return f"in play at {perm.location}"
    return "in trash"


def _power_str(power: dict[str, int]) -> str:
    return ", ".join(f"{v} {d}" for d, v in sorted(power.items()) if v)


def _names(cards: list[Card]) -> str:
    return ", ".join(c.name for c in cards) if cards else "—"
