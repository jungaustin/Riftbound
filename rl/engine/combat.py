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
from rl.engine.effects import (CNT_BOARD, CNT_EMPOWER, CNT_NONE, SAFE_UNLESS_IN_COMBAT,
                               CNT_TRASH,
                               COND_DEFENDING_ALONE,
                               COND_EMPOWERED, COND_LEGION, COND_LEVEL,
                               COND_EMPOWERED_N, COND_IN_COMBAT,
                               COND_OPP_NEAR_VICTORY, COND_GAINED_XP_THIS_TURN,
                               COND_OPP_CONTROLS_STUNNED, ER_OPP_STUNNED,
                               COND_CONTROL_TAG, COND_CONTROL_EMPOWERED,
                               COND_ENEMY_DIED_THIS_TURN, COND_DISCARDED_THIS_TURN,
                               COND_ATTACKING_WITH_ANOTHER, COND_COMBAT_ALONE,
                               COND_NOT_AT_BF_N_OTHERS, COND_STUNNED_ENEMY_HERE,
                               ER_OPP_CONTROLS_BF, ER_UNIT_DIED_THIS_TURN,
                               ST_NO_COMBAT_DAMAGE, SC_ENEMY_UNITS,
                               ST_NO_ENEMY_MOVE, DEATHKNELL_DOUBLERS,
                               EQUIP_BONUS_DOUBLERS, ER_SAME_NAME_IN_TRASH,
                               ER_OPP_NEAR_VICTORY, ER_SELF_NOT_NEAR_VICTORY,
                               HOLD_CONQUER_SWAP,
                               SMALLER_ALLY_GUARDS, EARLY_SCORE_TO_DRAW,
                               TIE_RECALLS_ALL, MOVED_TWICE_NO_DAMAGE,
                               PLAY_AFTER_TURN, PLAY_ONLY_CONQUERED,
                               BLOCKS_OPP_POINTS, ONE_RUNE_CHANNEL, WARDEN_LOCKS,
                               EFFECT_BONUS_DAMAGE, RUNE_WARD, IGNORE_TANK_HERE,
                               EQUIP_EFFECT_BONUS_DAMAGE, NEVER_READIED,
                               CNT_HOLD_POINTS, COND_NOT_CONQUERED_THIS_TURN,
                               COND_POWER_SPENT_2, COND_SRC_MIGHTY,
                               TR_MARKED_DIES, TR_MARKED_WINS, YOUR_DAMAGE_KILLS,
                               COND_BIG_SPELL_THIS_TURN, COND_BF_EXACTLY_TWO_UNITS,
                               CNT_MIGHTY, CNT_ANIMAL_TAGS, CNT_HIGHEST_MIGHT,
                               COND_NONE,
                               BF_STATICS, SC_UNITS_HERE, W_FRIENDLY,
                               SC_SELF, ST_DAMAGE_BONUS, ST_KEYWORD, ST_MIGHT,
                               ST_NO_DAMAGE, ST_NO_PLAY, ST_PLAY_OPEN,
                               ST_NO_MOVE_TO_BASE, SC_ALL_UNITS, ST_ENTERS_READY,
                               ENTERS_READY_IF, ENTERS_EXHAUSTED, ER_TWO_OTHERS_AT_BASE,
                               ER_DIED_IN_BEGINNING, ER_ALWAYS, ER_ANOTHER_DRAGON,
                               ER_LEVEL_3, ER_HAND_AT_MOST_2, CNT_CARDS_PLAYED,
                               ER_ANOTHER_MECH, CNT_BUFFED_HERE, COND_SRC_AT_BF,
                               ST_UNCHOOSABLE,
                               TR_ATTACK_OR_DEFEND, TR_COMBAT_ENDS,
                               TR_WIN_COMBAT,
                               TR_LEAVES_BOARD,
                               TR_OTHER_DIES,
                               TR_OPPONENT_SCORES,
                               TR_DEATH, TR_MOVE, TR_UNIT_MOVES, TR_YOU_KILL,
                               TR_MARKED_CONQUERS,
                               abilities_for, equip_abilities_for,
                               statics_for, row_statics, row_abilities,
                               row_statics_sourced, EQUIP_DEATH_REPLACEMENT,
                               COND_ATTACHED_THIS_TURN, COND_AT_BF_N_OTHERS,
                               COND_SRC_BUFFED, COND_RUNES_AT_LEAST,
                               COND_ANOTHER_FRIENDLY_HERE, CNT_POINTS)
from rl.engine.state import (F_DAMAGED_TURN, F_UNCHOOSABLE_TURN, F_STUNNED, PT_SPELL, PT_GEAR, PT_UNIT, F_LEGION, F_PAID_ADDITIONAL, P_ATTACH_TURN, P_OWNER, GRANT_IDX, P_EMPOWER, P_MIGHT_MOD, F_BUFFED,
                             F_DIED_ALONE, F_DIED_MIGHTY, F_DIED_IN_COMBAT,
                             BEGINNING,
                             F_EMPOWERED, F_NON_UNIT, F_NO_COMBAT_DAMAGE,
                             F_NO_MOVE,
                             N_BF, N_BF_BASE, N_SEATS, P_ALIVE, fd_slots,
                             P_ARRIVED, P_CARD, P_CTRL, P_DMG, P_FLAGS, P_LOC,
                             P_READY, SD_CLEANUP, SD_DAMAGE, SD_NONE,
                             SD_PRIORITY, GameState, base_loc, bf_loc, bf_index,
                             is_battlefield)

POINTS_PER_CONQUER = 1


# ---------------------------------------------------------------------------
# Unit characteristics
# ---------------------------------------------------------------------------

def static_might(state: GameState, table: CardTable, perm: int) -> int:
    return _static_might_parts(state, table, perm)[0]


def _static_might_parts(state: GameState, table: CardTable,
                        perm: int) -> tuple[int, list]:
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
        return 0, []
    total = 0
    floors = []
    for i in range(state.n_perms):
        src = state.perms[i]
        if src[P_ALIVE] != 1:
            continue
        # `row_statics_sourced`, not `row_statics`: an appended static reads
        # its scope against the UNIT (136.2.c makes "I" the Top-Most card, so
        # `SC_SELF` must reach `i`), while its CONDITION may ask about the gear
        # that appended it. Both rows are needed and they are not the same row.
        for st, printed_on in row_statics_sourced(state, table, i):
            if st.kind != ST_MIGHT:
                continue
            # Shared with `static_keyword` rather than re-derived. This block
            # used to be a second copy that silently ignored `scope_not_self`
            # and `scope_same_loc`, so a Might static narrowed to "other units
            # HERE" would have applied board-wide. No card in the pool used
            # that combination, which is exactly why it would have gone
            # unnoticed until one did.
            if not static_reaches(state, table, st, i, perm,
                                  attached_row=printed_on if printed_on != i
                                  else -1):
                continue
            if st.floor:
                floors.append(st)          # applied last, by `might`
                continue
            total += st.n * static_count(state, table, st, int(src[P_CTRL]),
                                         int(src[P_LOC]), int(src[P_CARD]),
                                         i)
    for seat, st in legend_statics(state, table):
        if st.kind != ST_MIGHT:
            continue
        if not static_reaches(state, table, st, -1, perm, src_seat=seat):
            continue
        if st.floor:
            floors.append(st)
            continue
        total += st.n * static_count(state, table, st, seat, -1,
                                     int(state.legend[seat]), -1)
    for st in bf_statics_for(state, table, perm):
        if st.kind == ST_MIGHT:
            total += st.n
    return total, floors


def static_applies(state: GameState, st, src_seat: int,
                   src_perm: int = -1, attached_row: int = -1,
                   table: CardTable | None = None) -> bool:
    """Is this static's gate satisfied for its controller right now?

    Shared by `static_might` and `cost.energy_discounts`, because a gate that
    only one of them honours is a card that is half on: Master Yi - Unstoppable
    gates a COST on [Level 3] and Targonian Visionary gates MIGHT on [Level 11],
    and both must ask the same question. Read live -- XP never resets, so there
    is no past moment to snapshot the way [Legion] needs.
    """
    if st.cond == COND_NONE:
        return True
    if st.cond == COND_ATTACHED_THIS_TURN:
        # Brutalizer: "If THIS was attached to me this turn, I have an
        # additional +2 Might." The only condition in the file that asks about
        # a row OTHER than the one the static reads as its self.
        #
        # 136.2.c makes every other pronoun in Effect Text mean the Top-Most
        # card, which is why `SC_SELF` still points at the unit -- but "this"
        # is the Equipment naming itself, and only its own `P_ATTACH_TURN` can
        # answer when the link was made. A unit equipped twice in one turn has
        # two gears each answering for itself, which is why the stamp lives on
        # the attached card and not on the unit.
        return (attached_row >= 0
                and int(state.perms[attached_row, P_ATTACH_TURN])
                == int(state.ply))
    if st.cond == COND_SRC_AT_BF:
        # "While I'm at a battlefield" (Eager Apprentice).
        return src_perm >= 0 and is_battlefield(int(state.perms[src_perm, P_LOC]))
    if st.cond == COND_SRC_BUFFED:
        # "While I'm buffed" (Wizened Elder) -- the source's own Buff counter.
        return src_perm >= 0 and state.has_flag(src_perm, F_BUFFED)
    if st.cond == COND_RUNES_AT_LEAST:
        # "While you have N+ runes" (Master Yi - Meditative) -- in play, ready
        # or exhausted.
        return int(state.runes_in_play(src_seat).sum()) >= st.level
    if st.cond == COND_ANOTHER_FRIENDLY_HERE:
        # "While you have another unit here" (Trusty Ramhound) -- at least one
        # other unit its controller has at the source's location.
        if src_perm < 0:
            return False
        loc = int(state.perms[src_perm, P_LOC])
        return any(i != src_perm and state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) == src_seat
                   and int(state.perms[i, P_LOC]) == loc
                   and not state.has_flag(i, F_NON_UNIT)
                   for i in range(state.n_perms))
    if st.cond == COND_AT_BF_N_OTHERS:
        # "I have +2 Might while I'm at a battlefield with EXACTLY ONE other
        # unit you control" (Hand Hammer). Exact, not a floor: a third friendly
        # unit arriving switches it off. Asked of `src_perm`, which for an
        # appended static is the UNIT (136.2.c).
        if src_perm < 0:
            return False
        loc = int(state.perms[src_perm, P_LOC])
        if not is_battlefield(loc):
            return False
        n = sum(1 for i in range(state.n_perms)
                if i != src_perm and state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) == src_seat
                and int(state.perms[i, P_LOC]) == loc
                and not state.has_flag(i, F_NON_UNIT))
        return n == st.level
    if st.cond == COND_LEVEL:
        return int(state.xp[src_seat]) >= st.level
    if st.cond == COND_OPP_CONTROLS_STUNNED:
        return opp_controls_stunned(state, src_seat)
    if st.cond == COND_CONTROL_TAG:
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) == src_seat
                   and table is not None
                   and st.cond_tag in perm_tags(state, table, i)
                   for i in range(state.n_perms))
    if st.cond == COND_CONTROL_EMPOWERED:
        # "if you control something that's [Empowered]" (Shock Blast).
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) == src_seat
                   and int(state.perms[i, P_FLAGS]) & F_EMPOWERED
                   for i in range(state.n_perms))
    if st.cond == COND_ENEMY_DIED_THIS_TURN:
        return any(int(state.unit_died_ply[s]) == int(state.ply)
                   for s in range(N_SEATS) if s != src_seat)
    if st.cond == COND_POWER_SPENT_2:
        # "If you've spent at least {any rune}{any rune} this turn" (Sivir -
        # Mercenary).
        return (int(state.power_spent_ply[src_seat]) == int(state.ply)
                and int(state.power_spent[src_seat]) >= 2)
    if st.cond == COND_SRC_MIGHTY:
        # "While I'm [Mighty]" (Fiora - Victorious). Her Shield feeds her Might
        # while she defends, so asking might() here recurses back into this
        # static; inside that recursion her own grant is treated as absent,
        # which is the only non-circular reading.
        if src_perm < 0 or table is None or src_perm in _MIGHTY_GUARD:
            return False
        _MIGHTY_GUARD.add(src_perm)
        try:
            return might(state, table, src_perm) >= 5
        finally:
            _MIGHTY_GUARD.discard(src_perm)
    if st.cond == COND_BIG_SPELL_THIS_TURN:
        return int(state.big_spell_ply[src_seat]) == int(state.ply)
    if st.cond == COND_BF_EXACTLY_TWO_UNITS:
        # "if you control a battlefield with exactly two units there" (Keeper
        # of Law) -- units of either player.
        return any(int(state.bf_ctrl[b]) == src_seat
                   and int(state.units_at(bf_loc(b)).size) == 2
                   for b in state.live_bfs())
    if st.cond == COND_DISCARDED_THIS_TURN:
        return int(state.discarded_ply[src_seat]) == int(state.ply)
    if st.cond == COND_ATTACKING_WITH_ANOTHER:
        # "while I'm attacking with another unit" (Crimson Pigeons).
        if src_perm < 0 or not in_combat(state, src_perm):
            return False
        loc = int(state.perms[src_perm, P_LOC])
        return (src_seat == int(state.attacker)
                and int(state.units_at(loc, src_seat).size) >= 2)
    if st.cond == COND_COMBAT_ALONE:
        # "while I'm attacking or defending alone" (Wielder of Water).
        return (src_perm >= 0 and in_combat(state, src_perm)
                and is_alone(state, src_perm))
    if st.cond == COND_NOT_AT_BF_N_OTHERS:
        # Sacred Protector: "...UNLESS I'm at a battlefield with exactly one
        # other unit you control" -- the complement of COND_AT_BF_N_OTHERS.
        return not static_applies(state, st._replace(cond=COND_AT_BF_N_OTHERS),
                                  src_seat, src_perm, attached_row, table)
    if st.cond == COND_STUNNED_ENEMY_HERE:
        # "While there's a stunned enemy unit here" (Kennen).
        if src_perm < 0:
            return False
        loc = int(state.perms[src_perm, P_LOC])
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) != src_seat
                   and int(state.perms[i, P_LOC]) == loc
                   and int(state.perms[i, P_FLAGS]) & F_STUNNED
                   for i in range(state.n_perms))
    if st.cond == COND_GAINED_XP_THIS_TURN:
        return int(state.xp_gained_ply[src_seat]) == int(state.ply)
    if st.cond == COND_LEGION:
        return bool(state.cards_played[src_seat])
    if st.cond == COND_EMPOWERED:
        # 828.1.c -- the dependent ability is active exactly while the SOURCE
        # holds the Empowered status, so this asks about a permanent and not a
        # player. `src_perm < 0` means the source is not on the board at all --
        # `cost.energy_discounts` asks about a card still in hand, which has no
        # status to hold, so the gate is correctly closed there.
        return src_perm >= 0 and state.has_flag(src_perm, F_EMPOWERED)
    if st.cond == COND_EMPOWERED_N:
        # "While I'm [Empowered] N times" -- at least N, the same reading
        # COND_LEVEL gives XP.
        return src_perm >= 0 and state.empower_count(src_perm) >= st.level
    if st.cond == COND_IN_COMBAT:
        # "While I'm in combat" -- about the permanent printing the static, so
        # it needs the row and not just the seat. `src_perm < 0` means the
        # source is not on the board (a card still in hand asking about its own
        # discount), and a card in hand is in no combat.
        return src_perm >= 0 and in_combat(state, src_perm)
    if st.cond == COND_OPP_NEAR_VICTORY:
        # "If an opponent's score is within 3 points of the Victory Score"
        # (Find Your Center, Leona - Zealot) -- a catch-up discount, live off
        # the scoreboard. Read against `state.victory_score` and not a literal
        # 8, so the card tracks the annealed curriculum value the same way the
        # win check does.
        #
        # "Within 3" includes exactly 3 away, and an opponent who has already
        # won is moot -- the game is over.
        return any(int(state.points[s]) >= state.victory_score - 3
                   for s in range(N_SEATS) if s != src_seat)
    return False


