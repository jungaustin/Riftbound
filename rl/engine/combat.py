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
                               COND_DEFENDING_ALONE,
                               COND_EMPOWERED, COND_LEGION, COND_LEVEL,
                               COND_NONE,
                               BF_STATICS, SC_UNITS_HERE, W_FRIENDLY,
                               SC_SELF, ST_DAMAGE_BONUS, ST_KEYWORD, ST_MIGHT,
                               ST_NO_PLAY, ST_UNCHOOSABLE,
                               TR_ATTACK_OR_DEFEND, TR_OTHER_DIES,
                               TR_OPPONENT_SCORES,
                               TR_DEATH, TR_MOVE, abilities_for,
                               statics_for)
from rl.engine.state import (GRANT_IDX, P_MIGHT_MOD, F_BUFFED,
                             F_DIED_ALONE,
                             BEGINNING,
                             F_EMPOWERED, F_NON_UNIT, F_NO_COMBAT_DAMAGE,
                             F_NO_MOVE,
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
    total = 0
    for i in range(state.n_perms):
        src = state.perms[i]
        if src[P_ALIVE] != 1:
            continue
        for st in statics_for(table, int(src[P_CARD])):
            if st.kind != ST_MIGHT:
                continue
            # Shared with `static_keyword` rather than re-derived. This block
            # used to be a second copy that silently ignored `scope_not_self`
            # and `scope_same_loc`, so a Might static narrowed to "other units
            # HERE" would have applied board-wide. No card in the pool used
            # that combination, which is exactly why it would have gone
            # unnoticed until one did.
            if not static_reaches(state, table, st, i, perm):
                continue
            total += st.n * static_count(state, table, st, int(src[P_CTRL]),
                                         int(src[P_LOC]), int(src[P_CARD]))
    for st in bf_statics_for(state, table, perm):
        if st.kind == ST_MIGHT:
            total += st.n
    return total


def static_applies(state: GameState, st, src_seat: int,
                   src_perm: int = -1) -> bool:
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
    if st.cond == COND_EMPOWERED:
        # 828.1.c -- the dependent ability is active exactly while the SOURCE
        # holds the Empowered status, so this asks about a permanent and not a
        # player. `src_perm < 0` means the source is not on the board at all --
        # `cost.energy_discounts` asks about a card still in hand, which has no
        # status to hold, so the gate is correctly closed there.
        return src_perm >= 0 and state.has_flag(src_perm, F_EMPOWERED)
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


def perm_kw(state: GameState, table: CardTable, perm: int, keyword: str,
            include_bf: bool = True) -> int:
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
    granted = static_keyword(state, table, perm, keyword, include_bf)
    idx = GRANT_IDX.get(keyword)
    if idx is None:
        return printed + granted    # nothing can grant it with an EFFECT
    return (printed + granted + int(state.kw_grant[perm, idx])
            + int(state.kw_grant_turn[perm, idx]))


def static_keyword(state: GameState, table: CardTable, perm: int,
                   keyword: str, include_bf: bool = True) -> int:
    """Value of `keyword` granted to `perm` by statics on the board right now.

    Derived on every read, exactly like `static_might` and for the same reason:
    a static is continuous, so "your token units have [Tank]" starts applying
    the instant Lillia arrives and stops the instant she dies, with nothing on
    the Chain and no moment at which a cache could be refreshed.
    """
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
        return 0
    total = 0
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in statics_for(table, int(state.perms[i, P_CARD])):
            if st.kind != ST_KEYWORD or st.keyword != keyword:
                continue
            if static_reaches(state, table, st, i, perm):
                total += max(1, st.n)
    if include_bf:
        for st in bf_statics_for(state, table, perm):
            if st.kind == ST_KEYWORD and st.keyword == keyword:
                total += max(1, st.n)
    return total


def bf_statics_for(state: GameState, table: CardTable, perm: int):
    """(static, applies) for every static printed on the battlefield `perm` is
    standing on.

    A battlefield is not a permanent -- it has no row, no controller and cannot
    die -- so it needs its own source loop rather than a row in the permanent
    scan. What it CAN do is reach the units standing on it, which is the only
    scope `SC_UNITS_HERE` has.
    """
    loc = int(state.perms[perm, P_LOC])
    if not is_battlefield(loc):
        return
    card = int(state.bf_card[bf_index(loc)])
    if card < 0:
        return
    row = state.perms[perm]
    unit_card = int(row[P_CARD])
    for st in BF_STATICS.get(table.names[card], ()):
        if st.scope != SC_UNITS_HERE:
            continue
        if not table.is_type(unit_card, "Unit"):
            continue
        # "your units here" would narrow by owner; the unqualified form does
        # not, and every battlefield in the pool prints the unqualified form.
        if st.who == W_FRIENDLY and int(row[P_CTRL]) != int(state.bf_ctrl[
                bf_index(loc)]):
            continue
        # "units here WITH [Temporary]" -- read through `perm_kw`, so a
        # GRANTED [Temporary] qualifies exactly as a printed one does.
        # `include_bf=False` is load-bearing, not an optimisation: this IS
        # the battlefield layer, and asking `perm_kw` the unguarded question
        # re-enters it and recurses until the stack dies. The requirement is
        # therefore read from the printed value, permanent statics and grants
        # -- so a unit GRANTED [Temporary] by Shadow's Call qualifies, while a
        # battlefield cannot satisfy its own requirement.
        if st.requires_keyword and not perm_kw(state, table, perm,
                                               st.requires_keyword,
                                               include_bf=False):
            continue
        # A battlefield's gate is about the AFFECTED unit, not about the
        # source's controller -- a battlefield has neither. So it is checked
        # here rather than through `static_applies`, which answers the other
        # question.
        if st.cond == COND_DEFENDING_ALONE and not defending_alone(
                state, table, perm):
            continue
        yield st


def static_reaches(state: GameState, table: CardTable, st, src_i: int,
                   perm: int) -> bool:
    """Does static `st`, printed on permanent `src_i`, apply to `perm`?

    The scope reading shared by every kind of static, so "your token units
    have [Tank]" and "I can't be chosen" answer the *same* question about who
    a static reaches and differ only in what they then do. Kept in one place
    because a second copy of this block would drift from the first exactly
    once, silently, on whichever card was added last.
    """
    src = state.perms[src_i]
    src_seat = int(src[P_CTRL])
    if not static_applies(state, st, src_seat, src_i):
        return False
    if st.scope == SC_SELF:
        return src_i == perm
    row = state.perms[perm]
    card = int(row[P_CARD])
    if src_seat != int(row[P_CTRL]):
        return False
    if st.scope_token and not table.is_token(card):
        return False
    if st.scope_not_self and src_i == perm:
        return False
    if st.scope_same_loc and int(src[P_LOC]) != int(row[P_LOC]):
        return False
    return bool(table.is_type(card, "Unit"))


def unchoosable_by(state: GameState, table: CardTable, perm: int,
                   seat: int) -> bool:
    """Ruin Runner -- "I can't be chosen by ENEMY spells and abilities".

    A restriction on who may point at the unit, not on what may be done to it:
    its own controller still targets it freely, and nothing here stops combat
    damage or a board-wide sweep, neither of which chooses (355.10).
    """
    if seat == int(state.perms[perm, P_CTRL]):
        return False
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in statics_for(table, int(state.perms[i, P_CARD])):
            if st.kind == ST_UNCHOOSABLE and static_reaches(
                    state, table, st, i, perm):
                return True
    return False


def _printed_kw(table: CardTable, card: int, keyword: str) -> int:
    """The printed value of a keyword on a card: its number, or 1 if bare."""
    if keyword == "Assault":
        return int(table.assault[card])
    if keyword == "Shield":
        return int(table.shield[card])
    if keyword == "Deflect":
        return int(table.deflect[card])
    return 1 if table.has(card, keyword) else 0


def defending_alone(state: GameState, table: CardTable, perm: int) -> bool:
    """Is `perm` a DEFENDER in the running combat, with no friendly company?

    Forbidding Waste. Two live facts at once:

      459     the Attacker/Defender designation, held in `state.attacker` --
              who moved is irrelevant, and the designation outlives the Move.
      740.2.a "alone" is no OTHER unit its controller has at that location.

    Read the same way `combat_role_bonus` reads the role, so [Shield] and this
    can never disagree about who is defending. Live rather than snapshotted: a
    second friendly unit arriving mid-combat turns the penalty off, which is
    what makes the battlefield a reason to commit two units rather than one.
    """
    bf = int(state.showdown_bf)
    if bf < 0:
        return False
    row = state.perms[perm]
    loc = int(row[P_LOC])
    if loc != bf_loc(bf):
        return False
    mine = int(row[P_CTRL])
    if mine == int(state.attacker):
        return False                       # an attacker is never defending
    return not any(i != perm and state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) == mine
                   and int(state.perms[i, P_LOC]) == loc
                   and not (int(state.perms[i, P_FLAGS]) & F_NON_UNIT)
                   for i in range(state.n_perms))


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
    # A permanent that has left the board has no Might to modify. The subject
    # of a trigger can die in the priority window before the ability resolves
    # (T_SUBJECT is a pseudo-slot, so nothing re-checks it the way 359.3.e
    # re-checks a target), and buffing a corpse then reported a "kill" that
    # destroyed it a second time.
    if row[P_ALIVE] != 1:
        return False
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
    """Mark damage and apply 143.2.a. Returns True if it killed the unit.

    **This is the spell-and-ability damage path, and only that.** Combat damage
    is assigned in the damage step, which writes `P_DMG` directly -- so Void
    Gate's "spells and abilities affecting units here each deal 1 Bonus Damage"
    belongs here and nowhere else, and combat damage is correctly untouched.

    "Each INSTANCE of damage is increased by 1" falls out of the call shape:
    one call is one instance, so a spell that deals damage twice is bonused
    twice without the wording having to be arranged for.
    """
    if amount > 0:
        # Bonus Damage rides on a nonzero instance. A 0-damage event is not an
        # instance of damage to increase -- and turning one into 1 would make
        # 143.2.a lethal where the rules say nothing happened at all.
        amount += bf_damage_bonus(state, table, int(state.perms[perm, P_LOC]))
    state.perms[perm, P_DMG] += amount
    dmg = int(state.perms[perm, P_DMG])
    # Imperial Decree lowers the lethal threshold to ANY nonzero damage, for
    # every unit on the board. 143.2.a's "nonzero" still holds -- a 0-damage
    # event kills nothing, which is what keeps Might reduction from becoming
    # removal under the Decree.
    if state.any_damage_kills and dmg > 0:
        _destroy(state, table, perm)
        return True
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
    # **Idempotent, because "kill it" can reach a corpse.** A pseudo-slot like
    # T_SUBJECT is not a target, so 359.3.e never re-checks it, and the unit a
    # trigger fired for can die during the priority window before the ability
    # resolves. Without this guard the second destroy queued a second
    # Deathknell and appended the card to the trash AGAIN -- a card minted from
    # nothing, which the per-seat conservation gate caught at victory 8.
    if row[P_ALIVE] != 1:
        return
    # Shadow Watcher's window: a unit dying during ITS CONTROLLER's Beginning
    # Phase. Recorded here because the question is asked later, when the phase
    # has passed and nothing on the board still says it happened.
    if (state.phase == BEGINNING and not state.has_flag(perm, F_NON_UNIT)
            and int(row[P_CTRL]) == int(state.active)):
        state.died_in_beginning[int(row[P_CTRL])] = 1
    # Zhonya's Hourglass -- "the next time a friendly UNIT would die, kill this
    # instead. Recall that unit exhausted." A replacement, so it runs before
    # anything else here: the unit never dies, so no Deathknell fires for it
    # and nothing reaches its trash.
    #
    # The guard is cleared FIRST and the guarding permanent is killed by the
    # same `_destroy` this sits in -- which is why clearing comes first. The
    # gear is not a unit, so it cannot guard its own death, and a second pass
    # finds no guard to consume. Without that order this recurses forever.
    ctrl_now = int(row[P_CTRL])
    guard = int(state.death_guard[ctrl_now])
    if (guard >= 0 and guard != perm
            and state.perms[guard, P_ALIVE] == 1
            and not state.has_flag(perm, F_NON_UNIT)):
        state.death_guard[ctrl_now] = -1
        _destroy(state, table, guard)
        # 455 -- a Recall relocates to the base and is NOT a Move (456.1), so
        # no move trigger fires. Exhausted, and deliberately NOT healed.
        row[P_LOC] = base_loc(ctrl_now)
        row[P_READY] = 0
        return
    # "When ANOTHER friendly unit dies" -- a watcher trigger, so it fires for
    # everyone else the controller has, and never for the unit that died.
    # Queued before the death is carried out, the same instant a [Deathknell]
    # is (808.1.d.2), so both see the same board.
    if not state.has_flag(perm, F_NON_UNIT):
        from rl.engine.chain import fire_watchers
        fire_watchers(state, table, int(row[P_CTRL]), TR_OTHER_DIES,
                      subj=perm, exclude=perm)

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
    # Vex - Apathetic: "They can't move it this turn." Checked here rather than
    # in the destination logic, so it blocks every ordinary Move including the
    # retreat home, which is what makes the stun stick.
    if state.has_flag(perm, F_NO_MOVE):
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
                       from_loc: int, to_loc: int = -1) -> None:
    """A Move trigger captures BOTH ends of the move (359.3.f.3).

    `ctx` is the location LEFT and `ctx2` the location ARRIVED AT, because
    printed text distinguishes them by word and needs whichever it names to
    outlive the unit. Lillia's "play a Sprite THERE" is the origin;
    Irresistible Faefolk's "move an enemy unit to THAT battlefield" is the
    destination. Both are captured at the moment of the move rather than read
    at resolution -- by then the unit may have moved again, or been Gusted off
    the board entirely by a response to this very trigger.

    `to_loc` defaults to the unit's current row because every caller moves the
    unit BEFORE queueing except `commit_declaration`, which queues first so
    that `from_loc` is still readable.
    """
    from rl.engine.chain import queue as chain_queue   # cycle: chain -> resolve -> combat
    card = int(state.perms[perm, P_CARD])
    if to_loc < 0:
        to_loc = int(state.perms[perm, P_LOC])
    if any(a.trigger == TR_MOVE for a in abilities_for(table, card)):
        chain_queue(state, TR_MOVE, int(perm), int(from_loc),
                    ctx2=int(to_loc))


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
        queue_move_trigger(state, table, i, int(row[P_LOC]), dst)
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
    queue_move_trigger(state, table, perm, int(row[P_LOC]),
                       base_loc(int(row[P_CTRL])))
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


