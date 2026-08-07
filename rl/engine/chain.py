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
from rl.engine.cost import plan_payment
from rl.engine.effects import (SPEED_ACTION, SPEED_REACTION, abilities_for,
                               spec_for)
from rl.engine.state import (C_ABIL, C_BOUND_BF, C_CARD, C_CTRL, C_CTX,
                             C_FINAL, C_FROM_HAND, C_SRC, C_UID,
                             MAIN, MAX_CHAIN, MAX_TARGETS, MAX_TRIGGERS,
                             N_BF, N_SEATS,
                             P_CARD, P_CTRL, GameState)


def speed_ok(state: GameState, cfg: Config, seat: int, speed: int) -> bool:
    """May `seat` play a card of this speed in the current window?

    The three speeds are printed permissions, not DSL:

      main      no keyword. Neutral Open State, your Main Phase (316.5.b).
      [Action]  "Play on your turn or in showdowns."
      [Reaction] "Play any time" -- any window in which you hold priority.

    `[Action]` is the interesting one: it is *your turn* OR *a showdown*, so it
    covers responding on the opponent's turn only while a Showdown is running.
    That is what makes Back Off a combat trick rather than a sorcery.
    """
    if speed == SPEED_REACTION:
        return True
    if speed == SPEED_ACTION:
        return seat == int(state.active) or state.showdown_bf >= 0
    return (seat == int(state.active) and state.phase == MAIN
            and state.n_chain == 0 and state.showdown_bf < 0)


def playable_hand_indices(state: GameState, table: CardTable, cfg: Config,
                          seat: int) -> list[int]:
    """Hand indices `seat` may legally play right now, duplicates collapsed.

    Shared by the action layer and by `combat.window_is_live`, which needs to
    know whether a priority window is a real decision before it opens one.
    Three identical cards are one choice: they are interchangeable, so offering
    all three triples the branching for nothing.
    """
    if cfg.units_only or state.no_spells[seat]:
        return []
    seen: set[int] = set()
    out: list[int] = []
    for i in range(int(state.n_hand[seat])):
        card = int(state.hand[seat, i])
        if card in seen:
            continue
        seen.add(card)
        spec = spec_for(table, card)
        if spec is None:
            continue                       # not implemented in the DSL yet
        if not speed_ok(state, cfg, seat, spec.speed):
            continue
        if plan_payment(state, table, seat, card) is None:
            continue
        # 359.3.e.14.a -- a card that cannot legally choose all of its targets
        # cannot be played at all.
        if not rsv.can_be_cast(state, table, spec, seat, -1):
            continue
        out.append(i)
    return out


def hideable(state: GameState, table: CardTable, cfg: Config,
             seat: int) -> tuple[list[int], list[int]]:
    """(hand indices that may be hidden, battlefields they may be hidden at).

    811.1.b -- "While this card is in your hand ... **on your turn during an
    Open State**, you may pay [A] to hide this facedown at a battlefield you
    control that doesn't already have a facedown card hidden there."

    Hide is not a Play (811.1.c.1) and does not open a Chain (811.1.c.2), so it
    cannot be responded to. It is a plain discretionary action.
    """
    if cfg.units_only or seat != int(state.active) or state.n_chain != 0:
        return [], []
    # 107.3.b/c -- yours to hide at, and not already occupied.
    spots = [i for i in range(N_BF)
             if int(state.bf_ctrl[i]) == seat and int(state.fd_owner[i]) < 0]
    if not spots or state.total_ready_runes(seat) < 1:
        return [], []
    seen: set[int] = set()
    cards: list[int] = []
    for i in range(int(state.n_hand[seat])):
        card = int(state.hand[seat, i])
        if card in seen or not table.has(card, "Hidden"):
            continue
        # Only hide what can be played back. `hidden_playable` needs a DSL
        # spec, so hiding a [Hidden] card without one buries it: the card is
        # gone from hand, the battlefield's one facedown slot is occupied, and
        # nothing can ever retrieve either. Real decks run [Hidden] units
        # (Tideturner, Keeper of Masks) whose text is not in the DSL yet, and
        # they became reachable the moment units stopped being filtered out of
        # decks by `v1_legal`.
        if spec_for(table, card) is None:
            continue
        seen.add(card)
        cards.append(i)
    return cards, spots


