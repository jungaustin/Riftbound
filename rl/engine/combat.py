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
from rl.engine.state import (P_MIGHT_MOD, F_NO_COMBAT_DAMAGE, N_BF, N_SEATS, P_ALIVE,
                             P_ARRIVED, P_CARD, P_CTRL, P_DMG, P_FLAGS, P_LOC,
                             P_READY, SD_CLEANUP, SD_DAMAGE, SD_NONE,
                             SD_PRIORITY, GameState, base_loc, bf_loc, bf_index,
                             is_battlefield)

POINTS_PER_CONQUER = 1


# ---------------------------------------------------------------------------
# Unit characteristics
# ---------------------------------------------------------------------------

def might(state: GameState, table: CardTable, perm: int) -> int:
    """Current Might: printed value plus any "this turn" modifier, floored at 0.

    143.2.b -- "If a unit's Might is ever less than 0, it is treated as 0 when
    referenced by spells and abilities, and when summing Might to be assigned as
    damage." So a -4 on a 2-Might unit contributes 0, never -2.

    Never read `table.might` directly at a call site, or modifiers will silently
    fail to apply (PLAN.md §1.3.d).
    """
    row = state.perms[perm]
    return max(0, int(table.might[int(row[P_CARD])]) + int(row[P_MIGHT_MOD]))


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
    base = int(table.might[int(row[P_CARD])])
    new = int(row[P_MIGHT_MOD]) + delta
    if floor is not None:
        new = max(new, floor - base)      # never take effective Might below floor
    row[P_MIGHT_MOD] = new

    dmg = int(row[P_DMG])
    if dmg > 0 and dmg >= might(state, table, perm):
        _destroy(state, perm)
        return True
    return False


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


def _destroy(state: GameState, perm: int) -> None:
    """Kill a permanent and put its card in its controller's trash."""
    row = state.perms[perm]
    row[P_ALIVE] = 0
    seat, card = int(row[P_CTRL]), int(row[P_CARD])
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
                or table.has(int(row[P_CARD]), "Ganking"))
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
        state.points[holder] += POINTS_PER_CONQUER
        state.winner = state.check_winner(cfg.victory_score)
        scored.append((holder, "conquer"))
    return scored


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
    open_showdown(state, bf, attacker)
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
            if window_is_live(state, table, cfg):
                return log                 # yield; the action layer takes over
            state.passes = 0

        bf, attacker = state.showdown_bf, int(state.attacker)
        # Steps 2-3, repeating while the result is "No Result" (466.3.d.1).
        log.setdefault("rounds", []).append(damage_step(state, table, cfg, bf))
        resolution_step(state, table, cfg, bf, attacker, log)
    return log


def open_showdown(state: GameState, bf: int, attacker: int) -> None:
    state.bf_contested[bf] = 1
    state.showdown_bf = bf
    state.showdown_step = SD_PRIORITY
    state.attacker = attacker
    state.priority = attacker              # 464.2.d: the Attacker gains Focus
    state.focus = attacker
    state.passes = 0


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
        if table.has(card, "Tank"):
            tank.append(i)
        elif table.has(card, "Backline"):
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
            _destroy(state, i)
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