def static_count(state: GameState, table: CardTable, st, src_seat: int,
                 src_loc: int, src_card: int, src_perm: int = -1) -> int:
    """How many things this static's "for each ..." clause counts. 1 if none.

    Shared by Might statics and cost discounts on purpose: "I have +1 Might for
    each X" and "I cost {1 energy} less for each X" differ only in what they do
    with the number, and letting them count separately is how the two drift
    apart.

    Returning 1 for a static with no counting clause is what makes `n * count`
    the single formula for both the flat and the scaled case.
    """
    if st.per == CNT_POINTS:
        return int(state.points[src_seat])
    if st.per == CNT_CARDS_PLAYED:
        return int(state.cards_played[src_seat])
    if st.per == CNT_HOLD_POINTS:
        return (int(state.hold_points[src_seat])
                if int(state.hold_points_ply[src_seat]) == int(state.ply) else 0)
    if st.per in (CNT_MIGHTY, CNT_ANIMAL_TAGS, CNT_HIGHEST_MIGHT):
        mine = [j for j in range(state.n_perms)
                if state.perms[j, P_ALIVE] == 1
                and int(state.perms[j, P_CTRL]) == src_seat
                and table.is_type(int(state.perms[j, P_CARD]), "Unit")]
        if st.per == CNT_MIGHTY:
            return sum(1 for j in mine if might(state, table, j) >= 5)
        if st.per == CNT_HIGHEST_MIGHT:
            return max((might(state, table, j) for j in mine), default=0)
        tags = set()
        for j in mine:
            tags |= perm_tags(state, table, j) & ANIMAL_TAGS
        return len(tags)
    if st.per == CNT_BUFFED_HERE:
        # "at MY BATTLEFIELD" -- a base is not one, which is the whole reason
        # the card says battlefield rather than location: Sett - Kingpin in his
        # base counts nobody, however many buffed friends stand beside him
        # (RiftJudge #7851).
        if not is_battlefield(src_loc):
            return 0
        return sum(1 for j in range(state.n_perms)
                   if state.perms[j, P_ALIVE] == 1
                   and int(state.perms[j, P_CTRL]) == src_seat
                   and int(state.perms[j, P_LOC]) == src_loc
                   and not state.has_flag(j, F_NON_UNIT)
                   and state.has_flag(j, F_BUFFED))
    if st.per == CNT_EMPOWER:
        # "for each time I'm Empowered" -- the only count that asks about the
        # source's own row. A source not on the board (a card in hand asking
        # about its own discount) has been Empowered zero times.
        return 0 if src_perm < 0 else state.empower_count(src_perm)
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
        if st.per_enemy and int(o[P_CTRL]) == src_seat:
            continue
        if st.per_same_loc and int(o[P_LOC]) != src_loc:
            continue
        card = int(o[P_CARD])
        if st.per_keyword and not table.has(card, st.per_keyword):
            continue
        if st.per_card_type and not table.is_type(card, st.per_card_type):
            continue
        if st.per_not_self and j == src_perm:
            continue
        if st.per_token and not table.is_token(card):
            continue
        if st.per_same_name and card != src_card:
            continue
        n += 1
    return n


def attached_keyword(state: GameState, table: CardTable, perm: int,
                     keyword: str) -> int:
    """718.3 -- `keyword`'s value from everything Attached to `perm`.

    Read off `table.attached_kw`, parsed from the "Attached:" band, and summed
    the way `static_keyword` sums: 807.1.c makes [Assault X] short for an
    ability, and two abilities both apply, so two swords stack.

    Deliberately not routed through `row_statics`: 718.2 switches off the
    Attached card's own printed Rules Text, and its Effect Text is the half
    that 718.3 keeps -- they are different bands of the card and the Inactive
    rule reaches only the first.
    """
    total = 0
    for i in state.attachments(perm):
        for kw, n in table.attached_kw[int(state.perms[i, P_CARD])]:
            if kw == keyword:
                total += n
    return total


def granted_kw(state: GameState, table: CardTable, perm: int,
               keyword: str, include_bf: bool = True) -> int:
    """`perm_kw` minus the card's own printed keyword -- what was GIVEN to it.

    135.4.b: "Any granted or appended Rules Text on a card is still Active even
    if that card is Attached." So when a rule has to sleep an Attached card's
    printed keyword (718.2) it must not sleep a granted one along with it --
    a Spinning Axe that was HANDED [Temporary] by Fading Memories still expires
    while attached, where its own printed [Temporary] does not (722.2).
    """
    idx = GRANT_IDX.get(keyword)
    granted = static_keyword(state, table, perm, keyword, include_bf)
    if idx is None:
        return granted
    return (granted + int(state.kw_grant[perm, idx])
            + int(state.kw_grant_turn[perm, idx]))


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
    printed = _printed_kw(table, state.eff_card(perm), keyword)
    if state.n_attached:
        from rl.engine.effects import TEXT_COPIERS
        printed *= 1 + sum(1 for g in state.attachments(perm)
                           if table.names[int(state.perms[g, P_CARD])] in TEXT_COPIERS)
    granted = static_keyword(state, table, perm, keyword, include_bf)
    # 718.3 -- an Attached card's Effect Text is APPENDED to this card's Rules
    # Text, so a keyword in that band is this permanent's keyword while the
    # Equipment stays attached. 136.2.c is what fixes the direction: Effect
    # Text's "I" means the object it is attached to, so Doran's Shield's
    # "[Tank] (I must be assigned combat damage first)" makes the UNIT a Tank.
    granted += attached_keyword(state, table, perm, keyword)
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
    # "...IF THEY DIDN'T ALREADY" (Spirit's Refuge). A grant that says so is not
    # additive: it tops the unit up to one instance and stops, so two Refuges
    # are one [Deflect] and not two (RiftJudge #7690). Collected apart from the
    # additive grants and applied once, after them, because whether it applies
    # at all depends on what the rest of the board already gave.
    topups = 0
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in row_statics(state, table, i):
            if st.kind != ST_KEYWORD or st.keyword != keyword:
                continue
            if static_reaches(state, table, st, i, perm):
                # "[Assault] equal to the number of gear you control" (Repair
                # Specialist) -- a counted keyword, zero when nothing counts.
                src = state.perms[i]
                amount = max(1, st.n) * static_count(
                    state, table, st, int(src[P_CTRL]), int(src[P_LOC]),
                    int(src[P_CARD]), i)
                if st.lacks_printed_keyword == keyword:
                    topups = max(topups, amount)
                else:
                    total += amount
    for seat, st in legend_statics(state, table):
        if st.kind != ST_KEYWORD or st.keyword != keyword:
            continue
        if static_reaches(state, table, st, -1, perm, src_seat=seat):
            total += max(1, st.n) * static_count(
                state, table, st, seat, -1, int(state.legend[seat]), -1)
    if include_bf:
        for st in bf_statics_for(state, table, perm):
            if st.kind == ST_KEYWORD and st.keyword == keyword:
                total += max(1, st.n)
    if topups and total == 0 and not _printed_kw(table, int(row[P_CARD]), keyword):
        total = topups
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
        # "BIRD, CAT, DOG, PORO, AND IVERN units here" (Brush) -- the same
        # affected-unit filters `static_reaches` applies on the permanent
        # path. Without them a battlefield's narrowed static reached every
        # unit standing there: Brush gave a Pirate +5 Might, one per tag.
        if st.scope_tag and st.scope_tag not in perm_tags(state, table, perm):
            continue
        if st.scope_name and table.names[unit_card] != st.scope_name:
            continue
        if st.scope_token and not table.is_token(unit_card):
            continue
        if st.requires_empowered and not state.empower_count(perm):
            continue
        if st.requires_buffed and not state.has_flag(perm, F_BUFFED):
            continue
        if st.requires_stunned and not state.has_flag(perm, F_STUNNED):
            continue
        if st.requires_defending_alone and not defending_alone(
                state, table, perm):
            continue
        if st.requires_equipped and not any(
                "Equipment" in table.tags[int(state.perms[g, P_CARD])]
                for g in state.attachments(perm)):
            continue
        yield st


def legend_statics(state: GameState, table: CardTable):
    """(seat, static) for every static printed on a legend in play.

    A legend is a Game Object from turn 1 that never leaves its zone (103.1),
    so its statics are simply always on -- there is no arrival, no death and no
    location to gate them. Iterated beside the permanent walk at each site that
    reads statics off the board, rather than being folded into `row_statics`,
    which is indexed by permanent row and has none to give.
    """
    from rl.engine.effects import legend_statics_for
    for seat in range(N_SEATS):
        lcard = int(state.legend[seat])
        if lcard < 0:
            continue
        for st in legend_statics_for(table, lcard):
            yield seat, st


def static_reaches(state: GameState, table: CardTable, st, src_i: int,
                   perm: int, attached_row: int = -1,
                   src_seat: int = -1) -> bool:
    """Does static `st`, printed on permanent `src_i`, apply to `perm`?

    The scope reading shared by every kind of static, so "your token units
    have [Tank]" and "I can't be chosen" answer the *same* question about who
    a static reaches and differ only in what they then do. Kept in one place
    because a second copy of this block would drift from the first exactly
    once, silently, on whichever card was added last.

    `src_i < 0` is a static with no permanent behind it -- a LEGEND's ("your
    Mechs have [Shield]"), which is printed in the Legend Zone. `src_seat` then
    says whose it is, and the clauses that ask where the source is standing
    cannot be satisfied: 107.4.b makes the Legend Zone not a location, so
    "here" reaches nothing and "I" is not a unit on the board.
    """
    if src_i >= 0:
        src = state.perms[src_i]
        src_seat = int(src[P_CTRL])
        src_loc = int(src[P_LOC])
    else:
        assert src_seat >= 0, "a sourceless static must say whose it is"
        src_loc = -1
    if not static_applies(state, st, src_seat, src_i, attached_row, table):
        return False
    if st.scope == SC_SELF:
        return src_i >= 0 and src_i == perm
    if src_i < 0 and (st.scope_same_loc or st.requires_less_might):
        return False
    row = state.perms[perm]
    card = int(row[P_CARD])
    if st.scope == SC_ALL_UNITS:
        return bool(table.is_type(card, "Unit"))
    if (src_seat == int(row[P_CTRL])) == (st.scope == SC_ENEMY_UNITS):
        return False
    if st.scope_token and not table.is_token(card):
        return False
    if st.scope_tag and st.scope_tag not in perm_tags(state, table, perm):
        return False
    if st.scope_name and table.names[card] != st.scope_name:
        return False
    if st.scope_not_self and src_i == perm:
        return False
    if st.scope_same_loc and src_loc != int(row[P_LOC]):
        return False
    # "your units THAT ARE [Empowered]" -- a requirement on the AFFECTED unit's
    # status (441.1.a), the mirror of `requires_keyword`. Aurok General's "(and
    # me)" needs no clause: he is a friendly unit and he is Empowered, since
    # `cond=COND_EMPOWERED` on the same static is what turned it on.
    if st.requires_empowered and not (int(row[P_FLAGS]) & F_EMPOWERED):
        return False
    if st.requires_buffed and not (int(row[P_FLAGS]) & F_BUFFED):
        return False
    if st.requires_stunned and not (int(row[P_FLAGS]) & F_STUNNED):
        return False
    if st.requires_defending_alone and not defending_alone(state, table, perm):
        return False
    if st.requires_equipped and not any(
            "Equipment" in table.tags[int(state.perms[g, P_CARD])]
            for g in state.attachments(perm)):
        return False
    if st.lacks_printed_keyword and _printed_kw(table, card, st.lacks_printed_keyword):
        return False
    # Last, and only for kinds that are not themselves Might: `might` reads
    # ST_MIGHT statics, so a Might static gated on Might would recurse.
    if st.requires_less_might:
        assert st.kind != ST_MIGHT, "requires_less_might on a Might static"
        if might(state, table, perm) >= might(state, table, src_i):
            return False
    return bool(table.is_type(card, "Unit"))


def in_combat(state: GameState, perm: int) -> bool:
    """Is `perm` a participant in the Combat currently open?

    A unit is in the Combat if there IS one and it is standing where it is
    happening -- the same reading `combat_role_bonus` uses to decide whether
    [Assault]/[Shield] apply.
    """
    bf = int(state.showdown_bf)
    return bf >= 0 and int(state.perms[perm, P_LOC]) == bf_loc(bf)


def damage_prevented(state: GameState, table: CardTable, perm: int) -> bool:
    """Ambessa -- "can't be dealt damage unless I'm in combat".

    Not `unchoosable_by` with different words. That one restricts who may POINT
    at a unit (355.10) and is therefore no defence at all against a sweep that
    chooses nothing; this stops the damage itself however it arrives, and is
    the reason the card reads as a wall rather than as evasion.

    "Unless I'm in combat" is the whole exception, and it is why this belongs
    in `mark_damage` rather than in the combat damage step: combat damage is
    only ever dealt to units that are in a Combat, so it is exempt by
    construction and needs no check.
    """
    if in_combat(state, perm):
        return False
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in row_statics(state, table, i):
            if st.kind == ST_NO_DAMAGE and static_reaches(
                    state, table, st, i, perm):
                return True
    return False


ANIMAL_TAGS = frozenset({"Bird", "Cat", "Dog", "Poro"})
_MIGHTY_GUARD: set[int] = set()


def modify_incoming(state: GameState, perm: int, raw: int,
                    consume: bool = True) -> int:
    """Damage `perm` actually takes from one instance of `raw`, after this
    turn's modifiers: doubled (Lotus Trap), then reduced by a prevention
    shield (Ki Barrier's 7, or Counter Strike's whole next instance). Doubling
    first is the order that favours the unit's controller, who orders
    replacement effects on their own unit (370.2)."""
    if raw <= 0:
        return raw
    ply = int(state.ply)
    amt = raw * 2 if int(state.double_dmg_ply[perm]) == ply else raw
    # The whole-instance prevent first: it takes the instance at any size,
    # so spending a Prevent Value on it as well would waste the value.
    if int(state.block_next_ply[perm]) == ply:
        if consume:
            state.block_next_ply[perm] = -1
        return 0
    if int(state.shield_ply[perm]) == ply:
        left = int(state.shield_amt[perm])
        blocked = min(left, amt)
        if consume:
            state.shield_amt[perm] = left - blocked
            if left - blocked <= 0:
                state.shield_ply[perm] = -1         # 437.3.a
        amt -= blocked
    return amt


def _raw_for(state: GameState, perm: int, need: int) -> int:
    """Smallest raw instance that deals `need` after `modify_incoming`."""
    ply = int(state.ply)
    if int(state.block_next_ply[perm]) == ply:
        return 10 ** 4                     # the whole instance is prevented
    if int(state.shield_ply[perm]) == ply:
        need += int(state.shield_amt[perm])
    if int(state.double_dmg_ply[perm]) == ply:
        need = (need + 1) // 2
    return max(1, need)


def note_damage_source(state: GameState, perm: int, by_seat: int,
                       amount: int) -> None:
    """Record whether an opponent of `perm`'s controller dealt this damage.

    Called just BEFORE the damage is added. An undamaged row starts over, so
    damage healed away earlier this turn cannot leave a stale mark behind.
    """
    if int(state.perms[perm, P_DMG]) <= 0:
        state.foe_dmg[perm] = 0
    if amount > 0 and by_seat >= 0 and by_seat != int(state.perms[perm, P_CTRL]):
        state.foe_dmg[perm] = 1


def your_damage_kills(state: GameState, table: CardTable, by_seat: int,
                      perm: int) -> bool:
    """Elder Dragon -- `by_seat` has one, and `perm` is an ENEMY of theirs."""
    return (by_seat >= 0 and int(state.perms[perm, P_CTRL]) != by_seat
            and any(state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == by_seat
                    and table.names[int(state.perms[i, P_CARD])] in YOUR_DAMAGE_KILLS
                    for i in range(state.n_perms)))


