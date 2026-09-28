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
from rl.engine.cost import base_flow, plan_flow, plan_payment, plan_wild_power
from rl.engine.effects import (TR_PLAY_ME, TR_PLAY_UNIT, TR_NTH_CARD,
                               TR_BECOME_EMPOWERED, TR_DEATH, TR_CHOSEN,
                               TR_TEMPORARY,
                               TR_DISCARD, COND_NONE, TR_SPEND_BUFF,
                               TR_DISCARD_ME,
                               compose_mode,
                               row_abilities, appended_abilities,
                               equip_abilities_for,
                               SPEED_ACTION, SPEED_REACTION, abilities_for,
                               bf_abilities_for, delayed_abilities_for,
                               legend_abilities_for,
                               CardSpec, repeated_spec, single_execution,
                               spec_for)
from rl.engine.state import (is_trash_src, trash_src, trash_src_seat,
                             F_BUFFED, F_DIED_IN_COMBAT, is_battlefield, is_bf_src, bf_src_index,  # noqa: F401
                             is_delayed_src, delayed_src, delayed_src_seat,
                             delayed_src_slot, MAX_DELAYED,
                             is_legend_src, legend_src, legend_src_seat, bf_loc,
                             C_REPEAT, C_PLAY_SPELL, C_SPENT_E,  # noqa: F401
                             bf_index, F_FROM_HIDDEN, P_FLAGS,
                             N_FD, N_FD_PER_BF, fd_bf, fd_slots,
                             C_ABIL, C_SUBJ, C_BOUND_BF, C_CARD, C_CTRL, C_CTX,
                             C_OWNER, F_STUNNED,
                             C_CTX2, C_COST_KILL,
                             C_FINAL, C_COST, C_DEST, C_FROM_HAND, C_SRC,
                             C_UID, COST_PRINTED, DEST_TRASH, DEST_BANISH,
                             DEST_RECYCLE,
                             MAIN, MAX_CHAIN, MAX_TARGETS, MAX_TRIGGERS,
                             N_BF, N_SEATS,
                             P_ALIVE, P_CARD, P_CTRL, P_LOC,
                             GameState)


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
        # 309.1.a -- a Chain makes the turn a CLOSED State, and only [Reaction]
        # plays there. [Action]'s permission (806.1.b) is about Showdowns, not
        # about answering something already on the Chain: RiftJudge #12560 is
        # exactly this, an [Action] in hand that cannot answer Warwick's attack
        # trigger. Without this an Action card could respond to any trigger --
        # including one of its controller's own spells, on their own turn.
        if state.n_chain > 0:
            return False
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

    **Spells and Gear-that-goes-on-the-Chain only.** Units and Gear are played
    through their own destination-choice flow (`actions._resolve_play`), never
    through here -- `SPECS` held only spells until Cruel Patron's printed
    "kill a [...] as an additional cost" (820) gave a UNIT a `CardSpec` for the
    first time, and without this guard it would have been offered a SECOND
    time here, since a Main-speed card's `spec.speed` passes `speed_ok` in the
    same Neutral Open window the unit-play loop already offers it in.
    """
    if cfg.units_only or state.no_spells[seat] or state.no_cards[seat]:
        return []
    seen: set[int] = set()
    out: list[int] = []
    for i in range(int(state.n_hand[seat])):
        card = int(state.hand[seat, i])
        if card in seen:
            continue
        seen.add(card)
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            continue
        spec = spec_for(table, card)
        if spec is None:
            continue                       # not implemented in the DSL yet
        if not speed_ok(state, cfg, seat, spec.speed):
            continue
        if _name_locked(state, table, seat, card):
            continue
        free_if_paid = (spec.paid_ignores_cost and spec.cost_kill is not None
                        and bool(rsv.cost_kill_targets(state, table, spec, seat)))
        if spec.paid_targets:
            # Castable one way or the other; `actions.spell_opt_cost_options`
            # decides which of the two plays is offered.
            if not (rsv.can_be_cast(state, table, spec, seat, -1, card=card)
                    or rsv.can_be_cast(state, table,
                                       spec._replace(targets=spec.paid_targets),
                                       seat, -1, card=card)):
                continue
            if plan_payment(state, table, seat, card) is None:
                continue
            out.append(i)
            continue
        if (plan_payment(state, table, seat, card) is None and not free_if_paid
                and not tag_discount_targets(state, table, seat, card, spec)):
            continue
        # 359.3.e.14.a -- a card that cannot legally choose all of its targets
        # cannot be played at all, and 820 makes an unpayable REQUIRED
        # additional cost (Sacrifice, or Heedless Resurrection's OWN target
        # coupled to which permanent pays it) the same deadlock one level
        # earlier -- see `can_play_with_cost_kill`. An OPTIONAL one never
        # blocks the play (Meditation).
        if spec.cost_kill_optional:
            if not rsv.can_be_cast(state, table, spec, seat, -1, card=card):
                continue
        elif not rsv.can_play_with_cost_kill(state, table, spec, seat, -1,
                                             card=card):
            continue
        out.append(i)
    return out


def tag_discount_targets(state: GameState, table: CardTable, seat: int,
                         card: int, spec) -> list[int]:
    """Undying Loyalty -- "this costs {2 energy} less if you choose a Bird, Cat,
    Dog, or Poro". The trash units whose choice makes the play affordable, or
    [] when the discounted cost is out of reach too (or the card has no such
    discount). A play affordable only this way is offered, and its slot then
    only offers these (`actions._slot_options`), so it can never reach
    finalization unpayable. It used to be offered only when the FULL cost was
    affordable, which hid the discount's whole point."""
    from rl.engine.effects import TRASH_TAG_DISCOUNT, unpack_trash
    td = TRASH_TAG_DISCOUNT.get(table.names[card])
    if td is None or spec is None or not spec.n_targets:
        return []
    if plan_payment(state, table, seat, card, -td[0]) is None:
        return []
    return [t for t in rsv.choosable_targets(state, table, spec, 0, seat, [],
                                             -1, -1, card, -1)
            if any(tag in table.tags[unpack_trash(t)[1]] for tag in td[1])]


def _name_locked(state: GameState, table: CardTable, seat: int, card: int) -> bool:
    """Fallen Feline: an opponent's, at a battlefield, named this spell."""
    from rl.engine.effects import NAMED_SPELL_LOCKS
    return any(state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) != seat
               and is_battlefield(int(state.perms[i, P_LOC]))
               and int(state.named[i]) == card
               and table.names[int(state.perms[i, P_CARD])] in NAMED_SPELL_LOCKS
               for i in range(state.n_perms))


def _playable_from_hidden(table: CardTable, card: int) -> bool:
    """Could this card do anything if played back out of a Facedown Zone?

    A PERMANENT always can: 337.2 puts it on the board and it stands there
    whether or not its rules text is transcribed, the same as a unit played
    from hand. A SPELL with no spec has nothing to resolve, so playing it
    would spend the card for no effect.

    Shared by `hideable` and `hidden_playable` so the two cannot drift --
    hiding something the play side would refuse buries the card permanently.
    """
    return (table.is_type(card, "Unit") or table.is_type(card, "Gear")
            or spec_for(table, card) is not None)


def fd_capacity(state: GameState, table: CardTable, i: int) -> int:
    """How many facedown cards battlefield `i` may hold.

    107.3.f says one. Bandle Tree's whole text is "you may hide an additional
    card here", which is the only reason the zone has a second slot at all --
    so the capacity is a property of the GROUND, not a constant.
    """
    from rl.engine.effects import BF_EXTRA_HIDE
    card = int(state.bf_card[i])
    if card >= 0 and table.names[card] in BF_EXTRA_HIDE:
        return min(N_FD_PER_BF, 1 + BF_EXTRA_HIDE[table.names[card]])
    return 1


def free_fd_slot(state: GameState, table: CardTable, i: int) -> int:
    """The next empty facedown slot at battlefield `i`, or -1 if it is full."""
    used = 0
    for k in fd_slots(i):
        if int(state.fd_owner[k]) >= 0:
            used += 1
    if used >= fd_capacity(state, table, i):
        return -1
    for k in fd_slots(i):
        if int(state.fd_owner[k]) < 0:
            return k
    return -1


