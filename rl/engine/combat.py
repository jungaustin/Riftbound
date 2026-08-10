"""Move declaration, Showdown, and Combat (rules 445-470).

This is the largest single piece of the engine and the one with the most
counter-intuitive rules. Four of them are load-bearing:

  1. **There is no attack action.** Move is atomic; landing where an opponent has
     Units *stages* a Combat (461), which the next Cleanup initiates (460).

  2. **Attackers are recalled if any Defender survives** (466.1.a.2). You cannot
     take a Battlefield by surviving alongside its garrison -- you must wipe it,
     or every attacking unit walks home. A half-committed attack accomplishes
     literally nothing: no damage persists (466.1.a.1 heals everyone) and no
     ground is taken. This is *the* rule that shapes the strategic layer, and it
     was missing from the first draft of PLAN.md §1.3.

  3. **Damage is a pool, spent exactly-lethal, one unit at a time** (465.2.c.3
     forbids spreading, 465.2.c.4 forbids overkill). Combined with the cleanup
     heal, the entire assignment decision collapses to "which subset dies?", and
     `[Tank]`/`[Backline]` (815.1.c.2, 826.4.b) make that subset *ordered*.

  4. **A player Scores a given Battlefield at most once per turn** (470), by
     Hold or Conquer. Retaking a Battlefield you already Held this turn is worth
     zero points -- worth doing for the board, not the scoreboard.

Everything heals afterward, so nothing here leaves residue except deaths,
locations, and Control.

One consequence worth knowing before you read `damage_step`: **with vanilla units
combat is always decisive.** Both sides surviving would need the attacker's pool
too small to kill any defender *and* the defender's pool too small to kill every
attacker -- `SA < SD` and `SD < SA` at once, where `S` is summed Might. So with
plain bodies one side is always wiped and the Recall never fires.

**`[Stun]` is what breaks that symmetry**, and it is why the Recall exists. A
Stunned unit contributes nothing to its pool (423.1.b) but still needs its full
Might in damage to die (423.1.c), so it decouples `SA` from `SD` in exactly the
way the algebra above forbids. The project owner's example: attack a 9-Might unit
with a 5-Might unit and Stun the defender. Your 5 is not lethal, their 0 kills
nothing, both live -- and because a Defender survived, your attacker is Recalled
and the Conquer fails. That is the shape of every real combat trick in this game,
and it is why `[Stun]` belongs in the first effect-DSL batch. See PLAN.md §1.3.e.
"""

from __future__ import annotations

import numpy as np

from rl.config import Config
from rl.engine.cardtable import CardTable
from rl.engine.effects import (CNT_BOARD, CNT_NONE, CNT_TRASH,
                               COND_LEGION, COND_LEVEL, COND_NONE,
                               SC_SELF, ST_KEYWORD, ST_MIGHT,
                               TR_ATTACK_OR_DEFEND,
                               TR_DEATH, TR_MOVE, abilities_for,
                               statics_for)
from rl.engine.state import (GRANT_IDX, P_MIGHT_MOD, F_BUFFED,
                             F_DIED_ALONE,
                             F_NON_UNIT, F_NO_COMBAT_DAMAGE,
                             N_BF, N_SEATS, P_ALIVE,
                             P_ARRIVED, P_CARD, P_CTRL, P_DMG, P_FLAGS, P_LOC,
                             P_READY, SD_CLEANUP, SD_DAMAGE, SD_NONE,
                             SD_PRIORITY, GameState, base_loc, bf_loc, bf_index,
                             is_battlefield)

POINTS_PER_CONQUER = 1


# ---------------------------------------------------------------------------
# Unit characteristics
# ---------------------------------------------------------------------------

def static_might(state: GameState, table: CardTable, perm: int) -> int:
    """Might granted to `perm` right now by static abilities on the board.

    Derived on every read rather than cached. A static is continuous: Petal
    Pixie grows the instant a Sprite arrives beside her, with nothing on the
    Chain and no window to respond in, so there is no moment at which a cached
    value could be refreshed that is not "all of them". Caching would need
    invalidation on every move, death, arrival and control change -- the exact
    set of events most likely to be missed.

    It is O(live permanents) per call and `might` is hot, so this is the first
    place to look if the engine gets slow. Measured at 48 rows it is not yet
    the bottleneck.
    """
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
        return 0
    seat, loc = int(row[P_CTRL]), int(row[P_LOC])
    is_token = table.is_token(int(row[P_CARD]))
    total = 0
    for i in range(state.n_perms):
        src = state.perms[i]
        if src[P_ALIVE] != 1:
            continue
        for st in statics_for(table, int(src[P_CARD])):
            if st.kind != ST_MIGHT:
                continue
            src_seat = int(src[P_CTRL])
            if st.scope == SC_SELF:
                if i != perm:
                    continue
            else:                               # SC_FRIENDLY_UNITS
                if src_seat != seat:
                    continue
                if st.scope_token and not is_token:
                    continue
                if not table.is_type(int(row[P_CARD]), "Unit"):
                    continue
            if not static_applies(state, st, src_seat):
                continue
            total += st.n * static_count(state, table, st, src_seat,
                                         int(src[P_LOC]), int(src[P_CARD]))
    return total