def settle_contested(state: GameState, i: int) -> None:
    """323.11 / 190.3 -- who, if anyone, currently has this Battlefield
    Contested.

    Contested is not "somebody is fighting here". 190.3.a.1 applies it when a
    unit *becomes present at a battlefield its controller does not control*,
    and it names the player who did so -- which is the whole reason it is
    tracked rather than inferred: 464.2.c.1 designates that player the
    Attacker, and no amount of looking at the board afterwards recovers who
    arrived first.

    Two clauses, in the order 323 runs them:

      323.11   Contested is removed from a battlefield where the player who
               applied it has no units left and nothing is ongoing. Gust the
               lone attacker away and the ground stops being contested.
      323.11.a If that removal leaves units belonging to somebody who does not
               control the battlefield, THEIR controller applies Contested --
               so the status hands off to whoever is still standing there.

    That hand-off is exactly the Irresistible Faefolk line: she contests an
    empty battlefield, is Gusted off it in response to her own move trigger,
    and the enemy unit her trigger drags in inherits the Contested status and
    with it the Attacker designation -- on the opponent's turn.

    190.3.b freezes all of this while a Showdown or Combat is ongoing there:
    the status persists until Control is established, whatever happens to the
    units in the meantime.
    """
    if state.showdown_bf == i:
        return
    loc = bf_loc(i)
    who = int(state.bf_contester[i])
    if who >= 0 and not state.has_units_at(loc, who):
        who = -1
    if who < 0:
        # Turn order (383.3.d.1's tie-break) decides if both players somehow
        # qualify at once. That needs a battlefield the previous contester
        # abandoned while both sides still had units on it, which no single
        # move produces -- it takes an effect that removes one unit and adds
        # another. Stated rather than assumed, because the alternative is an
        # arbitrary row order deciding who attacks.
        for seat in (int(state.active), 1 - int(state.active)):
            if state.has_units_at(loc, seat) and int(state.bf_ctrl[i]) != seat:
                who = seat
                break
    state.bf_contester[i] = who
    state.bf_contested[i] = int(who >= 0)