def hidden_playable(state: GameState, table: CardTable, cfg: Config,
                    seat: int) -> list[int]:
    """Battlefields whose facedown card `seat` may play right now.

    Three gates, and the first is the one most easily missed:

      811.1.b  "**Beginning on the next turn**" -- a card hidden this turn
               cannot be played this turn. `fd_ply` is what makes that
               checkable.
      811.6    while facedown it has [Reaction], so any window will do.
      811.1.d  it cannot be played at all if its bound targets have no legal
               options at that battlefield.
    """
    if cfg.units_only or state.no_spells[seat]:
        return []
    out = []
    for i in range(N_BF):
        if int(state.fd_owner[i]) != seat:
            continue
        if int(state.fd_ply[i]) >= int(state.ply):
            continue                       # hidden this turn -- not live yet
        card = int(state.fd_card[i])
        spec = spec_for(table, card)
        if spec is None:
            continue
        # Playing from Hidden costs 0 energy (811.1.b), so there is no payment
        # gate -- only the targeting one.
        if not rsv.can_be_cast(state, table, spec, seat, i):
            continue
        out.append(i)
    return out


def push(state: GameState, card: int, ctrl: int, from_hand: bool = True,
         bound_bf: int = -1, abil: int = -1, src: int = -1,
         ctx: int = -1) -> int:
    """Append a Pending Chain Item. Returns its index.

    `abil >= 0` makes it a Triggered Ability rather than a card (383.3).
    """
    i = state.n_chain
    assert i < MAX_CHAIN, "chain overflow"
    row = state.chain[i]
    row[C_CARD] = card
    row[C_CTRL] = ctrl
    row[C_FINAL] = 0
    row[C_FROM_HAND] = int(from_hand)
    row[C_BOUND_BF] = bound_bf
    row[C_UID] = state.chain_uid
    row[C_ABIL] = abil
    row[C_SRC] = src
    row[C_CTX] = ctx
    state.chain_uid += 1
    state.chain_targets[i, :] = -1
    state.n_chain = i + 1
    return i


def item_spec(state: GameState, table: CardTable, item: int):
    """The CardSpec or Ability a chain item will resolve with.

    One lookup for both, because everything downstream -- targeting,
    finalization, resolution -- treats them identically. That is 383.3 doing
    the work: a triggered ability behaves like an activated ability on the
    Chain, so the only thing that differs is where the spec came from.
    """
    card = int(state.chain[item, C_CARD])
    abil = int(state.chain[item, C_ABIL])
    if abil < 0:
        return spec_for(table, card)
    abilities = abilities_for(table, card)
    assert abil < len(abilities), f"ability {abil} missing on {table.names[card]!r}"
    return abilities[abil]


def has_trigger(table: CardTable, card: int, trigger: int) -> bool:
    """Does this card have an ability on `trigger`? Cheap pre-filter so the
    queue only ever holds triggers that will actually produce something."""
    return any(a.trigger == trigger for a in abilities_for(table, card))


def queue(state: GameState, trigger: int, src: int, ctx: int = -1) -> None:
    """Record that a trigger condition was met. Drained by `flush`.

    **Not put on the Chain here, deliberately.** Trigger conditions are met
    wherever the game action happens -- inside the Combat Damage Step, inside a
    Cleanup, inside a spell's resolution -- and `state.is_open` is
    `n_chain == 0`, so anything on the Chain makes a Cleanup refuse to run
    (321). Pushing a Deathknell straight from `_destroy` would therefore block
    the very Cleanup that was killing the unit, and combat would never finish.

    Queueing also gets 808.1.d.3 right for free: "before the card is moved to
    the Trash, note its location ... to process the trigger after it has been
    Finalized." `ctx` is captured now, at the moment the condition was met,
    not read later off a row that has since changed or been reused.
    """
    i = int(state.n_trig)
    assert i < MAX_TRIGGERS, "trigger queue overflow"
    state.trig[i] = (trigger, src, ctx)
    state.n_trig = i + 1


def trig_controller(state: GameState, i: int) -> int:
    """Which seat controls queued trigger `i`."""
    return int(state.perms[int(state.trig[i, 1]), P_CTRL])


def next_placer(state: GameState) -> int:
    """Which seat places the next queued trigger, or -1 if the queue is empty.

    383.3.d.1 -- "starting with the Turn Player and proceeding in Turn Order,
    each player orders their Triggered Abilities on the Chain." So the turn
    player empties their queue first, then the opponent.
    """
    for seat in (int(state.active), 1 - int(state.active)):
        for i in range(int(state.n_trig)):
            if trig_controller(state, i) == seat:
                return seat
    return -1