def static_applies(state: GameState, st, src_seat: int) -> bool:
    """Is this static's gate satisfied for its controller right now?

    Shared by `static_might` and `cost.energy_discounts`, because a gate that
    only one of them honours is a card that is half on: Master Yi - Unstoppable
    gates a COST on [Level 3] and Targonian Visionary gates MIGHT on [Level 11],
    and both must ask the same question. Read live -- XP never resets, so there
    is no past moment to snapshot the way [Legion] needs.
    """
    if st.cond == COND_NONE:
        return True
    if st.cond == COND_LEVEL:
        return int(state.xp[src_seat]) >= st.level
    if st.cond == COND_LEGION:
        return bool(state.cards_played[src_seat])
    return False


def static_count(state: GameState, table: CardTable, st, src_seat: int,
                 src_loc: int, src_card: int) -> int:
    """How many things this static's "for each ..." clause counts. 1 if none.

    Shared by Might statics and cost discounts on purpose: "I have +1 Might for
    each X" and "I cost {1 energy} less for each X" differ only in what they do
    with the number, and letting them count separately is how the two drift
    apart.

    Returning 1 for a static with no counting clause is what makes `n * count`
    the single formula for both the flat and the scaled case.
    """
    source = (CNT_TRASH if st.per == CNT_TRASH else
              CNT_BOARD if (st.per_keyword or st.per_card_type) else CNT_NONE)
    if source == CNT_NONE:
        return 1
    if source == CNT_TRASH:
        # "in your trash" -- the STATIC's controller, never the reader's. A
        # card is in exactly one player's trash and that is whose it counts.
        n = int(state.n_trash[src_seat])
        if st.per_same_name:
            return int(np.count_nonzero(state.trash[src_seat, :n] == src_card))
        return n
    n = 0
    for j in range(state.n_perms):
        o = state.perms[j]
        if o[P_ALIVE] != 1:
            continue
        if st.per_friendly and int(o[P_CTRL]) != src_seat:
            continue
        if st.per_same_loc and int(o[P_LOC]) != src_loc:
            continue
        card = int(o[P_CARD])
        if st.per_keyword and not table.has(card, st.per_keyword):
            continue
        if st.per_card_type and not table.is_type(card, st.per_card_type):
            continue
        n += 1
    return n


def perm_kw(state: GameState, table: CardTable, perm: int, keyword: str) -> int:
    """A permanent's effective value for `keyword`: printed plus anything
    granted to it. 0 means it does not have the keyword at all.

    **Never read `table.has` or `table.assault` off a permanent directly** --
    the same rule `combat.might` states for Might, and for the same reason. A
    site that reads the printed value ignores every grant, and the failure is
    silent: the unit simply does not get the [Ganking] it was given.

    Grants ADD to the printed value (807.1.c makes [Assault X] short for an
    ability, and two abilities both apply). For a valueless keyword the value
    is 1, so any nonzero result means "has it".
    """
    printed = _printed_kw(table, int(state.perms[perm, P_CARD]), keyword)
    granted = static_keyword(state, table, perm, keyword)
    idx = GRANT_IDX.get(keyword)
    if idx is None:
        return printed + granted    # nothing can grant it with an EFFECT
    return (printed + granted + int(state.kw_grant[perm, idx])
            + int(state.kw_grant_turn[perm, idx]))


def static_keyword(state: GameState, table: CardTable, perm: int,
                   keyword: str) -> int:
    """Value of `keyword` granted to `perm` by statics on the board right now.

    Derived on every read, exactly like `static_might` and for the same reason:
    a static is continuous, so "your token units have [Tank]" starts applying
    the instant Lillia arrives and stops the instant she dies, with nothing on
    the Chain and no moment at which a cache could be refreshed.
    """
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
        return 0
    seat, loc = int(row[P_CTRL]), int(row[P_LOC])
    card = int(row[P_CARD])
    is_token = table.is_token(card)
    total = 0
    for i in range(state.n_perms):
        src = state.perms[i]
        if src[P_ALIVE] != 1:
            continue
        for st in statics_for(table, int(src[P_CARD])):
            if st.kind != ST_KEYWORD or st.keyword != keyword:
                continue
            src_seat = int(src[P_CTRL])
            if not static_applies(state, st, src_seat):
                continue
            if st.scope == SC_SELF:
                if i != perm:
                    continue
            else:
                if src_seat != seat:
                    continue
                if st.scope_token and not is_token:
                    continue
                if st.scope_not_self and i == perm:
                    continue
                if st.scope_same_loc and int(src[P_LOC]) != loc:
                    continue
                if not table.is_type(card, "Unit"):
                    continue
            total += max(1, st.n)
    return total


def _printed_kw(table: CardTable, card: int, keyword: str) -> int:
    """The printed value of a keyword on a card: its number, or 1 if bare."""
    if keyword == "Assault":
        return int(table.assault[card])
    if keyword == "Shield":
        return int(table.shield[card])
    if keyword == "Deflect":
        return int(table.deflect[card])
    return 1 if table.has(card, keyword) else 0


def combat_role_bonus(state: GameState, table: CardTable, perm: int) -> int:
    """[Shield] and [Assault] -- Might that exists only during a Combat.

    807.1.c "while I am an attacker, I have +X [M]"; 814.1.c the same for a
    defender. Both are keyed to the Attacker/Defender **designation** (459), not
    to who moved: `state.attacker` holds it, and it survives for as long as the
    Combat does (807.1.d.1, 814.1.d.1).

    The value is a real number, not a flag -- [Assault 2], [Shield 3] -- and "if
    X is omitted, it is presumed to be 1".
    """
    bf = int(state.showdown_bf)
    if bf < 0:
        return 0
    row = state.perms[perm]
    if int(row[P_LOC]) != bf_loc(bf):
        return 0
    card = int(row[P_CARD])
    if int(row[P_CTRL]) == int(state.attacker):
        return perm_kw(state, table, perm, "Assault")
    return perm_kw(state, table, perm, "Shield")