def staged_showdown(state: GameState) -> tuple[int, bool]:
    """The next Showdown to open: `(battlefield, is_combat)`, or `(-1, False)`.

    323.9 stages a Combat at a Contested battlefield holding units of opposing
    players; 323.12 opens a plain Showdown only at Contested battlefields
    *without* a Combat staged. So Combats are answered first, and a battlefield
    one player walked onto alone still opens a Showdown -- it is that Showdown
    closing that Conquers it (348.2.a), not the Move.
    """
    for i in range(N_BF):
        if int(state.bf_contester[i]) < 0:
            continue
        a, b = state.seats_at(bf_loc(i))
        if a and b:
            return i, True
    for i in range(N_BF):
        if int(state.bf_contester[i]) >= 0:
            return i, False
    return -1, False


def cleanup(state: GameState, table: CardTable, cfg: Config,
            mover: int = -1, dst: int = -1) -> dict:
    """Perform a Cleanup, opening whatever Showdown it stages (318, 344, 460).

    `mover`/`dst` are retained for callers and logging only. **They no longer
    decide the Attacker**: 464.2.c.1 names the player who applied Contested,
    which `settle_contested` tracks, and "whoever moved last" is a different
    player whenever the last arrival is a reinforcement.
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

    # **A Combat already in progress is resumed, never re-initiated.**
    # `staged_combat` reads PRESENCE (461): units from both players at a
    # battlefield. That stays true for the whole Combat, so it is only a
    # question worth asking when no Combat is running. A Showdown that yields
    # for a response window empties the Chain, and the Cleanup that follows
    # would find the same two units still standing there and open the Showdown
    # a second time -- re-queueing every attack/defend trigger with it.
    #
    # Mask of Foresight made that visible: it re-triggered once per priority
    # pass and stacked +1 Might per decision, reaching +1270 on a single unit
    # while the turn counter never moved. The Combat cannot end, because the
    # only thing that advances it is the pass that keeps restarting it.
    # `advance_combat` is what resumes this one; see the A_PASS branch in
    # `actions._apply_one`.
    #
    # The one thing that DOES change an ongoing Showdown is a unit arriving to
    # face the player who opened it -- 344.1 turns a Non-Combat Showdown into a
    # Combat Showdown in place, rather than opening a second one.
    if state.showdown_bf >= 0:
        if escalate_to_combat(state, table, int(state.showdown_bf)):
            log["escalated"] = int(state.showdown_bf)
        return log

    # **A queued trigger is a Pending Chain Item, and that closes the State.**
    # 323.6, 323.12 and 323.13 are all conditioned on "if the turn is in an
    # Open State" (323.12 on a Neutral Open one), and 309.2 makes the State
    # Open only while no Chain exists. A trigger waiting in `state.trig` is one
    # that 320.1 will add to the Chain during this very Cleanup, so none of
    # those tasks happen yet -- 344.2 says the Showdown "is opened during the
    # next Cleanup" instead, once the Chain has emptied again.
    #
    # This is the whole timing of the Irresistible Faefolk line. She moves onto
    # empty ground; if the Showdown opened now, it would be HER Showdown, with
    # her controller Contesting and holding Focus, and the enemy unit her
    # trigger drags in would be joining a Showdown somebody else opened. It
    # does not: her move trigger closes the State, the Chain plays out (she
    # gets Gusted, the trigger still resolves), and the Showdown that finally
    # opens belongs to the unit left standing there -- the enemy's. That is
    # what makes the opponent the Attacker on your own turn.
    if state.n_trig:
        return log

    # 323.6 / 190.4.c -- a player with no Units at a Battlefield they control
    # loses it. This half of Control settlement still belongs in every Cleanup;
    # the other half, *establishing* Control, does not -- 190.4 only grants it
    # "at the end of a Showdown or Combat", so it moved to the close of one.
    for i in range(N_BF):
        _release_control(state, i)

    # 323.11, and it runs AFTER the release above so that 323.11.a sees the
    # battlefields that just went uncontrolled. It decides both which Showdowns
    # are staged (323.8/323.9) and who the Attacker will be (464.2.c.1), so it
    # has to be current at every battlefield before either is read.
    for i in range(N_BF):
        settle_contested(state, i)

    # A Cleanup resolves EVERY staged Showdown, not just the first. v0 could
    # only ever stage one at a time -- a single Move declaration has one
    # destination -- so a loop was unnecessary and its absence invisible. A
    # spell that moves a unit can stage a second one at another battlefield,
    # and stopping after the first left that one staged but never opened.
    for _ in range(N_BF + 1):
        bf, is_combat = staged_showdown(state)
        if bf < 0:
            break
        log.update(run_showdown(state, table, cfg, bf,
                                int(state.bf_contester[bf]), is_combat))
        if state.showdown_bf >= 0:
            return log       # yielded for a response; resume later
    else:
        raise AssertionError("more staged showdowns than battlefields")
    return log


def _release_control(state: GameState, i: int) -> None:
    """323.6 / 190.4.c -- lose a Battlefield you have no Units at.

    Runs in every Cleanup, unlike establishing Control. The asymmetry is in the
    rules: 190.4.a maintains Control "for as long as they have Units at that
    Battlefield" and 190.4.c takes it away in the following Cleanup once they
    do not, while 190.4 grants it only "at the end of a Showdown or Combat".
    Empty ground goes neutral immediately; taking ground takes a Showdown.
    """
    if state.showdown_bf == i:
        return                             # 190.4.b: frozen while one is ongoing
    prev = int(state.bf_ctrl[i])
    if prev >= 0 and not state.has_units_at(bf_loc(i), prev):
        state.bf_ctrl[i] = -1
        _clear_foreign_hidden(state, i, -1)


def _establish_control(state: GameState, table: CardTable, cfg: Config,
                       i: int) -> list[tuple[int, str]]:
    """Settle Control of one Battlefield and Conquer if it changed hands.

    Rule 466.5: the player with Units remaining Establishes Control if they did
    not already have it; 466.5.b: no Units at all means Uncontrolled; 466.5.d:
    establishing Control is a Conquer, subject to the once-per-turn cap (470).
    348.2.a says the same for a Non-Combat Showdown, and 348.2.a.1 that it too
    is a Conquer -- which is why this is called from the close of both.

    **Only ever called when a Showdown or Combat ENDS.** It used to run in
    every Cleanup, which made a Move onto empty ground score instantly and with
    no window: the point was banked before the opponent could answer, and the
    Showdown 344.2 opens for exactly that purpose did not exist.
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
        state.bf_contester[i] = -1
        return scored

    # 190.3.b -- Contested lasts "until Control is established or
    # re-established", which is here and nowhere else.
    state.bf_contested[i] = 0
    state.bf_contester[i] = -1
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
        from rl.engine.chain import fire_watchers as _fire_watchers
        _fire_watchers(state, table, 1 - holder, TR_OPPONENT_SCORES)
        # "When I conquer" fires for the units that took the ground.
        from rl.engine.chain import has_trigger, queue as chain_queue
        from rl.engine.effects import TR_CONQUER
        for u in state.units_at(loc, holder):
            if has_trigger(table, int(state.perms[u, P_CARD]), TR_CONQUER):
                chain_queue(state, TR_CONQUER, int(u), loc)
        # ...and for the BATTLEFIELD itself. "When you conquer here" is printed
        # on the ground, not on a unit, so it fires whether or not anything
        # standing there cares -- and it fires exactly once, where the unit
        # version fires once per unit.
        _queue_bf_trigger(state, table, TR_CONQUER, i, holder)
    return scored