def hideable(state: GameState, table: CardTable, cfg: Config,
             seat: int) -> tuple[list[int], list[int]]:
    """(hand indices that may be hidden, facedown SLOTS they may be hidden at).

    811.1.b -- "While this card is in your hand ... **on your turn during an
    Open State**, you may pay [A] to hide this facedown at a battlefield you
    control that doesn't already have a facedown card hidden there."

    Hide is not a Play (811.1.c.1) and does not open a Chain (811.1.c.2), so it
    cannot be responded to. It is a plain discretionary action.

    The second return value is a SLOT and not a battlefield: Bandle Tree holds
    two, so "where" needs to say which of them.
    """
    if cfg.units_only or seat != int(state.active) or state.n_chain != 0:
        return [], []
    # 107.3.b/c -- yours to hide at, and with room left (`fd_capacity`).
    spots = [k for k in (free_fd_slot(state, table, i)
                         for i in state.live_bfs()
                         if int(state.bf_ctrl[i]) == seat)
             if k >= 0]
    # The cost is [A] -- one POWER, paid by RECYCLING a rune (164.2.b) or from
    # floating Power. Recycling has no ready requirement, so a board of nothing
    # but exhausted runes can still hide; asking for a READY rune both refused
    # legal hides and, worse, implied the wrong price. See
    # `cost.plan_wild_power`.
    # Guerilla Warfare: "you can hide cards ignoring costs this turn" reads as
    # "you can [hide] [while] ignoring costs" (RiftJudge #6655), so this turn
    # the price is nothing and a player with no runes at all may still hide.
    free = int(state.free_hide_ply[seat]) == int(state.ply)
    if not spots or (not free and plan_wild_power(state, seat, 1) is None):
        return [], []
    seen: set[int] = set()
    cards: list[int] = []
    for i in range(int(state.n_hand[seat])):
        card = int(state.hand[seat, i])
        if card in seen or not table.has(card, "Hidden"):
            continue
        # Only hide what can be played back. Hiding a card `hidden_playable`
        # will refuse buries it: the card is gone from hand, the battlefield's
        # one facedown slot is occupied, and nothing can ever retrieve either.
        # Kept in step with `hidden_playable`'s own gate below -- a SPELL needs
        # a spec to do anything on resolution, a PERMANENT does not (337.2
        # resolves it onto the board and it simply stands there, exactly as it
        # would from hand). That distinction is what lets the pool's 14
        # [Hidden] units be hidden at all; requiring a spec of them buried
        # every one, so none was ever hidden.
        if not _playable_from_hidden(table, card):
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

    **811.6 is why `speed_ok` is deliberately not called here.** A facedown
    card gains [Reaction] *whatever its printed speed*, so a plain Main-speed
    unit hidden last turn is playable in any window a Reaction is -- including
    mid-Showdown on the opponent's turn. That is the whole point of the
    keyword, and it is the one place in the engine where a card's printed
    timing is overridden rather than consulted.
    """
    if cfg.units_only or state.no_spells[seat] or state.no_cards[seat]:
        return []
    out = []
    for k in range(N_FD):
        i = fd_bf(k)
        if i not in state.live_bfs():
            continue
        if int(state.fd_owner[k]) != seat:
            continue
        if int(state.fd_ply[k]) >= int(state.ply):
            continue                       # hidden this turn -- not live yet
        from rl.engine.effects import HIDDEN_LOCKS
        if any(state.perms[p, P_ALIVE] == 1 and int(state.perms[p, P_CTRL]) != seat
               and int(state.perms[p, P_LOC]) == bf_loc(i)
               and table.names[int(state.perms[p, P_CARD])] in HIDDEN_LOCKS
               for p in range(state.n_perms)):
            continue                       # Noxus Saboteur
        card = int(state.fd_card[k])
        if not _playable_from_hidden(table, card) or _name_locked(
                state, table, seat, card):
            continue
        # 811.1.d.1 -- a hidden PERMANENT must be played to that battlefield,
        # so it has no destination choice and nothing can make the play
        # illegal: it is not a spell, so there are no target slots to fill,
        # and 811.1.b waives the cost. The one thing that can still refuse it
        # is a battlefield whose own text forbids playing there (Rockfall
        # Path), which `bf_forbids_play` answers for the hand path too.
        if table.is_type(card, "Unit") or table.is_type(card, "Gear"):
            # Imported here, not at module scope: `resolve` imports both this
            # module and `combat`, so a top-level edge from here would tighten
            # an already-delicate cycle for one predicate.
            from rl.engine.combat import bf_forbids_play
            if bf_forbids_play(state, table, bf_loc(i)):
                continue
            out.append(k)
            continue
        # Playing from Hidden costs 0 energy (811.1.b), so there is no payment
        # gate -- only the targeting one. The BATTLEFIELD, not the slot, is
        # what binds the card's targets (811.1.d.2).
        if not rsv.can_be_cast(state, table, spec_for(table, card), seat, i,
                               card=card):
            continue
        out.append(k)
    return out


def flow_playable(state: GameState, table: CardTable, cfg: Config,
                  seat: int) -> list[int]:
    """Trash indices `seat` may play for a [Flow] cost (829.1.b).

    "You may play this from your trash for its flow cost." 829.1.b.2 is
    explicit that Flow changes only the ZONE it can be played from -- not its
    timing and not any other permission -- so the usual speed check still
    applies unchanged.
    """
    if cfg.units_only or state.no_spells[seat] or state.no_cards[seat]:
        return []
    seen: set[int] = set()
    out: list[int] = []
    from rl.engine.effects import TRASH_UNIT_PLAY, SPEED_MAIN
    for i in range(int(state.n_trash[seat])):
        card = int(state.trash[seat, i])
        if card in seen:
            continue
        got = TRASH_UNIT_PLAY.get(table.names[card])
        if got is None and int(state.riches_on[seat]) and (
                table.is_type(card, "Unit") or table.is_type(card, "Gear")):
            got = (int(table.energy[card]), int(table.power[card]))  # Endless Riches
            seen.add(card)
            if (speed_ok(state, cfg, seat, SPEED_MAIN)
                    and plan_payment(state, table, seat, card) is not None):
                out.append(i)
            continue
        if got is not None:
            # Undying Legion: [Legion] -- another card played this turn -- and
            # a unit's own timing.
            seen.add(card)
            if (int(state.cards_played[seat]) > 0
                    and speed_ok(state, cfg, seat, SPEED_MAIN)
                    and plan_payment(state, table, seat, card,
                                     got[0] - int(table.energy[card]),
                                     got[1]) is not None):
                out.append(i)
            continue
        if base_flow(state, table, seat, card)[0] < 0:
            continue
        seen.add(card)
        spec = spec_for(table, card)
        if spec is None or not speed_ok(state, cfg, seat, spec.speed):
            continue
        if _name_locked(state, table, seat, card):
            continue
        _flow = plan_flow(state, table, seat, card)
        if _flow is None:
            continue
        # 829.1.c.1 -- the Flow cost REPLACES the printed one, and it is often
        # heavier in Power (Lacerate prints 1, its Flow costs 2). Target
        # legality includes whether a [Deflect] surcharge is payable
        # (809.1.c), so it has to be asked against the cost this play will
        # actually pay: asking it against the printed cost offered a Flow play
        # whose only legal target then vanished at the slot.
        from rl.engine.actions import _castable_under_cost
        from rl.engine.state import COST_FLOW as _CF
        if not _castable_under_cost(state, table, seat, card, spec,
                                    cost_mode=_CF):
            continue
        out.append(i)
    return out


def push(state: GameState, card: int, ctrl: int, from_hand: bool = True,
         bound_bf: int = -1, abil: int = -1, src: int = -1,
         ctx: int = -1, cost: int = COST_PRINTED,
         dest: int = DEST_TRASH, subj: int = -1, ctx2: int = -1,
         owner: int = -1) -> int:
    """Append a Pending Chain Item. Returns its index.

    `abil >= 0` makes it a Triggered Ability rather than a card (383.3).
    """
    i = state.n_chain
    assert i < MAX_CHAIN, "chain overflow"
    if i == 0:
        # 340.2.a asks whether the chain "was initiated by a triggered
        # ability", which is a fact about the FIRST item on it. Recorded here
        # because it has to outlive that item: the rule is read at the moment
        # the chain empties again, when nothing is left to ask.
        state.chain_from_trigger = int(abil >= 0)
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
    row[C_COST] = cost
    row[C_DEST] = dest
    row[C_SUBJ] = subj
    row[C_CTX2] = ctx2
    row[C_COST_KILL] = -1
    row[C_OWNER] = owner
    row[C_SPENT_E] = 0
    row[C_PLAY_SPELL] = 0
    state.chain_uid += 1
    state.chain_targets[i, :] = -1
    state.n_chain = i + 1
    return i


def item_spec(state: GameState, table: CardTable, item: int):
    """The CardSpec or Ability a chain item will resolve with -- with its mode
    applied once one is chosen ("Choose one --", see `effects.TK_MODE`)."""
    spec = _item_spec_base(state, table, item)
    if (spec is not None and getattr(spec, "paid_targets", ())
            and int(state.chain[item, C_REPEAT]) in (2, 3)):
        spec = spec._replace(targets=spec.paid_targets)
    if spec is not None and spec.modes:
        m = int(state.chain_targets[item, 0])
        if m >= 0:
            return compose_mode(spec, m)
    # 820.2.a -- a spell played with its [Repeat] paid chooses a second set of
    # targets for the second execution. Moded spells keep one shared set: their
    # slot 0 is the mode, and a second mode choice is not modelled.
    if (spec is not None and int(state.chain[item, C_ABIL]) < 0
            and int(state.chain[item, C_REPEAT]) in (1, 3) and spec.n_targets
            and 2 * spec.n_targets <= MAX_TARGETS
            and isinstance(spec, CardSpec)):
        return repeated_spec(spec)
    return spec


def _item_spec_base(state: GameState, table: CardTable, item: int):
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
    # Which TABLE the index points into is a fact about the source, not about
    # the card -- a battlefield's abilities are numbered in `BF_ABILITIES`.
    src = int(state.chain[item, C_SRC])
    # 718.3 -- an ability APPENDED by an Attached card is numbered in
    # `EQUIP_ABILITIES` under the EQUIPMENT's name, while it fires from the
    # UNIT's row. The discriminator is that disagreement: for every other
    # permanent ability `C_CARD` IS the source row's card, and only an appended
    # one can name a different one. That is also what keeps "me" and "here"
    # pointing at the unit (136.2.c) while the text comes from the gear.
    #
    # Read off the CHAIN and not off the board, so it survives the Equipment
    # being detached or killed during the response window -- the ability is
    # already its own Chain Item by then, and 383.2.c.2 is about the SOURCE
    # being gone, not about where the text was looked up.
    #
    # **The disagreement alone is not enough.** A BORROWED ability (Heimerdinger
    # takes "all Exhaust abilities", see `ABILITY_BORROWERS`) also stores the
    # donor's card against the borrower's row, and reading that out of the
    # Equipment table found nothing and asserted. So the card must actually
    # have an appended-ability entry; `ABILITY_BORROWERS` and `EQUIP_ABILITIES`
    # are asserted disjoint at import in `effects.py`, which is what makes this
    # a decision rather than a guess.
    from rl.engine.effects import ABIL_TEMPORARY, GRANTED_ABILITIES, TEMPORARY_ABILITY
    if abil == ABIL_TEMPORARY:
        return TEMPORARY_ABILITY          # 816, see `fire`
    # A LEGEND item whose card is not the champion is an ability a battlefield
    # granted it (Forge of the Fluft): numbered under the GROUND's name, the
    # same way an Equipment's is numbered under the gear's.
    if (is_legend_src(src) and card != int(state.legend[legend_src_seat(src)])
            and table.names[card] in GRANTED_ABILITIES):
        return GRANTED_ABILITIES[table.names[card]][abil]
    if (src >= 0 and card != int(state.perms[src, P_CARD])
            and equip_abilities_for(table, card)):
        abilities = equip_abilities_for(table, card)
    elif src >= 0 and table.names[card] in GRANTED_ABILITIES:
        abilities = GRANTED_ABILITIES[table.names[card]]
    else:
        abilities = (bf_abilities_for(table, card) if is_bf_src(src)
                     else legend_abilities_for(table, card) if is_legend_src(src)
                     else delayed_abilities_for(table, card) if is_delayed_src(src)
                     else abilities_for(table, card))
    assert abil < len(abilities), f"ability {abil} missing on {table.names[card]!r}"
    return abilities[abil]


def open_slot_kind(state: GameState, table: CardTable) -> int:
    """The TK_* kind of the target slot currently being filled.

    **Anything reading an `A_TARGET` arg must ask this first.** The arg means
    whatever the slot's kind says: a permanent row, a location, a Chain uid, or
    a card id. Three separate bugs have come from reading it as a row anyway --
    the observation encoder describing permanent 0-3 for a location target,
    `deflect_cost` charging a surcharge for whichever unit sat in row 2, and
    the greedy baseline sorting counterspell targets by the Might of a row
    picked by a monotonic counter. Every one of those indices was VALID, so
    none of them crashed; they just described the wrong thing on exactly the
    decisions where the description mattered.

    Lives here rather than in either caller so there is one answer.
    """
    from rl.engine.effects import TK_UNIT
    if state.steal_seat >= 0 and int(state.steal_stage) == 3:
        i = index_of_uid(state, int(state.steal_uid))
        sp = item_spec(state, table, i) if i >= 0 else None
        k = int(state.steal_slot)
        return sp.targets[k].kind if sp is not None and k < sp.n_targets else TK_UNIT
    item = oldest_pending(state)
    if item < 0 or state.pend_slot < 0:
        return TK_UNIT
    spec = item_spec(state, table, item)
    slot = int(state.pend_slot)
    if spec is None or slot >= spec.n_targets:
        return TK_UNIT
    return spec.targets[slot].kind


def has_trigger(table: CardTable, card: int, trigger: int) -> bool:
    """Does this card have an ability on `trigger`? Cheap pre-filter so the
    queue only ever holds triggers that will actually produce something."""
    return any(a.trigger == trigger for a in abilities_for(table, card))


# Set by `new_step`, consumed by the next `queue`: the trigger about to be
# queued belongs to a LATER step of the action than whatever is already there.
_NEW_STEP: list[bool] = [False]


def new_step(state: GameState) -> None:
    """Start a new step: what is queued next is not simultaneous with
    what is queued already, and goes on the Chain after it.

    The rules step within one action -- 464.2.b's start-of-showdown
    effects before 464.2.c's designations -- is what makes two pending
    triggers non-simultaneous. Without this the placement order was
    purely 383.3.d.1's seat order, which put a defender's
    showdown-begins trigger ON TOP of the attacker's attack trigger and
    so resolved it first (RiftJudge #10254)."""
    _NEW_STEP[0] = True


def queue(state: GameState, trigger: int, src: int, ctx: int = -1,
          subj: int = -1, ctx2: int = -1, who: int = -1) -> None:
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
    # A battlefield source has no row to read a controller off, so one must be
    # supplied. Asserted rather than defaulted: falling back to a permanent row
    # lookup would index `perms[-101]`, which is a valid numpy index and would
    # silently attribute the ability to whatever sits at the end of the array.
    assert not is_bf_src(src) or who >= 0, (
        "a battlefield-sourced trigger must carry its controlling seat")
    # The step stamp (see `GameState.trig`). Derived from the queue itself
    # rather than from a counter on the state, so a copied or mirrored state
    # carries its own ordering: the newest stamp in the queue, plus one when
    # `new_step` has been called since the last queue.
    cur = int(state.trig[:i, 6].max()) if i else -1
    step = cur + 1 if (_NEW_STEP[0] or i == 0) else max(cur, 0)
    _NEW_STEP[0] = False
    state.trig[i] = (trigger, src, ctx, subj, ctx2, who, step)
    state.n_trig = i + 1


def fire_discarded(state: GameState, table: CardTable, seat: int,
                   cards) -> None:
    """Queue "When you discard me" for each discarded card that prints it."""
    for c in cards:
        c = int(c)
        if c >= 0 and any(a.trigger == TR_DISCARD_ME
                          for a in abilities_for(table, c)):
            queue(state, TR_DISCARD_ME, trash_src(seat), -1, subj=c, who=seat)


def spend_buff(state: GameState, table: CardTable, seat: int,
               perm: int) -> None:
    """Spend `perm`'s Buff counter for `seat`, and tell the watchers."""
    assert state.has_flag(perm, F_BUFFED), "spending a buff that is not there"
    if int(state.extra_buffs[perm]) > 0:
        state.extra_buffs[perm] -= 1              # Lee Sin keeps the rest
    else:
        state.clear_flag(perm, F_BUFFED)
    fire_watchers(state, table, seat, TR_SPEND_BUFF, subj=perm)


def ability_cond_holds(state: GameState, table: CardTable, ab, seat: int,
                       src: int, ctx: int = -1, ctx2: int = -1) -> bool:
    """`Ability.cond`, asked with the op-condition vocabulary (see there)."""
    from rl.engine.effects import Op, OP_DRAW
    from rl.engine.effects import COND_CONTROL_N_GEAR
    probe = Op(OP_DRAW, cond=ab.cond, level=ab.cond_level,
               cond_tag=getattr(ab, "cond_tag", None),
               floor=ab.cond_level if ab.cond == COND_CONTROL_N_GEAR else None)
    # A legend sentinel is a live source, not a dead row: it never leaves the
    # Legend Zone, and `_condition_holds` dispatches on it for "[Empowered] >".
    # Passing it as `dead_source` instead would index `perms` from the end.
    alive = (src if is_legend_src(src)
             else src if src >= 0 and state.perms[src, P_ALIVE] == 1 else -1)
    return rsv._condition_holds(state, table, probe, [], False, seat,
                                alive, ctx, src if alive < 0 else -1, ctx2)


def fire_legend(state: GameState, table: CardTable, seat: int, trigger: int,
                ctx: int = -1, subj: int = -1) -> None:
    """Queue `seat`'s legend's abilities on an event that is not a watcher.

    `fire_watchers` already reaches the legend for everything that happens TO
    another object. This is the other half: "when you conquer", "when you
    hold", "at the start of your Beginning Phase" -- events that belong to the
    PLAYER, which each fire once for the seat rather than once per permanent.
    The unit and battlefield versions of those words are queued at the same
    sites, so this sits beside them.
    """
    lcard = int(state.legend[seat])
    if lcard < 0:
        return
    for ab in legend_abilities_for(table, lcard):
        if ab.trigger != trigger:
            continue
        if ab.once_each_turn:
            if int(state.legend_once[seat]) == int(state.ply):
                continue
            state.legend_once[seat] = int(state.ply)
        queue(state, trigger, legend_src(seat), ctx, subj=subj, who=seat)
        break


def fire_watchers(state: GameState, table: CardTable, seat: int,
                  trigger: int, subj: int = -1, exclude: int = -1,
                  by_spell: bool = False) -> None:
    """Queue `seat`'s permanents watching for `trigger` to happen elsewhere.

    The generalisation of `fire_play_unit`: a watcher fires because something
    happened to a DIFFERENT permanent, so it needs the event's subject and, for
    an "another" clause, the one permanent that must not count as a watcher.
    """
    # Whether the event happened to somebody ELSE'S permanent, decided from the
    # subject rather than from the caller: `seat` here is the WATCHER's
    # controller, so "an enemy unit died" is the same call with the subject on
    # the other side. An event with no subject at all (a discard, a score) is
    # nobody's, and reads as friendly so the default watchers still fire.
    subj_enemy = subj >= 0 and int(state.perms[subj, P_CTRL]) != seat
    # Every discard in the engine announces itself here, so this is also where
    # "if you've discarded a card this turn" (Raging Soul) is recorded.
    if trigger == TR_DISCARD:
        state.discarded_ply[seat] = int(state.ply)
    for w in range(state.n_perms):
        if w == exclude or state.perms[w, P_ALIVE] != 1:
            continue
        if int(state.perms[w, P_CTRL]) != seat:
            continue
        for ab in row_abilities(state, table, w):
            if ab.trigger != trigger:
                continue
            # "when an ENEMY unit dies" against "when another FRIENDLY unit
            # dies". Both readings are printed, so neither can be the default
            # that a missing flag falls into -- the flag has to MATCH.
            if bool(ab.subject_enemy) != subj_enemy:
                continue
            # "when you choose or ready ME" -- the watcher is the subject, not
            # a bystander. Without this the card reads "...a friendly unit".
            if ab.subject_is_self and subj != w:
                continue
            # "When you choose a friendly UNIT" (Spirit Wheel) -- a gear is
            # chosen through the same slot machinery and must not count.
            if trigger == TR_CHOSEN and subj >= 0 and not table.is_type(
                    int(state.perms[subj, P_CARD]), ab.subject_card_type):
                continue
            # "...with a SPELL" -- an ability that chooses is still a choice.
            if ab.subject_by_spell and not by_spell:
                continue
            if ab.subject_stunned and not (
                    subj >= 0 and int(state.perms[subj, P_FLAGS]) & F_STUNNED):
                continue
            # "another NON-RECRUIT unit" -- a tag the SUBJECT must not carry.
            # Viktor - Leader makes Recruits, so without this each token's
            # death would make another one, forever.
            if ab.subject_lacks_tag and subj >= 0 and ab.subject_lacks_tag in \
                    combat_perm_tags(state, table, subj):
                continue
            # "...or another DRAGON" -- the mirror, a tag it must carry.
            if ab.subject_tag and not (subj >= 0 and ab.subject_tag in
                                       combat_perm_tags(state, table, subj)):
                continue
            # "while I'm at a battlefield" -- about the WATCHER's own ground,
            # not the subject's. Pyke in a base collects nothing.
            if ab.subject_here and not (
                    subj >= 0 and int(state.perms[subj, P_LOC])
                    == int(state.perms[w, P_LOC])):
                continue
            # "When a BUFFED friendly unit dies" -- the dying row keeps its
            # flags until compaction, so the Buff is still readable here.
            if ab.subject_on_battlefield and not (
                    subj >= 0 and is_battlefield(int(state.perms[subj, P_LOC]))):
                continue
            if ab.subject_buffed and not (
                    subj >= 0 and int(state.perms[subj, P_FLAGS]) & F_BUFFED):
                continue
            if ab.subject_at_battlefield and not is_battlefield(
                    int(state.perms[w, P_LOC])):
                continue
            # "The FIRST TIME ... each turn" -- one stamp per permanent per
            # turn, the same field Zilean's once-each-turn uses. Stamped LAST,
            # after every other filter has passed: an event the ability did not
            # want must not spend the turn's one use of it.
            if ab.once_each_turn:
                if int(state.once_used[w]) == int(state.ply):
                    continue
                state.once_used[w] = int(state.ply)
            queue(state, trigger, w, int(state.perms[w, P_LOC]), subj=subj)
            break
    _fire_legend_watchers(state, table, seat, trigger, subj, subj_enemy,
                          by_spell)


def _fire_legend_watchers(state: GameState, table: CardTable, seat: int,
                          trigger: int, subj: int, subj_enemy: bool,
                          by_spell: bool) -> None:
    """The same pass over `seat`'s LEGEND (103.1), which is not a permanent.

    A legend watches from the Legend Zone and is never on the board, so it has
    no row: every clause that asks where the watcher is standing (`subject_
    here`, `subject_at_battlefield`) or whether the watcher IS the subject
    (`subject_is_self`) cannot be satisfied by one, and an ability carrying a
    clause like that is simply not a legend's. Everything that asks about the
    EVENT reads the same as it does for a permanent.

    Reached from `fire_watchers` rather than from each of its ~20 call sites:
    "when you play a unit", "when you stun", "when you recycle a rune" and the
    rest are the same events whether a unit or a champion is listening.
    """
    lcard = int(state.legend[seat])
    if lcard < 0:
        return
    for ab in legend_abilities_for(table, lcard):
        if ab.trigger != trigger:
            continue
        if bool(ab.subject_enemy) != subj_enemy:
            continue
        if ab.subject_is_self or ab.subject_here or ab.subject_at_battlefield:
            continue
        if trigger == TR_CHOSEN and subj >= 0 and not table.is_type(
                int(state.perms[subj, P_CARD]), ab.subject_card_type):
            continue
        if ab.subject_by_spell and not by_spell:
            continue
        if ab.subject_stunned and not (
                subj >= 0 and int(state.perms[subj, P_FLAGS]) & F_STUNNED):
            continue
        if ab.subject_lacks_tag and subj >= 0 and ab.subject_lacks_tag in \
                combat_perm_tags(state, table, subj):
            continue
        if ab.subject_tag and not (subj >= 0 and ab.subject_tag in
                                   combat_perm_tags(state, table, subj)):
            continue
        if ab.subject_on_battlefield and not (
                subj >= 0 and is_battlefield(int(state.perms[subj, P_LOC]))):
            continue
        if ab.subject_buffed and not (
                subj >= 0 and int(state.perms[subj, P_FLAGS]) & F_BUFFED):
            continue
        if ab.cond != COND_NONE and not ability_cond_holds(
                state, table, ab, seat, -1, -1):
            continue
        # One stamp per SEAT rather than per row: the legend is the seat's, and
        # there is only ever one of it.
        if ab.once_each_turn:
            if int(state.legend_once[seat]) == int(state.ply):
                continue
            state.legend_once[seat] = int(state.ply)
        queue(state, trigger, legend_src(seat), -1, subj=subj, who=seat)
        break


def combat_perm_tags(state: GameState, table: CardTable, perm: int):
    from rl.engine.combat import perm_tags
    return perm_tags(state, table, perm)


def fire_empowered(state: GameState, table: CardTable, perm: int) -> None:
    """441.1 -- `perm` just BECAME Empowered. Queue the watchers.

    Called only on a real transition. 441.1.b/c make re-Empowering something
    already Empowered a no-op, and a no-op is not an event, so the caller
    checks the status BEFORE setting it -- the same shape `state.stun` uses to
    keep a redundant Stun from firing "when you stun an enemy unit".

    Two shapes of watcher, told apart by `subject_is_self`:
      "When I become [Empowered]"        -- the permanent itself (Kharox)
      "When you empower something else"  -- its controller's other permanents
                                            (Ambessa), which is why the walk
                                            covers the board and not just `perm`
    """
    # `perm` is an ability SOURCE: a row, or a legend sentinel when a champion
    # empowered itself (Zed - Master of Shadows). A legend has no controller
    # column to read, so the seat comes from the sentinel instead.
    legend = is_legend_src(perm)
    owner = (legend_src_seat(perm) if legend
             else int(state.perms[perm, P_CTRL]))
    for w in range(state.n_perms):
        if state.perms[w, P_ALIVE] != 1:
            continue
        for ab in row_abilities(state, table, w):
            if ab.trigger != TR_BECOME_EMPOWERED:
                continue
            if ab.subject_is_self and w != perm:
                continue
            # "something ELSE" -- Ambessa must not fire on her own Empower, or
            # she would Empower herself in a loop off her own trigger.
            if not ab.subject_is_self and (w == perm
                                           or int(state.perms[w, P_CTRL]) != owner):
                continue
            queue(state, TR_BECOME_EMPOWERED, w, int(state.perms[w, P_LOC]),
                  subj=perm)
    # ...and the legend, whose "when you empower something else" (Ambessa -
    # Matriarch of War, Mel - Soul's Reflection) watches the board from the
    # Legend Zone. Never on its OWN empower, for the same loop reason.
    lcard = int(state.legend[owner])
    if lcard >= 0 and not legend:
        for ab in legend_abilities_for(table, lcard):
            if ab.trigger != TR_BECOME_EMPOWERED or ab.subject_is_self:
                continue
            queue(state, TR_BECOME_EMPOWERED, legend_src(owner), -1,
                  subj=perm, who=owner)
            break


def card_played(state: GameState, table: CardTable, seat: int,
                card: int = -1, completed: bool = True) -> None:
    """Everything that rides on `seat` having PLAYED a card, whatever kind.

    Called at each of the four sites that increment `cards_played`, straight
    after the increment -- a spell finalizing, and a permanent arriving from
    hand, from the Facedown Zone, or from a look buffer. Both jobs here need a
    count of cards rather than of units, so neither could live in
    `fire_play_unit`: a spell never reaches that function, and 349 makes a
    countered spell a played card all the same.

    Two things happen, in this order and not the other:

      1. The one-shot discount is SPENT. "Your next card costs {...} less"
         names the card, so the promise is consumed by playing one whether or
         not the cost was paid -- a card played from Hidden ignores its cost
         entirely (811.1.b) and still uses the promise up. The payment has
         already happened by the time this runs, which is what makes spending
         it here safe.
      2. "When you play your Nth card" watchers fire. AFTER the clear, so a
         Heron triggering on your first card promises a discount that the
         first card cannot retroactively eat.

    Step 2 needs the play to be COMPLETE (419.4.a). A permanent's is complete
    here -- it resolves as it finalizes (337.2) -- but a spell's is not until
    it resolves, so the spell path passes `completed=False` and
    `spell_resolved` fires the watchers later, or never if it is countered.
    """
    state.next_discount[seat, :] = 0
    # "...if you've played an Equipment this turn" (Azir). Stamped at the one
    # site every play of every kind passes through.
    if card >= 0 and "Equipment" in table.tags[card]:
        state.equip_played_ply[seat] = int(state.ply)
    if completed:
        fire_nth_card(state, table, seat, card)


def fire_nth_card(state: GameState, table: CardTable, seat: int,
                  card: int) -> None:
    """419.4.a -- `seat` has just COMPLETED playing `card`: count it, and fire
    "when you play your Nth card" for the count it reached."""
    state.cards_completed[seat] += 1
    nth = int(state.cards_completed[seat])
    for w in range(state.n_perms):
        if state.perms[w, P_ALIVE] != 1:
            continue
        mine = int(state.perms[w, P_CTRL]) == seat
        for ab in row_abilities(state, table, w):
            # `subject_nth` 0 is "when you play A card" (Viktor, Innovator).
            if ab.trigger != TR_NTH_CARD or (ab.subject_nth
                                             and ab.subject_nth != nth):
                continue
            # "a card with Power cost {any rune}{any rune} or more" (Yordle
            # Explorer) -- the printed cost of the card just played.
            if ab.subject_min_power and not (
                    card >= 0 and int(table.power[card]) >= ab.subject_min_power):
                continue
            if ab.subject_enemy == mine:
                continue
            # "...if I'm at a battlefield" (Astral Heron). 359.3.f decides
            # whether the ability triggers at all, so a Heron sitting at base
            # never reaches the Chain rather than fizzling there.
            if ab.subject_at_battlefield and not is_battlefield(
                    int(state.perms[w, P_LOC])):
                continue
            queue(state, TR_NTH_CARD, w, int(state.perms[w, P_LOC]))


def spell_resolved(state: GameState, table: CardTable, seat: int, card: int,
                   spent_e: int) -> None:
    """Everything that triggers on `seat` having PLAYED the spell `card`.

    419.4.a -- "triggered abilities trigger when the act of playing the card
    has been completed by the resolution of the card", so this runs from
    `resolve_top` and never from finalization. A countered spell is removed
    without resolving and never reaches it (419.4.a.1): Ravenbloom Student does
    not grow, and Astral Heron does not see a first card (RiftJudge #12538).

    `seat` is the controller AT RESOLUTION: a spell taken over on the Chain is
    played by whoever took it (RiftJudge #12400, #12165).
    """
    from rl.engine.effects import TR_PLAY_SPELL
    fire_nth_card(state, table, seat, card)
    for u in range(state.n_perms):
        row = state.perms[u]
        if row[P_ALIVE] != 1 or int(row[P_CTRL]) != seat:
            continue
        # "a spell that costs {5 energy} or more" (Lux - Illuminated) and
        # "if you spent {4 energy} or more" -- the two facts about the spell a
        # watcher can ask. The spend was noted on the item at finalization.
        if any(a.trigger == TR_PLAY_SPELL
               and int(table.energy[card]) >= a.subject_min_energy
               and spent_e >= a.subject_min_spent
               for a in row_abilities(state, table, u)):
            queue(state, TR_PLAY_SPELL, u, int(row[P_LOC]))
    # ...and every BATTLEFIELD's (Abandoned Hall, Forgotten Library). "When a
    # player plays a spell" is about the player, not about where the spell was
    # played, so each live ground is asked once for the caster's seat.
    for _i in state.live_bfs():
        _combat()._queue_bf_trigger(state, table, TR_PLAY_SPELL, _i, seat,
                                    subj=card)
    # ...and the LEGEND's (Lux - Lady of Luminosity, Jhin - Virtuoso).
    lcard = int(state.legend[seat])
    if lcard >= 0:
        for a in legend_abilities_for(table, lcard):
            if (a.trigger == TR_PLAY_SPELL
                    and int(table.energy[card]) >= a.subject_min_energy
                    and spent_e >= a.subject_min_spent):
                queue(state, TR_PLAY_SPELL, legend_src(seat), -1,
                      subj=card, who=seat)
                break


def _combat():
    from rl.engine import combat
    return combat


def fire_play_unit(state: GameState, table: CardTable, seat: int,
                   card: int, perm: int = -1) -> None:
    """Queue "when you play a unit" watchers for `seat` (Lillia).

    Called from BOTH places a unit can be played -- from hand in
    `actions._resolve_play`, and as a token by `OP_CREATE_TOKEN`. A token is
    played, not conjured (187), so a watcher that only saw hand plays would
    miss the entire token deck it exists to reward.

    Every PERMANENT play reaches here, gear included, so each watcher states
    the type it wants via `subject_card_type` (default "Unit"). Pit Crew wants
    gear; without the filter Lillia's kin fired on both.
    """
    from rl.engine.effects import YOUR_DAMAGE_KILLS
    if table.names[card] in YOUR_DAMAGE_KILLS:
        # 337.2 then 319.4: the permanent resolves and a Cleanup follows BEFORE
        # its "when you play me" is placed, so damage already marked on an
        # enemy dies to Elder Dragon's static before anyone can answer the
        # trigger (RiftJudge #12102). The engine's Cleanup waits for the
        # trigger's targets, so the lethal sweep is run here instead.
        _combat().enforce_lethal(state, table)
    is_token = table.is_token(card)
    # Jax - Unmatched: "Your Equipment everywhere have [Quick-Draw]" -- the
    # attach-on-play half, granted for this turn to an Equipment without it.
    from rl.engine.effects import GRANTED_ABILITIES, TR_PLAY_ME as _TPM
    if (perm >= 0 and "Equipment" in table.tags[card]
            and not table.has(card, "Quick-Draw")):
        jax = next((i for i in range(state.n_perms)
                    if state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == seat
                    and table.names[int(state.perms[i, P_CARD])] == "Jax - Unmatched"),
                   -1)
        if jax >= 0:
            state.granted_card[perm] = int(state.perms[jax, P_CARD])
            state.granted_ply[perm] = int(state.ply)
            if not has_trigger(table, card, _TPM):
                queue(state, _TPM, perm, int(state.perms[perm, P_LOC]))
    # Sun Disc -- "the next unit you play this turn enters ready" is spent by
    # this play (it has already been read as the unit entered).
    if (table.is_type(card, "Unit")
            and int(state.next_unit_ready_ply[seat]) == int(state.ply)):
        state.next_unit_ready_ply[seat] = -1
    for w in range(state.n_perms):
        if state.perms[w, P_ALIVE] != 1:
            continue
        mine = int(state.perms[w, P_CTRL]) == seat
        for ab in row_abilities(state, table, w):
            if ab.trigger != TR_PLAY_UNIT:
                continue
            # "When you play a unit" (Lillia) watches its OWN controller;
            # "when an OPPONENT plays a unit" (Vex) watches the other seat.
            # One flag rather than two triggers, because everything else about
            # them -- when they fire, what they see -- is identical.
            if ab.subject_enemy == mine:
                continue
            # "When you play a UNIT" must not fire on a gear. Every permanent
            # play arrives here, so the type is the watcher's business.
            if not table.is_type(card, ab.subject_card_type):
                continue
            if ab.subject_token and not is_token:
                continue
            if ab.subject_nontoken and is_token:
                continue
            if ab.subject_not_self and w == perm:
                continue
            if ab.in_showdown and int(state.showdown_bf) < 0:
                continue
            if ab.subject_lacks_tag and perm >= 0 and ab.subject_lacks_tag in \
                    combat_perm_tags(state, table, perm):
                continue
            # "...or another DRAGON" -- a tag the played card must carry. Asked
            # of the CARD rather than of `perm`, because a play watcher has to
            # answer before the permanent exists in some paths and the card is
            # the thing that was played either way.
            if ab.subject_tag and ab.subject_tag not in table.tags[card]:
                continue
            # Vex needs somewhere to point [Stun], and that is the permanent
            # just played -- not a target, so it rides as the subject the same
            # way an attack trigger's does.
            if ab.subject_enemy and perm < 0:
                continue
            if ab.subject_at_battlefield and not is_battlefield(
                    int(state.perms[w, P_LOC])):
                continue
            # "The first time you play a non-token gear each turn" (Jayce) --
            # stamped last, as `fire_watchers` does.
            if ab.once_each_turn:
                if int(state.once_used[w]) == int(state.ply):
                    continue
                state.once_used[w] = int(state.ply)
            queue(state, TR_PLAY_UNIT, w, int(state.perms[w, P_LOC]),
                  subj=perm)

    # ...and the BATTLEFIELD the permanent landed on (Valley of Idols, Star
    # Spring). "When a player plays a unit HERE" is about the ground it
    # arrived at, so nothing fires for a play to a base.
    if perm >= 0:
        from rl.engine.combat import _queue_bf_trigger
        from rl.engine.state import bf_index as _bfi
        _pl = int(state.perms[perm, P_LOC])
        if is_battlefield(_pl):
            # A battlefield watcher filters the same way a permanent's does:
            # Star Spring asks for a NON-TOKEN unit (RiftJudge #10403, #10351).
            from rl.engine.effects import bf_abilities_for as _bfa
            _bfc = int(state.bf_card[_bfi(_pl)])
            _ok = _bfc < 0 or any(
                ab.trigger == TR_PLAY_UNIT
                and not (ab.subject_nontoken and is_token)
                and not (ab.subject_token and not is_token)
                for ab in _bfa(table, _bfc))
            if _ok:
                _queue_bf_trigger(state, table, TR_PLAY_UNIT, _bfi(_pl), seat,
                                  subj=perm)

    # ...and each LEGEND, which watches plays from the Legend Zone (Rengar -
    # Pridestalker, Volibear - Relentless Storm, Nasus - Curator of the Sands).
    # The same filters, minus the ones that ask where the watcher is standing.
    for who in range(N_SEATS):
        lcard = int(state.legend[who])
        if lcard < 0:
            continue
        mine = who == seat
        for ab in legend_abilities_for(table, lcard):
            if ab.trigger != TR_PLAY_UNIT or ab.subject_enemy == mine:
                continue
            if not table.is_type(card, ab.subject_card_type):
                continue
            if ab.subject_token and not is_token:
                continue
            if ab.subject_nontoken and is_token:
                continue
            if ab.in_showdown and int(state.showdown_bf) < 0:
                continue
            if ab.subject_tag and ab.subject_tag not in table.tags[card]:
                continue
            if ab.subject_lacks_tag and perm >= 0 and ab.subject_lacks_tag in \
                    combat_perm_tags(state, table, perm):
                continue
            if ab.subject_enemy and perm < 0:
                continue
            # "when you play a [Mighty] unit" (Volibear) -- read off the
            # permanent that just arrived, since Might is a board fact.
            if ab.subject_min_power and not (
                    perm >= 0 and _combat().might(state, table, perm)
                    >= ab.subject_min_power):
                continue
            # "...with Energy cost {7 energy} or more" (Nasus).
            if int(table.energy[card]) < ab.subject_min_energy:
                continue
            if ab.once_each_turn:
                if int(state.legend_once[who]) == int(state.ply):
                    continue
                state.legend_once[who] = int(state.ply)
            queue(state, TR_PLAY_UNIT, legend_src(who), -1, subj=perm,
                  who=who)
            break

    # Delayed Abilities watching the same event (389-390). They are NOT on the
    # board -- the spell that armed them is in a trash -- so the permanent walk
    # above can never reach them, and they need their own pass.
    #
    # Only the arming seat's own are consulted: every delayed trigger in the
    # pool says "a FRIENDLY unit". A card that watches the opponent's plays
    # would want `subject_enemy` here, the same flag the permanent walk uses.
    for slot in range(MAX_DELAYED):
        armed = int(state.delayed[seat, slot])
        if armed < 0:
            continue
        for ab in delayed_abilities_for(table, armed):
            if ab.trigger != TR_PLAY_UNIT:
                continue
            if not table.is_type(card, ab.subject_card_type):
                continue
            if ab.subject_token and not is_token:
                continue
            if ab.subject_nontoken and is_token:
                continue
            # "The NEXT time you play a unit this turn" -- only one firing may
            # be outstanding. The slot is disarmed as the trigger is PLACED
            # (`fire`), since placement reads the card back out of it; until
            # then a second play must not queue a second copy.
            if ab.delayed_once and any(
                    int(state.trig[t, 1]) == delayed_src(seat, slot)
                    for t in range(int(state.n_trig))):
                continue
            queue(state, TR_PLAY_UNIT, delayed_src(seat, slot), -1, subj=perm)


def arm_delayed(state: GameState, seat: int, card: int) -> int:
    """Put `card`'s Delayed Ability into a free slot. Returns the slot, or -1.

    Duplicates are kept rather than collapsed: arming the same card twice
    really does create two delayed abilities and both fire (390). It is a no-op
    for Rally the Troops -- 426.1.b.1 caps a unit at one Buff -- but that is a
    fact about Buff, not about delayed abilities.
    """
    for slot in range(MAX_DELAYED):
        if int(state.delayed[seat, slot]) < 0:
            state.delayed[seat, slot] = card
            return slot
    # Not an assertion: a seat somehow arming a ninth delayed ability in one
    # turn should lose the ninth, not take down a training run. Three copies is
    # the deck limit and one card in the pool arms one, so the real ceiling is
    # 3 against 8.
    return -1


def trig_card(state: GameState, src: int) -> int:
    """The card an ability source is printed on.

    Four kinds of source: a permanent row, a battlefield slot, a legend zone,
    and a Delayed Ability slot (389-390). One decoder, because every caller
    downstream only wants the card.
    """
    if is_bf_src(src):
        return int(state.bf_card[bf_src_index(src)])
    if is_legend_src(src):
        return int(state.legend[legend_src_seat(src)])
    if is_delayed_src(src):
        # The card that ARMED the delayed ability, which is in a trash by now.
        # Stored rather than derived for exactly that reason.
        return int(state.delayed[delayed_src_seat(src), delayed_src_slot(src)])
    if is_trash_src(src):
        return -1          # the card rides the queue entry; see `fire`
    return state.eff_card(src)


def trig_controller(state: GameState, i: int) -> int:
    """Which seat controls queued trigger `i`.

    A permanent's ability is controlled by whoever controls the permanent. A
    BATTLEFIELD's is not: the battlefield has no controller of its own, and
    "when you conquer here" belongs to the player who conquered even though
    control of the battlefield can change again before the queue drains. That
    seat is therefore carried on the queue entry rather than re-derived.
    """
    who = int(state.trig[i, 5])
    if who >= 0:
        return who
    src = int(state.trig[i, 1])
    # A LEGEND's and a DELAYED ability's sentinel both encode their own seat,
    # so neither needs the seat carried -- but neither is a permanent row
    # either, and reading `perms[src]` with a negative sentinel indexes the
    # array from the END and returns some unrelated unit's controller.
    if is_legend_src(src):
        return legend_src_seat(src)
    if is_delayed_src(src):
        return delayed_src_seat(src)
    return int(state.perms[src, P_CTRL])


def next_placer(state: GameState) -> int:
    """Which seat places the next queued trigger, or -1 if the queue is empty.

    383.3.d.1 -- "starting with the Turn Player and proceeding in Turn Order,
    each player orders their Triggered Abilities on the Chain." So the turn
    player empties their queue first, then the opponent.
    """
    step = _oldest_step(state)
    for seat in (int(state.active), 1 - int(state.active)):
        for i in range(int(state.n_trig)):
            if (int(state.trig[i, 6]) == step
                    and trig_controller(state, i) == seat):
                return seat
    return -1


def _oldest_step(state: GameState) -> int:
    """The lowest step stamp still queued -- the only one being placed."""
    n = int(state.n_trig)
    return int(state.trig[:n, 6].min()) if n else -1


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
    step = _oldest_step(state)
    for i in range(int(state.n_trig)):
        if trig_controller(state, i) != seat or int(state.trig[i, 6]) != step:
            continue
        src = int(state.trig[i, 1])
        key = (trig_card(state, src), int(state.trig[i, 0]),
               int(state.trig[i, 2]), int(state.trig[i, 4]))
        if is_trash_src(src):
            key += (int(state.trig[i, 3]),)     # which discarded card
        # A unit's own Deathknell and its Equipment's are different abilities
        # on one source; the gear rides as the subject (see `fire`).
        if int(state.trig[i, 0]) == TR_DEATH and int(state.trig[i, 3]) >= 0:
            key += (int(state.perms[int(state.trig[i, 3]), P_CARD]),)
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
    trigger, src, ctx, subj, ctx2, who = (int(x) for x in state.trig[i, :6])
    added = fire(state, table, cfg, trigger, src, ctx, subj, ctx2, who)
    n = int(state.n_trig)
    if i < n - 1:
        state.trig[i:n - 1] = state.trig[i + 1:n]
    state.trig[n - 1] = -1
    state.n_trig = n - 1
    return added


def fire(state: GameState, table: CardTable, cfg: Config, trigger: int,
         src: int, ctx: int = -1, subj: int = -1, ctx2: int = -1,
         who: int = -1) -> int:
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
    if is_trash_src(src):
        card, subj = subj, -1         # the card rides the queue as the subject
    else:
        card = trig_card(state, src)
    if card < 0:
        return 0          # the battlefield slot is empty; nothing to fire
    if is_trash_src(src):
        ctrl = trash_src_seat(src)
        abils = [(card, k, a) for k, a in enumerate(abilities_for(table, card))]
    elif is_bf_src(src):
        # A battlefield's abilities live in their own table, for the same
        # reason its statics do: it is not a permanent, and putting them in
        # `ABILITIES` would make every permanent-side loop that walks a card's
        # abilities start finding them.
        ctrl = who
        abils = [(card, k, a) for k, a in
                 enumerate(bf_abilities_for(table, card))]
    elif is_legend_src(src):
        # A legend HAS an owner, so the controller is recoverable from the
        # source alone -- unlike a battlefield, which needed the seat carried.
        ctrl = legend_src_seat(src)
        abils = [(card, k, a) for k, a in
                 enumerate(legend_abilities_for(table, card))]
    elif is_delayed_src(src):
        # Same as a legend: the seat is half of what the sentinel encodes.
        ctrl = delayed_src_seat(src)
        abils = [(card, k, a) for k, a in
                 enumerate(delayed_abilities_for(table, card))]
        if any(a.delayed_once and a.trigger == trigger for _, _, a in abils):
            state.delayed[ctrl, delayed_src_slot(src)] = -1
    elif trigger == TR_DEATH and subj >= 0:
        # An Equipment's Deathknell, queued by `combat._destroy` with the GEAR
        # as the subject because the unit has already shed it (719.5). The
        # unit is still the source -- "I" is the unit (136.2.c) -- and the
        # card that travels is the gear's, which is how `item_spec` finds it.
        ctrl = int(state.perms[src, P_CTRL])
        gcard = int(state.perms[subj, P_CARD])
        abils = [(gcard, k, a) for k, a in
                 enumerate(equip_abilities_for(table, gcard))]
    elif trigger == TR_TEMPORARY:
        # 816 -- the keyword's own ability, synthesized for whatever row is
        # carrying [Temporary] right now (printed on the card, or granted by
        # Fading Memories / Shadow's Call / Last Stand).
        from rl.engine.effects import ABIL_TEMPORARY, TEMPORARY_ABILITY
        ctrl = int(state.perms[src, P_CTRL])
        abils = [(card, ABIL_TEMPORARY, TEMPORARY_ABILITY)]
    else:
        ctrl = int(state.perms[src, P_CTRL])
        # 721.2 -- an Inactive ability "does not trigger", so an Attached
        # permanent contributes none of its own...
        own = () if state.is_attached(src) else abilities_for(table, card)
        abils = [(card, k, a) for k, a in enumerate(own)]
        # ...and 718.3 appends the ones its Equipment carries. These are
        # numbered in `EQUIP_ABILITIES` under the EQUIPMENT's name, which is
        # why the card travels with the index rather than being assumed to be
        # the source row's -- `item_spec` reads both back off the Chain Item.
        abils.extend(appended_abilities(state, table, src))
    n = 0
    for acard, k, ab in abils:
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
        #
        # 811 -- was this permanent played FROM FACE DOWN? A row flag, since
        # the card left its Facedown Zone before the queue drained. Only a
        # real permanent can carry one.
        #
        # Asked as `src >= 0` rather than by naming the sentinel kinds. Every
        # sentinel is negative and so is the -1 that means "no source", so this
        # is the same question and it cannot go stale -- the enumeration it
        # replaces listed battlefields and legends, and adding a third kind
        # (Delayed Abilities, 389-390) made it index `perms` from the END and
        # return an unrelated unit's flags.
        hidden_play = (src >= 0
                       and bool(int(state.perms[src, P_FLAGS])
                                & F_FROM_HIDDEN))
        # "When you play me from face down [on your turn]" -- narrowings of
        # the TRIGGER (359.3.f), so a play that does not match never reaches
        # the Chain at all. See `Ability.from_hidden` for why this is not an
        # op condition.
        if ab.from_hidden and not hidden_play:
            continue
        # 828.1.d -- an [Empowered] dependent trigger does not exist unless its
        # source holds the status, so it never reaches the Chain otherwise.
        if ab.while_empowered and not (src >= 0 and state.empower_count(src)):
            continue
        # "When I die IN COMBAT" -- read off the snapshot on the dead row.
        if ab.died_in_combat and not (
                src >= 0 and int(state.perms[src, P_FLAGS]) & F_DIED_IN_COMBAT):
            continue
        if ab.own_turn and ctrl != int(state.active):
            continue
        if ab.opp_turn and ctrl == int(state.active):
            continue
        if ab.cond != COND_NONE and not ability_cond_holds(
                state, table, ab, ctrl, src, ctx, ctx2):
            continue
        # "When you play me TO A BATTLEFIELD" -- where the permanent LANDED,
        # which for a play trigger is simply where it is now.
        if ab.at_battlefield and not (
                src >= 0 and is_battlefield(int(state.perms[src, P_LOC]))):
            continue
        # 811.1.d.2 -- "if a PLAY EFFECT of a hidden permanent chooses any
        # targets, those targets must be chosen from among options at that
        # battlefield". The permanent is standing on that battlefield (811.
        # 1.d.1 forced it there), so its own location IS the binding, and no
        # separate column has to ride the trigger queue to carry one.
        #
        # Scoped to TR_PLAY_ME on purpose. F_FROM_HIDDEN stays set for the
        # permanent's whole life, but the rule restricts only the play
        # effect -- a later [Deathknell] or move trigger on the same body
        # chooses freely, and binding those too would be a narrowing the card
        # never printed.
        bound = -1
        if (trigger == TR_PLAY_ME and hidden_play
                and is_battlefield(int(state.perms[src, P_LOC]))):
            bound = bf_index(int(state.perms[src, P_LOC]))
        if ab.n_targets and not rsv.can_be_cast(state, table, ab, ctrl, bound,
                                                src, acard):
            continue
        push(state, acard, ctrl, from_hand=False, abil=k, src=src, ctx=ctx,
             subj=subj, ctx2=ctx2, bound_bf=bound)
        n += 1
    return n


def index_of_uid(state: GameState, uid: int) -> int:
    """Chain index holding `uid`, or -1 if it has already left the chain."""
    for i in range(state.n_chain):
        if int(state.chain[i, C_UID]) == uid:
            return i
    return -1


def counter(state: GameState, table: CardTable, uid: int,
            to_hand: bool = False) -> str | None:
    """Remove a chain item without resolving it. Returns its card name.

    A countered spell still goes to the trash -- it was played, it just never
    resolved. Returns None if it is already gone, which is normal: two players
    can counter the same item, and the second one fizzles (359.3.e).

    **Unless it was played for its [Flow] cost.** 829.1.b.1 hangs the banish on
    *leaving the Chain after becoming a Finalized Chain Item*, not on resolving,
    and adds only one exemption -- "leaving the chain wasn't instructed by its
    own execution", which is about a spell that moves itself somewhere. A
    counter is neither. Trashing it here would return the card to the very zone
    Flow plays it from, so countering a Flow spell would REFUND it and the same
    copy could be replayed every turn forever -- the loop the banish exists to
    close, reopened by the one line that looks like it has nothing to do with
    Flow.
    """
    i = index_of_uid(state, uid)
    if i < 0:
        return None
    # "This can't be countered" (Decree of Rage) and an empowered Mel's "your
    # spells and abilities can't be countered": the counter fails, the item
    # stays. A prevention on the ACTION, so the item was a legal choice.
    if int(state.chain[i, C_ABIL]) < 0:
        _sp = spec_for(table, int(state.chain[i, C_CARD]))
        if _sp is not None and getattr(_sp, "uncounterable", False):
            return None
    if rsv._ward_count(state, table, int(state.chain[i, C_CTRL])):
        return None
    dest = int(state.chain[i, C_DEST])
    abil = int(state.chain[i, C_ABIL])
    owner = int(state.chain[i, C_OWNER])
    card, ctrl, *_ = _pop(state, i)
    if owner >= 0:
        ctrl = owner                 # its zones are its owner's
    # **An ability is not a card and has no zone to go to.** 151.2.a.1 makes an
    # activated ability behave "like a spell WITHOUT an associated card", and a
    # triggered ability is the same (383.3): its source is still a permanent on
    # the board, or already dead and in the trash. `resolve_top` has always
    # known this; this path did not, so countering an ability trashed its
    # source's card a second time and minted a duplicate out of nothing.
    #
    # It was invisible until the trash became a resource. A phantom copy pads
    # Rhasa's discount and Dr. Mundo's Might, and -- worse -- Fizz, Soulgorger
    # and Forge of the Future could all name a card that does not exist,
    # playing or recycling a copy the game never had.
    if abil < 0:
        # "Return it to its owner's hand INSTEAD OF putting it in their trash"
        # (Abandon). A replacement of the TRASH destination specifically, so a
        # countered Flow spell -- whose destination is Banishment (829.1.b.1)
        # -- is still banished: it was never going to the trash, and there is
        # nothing for the replacement to replace.
        if to_hand and dest == DEST_TRASH:
            h = int(state.n_hand[ctrl])
            assert h < state.hand.shape[1], "hand overflow from a counter"
            state.hand[ctrl, h] = card
            state.n_hand[ctrl] = h + 1
        else:
            _send(state, ctrl, card, dest)
    return table.names[card]


def _send(state: GameState, ctrl: int, card: int, dest: int) -> None:
    """Put a card that has left the Chain into its destination zone.

    One place, because the choice is per-ITEM rather than per-card: the same
    Dredge Up trashes when cast from hand and banishes when cast for its Flow
    cost, and the same spell Fizz replayed recycles instead. Reading the card
    to decide would get every one of those wrong.
    """
    if dest == DEST_BANISH:
        state.banish_card(ctrl, card)
    elif dest == DEST_RECYCLE:
        state.recycle_card(ctrl, card)
    elif int(state.riches_on[ctrl]):
        state.banish_card(ctrl, card)          # Endless Riches
    else:
        n = int(state.n_trash[ctrl])
        assert n < state.trash.shape[1], "trash overflow"
        state.trash[ctrl, n] = card
        state.n_trash[ctrl] = n + 1


def decision_open(state: GameState) -> bool:
    """Is a resolution-time decision (look, discard, ask, ...) waiting?"""
    return bool(state.pend_look >= 0 or state.pend_discard >= 0
                or state.pend_hand_play >= 0 or state.pend_ask >= 0
                or int(state.pend_reveal[0]) >= 0 or state.pend_grave >= 0
                or state.pend_cull >= 0 or int(state.pend_double[0]) >= 0
                or state.pend_tax >= 0 or state.rp_seat >= 0
                or state.pend_split >= 0 or state.pend_amount >= 0
                or state.steal_seat >= 0 or state.pend_name >= 0
                or state.dj_seat >= 0 or state.pend_altar >= 0
                or state.pend_repl >= 0)


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
    """340.1 -- the newest Finalized item resolves, alone.

    One chain item is one resolution even when [Repeat] runs its instructions
    twice, so lethal damage from both executions waits for the same Cleanup
    (`combat.RESOLVING`; RiftJudge #10889).
    """
    from rl.engine import combat as _cmb
    _cmb.RESOLVING[0] += 1
    try:
        return _resolve_top(state, table, cfg)
    finally:
        _cmb.RESOLVING[0] -= 1
        if not _cmb.RESOLVING[0] and _cmb.HELD_DEATHS:
            _cmb.release_held_deaths(state, table)


def _resolve_top(state: GameState, table: CardTable, cfg: Config) -> dict:
    item = newest_finalized(state)
    assert item >= 0, "resolve_top with no finalized item"
    spec = item_spec(state, table, item)
    abil = int(state.chain[item, C_ABIL])
    src = int(state.chain[item, C_SRC])
    ctx = int(state.chain[item, C_CTX])
    ctx2 = int(state.chain[item, C_CTX2])
    dest = int(state.chain[item, C_DEST])
    subj = int(state.chain[item, C_SUBJ])
    repeated = int(state.chain[item, C_REPEAT]) in (1, 3)
    owner = int(state.chain[item, C_OWNER])
    paid_optional = int(state.chain[item, C_REPEAT]) in (2, 3)
    uid_now = int(state.chain[item, C_UID])
    owed_play = int(state.chain[item, C_PLAY_SPELL]) == 1
    spent_e = int(state.chain[item, C_SPENT_E])
    card, ctrl, from_hand, bound, targets = _pop(state, item)

    assert spec is not None, f"no spec for {table.names[card]!r} on the chain"
    # 820.2.a -- a repeated spell carries a target set per execution.
    n1 = getattr(spec, "exec_len", 0)
    again_targets = targets[n1:2 * n1] if n1 else None
    spec = single_execution(spec)
    # Ravenborn Tome -- this spell was the "next spell" it named.
    if abil < 0 and int(state.bonus_uid[ctrl]) == uid_now:
        state.resolving_bonus = 1
        state.bonus_uid[ctrl] = -1
    state.resolving_paid = int(abil < 0 and paid_optional)
    from rl.engine import combat as _cb
    _prev_killer = _cb.KILLER[:]
    _cb.KILLER[:] = [ctrl, abil < 0]
    try:
        log = rsv.resolve(state, table, cfg, spec, ctrl,
                          targets[:spec.n_targets], bound, from_hand,
                          source=src, ctx=ctx, subj=subj, ctx2=ctx2, card=card)
    finally:
        _cb.KILLER[:] = _prev_killer
    # "Banish this." (Arcane Shift, Time Warp) -- where the card lands once it
    # has RESOLVED; a countered one never reaches here and is trashed.
    if abil < 0 and getattr(spec, "banish_self", False) and dest == DEST_TRASH:
        dest = DEST_BANISH
    if repeated and decision_open(state):
        # The first pass suspended for a choice (Called Shot's look, Hard
        # Bargain's tax); the second waits for it, with the same targets
        # (`actions._settle_after_decision`).
        assert int(state.pend_repeat_card) < 0, "two deferred [Repeat]s"
        state.pend_repeat_card = card
        state.pend_repeat_seat = ctrl
        state.pend_repeat_tgts[:] = -1
        _nt = spec.n_targets
        state.pend_repeat_tgts[:_nt] = (again_targets if again_targets is not None
                                        else targets[:_nt])
        state.pend_repeat_bound = bound
        state.pend_repeat_hand = int(from_hand)
    elif repeated:
        # 820.1.d -- "execute the instructions of this chain item one
        # additional time during resolution". One more pass over the SAME ops,
        # inside the same resolution, with the second set of targets chosen
        # as the spell was played (820.2 / 820.2.a). 820.1.c.3 makes it
        # exactly one extra pass, never a loop.
        # 356.2.b -- an optional additional cost is paid ONCE, as the card is
        # played. The repeated execution is a second pass over the
        # instructions, and inside it nothing was paid, so a clause linked to
        # the payment ("you may exhaust a friendly unit. If you do, draw 2.
        # Otherwise, draw 1.") takes its OTHERWISE branch: Meditation repeated
        # by The Academy draws 2 then 1, never 2 then 2 (RiftJudge #10271).
        state.resolving_paid = 0
        again = rsv.resolve(state, table, cfg, spec, ctrl,
                            (again_targets if again_targets is not None
                             else targets[:spec.n_targets]),
                            bound, from_hand,
                            source=src, ctx=ctx, subj=subj, ctx2=ctx2,
                            card=card)
        log["repeated"] = again
    state.resolving_bonus = 0
    state.resolving_paid = 0
    log["card"] = table.names[card]
    if abil < 0 and owed_play:
        # 419.4.a -- the play is complete now, and only now.
        spell_resolved(state, table, ctrl, card, spent_e)
        # A spell played from the Facedown Zone: its "from hidden" watchers
        # wait here too, for the same reason (RiftJudge #8491). `bound` is set
        # on a spell item by that path and by no other.
        if bound >= 0 and not from_hand:
            from rl.engine.effects import TR_PLAY_FROM_HIDDEN, TR_PLAY_NONHAND
            fire_watchers(state, table, ctrl, TR_PLAY_FROM_HIDDEN)
            fire_watchers(state, table, ctrl, TR_PLAY_NONHAND)

    if abil >= 0:
        # A Triggered Ability is not a card and has no zone to go to -- its
        # source is still on the board. Only the spell path trashes anything.
        log["ability"] = abil
        return log

    # The spell leaves play. (Units never reach here -- 337.2 resolves them
    # immediately at finalization, so nothing on this chain is a permanent.)
    #
    # 829.1.b's "Then banish it" is a delayed replacement effect (829.1.b.1) on
    # where the card lands, and Fizz's "Recycle that spell after you play it"
    # replaces the same step with a different zone. Both were decided when the
    # item was pushed, which is the only moment that knows how the card was
    # played, so both arrive here as `C_DEST`.
    _send(state, owner if owner >= 0 else ctrl, card, dest)
    if dest != DEST_TRASH:
        log["dest"] = ("trash", "banished", "recycled")[dest]
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