def might(state: GameState, table: CardTable, perm: int) -> int:
    """Current Might: printed value, static abilities, and any "this turn"
    modifier, floored at 0.

    143.2.b -- "If a unit's Might is ever less than 0, it is treated as 0 when
    referenced by spells and abilities, and when summing Might to be assigned as
    damage." So a -4 on a 2-Might unit contributes 0, never -2.

    Never read `table.might` directly at a call site, or modifiers will silently
    fail to apply (PLAN.md §1.3.d).
    """
    row = state.perms[perm]
    # 703 -- each Buff counter contributes +1 Might. It is a counter, not a
    # "this turn" modifier, so it survives the end-of-turn cleanup and only
    # goes away when the unit leaves play (705).
    buff = 1 if int(row[P_FLAGS]) & F_BUFFED else 0
    return max(0, int(table.might[int(row[P_CARD])]) + int(row[P_MIGHT_MOD])
               + buff + static_might(state, table, perm)
               + combat_role_bonus(state, table, perm))


def enforce_lethal(state: GameState, table: CardTable) -> list[int]:
    """143.2.a across the whole board. Returns the rows it killed.

    `set_might_mod` and `mark_damage` check the unit they touched, which was
    enough while Might only changed one unit at a time. A static changes other
    units' Might as a side effect of something happening to its SOURCE: kill
    Soul Shepherd and every damaged token she was pumping becomes lethally
    damaged at that instant, with nothing having touched the tokens at all.

    143.2.a is worded as a continuous check for exactly this reason, so the
    sweep is the honest implementation. It loops because a death can shrink
    another unit in turn.
    """
    killed: list[int] = []
    for _ in range(state.n_perms + 1):
        # Two phases per pass. Everything lethally damaged at this instant is
        # collected FIRST, then destroyed -- so each death sees the others as
        # simultaneous rather than as having predeceased it. Destroying inline
        # made the answer depend on row order, which is exactly the kind of
        # invisible tie-break that only shows up in a card's text later.
        doomed = tuple(i for i in range(state.n_perms)
                       if state.perms[i, P_ALIVE] == 1
                       and int(state.perms[i, P_DMG]) > 0
                       and int(state.perms[i, P_DMG]) >= might(state, table, i))
        if not doomed:
            return killed
        for i in doomed:
            _destroy(state, table, i, batch=doomed)
            killed.append(i)
    raise AssertionError("enforce_lethal did not reach a fixed point")


def set_might_mod(state: GameState, table: CardTable, perm: int, delta: int,
                  floor: int | None = None) -> bool:
    """Apply a "this turn" Might change. Returns True if it killed the unit.

    Two rules make this more than an addition:

    **143.2.b** floors the *effective* Might at 0, but a card may print a
    stricter floor of its own -- Stupefy says "to a minimum of 1 Might", so the
    modifier is clamped so the result never drops below `floor`. That is part of
    the effect, not a general rule, which is why it is a parameter.

    **143.2.a** is a *continuous* check: "if a Unit EVER has nonzero damage
    marked on it equalling or exceeding its Might, it is Killed." So reducing
    Might can kill -- not by itself (lethal damage must be non-zero, 142.4.b),
    but by dropping Might to meet damage already on the board. The rulebook
    gives this as its own example: a 5-Might unit with 3 damage marked drops to
    3 Might and dies. Checking only at damage-assignment time would miss it.
    """
    row = state.perms[perm]
    # The printed floor is on EFFECTIVE Might, so statics count toward it:
    # Stupefy's "to a minimum of 1 Might" on a Sprite that Soul Shepherd has
    # pumped to 4 leaves it at 1, not at 0.
    base = int(table.might[int(row[P_CARD])]) + static_might(state, table, perm)
    new = int(row[P_MIGHT_MOD]) + delta
    if floor is not None:
        new = max(new, floor - base)      # never take effective Might below floor
    row[P_MIGHT_MOD] = new

    dmg = int(row[P_DMG])
    if dmg > 0 and dmg >= might(state, table, perm):
        _destroy(state, table, perm)
        return True
    return False


def mark_damage(state: GameState, table: CardTable, perm: int,
                amount: int) -> bool:
    """Mark damage and apply 143.2.a. Returns True if it killed the unit."""
    state.perms[perm, P_DMG] += amount
    dmg = int(state.perms[perm, P_DMG])
    if dmg > 0 and dmg >= might(state, table, perm):
        _destroy(state, table, perm)
        return True
    return False


def banish(state: GameState, table: CardTable, perm: int) -> None:
    """Remove a permanent to Banishment (427). NOT a kill.

    427.2.a is explicit that "Banish is not a subset of Kill", so this must not
    do the two things `_destroy` does: no [Deathknell] fires and the card does
    not go to the trash. Getting that wrong would hand a Deathknell deck free
    value from the opponent's removal.
    """
    state.perms[perm, P_ALIVE] = 0


def destroy(state: GameState, table: CardTable, perm: int) -> None:
    """Kill outright (428) -- no damage involved, so no lethal check."""
    _destroy(state, table, perm)