def return_to_hand(state: GameState, table: CardTable, perm: int) -> None:
    """Bounce `perm` to its OWNER's hand -- what every bounce prints.

    The third way off the board, neither a Kill nor a Banish (see
    `queue_leaves_board`). 185.3: a token that leaves the board ceases to
    exist, so only real cards reach a hand.
    """
    owner = int(state.perms[perm, P_OWNER])
    card = int(state.perms[perm, P_CARD])
    queue_leaves_board(state, table, perm)
    # Ripper's Bay -- "When a unit here is returned to a player's hand, THAT
    # player may pay [1]". The zone change happens first, so a token that then
    # ceases to exist still fired it (RiftJudge #11712).
    loc = int(state.perms[perm, P_LOC])
    if is_battlefield(loc) and table.is_type(card, "Unit"):
        _queue_bf_trigger(state, table, TR_LEAVES_BOARD, bf_index(loc), owner,
                          subj=perm)
    state.perms[perm, P_ALIVE] = 0
    if not table.is_token(card):
        h = int(state.n_hand[owner])
        assert h < state.hand.shape[1], "hand overflow"
        state.hand[owner, h] = card
        state.n_hand[owner] = h + 1


def _named_at_bf(state: GameState, table: CardTable, names, seat: int = -1,
                 not_seat: int = -1, loc: int = -1) -> bool:
    """Is a permanent named in `names` alive at a battlefield (or at `loc`),
    controlled by `seat` / by anyone but `not_seat`?"""
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        if table.names[int(state.perms[i, P_CARD])] not in names:
            continue
        c, l = int(state.perms[i, P_CTRL]), int(state.perms[i, P_LOC])
        if seat >= 0 and c != seat or not_seat >= 0 and c == not_seat:
            continue
        if (loc >= 0 and l != loc) or (loc < 0 and not is_battlefield(l)):
            continue
        return True
    return False


def points_blocked(state: GameState, table: CardTable | None, seat: int) -> bool:
    """Tianna Crownguard -- an opponent of `seat` has her at a battlefield."""
    return table is not None and _named_at_bf(state, table, BLOCKS_OPP_POINTS,
                                              not_seat=seat)


def score_blocked_here(state: GameState, table: CardTable | None, seat: int,
                       i: int) -> bool:
    """Forgotten Monument -- "players can't score HERE until their third turn".

    Counted in the scoring player's OWN turns: `state.turn` advances once per
    round, so seat 0 and seat 1 have both taken `turn + 1` turns by the time
    either scores on it. Read as "this is my third turn or later", which is
    turn index 2.
    """
    from rl.engine.effects import BF_SCORE_RULES
    if table is None:
        return False
    card = int(state.bf_card[i])
    if card < 0:
        return False
    rule = BF_SCORE_RULES.get(table.names[card], {})
    need = int(rule.get("no_score_before_turn", 0))
    return bool(need) and int(state.turn) < need - 1


def channel_count(state: GameState, table: CardTable | None) -> int:
    """Runes channelled at the Channel Phase: 2, or 1 under Sandstone Chimera."""
    return 1 if table is not None and _named_at_bf(state, table,
                                                   ONE_RUNE_CHANNEL) else 2


def ready_blocked(state: GameState, table: CardTable, perm: int) -> bool:
    """Mageseeker Warden -- spells and abilities can't ready the units and
    gear of the Warden's opponents while he is at a battlefield. Maduli the
    Gatekeeper -- "I can't be readied", by anything."""
    if table.names[int(state.perms[perm, P_CARD])] in NEVER_READIED:
        return True
    return _named_at_bf(state, table, WARDEN_LOCKS,
                        not_seat=int(state.perms[perm, P_CTRL]))


def base_only_plays(state: GameState, table: CardTable, seat: int) -> bool:
    """Mageseeker Warden -- `seat`'s units may only be played to its base."""
    return _named_at_bf(state, table, WARDEN_LOCKS, not_seat=seat)


def permanent_play_allowed(state: GameState, table: CardTable, seat: int,
                           card: int) -> bool:
    """Printed limits on WHEN or WHERE a permanent may be played."""
    after = PLAY_AFTER_TURN.get(table.names[card])
    if after is not None and int(state.turn) <= after:
        return False          # Ol' Poro
    if table.names[card] in PLAY_ONLY_CONQUERED:
        return any(int(state.bf_conquered_ply[seat, b]) == int(state.ply)
                   for b in state.live_bfs())
    return True


def _queue_mark(state: GameState, perm: int, trigger: int) -> None:
    """Queue the Delayed Ability marked on `perm` this turn, if any."""
    if int(state.mark_ply[perm]) != int(state.ply) or int(state.mark_slot[perm]) < 0:
        return
    from rl.engine.chain import queue as chain_queue
    from rl.engine.state import delayed_src
    seat, slot = int(state.mark_seat[perm]), int(state.mark_slot[perm])
    if int(state.delayed[seat, slot]) < 0:
        return
    chain_queue(state, trigger, delayed_src(seat, slot),
                int(state.perms[perm, P_LOC]), subj=int(perm))


def moved_twice_protected(state: GameState, table: CardTable, perm: int) -> bool:
    return (table.names[int(state.perms[perm, P_CARD])] in MOVED_TWICE_NO_DAMAGE
            and int(state.move_ply[perm]) == int(state.ply)
            and int(state.move_count[perm]) >= 2)


def _soraka_guards(state: GameState, table: CardTable, perm: int,
                   batch: tuple[int, ...] = ()) -> bool:
    """Soraka - Wanderer's replacement for a smaller friendly unit here.

    A Soraka dying in the same `batch` still guards: 370.4 lets a Game Object
    apply its replacement to events simultaneous with its own leaving, and
    names Soraka as the example (RiftJudge #12381). Without it the answer
    depended on row order -- a Soraka swept first was already gone.
    """
    ctrl, loc = int(state.perms[perm, P_CTRL]), int(state.perms[perm, P_LOC])
    for i in range(state.n_perms):
        if (i != perm and (state.perms[i, P_ALIVE] == 1 or i in batch)
                and int(state.perms[i, P_CTRL]) == ctrl
                and int(state.perms[i, P_LOC]) == loc
                and table.names[int(state.perms[i, P_CARD])] in SMALLER_ALLY_GUARDS
                and might(state, table, perm) < might(state, table, i)):
            return True
    return False


def early_score_draws(state: GameState, table: CardTable | None) -> bool:
    """Otterpus -- is a conquer/hold point replaced by a draw right now?"""
    if table is None or int(state.turn) > 2:
        return False
    return any(state.perms[i, P_ALIVE] == 1
               and table.names[int(state.perms[i, P_CARD])] in EARLY_SCORE_TO_DRAW
               for i in range(state.n_perms))


def opp_controls_stunned(state: GameState, seat: int) -> bool:
    """Monch -- "if an opponent controls a stunned unit"."""
    return any(state.perms[i, P_ALIVE] == 1
               and int(state.perms[i, P_CTRL]) != seat
               and int(state.perms[i, P_FLAGS]) & F_STUNNED
               for i in range(state.n_perms))


def queue_combat_ends(state: GameState, table: CardTable, bf: int) -> None:
    """Queue "when a combat that I was in ends" for everyone still standing.

    Called from both places a Showdown closes, and gated by the CALLER on
    `showdown_combat`: 344.2 opens a Non-Combat Showdown that ends through the
    same code, and a card that says "combat" must not pay out for one.

    "That I was in" is read as still being at the battlefield when it ends. A
    unit that died in the combat is not there to receive anything, and every
    op that could act on it checks `P_ALIVE` anyway.
    """
    loc = bf_loc(bf)
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1 or int(state.perms[i, P_LOC]) != loc:
            continue
        if any(a.trigger == TR_COMBAT_ENDS
               for a in row_abilities(state, table, i)):
            from rl.engine.chain import queue as chain_queue
            chain_queue(state, TR_COMBAT_ENDS, i, loc)


def unchoosable_by(state: GameState, table: CardTable, perm: int,
                   seat: int) -> bool:
    """Ruin Runner -- "I can't be chosen by ENEMY spells and abilities".

    A restriction on who may point at the unit, not on what may be done to it:
    its own controller still targets it freely, and nothing here stops combat
    damage or a board-wide sweep, neither of which chooses (355.10).
    """
    if seat == int(state.perms[perm, P_CTRL]):
        return False
    # Twilight Shroud -- the same prohibition granted to one unit for a turn.
    if int(state.perms[perm, P_FLAGS]) & F_UNCHOOSABLE_TURN:
        return True
    # Akali, Silent -- "...unless I'm in combat". Checked again as the spell
    # resolves, so Flashing her out mistargets her (758.1, RiftJudge #11754).
    if (table.names[state.eff_card(perm)] in SAFE_UNLESS_IN_COMBAT
            and not in_combat(state, perm)):
        return True
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in row_statics(state, table, i):
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
    # 807.1.d -- the designations exist only "during Combat". A Non-Combat
    # Showdown (moving onto open ground) has no Attacker and no Defender, so
    # neither keyword adds anything there (RiftJudge #11895).
    if bf < 0 or not state.showdown_combat:
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
    buff = (1 + int(state.extra_buffs[perm])) if int(row[P_FLAGS]) & F_BUFFED else 0
    # Stand United -- "Buffs give an additional +1 Might to friendly units".
    if buff and int(state.buff_bonus_ply[int(row[P_CTRL])]) == int(state.ply):
        buff += max(1, int(state.buff_bonus_n[int(row[P_CTRL])]))
    st_total, floors = _static_might_parts(state, table, perm)
    total = (base_might(state, table, perm) + int(row[P_MIGHT_MOD])
             + buff + st_total
             + attached_might(state, table, perm)
             + combat_role_bonus(state, table, perm))
    if (int(state.combat_might_ply[perm]) == int(state.ply)
            and in_combat(state, perm)):
        total += int(state.combat_might_val[perm])
    # "-8 Might, to a minimum of 1" (Leona - Zealot): a floored static lowers
    # the unit's Might as it otherwise stands, never below its floor, and never
    # RAISES a unit already under it.
    for st in floors:
        total = min(total, max(st.floor, total + st.n))
    return max(0, total)


def base_might(state: GameState, table: CardTable, perm: int) -> int:
    """The printed Might, unless an effect has set it ("Its base Might becomes
    5 this turn", Dragon Form). Modifiers and statics still apply on top."""
    if int(state.base_might_ply[perm]) == int(state.ply):
        return int(state.base_might_val[perm])
    return int(table.might[state.eff_card(perm)])


def attached_might(state: GameState, table: CardTable, perm: int) -> int:
    """718.4 -- the Might Bonus of everything Attached to `perm` (137.3).

    Unlike a static, this is not read off the Attached card's Rules Text: a
    Might Bonus is its own printed field (137.3) and keeps applying while the
    card's Rules Text is Inactive (718.4 sits alongside 718.2, not under it).
    So this deliberately does NOT go through `row_statics`.

    137.3.a scopes it exactly: it "is applied while Attached and stops applying
    as soon as the card with the Might Bonus is no longer Attached" -- which is
    why it is computed here on every call rather than written into
    `P_MIGHT_MOD` when the Equipment attaches.

    Read off `table.might_bonus`, which `cardtable.might_bonus` parses out of
    the "Attached:" band the errata overlay supplies -- see the note in
    `effects.py` for why there is no registry.
    """
    total = sum(int(table.might_bonus[int(state.perms[i, P_CARD])])
                for i in state.attachments(perm))
    if total and table.names[int(state.perms[perm, P_CARD])] in EQUIP_BONUS_DOUBLERS:
        total *= 2          # Gearhead
    return total


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
                       and (int(state.perms[i, P_DMG]) >= might(state, table, i)
                            # Elder Dragon -- the opponent's damage already
                            # on the unit is "your damage" to them.
                            or (state.foe_dmg[i]
                                and your_damage_kills(
                                    state, table,
                                    1 - int(state.perms[i, P_CTRL]), i))))
        if not doomed:
            return killed
        for i in doomed:
            _destroy(state, table, i, batch=doomed)
            if state.perms[i, P_ALIVE] == 1:
                # Altar of Blood opened an offer: this unit has not died and
                # the rest of the sweep must wait for the answer, or the
                # continuous check would come back round and kill it anyway.
                if int(state.pend_altar) >= 0:
                    return killed
                continue
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
    # The printed floor binds EFFECTIVE Might, so everything `might` counts
    # counts here -- statics, buffs, and an attached Equipment's Might Bonus
    # (137.3). Reading only base + statics floored a 2-Might unit wearing a
    # +2 sword at 1 - 2 instead of 1 - 4, so Smoke Screen left it on 3 where
    # the ruling (RiftJudge #12586) is 1.
    cur = might(state, table, perm)
    new = int(row[P_MIGHT_MOD]) + delta
    if floor is not None and cur + delta < floor:
        new = int(row[P_MIGHT_MOD]) + (floor - cur)
    row[P_MIGHT_MOD] = new

    dmg = int(row[P_DMG])
    if dmg > 0 and dmg >= might(state, table, perm):
        _destroy(state, table, perm)
        return True
    return False


def mark_damage(state: GameState, table: CardTable, perm: int,
                amount: int, by_seat: int = -1, unit_source: bool = False) -> bool:
    """Mark damage and apply 143.2.a. Returns True if it killed the unit.

    **This is the spell-and-ability damage path, and only that.** Combat damage
    is assigned in the damage step, which writes `P_DMG` directly -- so Void
    Gate's "spells and abilities affecting units here each deal 1 Bonus Damage"
    belongs here and nowhere else, and combat damage is correctly untouched.

    "Each INSTANCE of damage is increased by 1" falls out of the call shape:
    one call is one instance, so a spell that deals damage twice is bonused
    twice without the wording having to be arranged for.

    `unit_source`: the damage is dealt BY A UNIT a spell or ability named
    ("they deal damage equal to their Mights to each other"). 417.6.b.3 makes
    the unit the only source -- "not in addition to" the spell -- so nothing
    that reads spell or ability damage applies: not Unyielding Spirit, not
    Void Gate's or Annie's Bonus Damage, not Esteemed Hierophant's ward
    (RiftJudge #11411). `by_seat` is then the dealing unit's controller
    (417.6.b.4).
    """
    # Ambessa -- refused outright, so no damage is marked and nothing about
    # the unit changes. Checked before the Bonus Damage arithmetic below: a
    # bonus applied to damage that is never dealt would be a number computed
    # for nobody.
    if amount > 0 and (damage_prevented(state, table, perm)
                       or moved_twice_protected(state, table, perm)):
        return False
    if amount > 0 and by_seat >= 0 and not unit_source:
        ctrl_t = int(state.perms[perm, P_CTRL])
        # Esteemed Hierophant -- an ENEMY spell's damage, with 7+ runes.
        if (by_seat != ctrl_t
                and table.names[int(state.perms[perm, P_CARD])] in RUNE_WARD
                and int(state.runes_in_play(ctrl_t).sum()) >= 7):
            return False
        # Ravenborn Tome -- the spell resolving right now carries its bonus.
        amount += int(state.resolving_bonus)
        # Annie - Fiery -- "your spells and abilities deal 1 Bonus Damage".
        amount += sum(
            EFFECT_BONUS_DAMAGE.get(table.names[int(state.perms[i, P_CARD])], 0)
            + (EQUIP_EFFECT_BONUS_DAMAGE.get(
                table.names[int(state.perms[i, P_CARD])], 0)
               if state.is_attached(i) else 0)
            for i in range(state.n_perms)
            if state.perms[i, P_ALIVE] == 1
            and int(state.perms[i, P_CTRL]) == by_seat)
    # Unyielding Spirit -- every caller of this function is a spell or an
    # ability; combat damage is marked by `_assign`.
    if (amount > 0 and not unit_source
            and int(state.no_effect_damage_ply) == int(state.ply)):
        return False
    if amount > 0:
        # Bonus Damage rides on a nonzero instance. A 0-damage event is not an
        # instance of damage to increase -- and turning one into 1 would make
        # 143.2.a lethal where the rules say nothing happened at all.
        if not unit_source:
            amount += bf_damage_bonus(state, table,
                                      int(state.perms[perm, P_LOC]))
        amount = modify_incoming(state, perm, amount)
        if amount <= 0:
            return False                   # prevented entirely
    note_damage_source(state, perm, by_seat, amount)
    state.perms[perm, P_DMG] += amount
    if amount > 0:
        state.perms[perm, P_FLAGS] |= F_DAMAGED_TURN
        if int(state.guillotine_ply[perm]) == int(state.ply):
            # Noxian Guillotine -- "kill it the next time it takes damage".
            state.guillotine_ply[perm] = -1
            _destroy(state, table, perm)
            return state.perms[perm, P_ALIVE] != 1
    dmg = int(state.perms[perm, P_DMG])
    # Imperial Decree lowers the lethal threshold to ANY nonzero damage, for
    # every unit on the board. 143.2.a's "nonzero" still holds -- a 0-damage
    # event kills nothing, which is what keeps Might reduction from becoming
    # removal under the Decree.
    if state.any_damage_kills and dmg > 0:
        _destroy(state, table, perm)
        return True
    lethal = dmg > 0 and (
        (amount > 0 and your_damage_kills(state, table, by_seat, perm))  # Elder Dragon
        or dmg >= might(state, table, perm))
    if lethal and RESOLVING[0]:
        # Inside a spell's or ability's resolution the unit dies in the
        # Cleanup that follows it, together with everything else that took
        # lethal damage there: both of Falling Star's 3s land before one
        # Zhonya's is spent (#12367), and a Poro and a Sentry killed by one
        # Bellows Breath die side by side, not alone (#10889). Reported as a
        # kill now, so "if this kills it" still reads it.
        if perm not in HELD_DEATHS:
            HELD_DEATHS.append(perm)
            # Who is killing it is known NOW, inside the resolution; by the
            # release the spell's KILLER context has been restored, and Immortal
            # Phoenix would never learn a spell killed anything (#9374).
            HELD_KILLER[perm] = tuple(KILLER)
        return True
    if lethal:
        _destroy(state, table, perm)
        return True
    return False