def _queue_bf_trigger(state: GameState, table: CardTable, trigger: int,
                      i: int, seat: int) -> None:
    """Queue battlefield slot `i`'s abilities on `trigger`, for `seat`.

    The seat has to be passed: a battlefield has no controller of its own, and
    the one that matters is whoever the trigger fired FOR -- the conqueror, the
    holder, the player taking the turn.
    """
    from rl.engine.chain import queue as chain_queue
    from rl.engine.effects import bf_abilities_for
    from rl.engine.state import bf_src
    card = int(state.bf_card[i])
    if card < 0:
        return
    if any(a.trigger == trigger for a in bf_abilities_for(table, card)):
        chain_queue(state, trigger, bf_src(i), bf_loc(i), who=seat)


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

def run_showdown(state: GameState, table: CardTable, cfg: Config,
                 bf: int, attacker: int, is_combat: bool) -> dict:
    """Open a Showdown at `bf` and run it as far as the rules allow unattended.

    A Showdown is a *resumable* state machine, not a function that plays itself
    out. It runs forward until either it closes or a player has a real decision
    to make, and in the second case it returns with `state.showdown_bf >= 0` so
    the action layer can ask them. `advance_combat` picks it back up.

    That structure exists for one reason: the Showdown Step is where
    `[Reaction]` cards and every live `[Hidden]` card are played, and that window
    is the entire interactive layer of the game (PLAN.md §5.3 gotcha 3). A
    version that resolves Combat in one call cannot represent a combat trick.

    **Both kinds of Showdown come through here.** 344.1 opens one as the first
    step of Combat when both players have units at the Contested battlefield;
    344.2 opens a Non-Combat Showdown when only one does. The second is not a
    formality -- it is the window in which a lone attacker gets Gusted off the
    ground it just walked onto, and the one in which an [Ambush] unit arrives
    to answer it. 348.2 then closes it by establishing Control, so the Conquer
    happens at the *end* of that window rather than on arrival.
    """
    log: dict = {"combat_at" if is_combat else "showdown_at": bf}
    open_showdown(state, table, bf, attacker, is_combat)
    return advance_combat(state, table, cfg, log)