def might_for_pool(state: GameState, table: CardTable, perm: int) -> int:
    """Might this unit contributes to its side's damage pool (465.2.a/b).

    Zero if it is Stunned or otherwise blanked (423.1.b). **This is not the same
    number as `might()`** -- 423.1.c is explicit that a Stunned unit still has to
    be dealt damage equal to its *full* Might to die. Stun stops a unit hitting
    back; it never makes it easier to kill. Reading one where you meant the other
    is the most likely bug in this file.
    """
    if state.perms[perm, P_FLAGS] & F_NO_COMBAT_DAMAGE:
        return 0
    return might(state, table, perm)


def lethal_cost(state: GameState, table: CardTable, perm: int) -> int:
    """Damage still needed to destroy this unit.

    465.2.c.2 defines Lethal Damage as **non-zero** damage equaling or exceeding
    current Might, so a 0-Might unit still costs 1 to kill -- it is not free, and
    it does not die to an empty pool.
    """
    return max(1, might(state, table, perm) - int(state.perms[perm, P_DMG]))


def _destroy(state: GameState, table: CardTable, perm: int,
             batch: tuple[int, ...] = ()) -> None:
    """Kill a permanent and put its card in its controller's trash.

    808.1.d.2 -- a Deathknell is added to the Chain as a Pending Item *before*
    the card moves to the Trash, and 808.1.d.3 says to note its location first.
    Queueing here does both: the location is captured at the moment of death,
    and the actual Chain push happens at the next safe point (see
    `chain.queue`, which explains why it cannot happen inline).

    `batch` is the rest of the units dying in this same lethal check. They are
    still standing as far as this death is concerned: 143.2.a is a continuous
    check, so everything it catches dies at one instant, and "I died alone"
    must not depend on which row the sweep happened to reach first. Without it,
    two friendly units dying together at one battlefield would give a different
    answer depending on their order in `perms` -- and both orders would be
    wrong, because neither of them died alone.
    """
    from rl.engine.chain import queue as chain_queue   # cycle: chain -> resolve -> combat
    row = state.perms[perm]
    if any(a.trigger == TR_DEATH for a in abilities_for(table, int(row[P_CARD]))):
        loc, ctrl = int(row[P_LOC]), int(row[P_CTRL])
        others = [i for i in range(state.n_perms)
                  if i != perm and int(state.perms[i, P_CTRL]) == ctrl
                  and int(state.perms[i, P_LOC]) == loc
                  and (state.perms[i, P_ALIVE] == 1 or i in batch)
                  and not state.has_flag(i, F_NON_UNIT)]
        if not others:
            row[P_FLAGS] |= F_DIED_ALONE
        chain_queue(state, TR_DEATH, perm, loc)
    row[P_ALIVE] = 0
    seat, card = int(row[P_CTRL]), int(row[P_CARD])
    # 185.3 -- a token that leaves the board ceases to exist; it does not go to
    # a trash, hand or deck. `OP_RETURN_TO_HAND` had this right for bounce and
    # this path did not, so every Sprite that died has been silently padding
    # its controller's trash. It stayed invisible because nothing reads the
    # trash yet -- but Rhasa the Sunderer costs less per card in it, and Fizz
    # and Spectral Matron replay from it, so a padded trash is a real number
    # being wrong rather than a cosmetic one.
    if table.is_token(card):
        return
    n = int(state.n_trash[seat])
    assert n < state.trash.shape[1], "trash overflow"
    state.trash[seat, n] = card
    state.n_trash[seat] = n + 1


# ---------------------------------------------------------------------------
# Move declaration (PLAN.md §1.3.a)
# ---------------------------------------------------------------------------
# Factored, never enumerated as subsets: choose a destination, then add units
# one at a time, then COMMIT. With N awake units the raw space is 2^N per
# destination; this way each decision point offers at most N+2 candidates.

def can_move(state: GameState, table: CardTable, cfg: Config,
             perm: int, dst_loc: int) -> bool:
    """Is this a legal ordinary Move for the turn player?

    Ordinary movement is base <-> battlefield ONLY. Lateral battlefield-to-
    battlefield movement requires `[Ganking]` ("I can move from battlefield to
    battlefield"), which is what makes commitment sticky.
    """
    row = state.perms[perm]
    if row[P_ALIVE] != 1 or row[P_READY] != 1 or row[P_CTRL] != state.active:
        return False
    if not table.is_type(int(row[P_CARD]), "Unit"):
        return False
    src = int(row[P_LOC])
    if src == dst_loc:
        return False
    if is_battlefield(src) and is_battlefield(dst_loc):
        return (not cfg.lateral_movement_needs_ganking
                or perm_kw(state, table, perm, "Ganking"))
    return True


def movable_units(state: GameState, table: CardTable, cfg: Config,
                  dst_loc: int) -> list[int]:
    """Rows the turn player could still add to a declaration headed to `dst_loc`."""
    return [i for i in range(state.n_perms)
            if not (state.decl_mask >> i) & 1
            and can_move(state, table, cfg, i, dst_loc)]


def move_destinations(state: GameState, table: CardTable,
                      cfg: Config) -> list[int]:
    """Battlefields the turn player could declare a Move to."""
    return [bf_loc(i) for i in range(N_BF)
            if movable_units(state, table, cfg, bf_loc(i))]


def declare_move(state: GameState, dst_loc: int) -> None:
    assert not state.declaring, "a declaration is already open"
    state.decl_dst = dst_loc
    state.decl_mask = 0


def add_to_declaration(state: GameState, perm: int) -> None:
    assert state.declaring, "no declaration open"
    state.decl_mask |= 1 << perm