def banish(state: GameState, table: CardTable, perm: int) -> None:
    """Remove a permanent to Banishment (427). NOT a kill.

    427.2.a is explicit that "Banish is not a subset of Kill", so this must not
    do the two things `_destroy` does: no [Deathknell] fires and the card does
    not go to the trash. Getting that wrong would hand a Deathknell deck free
    value from the opponent's removal.

    It IS a leaving, though, and that is the distinction Treasure Trove is
    built on: "when this leaves the board" pays out however the card goes, so
    banishing it does not deny the trigger the way it denies a Deathknell.

    **The card lands in its OWNER's Banishment (108.6).** This used to clear
    `P_ALIVE` and nothing else, which was invisible for as long as `OP_BLINK`
    was the only caller -- it banishes and immediately replays, so the card
    came straight back and nothing noticed it had been nowhere in between. The
    moment `OP_BANISH` banished one for real (Wind and Ghosts), the card simply
    ceased to exist, and the per-seat conservation gate caught it in both the
    spell and deck fuzzes.

    186 is the exception: a token in any non-board zone ceases to exist, so
    banishing one is straight removal with nothing to store -- the same
    carve-out `_destroy` makes for the trash.
    """
    queue_leaves_board(state, table, perm)
    row = state.perms[perm]
    card = int(row[P_CARD])
    row[P_ALIVE] = 0
    if not table.is_token(card):
        state.banish_card(int(row[P_OWNER]), card)


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
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in row_statics(state, table, i):
            if st.kind == ST_NO_COMBAT_DAMAGE and static_reaches(
                    state, table, st, i, perm):
                return 0
    return might(state, table, perm)


def lethal_cost(state: GameState, table: CardTable, perm: int,
                assigner: int = -1) -> int:
    """Damage still needed to destroy this unit.

    465.2.c.2 defines Lethal Damage as **non-zero** damage equaling or exceeding
    current Might, so a 0-Might unit still costs 1 to kill -- it is not free, and
    it does not die to an empty pool.
    """
    # Noxian Guillotine: any damage at all kills it this turn.
    if int(state.guillotine_ply[perm]) == int(state.ply):
        return _raw_for(state, perm, 1)
    # Kayn - Unleashed takes no damage at all: no assignment kills him.
    if moved_twice_protected(state, table, perm):
        return 10 ** 4
    if your_damage_kills(state, table, assigner, perm):
        return _raw_for(state, perm, 1)              # Elder Dragon
    return _raw_for(state, perm,
                    max(1, might(state, table, perm) - int(state.perms[perm, P_DMG])))


def queue_leaves_board(state: GameState, table: CardTable, perm: int) -> None:
    """Queue "when this leaves the board" for `perm`, if it prints one.

    Called from every path that takes a permanent off the board, and there are
    three: a Kill (428), a Banish (427) and a bounce to hand. They are
    deliberately different events everywhere else -- 427.2.a makes Banish not a
    subset of Kill, and only a Kill fires [Deathknell] -- so a trigger that
    covers all three cannot ride on any one of them.

    Queued while the row is still readable, the same instant `TR_DEATH` is
    (808.1.d.2), so both see the same board.

    **719.5's Detach also happens here**, and for the same reason this function
    exists at all: "when a Top-Most Card changes zones from a board zone to a
    non-board zone" is exactly the union of those three paths, so putting it
    anywhere else would need all three to remember it and would drift the first
    time a fourth exit appeared.
    """
    from rl.engine.chain import queue as chain_queue  # cycle: chain -> resolve -> combat
    if any(a.trigger == TR_LEAVES_BOARD
           for a in row_abilities(state, table, perm)):
        chain_queue(state, TR_LEAVES_BOARD, perm,
                    int(state.perms[perm, P_LOC]))
    # 719.5 -- whatever was Attached to this card detaches and STAYS on the
    # board. A killed unit drops its Equipment rather than taking it along.
    state.detach_all(perm)
    if table.names[int(state.perms[perm, P_CARD])] == "Endless Riches":
        state.riches_on[int(state.perms[perm, P_CTRL])] = max(
            0, int(state.riches_on[int(state.perms[perm, P_CTRL])]) - 1)
    # Akshan: what he took is handed back to its owner as he leaves.
    for g in range(state.n_perms):
        if int(state.ctrl_link[g]) == perm and state.perms[g, P_ALIVE] == 1:
            state.ctrl_link[g] = -1
            owner = int(state.perms[g, P_OWNER])
            if int(state.perms[g, P_CTRL]) != owner:
                if state.is_attached(g):
                    state.detach(g)
                state.perms[g, P_CTRL] = owner
                state.set_location(g, base_loc(owner))
    # ...and if the card leaving was itself Attached, its own link goes with
    # it. 718.1 ends the Attached state; leaving the board certainly ends it,
    # and a stale row index here would outlive the card that owned it.
    state.detach(perm)


# Who is killing right now: (seat, by a spell). Set around a Chain Item's
# resolution and around each side's combat damage; (-1, False) otherwise.
# Transient -- it never outlives the call that set it, so it is not state.
KILLER: list = [-1, False]


def altar_offer(state: GameState, table: CardTable, perm: int) -> bool:
    """Is this death one Altar of Blood offers to replace, for a price?

    Four conditions, all from the card: a UNIT (a gear is not one), standing at
    the Altar, dying DURING A COMBAT there, whose controller can actually pay
    the three Power. The per-row ply stamp is the fifth and is not from the
    card: it makes a declined offer stick for the instant it takes the caller
    to come back round and kill the unit for real.
    """
    from rl.engine.cost import plan_wild_power
    from rl.engine.effects import BF_DEATH_REPLACEMENT
    row = state.perms[perm]
    if state.has_flag(perm, F_NON_UNIT) or int(state.pend_altar) >= 0:
        return False
    if int(state.altar_ply[perm]) == int(state.ply):
        return False
    loc = int(row[P_LOC])
    if not is_battlefield(loc):
        return False
    i = bf_index(loc)
    card = int(state.bf_card[i])
    if card < 0 or table.names[card] not in BF_DEATH_REPLACEMENT:
        return False
    # "DURING COMBAT" -- the Combat Showdown at this very battlefield.
    if int(state.showdown_bf) != i or not int(state.showdown_combat):
        return False
    cost = BF_DEATH_REPLACEMENT[table.names[card]]
    return plan_wild_power(state, int(row[P_CTRL]), cost) is not None


# Depth of spell/ability resolutions in progress, and the units whose lethal
# damage was held back inside one because a death REPLACEMENT waits for them.
# 143.2.a's kill happens in the Cleanup after the item resolves, so a unit hit
# twice by one Falling Star takes both 3s before Zhonya's is spent once
# (RiftJudge #12367). Only replaceable deaths are held: every other kill stays
# immediate, which "if this kills it" wording relies on. Transient.
RESOLVING: list = [0]
HELD_DEATHS: list = []
HELD_KILLER: dict = {}


def death_replaceable(state: GameState, table: CardTable, perm: int) -> bool:
    """Would a replacement stop `perm` dying right now (see `_destroy`)?"""
    if state.has_flag(perm, F_NON_UNIT):
        return False
    if any(table.names[int(state.perms[i, P_CARD])] in EQUIP_DEATH_REPLACEMENT
           for i in state.attachments(perm)):
        return True
    if int(state.death_shield_ply[perm]) == int(state.ply):
        return True
    guard = int(state.death_guard[int(state.perms[perm, P_CTRL])])
    return guard >= 0 and guard != perm and state.perms[guard, P_ALIVE] == 1


def release_held_deaths(state: GameState, table: CardTable) -> None:
    """End of the outermost resolution: the held units die now, together, if
    they are still lethally damaged (a heal or a +Might in between saves one)."""
    held, HELD_DEATHS[:] = list(HELD_DEATHS), []
    killers = dict(HELD_KILLER)
    HELD_KILLER.clear()
    doomed = tuple(
        p for p in held
        if state.perms[p, P_ALIVE] == 1 and int(state.perms[p, P_DMG]) > 0
        and (int(state.perms[p, P_DMG]) >= might(state, table, p)
             or (state.foe_dmg[p] and your_damage_kills(
                 state, table, 1 - int(state.perms[p, P_CTRL]), p))))
    prev = KILLER[:]
    try:
        for p in doomed:
            KILLER[:] = list(killers.get(p, (-1, False)))
            _destroy(state, table, p, batch=doomed)
    finally:
        KILLER[:] = prev


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
    # Altar of Blood -- "if a unit here would die during combat, its controller
    # may pay {any rune}{any rune}{any rune} to heal it, exhaust it, and recall
    # it instead." A replacement that charges a COST, so unlike every other one
    # in this ladder it cannot be decided in advance: the game stops here and
    # `actions` asks. The unit does not die yet, and does not die at all if the
    # offer is accepted.
    if altar_offer(state, table, perm):
        state.altar_ply[perm] = int(state.ply)
        state.pend_altar = int(perm)
        return
    # Shadow Watcher's window: a unit dying during ITS CONTROLLER's Beginning
    # Phase. Recorded here because the question is asked later, when the phase
    # has passed and nothing on the board still says it happened.
    if (state.phase == BEGINNING and not state.has_flag(perm, F_NON_UNIT)
            and int(row[P_CTRL]) == int(state.active)):
        if not state.died_in_beginning[int(row[P_CTRL])]:
            from rl.engine.chain import fire_watchers as _fw
            from rl.engine.effects import TR_FIRST_BEGINNING_DEATH
            _fw(state, table, int(row[P_CTRL]), TR_FIRST_BEGINNING_DEATH)
        state.died_in_beginning[int(row[P_CTRL])] = 1
    # Zhonya's Hourglass -- "If a friendly unit would die, kill this instead.
    # Heal that unit, exhaust it, and recall it." (ERRATA; the printed text
    # omits the heal.) A replacement, so it runs before
    # anything else here: the unit never dies, so no Deathknell fires for it
    # and nothing reaches its trash.
    #
    # The guard is cleared FIRST and the guarding permanent is killed by the
    # same `_destroy` this sits in -- which is why clearing comes first. The
    # gear is not a unit, so it cannot guard its own death, and a second pass
    # finds no guard to consume. Without that order this recurses forever.
    ctrl_now = int(row[P_CTRL])
    # Guardian Angel -- "If I would die, kill Guardian Angel instead. Heal me,
    # exhaust me, and recall me." The same replacement as Zhonya's Hourglass,
    # but printed in an Equipment's Effect Text, so 136.2.c makes "I" the unit
    # it is attached to: it guards exactly that body and nothing else.
    #
    # Checked before Zhonya's. When both could replace the same death, 370.2
    # lets the controller apply them in either order, and the outcome for the
    # unit is identical (heal, exhaust, recall) -- what differs is which gear is
    # spent. Spending the attached Angel first is a fixed choice rather than an
    # offered one; it is the only place this engine picks between two
    # replacements for the player, and no deck in the corpus runs both.
    if not state.has_flag(perm, F_NON_UNIT):
        angel = next((i for i in state.attachments(perm)
                      if table.names[int(state.perms[i, P_CARD])]
                      in EQUIP_DEATH_REPLACEMENT), -1)
        if angel >= 0:
            # The Angel is a gear, not a unit, so its own death cannot recurse
            # into this branch; `queue_leaves_board` detaches it as it goes.
            _destroy(state, table, angel)
            state.perms[perm, P_DMG] = 0
            state.set_location(perm, base_loc(ctrl_now))
            row[P_READY] = 0
            return
    # One-turn death shields on the unit itself (Tactical Retreat, Highlander),
    # then Soraka's for a smaller ally beside her. All three are the same
    # replacement as Guardian Angel's: the unit never dies.
    if not state.has_flag(perm, F_NON_UNIT):
        shielded = int(state.death_shield_ply[perm]) == int(state.ply)
        if shielded:
            state.death_shield_ply[perm] = -1
        elif int(state.armory_ply[perm]) == int(state.ply):
            # Unlicensed Armory: "you may pay {Fury rune}" -- paid if it can be.
            state.armory_ply[perm] = -1
            from rl.engine.resolve import _pay_domain_power
            shielded = _pay_domain_power(state, ctrl_now, 3, 1)
        elif _soraka_guards(state, table, perm, batch):
            shielded = True
        if shielded:
            state.perms[perm, P_DMG] = 0
            state.set_location(perm, base_loc(ctrl_now))
            row[P_READY] = 0
            return
    # Smite -- "If it would die this turn, banish it instead."
    if int(state.banish_death_ply[perm]) == int(state.ply):
        state.banish_death_ply[perm] = -1
        banish(state, table, perm)
        return
    guard = int(state.death_guard[ctrl_now])
    if (guard >= 0 and guard != perm
            and state.perms[guard, P_ALIVE] == 1
            and not state.has_flag(perm, F_NON_UNIT)):
        state.death_guard[ctrl_now] = -1
        _destroy(state, table, guard)
        # 455 -- a Recall relocates to the base and is NOT a Move (456.1), so
        # no move trigger fires.
        #
        # **The HEAL is the errata, and it changes what the card answers.** The
        # printed text is "Recall that unit exhausted" with no heal, which made
        # this a replacement of the death and not of its cause: the marked
        # damage survived, 143.2.a is a continuous check, and the unit died
        # again on the spot. Read that way Zhonya's answered targeted removal
        # and did nearly nothing against damage. `data/errata.json` supersedes
        # it with "Heal that unit, exhaust it, and recall it", so the damage
        # goes and the unit actually survives a lethal hit.
        state.perms[perm, P_DMG] = 0
        state.set_location(perm, base_loc(ctrl_now))
        row[P_READY] = 0
        return
    if not state.has_flag(perm, F_NON_UNIT):
        state.unit_died_ply[int(row[P_CTRL])] = int(state.ply)
    _queue_mark(state, perm, TR_MARKED_DIES)
    # "When ANOTHER friendly unit dies" -- a watcher trigger, so it fires for
    # everyone else the controller has, and never for the unit that died.
    # Queued before the death is carried out, the same instant a [Deathknell]
    # is (808.1.d.2), so both see the same board.
    if not state.has_flag(perm, F_NON_UNIT):
        from rl.engine.chain import fire_watchers
        # Fired for BOTH seats, because "when an enemy unit dies" (Pyke -
        # Returned) is the same event seen from the other side. `fire_watchers`
        # walks one seat's permanents and each watcher states which side it
        # wants through `subject_enemy`, so the opposite seat's pass turns up
        # nothing unless a card asked for it.
        for who in (int(row[P_CTRL]), 1 - int(row[P_CTRL])):
            fire_watchers(state, table, who, TR_OTHER_DIES,
                          subj=perm, exclude=perm)
        killer, by_spell = int(KILLER[0]), bool(KILLER[1])
        if killer >= 0:
            fire_watchers(state, table, killer, TR_YOU_KILL, subj=perm,
                          exclude=perm, by_spell=by_spell)
            from rl.engine.effects import TR_KILL_FROM_TRASH
            from rl.engine.state import trash_src
            for k in range(int(state.n_trash[killer])):
                tc = int(state.trash[killer, k])
                if any(a.trigger == TR_KILL_FROM_TRASH
                       and (by_spell or not a.subject_by_spell)
                       for a in abilities_for(table, tc)):
                    chain_queue(state, TR_KILL_FROM_TRASH, trash_src(killer),
                                -1, subj=tc, who=killer)

    # 136.2.c -- an Equipment's "[Deathknell]" is the UNIT's ("When I die"),
    # but `queue_leaves_board` detaches the gear a moment from now (719.5), so
    # by the time the trigger is placed the unit no longer carries it. Each
    # such gear therefore queues its own Death trigger naming itself as the
    # subject, and `chain.fire` reads the ability off that row.
    own_death = not state.is_attached(perm) and any(
        a.trigger == TR_DEATH for a in abilities_for(table, int(row[P_CARD])))
    gear_deaths = [g for g in state.attachments(perm)
                   if any(a.trigger == TR_DEATH for a in equip_abilities_for(
                       table, int(state.perms[g, P_CARD])))]
    if own_death or gear_deaths:
        loc, ctrl = int(row[P_LOC]), int(row[P_CTRL])
        others = [i for i in range(state.n_perms)
                  if i != perm and int(state.perms[i, P_CTRL]) == ctrl
                  and int(state.perms[i, P_LOC]) == loc
                  and (state.perms[i, P_ALIVE] == 1 or i in batch)
                  and not state.has_flag(i, F_NON_UNIT)]
        if not others:
            row[P_FLAGS] |= F_DIED_ALONE
        # 740.2 -- "I'm Mighty while I have 5+ Might", read here because the
        # question a Deathknell asks is past tense and the row's modifiers do
        # not survive to resolution. `might` rather than the printed value:
        # a unit is Mighty because of a buff just as much as because of print.
        if might(state, table, perm) >= 5:
            row[P_FLAGS] |= F_DIED_MIGHTY
        if state.showdown_combat and in_combat(state, perm):
            row[P_FLAGS] |= F_DIED_IN_COMBAT
        # Karthus - Eternal: "Your [Deathknell] effects trigger an additional
        # time" -- once more per Karthus the dying card's controller has.
        # A Karthus dying in the SAME batch still counts: a passive is live at
        # the instant the trigger is created, and these deaths are simultaneous
        # (RiftJudge #10438, #10530), the same reading `others` above uses.
        times = 1 + sum(
            1 for k in range(state.n_perms)
            if k != perm and (state.perms[k, P_ALIVE] == 1 or k in batch)
            and int(state.perms[k, P_CTRL]) == ctrl
            and table.names[int(state.perms[k, P_CARD])] in DEATHKNELL_DOUBLERS)
        for _ in range(times):
            if own_death:
                chain_queue(state, TR_DEATH, perm, loc)
            for g in gear_deaths:
                chain_queue(state, TR_DEATH, perm, loc, subj=int(g))
    # A death IS a leaving, so this fires alongside [Deathknell] rather than
    # instead of it. 383.3.d lets the controller order their own simultaneous
    # triggers, which the queue already handles.
    queue_leaves_board(state, table, perm)
    row[P_ALIVE] = 0
    # 108.2 -- each player has their OWN trash, and a dead card goes to its
    # owner's. Reading `P_CTRL` here would launder a unit dug out of the
    # opponent's trash (Kharox) into the digger's pile.
    seat, card = int(row[P_OWNER]), int(row[P_CARD])
    # 185.3 -- a token that leaves the board ceases to exist; it does not go to
    # a trash, hand or deck. `OP_RETURN_TO_HAND` had this right for bounce and
    # this path did not, so every Sprite that died has been silently padding
    # its controller's trash. It stayed invisible because nothing reads the
    # trash yet -- but Rhasa the Sunderer costs less per card in it, and Fizz
    # and Spectral Matron replay from it, so a padded trash is a real number
    # being wrong rather than a cosmetic one.
    if table.is_token(card):
        return
    if int(state.riches_on[seat]):
        state.banish_card(seat, card)          # Endless Riches
        return
    n = int(state.n_trash[seat])
    assert n < state.trash.shape[1], "trash overflow"
    state.trash[seat, n] = card
    state.n_trash[seat] = n + 1
    # 383.2.c.1 -- a trash-zone trigger is evaluated for a card that ENTERS the
    # trash as its condition is met: "Immortal Phoenix ... triggers ... even if
    # the unit you killed with a spell was that Immortal Phoenix" (RiftJudge
    # #9374). The scan in the killer block above only saw cards already there.
    killer, by_spell = int(KILLER[0]), bool(KILLER[1])
    if killer == seat:
        from rl.engine.effects import TR_KILL_FROM_TRASH
        from rl.engine.state import trash_src
        if any(a.trigger == TR_KILL_FROM_TRASH
               and (by_spell or not a.subject_by_spell)
               for a in abilities_for(table, card)):
            chain_queue(state, TR_KILL_FROM_TRASH, trash_src(killer), -1,
                        subj=card, who=killer)