def run_combat(state: GameState, table: CardTable, cfg: Config,
               bf: int, attacker: int) -> dict:
    """Initiate a Combat Showdown at `bf`. Kept for callers and tests."""
    return run_showdown(state, table, cfg, bf, attacker, True)


def escalate_to_combat(state: GameState, table: CardTable, bf: int) -> bool:
    """344.1 -- an ongoing Non-Combat Showdown becomes a Combat Showdown.

    "If a Showdown is already ongoing at that Battlefield, it will become a
    Combat Showdown and a Combat will initiate there." The Attacker does NOT
    change: 464.2.c.1 reads the Contested status, which 190.3.b has held frozen
    since the Showdown opened, so the player who walked in alone stays the
    Attacker and the unit that just arrived to face them is a Defender.

    That is the whole point of the window. Playing an [Ambush] unit into the
    battlefield an enemy just took makes you the Defender, with [Shield] rather
    than [Assault] and with the 466.1.a.2 Recall working for you instead of
    against you -- and the engine used to hand the Attacker designation to
    whoever moved most recently, which is the opposite answer.
    """
    if state.showdown_bf != bf or state.showdown_combat:
        return False
    a, b = state.seats_at(bf_loc(bf))
    if not (a and b):
        return False
    state.showdown_combat = 1
    # 464.2.a's tasks, in order: designate, then the Attacker gains Focus.
    _designate(state, table, bf, int(state.attacker))
    state.showdown_step = SD_PRIORITY
    state.priority = int(state.attacker)      # 464.2.d
    state.focus = int(state.attacker)
    state.passes = 0
    return True


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

            if not state.showdown_combat:
                # 348 -- every player passed without acting, so the Showdown
                # closes. 348.2 rather than 348.1: there is no damage step,
                # only Control, and 348.2.a.1 makes that a Conquer.
                close_noncombat_showdown(state, table, cfg, log)
                return log

        bf, attacker = state.showdown_bf, int(state.attacker)
        # Steps 2-3, repeating while the result is "No Result" (466.3.d.1).
        log.setdefault("rounds", []).append(damage_step(state, table, cfg, bf))
        resolution_step(state, table, cfg, bf, attacker, log)
    return log