def cancel_declaration(state: GameState) -> None:
    """Abandon a declaration. Free -- nothing has moved yet."""
    state.clear_declaration()


def queue_move_trigger(state: GameState, table: CardTable, perm: int,
                       from_loc: int) -> None:
    """"When I move from a location" -- ctx is the location LEFT (359.3.f.3).

    Captured at the moment of the move rather than read at resolution: by then
    the unit is somewhere else, and Lillia's Sprite goes where she came from.
    """
    from rl.engine.chain import queue as chain_queue   # cycle: chain -> resolve -> combat
    card = int(state.perms[perm, P_CARD])
    if any(a.trigger == TR_MOVE for a in abilities_for(table, card)):
        chain_queue(state, TR_MOVE, int(perm), int(from_loc))


def commit_declaration(state: GameState, table: CardTable, cfg: Config) -> dict:
    """Resolve the declaration: everyone arrives at once, exhausted (445-453).

    One declaration produces exactly one Showdown, however many units it holds.
    Splitting the same units across two declarations produces two Showdowns and
    hands the defender the choice of what to kill first -- a real, and usually
    bad, option that the action space must keep available.
    """
    assert state.declaring, "no declaration open"
    dst = state.decl_dst
    moved = state.declared()
    assert moved, "cannot commit an empty declaration"
    for i in moved:
        row = state.perms[i]
        queue_move_trigger(state, table, i, int(row[P_LOC]))
        row[P_LOC] = dst
        row[P_READY] = 0          # units arrive exhausted
        row[P_ARRIVED] = state.turn
    state.clear_declaration()
    return cleanup(state, table, cfg, mover=state.active, dst=dst)


def retreat(state: GameState, table: CardTable, cfg: Config, perm: int) -> dict:
    """Return a readied unit from a Battlefield to its base, on your turn.

    A Move like any other, so it exhausts. Hold banks in the Beginning Phase,
    before Main -- so retreating costs the *next* turn's point, never the one
    just collected.
    """
    row = state.perms[perm]
    assert is_battlefield(int(row[P_LOC])), "not at a battlefield"
    queue_move_trigger(state, table, perm, int(row[P_LOC]))
    row[P_LOC] = base_loc(int(row[P_CTRL]))
    row[P_READY] = 0
    return cleanup(state, table, cfg, mover=state.active, dst=-1)


# ---------------------------------------------------------------------------
# Cleanup: stage combat, resolve Control (318, 460, 461, 190.4)
# ---------------------------------------------------------------------------

def staged_combat(state: GameState) -> int:
    """Battlefield index with Units from both players, or -1 (461).

    Combat is staged by *presence*, not by the Move that created it -- so a unit
    played in via `[Ambush]` stages one exactly the same way.
    """
    for i in range(N_BF):
        a, b = state.seats_at(bf_loc(i))
        if a and b:
            return i
    return -1


def cleanup(state: GameState, table: CardTable, cfg: Config,
            mover: int = -1, dst: int = -1) -> dict:
    """Perform a Cleanup, initiating Combat if one is staged (453, 460).

    `mover`/`dst` identify who just moved where, which decides the Attacker
    designation (464.2.c.1) and who Conquers an undefended Battlefield.
    """
    log: dict = {}
    if not state.is_open:
        return log

    # 143.2.a board-wide. A Cleanup follows every board change in an Open
    # State, which makes it the one place that catches a unit becoming lethally
    # damaged because some OTHER unit changed -- a static's source dying or
    # moving away. Nothing touched the shrinking unit, so no per-unit check
    # would have fired.
    dead = enforce_lethal(state, table)
    if dead:
        log["lethal_static"] = dead

    # A Cleanup resolves EVERY staged Combat, not just the first. v0 could only
    # ever stage one at a time -- a single Move declaration has one destination
    # -- so a loop was unnecessary and its absence invisible. A spell that moves
    # a unit can stage a second one at another battlefield, and stopping after
    # the first left that one staged but never initiated.
    for _ in range(N_BF + 1):
        bf = staged_combat(state)
        if bf < 0:
            break
        # The mover applied Contested; if this fired from something other than a
        # move, the turn player is the aggressor by default.
        attacker = mover if mover >= 0 else state.active
        log.update(run_combat(state, table, cfg, bf, attacker))
        if state.showdown_bf >= 0:
            return log       # combat yielded for a response; resume later
    else:
        raise AssertionError("more staged combats than battlefields")
    if staged_combat(state) >= 0:
        return log

    # No combat: settle Control everywhere (190.4, 466.5).
    log["scored"] = []
    for i in range(N_BF):
        log["scored"].extend(_establish_control(state, table, cfg, i))
    return log