# ---------------------------------------------------------------------------
# Move declaration (PLAN.md §1.3.a)
# ---------------------------------------------------------------------------
# Factored, never enumerated as subsets: choose a destination, then add units
# one at a time, then COMMIT. With N awake units the raw space is 2^N per
# destination; this way each decision point offers at most N+2 candidates.

def permanent_enters_ready(state: GameState, table: CardTable, seat: int,
                           card: int, is_unit: bool) -> bool:
    """Does a permanent enter READY as it is played?

    359.2.c/d are opposite defaults -- a unit enters exhausted, a gear ready --
    and each has printed exceptions in the other direction. A unit's live in
    `ENTERS_READY_IF` ("I enter ready if..."). A gear's is the flat
    "This enters exhausted." (Scryer's Bloom, Platewyrm Egg, Honeyfruit), a
    rate limit on the resource and trick gear: they cannot be used the turn
    they land.

    One function for every play site, because there are four of them (hand,
    Facedown, look buffer, trash dig) and each wrote `not is_unit or ...`
    inline -- so a gear exception added at one would have been missing at the
    other three.
    """
    if not is_unit:
        return table.names[card] not in ENTERS_EXHAUSTED
    return (_printed_enters_ready(state, table, seat, card)
            or granted_enters_ready(state, table, seat, card))


def _printed_enters_ready(state: GameState, table: CardTable, seat: int,
                  card: int) -> bool:
    """Does this card print its own exception to 359.2.c (enter exhausted)?

    Checked as the unit is played, which is when the card asks. Xin Zhao counts
    the board at that instant -- "two or more OTHER units", and he is not on it
    yet, so every friendly unit at the base is an "other" one.
    """
    kind = ENTERS_READY_IF.get(table.names[card])
    if kind is None:
        return False
    if kind == ER_TWO_OTHERS_AT_BASE:
        return int(state.units_at(base_loc(seat), seat).size) >= 2
    if kind == ER_DIED_IN_BEGINNING:
        return bool(state.died_in_beginning[seat])
    if kind == ER_ALWAYS:
        return True
    if kind == ER_OPP_STUNNED:
        return opp_controls_stunned(state, seat)
    if kind == ER_SELF_NOT_NEAR_VICTORY:
        return int(state.points[seat]) < state.victory_score - 3
    if kind == ER_OPP_NEAR_VICTORY:
        return any(int(state.points[s]) >= state.victory_score - 3
                   for s in range(N_SEATS) if s != seat)
    if kind == ER_SAME_NAME_IN_TRASH:
        n = int(state.n_trash[seat])
        return bool(np.count_nonzero(state.trash[seat, :n] == card))
    if kind == ER_OPP_CONTROLS_BF:
        return any(int(c) >= 0 and int(c) != seat for c in state.bf_ctrl)
    if kind == ER_UNIT_DIED_THIS_TURN:
        return any(int(p) == int(state.ply) for p in state.unit_died_ply)
    if kind == ER_HAND_AT_MOST_2:
        return int(state.n_hand[seat]) <= 2
    if kind == ER_ANOTHER_MECH:
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) == seat
                   and "Mech" in perm_tags(state, table, i)
                   for i in range(state.n_perms))
    if kind == ER_ANOTHER_DRAGON:
        # He is not on the board yet, so every Dragon already there counts.
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) == seat
                   and "Dragon" in perm_tags(state, table, i)
                   for i in range(state.n_perms))
    if kind == ER_LEVEL_3:
        # "[Level 3][>] I have +1 Might AND ENTER READY" -- the same 3+ XP
        # gate `COND_LEVEL` reads for the Might half, asked here because
        # entering ready is a replacement decided as the unit is played
        # (359.2.c) rather than a continuous effect a static can express.
        return int(state.xp[seat]) >= 3
    return False


def granted_enters_ready(state: GameState, table: CardTable, seat: int,
                         card: int) -> bool:
    """Does something ELSE on the board make this unit enter ready?

    Magma Wurm -- "Other friendly units enter ready." -- and Renata Glasc,
    Industrialist -- "Your tokens enter ready." 369.3 makes both replacements
    of the way a unit enters, so they are asked at the same instant the unit's
    own printed exception is, and by every path a unit enters by. "Other" costs
    nothing to check: the unit being asked about is not on the board yet.
    Units only -- a gear token played "exhausted" by the effect that makes it
    keeps its own instruction.
    """
    is_token = bool(table.is_token(card))
    # Confront -- a promise made this turn, held on the player.
    if int(state.next_unit_ready_ply[seat]) == int(state.ply):
        return True              # Sun Disc's promise, spent by `chain.card_played`
    if int(state.units_enter_ready_turn[seat]) == int(state.ply):
        return True
    for i in range(state.n_perms):
        r = state.perms[i]
        if r[P_ALIVE] != 1 or int(r[P_CTRL]) != seat:
            continue
        for st in row_statics(state, table, i):
            if st.kind != ST_ENTERS_READY:
                continue
            if st.scope_token and not is_token:
                continue
            return True
    # ...and the legend's ("[Level 11] > your units enter ready" -- Master Yi -
    # Wuju Master), which is a static with no permanent to walk to.
    for who, st in legend_statics(state, table):
        if who != seat or st.kind != ST_ENTERS_READY:
            continue
        if st.scope_token and not is_token:
            continue
        if not static_applies(state, st, who, -1, -1, table):
            continue
        return True
    return False


def played_bits(table: CardTable, card: int) -> int:
    """Which of Swain's kinds this card counts as, when played.

    **A card with more than one type counts for EVERY one of them.** A gear
    unit is both a gear and a unit for Swain's "a non-token unit, a non-token
    gear, and a spell this turn", so this ORs the bits rather than picking one.
    Written as an if/elif first, which would have quietly counted such a card
    once and made the trio a card harder to complete than it is.

    No card in the current export carries two types, so nothing exercises this
    today -- which is exactly why it is worth stating: the chain was wrong in
    principle and would have stayed wrong invisibly until the set that prints
    one landed.
    """
    bits = 0
    if table.is_type(card, "Unit"):
        bits |= PT_UNIT
    if table.is_type(card, "Gear"):
        bits |= PT_GEAR
    if table.is_type(card, "Spell"):
        bits |= PT_SPELL
    return bits


def record_effect_play(state: GameState, table: CardTable, seat: int,
                       card: int, loc: int, owner: int,
                       free_costs: bool = False) -> int:
    """PLAY a unit that an effect put onto the board, and return its row.

    349 makes "play a unit from your trash" (Spectral Matron, Last Rites) and
    "its owner plays it" (a blink) plays like any other. This used to add the
    permanent and stop there, so such a unit was never counted for [Legion],
    never seen by "when you play a unit" watchers, and ignored its own "I enter
    ready" -- Eager Drakehound replayed from the trash entered exhausted.
    Everything a hand play does after paying, in the same order, except the
    things only a hand play has (Accelerate, the destination choice).
    """
    from rl.engine import chain as _chain
    from rl.engine.effects import TR_PLAY_ME as _TR_PM
    is_token = bool(table.is_token(card))
    legion = bool(state.cards_played[seat])
    if not is_token:
        state.cards_played[seat] += 1
        state.played_types[seat] |= played_bits(table, card)
        _chain.card_played(state, table, seat, card, completed=False)
        # "When you play a card from anywhere other than your hand" (Yordle,
        # Kennen - Heart of the Tempest). This function IS the non-hand play
        # path -- a trash, a deck, a look buffer -- and 185 keeps a token out
        # of it, since a token is not a card.
        from rl.engine.effects import TR_PLAY_NONHAND
        _chain.fire_watchers(state, table, seat, TR_PLAY_NONHAND)
    is_unit = bool(table.is_type(card, "Unit"))
    loc = baron_pit_entry(state, table, card, loc)          # Baron Nashor
    src = state.add_permanent(
        card, seat, loc,
        ready=permanent_enters_ready(state, table, seat, card, is_unit),
        is_unit=is_unit, owner=owner)
    if legion:
        state.perms[src, P_FLAGS] |= F_LEGION
    if not is_token:
        # 419.4.a -- a permanent's play completes as it enters, so "your Nth
        # card" watchers fire once it is on the board and can see itself
        # (a second Astral Heron played to a battlefield, RiftJudge #11683).
        _chain.fire_nth_card(state, table, seat, card)
    _chain.fire_play_unit(state, table, seat, card, src)
    # 356.4.f.1 -- an optional additional cost counts as PAID once the player
    # decides to pay it, "no matter how much the player actually paid". A play
    # that ignores the card's costs reduces that cost to 0, so the decision is
    # free and the clause it buys applies: Bone Skewer's "ignoring any and all
    # costs" still draws its owner a card off Clockwork Keeper (RiftJudge
    # #10266). Only the printed rune/energy costs in PLAY_COSTS ride this --
    # an optional cost with a choice in it (kill a friendly gear) is a decision
    # the play path offers on its own.
    if free_costs and not is_token:
        from rl.engine.effects import PLAY_COSTS
        if table.names[card] in PLAY_COSTS:
            state.perms[src, P_FLAGS] |= F_PAID_ADDITIONAL
    if _chain.has_trigger(table, card, _TR_PM):
        _chain.queue(state, _TR_PM, src, loc)
    return src


def cant_move_to_base(state: GameState, table: CardTable, perm: int) -> bool:
    """Does any static forbid `perm` from MOVING to a base?

    Determined Sentry ("I can't move to base") and Minotaur Reckoner ("Units
    can't move to base"). A Move only -- 456.1 makes a Recall not a Move, so
    the combat-loss recall and every "recall" effect still send the unit home.
    """
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in row_statics(state, table, i):
            if st.kind == ST_NO_MOVE_TO_BASE and static_reaches(
                    state, table, st, i, perm):
                return True
    # ...and the GROUND it is standing on (Vilemaw's Lair): "units can't move
    # from here to base" is printed on the battlefield, which has no row for
    # the walk above to reach.
    for st in bf_statics_for(state, table, perm):
        if st.kind == ST_NO_MOVE_TO_BASE:
            return True
    return False


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
    if is_battlefield(dst_loc) and not state.bf_present(bf_index(dst_loc)):
        return False
    if not is_battlefield(dst_loc) and cant_move_to_base(state, table, perm):
        return False
    if is_battlefield(src) and is_battlefield(dst_loc):
        # 187.9 -- the Baron Pit: "Units can move here from anywhere."
        if moves_from_anywhere(state, table, bf_index(dst_loc)):
            return True
        return (not cfg.lateral_movement_needs_ganking
                or perm_kw(state, table, perm, "Ganking"))
    return True