def orderable(state: GameState, table: CardTable, seat: int) -> list[int]:
    """Queue indices `seat` may place next, interchangeable ones collapsed.

    383.3.d gives the controller the choice of order, and **the order is not
    cosmetic**: the Chain resolves newest-first (340.1), so the ability placed
    LAST resolves FIRST. Two triggers that would fight over the same target, or
    a token-maker and something that counts tokens, genuinely differ.

    Triggers identical in (card, ability, captured context) are collapsed --
    swapping two copies of the same Deathknell cannot produce a different game,
    and offering the choice would just widen the branching factor.
    """
    seen: set[tuple] = set()
    out: list[int] = []
    for i in range(int(state.n_trig)):
        if trig_controller(state, i) != seat:
            continue
        src = int(state.trig[i, 1])
        key = (int(state.perms[src, P_CARD]), int(state.trig[i, 0]),
               int(state.trig[i, 2]))
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out


def place(state: GameState, table: CardTable, cfg: Config, i: int) -> int:
    """Move queued trigger `i` onto the Chain and drop it from the queue.

    Always consumes the entry, even when `fire` declines to push anything
    (355.8, no legal targets) -- otherwise the drain loop would spin on it.
    """
    trigger, src, ctx = (int(x) for x in state.trig[i])
    added = fire(state, table, cfg, trigger, src, ctx)
    n = int(state.n_trig)
    if i < n - 1:
        state.trig[i:n - 1] = state.trig[i + 1:n]
    state.trig[n - 1] = -1
    state.n_trig = n - 1
    return added


def fire(state: GameState, table: CardTable, cfg: Config, trigger: int,
         src: int, ctx: int = -1) -> int:
    """Put every matching Triggered Ability of `src` on the Chain (383.3).

    Returns how many were added. Nothing fires while `units_only` is set, which
    is what keeps v0 bit-identical: v0's whole claim is that a unit resolving
    immediately (337.2) never opens a priority window, and an ETB trigger
    opens one.

    383.3.d orders simultaneous triggers by their controller's choice. Not
    exposed: no card in the pool has two abilities on the same trigger, so the
    choice would be between one option. It becomes a real decision the moment
    one does, and this is where it goes.
    """
    if cfg.units_only:
        return 0
    card = int(state.perms[src, P_CARD])
    ctrl = int(state.perms[src, P_CTRL])
    n = 0
    for k, ab in enumerate(abilities_for(table, card)):
        if ab.trigger != trigger:
            continue
        # 355.8 -- "In order to put a spell or ability on the chain, valid
        # choices must be made for all targets." An ability that cannot fill
        # its slots never reaches the chain at all.
        #
        # This matters far more for abilities than for cards. A card is only
        # offered when it is castable, so the check never fires; an ability
        # triggers whether or not the board can satisfy it. First Mate ("ready
        # another unit") played onto an empty board is the case -- without
        # this, the trigger sat Pending with an empty option list and the game
        # deadlocked with a player to act and nothing to do.
        if ab.n_targets and not rsv.can_be_cast(state, table, ab, ctrl, -1, src):
            continue
        push(state, card, ctrl, from_hand=False, abil=k, src=src, ctx=ctx)
        n += 1
    return n


def index_of_uid(state: GameState, uid: int) -> int:
    """Chain index holding `uid`, or -1 if it has already left the chain."""
    for i in range(state.n_chain):
        if int(state.chain[i, C_UID]) == uid:
            return i
    return -1


def counter(state: GameState, table: CardTable, uid: int) -> str | None:
    """Remove a chain item without resolving it. Returns its card name.

    A countered spell still goes to the trash -- it was played, it just never
    resolved. Returns None if it is already gone, which is normal: two players
    can counter the same item, and the second one fizzles (359.3.e).
    """
    i = index_of_uid(state, uid)
    if i < 0:
        return None
    card, ctrl, *_ = _pop(state, i)
    n = int(state.n_trash[ctrl])
    assert n < state.trash.shape[1], "trash overflow"
    state.trash[ctrl, n] = card
    state.n_trash[ctrl] = n + 1
    return table.names[card]


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
    spec = item_spec(state, table, item)
    abil = int(state.chain[item, C_ABIL])
    src = int(state.chain[item, C_SRC])
    ctx = int(state.chain[item, C_CTX])
    card, ctrl, from_hand, bound, targets = _pop(state, item)

    assert spec is not None, f"no spec for {table.names[card]!r} on the chain"
    log = rsv.resolve(state, table, cfg, spec, ctrl, targets[:spec.n_targets],
                      bound, from_hand, source=src, ctx=ctx)
    log["card"] = table.names[card]

    if abil >= 0:
        # A Triggered Ability is not a card and has no zone to go to -- its
        # source is still on the board. Only the spell path trashes anything.
        log["ability"] = abil
        return log

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