def _establish_control(state: GameState, table: CardTable, cfg: Config,
                       i: int) -> list[tuple[int, str]]:
    """Settle Control of one Battlefield and Conquer if it changed hands.

    Rule 466.5: the player with Units remaining Establishes Control if they did
    not already have it; 466.5.b: no Units at all means Uncontrolled; 466.5.d:
    establishing Control is a Conquer, subject to the once-per-turn cap (470).
    """
    scored: list[tuple[int, str]] = []
    if state.showdown_bf == i:
        return scored                      # 190.4.b: Control is frozen in combat

    loc = bf_loc(i)
    a, b = state.seats_at(loc)
    prev = int(state.bf_ctrl[i])

    if a and b:
        return scored                      # still contested; combat will settle it
    holder = 0 if a else (1 if b else -1)

    if holder < 0:
        if prev >= 0:
            state.bf_ctrl[i] = -1
            _clear_foreign_hidden(state, i, -1)
        state.bf_contested[i] = 0
        return scored

    state.bf_contested[i] = 0
    if holder == prev:
        return scored                      # 190.4.a: already theirs, nothing happens

    state.bf_ctrl[i] = holder
    _clear_foreign_hidden(state, i, holder)
    if not state.bf_scored[holder, i]:
        state.bf_scored[holder, i] = 1
        if _final_point_blocked(state, cfg, holder):
            # 471.1.b -- the Final Point cannot be taken by Conquer unless the
            # player has Scored EVERY Battlefield this turn. Otherwise they draw
            # a card instead of scoring. You cannot win off a single lucky
            # conquer; the last point demands the whole board.
            from rl.engine import phases
            phases.draw_for(state, holder, 1)
            scored.append((holder, "final_point_denied"))
            return scored
        state.points[holder] += POINTS_PER_CONQUER
        state.winner = state.check_winner(cfg.victory_score)
        scored.append((holder, "conquer"))
        # "When I conquer" fires for the units that took the ground.
        from rl.engine.chain import has_trigger, queue as chain_queue
        from rl.engine.effects import TR_CONQUER
        for u in state.units_at(loc, holder):
            if has_trigger(table, int(state.perms[u, P_CARD]), TR_CONQUER):
                chain_queue(state, TR_CONQUER, int(u), loc)
    return scored


def _final_point_blocked(state: GameState, cfg: Config, seat: int) -> bool:
    """Would this Conquer be the Final Point without having Scored everywhere?

    471.1.b: the restriction applies once a player is within one point of the
    Victory Score. 471.1.a.1 exempts every non-Conquer source, so Hold, spells
    and Burn Out points are unaffected -- only Conquer is gated.
    """
    if int(state.points[seat]) < cfg.victory_score - 1:
        return False
    return not all(state.bf_scored[seat, j] for j in range(N_BF))


def _clear_foreign_hidden(state: GameState, i: int, holder: int) -> None:
    """466.5.c / 107.3.c -- only a Battlefield's controller may hide cards there."""
    owner = int(state.fd_owner[i])
    if owner >= 0 and owner != holder:
        card = int(state.fd_card[i])
        n = int(state.n_trash[owner])
        state.trash[owner, n] = card
        state.n_trash[owner] = n + 1
        state.fd_owner[i] = -1
        state.fd_card[i] = -1


# ---------------------------------------------------------------------------
# The Steps of Combat (463-466)
# ---------------------------------------------------------------------------

def run_combat(state: GameState, table: CardTable, cfg: Config,
               bf: int, attacker: int) -> dict:
    """Initiate Combat at `bf` and run it as far as the rules allow unattended.

    Combat is a *resumable* state machine, not a function that plays itself out.
    It runs forward until either the Combat ends or a player has a real decision
    to make, and in the second case it returns with `state.showdown_bf >= 0` so
    the action layer can ask them. `advance_combat` picks it back up.

    That structure exists for one reason: the Combat Showdown Step is where
    `[Reaction]` cards and every live `[Hidden]` card are played, and that window
    is the entire interactive layer of the game (PLAN.md §5.3 gotcha 3). A
    version that resolves Combat in one call cannot represent a combat trick.
    """
    log: dict = {"combat_at": bf}
    open_showdown(state, table, bf, attacker)
    return advance_combat(state, table, cfg, log)


def window_is_live(state: GameState, table: CardTable, cfg: Config) -> bool:
    """Is this priority window an actual decision for anybody?

    A window in which *neither* player can play anything and no Chain Item is
    pending cannot change the game, so skipping it is not the same as
    auto-passing a real decision -- the distinction PLAN.md §5.3 gotcha 3 turns
    on. Both seats are checked, not just the one holding priority: a window is
    live if *anyone* can act in it.

    This is what keeps v0 bit-identical. With no Reaction-speed cards yet,
    `showdown_responses` is empty for both seats, so combat still resolves in
    one call and the Phase 1-4 gate numbers do not move.
    """
    if not state.is_open:
        return True                        # a Chain Item is pending (312.2.c/d)
    return any(showdown_responses(state, table, cfg, s) for s in range(N_SEATS))


def advance_combat(state: GameState, table: CardTable, cfg: Config,
                   log: dict | None = None) -> dict:
    """Run Combat forward until somebody must decide, or until it ends."""
    log = {"combat_at": state.showdown_bf} if log is None else log
    guard = 0
    while state.showdown_bf >= 0:
        guard += 1
        assert guard <= N_SEATS * 8, "combat failed to terminate"

        if state.showdown_step == SD_PRIORITY:
            # `window_is_live` decides whether to OPEN a window, never whether
            # to leave one. Once both players have passed in succession (339.1)
            # the Showdown Step is over and Combat proceeds, however many
            # Reactions remain affordable -- re-testing affordability here made
            # the pass loop unable to terminate, because passing does not make a
            # card unaffordable.
            #
            # Random agents hid this: they eventually play a card and break the
            # cycle. A deterministic agent that keeps passing never does, which
            # is why greedy livelocked and the fuzz stayed clean.
            if state.passes < N_SEATS and window_is_live(state, table, cfg):
                return log                 # yield; the action layer takes over
            state.passes = 0

        bf, attacker = state.showdown_bf, int(state.attacker)
        # Steps 2-3, repeating while the result is "No Result" (466.3.d.1).
        log.setdefault("rounds", []).append(damage_step(state, table, cfg, bf))
        resolution_step(state, table, cfg, bf, attacker, log)
    return log