def movable_units(state: GameState, table: CardTable, cfg: Config,
                  dst_loc: int) -> list[int]:
    """Rows the turn player could still add to a declaration headed to `dst_loc`."""
    return [i for i in range(state.n_perms)
            if not (state.decl_mask >> i) & 1
            and can_move(state, table, cfg, i, dst_loc)]


def moves_from_anywhere(state: GameState, table: CardTable, i: int) -> bool:
    from rl.engine.effects import BF_MOVE_FROM_ANYWHERE
    c = int(state.bf_card[i])
    return c >= 0 and table.names[c] in BF_MOVE_FROM_ANYWHERE


def baron_pit_entry(state: GameState, table: CardTable, card: int, loc: int) -> int:
    """Baron Nashor (369.3): "As you play me, add the Baron Pit battlefield token
    to the board if it's not there already. If you do, I enter there." Returns
    where the played card actually enters."""
    from rl.engine.effects import BARON_PIT_MAKERS
    if table.names[card] not in BARON_PIT_MAKERS:
        return loc
    if any(int(state.bf_card[i]) >= 0 and table.names[int(state.bf_card[i])]
           == "Baron Pit" for i in state.live_bfs()):
        return loc                                  # already there: no entry
    slot = next((i for i in range(N_BF_BASE, N_BF) if int(state.bf_card[i]) < 0), -1)
    if slot < 0:
        return loc
    state.bf_card[slot] = table.id_of("Baron Pit")
    state.bf_ctrl[slot] = -1
    state.bf_contested[slot] = 0
    state.bf_contester[slot] = -1
    state.bf_scored[:, slot] = 0
    return bf_loc(slot)


def move_destinations(state: GameState, table: CardTable,
                      cfg: Config) -> list[int]:
    """Battlefields the turn player could declare a Move to."""
    return [bf_loc(i) for i in state.live_bfs()
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


def scan_might_transitions(state: GameState, table: CardTable,
                           cfg=None) -> None:
    """Fire "becomes [Mighty]" watchers and Renekton's 10-Might empower.

    Read at settle time, so a Might that rises and falls again inside one
    resolution is not seen -- the board between actions is what is compared.
    """
    from rl.engine.chain import fire_watchers
    from rl.engine.effects import (EMPOWER_AT_MIGHT, TR_BECOME_MIGHTY)
    from rl.engine.state import F_EMPOWERED, F_MIGHT_SEEN, F_WAS_MIGHTY
    from rl.engine.effects import legend_abilities_for
    # ...and a LEGEND is a watcher too (Fiora - Grand Duelist: "when one of your
    # units becomes [Mighty], you may exhaust me to channel 1 rune exhausted").
    # `fire_watchers` has always fired legend watchers; this gate did not know
    # they existed, so with no permanent watching, the scan returned early and
    # her card did nothing at all (RiftJudge #6308).
    watching = any(
        state.perms[w, P_ALIVE] == 1
        and any(a.trigger == TR_BECOME_MIGHTY
                for a in row_abilities(state, table, w))
        for w in range(state.n_perms)) or any(
        int(state.legend[_s]) >= 0
        and any(a.trigger == TR_BECOME_MIGHTY
                for a in legend_abilities_for(table, int(state.legend[_s])))
        for _s in range(N_SEATS))
    if not watching and not any(
            state.perms[i, P_ALIVE] == 1
            and table.names[int(state.perms[i, P_CARD])] in EMPOWER_AT_MIGHT
            for i in range(state.n_perms)):
        return
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or not table.is_type(int(row[P_CARD]), "Unit"):
            continue
        m = might(state, table, i)
        need = EMPOWER_AT_MIGHT.get(table.names[int(row[P_CARD])])
        hi_was = int(state.might_hi[i])
        if need is not None:
            state.might_hi[i] = int(m >= need)
        if (need is not None and m >= need and hi_was == 0
                and not int(row[P_FLAGS]) & F_EMPOWERED):
            if cfg is not None:
                from rl.engine import resolve as _rsv
                from rl.engine.effects import CardSpec, Op, OP_EMPOWER, SPEED_MAIN
                _rsv.resolve(state, table, cfg,
                             CardSpec(speed=SPEED_MAIN, ops=(Op(OP_EMPOWER),)),
                             int(row[P_CTRL]), [], -1, False, source=i)
        now = m >= 5
        flags = int(row[P_FLAGS])
        if watching and flags & F_MIGHT_SEEN and now and not flags & F_WAS_MIGHTY:
            fire_watchers(state, table, int(row[P_CTRL]), TR_BECOME_MIGHTY, subj=i)
        flags |= F_MIGHT_SEEN
        flags = (flags | F_WAS_MIGHTY) if now else (flags & ~F_WAS_MIGHTY)
        row[P_FLAGS] = flags


def perm_tags(state: GameState, table: CardTable, perm: int) -> frozenset:
    """A permanent's tags: printed, plus granted (Ivern - Friend to All) and
    band-granted by its Equipment (Experimental Hexplate)."""
    from rl.engine.effects import EQUIP_GRANTS_TAG, GRANTABLE_TAGS
    base = table.tags[state.eff_card(perm)]
    extra = set()
    g = int(state.tag_grant[perm])
    if g >= 0:
        extra.add(GRANTABLE_TAGS[g])
    if state.n_attached:
        for a in state.attachments(perm):
            t = EQUIP_GRANTS_TAG.get(table.names[int(state.perms[a, P_CARD])])
            if t:
                extra.add(t)
    return base | extra if extra else base


def queue_move_trigger(state: GameState, table: CardTable, perm: int,
                       from_loc: int, to_loc: int = -1,
                       seen: set | None = None) -> None:
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
    # 718.2 -- an Attached card's own text is Inactive, and 718.5.c says it
    # never moves separately anyway: it is dragged by `set_location`, which
    # is not a Move it can react to.
    # Counted for every move, whatever the unit prints (Kayn has no trigger).
    if int(state.move_ply[perm]) != int(state.ply):
        state.move_ply[perm] = int(state.ply)
        state.move_count[perm] = 0
    state.move_count[perm] += 1
    state.move_from[perm], state.move_to[perm] = int(from_loc), int(to_loc)
    _queue_move_watchers(state, table, perm, from_loc, to_loc, seen)
    queue_bf_move_trigger(state, table, perm, from_loc, to_loc)
    moves = [a for a in row_abilities(state, table, perm)
             if a.trigger == TR_MOVE
             # "The THIRD time I move in a turn" (Yasuo - Windrider).
             and (not a.subject_nth
                  or a.subject_nth == int(state.move_count[perm]))]
    if not moves:
        return
    # "The FIRST time I move each turn" (Miss Fortune - Captain).
    #
    # **`once_each_turn` was enforced in `fire_watchers` and nowhere else**, so
    # a trigger queued from a direct site like this one ignored it entirely --
    # and with [Ganking] on the same card that made her a free untapper on
    # every hop instead of once a turn.
    #
    # Stamped HERE and not in the drain loop, because `fire_watchers` already
    # stamps at queue time: a second gate downstream would see its own stamp
    # and silently suppress every watcher that uses the flag. One stamp per
    # queueing site is the invariant; this is the site that was missing one.
    if any(a.once_each_turn for a in moves):
        if int(state.once_used[perm]) == int(state.ply):
            return
        state.once_used[perm] = int(state.ply)
    chain_queue(state, TR_MOVE, int(perm), int(from_loc), ctx2=int(to_loc))


def queue_bf_move_trigger(state: GameState, table: CardTable, perm: int,
                          from_loc: int, to_loc: int) -> None:
    """"When a unit moves from here" printed on the GROUND (Back-Alley Bar).

    Fired for the moving unit's controller and from the battlefield it LEFT,
    which is what "from here" names. Separate from `queue_move_trigger` so the
    unit's own move triggers and the ground's stay independent -- a unit with
    no text still leaves a battlefield that cares.
    """
    if not is_battlefield(from_loc):
        return
    _queue_bf_trigger(state, table, TR_MOVE, bf_index(from_loc),
                      int(state.perms[perm, P_CTRL]), subj=int(perm),
                      ctx2=int(to_loc))


def _queue_move_watchers(state: GameState, table: CardTable, perm: int,
                         from_loc: int, to_loc: int,
                         seen: set | None) -> None:
    """TR_UNIT_MOVES -- other permanents watching this Move. `seen` holds the
    watchers already fired by the same Move of several units."""
    from rl.engine.chain import queue as chain_queue
    mover = int(state.perms[perm, P_CTRL])
    for w in range(state.n_perms):
        if w == perm or state.perms[w, P_ALIVE] != 1:
            continue
        if seen is not None and w in seen:
            continue
        here = int(state.perms[w, P_LOC])
        enemy = mover != int(state.perms[w, P_CTRL])
        for ab in row_abilities(state, table, w):
            if ab.trigger != TR_UNIT_MOVES or bool(ab.subject_enemy) != enemy:
                continue
            if ab.move_from_my_loc and from_loc != here:
                continue
            if ab.move_to_other_bf and (not is_battlefield(to_loc)
                                        or to_loc == here):
                continue
            chain_queue(state, TR_UNIT_MOVES, w, int(from_loc),
                        subj=int(perm), ctx2=int(to_loc))
            if seen is not None:
                seen.add(w)
            break


def move_tax(state: GameState, table: CardTable, seat: int, dst: int) -> int:
    """[A] owed per unit beyond the first moving to `dst` together."""
    from rl.engine.effects import MOVE_TAXERS
    return sum(1 for i in range(state.n_perms)
               if state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) != seat
               and int(state.perms[i, P_LOC]) == dst
               and table.names[int(state.perms[i, P_CARD])] in MOVE_TAXERS)


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
    tax = move_tax(state, table, int(state.active), dst) * (len(moved) - 1)
    if tax > 0:
        from rl.engine.cost import pay_wild_power, plan_wild_power
        _rc = plan_wild_power(state, int(state.active), tax)
        assert _rc is not None, "an unpayable Mageseeker tax was declared"
        pay_wild_power(state, int(state.active), tax, _rc)
    seen: set = set(int(i) for i in moved)
    for i in moved:
        row = state.perms[i]
        queue_move_trigger(state, table, i, int(row[P_LOC]), dst, seen)
        state.set_location(i, dst)
        row[P_READY] = 0          # units arrive exhausted
        row[P_ARRIVED] = state.ply
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
    state.set_location(perm, base_loc(int(row[P_CTRL])))
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
    for i in state.live_bfs():
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
    for i in state.live_bfs():
        if int(state.bf_contester[i]) < 0:
            continue
        a, b = state.seats_at(bf_loc(i))
        if a and b:
            return i, True
    for i in state.live_bfs():
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
    # 323.1 -- the first task of every Cleanup is the win check. Points gained
    # outside Hold and Conquer (Ahri - Alluring, Shen, Power Nexus) were never
    # checked, so a player could sit on 8 until the next Hold (RiftJudge #11417).
    if state.winner < 0:
        _w = state.check_winner(cfg.victory_score)
        if _w >= 0:
            state.winner = _w
            return log
    # 143.2.a board-wide. A Cleanup follows every board change, which makes it
    # the one place that catches a unit becoming lethally damaged because some
    # OTHER unit changed -- a static's source dying or moving away, or Elder
    # Dragon arriving to make damage already marked lethal. Nothing touched
    # the unit, so no per-unit check would have fired.
    #
    # 323.4/323.5 (and 323.7's recall) are not gated on an Open State the way
    # 323.6 onward are. Elder Dragon shows why: its own play trigger closes
    # the State, and the kill must still happen before anyone gets priority
    # to answer that trigger (RiftJudge #12102).
    dead = enforce_lethal(state, table)
    if dead:
        log["lethal_static"] = dead
    recall_stray_gear(state, table)
    if not state.is_open:
        return log

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
        elif state.showdown_combat and state.desig.any():
            # 323.2.a -- a unit that arrived after the designations were handed
            # out "inherits its controller's existing designation during the
            # next Cleanup", which is this one. So its "when I attack" fires
            # now, on a Combat that is still ongoing (RiftJudge #12564: Ava
            # Achiever plays Kennen into her own combat and he attacks).
            # `desig` is what keeps the units already fighting out of it --
            # and `desig.any()` keeps a hand-built Showdown (a test fixture
            # that sets `showdown_bf` without opening one) from having roles
            # invented for units that were never designated in the first place.
            #
            # 323.2.c FIRST, in the same step: a designated unit that is no
            # longer AT the Combat's battlefield "loses those designations now",
            # so if it comes back it is designated afresh by 323.2.a above and
            # its "when I attack/defend" fires a second time (RiftJudge #6364 --
            # Yasuo Flashed home and walked back in with Zenith Blade). FAQ
            # #6656 answers the mirror of this with "only the first time a unit
            # gains the designation", which is a rule the text does not have;
            # 323.2.a/c are what settle it, and #6656 is in `rejected.json`.
            _sd_loc = bf_loc(int(state.showdown_bf))
            for _u in range(state.n_perms):
                if int(state.desig[_u]) and (
                        state.perms[_u, P_ALIVE] != 1
                        or int(state.perms[_u, P_LOC]) != _sd_loc):
                    state.desig[_u] = 0
            from rl.engine.chain import new_step as _new_step
            _new_step(state)
            _designate(state, table, int(state.showdown_bf), int(state.attacker))
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
    # ...but not while a resolution is suspended waiting for a choice: Baited
    # Hook killing your last unit at a battlefield must not cost you control
    # before the unit it finds can be played there (RiftJudge #10517, #11963).
    # Only this half is held back; staging and the rest of the Cleanup are not.
    if not _decision_pending(state):
        for i in state.live_bfs():
            _release_control(state, i)

    # 323.11, and it runs AFTER the release above so that 323.11.a sees the
    # battlefields that just went uncontrolled. It decides both which Showdowns
    # are staged (323.8/323.9) and who the Attacker will be (464.2.c.1), so it
    # has to be current at every battlefield before either is read.
    for i in state.live_bfs():
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


def _decision_pending(state: GameState) -> bool:
    """Is a resolution suspended waiting for a player's choice?

    The Chain can be empty while a card is still resolving -- a look, a
    "play a unit from among them", an ordering -- and the game is not Open
    then. Mirrors `actions._mid_decision` without importing it (actions
    imports this module).
    """
    return bool(
        state.pend_look >= 0 or state.pend_hand_play >= 0 or state.pend_slot >= 0
        or state.pend_may >= 0 or state.pend_order >= 0 or state.pend_cull >= 0
        or state.pend_discard >= 0 or state.pend_grave >= 0
        or state.pend_split >= 0 or state.pend_amount >= 0 or state.pend_name >= 0
        or state.pend_ask >= 0 or state.pend_altar >= 0 or state.pend_kill_play >= 0
        or state.pend_dmg >= 0
        or state.pend_show_off >= 0
        or int(state.pend_double[0]) >= 0 or int(state.pend_reveal[0]) >= 0
        # `resume_kind` is 0 when nothing is suspended, not -1.
        or bool(int(state.resume_kind)))