def close_noncombat_showdown(state: GameState, table: CardTable, cfg: Config,
                             log: dict) -> None:
    """348.2 -- close a Non-Combat Showdown and settle Control.

    "If only one player's Units remain at the Battlefield, and if that player
    does not already Control the Battlefield, that player establishes Control
    over the Battlefield", and 348.2.a.1 makes that a Conquer. `_establish_
    control` already says all of that for the Combat case and says it the same
    way here -- the two endings differ in what precedes them, not in what
    Control means.

    The "if only one player's Units remain" guard is `_establish_control`'s own
    `a and b` early return: a unit that arrived during the window without
    escalating this to a Combat cannot exist (`escalate_to_combat` fires on
    exactly that), so in practice the branch is the empty-battlefield one --
    everybody left, and nobody Conquers.
    """
    bf = int(state.showdown_bf)
    state.showdown_bf = -1
    state.showdown_step = SD_NONE
    state.showdown_combat = 0
    state.attacker = -1
    state.priority = int(state.active)
    state.focus = -1
    state.passes = 0
    log.setdefault("scored", []).extend(
        _establish_control(state, table, cfg, bf))


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
                  attacker: int, is_combat: bool = True) -> None:
    """344/345 -- open a Showdown at `bf`. `attacker` is the Contesting seat."""
    state.bf_contested[bf] = 1
    state.showdown_bf = bf
    state.showdown_step = SD_PRIORITY
    state.showdown_combat = int(is_combat)
    state.attacker = attacker
    # 345 for a Non-Combat Showdown, 464.2.d for a Combat one -- the same seat
    # either way, because both name the player who applied Contested.
    state.priority = attacker
    state.focus = attacker
    state.passes = 0
    if is_combat:
        _designate(state, table, bf, attacker)