def is_alone(state: GameState, perm: int) -> bool:
    """740.2.a -- "A unit is alone when there are no other friendly units at the
    same location."

    The rules define it once and three different clauses use it: Lonely Poro's
    "died alone", Mask of Foresight's "attacks or defends alone", Wielder of
    Water's "while I'm attacking or defending alone". It is a LOCATION
    predicate, not a count of attackers -- an unattacked friendly unit standing
    beside the attacker is enough to break it.
    """
    row = state.perms[perm]
    seat, loc = int(row[P_CTRL]), int(row[P_LOC])
    return not any(
        i != perm and state.perms[i, P_ALIVE] == 1
        and int(state.perms[i, P_CTRL]) == seat
        and int(state.perms[i, P_LOC]) == loc
        and not state.has_flag(i, F_NON_UNIT)
        for i in range(state.n_perms))


def open_showdown(state: GameState, table: CardTable, bf: int,
                  attacker: int) -> None:
    state.bf_contested[bf] = 1
    state.showdown_bf = bf
    state.showdown_step = SD_PRIORITY
    state.attacker = attacker
    state.priority = attacker              # 464.2.d: the Attacker gains Focus
    state.focus = attacker
    state.passes = 0

    # "When a friendly unit attacks or defends alone" -- 459 designates every
    # unit at the battlefield as an attacker or a defender when the Combat
    # begins, so this is the moment the trigger condition is met. "Alone" is
    # checked HERE rather than at resolution: it is part of the trigger
    # condition, so a unit that is not alone never triggers at all, and one
    # that is keeps the +1 even if a friend walks in during the response
    # window. Same reading as Lonely Poro's "died alone" (359.3.f.3).
    from rl.engine.chain import queue as chain_queue, has_trigger
    loc = bf_loc(bf)
    for u in range(state.n_perms):
        if state.perms[u, P_ALIVE] != 1 or int(state.perms[u, P_LOC]) != loc:
            continue
        if state.has_flag(u, F_NON_UNIT) or not is_alone(state, u):
            continue
        owner = int(state.perms[u, P_CTRL])
        # The watcher is any permanent its controller has anywhere -- Mask of
        # Foresight sits at a base and watches a battlefield.
        for w in range(state.n_perms):
            if state.perms[w, P_ALIVE] != 1 or int(state.perms[w, P_CTRL]) != owner:
                continue
            if has_trigger(table, int(state.perms[w, P_CARD]),
                           TR_ATTACK_OR_DEFEND):
                chain_queue(state, TR_ATTACK_OR_DEFEND, w, loc, subj=u)


def showdown_responses(state: GameState, table: CardTable, cfg: Config,
                       seat: int) -> list:
    """Hand indices this seat could play into the current window.

    Delegates to the Chain, because a Showdown window is not a separate
    mechanism -- 342.1: a spell played in a Showdown creates a Chain as normal.
    Imported here rather than at module scope only to keep the dependency one
    way: `chain` reaches into `resolve`, which must not reach back into combat.
    """
    from rl.engine import chain
    return chain.playable_hand_indices(state, table, cfg, seat)


def showdown_pass(state: GameState) -> bool:
    """Pass priority. Returns True once both players have passed in succession."""
    state.passes += 1
    state.priority = 1 - state.priority
    return state.passes >= N_SEATS


# --- Step 2: the Combat Damage Step (465) ----------------------------------

def _tiers(state: GameState, table: CardTable, idxs) -> list[list[int]]:
    """Split targets into assignment-priority tiers (465.2.c.6).

    `[Tank]` first, unconstrained second, `[Backline]` last. A unit with both
    (465.2.c.8) is exclusionary -- the assigning player picks which requirement
    to satisfy -- and we take Tank, the stricter one, which is also the choice
    that keeps the enumeration deterministic.
    """
    tank, plain, back = [], [], []
    for i in idxs:
        card = int(state.perms[i, P_CARD])
        if perm_kw(state, table, i, "Tank"):
            tank.append(i)
        elif perm_kw(state, table, i, "Backline"):
            back.append(i)
        else:
            plain.append(i)
    return [tank, plain, back]


def _best_subset(costs: list[int], budget: int) -> tuple[int, list[int]]:
    """Largest-Might subset of one tier affordable within `budget`.

    Value equals weight, so this is subset-sum, not a general knapsack. Tiers
    hold a handful of units, so exhaustive search over bitmasks is both exact
    and faster than a DP table.
    """
    n = len(costs)
    best_val, best_cnt, best_mask = 0, 0, 0
    for mask in range(1 << n):
        total = cnt = 0
        for j in range(n):
            if (mask >> j) & 1:
                total += costs[j]
                cnt += 1
        if total > budget:
            continue
        # More Might destroyed wins; ties go to more bodies -- each surviving
        # body can garrison, so unit count is the right tiebreak.
        if (total, cnt) > (best_val, best_cnt):
            best_val, best_cnt, best_mask = total, cnt, mask
    return best_val, [j for j in range(n) if (best_mask >> j) & 1]