def recall_stray_gear(state: GameState, table: CardTable) -> list[int]:
    """323.7 / 457.1 -- Recall every unattached non-Unit Gear at a battlefield.

    A gear reaches a battlefield only by riding a unit there, so it is left
    behind whenever that link breaks: its unit dies, is banished or bounced,
    or the gear is unattached (435.4.a). Nothing recalled it, and a Long Sword
    dropped by a Temporal Breach stood at the battlefield for the rest of the
    game (RiftJudge #12217). Unlike most of a Cleanup this step is not gated
    on an Open State, and a Recall is not a Move (456.1), so nothing triggers.

    **[Deploy] gear is exempt.** 149.3's sweep is the corrective half of
    149.2's "Gear can only be played to a player's Base **unless an effect
    specifies otherwise**" -- it exists to clean up gear that has no business
    standing on ground. A [Deploy] card is the effect that specifies
    otherwise, so a battlefield is exactly where it belongs and sweeping it
    home would undo the keyword on the very next Cleanup. Without this the
    whole keyword was silently dead: the gear never stayed where it was
    played, and "when an opponent holds here, kill this" could never fire
    because it was never there when they held.
    """
    moved = []
    for i in range(state.n_perms):
        if (state.perms[i, P_ALIVE] == 1 and not state.is_attached(i)
                and is_battlefield(int(state.perms[i, P_LOC]))):
            card = int(state.perms[i, P_CARD])
            if table.has(card, "Deploy"):
                continue
            if table.is_type(card, "Gear") and not table.is_type(card, "Unit"):
                state.set_location(i, base_loc(int(state.perms[i, P_CTRL])))
                moved.append(i)
    return moved


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

    state.bf_prev_ctrl[i] = prev
    state.bf_ctrl[i] = holder
    _clear_foreign_hidden(state, i, holder)
    state.bf_conquered_ply[holder, i] = int(state.ply)
    if not state.bf_scored[holder, i]:
        state.bf_scored[holder, i] = 1
        denied = False
        if _final_point_blocked(state, cfg, holder):
            # 471.1.b -- the Final Point cannot be taken by Conquer unless the
            # player has Scored EVERY Battlefield this turn. Otherwise they draw
            # a card instead of scoring. You cannot win off a single lucky
            # conquer; the last point demands the whole board.
            #
            # **What is denied is the POINT, not the Conquer.** Control changed
            # hands, so "when I conquer" still triggers -- and 471.1.a.1 exempts
            # what those triggers then score, which is how Trinity Force takes
            # the eighth point off a Conquer that scored nothing itself. This
            # used to `return` here, which dropped every conquer trigger on the
            # board for the rest of that Combat.
            from rl.engine import phases
            phases.draw_for(state, holder, 1)
            scored.append((holder, "final_point_denied"))
            denied = True
        elif points_blocked(state, table, holder) or score_blocked_here(
                state, table, holder, i):
            scored.append((holder, "blocked"))   # Tianna, or the Monument
        elif early_score_draws(state, table):
            from rl.engine import phases
            phases.draw_for(state, holder, 1)
            scored.append((holder, "otterpus"))
        else:
            state.points[holder] += POINTS_PER_CONQUER
            if state.winner < 0:            # an OP_WIN stands
                state.winner = state.check_winner(cfg.victory_score)
            scored.append((holder, "conquer"))
        from rl.engine.chain import fire_watchers as _fire_watchers
        if not denied:                      # nobody scored, so nobody watched
            _fire_watchers(state, table, 1 - holder, TR_OPPONENT_SCORES)
        # "When I conquer" fires for the units that took the ground.
        from rl.engine.chain import queue as chain_queue
        from rl.engine.effects import TR_CONQUER, EXTRA_CONQUER_HERE
        # Red Brambleback -- each one here makes every conquer effect for
        # conquering here trigger once more.
        times = 1 + sum(1 for u in state.units_at(loc, holder)
                        if table.names[int(state.perms[u, P_CARD])]
                        in EXTRA_CONQUER_HERE)
        for u in state.units_at(loc, holder):
            state.conquer_ply[u] = int(state.ply)
            _queue_mark(state, int(u), TR_MARKED_CONQUERS)
        for u in state.units_at(loc, holder):
            # The ROW's abilities (718.3): an attached Equipment's "When I
            # conquer" (Doran's Ring, Warmog's Armor, Cull) is the unit's.
            conq = [a for a in row_abilities(state, table, int(u))
                    if a.trigger == TR_CONQUER]
            if not conq:
                continue
            # "The first time I conquer each turn" (Lucian - Merciless) --
            # stamped at the queueing site, like the move and win-combat ones.
            if all(a.once_each_turn for a in conq):
                if int(state.once_used[u]) == int(state.ply):
                    continue
                state.once_used[u] = int(state.ply)
            for _ in range(times):
                chain_queue(state, TR_CONQUER, int(u), loc)
        from rl.engine.effects import TR_HOLD as _TRH
        for u in state.units_at(loc, holder):
            # Skyfall of Areion: its unit's hold effects are conquer effects.
            if any(table.names[int(state.perms[g, P_CARD])] in HOLD_CONQUER_SWAP
                   for g in state.attachments(int(u))) and any(
                    a.trigger == _TRH for a in row_abilities(state, table, int(u))):
                chain_queue(state, _TRH, int(u), loc)
        # ...and for cards acting from the conqueror's TRASH ("When you
        # conquer, you may discard 1 to return this", Super Mega Death Rocket!).
        from rl.engine.effects import TR_CONQUER_FROM_TRASH
        from rl.engine.state import trash_src
        for k in range(int(state.n_trash[holder])):
            tc = int(state.trash[holder, k])
            if any(a.trigger == TR_CONQUER_FROM_TRASH
                   for a in abilities_for(table, tc)):
                chain_queue(state, TR_CONQUER_FROM_TRASH, trash_src(holder), -1,
                            subj=tc, who=holder)
        # ...and for the BATTLEFIELD itself. "When you conquer here" is printed
        # on the ground, not on a unit, so it fires whether or not anything
        # standing there cares -- and it fires exactly once, where the unit
        # version fires once per unit.
        for _ in range(times):
            _queue_bf_trigger(state, table, TR_CONQUER, i, holder)
        # ...and for the LEGEND, which conquers with its player and not with
        # any one unit, so it fires once however wide the board is.
        from rl.engine.chain import fire_legend
        for _ in range(times):
            fire_legend(state, table, holder, TR_CONQUER, loc)
    return scored


def _queue_bf_trigger(state: GameState, table: CardTable, trigger: int,
                      i: int, seat: int, subj: int = -1,
                      ctx2: int = -1) -> None:
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
    abils = [a for a in bf_abilities_for(table, card) if a.trigger == trigger]
    if not abils:
        return
    # "...for the first time each turn" (The Dreaming Tree). Stamped as it is
    # QUEUED, per player: Flash choosing two units there at once is still one
    # first time, one draw (RiftJudge #9241). `bf_first_use` is otherwise only
    # the ground's cost rules (Ornn's Forge), which this slot's card has none of.
    if all(a.once_each_turn for a in abils):
        if int(state.bf_first_use[seat, i]) == int(state.ply):
            return
        state.bf_first_use[seat, i] = int(state.ply)
    chain_queue(state, trigger, bf_src(i), bf_loc(i), subj=subj,
                ctx2=ctx2, who=seat)


def _final_point_blocked(state: GameState, cfg: Config, seat: int) -> bool:
    """Would this Conquer be the Final Point without having Scored everywhere?

    471.1.b: the restriction applies once a player is within one point of the
    Victory Score. 471.1.a.1 exempts every non-Conquer source, so Hold, spells
    and Burn Out points are unaffected -- only Conquer is gated.
    """
    if int(state.points[seat]) < cfg.victory_score - 1:
        return False
    return not all(state.bf_scored[seat, j] for j in state.live_bfs())


def _clear_foreign_hidden(state: GameState, i: int, holder: int) -> None:
    """466.5.c / 107.3.c -- only a Battlefield's controller may hide cards there.

    Every slot at the battlefield: Bandle Tree holds two, and control changing
    hands must not leave one of them behind.
    """
    for k in fd_slots(i):
        owner = int(state.fd_owner[k])
        if owner < 0 or owner == holder:
            continue
        card = int(state.fd_card[k])
        if int(state.riches_on[owner]):
            state.banish_card(owner, card)     # Endless Riches
        else:
            n = int(state.n_trash[owner])
            state.trash[owner, n] = card
            state.n_trash[owner] = n + 1
        state.fd_owner[k] = -1
        state.fd_card[k] = -1
        state.fd_ply[k] = -1


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
    # A later step than 464.2.b, so what the designations trigger goes on the
    # Chain ABOVE a showdown-begins trigger already queued (RiftJudge #10254).
    from rl.engine.chain import new_step as _new_step
    _new_step(state)
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
    if state.n_trig and not cfg.units_only:
        # A QUEUED trigger is one 320.1 puts on the Chain at the next Cleanup,
        # so the window it will create is real and the Combat may not run past
        # it -- `cleanup` says the same thing for the Neutral case. This is
        # where "when I attack" lives: `_designate` queues it as the Combat
        # opens, and without this the Damage Step ran first and every attack
        # trigger resolved on a battlefield whose fight was already over (Ava
        # Achiever played her unit into a finished combat -- RiftJudge #12564).
        # Nothing fires under `units_only`, so v0 has no window to open and
        # stays bit-identical -- the same carve-out `fire` itself makes.
        return True
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
        #
        # `SD_DAMAGE` on entry means the damage has already been dealt and the
        # Combat yielded for a decision taken inside it (Altar of Blood asking
        # whether to buy a death back). Resuming has to pick up at the
        # Resolution Step: dealing the damage a second time would kill the very
        # unit the player just paid to save.
        # `pend_dmg_bf >= 0` means the damage step is SUSPENDED part-way
        # through collecting a player's assignment, so re-enter it even though
        # `showdown_step` already says SD_DAMAGE. That flag is what tells
        # "damage dealt, yielded afterwards for Altar of Blood" apart from
        # "damage not dealt yet, yielded to ask who dies" -- and getting it
        # wrong would either skip the damage or deal it twice.
        if state.showdown_step != SD_DAMAGE or int(state.pend_dmg_bf) >= 0:
            log.setdefault("rounds", []).append(
                damage_step(state, table, cfg, bf))
            if int(state.pend_dmg) >= 0 or int(state.pend_altar) >= 0:
                return log
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
    # Read BEFORE the flag is cleared two lines down -- "a combat that I was
    # in" has to know which kind of Showdown this was.
    if state.showdown_combat and bf >= 0:
        queue_combat_ends(state, table, bf)
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
    state.desig[:] = 0                   # a fresh Showdown designates anew
    state.desig_seat[:] = 0
    # "When a showdown begins here" (Diana - Lunari) -- either kind.
    from rl.engine.chain import queue as _cq
    from rl.engine.effects import TR_SHOWDOWN_HERE
    for i in range(state.n_perms):
        if (state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_LOC]) == bf_loc(bf)
                and any(a.trigger == TR_SHOWDOWN_HERE
                        for a in row_abilities(state, table, i))):
            _cq(state, TR_SHOWDOWN_HERE, i, bf_loc(bf))
    if is_combat:
        # 464.2.b is step 1 and the designations are step 2, so what they
        # trigger is NOT simultaneous with a showdown-begins trigger and goes
        # on the Chain above it (RiftJudge #10254).
        from rl.engine.chain import new_step as _new_step
        _new_step(state)
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
    once_seen: set[int] = set()
    # Which seats ALREADY had a designated unit here when this pass began. A
    # Cleanup re-runs this for late arrivals (323.2.a), and the battlefield's
    # own "when you defend here" fires once for the PLAYER -- so it may only
    # fire for a seat that did not have a role a moment ago, or an ongoing
    # Combat would re-fire it at every Cleanup (Ravenbloom Conservatory drew
    # its controller ten cards in one combat).
    had_role = {seat for seat in range(N_SEATS)
                for u in state.units_at(loc, seat) if int(state.desig[u])}
    # A seat whose only designated unit has since walked out (323.2.c) has still
    # "defended here" once, so the ground must not pay it twice.
    had_role |= {seat for seat in range(N_SEATS) if int(state.desig_seat[seat])}
    for u in range(state.n_perms):
        if state.perms[u, P_ALIVE] != 1 or int(state.perms[u, P_LOC]) != loc:
            continue
        if state.has_flag(u, F_NON_UNIT):
            continue
        if state.desig[u]:
            continue          # already an Attacker or Defender in this Combat
        state.desig[u] = 1
        owner = int(state.perms[u, P_CTRL])
        alone = is_alone(state, u)
        role = ROLE_ATTACK if owner == attacker else ROLE_DEFEND
        # The watcher is any permanent its controller has anywhere -- Mask of
        # Foresight sits at a base and watches a battlefield.
        for w in range(state.n_perms):
            if state.perms[w, P_ALIVE] != 1 or int(state.perms[w, P_CTRL]) != owner:
                continue
            for ab in row_abilities(state, table, w):
                if ab.trigger != TR_ATTACK_OR_DEFEND:
                    continue
                if ab.once_per_combat and w in once_seen:
                    continue
                if not ab.subject_any_friendly and w != u:
                    continue          # "When I attack" -- I am the subject
                if ab.subject_alone and not alone:
                    continue
                if ab.subject_role not in (ROLE_EITHER, role):
                    continue
                chain_queue(state, TR_ATTACK_OR_DEFEND, w, loc, subj=u)
                if ab.once_per_combat:
                    once_seen.add(w)
                # One queue per (watcher, subject): the Chain Item names the
                # source, and resolution runs every matching ability on it.
                # Queueing per ability would run a two-ability card twice.
                break
        # ...and each player's LEGEND, which watches the designations from the
        # Legend Zone. Queued per designated UNIT rather than per seat, because
        # the unit is the subject the ability acts on -- Ahri - Nine-Tailed Fox
        # gives "it" -1 Might, and "it" is the enemy attacker.
        _queue_legend_role_trigger(state, table, u, owner, role, alone, loc)

    # ...and the battlefield's own "when you defend here". Fired once PER SEAT
    # that has a role, not once per unit: the ground says "when YOU defend",
    # and a player defending with three units has defended once. That is the
    # same once-for-the-player rule the conquer and hold sites follow, and the
    # reason this loop is over seats rather than nested in the one above.
    for seat in range(N_SEATS):
        if not state.units_at(loc, seat).size or seat in had_role:
            continue
        role = ROLE_ATTACK if seat == attacker else ROLE_DEFEND
        state.desig_seat[seat] = 1
        _queue_bf_role_trigger(state, table, bf, seat, role)


def _queue_legend_role_trigger(state: GameState, table: CardTable, u: int,
                               owner: int, role: int, alone: bool,
                               loc: int) -> None:
    """Queue either legend's "when I/an enemy attacks or defends" for unit `u`.

    The side clauses are checked here, the same way the permanent loop checks
    them: `subject_enemy` is read against the LEGEND's seat, so Ahri -
    Nine-Tailed Fox ("when an ENEMY unit attacks a battlefield you control")
    fires for the player whose ground is attacked, with the attacker riding as
    the subject.
    """
    from rl.engine.chain import queue as chain_queue
    from rl.engine.effects import (ROLE_EITHER, TR_ATTACK_OR_DEFEND,
                                   legend_abilities_for)
    from rl.engine.state import legend_src
    for who in range(N_SEATS):
        lcard = int(state.legend[who])
        if lcard < 0:
            continue
        for ab in legend_abilities_for(table, lcard):
            if ab.trigger != TR_ATTACK_OR_DEFEND:
                continue
            if bool(ab.subject_enemy) != (owner != who):
                continue
            if ab.subject_role not in (ROLE_EITHER, role):
                continue
            if ab.subject_alone and not alone:
                continue
            if ab.once_each_turn:
                if int(state.legend_once[who]) == int(state.ply):
                    continue
                state.legend_once[who] = int(state.ply)
            chain_queue(state, TR_ATTACK_OR_DEFEND, legend_src(who), loc,
                        subj=u, who=who)
            break


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
            # A printed [Reaction] unit (Janna - Savior) is a response too.
            + actions.fast_permanents_playable(state, table, cfg, seat)
            + chain.hidden_playable(state, table, cfg, seat)
            + chain.flow_playable(state, table, cfg, seat))


def showdown_pass(state: GameState) -> bool:
    """Pass priority. Returns True once both players have passed in succession."""
    state.passes += 1
    state.priority = 1 - state.priority
    return state.passes >= N_SEATS


# --- Step 2: the Combat Damage Step (465) ----------------------------------

