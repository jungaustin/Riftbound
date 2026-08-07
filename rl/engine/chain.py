"""The Chain and the FEPR loop (rules 332-340).

**The Chain resolves one item at a time, and a priority window opens after every
single resolution.** That is the rule that makes response play deep rather than
flat: by 340.4, once an item resolves and the chain is still non-empty, the
controller of the *new* newest item gains priority. So a card played five items
ago becomes respondable the moment the items above it clear. Confirmed with the
project owner.

The loop, FEPR (334):

    F  Finalize   the OLDEST pending item -- choose targets, pay costs (337.1).
                  Finalizing does NOT pass priority (337.1.a).
    E  Execute    the player with priority may act.
    P  Pass       all players passing in sequence with nothing added -> Resolve
                  (339.1); otherwise priority moves on and we return to E (339.2).
    R  Resolve    the NEWEST finalized item resolves, alone (340.1). Then:
                  empty chain -> Open State (340.2); pending items -> back to F
                  (340.3); otherwise the controller of the newest item gains
                  priority and we return to E (340.4).

**337.2 is the rule that keeps v0 correct.** A finalized Unit, Gear, or
resource-adding ability resolves *immediately* and never waits on the chain, so
it cannot be responded to. That is why playing a unit resolves inline in
`actions._resolve_play` and why the units-only engine has no response windows at
all -- only spells create them.

**There is no second priority system.** A Showdown is not a separate mechanism;
342.1 says a spell played in a Showdown "creates a Chain as normal", so combat's
window is this loop running while `showdown_bf >= 0`. Building a parallel
priority machine for combat would be the natural mistake and would then have to
be reconciled every time either half changed.
"""

from __future__ import annotations

from rl.config import Config
from rl.engine import resolve as rsv
from rl.engine.cardtable import CardTable
from rl.engine.effects import spec_for
from rl.engine.state import (C_BOUND_BF, C_CARD, C_CTRL, C_FINAL, C_FROM_HAND,
                             MAX_CHAIN, MAX_TARGETS, N_SEATS, GameState)


def push(state: GameState, card: int, ctrl: int, from_hand: bool = True,
         bound_bf: int = -1) -> int:
    """Append a Pending Chain Item. Returns its index."""
    i = state.n_chain
    assert i < MAX_CHAIN, "chain overflow"
    row = state.chain[i]
    row[C_CARD] = card
    row[C_CTRL] = ctrl
    row[C_FINAL] = 0
    row[C_FROM_HAND] = int(from_hand)
    row[C_BOUND_BF] = bound_bf
    state.chain_targets[i, :] = -1
    state.n_chain = i + 1
    return i


def oldest_pending(state: GameState) -> int:
    """Index of the oldest Pending item, or -1. 337.1.b: oldest first."""
    for i in range(state.n_chain):
        if state.chain[i, C_FINAL] == 0:
            return i
    return -1


def newest_finalized(state: GameState) -> int:
    """Index of the newest Finalized item, or -1. 340.1: newest resolves."""
    for i in range(state.n_chain - 1, -1, -1):
        if state.chain[i, C_FINAL] == 1:
            return i
    return -1


def set_target(state: GameState, item: int, slot: int, perm: int) -> None:
    assert slot < MAX_TARGETS, "MAX_TARGETS overflow"
    state.chain_targets[item, slot] = perm


def finalize(state: GameState, item: int) -> None:
    """Mark an item Finalized. Targets must already be chosen (349)."""
    state.chain[item, C_FINAL] = 1
    state.pend_slot = -1
    # 337.1.a -- finalizing does not pass priority, and it restarts the pass
    # count because the game state changed.
    state.passes = 0


def _pop(state: GameState, item: int) -> tuple[int, int, bool, int, list[int]]:
    """Remove an item, returning what is needed to resolve it."""
    row = state.chain[item]
    card, ctrl = int(row[C_CARD]), int(row[C_CTRL])
    from_hand, bound = bool(row[C_FROM_HAND]), int(row[C_BOUND_BF])
    targets = [int(x) for x in state.chain_targets[item]]

    n = state.n_chain
    if item < n - 1:
        state.chain[item:n - 1] = state.chain[item + 1:n]
        state.chain_targets[item:n - 1] = state.chain_targets[item + 1:n]
    state.chain[n - 1, :] = -1
    state.chain_targets[n - 1, :] = -1
    state.n_chain = n - 1
    return card, ctrl, from_hand, bound, targets


def resolve_top(state: GameState, table: CardTable, cfg: Config) -> dict:
    """340.1 -- the newest Finalized item resolves, alone."""
    item = newest_finalized(state)
    assert item >= 0, "resolve_top with no finalized item"
    card, ctrl, from_hand, bound, targets = _pop(state, item)

    spec = spec_for(table, card)
    assert spec is not None, f"no spec for {table.names[card]!r} on the chain"
    log = rsv.resolve(state, table, cfg, spec, ctrl, targets[:spec.n_targets],
                      bound, from_hand)
    log["card"] = table.names[card]

    # The spell leaves play. (Units never reach here -- 337.2 resolves them
    # immediately at finalization, so nothing on this chain is a permanent.)
    n = int(state.n_trash[ctrl])
    assert n < state.trash.shape[1], "trash overflow"
    state.trash[ctrl, n] = card
    state.n_trash[ctrl] = n + 1
    return log


def pass_priority(state: GameState) -> bool:
    """339 -- returns True once every player has passed in sequence."""
    state.passes += 1
    state.priority = 1 - int(state.priority)
    return state.passes >= N_SEATS


def after_resolution(state: GameState) -> None:
    """340.2-340.4 -- who holds priority once an item has resolved."""
    state.passes = 0
    if state.n_chain == 0:
        # 340.2 -- Open State. In a Showdown, Focus passes (340.2.a); outside
        # one, the turn player is acting again (335).
        if state.showdown_bf >= 0:
            state.focus = 1 - int(state.focus)
            state.priority = int(state.focus)
        else:
            state.priority = int(state.active)
        return
    if oldest_pending(state) >= 0:
        return                                  # 340.3 -- back to Finalize
    # 340.4 -- the controller of the newest item now decides. This is the line
    # that makes an item five deep respondable once the ones above it clear.
    state.priority = int(state.chain[state.n_chain - 1, C_CTRL])