def _designate(state: GameState, table: CardTable, bf: int,
               attacker: int) -> None:
    """464.2.c.3 -- hand out the Attacker/Defender designations and fire what
    they trigger."""
    # 459 designates every unit at the battlefield as an Attacker or a Defender
    # the moment the Combat begins, so this is when an attack/defend trigger's
    # condition is met -- and every part of that condition is checked HERE
    # rather than at resolution (359.3.f.3). A unit that does not qualify never
    # triggers at all; one that does keeps the effect even if a friend walks in
    # during the response window. Same reading as Lonely Poro's "died alone".
    #
    # Which conditions apply is read off each ABILITY. This loop used to apply
    # `is_alone` to every unit unconditionally, which was Mask of Foresight's
    # own "...alone" clause hardcoded into the shared path: correct for that one
    # card and wrong for every other attack/defend card, none of which had been
    # written yet. Ahri's "when I attack or defend" has no such clause.
    from rl.engine.chain import queue as chain_queue
    from rl.engine.effects import (ROLE_ATTACK, ROLE_DEFEND, ROLE_EITHER,
                                   abilities_for)
    loc = bf_loc(bf)
    for u in range(state.n_perms):
        if state.perms[u, P_ALIVE] != 1 or int(state.perms[u, P_LOC]) != loc:
            continue
        if state.has_flag(u, F_NON_UNIT):
            continue
        owner = int(state.perms[u, P_CTRL])
        alone = is_alone(state, u)
        role = ROLE_ATTACK if owner == attacker else ROLE_DEFEND
        # The watcher is any permanent its controller has anywhere -- Mask of
        # Foresight sits at a base and watches a battlefield.
        for w in range(state.n_perms):
            if state.perms[w, P_ALIVE] != 1 or int(state.perms[w, P_CTRL]) != owner:
                continue
            for ab in abilities_for(table, int(state.perms[w, P_CARD])):
                if ab.trigger != TR_ATTACK_OR_DEFEND:
                    continue
                if not ab.subject_any_friendly and w != u:
                    continue          # "When I attack" -- I am the subject
                if ab.subject_alone and not alone:
                    continue
                if ab.subject_role not in (ROLE_EITHER, role):
                    continue
                chain_queue(state, TR_ATTACK_OR_DEFEND, w, loc, subj=u)
                # One queue per (watcher, subject): the Chain Item names the
                # source, and resolution runs every matching ability on it.
                # Queueing per ability would run a two-ability card twice.
                break

    # ...and the battlefield's own "when you defend here". Fired once PER SEAT
    # that has a role, not once per unit: the ground says "when YOU defend",
    # and a player defending with three units has defended once. That is the
    # same once-for-the-player rule the conquer and hold sites follow, and the
    # reason this loop is over seats rather than nested in the one above.
    for seat in range(N_SEATS):
        if not state.units_at(loc, seat).size:
            continue
        role = ROLE_ATTACK if seat == attacker else ROLE_DEFEND
        _queue_bf_role_trigger(state, table, bf, seat, role)