def solve_kills(state: GameState, table: CardTable, pool: int,
                targets: list[int]) -> list[int]:
    """Choose which enemy units to destroy with `pool` damage.

    Damage that does not kill heals away at cleanup, so the only rational spends
    are exact-lethal ones and the whole decision is *which subset dies*. The
    ordering keywords make it an ordered subset: you may only reach into tier k
    once every unit in tiers below k is dead (815.1.c.2, 826.4.b).

    Damage is dealt simultaneously and dying units still deal full Might, so the
    two sides' allocations never interact and solving them independently is
    exact.

    **The choice only exists when you are losing.** If the pool covers every
    target, "kill everything" is optimal and there is nothing to decide; the
    ranking below is a stand-in that matters only in the partial case, which is
    exactly the case a policy should eventually own. `assignment_is_a_choice`
    detects it -- gate any future action-space exposure on that, not on being in
    combat, or you will flood the action space with forced decisions.
    """
    tiers = _tiers(state, table, targets)
    best_val, best_kills = -1, []
    spent_lower = 0
    for k, tier in enumerate(tiers):
        if spent_lower > pool:
            break
        costs = [lethal_cost(state, table, i) for i in tier]
        val, picks = _best_subset(costs, pool - spent_lower)
        lower = [i for t in tiers[:k] for i in t]
        total = val + spent_lower
        if total > best_val:
            best_val = total
            best_kills = lower + [tier[j] for j in picks]
        spent_lower += sum(costs)
    return best_kills


def assignment_is_a_choice(state: GameState, table: CardTable, pool: int,
                           targets: list[int]) -> bool:
    """Does the assigning player actually have a decision here?

    No, if the pool covers every target -- wiping the board is strictly best and
    the assignment is forced. Yes, only when the pool falls short and a subset
    must be picked. Confirmed by the project owner: "if your might is greater
    than [the] enemies', you can wipe all their units and [there is] no need to
    think about damage calculations. Only when losing does it really matter to
    decide who to kill."

    Gate on this before ever putting damage assignment in the action space.
    """
    return sum(lethal_cost(state, table, i) for i in targets) > pool


def _assign(state: GameState, table: CardTable, pool: int,
            targets: list[int]) -> list[int]:
    """Assign `pool` damage and return the rows that took lethal.

    Marks the damage as well as picking the kills, because a Reaction that heals
    or buffs mid-assignment will need the real numbers later. The leftover goes
    onto the next legal target (465.2.c.4): it changes nothing, since the
    Resolution Step heals it away, but assigning it keeps the model honest.
    """
    kills = solve_kills(state, table, pool, targets)
    left = pool
    for i in kills:
        c = lethal_cost(state, table, i)
        state.perms[i, P_DMG] += c
        left -= c
    if left > 0:
        for tier in _tiers(state, table, targets):
            spare = [i for i in tier if i not in kills]
            if spare:
                state.perms[spare[0], P_DMG] += left
                break
    return kills


def damage_step(state: GameState, table: CardTable, cfg: Config,
                bf: int) -> dict:
    """Both sides sum Might, assign, and deal simultaneously (465).

    Simultaneity is the whole point: there is no priority window in which to
    kill an attacker and save a defender, so a unit that dies still deals its
    full Might. That makes the two allocations separable.
    """
    state.showdown_step = SD_DAMAGE
    loc = bf_loc(bf)
    units = [list(state.units_at(loc, s)) for s in range(N_SEATS)]

    # 465.1: no damage unless both sides still have units here.
    if not units[0] or not units[1]:
        return {"pools": (0, 0), "killed": ([], [])}

    pools = [sum(might_for_pool(state, table, i) for i in units[s])
             for s in range(N_SEATS)]
    # Assign against the pre-damage board for both seats, then deal at once.
    killed = [_assign(state, table, pools[s], units[1 - s]) for s in range(N_SEATS)]
    for side in killed:
        for i in side:
            _destroy(state, table, i)
    return {"pools": tuple(pools), "killed": tuple(killed)}


# --- Step 3: the Resolution Step (466) -------------------------------------

def resolution_step(state: GameState, table: CardTable, cfg: Config,
                    bf: int, attacker: int, log: dict) -> bool:
    """Combat Cleanup, result, Control. Returns True when the Combat ends."""
    state.showdown_step = SD_CLEANUP
    loc = bf_loc(bf)

    # 466.1.a.1 -- heal ALL units, board-wide, not just the combatants. This is
    # why chip damage is worth exactly zero.
    if state.n_perms:
        state.perms[:state.n_perms, P_DMG] = 0

    # 466.1.a.2 -- Recall Attackers if any Defender is still present. Surviving
    # an attack you did not win sends every attacker home; you cannot take a
    # Battlefield by standing next to its garrison.
    defender = 1 - attacker
    recalled: list[int] = []
    if state.has_units_at(loc, defender):
        for i in state.units_at(loc, attacker):
            state.perms[i, P_LOC] = base_loc(attacker)
            recalled.append(int(i))
    log["recalled"] = recalled

    # 466.3 -- combat result. "No Result" restages only if both players still
    # have units here, which the Recall above rules out in practice.
    a, b = state.seats_at(loc)
    if recalled or (a and b) or not (a or b):
        log["result"] = "none"
        restage = a and b
    else:
        log["result"] = "won"
        restage = False

    if restage:
        state.showdown_step = SD_PRIORITY
        state.passes = 0
        return False

    # 466.5 -- Combat is over, so Control settles and a change of hands Conquers.
    state.showdown_bf = -1
    state.showdown_step = SD_NONE
    state.attacker = -1
    state.priority = state.active
    state.focus = -1
    log.setdefault("scored", []).extend(
        _establish_control(state, table, cfg, bf))
    for i in range(N_BF):
        if i != bf:
            log["scored"].extend(_establish_control(state, table, cfg, i))
    return True