def _tiers(state: GameState, table: CardTable, idxs,
           ignore_tank: bool = False) -> list[list[int]]:
    """Split targets into assignment-priority tiers (465.2.c.6).

    `[Tank]` first, unconstrained second, `[Backline]` last. A unit with both
    (465.2.c.8) is exclusionary -- the assigning player picks which requirement
    to satisfy -- and we take Tank, the stricter one, which is also the choice
    that keeps the enumeration deterministic.
    """
    tank, plain, back = [], [], []
    for i in idxs:
        card = int(state.perms[i, P_CARD])
        if not ignore_tank and perm_kw(state, table, i, "Tank"):
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
                targets: list[int], ignore_tank: bool = False,
                assigner: int = -1) -> list[int]:
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
    tiers = _tiers(state, table, targets, ignore_tank)
    best_val, best_kills = -1, []
    spent_lower = 0
    for k, tier in enumerate(tiers):
        if spent_lower > pool:
            break
        costs = [lethal_cost(state, table, i, assigner) for i in tier]
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


def _ignore_tank_here(state: GameState, table: CardTable,
                      targets: list[int], assigner: int) -> bool:
    """Dune Surfer -- "you ignore [Tank] while assigning combat damage here"."""
    return bool(targets) and assigner >= 0 and _named_at_bf(
        state, table, IGNORE_TANK_HERE, seat=assigner,
        loc=int(state.perms[targets[0], P_LOC]))


def _apply_kills(state: GameState, table: CardTable, pool: int,
                 targets: list[int], kills: list[int], assigner: int = -1,
                 ignore_tank: bool = False) -> list[int]:
    """Mark `kills` as having taken lethal and spill the leftover (465.2.c.4).

    Split out of `_assign` so that a PLAYER-chosen assignment and the engine's
    own `solve_kills` answer run through identical code once the choice is
    made. Everything here is consequence, not decision: marking the damage
    (because a Reaction that heals or buffs mid-assignment needs the real
    numbers later), the excess bookkeeping, and the spill onto the next legal
    target -- which changes nothing, since the Resolution Step heals it away,
    but keeps the model honest.
    """
    left = pool
    for i in kills:
        c = lethal_cost(state, table, i, assigner)
        dealt = modify_incoming(state, i, c)
        note_damage_source(state, i, assigner, dealt)
        state.perms[i, P_DMG] += dealt
        if dealt > 0:
            state.perms[i, P_FLAGS] |= F_DAMAGED_TURN
        left -= c
    if assigner >= 0:
        survivors = [i for i in targets if i not in kills]
        state.excess_ply[assigner] = int(state.ply)
        state.excess_amt[assigner] = max(0, left) if not survivors else 0
        state.excess_attacking[assigner] = int(int(state.attacker) == assigner)
    if left > 0:
        for tier in _tiers(state, table, targets, ignore_tank):
            spare = [i for i in tier if i not in kills]
            if spare and moved_twice_protected(state, table, spare[0]):
                break
            if spare:
                dealt = modify_incoming(state, spare[0], left)
                if dealt > 0:
                    note_damage_source(state, spare[0], assigner, dealt)
                    state.perms[spare[0], P_DMG] += dealt
                    state.perms[spare[0], P_FLAGS] |= F_DAMAGED_TURN
                    # Noxian Guillotine: even leftover damage kills it.
                    # Imperial Decree likewise -- "when any unit TAKES damage
                    # this turn, kill it" is about the event, and combat damage
                    # is damage (RiftJudge #11553: 5 Might into 3s kills the 3
                    # it was lethal to AND the one the last 2 landed on).
                    # Lethal assignment is untouched: the Decree kills after
                    # damage lands, it does not make 1 damage lethal.
                    if (int(state.guillotine_ply[spare[0]]) == int(state.ply)
                            or state.any_damage_kills):
                        kills.append(spare[0])
                break
    return kills


def _assign(state: GameState, table: CardTable, pool: int,
            targets: list[int], assigner: int = -1) -> list[int]:
    """Assign `pool` damage the engine's own way and return the lethal rows.

    The automatic path: `solve_kills` picks, `_apply_kills` performs. Used when
    the assignment is forced (the pool covers every target) or when
    `cfg.engine_solves_damage_assignment` pins the pre-D1 behaviour. When the
    player owns the choice, `damage_step` suspends instead and `actions`
    collects it -- see `state.pend_dmg`.
    """
    ignore_tank = _ignore_tank_here(state, table, targets, assigner)
    kills = solve_kills(state, table, pool, targets, ignore_tank, assigner)
    return _apply_kills(state, table, pool, targets, kills, assigner, ignore_tank)


def _dmg_spent(state: GameState, table: CardTable, seat: int) -> int:
    """Damage `seat` has already committed to its chosen kills."""
    return sum(lethal_cost(state, table, int(state.pend_dmg_kills[seat, j]), seat)
               for j in range(int(state.pend_dmg_n_kill[seat])))


def _dmg_targets(state: GameState, seat: int) -> list[int]:
    return [int(state.pend_dmg_targets[seat, j])
            for j in range(int(state.pend_dmg_n_tgt[seat]))]


def _dmg_chosen(state: GameState, seat: int) -> list[int]:
    return [int(state.pend_dmg_kills[seat, j])
            for j in range(int(state.pend_dmg_n_kill[seat]))]


def dmg_legal_kills(state: GameState, table: CardTable, seat: int) -> list[int]:
    """Rows `seat` may still choose to kill with what is left of its pool.

    The ordering keywords make the choice an *ordered* subset: you may not
    reach into a tier until every unit in the tiers below it is dead
    (815.1.c.2, 826.4.b). So the offer is always drawn from the lowest tier
    that still holds an unchosen unit, and within it only the units the
    remaining pool can actually kill.

    Returning empty means the seat is finished -- either everything reachable
    is already chosen, or nothing left is affordable.
    """
    chosen = set(_dmg_chosen(state, seat))
    alive = [i for i in _dmg_targets(state, seat)
             if state.perms[i, P_ALIVE] == 1]
    ignore_tank = _ignore_tank_here(state, table, alive, seat)
    budget = int(state.pend_dmg_pool[seat]) - _dmg_spent(state, table, seat)
    for tier in _tiers(state, table, alive, ignore_tank):
        rest = [i for i in tier if i not in chosen]
        if rest:
            return [i for i in rest
                    if lethal_cost(state, table, i, seat) <= budget]
    return []


def dmg_solver_choice(state: GameState, table: CardTable, seat: int) -> int:
    """The next kill `solve_kills` would take, or -1 to stop.

    The engine's own answer to a *player-owned* assignment, for agents that
    want it. `greedy` uses this so that handing the choice to the player does
    not quietly weaken the baseline: before D1 the engine solved every
    assignment optimally for both sides, and a baseline that started taking
    whatever was offered first would make the policy's win rate rise for
    reasons that have nothing to do with the policy.

    Not used by the learner -- the whole point is that it chooses for itself.
    """
    legal = set(dmg_legal_kills(state, table, seat))
    if not legal:
        return -1
    tg = _dmg_targets(state, seat)
    want = solve_kills(state, table, int(state.pend_dmg_pool[seat]), tg,
                       _ignore_tank_here(state, table, tg, seat), seat)
    chosen = set(_dmg_chosen(state, seat))
    for i in want:
        if i in legal and i not in chosen:
            return int(i)
    return -1


def damage_step(state: GameState, table: CardTable, cfg: Config,
                bf: int) -> dict:
    """Both sides sum Might, assign, and deal simultaneously (465).

    Simultaneity is the whole point: there is no priority window in which to
    kill an attacker and save a defender, so a unit that dies still deals its
    full Might. That makes the two allocations separable.

    **Assignment may belong to the player** (465.2.c.2), in which case this
    suspends rather than solving: `state.pend_dmg` names the seat being asked
    and `actions` collects one kill at a time. Re-entering with
    `state.pend_dmg_bf == bf` continues a suspended assignment. Nothing is
    marked on the board until *both* seats have answered, so the second seat
    asked cannot read the first's choice -- damage is simultaneous, and asking
    sequentially must not leak.
    """
    state.showdown_step = SD_DAMAGE
    if int(state.pend_dmg_bf) == bf:
        return _continue_assignment(state, table, bf)

    loc = bf_loc(bf)
    units = [list(state.units_at(loc, s)) for s in range(N_SEATS)]

    # 465.1: no damage unless both sides still have units here.
    if not units[0] or not units[1]:
        return {"pools": (0, 0), "killed": ([], [])}

    pools = [sum(might_for_pool(state, table, i) for i in units[s])
             for s in range(N_SEATS)]

    state.pend_dmg_targets[:] = -1
    state.pend_dmg_kills[:] = -1
    state.pend_dmg_n_kill[:] = 0
    state.pend_dmg_done[:] = 0
    for s in range(N_SEATS):
        tg = units[1 - s]
        state.pend_dmg_n_tgt[s] = len(tg)
        for j, i in enumerate(tg):
            state.pend_dmg_targets[s, j] = i
        state.pend_dmg_pool[s] = pools[s]
        # The engine answers when there is nothing to decide -- the pool covers
        # every target, so wiping the board is forced -- or when the old
        # behaviour is pinned by config. Otherwise the player owns it.
        if (cfg.engine_solves_damage_assignment
                or not assignment_is_a_choice(state, table, pools[s], tg)):
            ignore_tank = _ignore_tank_here(state, table, tg, s)
            kills = solve_kills(state, table, pools[s], tg, ignore_tank, s)
            for j, i in enumerate(kills):
                state.pend_dmg_kills[s, j] = i
            state.pend_dmg_n_kill[s] = len(kills)
            state.pend_dmg_done[s] = 1
    state.pend_dmg_bf = bf
    return _continue_assignment(state, table, bf)


def _continue_assignment(state: GameState, table: CardTable, bf: int) -> dict:
    """Ask the next seat that owes a choice, or deal the damage once both have."""
    for s in range(N_SEATS):
        if int(state.pend_dmg_done[s]):
            continue
        if dmg_legal_kills(state, table, s):
            state.pend_dmg = s
            return {"assigning": s,
                    "left": int(state.pend_dmg_pool[s]) - _dmg_spent(state, table, s)}
        # Nothing reachable is affordable, so there was never a choice here.
        state.pend_dmg_done[s] = 1
    state.pend_dmg = -1
    return _apply_assignment(state, table, bf)


def _apply_assignment(state: GameState, table: CardTable, bf: int) -> dict:
    """Mark both seats' chosen kills, then destroy -- simultaneously (465.3)."""
    pools = [int(state.pend_dmg_pool[s]) for s in range(N_SEATS)]
    killed = []
    for s in range(N_SEATS):
        tg = _dmg_targets(state, s)
        killed.append(_apply_kills(state, table, pools[s], tg,
                                  _dmg_chosen(state, s), s,
                                  _ignore_tank_here(state, table, tg, s)))
    # Cleared before `_destroy`, which can suspend again (Altar of Blood) and
    # re-enter the driver: a stale `pend_dmg_bf` would re-open the assignment
    # and deal the damage twice.
    state.pend_dmg = -1
    state.pend_dmg_bf = -1
    state.pend_dmg_done[:] = 0
    state.pend_dmg_n_tgt[:] = 0
    state.pend_dmg_n_kill[:] = 0
    state.pend_dmg_targets[:] = -1
    state.pend_dmg_kills[:] = -1
    state.pend_dmg_pool[:] = 0
    for s, side in enumerate(killed):
        _prev = KILLER[:]
        KILLER[:] = [s, False]
        try:
            for i in side:
                _destroy(state, table, i)
        finally:
            KILLER[:] = _prev
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
        # Symbol of the Solari -- a TIE (both sides still here) recalls every
        # unit, not just the attackers, when its controller is the attacker.
        tie_all = state.has_units_at(loc, attacker) and any(
            state.perms[g, P_ALIVE] == 1 and int(state.perms[g, P_CTRL]) == attacker
            and table.names[int(state.perms[g, P_CARD])] in TIE_RECALLS_ALL
            for g in range(state.n_perms))
        for i in state.units_at(loc, attacker):
            state.set_location(i, base_loc(attacker))
            recalled.append(int(i))
        if tie_all:
            for i in state.units_at(loc, defender):
                state.set_location(i, base_loc(defender))
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
        # 466.3.a -- the one player with units left won; 466.3.c hands the
        # result to their units here. Queued now, ahead of Control (466.5),
        # because 466.4 resolves the result's triggers first.
        if state.showdown_combat:
            queue_win_combat(state, table, 0 if a else 1, loc)

    if restage:
        state.showdown_step = SD_PRIORITY
        state.passes = 0
        return False

    # 466.5 -- Combat is over, so Control settles and a change of hands Conquers.
    if state.showdown_combat and int(state.showdown_bf) >= 0:
        queue_combat_ends(state, table, int(state.showdown_bf))
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


def queue_win_combat(state: GameState, table: CardTable, winner: int,
                     loc: int) -> None:
    """466.3.a/c -- queue "when I / you win a combat" for `winner`.

    Two shapes. "When I win a combat" is on a UNIT, and fires once for each of
    the winner's units still at the battlefield -- 466.3.c gives them their
    controller's result, so a unit that died in the exchange did not win.
    "When you win a combat" is on a LEGEND and fires once for the player; a
    legend has no row, so it is asked separately, as `phases` does for
    end-of-turn legend triggers.

    `once_each_turn` is stamped HERE for the same reason `queue_move_trigger`
    stamps it: this is a direct queueing site, and a gate that only
    `fire_watchers` honoured would let Draven - Audacious score on every
    combat instead of the first.
    """
    from rl.engine.chain import queue as chain_queue
    from rl.engine.effects import legend_abilities_for
    from rl.engine.state import legend_src
    for i in state.units_at(loc, winner):
        i = int(i)
        wins = [ab for ab in row_abilities(state, table, i)
                if ab.trigger == TR_WIN_COMBAT]
        if not wins:
            continue
        if any(ab.once_each_turn for ab in wins):
            if int(state.once_used[i]) == int(state.ply):
                continue
            state.once_used[i] = int(state.ply)
        chain_queue(state, TR_WIN_COMBAT, i, loc)
    for i in state.units_at(loc, winner):
        _queue_mark(state, int(i), TR_MARKED_WINS)
    from rl.engine.chain import fire_legend
    fire_legend(state, table, winner, TR_WIN_COMBAT, loc)


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


def grants_play_kind(state: GameState, table: CardTable, seat: int,
                     kind: int) -> bool:
    """Does anything `seat` controls carry a play-permission static `kind`?"""
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or int(row[P_CTRL]) != seat:
            continue
        if any(st.kind == kind for st in row_statics(state, table, i)):
            return True
    return False


def unmovable_by(state: GameState, table: CardTable, perm: int,
                 seat: int) -> bool:
    """Jagged Cutlass -- "I can't be moved by ENEMY spells and abilities"."""
    if seat < 0 or seat == int(state.perms[perm, P_CTRL]):
        return False
    for i in range(state.n_perms):
        if state.perms[i, P_ALIVE] != 1:
            continue
        for st in row_statics(state, table, i):
            if st.kind == ST_NO_ENEMY_MOVE and static_reaches(
                    state, table, st, i, perm):
                return True
    return False


def grants_open_play(state: GameState, table: CardTable, seat: int) -> bool:
    """Does anything `seat` controls widen 806.3 to open battlefields?

    Miss Fortune - Buccaneer: "Friendly units may be played to open
    battlefields." The first printed exception to 806.3 that lives on a
    permanent rather than on the card being played, so it has to be read off
    the BOARD -- which is why it cannot go in `effects.PLAY_PERMISSIONS`, a
    registry keyed by the name of the card being played.

    Scoped SC_YOUR_CARDS for the same reason a cost discount is: what it
    affects is still in its owner's hand, with no row to ask about. Read by
    `actions.play_destinations`, the counterpart to `bf_forbids_play` above.
    """
    for i in range(state.n_perms):
        row = state.perms[i]
        if row[P_ALIVE] != 1 or int(row[P_CTRL]) != seat:
            continue
        for st in row_statics(state, table, i):
            if st.kind == ST_PLAY_OPEN:
                return True
    return False


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