def _queue_bf_role_trigger(state: GameState, table: CardTable, bf: int,
                           seat: int, role: int) -> None:
    """Queue the battlefield's TR_ATTACK_OR_DEFEND abilities for one seat."""
    from rl.engine.chain import queue as chain_queue
    from rl.engine.effects import (ROLE_EITHER, TR_ATTACK_OR_DEFEND,
                                   bf_abilities_for)
    from rl.engine.state import bf_src
    card = int(state.bf_card[bf])
    if card < 0:
        return
    for ab in bf_abilities_for(table, card):
        if ab.trigger != TR_ATTACK_OR_DEFEND:
            continue
        if ab.subject_role not in (ROLE_EITHER, role):
            continue
        chain_queue(state, TR_ATTACK_OR_DEFEND, bf_src(bf), bf_loc(bf),
                    who=seat)
        break


def showdown_responses(state: GameState, table: CardTable, cfg: Config,
                       seat: int) -> list:
    """Everything this seat could play into the current window.

    Mostly delegation, because a Showdown window is not a separate mechanism --
    342.1: a spell played in a Showdown creates a Chain as normal. Imported
    inside the function rather than at module scope only to keep the dependency
    one way: `chain` reaches into `resolve`, which must not reach back into
    combat, and `actions` imports this module.

    **It must list the same four sources `actions.legal_actions` offers**, not
    just Reaction-speed spells from hand. `window_is_live` is the only thing
    standing between a real decision and a window that is silently auto-passed,
    so anything it cannot see is a play the game will never let you make:

        [Reaction] spells      chain.playable_hand_indices
        [Ambush] units         822.1.b grants Reaction speed while being played
                               to a battlefield you control units at
        [Hidden] cards         811.6 -- facedown cards have [Reaction]
        [Flow] cards           829, played from the trash at Reaction speed

    Only the first was checked. The three that were not are precisely the ones
    that answer a battlefield you have just lost -- and with the Non-Combat
    Showdown of 344.2 now opening on every lone arrival, an [Ambush] unit is
    the *whole* point of that window. Skipping it made the window close before
    anyone could use it, which looks exactly like the window not existing.

    Returns a list only so callers can test it for emptiness; the entries are
    hand indices from four different namespaces and are not interchangeable.
    """
    from rl.engine import actions, chain
    return (chain.playable_hand_indices(state, table, cfg, seat)
            + actions.ambush_playable(state, table, cfg, seat)
            + chain.hidden_playable(state, table, cfg, seat)
            + chain.flow_playable(state, table, cfg, seat))


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
    state.showdown_combat = 0
    state.attacker = -1
    state.priority = state.active
    state.focus = -1
    # Only THIS battlefield. 190.4 grants Control "at the end of a Showdown or
    # Combat", and the one that just ended was here -- a second battlefield
    # somebody happens to be standing alone on has had no Showdown, so it is
    # not theirs yet. It used to be settled here too, which was the same
    # instant-Conquer-without-a-window bug that `cleanup` had, hiding in the
    # Combat path. The Cleanup that follows this one opens its Showdown.
    log.setdefault("scored", []).extend(
        _establish_control(state, table, cfg, bf))
    return True


def bf_damage_bonus(state: GameState, table: CardTable, loc: int) -> int:
    """Bonus Damage added by the battlefield at `loc` (Void Gate).

    Zero at a base and at an unscripted battlefield. Summed rather than maxed:
    two sources of Bonus Damage would each add, which is what "each deal 1
    Bonus Damage" says, though only one card in the pool prints it.
    """
    if not is_battlefield(loc):
        return 0
    card = int(state.bf_card[bf_index(loc)])
    if card < 0:
        return 0
    return sum(st.n for st in BF_STATICS.get(table.names[card], ())
               if st.kind == ST_DAMAGE_BONUS)


def bf_forbids_play(state: GameState, table: CardTable, loc: int) -> bool:
    """Does the battlefield at `loc` forbid playing units there (ST_NO_PLAY)?

    Rockfall Path. Read by `actions.play_destinations` rather than by the board
    scan every other static uses, because the unit this applies to is not on
    the board yet -- there is no row to reach.

    A base is never forbidden: 806.3 always allows a unit to be played to its
    controller's own base, and no card in the pool takes that away.
    """
    if not is_battlefield(loc):
        return False
    card = int(state.bf_card[bf_index(loc)])
    if card < 0:
        return False
    return any(st.kind == ST_NO_PLAY
               for st in BF_STATICS.get(table.names[card], ()))
