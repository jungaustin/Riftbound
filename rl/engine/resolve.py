"""The DSL interpreter: which targets are legal, and what happens on resolution.

Two halves, and the rules put a hard wall between them.

**Legality (355).** A target is chosen when the card is *finalized*, and every
restriction is checked then. `legal_targets` answers "what may fill slot k,
given the slots already filled". Slots fill one at a time, reusing the same
add-one/COMMIT machinery as a Move declaration -- which is why that machinery
was built generically in the first place.

**Resolution (359.3.e).** Between finalization and resolution the board can
change, so targets are re-checked on the way in. A target that became illegal is
skipped, and the instructions that act on it with it -- even if *every* target
became illegal, the untargeted instructions still happen (359.3.e.1, e.7,
e.10). This is the difference that makes response windows matter, and
it is why `[Stun]` has to be a real status rather than a subtraction applied at
finalization.

The distinction the rules care about most, and the one worth getting right here:
a **restriction** narrows what may be chosen (checked at finalization, and again
at resolution), while a **condition** is checked only at resolution and can
simply fail. "Kill a unit with 3 might or less" is a restriction -- a 4-might
unit was never a legal choice. "Kill a unit if it has 3 might or less" is a
condition -- any unit is a legal target, and growing it in response makes the
spell fizzle (355.9.b).
"""

from __future__ import annotations

import numpy as np

from rl.config import CARD_TYPES, Config
from rl.engine import phases
from rl.engine.cardtable import CardTable
from rl.engine import combat
from rl.engine.effects import LOOK_REVEAL_ALL
from rl.engine.effects import (COND_ANY_TARGET_TEMPORARY, COND_DIED_ALONE,
                               COND_FROM_HAND,
                               COND_EMPOWERED, COND_PLAYED_TRIO,
                               COND_NOT_EMPOWERED,
                               COND_FEW_RUNES, COND_NOT_DIED_ALONE,
                               COND_CTX_BATTLEFIELD, COND_CTX2_BATTLEFIELD,
                               COND_SELF_AT_BF,
                               COND_N_OTHERS_HERE, COND_OTHERS_MIGHT,
                               CT_MY_BATTLEFIELDS, CT_MY_MIGHTY_UNITS,
                               CT_MY_OTHER_BATTLEFIELDS, CT_MY_EQUIPMENT,
                               CT_MY_UNITS, COND_CONTROL_TAG,
                               COND_OPP_CONTROLS_STUNNED, COND_OPP_ANOTHER_SPELL,
                               COND_ENEMY_ALONE_WHERE_MOVED,
                               COND_NOT_DAMAGED_THIS_TURN, OP_UNCHOOSABLE_TURN,
                               TR_STUN, TR_BUFFED, CT_ANIMAL_TAGS,
                               COND_CHOSE_ENEMY_THIS_TURN, COND_ALL_ANIMAL_TAGS,
                               COND_TARGET_NOT_EMPOWERED, COND_RUNES_AT_LEAST,
                               TR_MOVED_ENEMY, OP_SPEND_BUFF,
                               COND_BELOW_LEVEL, COND_NO_FACEDOWN,
                               COND_TARGET_ATTACKING, COND_TARGET_NOT_ATTACKING,
                               COND_MY_BEGINNING, COND_ENEMY_ALONE_HERE,
                               COND_NOT_MY_BEGINNING,
                               OP_MOVE_ALL_TO_BASE, OP_WEAPONMASTER,
                               CT_SOURCE_EQUIPMENT, TR_EQUIPPED,
                               OP_DEATH_SHIELD, OP_GUILLOTINE, COND_NOT_LEGION,
                               OP_MARK, COND_RUNES_BELOW, CULL_KEEP_OWN,
                               OP_BUFF_BONUS_TURN, OP_BASE_MIGHT, OP_TAKE_CONTROL,
                               COND_FRIENDLY_COUNT_AT_SLOT, OP_REVEAL_TOP,
                               COND_REVEAL_MISSED, OP_ASK, OP_TO_DECK,
                               OP_ADD_ANY_NEXT_MAIN, OP_DAMAGE_SHIELD,
                               OP_DOUBLE_DAMAGE, OP_BANISH_ON_DEATH,
                               OP_NEXT_UNIT_READY, OP_EXTRA_TURN,
                               OP_BANISH_FROM_TRASH, COND_PLAYED_CARD_THIS_TURN,
                               COND_NOT_PAID_ADDITIONAL, OP_GRANT_MY_KEYWORDS,
                               OP_TOGGLE_ATTACH, OP_DETACH_THIS,
                               OP_NEXT_SPELL_BONUS, OP_NEXT_SPELL_REPEAT,
                               OP_PLAY_FROM_HAND, OP_RETURN_FACEDOWN,
                               OP_MIGHT_THIS_COMBAT, OP_EXHAUST_LEGEND, OP_WIN,
                               OP_REVEAL_RUNE, TR_RUNE_BODY, OP_REVEAL_PLAY,
                               COND_ONE_ON_ONE, COND_HAND_UNITS_AT_BF,
                               COND_DISEMPOWERED, COND_PICKED_ANIMAL,
                               OP_QUEUE_FOLLOWUP, OP_REVEAL_COUNT_DAMAGE,
                               OP_PAY_POWER, T_LAST_TOKEN,
                               COND_HAND_AT_MOST, COND_UNITS_AT_CTX,
                               COND_PLAYED_EQUIPMENT, COND_CTX_BF_MINE,
                               COND_CHOSE_ENEMY_TWICE, COND_MIGHTY_AT_CTX,
                               COND_SHOWED_OFF,
                               COND_HELD_HERE, COND_KILLED_N, COND_TRASH_BELOW,
                               OP_RECYCLE_TRASH_ALL, OP_SPLIT_DAMAGE, OP_DETACH_ONE,
                               OP_ADD_SPELL_ENERGY, COND_CONQUERED_UNCONTROLLED,
                               EMPOWERED_SPELL_WARD, EMPOWERED_CHOSEN_TO_MIGHT,
                               OP_PAY_ANY_AMOUNT, OP_FREE_GEAR, OP_ARMORY,
                               COND_BURNED_UNIT, COND_KILLED_MIGHT_AT_MOST,
                               OP_GRANT_FLOW, OP_SARC_BANISH, OP_SARC_PLAY,
                               OP_STEAL_SPELL, MULTI_BUFF, OP_GAIN_TAG, OP_NAME,
                               OP_COPY_PREP, OP_BECOME_COPY, COPY_ON_ATTACH,
                               OP_GRANT_ABILITY, OP_REPLAY_CARD, OP_LINK_CONTROL,
                               OP_ZERO_BANISH, OP_ZERO_PLAY, OP_PROMISING_FUTURE,
                               OP_DIVINE_JUDGMENT, OP_ENDLESS_RICHES,
                               OP_REPLACE_BF, OP_RESTORE_BF,
                               OP_BANISH_SPELL_PILE, OP_RECYCLE_RUNE,
                               OP_ACTIVATE_CONQUERS, OP_UNIT_TAX, OP_FREE_HIDE,
                               NAME_FRIENDLY_UNIT,
                               TR_FOLLOWUP,
                               COND_NOT_CONQUERED_THIS_TURN,
                               COND_EXCESS_AT_LEAST, COND_EXCESS_AFTER_ATTACK,
                               OP_DISCOUNT_NEXT_SPELL,
                               OP_GRANT_KEYWORD_ALL, OP_PREVENT_EFFECT_DAMAGE,
                               COND_GAINED_XP_THIS_TURN, COND_OPP_NEAR_VICTORY,
                               CT_ENEMIES_AT_TARGET, COND_READY_ENEMY_HERE,
                               COND_FIRST_TURN, COND_WAS_MIGHTY,
                               COND_FEWER_RUNES_THAN_OPP,
                               COND_PAID_ADDITIONAL, COND_TARGET_EMPOWERED,
                               COND_TARGET_MAX_MIGHT, COND_TARGET_OVER_MIGHT,
                               COND_SLOT_FRIENDLY, COND_SLOT_ENEMY,
                               COND_FACEDOWN_AT_BF, COND_TARGET_STUNNED,
                               COND_TARGET_NOT_STUNNED, COND_SLOT_DIED,
                               COND_LEGION, COND_LEVEL, COND_NONE,
                               COND_ONLY_UNIT_THERE,
                               LOC_BOUND, OP_COUNTER, OP_DAMAGE,
                               OP_DRAW_CONTROLLER, OP_KILL,
                               OP_CREATE_TOKEN, OP_MOVE_TO,
                               OP_RETURN_TO_HAND,
                               OP_DRAW, OP_NO_SPELLS,
                               OP_MODIFY_MIGHT, OP_STUN,
                               COND_CONTROL_N_GEAR, OP_ADD_ENERGY,
                               OP_ADD_POWER, OP_BLINK, OP_BUFF,
                               OP_BUFF_ALL_AT,
                               OP_DAMAGE_ALL,
                               OP_DISCARD, OP_EXHAUST_ALL, OP_HEAL_AT,
                               OP_KILL_ALL, OP_MODIFY_MIGHT_ALL,
                               OP_READY, OP_SWAP_LOC,
                               REL_DIFFERENT_LOC, REL_NONE,
                               REL_SAME_BF, TK_BATTLEFIELD, TK_UNIT,
                               W_ANY, W_ENEMY,
                               TK_LOCATION, TK_SPELL, TK_TRASH_CARD, TK_MODE,
                               compose_mode,
                               OP_TRASH_TO_HAND, OP_PLAY_FROM_TRASH,
                               OP_PLAY_UNIT_FROM_TRASH, W_FRIENDLY,
                               OP_RECYCLE_FROM_TRASH, OP_GAIN_XP,
                               OP_LOOK_TOP, OP_EMPOWER, OP_CHANNEL,
                               OP_DEATH_GUARD, OP_REVEAL_HAND, OP_SCORE,
                               OP_EACH_KILLS_OWN, OP_NO_MOVE,
                               OP_ANY_DAMAGE_KILLS, OP_SWAP_MIGHT,
                               OP_READY_RUNES, OP_DISCARD_CHOOSE,
                               OP_READY_LEGEND,
                               OP_COUNTER_UNLESS_PAYS,
                               OP_ARM_DELAYED, OP_BURN,
                               OP_DISCOUNT_NEXT, OP_NO_CARDS, OP_ATTACH,
                               OP_DIG_TRASH, OP_DISEMPOWER, OP_BANISH,
                               OP_FIGHT, OP_MIGHT_UP_TO, OP_READY_ALL,
                               OP_RETURN_ALL, OP_UNITS_ENTER_READY,
                               empower_limit,
                               TR_REVEALED_FROM_DECK, abilities_for,
                               FOLLOWUPS, SPEED_MAIN,
                               OP_RECYCLE_SELF,
                               OP_SEE_HAND, OP_SEE_FACEDOWN,
                               OP_GRANT_KEYWORD,
                               TR_PLAY_ME, T_COMBAT,
                               T_CTX, T_CTX2, T_HERE, T_MY_BASE,
                               T_OWNER_BASE, T_SELF, T_SUBJECT,
                               TOKEN_DOUBLERS,
                               CardSpec, Op, pack_trash, unpack_trash,
                               TargetSpec)
from rl.engine import chain
from rl.engine.state import (P_ATTACHED_TO, DEST_TOP, DEST_RECYCLE, EOT_DISEMPOWER, EOT_EMPOWER, EOT_REVERT_CONTROL, BEGINNING, F_DAMAGED_TURN, F_UNCHOOSABLE_TURN, F_STUNNED, P_OWNER, C_ABIL, C_CARD, C_CTRL, C_DEST, C_FINAL, C_UID, COST_FREE,
                             LOOK_TYPE_BIT, DEST_BANISH, D_ANY, MAX_TARGETS,
                             fd_slots, fd_bf,
                             COST_NO_ENERGY, COST_PRINTED,
                             F_BUFFED,
                             F_DIED_ALONE, F_DIED_MIGHTY,
                             F_EMPOWERED, F_LEGION, F_NO_MOVE,
                             P_EMPOWER,
                             F_PAID_ADDITIONAL,
                             GRANT_IDX, N_BF, N_SEATS, P_ALIVE,
                             PT_GEAR, PT_SPELL, PT_UNIT,
                             P_FLAGS,
                             P_CARD, P_CTRL, P_DMG, P_LOC, P_MIGHT_MOD, P_ARRIVED,
                             P_READY, GameState,
                             LOC_NONE,
                             base_loc, bf_index, bf_loc,
                             bf_src_index, is_bf_src,
                             is_legend_src, legend_src,
                             is_battlefield)


def source_loc(state: GameState, source: int) -> int:
    """Where an ability's source stands -- its "here". -1 if it has none.

    **The one decoder for the question**, because there are now three kinds of
    source and two places that ask. A permanent is at its row's location; a
    battlefield IS a location, and unlike a permanent's it cannot move or die,
    so it never fizzles; a legend has no location at all (107.4.b -- the Legend
    Zone is not one), and -1 is the honest answer rather than a lie that would
    put its abilities somewhere.

    Split out after `same_loc_as_source` silently excluded every battlefield
    source: it tested `source < 0`, which is true of every sentinel, so
    Emperor's Dais found no candidates for "a unit you control HERE" and 355.8
    refused to put the ability on the Chain at all. The ability simply never
    happened, with nothing to see -- a trigger that declines to fire looks the
    same as one that was never written.
    """
    if is_bf_src(source):
        return bf_loc(bf_src_index(source))
    if is_legend_src(source):
        return -1
    return int(state.perms[source, P_LOC]) if source >= 0 else -1


def deflect_cost(state: GameState, table: CardTable, seat: int,
                 chosen: list[int], spec: CardSpec | None = None) -> int:
    """Extra Power owed for choosing [Deflect] permanents (809.1.c).

    "Spells and abilities an OPPONENT controls that target me cost an amount of
    Power equal to the Deflect Value more to play, for each time they choose
    me." Three details the wording carries and a naive reading drops:

      - only an opponent's spell pays it, so targeting your own Deflect unit
        is free;
      - it is per CHOICE, so a card that targets the same unit twice pays
        twice -- which is why this sums over `chosen` rather than over the set;
      - 809.1.c.1 the Power may be of ANY domain, unlike a printed Power cost.
    """
    if spec is not None and getattr(spec, "ignore_deflect", False):
        return 0          # Decree of Insight
    total = 0
    for slot, p in enumerate(chosen):
        # **A slot's value means whatever its KIND says.** A TK_LOCATION slot
        # holds 0-3, which are perfectly valid permanent ROW indices, so
        # reading every slot as a row charged a phantom surcharge for whichever
        # unit happened to sit in row 2 -- and then failed the affordability
        # assert at finalization. Only unit slots can carry a Deflect target.
        if spec is not None:
            if slot >= spec.n_targets or spec.targets[slot].kind != TK_UNIT:
                continue
        if p is None or p < 0 or p >= state.n_perms:
            continue
        if state.perms[p, P_ALIVE] != 1 or int(state.perms[p, P_CTRL]) == seat:
            continue
        # Heisho, Shell of the World: "players ignore [Deflect] while paying
        # for spells and abilities choosing something HERE". The ground the
        # CHOSEN unit is standing on, so a Deflect unit is only sheltered while
        # it stands there.
        if _deflect_ignored_at(state, table, int(state.perms[p, P_LOC])):
            continue
        total += combat.perm_kw(state, table, p, "Deflect")
    return total


def _deflect_ignored_at(state: GameState, table: CardTable, loc: int) -> bool:
    """Does a battlefield at `loc` switch [Deflect] off (Heisho)?"""
    from rl.engine.effects import BF_IGNORE_DEFLECT
    if not is_battlefield(loc):
        return False
    card = int(state.bf_card[bf_index(loc)])
    return card >= 0 and table.names[card] in BF_IGNORE_DEFLECT


def _affordable_with(state: GameState, table: CardTable, card: int, seat: int,
                     chosen: list[int], extra: int,
                     spec: CardSpec | None = None) -> bool:
    """Could `seat` still pay for `card` after choosing these targets?

    Deflect turns affordability into part of target LEGALITY: a target the
    caster cannot pay the surcharge for was never a legal choice, and offering
    it would announce a card that can never be finalized -- the same deadlock
    shape as a target dead-end.
    """
    if card < 0:
        return True
    need = deflect_cost(state, table, seat, chosen, spec) + extra
    if need <= 0:
        return True
    from rl.engine.cost import plan_surcharge
    return plan_surcharge(state, table, seat, card, need) is not None


def _run_revealed_abilities(state: GameState, table: CardTable, cfg: Config,
                            seat: int, rc: int, log: dict) -> None:
    """"As I'm revealed from your deck, ..." (Undertitan). The card is in NO
    zone and has no row, so these cannot ride the Chain; every such ability in
    the pool is `immediate` (337.2, a resource add) and runs inline."""
    for _ab in abilities_for(table, rc):
        if _ab.trigger != TR_REVEALED_FROM_DECK:
            continue
        assert _ab.immediate, (
            f"{table.names[rc]!r} reveals from the deck with a non-immediate "
            "ability; a card in no zone has no source to put on the Chain")
        _sub = resolve(state, table, cfg, _ab, seat, [], -1, False, card=rc)
        log.setdefault("revealed_abilities", []).append(rc)
        log["resolved"].extend(_sub["resolved"])


def _queue_equipped(state: GameState, table: CardTable, unit: int) -> None:
    """TR_EQUIPPED for the unit an Equipment just attached to."""
    from rl.engine.effects import row_abilities
    if any(ab.trigger == TR_EQUIPPED for ab in row_abilities(state, table, unit)):
        chain.queue(state, TR_EQUIPPED, int(unit), int(state.perms[unit, P_LOC]))


def _weaponmaster_payable(state: GameState, table: CardTable, seat: int,
                          gear: int) -> bool:
    from rl.engine.effects import weaponmaster_cost
    from rl.engine.cost import plan_ability_cost
    cost = weaponmaster_cost(state, table, seat, gear)
    if cost is None:
        return False
    e, p, xp = cost
    if xp and int(state.xp[seat]) < xp:
        return False
    return plan_ability_cost(state, table, seat, int(state.perms[gear, P_CARD]),
                             e, p) is not None


def _ward_count(state: GameState, table: CardTable, seat: int) -> int:
    """Empowered Mel, Newly Awakened permanents `seat` controls."""
    return sum(1 for i in range(state.n_perms)
               if state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == seat
               and table.names[int(state.perms[i, P_CARD])] in EMPOWERED_SPELL_WARD
               and state.empower_count(i))


def _fury_threatened(state: GameState, table: CardTable, perm: int,
                     seat: int) -> bool:
    """In combat with an enemy Fury unit, or chosen by an enemy Fury spell."""
    fury = 1 << 3                                   # config.DOMAINS "Fury"
    if combat.in_combat(state, perm):
        loc = int(state.perms[perm, P_LOC])
        if any(state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) != seat
               and int(state.perms[i, P_LOC]) == loc
               and int(table.domain_mask[int(state.perms[i, P_CARD])]) & fury
               for i in range(state.n_perms)):
            return True
    for j in range(state.n_chain):
        if int(state.chain[j, C_ABIL]) >= 0 or int(state.chain[j, C_CTRL]) == seat:
            continue
        c = int(state.chain[j, C_CARD])
        if not int(table.domain_mask[c]) & fury:
            continue
        sp = chain.item_spec(state, table, j)
        if sp is None:
            continue
        if any(k < sp.n_targets and sp.targets[k].kind == TK_UNIT
               and int(state.chain_targets[j, k]) == perm
               for k in range(sp.n_targets)):
            return True
    return False


def _matches(state: GameState, table: CardTable, spec: TargetSpec, perm: int,
             seat: int, chosen: list[int], bound_bf: int,
             source: int = -1, parent: CardSpec | None = None,
             lost_ok: bool = False) -> bool:
    """Does `perm` satisfy one slot's restrictions?"""
    row = state.perms[perm]
    if row[P_ALIVE] != 1:
        return False
    # "I can't be chosen by enemy spells and abilities" (Ruin Runner). A
    # prohibition rather than a surcharge -- [Deflect] makes you pay, this
    # makes the unit not a legal choice at all, so it never reaches the slot.
    if combat.unchoosable_by(state, table, perm, seat):
        return False
    card = int(row[P_CARD])
    # `card_type` overrides the kind's default. A TK_UNIT slot means "a unit"
    # unless the card says otherwise -- Salvage kills a GEAR, and gear are
    # permanents on the board like any other, so they need the same slot rather
    # than a parallel target kind.
    if spec.card_type:
        if not any(table.is_type(card, t) for t in spec.card_type):
            return False
    elif spec.kind == TK_UNIT and not table.is_type(card, "Unit"):
        return False
    # A tag whitelist -- Bubble Bot's "another friendly Mech". Tags carry no
    # rules of their own; they exist only to be named like this.
    _tags = combat.perm_tags(state, table, perm)
    if spec.tags and not any(t in _tags for t in spec.tags):
        return False
    if spec.lacks_tag and spec.lacks_tag in _tags:
        return False
    if spec.not_self and perm == source:
        return False          # "another unit" -- never the ability's own source
    if spec.not_subject and perm == TARGET_SUBJ[0]:
        return False          # "another unit" than the one that triggered it
    if spec.token_only and not table.is_token(card):
        return False

    ctrl, loc = int(row[P_CTRL]), int(row[P_LOC])
    if spec.who == W_FRIENDLY and ctrl != seat:
        return False
    if spec.who == W_ENEMY and ctrl == seat:
        return False

    # "an enemy unit HERE" on a unit's own ability -- the source's location.
    # Distinct from `rel`/`rel_to`, which can only relate a slot to an earlier
    # SLOT and so cannot say this at all; and from `at_battlefield`, which says
    # "at SOME battlefield" and would let Crackshot Corsair shoot across the
    # board. With no source (a spell), there is no "here" and nothing matches.
    if spec.same_loc_as_source and source_loc(state, source) != loc:
        return False
    # The mirror -- "at a DIFFERENT location" from the source. A missing
    # source has no location to differ from, so nothing qualifies rather than
    # everything: the same failure direction `same_loc_as_source` takes.
    if spec.different_loc_from_source:
        here = source_loc(state, source)
        if here < 0 or here == loc:
            return False

    if spec.lacks_keyword and combat.perm_kw(state, table, perm,
                                            spec.lacks_keyword):
        return False
    if spec.at_battlefield and not is_battlefield(loc):
        return False
    # "a unit at a base" -- unqualified, so EITHER base. `who` narrows it to
    # one side when the card says so; without that this would silently mean
    # "your base" and Rocket Barrage could never hit anything worth hitting.
    if spec.at_base and is_battlefield(loc):
        return False
    # "with 3 Might or less" asks what the unit's Might IS, not what its corner
    # prints -- `combat.might` is the single read path, and reading the table
    # here let a 2-Might body pumped to 7 stay a legal choice. Because
    # `_matches` runs again at resolution (359.3.e), the effective reading also
    # makes the restriction re-check correctly: pumping the target during the
    # response window takes it out of range.
    if spec.max_might >= 0 and combat.might(state, table, perm) > spec.max_might:
        return False
    # "a friendly [Mighty] unit" (Sacrifice) -- effective Might, same as
    # `max_might` above, just floored instead of capped.
    if spec.min_might >= 0 and combat.might(state, table, perm) < spec.min_might:
        return False
    # "...something else that's EXHAUSTED". Readying a ready permanent is a
    # no-op, so this keeps the choice meaningful rather than letting the
    # ability fire into a board with nothing to wake up.
    if spec.must_be_exhausted and int(state.perms[perm, P_READY]):
        return False
    if spec.must_be_buffed and not int(state.perms[perm, P_FLAGS]) & F_BUFFED:
        return False
    if spec.must_be_ready and not int(state.perms[perm, P_READY]):
        return False
    if spec.fury_threatened and not _fury_threatened(state, table, perm, seat):
        return False
    if spec.named_tag_of_source:
        from rl.engine.effects import tag_vocab
        nm = int(state.named[source]) if source >= 0 else -1
        if nm < 0 or tag_vocab(table)[nm] not in combat.perm_tags(state, table, perm):
            return False
    if spec.at_source_move_ends:
        if source < 0 or not is_battlefield(loc) or loc not in (
                int(state.move_from[source]), int(state.move_to[source])):
            return False
    if spec.attached_to_slot >= 0:
        host = (chosen[spec.attached_to_slot]
                if spec.attached_to_slot < len(chosen) else -1)
        if host < 0 or int(state.perms[perm, P_ATTACHED_TO]) != host:
            return False
    if spec.equipped and not any(
            "Equipment" in table.tags[int(state.perms[g, P_CARD])]
            for g in state.attachments(perm)):
        return False
    if spec.must_be_empowered and not int(state.perms[perm, P_FLAGS]) & F_EMPOWERED:
        return False
    if (spec.unit_at_battlefield and table.is_type(card, "Unit")
            and not is_battlefield(int(state.perms[perm, P_LOC]))):
        return False
    if spec.level_gate and (seat < 0 or int(state.xp[seat]) < spec.level_gate):
        return False
    if spec.card_name and table.names[card] != spec.card_name:
        return False
    if spec.champion_only and not bool(table.champion[card]):
        return False
    if spec.max_total_might >= 0 and parent is not None:
        tot = combat.might(state, table, perm) + sum(
            combat.might(state, table, c) for k, c in enumerate(chosen)
            if c >= 0 and k < parent.n_targets
            and parent.targets[k].kind == TK_UNIT and c < state.n_perms
            and state.perms[c, P_ALIVE] == 1)
        if tot > spec.max_total_might:
            return False
    if 0 <= spec.same_ctrl_as < len(chosen):
        other = chosen[spec.same_ctrl_as]
        if other < 0 or int(state.perms[other, P_CTRL]) != ctrl:
            return False
    if spec.exact_loc >= 0:
        if seat < 0 or int(state.perms[perm, P_LOC]) != (
                base_loc(seat), base_loc(1 - seat), bf_loc(0), bf_loc(1))[spec.exact_loc]:
            return False
    if spec.weaponmaster and not _weaponmaster_payable(state, table, seat, perm):
        return False
    # "an enemy unit with LESS Might than" an earlier slot's choice. Strictly
    # less, and both sides effective, so a static or a buff on either unit
    # moves the line. Re-checked at resolution like any other restriction.
    if 0 <= spec.less_might_than < len(chosen):
        other = chosen[spec.less_might_than]
        if other < 0 or combat.might(state, table, perm) >= combat.might(
                state, table, other):
            return False
    # "...with less Might than ME" -- the same comparison against the ability's
    # SOURCE, which is not a slot. A dead or non-permanent source has no Might
    # to compare against, so nothing qualifies rather than everything.
    if spec.less_might_than_source:
        if source < 0 or state.perms[source, P_ALIVE] != 1:
            return False
        if combat.might(state, table, perm) >= combat.might(
                state, table, source):
            return False
    # "a gear with Energy cost no more than {1 energy}" -- the same restriction
    # `_trash_card_ok` already applied to a card in a pile, now on the board.
    if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
        return False
    if spec.max_energy_source_might:
        if source < 0 or state.perms[source, P_ALIVE] != 1:
            return False
        if int(table.energy[card]) > combat.might(state, table, source):
            return False
    # "an enemy Chaos unit or gear" -- the target's own printed domain.
    if spec.domain >= 0 and not (int(table.domain_mask[card]) >> spec.domain & 1):
        return False
    # 459 -- the Attacker's units at the contested battlefield are the
    # attacking ones. Outside a Showdown nobody is attacking, so the slot is
    # empty and the card is simply unplayable (355.8).
    # 807.1.d -- the designations exist only during COMBAT, so a unit that
    # moved onto open ground is attacking nothing (RiftJudge #10763), the same
    # reading `combat.combat_role_bonus` uses for [Assault]/[Shield].
    if spec.attacking and not (
            state.showdown_bf >= 0 and state.showdown_combat
            and ctrl == int(state.attacker)
            and loc == bf_loc(int(state.showdown_bf))):
        return False
    # "a friendly unit in a showdown" (Akali - Rogue Assassin) -- at the
    # battlefield of the open Showdown, either side. The field was declared
    # but never read, so a unit that had already conquered and was in no
    # showdown at all could still be chosen (RiftJudge #12449).
    if spec.in_showdown and not (
            state.showdown_bf >= 0 and loc == bf_loc(int(state.showdown_bf))):
        return False

    # 811.1.d.2.a -- a bound slot may only reach the battlefield the card was
    # hidden at. `bound_bf` is -1 when the card was not played from hiding, in
    # which case locality never applies.
    if bound_bf >= 0 and spec.locality == LOC_BOUND and loc != bf_loc(bound_bf):
        return False

    # "another unit" relative to an earlier SLOT, with no location clause.
    if 0 <= spec.distinct_from < len(chosen) and perm == chosen[spec.distinct_from]:
        return False

    if spec.rel != REL_NONE and 0 <= spec.rel_to < len(chosen):
        other = chosen[spec.rel_to]
        if other < 0:
            # At the OFFER, a slot with nothing to point at cannot be filled
            # yet. At RESOLUTION the question is different: 359.3.e.2 re-reads
            # this target's OWN requirements, and the relationship between two
            # targets was settled when they were chosen. Facebreaker's enemy is
            # still stunned after its friendly half is killed in response
            # (RiftJudge #10273) -- `lost_ok` is that second reading.
            return lost_ok
        # **What the referenced slot HOLDS decides how to read it.** "another
        # unit at a different location" points at a unit row; Crescent Strike's
        # "an enemy unit THERE" points at a battlefield slot, which holds a
        # location. Reading a location as a permanent row silently compares
        # against whatever unit happens to sit in row 0-3 -- a valid index and
        # the wrong question.
        ref_kind = (parent.targets[spec.rel_to].kind
                    if parent is not None and spec.rel_to < parent.n_targets
                    else TK_UNIT)
        if ref_kind in (TK_BATTLEFIELD, TK_LOCATION):
            other_loc = other
        else:
            if perm == other:
                return False               # "another unit" is never the same one
            other_loc = int(state.perms[other, P_LOC])
        if spec.rel == REL_SAME_BF and loc != other_loc:
            return False
        if spec.rel == REL_DIFFERENT_LOC and loc == other_loc:
            return False
    return True


def _spell_targets(state: GameState, table: CardTable, spec: TargetSpec,
                   seat: int, chosen: list[int],
                   all_chosen: list[int] = ()) -> list[int]:
    """Chain items this slot may counter, as stable uids.

    Excludes items still Pending -- which is what keeps a spell from countering
    itself: it is Pending on the Chain while its own targets are chosen, and is
    only Finalized afterwards.

    **It used to ALSO exclude the newest item, and that made counterspells
    nearly dead cards.** The reasoning was "the countering card is the newest
    item when its targets are chosen" -- true then, but this function is asked
    at the OFFER too (`playable_hand_indices` -> `can_be_cast`), before the
    counter has been pushed. There the newest item is the spell being answered.
    So against a single spell on the Chain -- the ordinary case of responding to
    what the opponent just cast -- no counter in the pool was ever offered, and
    against two it could only reach the older one. The Pending check already
    covers the self case, so the newest-item rule was never needed.

    **A unit is not a spell, and neither is an ability.** Units never appear
    here at all -- 337.2 resolves them immediately at finalization, so they
    never become a Chain Item and there is nothing to counter. Abilities DO sit
    on the Chain (383.3), and eleven of the thirteen counter cards in the pool
    say "Counter a spell" and mean only that; just Not So Fast and Repulse say
    "spell or ability". So the slot has to opt IN to reaching abilities, and
    the default excludes them.

    The cost restrictions come off the printed card, which is meaningful for a
    spell and meaningless for an ability -- Defy's "costs no more than
    {4 energy}" would otherwise be measured against the ability's SOURCE card,
    a number the ability never had.
    """
    out = []
    for i in range(state.n_chain):
        if state.chain[i, C_FINAL] != 1:
            continue
        is_ability = int(state.chain[i, C_ABIL]) >= 0
        if is_ability and not spec.chain_abilities:
            continue
        # "Can't be countered" (Decree of Rage, an empowered Mel) is NOT a
        # targeting restriction: the spell may still be chosen, and the counter
        # simply fails when it resolves (RiftJudge #11722, #11742). That check
        # lives in `chain.counter`.
        ctrl = int(state.chain[i, C_CTRL])
        if spec.chooses_only >= 0:
            # Repulse -- it chooses that unit and no other friendly unit.
            ref = (all_chosen[spec.chooses_only]
                   if spec.chooses_only < len(all_chosen) else -1)
            sp = chain.item_spec(state, table, i)
            units = ([int(state.chain_targets[i, k]) for k in range(sp.n_targets)
                      if sp.targets[k].kind == TK_UNIT
                      and int(state.chain_targets[i, k]) >= 0]
                     if sp is not None else [])
            if ref < 0 or ref not in units or any(
                    u != ref and int(state.perms[u, P_CTRL]) == seat for u in units):
                continue
        if spec.who == W_FRIENDLY and ctrl != seat:
            continue
        if spec.who == W_ENEMY and ctrl == seat:
            continue
        card = int(state.chain[i, C_CARD])
        if not is_ability:
            if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
                continue
            if spec.max_power >= 0 and int(table.power[card]) > spec.max_power:
                continue
        if spec.chooses_friendly_perm and not _chose_friendly_perm(
                state, table, i, seat):
            continue
        uid = int(state.chain[i, C_UID])
        if uid not in chosen:
            out.append(uid)
    return out


def _chose_friendly_perm(state: GameState, table: CardTable, item: int,
                         seat: int) -> bool:
    """Did Chain Item `item` choose a unit or gear controlled by `seat`?

    Read off that item's own recorded targets. **A slot's value means whatever
    its KIND says** -- a location slot holds 0-3 and a counterspell slot holds
    a Chain uid, both of which are valid permanent ROW indices and neither of
    which is a permanent. So this consults the source's spec and skips every
    slot that is not a unit slot; the same trap `deflect_cost` documents, and
    it would misfire in exactly the same way.
    """
    src_spec = chain.item_spec(state, table, item)
    if src_spec is None:
        return False
    for slot in range(src_spec.n_targets):
        if src_spec.targets[slot].kind != TK_UNIT:
            continue
        p = int(state.chain_targets[item, slot])
        if p < 0 or p >= state.n_perms:
            continue
        if state.perms[p, P_ALIVE] == 1 and int(state.perms[p, P_CTRL]) == seat:
            return True
    return False


def can_play_from_trash(state: GameState, table: CardTable, seat: int,
                        card: int, cost_mode: int, discount: int = 0) -> bool:
    """Could `seat` play this card out of their trash right now?

    **Asked twice, and the second time is the one that matters.** At
    finalization it is a target restriction: it stops the player choosing a
    card that could never be played. At resolution it is re-asked, because a
    full priority window sits between the two -- Fizz's ability finalizes,
    the opponent responds, and only then does the ability resolve and try to
    play what it named.

    Two real-deck fuzz deadlocks came from having only the first check.
    Seed 45 replayed Rebuke ("return a unit at a battlefield") onto a board
    with no unit at a battlefield; seed 1995 replayed Gust after its only legal
    target had been answered in that very window. Both left a spell Pending
    with an empty option list, which is a deadlock rather than a fizzle.

    359.3.e.14.a says a card that cannot legally choose all its targets cannot
    be played, so the honest outcome is that the play simply does not happen.
    """
    from rl.engine import cost as _cost
    with _cost.nonhand():
        return _can_play_from_trash(state, table, seat, card, cost_mode, discount)


def _can_play_from_trash(state: GameState, table: CardTable, seat: int,
                         card: int, cost_mode: int, discount: int = 0) -> bool:
    from rl.engine.cost import plan_ability_cost, plan_payment
    from rl.engine.effects import spec_for as _spec_for
    # **A unit is playable whether or not its text is encoded; a spell is not.**
    # 337.2 resolves a unit immediately and it simply stands there, so a unit
    # with rules text the DSL cannot express is still a perfectly good unit --
    # real decks are full of them and the engine plays them from hand every
    # game. A SPELL with no spec has nothing to do on resolution, so playing it
    # would be a no-op that spent a card, and it has target slots that could
    # dead-end. Requiring a spec of both made The Harrowing able to reanimate
    # nothing at all.
    is_unit = bool(table.is_type(card, "Unit"))
    card_spec = None if is_unit else _spec_for(table, card)
    if not is_unit and card_spec is None:
        return False                       # no rules text the engine can run
    # "ignoring its Energy cost. (You must still pay its Power cost.)"
    if cost_mode == COST_FREE:
        plan = []                          # "ignoring its cost": nothing to pay
    elif cost_mode == COST_NO_ENERGY:
        plan = plan_ability_cost(state, table, seat, card, 0,
                                 int(table.power[card]))
    else:
        plan = plan_payment(state, table, seat, card, -discount)
    if plan is None:
        return False
    # A REQUIRED kill cost is part of what makes the play possible: Heedless
    # Resurrection's trash unit must cost no more than the unit it kills, and
    # 355 chooses that target (step 2) before the kill is paid (step 3). Fizz
    # offering it with only himself to kill and nothing cheap enough in the
    # trash announced a spell whose cost had no legal payment -- an assert in
    # `legal_actions` (RiftJudge #10174's staging).
    if (card_spec is not None and card_spec.cost_kill is not None
            and not card_spec.cost_kill_optional):
        return can_play_with_cost_kill(state, table, card_spec, seat, -1,
                                       card=card)
    # Terminates because no spell in the pool replays a spell that replays a
    # spell; two that did would recurse forever right here.
    return card_spec is None or not card_spec.n_targets or can_be_cast(
        state, table, card_spec, seat, -1, card=card)


def _pay_trash_play(state: GameState, table: CardTable, seat: int, card: int,
                    cost_mode: int, discount: int = 0) -> None:
    """Charge for a card played out of the trash, per its cost mode."""
    from rl.engine import cost as _cost
    with _cost.nonhand():
        _pay_trash_play_inner(state, table, seat, card, cost_mode, discount)


def _pay_trash_play_inner(state: GameState, table: CardTable, seat: int,
                          card: int, cost_mode: int, discount: int = 0) -> None:
    from rl.engine.cost import (effective_power, pay, pay_ability_cost,
                                plan_ability_cost, plan_payment)
    if cost_mode == COST_FREE:
        return                             # "ignoring its cost"
    if cost_mode == COST_NO_ENERGY:
        _p = effective_power(state, table, seat, card)
        recycle = plan_ability_cost(state, table, seat, card, 0, _p)
        assert recycle is not None, "unaffordable Power cost reached the play"
        pay_ability_cost(state, table, seat, 0, recycle, _p, card)
        return
    recycle = plan_payment(state, table, seat, card, -discount)
    assert recycle is not None, "unaffordable card reached the play"
    pay(state, table, seat, card, recycle, -discount)


def _trash_card_ok(table: CardTable, spec: TargetSpec, card: int,
                   state: GameState | None = None, seat: int = -1,
                   cost_kill_card: int = -1) -> bool:
    """Does one card in the trash satisfy a TK_TRASH_CARD slot's restrictions?"""
    if spec.card_type and not any(table.is_type(card, t) for t in spec.card_type):
        return False
    if spec.playable:
        # A card about to be PLAYED needs more than a matching type. Everything
        # that makes a card unplayable from hand makes it an illegal CHOICE
        # here, because choosing it announces a spell that then cannot be
        # finalized -- and an unfinalizable spell sits Pending with an empty
        # option list, which is a deadlock rather than a fizzle.
        #
        # Found by the real-deck fuzz on seed 45: Fizz replayed Rebuke ("return
        # a unit at a battlefield to its owner's hand") onto a board with no
        # unit at any battlefield, 291 steps in.
        if state is None:
            from rl.engine.effects import spec_for as _spec_for
            return _spec_for(table, card) is not None
        if not can_play_from_trash(state, table, seat, card,
                                   spec.playable_cost):
            return False
    if spec.tags and not any(t in table.tags[card] for t in spec.tags):
        return False
    if spec.lacks_tag and spec.lacks_tag in table.tags[card]:
        return False
    if spec.champion_only and not bool(table.champion[card]):
        return False
    if spec.has_keyword and not table.has(card, spec.has_keyword):
        return False
    if spec.max_energy >= 0 and int(table.energy[card]) > spec.max_energy:
        return False
    if spec.max_power >= 0 and int(table.power[card]) > spec.max_power:
        return False
    if spec.energy_below_points and (
            state is None or seat < 0
            or int(table.energy[card]) >= int(state.points[seat])):
        return False
    # "costs no more than the unit THIS PLAY killed" (Heedless Resurrection).
    # `cost_kill_card` is always a real card id by the time this matters:
    # `actions._slot_options` reads it off `C_COST_KILL` once the cost has
    # actually been paid, and `chain.playable_hand_indices`'s OFFERING check
    # supplies one CANDIDATE at a time from `cost_kill_targets` -- see
    # `_cost_kill_variants`. -1 only reaches here for a card with no such
    # restriction, where `spec.capped_by_cost_kill` is False anyway.
    if spec.capped_by_cost_kill and cost_kill_card >= 0:
        if int(table.energy[card]) > int(table.energy[cost_kill_card]):
            return False
        if int(table.power[card]) > int(table.power[cost_kill_card]):
            return False
    return True


def _trash_seats(spec: TargetSpec, seat: int) -> tuple[int, ...]:
    """Which trashes a slot may draw from -- the pile(s) `spec.who` names.

    An unqualified "from trashes" reaches both piles. That is not a generosity
    the engine grants; it is what the card omits to restrict, the same way an
    unqualified "a unit" may be pointed at your own.
    """
    if spec.who == W_FRIENDLY:
        return (seat,)
    if spec.who == W_ENEMY:
        return tuple(s for s in range(N_SEATS) if s != seat)
    return (seat,) + tuple(s for s in range(N_SEATS) if s != seat)


# True only while `actions._slot_options` asks for a slot AFTER the play's kill
# cost has been paid, so the killed card is already in the trash. The
# castability check before the kill must not discount it.
COST_KILL_PAID = [False]

# The subject of the trigger whose slots are being asked about, for
# `TargetSpec.not_subject`. Set around the query like `COST_KILL_PAID`.
TARGET_SUBJ = [-1]


def _trash_targets(state: GameState, table: CardTable, spec: TargetSpec,
                   seat: int, chosen: list[int],
                   cost_kill_card: int = -1) -> list[int]:
    """Distinct cards in the trashes this slot may name (108.2.c).

    Returns values packed by `pack_trash`, deduplicated: two copies of one card
    in an unordered zone are the same choice, and offering both would double the
    branching factor to describe a decision that does not exist. Two copies in
    DIFFERENT trashes are not the same choice, which is why the owner is part of
    the packed value and part of the key counted below.

    But a slot may still name a card an EARLIER slot already named, so long as
    the trash actually holds another copy -- Guerilla Warfare returning two
    Sprite Calls is legal when two are there and illegal when one is. So the
    exclusion counts copies rather than testing membership, which is the same
    duplicate bookkeeping [Flow] needed and the opposite of the `not in chosen`
    rule that unit slots use (a permanent row IS unique).
    """
    have: dict[int, int] = {}
    for owner in _trash_seats(spec, seat):
        for i in range(int(state.n_trash[owner])):
            key = pack_trash(owner, int(state.trash[owner, i]))
            have[key] = have.get(key, 0) + 1
    out: list[int] = []
    for key, count in have.items():
        # Heedless Resurrection chooses its unit before its kill cost is paid
        # (355 before 357), so the unit it killed was never in the trash to be
        # chosen (RiftJudge #11472). The engine pays the kill first, so that
        # one copy is discounted here instead.
        if (spec.capped_by_cost_kill and cost_kill_card >= 0
                and COST_KILL_PAID[0]
                and unpack_trash(key) == (seat, cost_kill_card)):
            count -= 1
        if chosen.count(key) >= count:
            continue
        if _trash_card_ok(table, spec, unpack_trash(key)[1], state, seat,
                         cost_kill_card):
            out.append(key)
    return sorted(out)


def take_from_trash(state: GameState, owner: int, card: int) -> bool:
    """Remove one copy of `card` from `owner`'s trash. False if it is not there.

    Any copy will do -- 108.2.c makes the zone unordered, so the copies are
    interchangeable and there is no "which one" to get right. The caller checks
    the return value because the trash it was promised at finalization is not
    the trash it gets at resolution: a whole priority window stands between.
    """
    n = int(state.n_trash[owner])
    idx = next((i for i in range(n) if int(state.trash[owner, i]) == card), -1)
    if card < 0 or idx < 0:
        return False
    state.trash[owner, idx:n - 1] = state.trash[owner, idx + 1:n]
    state.trash[owner, n - 1] = -1
    state.n_trash[owner] = n - 1
    return True


def _location_targets(state: GameState, spec: TargetSpec, seat: int,
                      bound_bf: int) -> list[int]:
    """Locations this slot may name.

    811.1.d.1/d.3 -- a hidden permanent, and a unit played by a hidden spell,
    must go to the battlefield the card was hidden at. A slot marked LOC_FREE
    ignores that, which is what lets Ride The Wind move a unit anywhere while
    Sprite Call's token is pinned.
    """
    if bound_bf >= 0 and spec.locality == LOC_BOUND:
        return [bf_loc(bound_bf)]
    if spec.play_destination:
        # 806.3 -- a Unit may only be PLAYED to your base or a Battlefield you
        # control. A movement destination is any location; a play destination
        # is not, and offering the difference would let The Harrowing drop a
        # unit onto contested ground without ever fighting for it. Same
        # restriction `actions.play_destinations` enforces for a card from
        # hand, and for the same reason.
        return ([base_loc(seat)]
                + [bf_loc(i) for i in state.live_bfs()
                   if int(state.bf_ctrl[i]) == seat])
    # **Which bases this slot reaches.** A location is a base or a battlefield,
    # and there are two bases. `who` picks them the same way it picks a unit's
    # controller, so "a unit at a base" can reach the far side.
    #
    # The default is W_FRIENDLY rather than W_ANY, and that is a rules answer
    # rather than caution: every location slot written so far is a DESTINATION
    # -- a Move or a token placement -- and no card in the pool sends anything
    # to the opponent's base. Movement is base<->battlefield with a unit going
    # to ITS OWN base (`T_OWNER_BASE`), so offering the enemy base as somewhere
    # to move to would invent a play the game does not have.
    if spec.who == W_ENEMY:
        bases = [base_loc(1 - seat)]
    elif spec.who == W_ANY:
        bases = [base_loc(seat), base_loc(1 - seat)]
    else:
        bases = [base_loc(seat)]
    return bases + [bf_loc(i) for i in state.live_bfs()]


def _battlefield_targets(state: GameState, table: CardTable, spec: TargetSpec,
                         seat: int, bound_bf: int,
                         chosen: list[int], source: int = -1) -> list[int]:
    """Battlefields this slot may name, as LOCATIONS.

    A battlefield slot returns the same encoding a TK_LOCATION slot does, so an
    op that moves or damages "there" needs no idea which kind of slot chose it.
    The difference is only in what may be chosen: never a base.

    `who` reads as CONTROL here, because that is what the cards say -- "a
    battlefield you control" (Resonating Strike) against the unqualified "a
    battlefield" (Crescent Strike). An uncontrolled battlefield is neither
    player's, so W_ENEMY excludes it as well as excluding your own.
    """
    if bound_bf >= 0 and spec.locality == LOC_BOUND:
        return [bf_loc(bound_bf)]
    out = []
    for i in state.live_bfs():
        ctrl = int(state.bf_ctrl[i])
        if spec.who == W_FRIENDLY and ctrl != seat:
            continue
        if spec.who == W_ENEMY and (ctrl == seat or ctrl < 0):
            continue
        # "a battlefield where you have units" (Moonfall). A restriction on the
        # battlefield, checked when it is chosen -- and re-checked at
        # resolution, where the units may already be gone.
        if spec.needs_own_units and state.units_at(bf_loc(i), seat).size == 0:
            continue
        if spec.open_bf and any(state.seats_at(bf_loc(i))):
            continue
        if spec.own_facedown and not any(
                int(state.fd_owner[k]) == seat for k in fd_slots(i)):
            continue
        if spec.enemy_might_below_source:
            # Maduli: "an occupied enemy battlefield if my Might is greater
            # than the total Might of enemy units there".
            foes = state.units_at(bf_loc(i), 1 - seat)
            if (ctrl != 1 - seat or not foes.size or source < 0
                    or sum(combat.might(state, table, int(f)) for f in foes)
                    >= combat.might(state, table, source)):
                continue
        loc = bf_loc(i)
        # "to a DIFFERENT battlefield" (Imposing Challenger) -- not the one
        # the ability's source stands at.
        if spec.different_loc_from_source and source_loc(state, source) == loc:
            continue
        if loc not in chosen:
            out.append(loc)
    return out


def legal_targets(state: GameState, table: CardTable, spec: CardSpec, slot: int,
                  seat: int, chosen: list[int], bound_bf: int,
                  source: int = -1, card: int = -1,
                  cost_kill_card: int = -1) -> list[int]:
    """Values that may fill `slot`. Their meaning depends on the slot's kind:
    a permanent row, a chain uid (TK_SPELL), or a location (TK_LOCATION).

    `cost_kill_card` is the card id this same play killed as its own printed
    additional cost (820), or -1. It only ever matters to a TK_TRASH_CARD slot
    with `capped_by_cost_kill` set (Heedless Resurrection) -- see
    `_trash_card_ok`.
    """
    n1 = getattr(spec, "exec_len", 0)
    if n1 and slot >= n1:
        # 820.2.a -- a [Repeat] execution's slots are legal exactly as the
        # first execution's are, judged against ITS OWN earlier choices: the
        # same unit may be chosen again (RiftJudge #12522). Only a Deflect
        # surcharge spans both, since every choice of the unit is paid for.
        base = spec._replace(targets=spec.targets[:n1], exec_len=0)
        opts = legal_targets(state, table, base, slot - n1, seat, chosen[n1:],
                             bound_bf, source, card, cost_kill_card)
        if base.targets[slot - n1].kind != TK_UNIT:
            return opts
        return [i for i in opts if _affordable_with(
            state, table, card, seat, chosen,
            combat.perm_kw(state, table, i, "Deflect")
            if int(state.perms[i, P_CTRL]) != seat
            and not getattr(spec, "ignore_deflect", False) else 0, spec)]
    t = spec.targets[slot]
    # Earlier choices of the SAME kind, for "not chosen twice" exclusions. A
    # slot's value means what its kind says, so a mode index, a Chain uid, a
    # location and a permanent row can all be the same integer -- Flurry of
    # Feathers' mode 0 once hid the spell with uid 0.
    same = [c for k, c in enumerate(chosen)
            if k < spec.n_targets and spec.targets[k].kind == t.kind]
    if t.kind == TK_BATTLEFIELD:
        # Only earlier LOCATION choices can collide with a battlefield: a unit
        # slot holds a permanent row, and row 2 is not battlefield 0.
        locs = [c for k, c in enumerate(chosen)
                if spec.targets[k].kind in (TK_BATTLEFIELD, TK_LOCATION)]
        out = _battlefield_targets(state, table, t, seat, bound_bf, locs,
                                   source)
        # 355.4.a -- "a move to where it already stands is no move", so the
        # destination of a move is never the mover's own location. The
        # TK_LOCATION branch below has always filtered this; a BATTLEFIELD slot
        # that is a move destination (Call to Battle, RiftJudge #10256) is the
        # same restriction with a narrower slot kind.
        if 0 <= t.move_dest_of < len(chosen) and chosen[t.move_dest_of] >= 0:
            here = int(state.perms[chosen[t.move_dest_of], P_LOC])
            out = [l for l in out if l != here]
        return out
    if t.kind == TK_LOCATION:
        locs = _location_targets(state, t, seat, bound_bf)
        if 0 <= t.move_dest_of < len(chosen) and chosen[t.move_dest_of] >= 0:
            mover = chosen[t.move_dest_of]
            here = int(state.perms[mover, P_LOC])
            home = base_loc(int(state.perms[mover, P_CTRL]))
            locs = [l for l in _location_targets(state, t._replace(who=W_ANY),
                                                 seat, bound_bf)
                    if l != here and (is_battlefield(l) or l == home)]
            if 0 <= t.dest_has_ally_of == t.move_dest_of:
                # Temptation -- "a location where there's a unit with the same
                # controller" as the unit being moved.
                c = int(state.perms[mover, P_CTRL])
                locs = [l for l in locs if any(
                    i != mover and int(state.perms[i, P_CTRL]) == c
                    for i in state.units_at(l))]
        return locs
    if t.kind == TK_SPELL:
        return _spell_targets(state, table, t, seat, same, chosen)
    if t.kind == TK_TRASH_CARD:
        return _trash_targets(state, table, t, seat, same, cost_kill_card)
    if t.kind == TK_MODE:
        # "Choose one --": a mode is choosable only if ITS targets can all be
        # filled (355.8 per mode, as for a card).
        used = 0
        if (getattr(spec, "modes_once_per_turn", False) and source >= 0
                and int(state.mode_used_ply[source]) == int(state.ply)):
            used = int(state.mode_used_mask[source])
        mcosts = getattr(spec, "mode_costs", ())
        if mcosts and card >= 0 and seat >= 0:
            from rl.engine.cost import plan_payment as _pp
        return [m for m in range(len(spec.modes))
                if not used >> m & 1
                and (not mcosts or card < 0 or seat < 0 or _pp(
                    state, table, seat, card, mcosts[m][0], mcosts[m][1]) is not None)
                and _can_complete(state, table, compose_mode(spec, m), 1, seat,
                                  [m], bound_bf, source, card, cost_kill_card)]
    return _legend_targets(state, t, seat, same) + [
            i for i in range(state.n_perms)
            if (t.allow_repeat or i not in same)
            and _matches(state, table, t, i, seat, chosen, bound_bf, source,
                         parent=spec)
            # 809 -- an unaffordable Deflect surcharge makes it not a choice.
            and _affordable_with(state, table, card, seat, chosen,
                                 combat.perm_kw(state, table, i, "Deflect")
                                 if int(state.perms[i, P_CTRL]) != seat
                                 and not getattr(spec, "ignore_deflect", False)
                                 else 0,
                                 spec)]


def _legend_targets(state: GameState, t, seat: int, same: list[int]) -> list[int]:
    """The Champion Legends an `or_legend` slot may name (Profiteer)."""
    if not t.or_legend:
        return []
    out = []
    for p in range(N_SEATS):
        if int(state.legend[p]) < 0 or (not t.allow_repeat and legend_src(p) in same):
            continue
        if (t.who == W_FRIENDLY and p != seat) or (t.who == W_ENEMY and p == seat):
            continue
        if t.must_be_empowered and not int(state.legend_emp[p]):
            continue
        out.append(legend_src(p))
    return out


def _can_complete(state: GameState, table: CardTable, spec: CardSpec, slot: int,
                  seat: int, chosen: list[int], bound_bf: int,
                  source: int = -1, card: int = -1,
                  cost_kill_card: int = -1) -> bool:
    """Can slots `slot`..end still all be filled, given `chosen` so far?

    Backtracking, not greedy. Greedy is wrong here: Facebreaker's slots are
    coupled, so committing to the *first* friendly unit can leave the enemy slot
    empty while a different friendly unit would have worked. That was a real
    deadlock -- the enumerator offered a slot-0 choice with no slot-1 follow-up,
    and the player was then to act with an empty action list.
    """
    if slot >= spec.n_targets:
        return True
    _gate = spec.targets[slot].level_gate
    if spec.targets[slot].optional or (
            _gate and (seat < 0 or int(state.xp[seat]) < _gate)):
        # A [Level N] slot below N has nothing to choose and is skipped.
        # 355.14 -- "up to N" may be satisfied with fewer, so an optional slot
        # can always be completed by skipping it. Without this the whole card
        # would be unplayable when the board is too empty to fill it.
        return _can_complete(state, table, spec, slot + 1, seat, chosen + [-1],
                             bound_bf, source, card, cost_kill_card)
    return any(
        _can_complete(state, table, spec, slot + 1, seat, chosen + [p], bound_bf,
                      source, card, cost_kill_card)
        for p in legal_targets(state, table, spec, slot, seat, chosen, bound_bf,
                               source, card, cost_kill_card))


def choosable_targets(state: GameState, table: CardTable, spec: CardSpec,
                      slot: int, seat: int, chosen: list[int],
                      bound_bf: int, source: int = -1,
                      card: int = -1, cost_kill_card: int = -1) -> list[int]:
    """Targets for `slot` that do not dead-end the slots after it.

    359.3.e.14.a says a card whose targets cannot all be chosen legally cannot
    be played. That applies *per choice*, not only up front: picking a target
    that makes a later slot unfillable is itself an illegal choice, because it
    would leave a card that can never be finalized.
    """
    return [p for p in legal_targets(state, table, spec, slot, seat, chosen,
                                     bound_bf, source, card, cost_kill_card)
            if _can_complete(state, table, spec, slot + 1, seat, chosen + [p],
                             bound_bf, source, card, cost_kill_card)]


def can_be_cast(state: GameState, table: CardTable, spec: CardSpec, seat: int,
                bound_bf: int, source: int = -1, card: int = -1,
                cost_kill_card: int = -1) -> bool:
    """Is there any legal way to fill every slot? (359.3.e.14.a)"""
    return _can_complete(state, table, spec, 0, seat, [], bound_bf, source,
                         card, cost_kill_card)


def cost_kill_targets(state: GameState, table: CardTable, spec: CardSpec,
                      seat: int, bound_bf: int = -1) -> list[int]:
    """Legal permanents for `spec.cost_kill`, empty if the card prints none."""
    if spec.cost_kill is None:
        return []
    return [i for i in range(state.n_perms)
            if _matches(state, table, spec.cost_kill, i, seat, [], bound_bf)]


def choosable_cost_kill_targets(state: GameState, table: CardTable,
                                spec: CardSpec, seat: int, bound_bf: int = -1,
                                source: int = -1, card: int = -1) -> list[int]:
    """`cost_kill_targets`, filtered to choices that leave the REST of this
    card's own targets fillable (359.3.e.14.a, applied to the cost itself).

    For a card whose `targets` do not read `capped_by_cost_kill` (Sacrifice,
    Cruel Patron, Stalking Wolf -- every one with empty `targets`), every
    candidate trivially satisfies `can_be_cast` and this equals
    `cost_kill_targets` exactly. Heedless Resurrection's trash-unit slot is
    the first exception: which permanent pays the cost bounds what may fill
    a LATER slot, so the wrong kill choice can deadlock it the same way a
    wrong ordinary-slot choice can -- `can_play_with_cost_kill` only proved
    SOME choice works before the card could be announced; this is what stops
    the player (or the fuzzer) from picking a losing one once it has been.
    """
    return [p for p in cost_kill_targets(state, table, spec, seat, bound_bf)
            if can_be_cast(state, table, spec, seat, bound_bf, source, card,
                          int(state.perms[p, P_CARD]))]


def can_play_with_cost_kill(state: GameState, table: CardTable,
                            spec: CardSpec, seat: int, bound_bf: int = -1,
                            source: int = -1, card: int = -1) -> bool:
    """Is this card playable at all, its printed kill cost (820) included?

    A card without `cost_kill` reduces straight to `can_be_cast`. One WITH it
    needs more than "is there something to kill": Heedless Resurrection's
    OTHER target (a trash unit "that costs no more than the killed unit") is
    COUPLED to which permanent pays the cost, exactly the way Facebreaker's
    two ordinary slots are coupled to each other -- `_can_complete`'s own
    docstring covers why greedy is wrong there. But the cost is not itself
    one of `spec.targets` (`cost_kill`'s own module comment explains why), so
    it cannot join that backtracking directly; this tries each legal kill
    target in turn and asks whether THAT choice leaves the rest playable.

    For a card with no such coupling (Sacrifice, Cruel Patron -- empty
    `targets`), `can_be_cast` is trivially True regardless of which kill was
    tried, so this reduces to "does any legal kill target exist", exactly
    what a plain existence check would have said.
    """
    if spec.cost_kill is None:
        return can_be_cast(state, table, spec, seat, bound_bf, source, card)
    return any(
        can_be_cast(state, table, spec, seat, bound_bf, source, card,
                   int(state.perms[p, P_CARD]))
        for p in cost_kill_targets(state, table, spec, seat, bound_bf))


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _condition_holds(state: GameState, table: CardTable, op: Op,
                     targets: list[int], from_hand: bool, seat: int = -1,
                     source: int = -1, ctx: int = -1,
                     dead_source: int = -1, ctx2: int = -1) -> bool:
    if op.cond == COND_NONE:
        return True
    if op.cond == COND_LEVEL:
        # "[Level N] - while you have N+ XP, get the effect." Continuous and
        # read live: XP never resets, so unlike [Legion] there is no past
        # moment to snapshot, and a level gained mid-chain legitimately turns
        # the effect on.
        return seat >= 0 and int(state.xp[seat]) >= op.level
    if op.cond == COND_LEGION:
        # 822 -- "get the effect if you've played another card this turn",
        # snapshotted onto the source when it was played. Read live, this would
        # be wrong twice over: the source has itself been counted by now, and a
        # "[Legion] - When you play me" trigger sits on the Chain through a
        # priority window in which the count can move again.
        if source >= 0:
            return bool(int(state.perms[source, P_FLAGS]) & F_LEGION)
        if dead_source >= 0:
            return bool(int(state.perms[dead_source, P_FLAGS]) & F_LEGION)
        # A LEGEND has no row either, and unlike a spell it was never counted:
        # 103.1 keeps it in its own zone and it is not played at all. Its
        # reminder text says so -- "get the effect if you've played A card this
        # turn" (Darius - Hand of Noxus), not "another" -- so one card is
        # enough. Read through the spell branch it needed two, and the legend
        # simply exhausted for nothing (RiftJudge #8172).
        if is_legend_src(source):
            return seat >= 0 and int(state.cards_played[seat]) >= 1
        # A SPELL has no row to snapshot onto. It was counted as it was
        # played, so "another card this turn" is a second card played by its
        # controller -- before it or since (Noxian Guillotine).
        return seat >= 0 and int(state.cards_played[seat]) >= 2
    if op.cond == COND_NOT_LEGION:
        return not _condition_holds(state, table, op._replace(cond=COND_LEGION),
                                    targets, from_hand, seat, source, ctx,
                                    dead_source, ctx2)
    if op.cond == COND_PLAYED_TRIO:
        # All three kinds this turn. `played_types` is set as each card is
        # played, so this asks about the turn's history rather than the board.
        return seat >= 0 and int(state.played_types[seat]) & (
            PT_UNIT | PT_GEAR | PT_SPELL) == (PT_UNIT | PT_GEAR | PT_SPELL)
    if op.cond == COND_NOT_DIED_ALONE:
        # Same snapshot as COND_DIED_ALONE, read the other way. `dead_source`,
        # because by now the source is a corpse and `source` has been blanked.
        return dead_source >= 0 and not (
            int(state.perms[dead_source, P_FLAGS]) & F_DIED_ALONE)
    if op.cond == COND_FIRST_TURN:
        # `state.turn` counts ROUNDS, advancing after the second seat's turn,
        # so BOTH players' first Beginning Phase falls on turn 1.
        return int(state.turn) == 1
    if op.cond == COND_CTX_BATTLEFIELD:
        return ctx >= 0 and is_battlefield(ctx)
    if op.cond == COND_CTX2_BATTLEFIELD:
        return ctx2 >= 0 and is_battlefield(ctx2)
    if op.cond == COND_SELF_AT_BF:
        who = source if source >= 0 else dead_source
        return who >= 0 and is_battlefield(int(state.perms[who, P_LOC]))
    if op.cond == COND_READY_ENEMY_HERE:
        who = source if source >= 0 else dead_source
        if who < 0:
            return False
        loc, mine = int(state.perms[who, P_LOC]), int(state.perms[who, P_CTRL])
        return any(state.perms[i, P_ALIVE] == 1
                   and int(state.perms[i, P_CTRL]) != mine
                   and int(state.perms[i, P_LOC]) == loc
                   and state.perms[i, P_READY] == 1
                   and table.is_type(int(state.perms[i, P_CARD]), "Unit")
                   for i in range(state.n_perms))
    if op.cond == COND_N_OTHERS_HERE:
        who = source if source >= 0 else dead_source
        if who < 0:
            return False
        loc, ctrl = int(state.perms[who, P_LOC]), int(state.perms[who, P_CTRL])
        n = sum(1 for i in range(state.n_perms)
                if i != who and state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) == ctrl
                and int(state.perms[i, P_LOC]) == loc
                and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
        return n == op.level
    if op.cond == COND_OTHERS_MIGHT:
        who = source if source >= 0 else dead_source
        if who < 0 or seat < 0:
            return False
        total = sum(combat.might(state, table, i)
                    for i in range(state.n_perms)
                    if i != who and state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == seat
                    and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
        return total >= op.level
    if op.cond == COND_TARGET_EMPOWERED:
        # "If IT'S [Empowered]" -- the op's own target, read live at
        # resolution. Not a restriction: the spell is played and the target
        # chosen either way, and 355.9.b is why that matters here -- an
        # opponent can answer by disempowering in the response window.
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        return a >= 0 and bool(int(state.perms[a, P_FLAGS]) & F_EMPOWERED)
    if op.cond in (COND_TARGET_STUNNED, COND_TARGET_NOT_STUNNED):
        # "If it is stunned, kill it. Otherwise, stun it." (Solari Chief).
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        if a < 0 or state.perms[a, P_ALIVE] != 1:
            return False
        stunned = bool(int(state.perms[a, P_FLAGS]) & F_STUNNED)
        return stunned if op.cond == COND_TARGET_STUNNED else not stunned
    if op.cond == COND_CONTROL_TAG:
        # "If you control a Poro" (Poro Herder) -- any permanent carrying the
        # tag, the source included if it has one.
        return seat >= 0 and any(
            state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == seat
            and op.cond_tag in combat.perm_tags(state, table, i)
            for i in range(state.n_perms))
    if op.cond == COND_OPP_CONTROLS_STUNNED:
        return seat >= 0 and combat.opp_controls_stunned(state, seat)
    if op.cond == COND_BELOW_LEVEL:
        return seat >= 0 and int(state.xp[seat]) < op.level
    if op.cond == COND_NO_FACEDOWN:
        return seat >= 0 and not any(int(state.fd_owner[b]) == seat
                                     for b in range(len(state.fd_owner)))
    if op.cond in (COND_TARGET_ATTACKING, COND_TARGET_NOT_ATTACKING):
        # "If it's attacking, deal 4 instead" (Sudden Storm) -- 459, read live.
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        if a < 0 or state.perms[a, P_ALIVE] != 1:
            return False
        att = (int(state.showdown_bf) >= 0
               and int(state.perms[a, P_CTRL]) == int(state.attacker)
               and int(state.perms[a, P_LOC]) == bf_loc(int(state.showdown_bf)))
        return att if op.cond == COND_TARGET_ATTACKING else not att
    if op.cond in (COND_MY_BEGINNING, COND_NOT_MY_BEGINNING):
        mine = (seat >= 0 and int(state.phase) == BEGINNING
                and int(state.active) == seat)
        return mine if op.cond == COND_MY_BEGINNING else not mine
    if op.cond == COND_ENEMY_ALONE_HERE:
        who = source if source >= 0 else dead_source
        if who < 0 or seat < 0:
            return False
        loc = int(state.perms[who, P_LOC])
        return any(int(state.units_at(loc, s).size) == 1
                   for s in range(len(state.points)) if s != seat)
    if op.cond == COND_CHOSE_ENEMY_THIS_TURN:
        return seat >= 0 and int(state.chose_enemy_ply[seat]) == int(state.ply)
    if op.cond == COND_RUNES_AT_LEAST:
        return seat >= 0 and int(state.runes_in_play(seat).sum()) >= op.level
    if op.cond == COND_FRIENDLY_COUNT_AT_SLOT:
        loc = targets[op.cond_slot] if 0 <= op.cond_slot < len(targets) else -1
        return (loc >= 0 and seat >= 0
                and int(state.units_at(loc, seat).size) == op.level)
    if op.cond == COND_RUNES_BELOW:
        return seat >= 0 and int(state.runes_in_play(seat).sum()) < op.level
    if op.cond == COND_ALL_ANIMAL_TAGS:
        tags = set()
        for i in range(state.n_perms):
            if (state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == seat
                    and table.is_type(int(state.perms[i, P_CARD]), "Unit")):
                tags |= combat.perm_tags(state, table, i) & combat.ANIMAL_TAGS
        return len(tags) == len(combat.ANIMAL_TAGS)
    if op.cond == COND_TARGET_NOT_EMPOWERED:
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        return (a >= 0 and state.perms[a, P_ALIVE] == 1
                and not int(state.perms[a, P_FLAGS]) & F_EMPOWERED)
    if op.cond == COND_NOT_DAMAGED_THIS_TURN:
        # "If I haven't been dealt damage this turn" (Affectionate Poro).
        who = source if source >= 0 else dead_source
        return who >= 0 and not (int(state.perms[who, P_FLAGS])
                                 & F_DAMAGED_TURN)
    if op.cond == COND_OPP_ANOTHER_SPELL:
        # "Counter a spell if an opponent has played ANOTHER spell this turn"
        # (Crumbling Sands). The target is itself a spell some player played
        # this turn; when that player is an opponent it does not count as the
        # "another".
        if seat < 0:
            return False
        n = sum(int(state.spells_played[s]) for s in range(len(state.points))
                if s != seat)
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        i = chain.index_of_uid(state, a) if a >= 0 else -1
        if i >= 0 and int(state.chain[i, C_CTRL]) != seat \
                and int(state.chain[i, C_ABIL]) < 0:
            n -= 1
        return n >= 1
    if op.cond == COND_GAINED_XP_THIS_TURN:
        return seat >= 0 and int(state.xp_gained_ply[seat]) == int(state.ply)
    if op.cond == COND_OPP_NEAR_VICTORY:
        # Same reading as the static gate in `combat.static_condition`.
        return seat >= 0 and any(
            int(state.points[s]) >= state.victory_score - 3
            for s in range(len(state.points)) if s != seat)
    if op.cond == COND_SLOT_DIED:
        # "If this kills it" (Disintegrate) -- the slot's unit is now dead.
        a = targets[op.cond_slot] if 0 <= op.cond_slot < len(targets) else -1
        return a >= 0 and (state.perms[a, P_ALIVE] != 1 or a in combat.HELD_DEATHS)
    if op.cond == COND_FACEDOWN_AT_BF:
        # "if you control a facedown card at a battlefield" (Mushroom Pouch).
        return seat >= 0 and any(int(state.fd_owner[b]) == seat
                                 for b in range(len(state.fd_owner)))
    if op.cond in (COND_SLOT_FRIENDLY, COND_SLOT_ENEMY):
        # "If it was an enemy unit ... If it was a friendly unit" (Blood Money).
        # PAST tense: the unit is usually already dead by the time this op runs
        # (the kill was the op before it), so this reads the dead row, whose
        # P_CTRL survives until end-of-turn compaction.
        a = targets[op.cond_slot] if 0 <= op.cond_slot < len(targets) else -1
        if a < 0 or seat < 0:
            return False
        friendly = int(state.perms[a, P_CTRL]) == seat
        return friendly if op.cond == COND_SLOT_FRIENDLY else not friendly
    if op.cond in (COND_TARGET_MAX_MIGHT, COND_TARGET_OVER_MIGHT):
        # "If it has 3 Might OR LESS, banish it. OTHERWISE, return it to its
        # owner's hand." One sentence, two ops, and the pair must partition:
        # `op.level` is the threshold and the two conditions are exact
        # complements, so exactly one of them runs -- a target that vanished
        # in the response window runs neither, which is 383.2.c.2.
        #
        # EFFECTIVE Might, not the printed corner, so a pump in the response
        # window genuinely flips which half happens. That is the counterplay
        # the card offers and reading `table.might` here would delete it.
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        if a < 0 or state.perms[a, P_ALIVE] != 1:
            return False
        m = combat.might(state, table, a)
        return (m <= op.level if op.cond == COND_TARGET_MAX_MIGHT
                else m > op.level)
    if op.cond == COND_BURNED_UNIT:
        c = int(state.last_burned)
        return c >= 0 and bool(table.is_type(c, "Unit"))
    if op.cond == COND_CONQUERED_UNCONTROLLED:
        return is_battlefield(ctx) and int(state.bf_prev_ctrl[bf_index(ctx)]) == -1
    if op.cond == COND_HELD_HERE:
        if source < 0 or seat < 0:
            return False
        loc = int(state.perms[source, P_LOC])
        return (is_battlefield(loc) and int(state.bf_ctrl[bf_index(loc)]) == seat
                and bool(state.bf_scored[seat, bf_index(loc)]))
    if op.cond == COND_TRASH_BELOW:
        return seat >= 0 and int(state.n_trash[seat]) < op.level
    if op.cond == COND_HAND_AT_MOST:
        return seat >= 0 and int(state.n_hand[seat]) <= op.level
    if op.cond == COND_CHOSE_ENEMY_TWICE:
        return (seat >= 0 and int(state.chose_enemy_ply[seat]) == int(state.ply)
                and int(state.chose_enemy_n[seat]) >= 2)
    if op.cond == COND_CTX_BF_MINE:
        return (seat >= 0 and ctx >= 0 and is_battlefield(ctx)
                and int(state.bf_ctrl[bf_index(ctx)]) == seat)
    if op.cond == COND_PLAYED_EQUIPMENT:
        return seat >= 0 and int(state.equip_played_ply[seat]) == int(state.ply)
    if op.cond == COND_SHOWED_OFF:
        # [Show Off] was taken up as this card was played. "You may", so the
        # honest test is whether a unit was actually named -- declining leaves
        # both slots at -1. Scoped by `show_off_ply`, because the slots are
        # per-seat standing state and a choice made last turn must not answer
        # for this one.
        return (seat >= 0 and int(state.show_off_ply[seat]) == int(state.ply)
                and (int(state.show_off_perm[seat]) >= 0
                     or int(state.show_off_card[seat]) >= 0))
    if op.cond == COND_MIGHTY_AT_CTX:
        return (seat >= 0 and ctx >= 0
                and any(combat.might(state, table, int(u)) >= 5
                        for u in state.units_at(ctx, seat)))
    if op.cond == COND_UNITS_AT_CTX:
        return (seat >= 0 and ctx >= 0
                and int(state.units_at(ctx, seat).size) >= op.level)
    if op.cond == COND_PICKED_ANIMAL:
        c = int(state.look_last_pick)
        return c >= 0 and any(t in table.tags[c]
                              for t in ("Bird", "Cat", "Dog", "Poro"))
    if op.cond == COND_ONE_ON_ONE:
        if source < 0 or state.perms[source, P_ALIVE] != 1 \
                or not combat.in_combat(state, source):
            return False
        return int(state.units_at(int(state.perms[source, P_LOC])).size) == 2 \
            and combat.is_alone(state, source)
    if op.cond == COND_HAND_UNITS_AT_BF:
        return (seat >= 0 and int(state.n_hand[seat]) == op.level
                and sum(int(state.units_at(bf_loc(b), seat).size)
                        for b in state.live_bfs()) == op.level)
    if op.cond in (COND_EXCESS_AT_LEAST, COND_EXCESS_AFTER_ATTACK):
        if seat < 0 or int(state.excess_ply[seat]) != int(state.ply):
            return False
        if op.cond == COND_EXCESS_AFTER_ATTACK and not int(state.excess_attacking[seat]):
            return False
        return int(state.excess_amt[seat]) >= op.level
    if op.cond == COND_NOT_CONQUERED_THIS_TURN:
        who = source if source >= 0 else dead_source
        return who >= 0 and int(state.conquer_ply[who]) != int(state.ply)
    if op.cond == COND_PLAYED_CARD_THIS_TURN:
        # [Legion] -- "if you've played ANOTHER card this turn". A permanent
        # played this turn is itself one of the cards counted, so its own
        # [Legion] needs a second: Sun Disc cannot be exhausted the turn it
        # comes down on its own (RiftJudge #9616). Sun Disc is gear and never
        # moves, so arriving this turn means it was played this turn.
        need = 1
        if (source >= 0 and not is_bf_src(source) and not is_legend_src(source)
                and int(state.perms[source, P_ARRIVED]) == int(state.ply)
                and not table.is_token(int(state.perms[source, P_CARD]))):
            need = 2
        return seat >= 0 and int(state.cards_played[seat]) >= need
    if op.cond == COND_NOT_PAID_ADDITIONAL:
        return not _condition_holds(state, table, op._replace(cond=COND_PAID_ADDITIONAL),
                                    targets, from_hand, seat, source, ctx,
                                    dead_source, ctx2)
    if op.cond == COND_PAID_ADDITIONAL:
        # "When you play me, IF YOU PAID the additional cost, ...". Recorded on
        # the row as the card was played, because the payment is a moment that
        # has passed by the time this trigger resolves -- the same reading
        # [Legion] needs. `dead_source` too: the unit can be answered in the
        # response window and the clause is still about what was paid.
        who = source if source >= 0 else dead_source
        if who < 0:
            return bool(state.resolving_paid)       # a spell's own payment
        return bool(int(state.perms[who, P_FLAGS]) & F_PAID_ADDITIONAL)
    if op.cond == COND_WAS_MIGHTY:
        # 740.2 -- Mighty is 5+ Might, and "I WAS Mighty" asks about the moment
        # of death. Reads the flag `combat._destroy` recorded then, for the same
        # reason COND_DIED_ALONE does: the Deathknell resolves a priority window
        # later, over a row whose buffs may already have been cleared.
        return dead_source >= 0 and bool(
            int(state.perms[dead_source, P_FLAGS]) & F_DIED_MIGHTY)
    if op.cond == COND_FEWER_RUNES_THAN_OPP:
        # "If you control FEWER runes than an opponent" -- both boards counted
        # the way COND_FEW_RUNES counts one: ready plus spent, because an
        # exhausted rune is still controlled.
        if seat < 0:
            return False
        mine = int(state.runes_ready[seat].sum() + state.runes_spent[seat].sum())
        other = 1 - seat
        theirs = int(state.runes_ready[other].sum()
                     + state.runes_spent[other].sum())
        return mine < theirs
    if op.cond == COND_FEW_RUNES:
        # "If you control N or fewer runes." Runes on the BOARD -- ready plus
        # spent -- because an exhausted rune is still controlled; the ones left
        # in the rune deck are not.
        return seat >= 0 and int(state.runes_ready[seat].sum()
                                 + state.runes_spent[seat].sum()) <= op.level
    if op.cond == COND_EMPOWERED:
        # 828.1.d -- an [Empowered] dependent ability that is a TRIGGER is
        # active while its source holds the status. Read on the source, and
        # `dead_source` matters: Noxian Emissary's payload is a [Deathknell],
        # so by resolution the source is already a corpse and `source` alone
        # would be -1. The status it held when it died is what the card asks
        # about (359.3.f.3), and the flag is still on the dead row.
        if is_legend_src(source):
            return state.src_empowered(source)
        who = source if source >= 0 else dead_source
        return who >= 0 and bool(int(state.perms[who, P_FLAGS]) & F_EMPOWERED)
    if op.cond == COND_NOT_EMPOWERED:
        # The other half of "[Add] {1 energy}. If this is [Empowered], [Add]
        # {2 energy} INSTEAD" (Platewyrm Egg). "Instead" makes the two amounts
        # a partition, so the base amount needs the negation rather than
        # always running with a bonus stacked on top of it.
        who = source if source >= 0 else dead_source
        return who >= 0 and not (int(state.perms[who, P_FLAGS]) & F_EMPOWERED)
    if op.cond == COND_DIED_ALONE:
        # Lonely Poro: "If I died alone", where its own reminder defines alone
        # as "no other friendly units here". Past tense, and that decides the
        # implementation: read the flag `combat._destroy` recorded at the
        # moment of death rather than counting the board now. A Deathknell sits
        # on the Chain through a full priority window (808.1.d.2), so "now" is
        # a board a response has had every chance to change.
        #
        # Reads `dead_source`, not `source`: `resolve` blanks a source that is
        # no longer on the board (383.2.c.2), and a Deathknell's source is
        # always exactly that.
        return dead_source >= 0 and bool(
            int(state.perms[dead_source, P_FLAGS]) & F_DIED_ALONE)
    if op.cond == COND_FROM_HAND:
        return from_hand
    if op.cond == COND_ONLY_UNIT_THERE:
        a = targets[op.target] if 0 <= op.target < len(targets) else -1
        if a < 0:
            return False
        loc, ctrl = int(state.perms[a, P_LOC]), int(state.perms[a, P_CTRL])
        return state.units_at(loc, ctrl).size == 1
    if op.cond == COND_CONTROL_N_GEAR:
        # "if you control N or more OTHER gear" -- the source itself does not
        # count, which is what `floor` carries here as the threshold.
        n = sum(1 for i in range(state.n_perms)
                if state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) == seat
                and i != source
                and table.is_type(int(state.perms[i, P_CARD]), "Gear"))
        return n >= int(op.floor or 0)
    if op.cond == COND_ANY_TARGET_TEMPORARY:
        return any(combat.perm_kw(state, table, t, "Temporary")
                   for t in targets if t >= 0)
    raise ValueError(f"unknown condition {op.cond}")


def _sweep(state: GameState, table: CardTable, op: Op, seat: int,
           still_legal: list[int], source: int, ctx: int,
           subj: int = -1, ctx2: int = -1) -> list[int]:
    """Live unit rows a board-wide op reaches, after its scoping clauses.

    The mass effects in the pool are rarely as broad as "all units": they say
    "enemy units", or "units there", or "each OTHER enemy unit there". None of
    those are targets under 355.10 -- there is no count and no choice, so the
    opponent cannot respond by making one of them illegal -- but they are still
    restrictions, and applying them here keeps the sweep in one place instead
    of one `continue` chain per op.

    **An unscoped op reaches the whole board, bases included.** "Give enemy
    units -3 Might" has no location clause and means all of them; the mass
    DAMAGE cards happen to print "at battlefields", which is `at_battlefields`
    and belongs to the card rather than to the op. Defaulting to battlefields
    would have quietly spared every unit sitting at a base.
    """
    where = (_slot(state, still_legal, op.at, source, ctx,
                   seat, subj, ctx2)
             if op.at != -1 else -1)
    spare = (_slot(state, still_legal, op.except_target, source, ctx,
                   seat, subj, ctx2)
             if op.except_target != -1 else -1)
    # A sweep that NAMES a location and cannot find one reaches nothing. The
    # location goes missing in two ordinary ways -- the source of an `at=T_HERE`
    # ability died in the response window (383.2.c.2), and `T_COMBAT` is asked
    # outside a Showdown -- and in both the card's own words scope it to a place
    # that is not there. Falling through to the unscoped branch instead turned
    # "deal 4 to all enemy units HERE" into a board wipe, which is the one
    # answer that is never right.
    if op.at != -1 and where < 0:
        return []
    out = []
    for i in range(state.n_perms):
        r = state.perms[i]
        if r[P_ALIVE] != 1 or i == spare:
            continue
        if not table.is_type(int(r[P_CARD]), "Unit"):
            continue
        if op.tag and op.tag not in combat.perm_tags(state, table, i):
            continue
        if op.damaged_only and int(r[P_DMG]) <= 0:
            continue
        if op.less_might_than_slot >= 0:
            ref = (still_legal[op.less_might_than_slot]
                   if op.less_might_than_slot < len(still_legal) else -1)
            if ref < 0 or combat.might(state, table, i) >= combat.might(
                    state, table, ref):
                continue
        loc = int(r[P_LOC])
        if where >= 0:
            if loc != where:
                continue
        elif op.at_battlefields and not is_battlefield(loc):
            continue
        ctrl = int(r[P_CTRL])
        if op.who == W_FRIENDLY and ctrl != seat:
            continue
        if op.who == W_ENEMY and ctrl == seat:
            continue
        out.append(i)
    return out


_REVEAL_OPS = {OP_REVEAL_TOP, OP_REVEAL_COUNT_DAMAGE, OP_REVEAL_PLAY}
_RESUMING = [False]


def _ask_group_loc(state: GameState, table: CardTable, spec, seat: int,
                   card: int, targets: list[int], bound_bf: int,
                   from_hand: bool, source: int, ctx: int, subj: int,
                   ctx2: int, locs: list[int]) -> bool:
    """355.11.b -- pause this resolution to ask `seat` where a scattered group
    settles. True when paused.

    Same suspend-and-resume machinery `_peek_before_reveal` uses: the pause
    happens BEFORE any op has run, so the resumed resolution simply starts over
    with `state.group_loc` set and nothing is applied twice.
    """
    from rl.engine.effects import (abilities_for, equip_abilities_for,
                                   spec_for as _sf)
    if int(state.pend_group_loc) >= 0 or int(state.resume_kind):
        return False
    kind, idx = 0, -1
    if card >= 0 and _sf(table, card) is spec:
        kind = 1
    elif card >= 0 and spec in abilities_for(table, card):
        kind, idx = 2, abilities_for(table, card).index(spec)
    elif card >= 0 and spec in equip_abilities_for(table, card):
        kind, idx = 3, equip_abilities_for(table, card).index(spec)
    else:
        for k, ops in enumerate(FOLLOWUPS):
            if ops and tuple(spec.ops) == tuple(ops):
                kind, idx = 4, k
                break
    if not kind or seat < 0:
        return False                # nothing to resume into: keep the fallback
    state.resume_kind, state.resume_card, state.resume_idx = kind, card, idx
    state.resume_op, state.resume_seat, state.resume_src = 0, seat, source
    state.resume_ctx, state.resume_ctx2, state.resume_subj = ctx, ctx2, subj
    state.resume_hand, state.resume_bound = int(from_hand), bound_bf
    state.resume_tgts[:] = -1
    state.resume_tgts[:len(targets)] = targets[:MAX_TARGETS]
    state.group_loc_opts[:] = -1
    state.group_loc_opts[:len(locs)] = locs[:MAX_TARGETS]
    state.n_group_loc = min(len(locs), MAX_TARGETS)
    state.pend_group_loc = seat
    return True


def _peek_before_reveal(state: GameState, table: CardTable, spec, seat: int,
                        card: int, op_index: int, targets: list[int],
                        bound_bf: int, from_hand: bool, source: int, ctx: int,
                        subj: int, ctx2: int) -> bool:
    """Void Hatchling: pause this resolution for a one-card look (recycle or
    keep on top) if `seat` controls one; True when paused."""
    from rl.engine.effects import (REVEAL_PEEKERS, abilities_for,
                                   equip_abilities_for, spec_for as _sf)
    if int(state.pend_look) >= 0 or int(state.resume_kind):
        return False
    if not any(state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == seat
               and table.names[int(state.perms[i, P_CARD])] in REVEAL_PEEKERS
               for i in range(state.n_perms)):
        return False
    ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
    if ptr >= end:
        return False
    kind, idx = 0, -1
    if card >= 0 and _sf(table, card) is spec:
        kind = 1
    elif card >= 0 and spec in abilities_for(table, card):
        kind, idx = 2, abilities_for(table, card).index(spec)
    elif card >= 0 and spec in equip_abilities_for(table, card):
        kind, idx = 3, equip_abilities_for(table, card).index(spec)
    else:
        for k, ops in enumerate(FOLLOWUPS):
            if ops and tuple(spec.ops) == tuple(ops):
                kind, idx = 4, k
                break
    if not kind:
        return False
    state.resume_kind, state.resume_card, state.resume_idx = kind, card, idx
    state.resume_op, state.resume_seat, state.resume_src = op_index, seat, source
    state.resume_ctx, state.resume_ctx2, state.resume_subj = ctx, ctx2, subj
    state.resume_hand, state.resume_bound = int(from_hand), bound_bf
    state.resume_tgts[:] = -1
    state.resume_tgts[:len(targets)] = targets[:MAX_TARGETS]
    state.look_cards[:] = -1
    state.look_cards[0] = state.deck[seat, ptr]
    state.n_look = 1
    state.deck_ptr[seat] = ptr + 1
    state.look_pick_dest, state.look_rest_dest = DEST_RECYCLE, DEST_TOP
    state.look_optional, state.look_multi = 1, 0
    state.look_min_energy, state.look_type_mask = 0, 0
    state.pend_look = seat
    return True


def run_resume(state: GameState, table: CardTable, cfg) -> dict:
    """Continue a resolution `_peek_before_reveal` paused."""
    from rl.engine.effects import abilities_for, equip_abilities_for, spec_for as _sf
    kind, card, idx = int(state.resume_kind), int(state.resume_card), int(state.resume_idx)
    if not kind:
        return {}
    state.resume_kind = 0
    spec = (_sf(table, card) if kind == 1 else abilities_for(table, card)[idx]
            if kind == 2 else equip_abilities_for(table, card)[idx] if kind == 3
            else CardSpec(speed=SPEED_MAIN, ops=FOLLOWUPS[idx]))
    tg = [int(x) for x in state.resume_tgts[:spec.n_targets]]
    spec = spec._replace(ops=tuple(spec.ops[int(state.resume_op):]))
    _RESUMING[0] = True
    try:
        return resolve(state, table, cfg, spec, int(state.resume_seat), tg,
                       int(state.resume_bound), bool(state.resume_hand),
                       source=int(state.resume_src), ctx=int(state.resume_ctx),
                       subj=int(state.resume_subj), ctx2=int(state.resume_ctx2),
                       card=card)
    finally:
        _RESUMING[0] = False


def _can_pay_domain_power(state: GameState, seat: int, domain: int,
                          n: int) -> bool:
    """Could `seat` pay `n` Power of `domain` now -- floating Power of that
    domain or [A], plus runes of that domain to recycle?"""
    have = (int(state.pool_power[seat, domain]) + int(state.pool_power[seat, D_ANY])
            + int(state.runes_in_play(seat)[domain]))
    return have >= n


def _pay_domain_power(state: GameState, seat: int, domain: int, n: int) -> bool:
    if not _can_pay_domain_power(state, seat, domain, n):
        return False
    for d in (domain, D_ANY):
        use = min(n, int(state.pool_power[seat, d]))
        state.pool_power[seat, d] -= use
        state.note_power_spent(seat, use)
        n -= use
    for _ in range(n):
        state.recycle_rune(seat, domain)
    return True


def show_off_might(state, table, seat: int) -> int:
    """The Might of the unit `seat` showed off as the current card was played.

    Two sources and they are read differently. A permanent's Might is read
    LIVE, so a buff it gained between the choice and resolution counts -- the
    card says "that unit's Might", not "its Might when you chose it". A card
    revealed from HAND has no row and no buffs, so its printed Might is all
    there is.

    0 when nothing was shown off, or when the choice belongs to an earlier ply
    (the slots are standing per-seat state), or when a chosen permanent has
    since died -- there is no unit left whose Might to read, and unlike
    `n_from_might`'s kill case this spell did not do the killing, so there is
    no recorded last-known value to fall back on.
    """
    from rl.engine import combat as _c
    if seat < 0 or int(state.show_off_ply[seat]) != int(state.ply):
        return 0
    perm = int(state.show_off_perm[seat])
    if perm >= 0:
        return (_c.might(state, table, perm)
                if state.perms[perm, P_ALIVE] == 1 else 0)
    card = int(state.show_off_card[seat])
    return int(table.might[card]) if card >= 0 else 0


def _slot(state: GameState, still_legal: list[int], idx: int, source: int,
          ctx: int, seat: int = -1, subj: int = -1, ctx2: int = -1) -> int:
    """Decode an op's target index, including the pseudo-slots.

    A spell's ops address chosen targets by slot. A unit ability also has to
    say "me", "here" and "there" -- none of which are choices, so none of which
    can be slots. Decoding them in one place means every op that takes a target
    understands them without knowing they exist.
    """
    if idx == T_SELF:
        # A battlefield IS the source but has no permanent row, so "me" is not
        # a thing an op can point at. -1 rather than the sentinel: every op
        # downstream treats -1 as "no target" and fizzles, which is the right
        # answer, where the sentinel would be read as a row index.
        return -1 if (is_bf_src(source) or is_legend_src(source)) else source
    if idx == T_HERE:
        return source_loc(state, source)
    if idx == T_CTX:
        return ctx
    if idx == T_CTX2:
        return ctx2
    if idx == T_MY_BASE:
        return base_loc(seat) if seat >= 0 else -1
    if idx == T_SUBJECT:
        return subj
    if idx == T_LAST_TOKEN:
        t = int(state.last_token)
        return t if t >= 0 and state.perms[t, P_ALIVE] == 1 else -1
    if idx == T_COMBAT:
        # 459 -- the contested battlefield. `showdown_bf` is the battlefield
        # INDEX, not a location, and the two are different numbers; conflating
        # them would point "in combat" at a base.
        bf = int(state.showdown_bf)
        return bf_loc(bf) if bf >= 0 else LOC_NONE

    return still_legal[idx] if 0 <= idx < len(still_legal) else -1


def resolve(state: GameState, table: CardTable, cfg: Config, spec: CardSpec,
            seat: int, targets: list[int], bound_bf: int,
            from_hand: bool, source: int = -1, ctx: int = -1,
            subj: int = -1, ctx2: int = -1, card: int = -1) -> dict:
    """See `_resolve`. Holds replaceable lethal-damage deaths to the end of the
    outermost resolution (`combat.RESOLVING`)."""
    combat.RESOLVING[0] += 1
    try:
        return _resolve(state, table, cfg, spec, seat, targets, bound_bf,
                        from_hand, source, ctx, subj, ctx2, card)
    finally:
        combat.RESOLVING[0] -= 1
        if not combat.RESOLVING[0] and combat.HELD_DEATHS:
            combat.release_held_deaths(state, table)


def _resolve(state: GameState, table: CardTable, cfg: Config, spec: CardSpec,
             seat: int, targets: list[int], bound_bf: int,
             from_hand: bool, source: int = -1, ctx: int = -1,
             subj: int = -1, ctx2: int = -1, card: int = -1) -> dict:
    """Apply a finalized card's or ability's ops. Returns a log dict.

    Targets are re-checked here, not trusted from finalization: the window
    between the two is exactly where a response lands (359.3.e).

    `source` and `ctx` are the two things a triggered ability knows and a spell
    does not: the permanent it is printed on, and the location captured when it
    triggered (359.3.f.3). Both are -1 for a card.

    `ctx2` is the second captured location a Move produces. `ctx` is where the
    unit came FROM and `ctx2` where it went TO, and printed text picks between
    them by word -- see `state.C_CTX2`. Neither is a live read, so both outlive
    the source; `T_HERE` is the live one and is meant to fizzle.
    """
    log: dict = {"resolved": [], "fizzled": []}

    # 383.2.c.2 -- an ability whose source left the board cannot reference it.
    # Sprite Mother's "here" has no meaning once she is dead, and dereferencing
    # a dead row would silently place the token at her last location.
    #
    # `dead_source` keeps the row anyway, for the one thing a dead source is
    # still the authority on: what was recorded ABOUT its death. A Deathknell's
    # source is dead by definition, so blanking it outright would make
    # "if I died alone" unanswerable on the only card that asks.
    dead_source = source
    if source >= 0 and state.perms[source, P_ALIVE] != 1:
        source = -1

    still_legal: list[int] = []
    chosen_so_far: list[int] = []
    # 355.11.b -- a GROUP requirement ("up to three units at the same
    # location", Bellows Breath) is not lost when a response scatters what was
    # chosen: the spell resolves (359.3.e.1) and its controller picks ONE of the
    # locations those units are now at; everything they chose there is affected
    # and the rest are not (FAQ #11681 / #11505 / #11633).
    #
    # The engine picks that location rather than asking for it -- the remaining
    # half of gap #9352 -- but it picks the location holding the MOST of the
    # chosen units, which is the choice a player almost always wants. Anchoring
    # on "wherever slot 0 ended up" instead, as this used to, could damage the
    # two units that ran away and spare the one that stood still.
    _group: set[int] = set()
    _anchor_loc = -1
    _rel_to = next((int(ts.rel_to) for ts in spec.targets
                    if ts.rel == REL_SAME_BF and 0 <= int(ts.rel_to) < spec.n_targets
                    and spec.targets[int(ts.rel_to)].kind == TK_UNIT), -1)
    if _rel_to >= 0:
        _group = {_rel_to} | {i for i, ts in enumerate(spec.targets)
                              if ts.rel == REL_SAME_BF and int(ts.rel_to) == _rel_to}
        _counts: dict[int, int] = {}
        for i in sorted(_group):
            t_i = targets[i] if i < len(targets) else -1
            if t_i >= 0 and state.perms[t_i, P_ALIVE] == 1:
                _counts[int(state.perms[t_i, P_LOC])] = _counts.get(
                    int(state.perms[t_i, P_LOC]), 0) + 1
        if len(_counts) > 1:
            if int(state.group_loc) >= 0:
                _anchor_loc = int(state.group_loc)   # answered, and consumed
                state.group_loc = -1
            elif _ask_group_loc(state, table, spec, seat, card, targets,
                                bound_bf, from_hand, source, ctx, subj, ctx2,
                                sorted(_counts)):
                log["paused_for_group_loc"] = True
                return log                           # their choice to make
            else:
                # No way back into this resolution (an ad-hoc spec built in
                # code, not a card): fall back on the location holding the most
                # of them, which is the choice a player almost always makes.
                _best = max(_counts.values())
                _first = (int(state.perms[targets[_rel_to], P_LOC])
                          if targets[_rel_to] >= 0
                          and state.perms[targets[_rel_to], P_ALIVE] == 1 else -1)
                _anchor_loc = (_first if _counts.get(_first, -1) == _best
                               else min(l for l, n in _counts.items()
                                        if n == _best))
        else:
            _group = set()                 # all together: nothing to anchor
    _prev_subj, TARGET_SUBJ[0] = TARGET_SUBJ[0], subj
    for slot, t in enumerate(targets):
        if spec.targets[slot].kind == TK_BATTLEFIELD:
            # Re-checked, unlike a plain location: "a battlefield you control"
            # and "where you have units" are both things a response window can
            # take away.
            ok = t >= 0 and t in _battlefield_targets(
                state, table, spec.targets[slot], seat, bound_bf, [], source)
        elif spec.targets[slot].kind == TK_LOCATION:
            ts = spec.targets[slot]
            if ts.dest_has_ally_of >= 0:
                # Temptation -- "to a location where there's a unit with the
                # same controller". That is a REQUIREMENT on the chosen
                # location, so 359.3.e.2 re-reads it as the spell resolves: a
                # [Repeat] that emptied the place with its first move (RiftJudge
                # #6756), or an ally Gusted out of it, leaves the destination
                # illegal and the move simply does not happen. A plain location
                # (Flash's base, Ride The Wind's battlefield) carries no such
                # requirement and is not re-checked.
                ok = t >= 0 and t in legal_targets(
                    state, table, spec, slot, seat, chosen_so_far, bound_bf,
                    source)
            else:
                ok = t >= 0
        elif spec.targets[slot].kind == TK_SPELL:
            # Still legal iff the item is still on the chain. If someone else
            # countered it first, this one fizzles (359.3.e).
            ok = t >= 0 and chain.index_of_uid(state, t) >= 0
        elif spec.targets[slot].kind == TK_MODE:
            ok = t >= 0
        elif spec.targets[slot].kind == TK_TRASH_CARD:
            # Still legal iff a copy is still there -- and iff no EARLIER slot
            # of this same card has already spoken for the last one. Two slots
            # naming the same card were legal at finalization because two copies
            # existed; if one has since been played out of the trash with
            # [Flow], only the first slot may still have it. Counted in the
            # OWNER's pile, which the packed value names -- the same card in the
            # other player's trash is a different choice and does not stand in.
            need = chosen_so_far.count(t) + 1
            if t < 0:
                ok = False
            else:
                owner, card_t = unpack_trash(t)
                ok = int(np.count_nonzero(
                    state.trash[owner, :int(state.n_trash[owner])]
                    == card_t)) >= need
        else:
            # "the battlefield I moved to or from" (Akali, Deadly Weapon) is
            # information implicit to the trigger, not to her current state:
            # it still names a place after she dies (359.3.f.3, RiftJudge #11760).
            ts = spec.targets[slot]
            ok = (t in _legend_targets(state, ts, seat, []) if is_legend_src(t)
                  else t >= 0 and _matches(state, table, ts, t, seat,
                                      chosen_so_far, bound_bf,
                                      dead_source if ts.at_source_move_ends
                                      else source, parent=spec,
                                      lost_ok=True))
        if ok and slot in _group and _anchor_loc >= 0:
            # ...and every member of a scattered group that is not at the
            # location its controller settled on is simply unaffected.
            ok = (t >= 0 and state.perms[t, P_ALIVE] == 1
                  and int(state.perms[t, P_LOC]) == _anchor_loc)
        still_legal.append(t if ok else -1)
        chosen_so_far.append(t if ok else -1)
    TARGET_SUBJ[0] = _prev_subj

    # 359.3.e.1 -- "the spell resolves even if some or ALL of its targets are
    # illegal". Only the instructions that act on a lost target are skipped
    # (359.3.e.7, per op below); the rest still happen, and the spell still
    # counts as played (359.3.e.10). Discipline whose unit was Gusted still
    # draws (RiftJudge #11983). This used to counter the whole card.
    if spec.n_targets and all(t < 0 for t in still_legal):
        log["all_targets_lost"] = True

    for _opi, op in enumerate(spec.ops):
        if (op.op in _REVEAL_OPS and not _RESUMING[0] and seat >= 0
                and not (op.op == OP_REVEAL_PLAY and (op.from_opponent))
                and _peek_before_reveal(state, table, spec, seat, card, _opi,
                                        targets, bound_bf, from_hand,
                                        dead_source, ctx, subj, ctx2)):
            log["paused_for_peek"] = _opi
            return log
        if op.cond == COND_ENEMY_ALONE_WHERE_MOVED:
            # "Then, if there's an enemy unit alone at THAT battlefield"
            # (Isolate) -- where an earlier op of this card moved its unit
            # FROM, which only this resolution remembers.
            origin = int(log.get("moved_from", -1))
            held = origin >= 0 and is_battlefield(origin) and any(
                int(state.units_at(origin, s).size) == 1
                for s in range(len(state.points)) if s != seat)
            if not held:
                log["fizzled"].append(op.op)
                continue
        elif op.cond == COND_KILLED_MIGHT_AT_MOST:
            if log.get("killed_might") is None or int(log["killed_might"]) > op.level:
                log["fizzled"].append(op.op)
                continue
        elif op.cond == COND_KILLED_N:
            if len(log.get("killed", [])) < op.level:
                log["fizzled"].append(op.op)
                continue
        elif op.cond == COND_SLOT_DIED:
            # "If this kills it" / "If you do" after a kill -- THIS resolution
            # has to be what killed it. Read as "the row is dead" it would also
            # pass for a target that was already gone when the kill ran: the
            # gear its controller spent in answer to Pickpocket's trigger is
            # dead, but nothing killed it here, so there is no "if you do" and
            # no Gold token (RiftJudge #6498). `combat.HELD_DEATHS` covers a
            # death this resolution holds to its end.
            _cs = (still_legal[op.cond_slot]
                   if 0 <= op.cond_slot < len(still_legal) else -1)
            if _cs < 0 or not (_cs in log.get("killed", ())
                               or _cs in combat.HELD_DEATHS):
                log["fizzled"].append(op.op)
                continue
        elif op.cond == COND_DISEMPOWERED:
            if "disempowered" not in log:
                log["fizzled"].append(op.op)
                continue
        elif op.cond == COND_REVEAL_MISSED:
            if not log.get("reveal_missed"):
                log["fizzled"].append(op.op)
                continue
        elif not _condition_holds(state, table, op, still_legal, from_hand,
                                  seat, source, ctx, dead_source, ctx2):
            log["fizzled"].append(op.op)
            continue

        if op.op == OP_DRAW:
            # "THEY discard that card and draw 1" (Insightful Investigator).
            # `who` picks the drawer, the same way OP_BURN picks the miller;
            # W_ANY/W_FRIENDLY both mean the resolving player, which is what
            # every other draw in the pool wants.
            drawer = (1 - seat) if op.who == W_ENEMY else seat
            n = op.n
            if op.n_from_count == CT_MY_BATTLEFIELDS:
                n = op.n * sum(1 for i in state.live_bfs()
                               if int(state.bf_ctrl[i]) == seat)
            elif op.n_from_count == CT_MY_OTHER_BATTLEFIELDS:
                # "Other" than the source's own. `source` is a battlefield here
                # (Seat of Power), so exclude its slot directly.
                mine = bf_src_index(source) if is_bf_src(source) else -1
                n = op.n * sum(1 for i in state.live_bfs()
                               if i != mine and int(state.bf_ctrl[i]) == seat)
            elif op.n_from_count == CT_MY_MIGHTY_UNITS:
                # 5+ Might is Mighty, read as EFFECTIVE Might so statics and
                # buffs count -- the number on the board, not the corner.
                n = op.n * sum(1 for i in range(state.n_perms)
                               if state.perms[i, P_ALIVE] == 1
                               and int(state.perms[i, P_CTRL]) == seat
                               and table.is_type(int(state.perms[i, P_CARD]), "Unit")
                               and combat.might(state, table, i) >= 5)
            if op.each_player:
                log["drew"] = []
                for _p in (int(state.active), 1 - int(state.active)):
                    log["drew"] += phases.draw_for(state, _p, n) if n else []
            else:
                log["drew"] = phases.draw_for(state, drawer, n) if n else []
            log["resolved"].append(op.op)
            continue

        a = _slot(state, still_legal, op.target, source, ctx,
                  seat, subj, ctx2)
        if op.target != -1 and a < 0 and not (
                is_legend_src(a) and op.op in (OP_EMPOWER, OP_DISEMPOWER)):
            if op.op == OP_COPY_PREP:
                state.copy_pending = -1       # nothing to copy, not a stale card
            log["fizzled"].append(op.op)      # this target specifically is gone
            continue

        # Gangplank, Naval (Empowered): a spell or ability that CHOOSES him and
        # would stun him, shrink him or return him gives +3 Might instead.
        # Mel, Newly Awakened (Empowered) first deepens a chosen -Might by 1.
        if op.op == OP_MODIFY_MIGHT and op.target >= 0 and a >= 0 and seat >= 0 \
                and op.n < 0 and _ward_count(state, table, seat):
            op = op._replace(n=op.n - _ward_count(state, table, seat))
        if ((op.op in (OP_STUN, OP_RETURN_TO_HAND)
             or (op.op == OP_MODIFY_MIGHT and op.n < 0))
                and op.target >= 0 and a >= 0 and state.perms[a, P_ALIVE] == 1
                and table.names[int(state.perms[a, P_CARD])]
                in EMPOWERED_CHOSEN_TO_MIGHT and state.empower_count(a)
                # 477.3.b -- a floor that snapshots the -Might to -0 gives no
                # -Might, so there is no event to replace (RiftJudge #11759).
                and not (op.op == OP_MODIFY_MIGHT and op.floor is not None
                         and combat.might(state, table, a) <= op.floor)
                # Stunning a unit already Stunned performs no stun, so there
                # is nothing to replace either (RiftJudge #11758).
                and not (op.op == OP_STUN and state.has_flag(a, F_STUNNED))):
            combat.set_might_mod(state, table, a, 3)
            log.setdefault("instead_might", []).append(a)
            continue

        # "+Might equal to its Might" -- read off another slot at RESOLUTION,
        # so it counts buffs and statics rather than the printed number, and it
        # must be read before any op in this same card kills that unit.
        amount = op.n
        if op.n_from_count == CT_ENEMIES_AT_TARGET and a >= 0:
            # "+2 Might FOR EACH enemy unit there" -- `n` is the rate, and
            # "there" is the chosen unit's location, not the source's.
            loc = int(state.perms[a, P_LOC])
            amount = op.n * sum(
                1 for i in range(state.n_perms)
                if state.perms[i, P_ALIVE] == 1
                and int(state.perms[i, P_CTRL]) != seat
                and int(state.perms[i, P_LOC]) == loc
                and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
        if op.grenade_bonus:
            if int(state.grenade_ply) != int(state.ply):
                state.grenade_ply, state.grenade_hits = int(state.ply), 0
            amount += int(state.grenade_hits)
        if op.n_from_last_burned:
            c = int(state.last_burned)
            amount = max(0, int(table.might[c])) if c >= 0 else 0
        if op.n_from_excess:
            amount = (int(state.excess_amt[seat])
                      if seat >= 0 and int(state.excess_ply[seat]) == int(state.ply)
                      else 0)
        if op.n_from_spell_energy >= 0:
            uid = (still_legal[op.n_from_spell_energy]
                   if op.n_from_spell_energy < len(still_legal) else -1)
            i = chain.index_of_uid(state, uid) if uid >= 0 else -1
            amount = int(table.energy[int(state.chain[i, C_CARD])]) if i >= 0 else 0
        if op.n_from_count == CT_SOURCE_EQUIPMENT:
            amount = op.n * (sum(
                1 for g in state.attachments(source)
                if "Equipment" in table.tags[int(state.perms[g, P_CARD])])
                if source >= 0 else 0)
        if op.plus_same_name_trash and card >= 0 and seat >= 0:
            n_t = int(state.n_trash[seat])
            amount += int(np.count_nonzero(state.trash[seat, :n_t] == card))
        if op.n_from_assault != -1:
            ref = _slot(state, still_legal, op.n_from_assault, source, ctx,
                        seat, subj, ctx2)
            amount = (combat.perm_kw(state, table, ref, "Assault")
                      if ref >= 0 and state.perms[ref, P_ALIVE] == 1 else 0)
        if op.n_from_damage != -1:
            ref = _slot(state, still_legal, op.n_from_damage, source, ctx,
                        seat, subj, ctx2)
            amount = (int(state.perms[ref, P_DMG])
                      if ref >= 0 and state.perms[ref, P_ALIVE] == 1 else 0)
        if op.n_from_count == CT_ANIMAL_TAGS:
            present = set()
            for i in range(state.n_perms):
                if (state.perms[i, P_ALIVE] == 1
                        and int(state.perms[i, P_CTRL]) == seat
                        and table.is_type(int(state.perms[i, P_CARD]), "Unit")):
                    present |= combat.perm_tags(state, table, i) & {
                        "Bird", "Cat", "Dog", "Poro"}
            amount = op.n * len(present)
        # `!= -1`, not `>= 0`: T_SELF is negative, and "damage equal to MY
        # Might" (Caitlyn - Patrolling) names the source rather than a slot.
        if op.n_from_show_off:
            amount = show_off_might(state, table, seat)
        if op.n_from_might != -1:
            ref = _slot(state, still_legal, op.n_from_might, source, ctx, seat,
                        subj)
            amount = (combat.might(state, table, ref)
                      if ref >= 0 and state.perms[ref, P_ALIVE] == 1 else 0)
            # "Kill X. If you do, ... equal to its Might" -- X is dead by now,
            # so its Might is the one this spell's kill recorded (last
            # known information), not a live read of a corpse.
            if (ref >= 0 and state.perms[ref, P_ALIVE] != 1
                    and ref in log.get("killed", ())
                    and log.get("killed_might") is not None):
                amount = int(log["killed_might"])
        if op.op == OP_CREATE_TOKEN:
            # 811.1.d.3 -- a hidden spell that plays a unit must play it at
            # that battlefield. That is enforced by the slot's LOC_BOUND
            # locality, so the player chooses freely from hand and is pinned
            # from hiding, with no special case here.
            card = table.id_of(op.token)
            # "Choose an opponent. They play a 1 Might Bird" (Walking Roost) --
            # the token is theirs from the moment it is played, base included.
            tok_seat = (1 - seat) if op.who == W_ENEMY else seat
            loc = a if a >= 0 else base_loc(tok_seat)
            # Rockfall Path -- "Units can't be played here" stops a token unit
            # too: the instruction is simply not performed (RiftJudge #12328).
            if (table.is_type(card, "Unit") and is_battlefield(loc)
                    and combat.bf_forbids_play(state, table, loc)):
                log["fizzled"].append(op.op)
                continue
            # "...FOR EACH Equipment you control" (Arise!). `op.n` is the rate,
            # as it is everywhere `n_from_count` appears, so a board with no
            # Equipment plays no tokens rather than one.
            count = op.n
            if op.n_from_count == CT_MY_EQUIPMENT:
                count = op.n * sum(
                    1 for i in range(state.n_perms)
                    if state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == seat
                    and "Equipment" in table.tags[int(state.perms[i, P_CARD])])
            # Renata Glasc - Industrialist / Magma Wurm make a token UNIT enter
            # ready whatever the effect said; a gear token keeps the effect's
            # own "exhausted" (see `combat.granted_enters_ready`).
            tok_ready = op.ready or (bool(table.is_type(card, "Unit"))
                                     and combat.granted_enters_ready(
                                         state, table, tok_seat, card))
            made = [state.add_permanent(card, tok_seat, loc, ready=tok_ready,
                                        is_unit=bool(table.is_type(card, "Unit")))
                    for _ in range(count)]
            # "Then ready two of them." The tokens are indistinguishable, so
            # which two is arithmetic rather than a choice -- see `Op.ready_n`.
            for _r in made[:op.ready_n]:
                state.perms[_r, P_READY] = 1
            log["tokens"] = made
            if made:
                state.last_token = made[0]
                state.last_token_n = len(made)
            # 187 -- a token is PLAYED, so "when you play a token unit" sees it.
            # Missing this would have made Lillia blind to the token deck she
            # exists to reward.
            if table.is_type(card, "Unit"):
                for _row in made:
                    chain.fire_play_unit(state, table, tok_seat, card, _row)
            # Zilean - Time Mage: "Once each turn, if you would play a TOKEN
            # UNIT while I'm AT A BATTLEFIELD, you may play that token and an
            # additional copy of it instead." Offered rather than applied --
            # the extra body can break an "alone" clause (740.2.a), so it is a
            # real choice and not a strictly better one.
            #
            # The offer is deferred to after this resolution finishes, which
            # costs no ordering: every token-creating op in the pool is its
            # card's last, asserted at import in `effects.py`.
            if table.is_type(card, "Unit") and state.pend_double[0] < 0:
                for z in range(state.n_perms):
                    zr = state.perms[z]
                    if (zr[P_ALIVE] == 1 and int(zr[P_CTRL]) == tok_seat
                            and is_battlefield(int(zr[P_LOC]))
                            and table.names[int(zr[P_CARD])] in TOKEN_DOUBLERS
                            and int(state.once_used[z]) != int(state.ply)):
                        state.pend_double[:] = (z, card, loc)
                        break
            if op.then_key >= 0 and made:
                # "Then do this: ..." about the token. After Zilean's offer
                # when there is one (`actions._resolve_double` runs it).
                if int(state.pend_double[0]) >= 0:
                    state.pend_then[:] = (op.then_key, source)
                else:
                    _sub = resolve(state, table, cfg,
                                   CardSpec(speed=SPEED_MAIN,
                                            ops=FOLLOWUPS[op.then_key]),
                                   seat, [], -1, True, source=source)
                    log["resolved"].extend(_sub["resolved"])
            # No cleanup here: 321 forbids one while Chain Items are resolving.
            # Arriving units stage a Combat by presence (461); it is initiated
            # by the cleanup the action layer runs once the Chain empties.
        elif op.op == OP_DAMAGE:
            # 143.2.a -- marking damage kills as soon as it is non-zero and at
            # least the unit's current Might. Same continuous check as a Might
            # reduction; combat.mark_damage owns it so there is one code path.
            # `amount`, not `op.n`, so a computed amount ("damage equal to my
            # Might") reaches the damage. No damage op computed one before.
            if combat.mark_damage(state, table, a, amount, seat):
                log.setdefault("killed", []).append(a)
            if op.grenade_bonus:
                state.grenade_hits += 1
        elif op.op == OP_KILL:
            might_then = combat.might(state, table, a)
            combat.destroy(state, table, a)
            # A replaced death (Soraka, Zhonya's, Guardian Angel) is no kill:
            # the unit is still standing, so "the killed unit" that a later
            # instruction measures does not exist and that instruction does
            # nothing (359.3.e.12, RiftJudge #12008 -- Baited Hook plays no
            # unit off the top when Soraka saved the bait).
            if state.perms[a, P_ALIVE] != 1:
                log["killed_might"] = might_then
                log.setdefault("killed", []).append(a)
        elif op.op == OP_DRAW_CONTROLLER:
            # The TARGET's controller draws, not the caster.
            owner = int(state.perms[a, P_CTRL])
            log["drew_opponent"] = phases.draw_for(state, owner, op.n)
        elif op.op == OP_MOVE_TO:
            # `!= -1`: a pseudo-slot (T_SUBJECT, Vex - Mocking's "that
            # battlefield") is negative and still names a unit.
            if op.loc_of_target != -1:
                # "that enemy unit's battlefield" -- the LOCATION of a unit
                # chosen in another slot. Reading the slot as a destination
                # directly would use its permanent ROW as a location id.
                ref = _slot(state, still_legal, op.loc_of_target, source, ctx,
                            seat, subj, ctx2)
                dst = int(state.perms[ref, P_LOC]) if ref >= 0 else -1
            elif op.target_b == T_OWNER_BASE:
                # "to its base" -- the base of whoever controls THIS op's own
                # target, so an enemy unit goes home rather than to ours, and
                # a card moving two units sends each to the right place.
                dst = base_loc(int(state.perms[a, P_CTRL])) if a >= 0 else -1
            else:
                dst = _slot(state, still_legal, op.target_b, source, ctx,
                            seat, subj, ctx2)
                # Every "move ... HERE" in the pool means "to this battlefield"
                # (Azir, Iascylla, Blitzcrank, Fae Porter, Evelynn). A source
                # pushed back to its base has no battlefield left, and moving
                # the units to the BASE instead is not what the card says:
                # Azir sent home by Overzealous Fan takes no tokens anywhere
                # (RiftJudge #9685).
                if op.target_b == T_HERE and dst >= 0 and not is_battlefield(dst):
                    dst = -1
            # 449.1 -- an effect that MOVES is a Move, so "can't move to base"
            # (Determined Sentry, Minotaur Reckoner) stops it. A Recall is not
            # a Move (456.1) and never comes through this op.
            # "THEY can't move it this turn" (Vex - Apathetic) forbids its
            # controller every Move, an effect's included -- but only its
            # controller: an opponent's Charm still moves it (RiftJudge #11532).
            blocked = (dst < 0
                       or (not is_battlefield(dst)
                           and combat.cant_move_to_base(state, table, a))
                       or combat.unmovable_by(state, table, a, seat)  # Jagged Cutlass
                       or (state.has_flag(a, F_NO_MOVE)
                           and seat == int(state.perms[a, P_CTRL])))
            if not blocked:
                log["moved_from"] = int(state.perms[a, P_LOC])
                combat.queue_move_trigger(state, table, a,
                                          int(state.perms[a, P_LOC]), dst)
                state.set_location(a, dst)
            # "Move a friendly unit and ready it": an ignored move is only the
            # move ignored -- the unit still readies (359.3.e.6, RiftJudge #11771).
            if op.then_ready and not combat.ready_blocked(state, table, a):
                woke = int(state.perms[a, P_READY]) == 0
                state.perms[a, P_READY] = 1
                if woke:
                    from rl.engine.effects import TR_READIED
                    chain.fire_watchers(state, table,
                                        int(state.perms[a, P_CTRL]),
                                        TR_READIED, subj=a)
            if blocked:
                log["fizzled"].append(op.op)
                continue
            log["moved"] = (a, dst)
            if seat >= 0 and int(state.perms[a, P_CTRL]) != seat:
                chain.fire_watchers(state, table, seat, TR_MOVED_ENEMY, subj=a)
            # Staged, not initiated -- see the note in OP_CREATE_TOKEN.
        elif op.op == OP_RETURN_TO_HAND:
            # "to its OWNER's hand" -- what every bounce in the pool prints,
            # and the variable was already named `owner` while reading P_CTRL.
            combat.return_to_hand(state, table, a)
            log.setdefault("returned", []).append(a)
        elif op.op == OP_TRASH_TO_HAND:
            # `a` is a packed (owner, card), not a permanent row -- see the
            # TK_TRASH_CARD note in effects.py.
            if op.self_card:
                n_t = int(state.n_trash[seat])
                a = (pack_trash(seat, card) if card >= 0 and seat >= 0 and
                     np.count_nonzero(state.trash[seat, :n_t] == card) else -1)
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            # To the OWNER's hand, not the caster's. Shadows of the Past says
            # "to their owners' hands" and means it: raising an opponent's unit
            # hands it back to them, which is why the card is a symmetric
            # rebuild and not a theft.
            h = int(state.n_hand[owner])
            assert h < state.hand.shape[1], "hand overflow"
            state.hand[owner, h] = card
            state.n_hand[owner] = h + 1
            log.setdefault("from_trash", []).append(table.names[card])
        elif op.op == OP_RECYCLE_FROM_TRASH:
            # 416.1.c -- "each player recycles to their own Main Deck",
            # regardless of who was instructed to perform the Recycle. So this
            # reads the owner off the packed target rather than using `seat`;
            # Forge of the Future recycling an opponent's card puts it on the
            # bottom of THEIR deck, which is a mill answer rather than a steal.
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            state.recycle_card(owner, card)
            log.setdefault("recycled", []).append(table.names[card])
        elif op.op == OP_PLAY_FROM_TRASH:
            # 349 -- this PLAYS the card. It is not moved to the board and it is
            # not resolved here: it goes on the Chain as a new Pending Item and
            # takes its own priority windows, which is why the opponent can
            # counter what Fizz digs up. `actions._advance_pending` picks it up
            # after this resolution finishes (340.3).
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            assert owner == seat, "playing from another player's trash"
            # Re-checked HERE, not just at finalization -- a priority window
            # stood between the two and the board has moved. See
            # `can_play_from_trash`.
            if not can_play_from_trash(state, table, seat, card, op.cost):
                log["fizzled"].append(op.op)
                continue
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            chain.push(state, card, seat, from_hand=False, bound_bf=-1,
                       cost=op.cost, dest=op.dest)
            log.setdefault("played_from_trash", []).append(table.names[card])
        elif op.op == OP_PLAY_UNIT_FROM_TRASH:
            # A unit, not a spell, so 337.2 resolves it IMMEDIATELY -- no chain
            # item, nothing to respond to, and therefore no destination to
            # record. It goes on the board instead, which is why this needs a
            # location where `OP_PLAY_FROM_TRASH` needs a `dest`.
            if op.self_card:
                # "...to play ME": the resolving card, if it is still in the
                # trash it was discarded to.
                n_t = int(state.n_trash[seat])
                a = (pack_trash(seat, card) if card >= 0 and seat >= 0 and
                     np.count_nonzero(state.trash[seat, :n_t] == card) else -1)
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, card = unpack_trash(a)
            assert owner == seat, "playing from another player's trash"
            # "Reduce its Energy cost by the Might of the unit you recycled"
            # (Rumble - Hotheaded) -- read before that unit leaves.
            _ref = (_slot(state, still_legal, op.n_from_might, source, ctx,
                          seat, subj, ctx2) if op.n_from_might != -1 else -1)
            _disc = (combat.might(state, table, _ref)
                     if _ref >= 0 and state.perms[_ref, P_ALIVE] == 1 else 0)
            if not can_play_from_trash(state, table, seat, card, op.cost, _disc):
                log["fizzled"].append(op.op)
                continue
            dst = _slot(state, still_legal, op.target_b, source, ctx,
                        seat, subj, ctx2)
            # The destination was chosen at finalization and a response window
            # has passed since. If that Battlefield is no longer this seat's,
            # 806.3 no longer permits it -- but the base always does, and the
            # play itself is not optional, so it lands there rather than
            # fizzling a card the player already committed to.
            if dst < 0 or (is_battlefield(dst)
                           and int(state.bf_ctrl[bf_index(dst)]) != seat):
                dst = base_loc(seat)
            if not take_from_trash(state, owner, card):
                log["fizzled"].append(op.op)
                continue
            _pay_trash_play(state, table, seat, card, op.cost, _disc)
            # 349 -- a PLAY, so it counts for [Legion], fires play watchers and
            # honours its own "I enter ready" exactly as a hand play does. It
            # used to be added to the board and nothing else. OWNED by whoever's
            # trash it came from, controlled by the player who played it.
            combat.record_effect_play(state, table, seat, card, dst, owner,
                                      free_costs=op.cost == COST_FREE)
            log.setdefault("played_from_trash", []).append(table.names[card])
        elif op.op == OP_GRANT_KEYWORD:
            # 143.2.a again: granting [Shield 3] can only ever help, but
            # granting [Temporary] schedules a death and granting nothing at
            # all is still a legal resolution. The Might-relevant keywords go
            # through `combat.might` on the next read, so no re-check is owed
            # here -- Assault and Shield only apply during a Combat, and
            # `combat_role_bonus` is derived rather than stored.
            idx = GRANT_IDX.get(op.keyword)
            assert idx is not None, f"{op.keyword!r} is not grantable"
            arr = state.kw_grant_turn if op.grant_this_turn else state.kw_grant
            arr[a, idx] += max(1, amount)
            log.setdefault("granted", []).append((a, op.keyword))
        elif op.op == OP_GRANT_KEYWORD_ALL:
            # "Give your other units here [Shield] this turn" (Chakram
            # Dancer) -- the sweep form, scoped by `at`/`who`/`except_target`.
            idx = GRANT_IDX.get(op.keyword)
            assert idx is not None, f"{op.keyword!r} is not grantable"
            arr = state.kw_grant_turn if op.grant_this_turn else state.kw_grant
            for i in _sweep(state, table, op, seat, still_legal, source, ctx,
                            subj, ctx2):
                arr[i, idx] += max(1, amount)
                log.setdefault("granted", []).append((i, op.keyword))
        elif op.op == OP_WEAPONMASTER:
            # 821.1.c -- pay the (discounted) Equip cost, then attach the
            # Equipment to the unit with Weaponmaster. Unpayable now (the
            # response window spent the runes) -> it stays put (821.1.c.5).
            from rl.engine.effects import weaponmaster_cost
            from rl.engine.cost import plan_ability_cost, pay_ability_cost
            if source < 0 or state.perms[source, P_ALIVE] != 1 or a < 0:
                log["fizzled"].append(op.op)
                continue
            cost = weaponmaster_cost(state, table, seat, a)
            gcard = int(state.perms[a, P_CARD])
            recycle = (plan_ability_cost(state, table, seat, gcard, cost[0],
                                         cost[1]) if cost is not None else None)
            if recycle is None or int(state.xp[seat]) < cost[2]:
                log["fizzled"].append(op.op)
                continue
            pay_ability_cost(state, table, seat, cost[0], recycle, cost[1], gcard)
            state.xp[seat] -= cost[2]
            state.attach(a, source)
            log["attached"] = (a, source)
            _queue_equipped(state, table, source)
        elif op.op == OP_PLAY_FROM_HAND:
            state.pend_hand_play = seat
            state.hp_types = 0
            for _t in op.pick_types:
                state.hp_types |= LOOK_TYPE_BIT[_t]
            state.hp_tag = 1 if op.tag == "Equipment" else -1
            state.hp_max_energy = op.level
            state.hp_cost = op.cost
            state.hp_discount = op.n
            if op.target_b == T_MY_BASE:
                state.hp_dest = -1
            elif op.target_b == -2:
                state.hp_dest = -2
            else:
                state.hp_dest = _slot(state, still_legal, op.target_b, source,
                                      ctx, seat, subj, ctx2)
            state.hp_attach = source if op.attach_to_source else -1
            from rl.config import ALL_KEYWORDS as _AK
            state.hp_kw = _AK.index(op.keyword) if op.keyword else -1
            state.hp_spells = int(op.play_spells)
            state.hp_optional = int(op.pick_optional)
            state.hp_pick = -1
            from rl.engine.actions import hand_play_choices
            if not hand_play_choices(state, table, seat):
                state.pend_hand_play = -1          # nothing playable: nothing asked
            log["hand_play"] = int(state.pend_hand_play)
        elif op.op == OP_NEXT_SPELL_BONUS:
            state.next_spell_bonus_ply[seat] = int(state.ply)
        elif op.op == OP_NEXT_SPELL_REPEAT:
            state.next_spell_repeat_ply[seat] = int(state.ply)
        elif op.op == OP_GRANT_MY_KEYWORDS:
            # "Give another friendly unit my keywords" (Kato the Arm): every
            # grantable keyword the source has, at its current value.
            if source >= 0 and state.perms[source, P_ALIVE] == 1:
                for kw, idx in GRANT_IDX.items():
                    v = combat.perm_kw(state, table, source, kw)
                    if v:
                        state.kw_grant_turn[a, idx] += v
        elif op.op == OP_TOGGLE_ATTACH:
            # Angle Shot -- attach that Equipment to that unit, or detach it
            # if it is already attached to it.
            g = _slot(state, still_legal, op.target_b, source, ctx, seat, subj, ctx2)
            if g < 0 or state.perms[g, P_ALIVE] != 1:
                log["fizzled"].append(op.op)
                continue
            if int(state.perms[g, P_ATTACHED_TO]) == a:
                state.detach(g)
                log["detached"] = g
            else:
                state.attach(g, a)
                _queue_equipped(state, table, a)
                log["attached"] = (g, a)
        elif op.op == OP_DETACH_THIS:
            # "Unattach this" from an Equipment's own ability: the gear with the
            # resolving card that is attached to the source.
            for g in state.attachments(source) if source >= 0 else ():
                if int(state.perms[g, P_CARD]) == card:
                    state.detach(g)
                    log["detached"] = int(g)
                    break
        elif op.op == OP_DAMAGE_SHIELD:
            ply = int(state.ply)
            if op.n < 0:
                state.block_next_ply[a] = ply
            else:
                # 437.5.a -- a second Prevent adds its value to the first.
                held = int(state.shield_amt[a]) if int(state.shield_ply[a]) == ply else 0
                state.shield_ply[a] = ply
                state.shield_amt[a] = held + op.n
        elif op.op == OP_DOUBLE_DAMAGE:
            state.double_dmg_ply[a] = int(state.ply)
        elif op.op == OP_BANISH_ON_DEATH:
            state.banish_death_ply[a] = int(state.ply)
        elif op.op == OP_NEXT_UNIT_READY:
            state.next_unit_ready_ply[seat] = int(state.ply)
        elif op.op == OP_EXTRA_TURN:
            state.extra_turns[seat] += 1
        elif op.op == OP_BANISH_FROM_TRASH:
            # `a` is a packed (owner, card): into its OWNER's Banishment.
            if a < 0:
                log["fizzled"].append(op.op)
                continue
            owner, tc = unpack_trash(a)
            if not take_from_trash(state, owner, tc):
                log["fizzled"].append(op.op)
                continue
            n_b = int(state.n_banished[owner])
            state.banished[owner, n_b] = tc
            state.n_banished[owner] = n_b + 1
            log.setdefault("banished_from_trash", []).append(table.names[tc])
        elif op.op == OP_ADD_ANY_NEXT_MAIN:
            state.pending_add_any[seat] += op.n
        elif op.op == OP_GRANT_FLOW:
            if op.self_card:
                gcard = card
            elif a >= 0:
                gcard = unpack_trash(a)[1]
            else:
                gcard = -1
            if gcard < 0 or seat < 0:
                log["fizzled"].append(op.op)
                continue
            free = [k for k in range(state.flow_grant_card.shape[1])
                    if int(state.flow_grant_card[seat, k]) < 0
                    or int(state.flow_grant_ply[seat, k]) not in (-2, int(state.ply))]
            if not free:
                log["fizzled"].append(op.op)
                continue
            k = free[0]
            state.flow_grant_card[seat, k] = gcard
            if op.grant_this_turn and op.ready:
                state.flow_grant_e[seat, k] = int(table.energy[gcard])
                state.flow_grant_p[seat, k] = int(table.power[gcard])
                state.flow_grant_ply[seat, k] = int(state.ply)
                state.flow_grant_banish[seat, k] = 1
            else:
                state.flow_grant_e[seat, k] = op.n
                state.flow_grant_p[seat, k] = op.power
                state.flow_grant_ply[seat, k] = -2
                state.flow_grant_banish[seat, k] = 0
            log["granted_flow"] = table.names[gcard]
        elif op.op == OP_NAME:
            from rl.engine.effects import tag_vocab, NAME_TAG
            foe = 1 - seat
            opts: list = []
            if op.n == NAME_TAG:
                vocab = tag_vocab(table)
                seen = set()
                for i in range(state.n_perms):
                    if state.perms[i, P_ALIVE] == 1 and int(state.perms[i, P_CTRL]) == foe \
                            and table.is_type(int(state.perms[i, P_CARD]), "Unit"):
                        seen |= set(combat.perm_tags(state, table, i))
                for c in state.trash[foe, :int(state.n_trash[foe])]:
                    if table.is_type(int(c), "Unit"):
                        seen |= set(table.tags[int(c)])
                opts = sorted(vocab.index(t) for t in seen)
            else:
                opts = sorted({int(c) for c in state.trash[foe, :int(state.n_trash[foe])]
                               if table.is_type(int(c), "Spell")})
            opts = opts[:state.name_opts.shape[0]]
            if source < 0 or not opts:
                log["fizzled"].append(op.op)
                continue
            state.name_opts[:] = -1
            state.name_opts[:len(opts)] = opts
            state.n_name_opts = len(opts)
            state.pend_name, state.name_kind, state.name_src = seat, op.n, source
        elif op.op == OP_ZERO_BANISH:
            who = dead_source if dead_source >= 0 else source
            if who < 0:
                log["fizzled"].append(op.op)
                continue
            uc, owner = int(state.perms[who, P_CARD]), int(state.perms[who, P_OWNER])
            if table.is_token(uc) or not take_from_trash(state, owner, uc):
                log["fizzled"].append(op.op)
                continue
            state.banish_card(owner, uc)
            k = int(state.n_zero[seat])
            if k < state.zero_cards.shape[1]:
                state.zero_cards[seat, k], state.zero_owner[seat, k] = uc, owner
                state.n_zero[seat] = k + 1
        elif op.op == OP_ZERO_PLAY:
            for k in range(int(state.n_zero[seat])):
                uc, owner = int(state.zero_cards[seat, k]), int(state.zero_owner[seat, k])
                n_b = int(state.n_banished[owner])
                idx = [i for i in range(n_b) if int(state.banished[owner, i]) == uc]
                if not idx:
                    continue
                j = idx[-1]
                state.banished[owner, j:n_b - 1] = state.banished[owner, j + 1:n_b].copy()
                state.banished[owner, n_b - 1] = -1
                state.n_banished[owner] = n_b - 1
                combat.record_effect_play(state, table, seat, uc, base_loc(seat), owner)
            state.zero_cards[seat, :] = -1
            state.zero_owner[seat, :] = -1
            state.n_zero[seat] = 0
            if source >= 0 and state.perms[source, P_ALIVE] == 1:
                combat.banish(state, table, source)
        elif op.op == OP_ENDLESS_RICHES:
            for j in range(int(state.n_hand[seat])):
                state.banish_card(seat, int(state.hand[seat, j]))
            state.hand[seat, :] = -1
            state.n_hand[seat] = 0
            for j in range(int(state.n_trash[seat])):
                state.banish_card(seat, int(state.trash[seat, j]))
            state.trash[seat, :] = -1
            state.n_trash[seat] = 0
            state.riches_on[seat] += 1
            log["burned"] = phases.burn(state, seat, 7)
        elif op.op == OP_ACTIVATE_CONQUERS:
            # Reckoner's Arena. Queued rather than resolved inline: a conquer
            # effect is a triggered ability and belongs on the Chain, where it
            # can be responded to like the real thing (383.3).
            from rl.engine.effects import TR_CONQUER as _TRC
            from rl.engine.effects import row_abilities as _row_abs
            if ctx >= 0:
                # The "conquest" these re-run is of a battlefield its holder
                # already controlled, so a condition on the conquest itself
                # sees that: Yone's "when I conquer an OPEN battlefield" does
                # nothing here (RiftJudge #9962/#9922). `bf_prev_ctrl` would
                # otherwise still describe some earlier, real conquest.
                if is_battlefield(ctx):
                    state.bf_prev_ctrl[bf_index(ctx)] = seat
                for _u in state.units_at(ctx, seat):
                    if any(a.trigger == _TRC
                           for a in _row_abs(state, table, int(_u))):
                        chain.queue(state, _TRC, int(_u), ctx)
                        log.setdefault("reactivated", []).append(int(_u))
        elif op.op == OP_UNIT_TAX:
            state.unit_tax_ply[seat] = int(state.ply)
        elif op.op == OP_FREE_HIDE:
            # Guerilla Warfare -- hiding costs nothing for the rest of this
            # turn. "This turn" is a ply and not a round, so the stamp expires
            # when the turn does and never reaches the opponent's.
            state.free_hide_ply[seat] = int(state.ply)
        elif op.op == OP_RECYCLE_RUNE:
            # 416.1.b. Deterministic on purpose: Sigil of the Storm prints
            # "(This doesn't choose anything.)", so there is no decision to
            # offer -- the rune goes from the domain the player holds most of.
            _have = state.runes_in_play(seat)
            for _ in range(max(1, op.n)):
                _have = state.runes_in_play(seat)
                if int(_have.sum()) <= 0:
                    break
                state.recycle_rune(seat, int(np.argmax(_have)))
                log.setdefault("recycled_runes", 0)
                log["recycled_runes"] += 1
        elif op.op == OP_BANISH_SPELL_PILE:
            # "You may banish IT" -- the spell that fired this trigger. 419.4.a
            # fires "when you play a spell" once the spell has RESOLVED, so its
            # effect has already happened and the card is in the trash; that
            # is where it is banished from. (This used to counter it on the
            # Chain, on the old reading that a card is played at finalization.)
            _card = subj
            if _card >= 0 and take_from_trash(state, seat, _card):
                state.banish_card(seat, _card)
                _n = int(state.legend_pile_n[seat])
                if _n < state.legend_pile.shape[1]:
                    state.legend_pile[seat, _n] = _card
                    state.legend_pile_n[seat] = _n + 1
                log["banished_with_legend"] = _card
            # "Then, if there are four spells banished with me, put each in its
            # trash, channel 4 runes, and draw 1."
            if int(state.legend_pile_n[seat]) >= state.legend_pile.shape[1]:
                for _k in range(int(state.legend_pile_n[seat])):
                    _c = int(state.legend_pile[seat, _k])
                    if _c >= 0 and state.unbanish(seat, _c):
                        phases._to_trash(state, seat, _c)
                state.legend_pile[seat, :] = -1
                state.legend_pile_n[seat] = 0
                for _ in range(4):
                    state.channel_one(seat, ready=False)
                log["drew"] = phases.draw_for(state, seat, 1)
                log["legend_pile_paid"] = True
        elif op.op == OP_REPLACE_BF:
            # Ivern - Green Father: "replace THAT battlefield with a Brush
            # battlefield token". The ground changes card while everything
            # standing on it stays -- control, contested status and the units
            # are all properties of the LOCATION, not of the card printed
            # there. What the token replaced is remembered so its own text can
            # put it back when the ground is next scored.
            _loc = ctx if ctx >= 0 else -1
            if _loc >= 0 and is_battlefield(_loc):
                _i = bf_index(_loc)
                _tok = table.id_of(op.tag)
                if int(state.bf_card[_i]) != _tok:
                    state.bf_replaced[_i] = int(state.bf_card[_i])
                    state.bf_card[_i] = _tok
                    log["replaced_bf"] = _i
        elif op.op == OP_RESTORE_BF:
            # The Brush token's own half: put the battlefield it replaced back.
            _loc = ctx if ctx >= 0 else -1
            if _loc >= 0 and is_battlefield(_loc):
                _i = bf_index(_loc)
                if int(state.bf_replaced[_i]) >= 0:
                    state.bf_card[_i] = int(state.bf_replaced[_i])
                    state.bf_replaced[_i] = -1
                    log["restored_bf"] = _i
        elif op.op == OP_DIVINE_JUDGMENT:
            from rl.engine.actions import dj_begin
            dj_begin(state, table, seat)
        elif op.op == OP_PROMISING_FUTURE:
            from rl.engine.actions import pf_open_look, pf_advance
            state.pf_stage, state.pf_first = 1, seat
            state.pf_cards[:] = -1
            if not pf_open_look(state, seat):
                pf_advance(state, table, seat)
        elif op.op == OP_LINK_CONTROL:
            if source >= 0:
                state.ctrl_link[a] = source
        elif op.op == OP_REPLAY_CARD:
            if a < 0 or card < 0:
                log["fizzled"].append(op.op)
                continue
            payer = int(state.perms[a, P_CTRL])
            from rl.engine.cost import plan_wild_power as _pwp, pay_wild_power as _paw
            _rc = _pwp(state, payer, op.power)
            where = next((s_ for s_ in (seat, 1 - seat) if np.count_nonzero(
                state.trash[s_, :int(state.n_trash[s_])] == card)), -1)
            if _rc is None or where < 0:
                log["fizzled"].append(op.op)
                continue
            _paw(state, payer, op.power, _rc)
            take_from_trash(state, where, card)
            chain.push(state, card, payer, from_hand=False, bound_bf=-1,
                       cost=COST_FREE, owner=where if where != payer else -1)
            log["replayed"] = table.names[card]
        elif op.op == OP_GRANT_ABILITY:
            if card >= 0:
                state.granted_card[a] = card
                state.granted_ply[a] = int(state.ply)
        elif op.op == OP_COPY_PREP:
            state.copy_pending = (state.eff_card(a)
                                  if a >= 0 and state.perms[a, P_ALIVE] == 1 else -1)
        elif op.op == OP_BECOME_COPY:
            c = int(state.copy_pending)
            t0, tn = int(state.last_token), int(state.last_token_n)
            if t0 < 0 or (c < 0 and not op.keyword):
                log["fizzled"].append(op.op)
                continue
            # A lost copy target only fails "becomes a copy": the Reflection is
            # still a 0 Might token with Temporary (359.3.e.6, RiftJudge #11726).
            for r in range(t0, min(t0 + tn, state.n_perms)):
                if state.perms[r, P_ALIVE] == 1:
                    if c >= 0:
                        state.copy_of[r] = c
                        state.copy_via[r] = -1
                    if op.keyword:
                        state.kw_grant[r, GRANT_IDX[op.keyword]] += 1
            state.copy_pending = -1
        elif op.op == OP_GAIN_TAG:
            from rl.engine.effects import GRANTABLE_TAGS
            state.tag_grant[a] = GRANTABLE_TAGS.index(op.tag)
        elif op.op == OP_STEAL_SPELL:
            i = chain.index_of_uid(state, a)
            if i < 0:
                log["fizzled"].append(op.op)
                continue
            state.steal_seat, state.steal_uid = seat, a
            if op.power:
                from rl.engine.cost import plan_wild_power
                if plan_wild_power(state, seat, op.power) is None:
                    state.steal_seat, state.steal_uid = -1, -1
                    log["countered_spell"] = chain.counter(state, table, a)
                    continue
                state.steal_stage = 1
            else:
                from rl.engine.actions import steal_control
                steal_control(state, table, seat, a)
            log["steal"] = a
        elif op.op == OP_SARC_BANISH:
            n_t = int(state.n_trash[seat])
            units = [int(c) for c in state.trash[seat, :n_t]
                     if table.is_type(int(c), "Unit")]
            for c in units:
                take_from_trash(state, seat, c)
                state.banish_card(seat, c)
                k = int(state.n_sarc[seat])
                if k < state.sarc_cards.shape[1]:
                    state.sarc_cards[seat, k] = c
                    state.n_sarc[seat] = k + 1
            log["sarc_banished"] = len(units)
        elif op.op == OP_SARC_PLAY:
            if int(state.n_sarc[seat]) <= 0:
                log["fizzled"].append(op.op)
                continue
            state.rp_seat, state.rp_owner, state.rp_card = seat, seat, -1
            state.rp_cost, state.rp_discount, state.rp_power = COST_PRINTED, 0, 0
            state.rp_here, state.rp_empower, state.rp_zone = -1, 0, 0
            state.rp_from_sarc = 1
        elif op.op == OP_FREE_GEAR:
            state.free_gear_ply[seat] = int(state.ply)
        elif op.op == OP_ARMORY:
            state.armory_ply[a] = int(state.ply)
        elif op.op == OP_PAY_ANY_AMOUNT:
            state.pend_amount = seat
            state.amt_kind = op.n
            state.amt_loc = a if op.target != -1 else -1
            state.amt_spell = int(card >= 0 and source < 0)
            log["amount_choice"] = seat
        elif op.op == OP_ADD_SPELL_ENERGY:
            # 135.2.e.4 -- an [Add] may restrict what its resource pays for.
            # `op.level` names the restriction; the Energy and the (wildcard)
            # Power go into that column of the restricted pools.
            if op.n:
                state.pool_rstr_e[seat, op.level] += op.n
            if op.power:
                state.pool_rstr_p[seat, op.level] += op.power
        elif op.op == OP_DETACH_ONE:
            for g in state.attachments(a):
                if "Equipment" in table.tags[int(state.perms[g, P_CARD])]:
                    state.detach(g)
                    log["detached"] = int(g)
                    break
        elif op.op == OP_SPLIT_DAMAGE:
            if op.n_from_might != -1:
                ref = _slot(state, still_legal, op.n_from_might, source, ctx,
                            seat, subj, ctx2)
                total = combat.might(state, table, ref) if ref >= 0 else 0
            else:
                total = op.n
            state.split_loc = (source_loc(state, source) if op.at == T_HERE
                               else -1)
            if op.at == T_HERE and state.split_loc < 0:
                log["fizzled"].append(op.op)
                continue
            state.split_left = total
            state.split_xp = int(op.xp_per_kill)
            state.split_spell = int(card >= 0 and source < 0)
            state.split_alloc[:] = 0
            state.pend_split = seat if total > 0 else -1
            from rl.engine.actions import split_candidates
            if state.pend_split >= 0 and not split_candidates(state, table):
                state.pend_split = -1
            log["split"] = total
        elif op.op == OP_RECYCLE_TRASH_ALL:
            while int(state.n_trash[seat]) > 0:
                c = int(state.trash[seat, 0])
                take_from_trash(state, seat, c)
                state.recycle_card(seat, c)
        elif op.op == OP_PAY_POWER:
            if not _pay_domain_power(state, seat, op.domain, op.n):
                log["fizzled"].append(op.op)
        elif op.op == OP_ASK:
            # Suspends for another player's yes/no; see `actions._finish_ask`.
            if op.target != -1 and a < 0:
                log["fizzled"].append(op.op)
                continue
            _payer = (int(state.perms[a, P_OWNER if op.ask_owner else P_CTRL])
                      if a >= 0 else seat)
            if op.domain < 0 and op.power:
                from rl.engine.cost import plan_wild_power as _pwp
                _cant = _pwp(state, _payer, op.power) is None
            else:
                _cant = bool(op.power) and not _can_pay_domain_power(
                    state, _payer, op.domain, op.power)
            if _cant:
                # Nothing to decide: "you may pay" with no way to pay.
                if op.ask_no_key >= 0 and FOLLOWUPS[op.ask_no_key]:
                    _sub = resolve(state, table, cfg,
                                   CardSpec(speed=SPEED_MAIN,
                                            ops=FOLLOWUPS[op.ask_no_key]),
                                   seat, [], -1, True, source=source, subj=a)
                    log["resolved"].extend(_sub["resolved"])
                continue
            if a >= 0:
                asked = int(state.perms[a, P_OWNER if op.ask_owner else P_CTRL])
            elif op.who == W_FRIENDLY:
                asked = seat
            else:
                asked = 1 - seat
            state.pend_ask = asked
            state.pend_ask_caster = seat
            state.pend_ask_yes = op.then_key
            state.pend_ask_no = op.ask_no_key
            state.pend_ask_subj = a
            state.pend_ask_card = card
            log["asked"] = asked
        elif op.op == OP_TO_DECK:
            # To its OWNER's Main Deck; a token ceases to exist (185.3).
            owner, pc = int(state.perms[a, P_OWNER]), int(state.perms[a, P_CARD])
            combat.queue_leaves_board(state, table, a)
            state.perms[a, P_ALIVE] = 0
            if not table.is_token(pc):
                if op.pick_dest == DEST_TOP:
                    state.put_on_top(owner, pc)
                else:
                    state.recycle_card(owner, pc)
            log["to_deck"] = a
        elif op.op == OP_REVEAL_TOP:
            ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
            if ptr >= end:
                log["fizzled"].append(op.op)          # nothing to reveal
                continue
            rc = int(state.deck[seat, ptr])
            _run_revealed_abilities(state, table, cfg, seat, rc, log)
            if any(table.is_type(rc, t) for t in op.pick_types):
                log.setdefault("drew", []).extend(phases.draw_for(state, seat, 1))
            else:
                state.deck_ptr[seat] = ptr + 1
                if op.rest_dest == DEST_RECYCLE:
                    state.recycle_card(seat, rc)
                else:
                    phases._to_trash(state, seat, rc, from_deck=True)
                log["reveal_missed"] = True
            log["revealed"] = rc
        elif op.op == OP_BUFF_BONUS_TURN:
            if int(state.buff_bonus_ply[seat]) != int(state.ply):
                state.buff_bonus_n[seat] = 0
            state.buff_bonus_ply[seat] = int(state.ply)
            state.buff_bonus_n[seat] += 1
        elif op.op == OP_BASE_MIGHT:
            # "Its base Might becomes 5 this turn" (Dragon Form).
            state.base_might_ply[a] = int(state.ply)
            state.base_might_val[a] = op.n
            combat.enforce_lethal(state, table)
        elif op.op == OP_TAKE_CONTROL:
            # 718.5 -- control changes; ownership never does. Recalled to the
            # NEW controller's base when the card says so (Possession), readied
            # where it stands when it says that (Hostile Takeover), and handed
            # back at end of turn when the effect is temporary.
            _new = (1 - seat) if op.who == W_ENEMY else seat
            state.perms[a, P_CTRL] = _new
            if op.to_base:
                state.set_location(a, base_loc(_new))
            if op.then_ready and not combat.ready_blocked(state, table, a):
                # 415.1 -- readying it is a real ready, and by now `_new`
                # controls it, so "when you ready me" belongs to the taker
                # (191.4.a: Irelia, Fervent gets her +1 off Hostile Takeover).
                # A unit that was already ready is not readied again (415.1.c).
                woke = int(state.perms[a, P_READY]) == 0
                state.perms[a, P_READY] = 1
                if woke:
                    from rl.engine.effects import TR_READIED
                    chain.fire_watchers(state, table, _new, TR_READIED, subj=a)
            if op.then_exhaust:
                state.perms[a, P_READY] = 0
            if op.eot_revert:
                state.eot_ply[a] = int(state.ply)
                state.eot_kind[a] = EOT_REVERT_CONTROL
            log["took_control"] = a
        elif op.op == OP_MARK:
            # "When it dies / wins a combat this turn, ..." -- arm this card's
            # Delayed Ability and point it at the unit.
            slot = chain.arm_delayed(state, seat, card) if card >= 0 else -1
            if slot < 0 or a < 0:
                log["fizzled"].append(op.op)
                continue
            state.mark_ply[a] = int(state.ply)
            state.mark_slot[a] = slot
            state.mark_seat[a] = seat
        elif op.op == OP_DEATH_SHIELD:
            state.death_shield_ply[a] = int(state.ply)
        elif op.op == OP_GUILLOTINE:
            state.guillotine_ply[a] = int(state.ply)
        elif op.op == OP_MOVE_ALL_TO_BASE:
            # Each unit is moved to ITS OWN controller's base -- a Move, so
            # "can't move to base" and Jagged Cutlass both get a say, and each
            # one's move triggers fire.
            movers = _sweep(state, table, op, seat, still_legal, source, ctx,
                            subj, ctx2)
            for i in movers:
                dst = base_loc(int(state.perms[i, P_CTRL]))
                if combat.cant_move_to_base(state, table, i) \
                        or combat.unmovable_by(state, table, i, seat) \
                        or (state.has_flag(i, F_NO_MOVE)
                            and seat == int(state.perms[i, P_CTRL])):
                    continue
                combat.queue_move_trigger(state, table, i,
                                          int(state.perms[i, P_LOC]), dst)
                state.set_location(i, dst)
                log.setdefault("moved_all", []).append(int(i))
                if seat >= 0 and int(state.perms[i, P_CTRL]) != seat:
                    chain.fire_watchers(state, table, seat, TR_MOVED_ENEMY,
                                        subj=int(i))
        elif op.op == OP_SPEND_BUFF:
            if a >= 0 and state.perms[a, P_ALIVE] == 1 and state.has_flag(a, F_BUFFED):
                chain.spend_buff(state, table, seat, a)
            else:
                log["fizzled"].append(op.op)
        elif op.op == OP_DISCOUNT_NEXT_SPELL:
            state.next_spell_discount[seat] += op.n
        elif op.op == OP_PREVENT_EFFECT_DAMAGE:
            state.no_effect_damage_ply = int(state.ply)
        elif op.op == OP_GAIN_XP:
            # A player resource, not a permanent's. It has no cap and does not
            # reset, which is what makes [Level 11] reachable.
            gain = amount
            if op.n_from_count == CT_MY_UNITS:
                # "1 XP for each friendly unit" (Scrutinizing Sergeant).
                gain = op.n * sum(
                    1 for i in range(state.n_perms)
                    if state.perms[i, P_ALIVE] == 1
                    and int(state.perms[i, P_CTRL]) == seat
                    and table.is_type(int(state.perms[i, P_CARD]), "Unit"))
            state.xp[seat] += gain
            if gain > 0:
                state.xp_gained_ply[seat] = int(state.ply)
            log["xp"] = int(state.xp[seat])
        elif op.op == OP_COUNTER:
            # Record the controller BEFORE removing the item -- Lilting
            # Lullaby's second op ("its controller can't play spells this
            # turn") runs after the item is already off the chain.
            i = chain.index_of_uid(state, a)
            if i >= 0:
                log["countered_ctrl"] = int(state.chain[i, C_CTRL])
            name = chain.counter(state, table, a,
                                 to_hand=op.counter_to_hand)
            if name is None:
                log["fizzled"].append(op.op)   # already countered by someone else
                continue
            log["countered_spell"] = name
        elif op.op == OP_BURN:
            # [Burn N] -- "put the top N cards of your Main Deck into your
            # trash". Self-mill, and the one keyword that can hand the opponent
            # a point: running the deck out is a Burn Out (431.2), which is why
            # this goes through the same empty-deck path a draw does rather
            # than silently milling zero.
            #
            # `op.who` picks the miller: W_FRIENDLY is the resolving player
            # ("[Burn 2]"), W_ENEMY the opponent ("they [Burn 1]").
            burner = (1 - seat) if op.who == W_ENEMY else seat
            log["burned"] = phases.burn(state, burner, op.n)
            if log["burned"]:
                state.last_burned = int(log["burned"][-1])
        elif op.op == OP_ATTACH:
            # 434.1 / 818.1.b -- link the SOURCE gear to the chosen unit, which
            # becomes its Top-Most Card (818.1.b.2). The source is the gear
            # itself for both routes into this op: its own [Equip] ability and
            # [Quick-Draw]'s play trigger are both printed on the gear.
            #
            # 383.2.c.2 -- an ability whose source has left the board resolves
            # without it. An Equipment killed in response to its own Equip has
            # nothing left to attach, so this fizzles rather than writing a
            # link from a dead row.
            gear = (_slot(state, still_legal, op.target_b, source, ctx, seat,
                          subj, ctx2) if op.target_b != -1 else source)
            if gear < 0 or state.perms[gear, P_ALIVE] != 1 or a < 0 \
                    or state.perms[a, P_ALIVE] != 1 \
                    or "Equipment" not in table.tags[int(state.perms[gear, P_CARD])]:
                log["fizzled"].append(op.op)
                continue
            # 718.5.d allows one Top-Most card at a time, so `attach` MOVES an
            # already-attached Equipment rather than refusing. That is what
            # [Weaponmaster] means by "even if it's already attached".
            # `target_b` names a chosen Equipment instead of the source
            # (Relentless Pursuit).
            if int(state.perms[gear, P_ATTACHED_TO]) == a:
                # 434.1.h -- it is already there, so nothing additional
                # happens: no "when you attach an Equipment to me" trigger and
                # no renewed attach stamp.
                log["resolved"].append(op.op)
                continue
            state.attach(gear, a)
            log["attached"] = (gear, a)
            if table.names[int(state.perms[gear, P_CARD])] in COPY_ON_ATTACH:
                # Shady Spectacles: choose another friendly unit to become.
                owner_seat = int(state.perms[a, P_CTRL])
                opts = sorted({state.eff_card(i) for i in range(state.n_perms)
                               if i != a and state.perms[i, P_ALIVE] == 1
                               and int(state.perms[i, P_CTRL]) == owner_seat
                               and table.is_type(int(state.perms[i, P_CARD]), "Unit")})
                opts = opts[:state.name_opts.shape[0]]
                if opts:
                    state.name_opts[:] = -1
                    state.name_opts[:len(opts)] = opts
                    state.n_name_opts = len(opts)
                    state.pend_name, state.name_kind = owner_seat, NAME_FRIENDLY_UNIT
                    state.name_src = gear
            _queue_equipped(state, table, a)
        elif op.op == OP_DIG_TRASH:
            # "Then you may do this: Choose a unit in their trash and play it,
            # ignoring its cost" (Kharox). A suspend-and-ask, because the pile
            # this reads was filled by an EARLIER op of the same card -- the
            # Burn immediately above it. A target slot is chosen at
            # finalization (355.8) and would read the trash as it stood before
            # the Burn, so it cannot express this at all.
            #
            # Not a target either way: 355.10 -- no count is announced and the
            # opponent cannot respond to the choice.
            owner = (1 - seat) if op.who == W_ENEMY else seat
            state.pend_grave = seat
            state.pend_grave_owner = owner
            state.pend_grave_dest = base_loc(seat)
            log["dig_trash"] = owner
        elif op.op == OP_NO_CARDS:
            # "Opponents can't play cards this turn" (Brynhir). The wider
            # sibling of OP_NO_SPELLS, and unlike that one it takes a SIDE
            # rather than a Chain Item: Lullaby locks the controller of the
            # spell it just countered, this one locks a seat outright.
            locked = (1 - seat) if op.who == W_ENEMY else seat
            state.no_cards[locked] = 1
            log["no_cards"] = locked
        elif op.op == OP_DISCOUNT_NEXT:
            # "Your next card costs {2 energy}{any rune}{any rune} less"
            # (Astral Heron). A promise held on the PLAYER, not a static on a
            # permanent -- so unlike every other cost modification in `cost.py`
            # it survives the source leaving, and unlike a static it is spent
            # by the next card rather than asked afresh each time.
            #
            # 356.4.d applies discounts per component, which is why both halves
            # are carried: `op.n` is the Energy and `op.power` the Power.
            # Accumulated rather than overwritten -- two Herons at two
            # battlefields each promise, and neither cancels the other.
            state.next_discount[seat, 0] += op.n
            state.next_discount[seat, 1] += op.power
            log["discount_next"] = (op.n, op.power)
        elif op.op == OP_ARM_DELAYED:
            # 389-390 -- arm this card's own Delayed Ability for the rest of
            # the turn. Which ability is looked up by the resolving CARD, so
            # the op carries no argument and cannot drift out of sync with
            # `DELAYED_ABILITIES`.
            # `card` is the resolving card, which is what
            # `DELAYED_ABILITIES` is keyed by. Only the Chain passes it -- a
            # sub-resolution has no card of its own -- so an op reaching here
            # without one has nothing to arm.
            if card < 0:
                log["fizzled"].append(op.op)
            else:
                slot = chain.arm_delayed(state, seat, card)
                if slot >= 0:
                    log["armed_delayed"] = slot
        elif op.op == OP_COUNTER_UNLESS_PAYS:
            # "Counter a spell unless its controller pays {N}."
            #
            # The counter is NOT applied here. This suspends for the target's
            # controller to answer, and `actions._finish_tax` counters only if
            # they refuse -- the same shape as OP_DISCARD_CHOOSE, and for the
            # same reason: resolution does not halt at a pending decision, so
            # anything conditional on the answer has to run from the resume
            # path or it runs unconditionally and too early.
            i = chain.index_of_uid(state, a)
            if i < 0:
                # Already countered by something else in this window (359.3.e).
                log["fizzled"].append(op.op)
                continue
            victim = int(state.chain[i, C_CTRL])
            # No decision to offer when they cannot pay: a choice with one
            # option is not a choice, and pending it would ask the policy to
            # "decide" between refusing and refusing. `plan_ability_cost` with
            # power=0 is the affordability question including runes they could
            # still exhaust -- energy already in the pool is not the whole
            # answer, and reading `pool_energy` alone would let a full rune
            # board be taxed out for free.
            from rl.engine.cost import plan_ability_cost as _plan_cost
            if _plan_cost(state, table, victim,
                                 int(state.chain[i, C_CARD]),
                                 op.cost, 0) is None:
                log["countered_ctrl"] = victim
                name = chain.counter(state, table, a)
                if name is not None:
                    log["countered_spell"] = name
                    log["tax_unaffordable"] = victim
                continue
            state.pend_tax = victim
            state.pend_tax_uid = int(a)
            state.pend_tax_cost = int(op.cost)
            log["tax_choice"] = victim
        elif op.op == OP_NO_SPELLS:
            i = chain.index_of_uid(state, a)
            if i >= 0:
                state.no_spells[int(state.chain[i, C_CTRL])] = 1
            else:
                # The item was countered by this same card a moment ago, so its
                # controller is read from the log rather than the chain.
                ctrl = log.get("countered_ctrl")
                if ctrl is not None:
                    state.no_spells[ctrl] = 1
        elif op.op == OP_MODIFY_MIGHT:
            # May kill, but only by meeting damage already marked (143.2.a).
            # Never by reduction alone -- lethal damage must be non-zero.
            if combat.set_might_mod(state, table, a, amount, op.floor):
                log.setdefault("killed_by_might", []).append(a)
        elif op.op == OP_MIGHT_UP_TO:
            # "INCREASE my Might to its Might this turn" (Dame the Despoiler).
            # Only upward: if the chosen unit is smaller, the source's Might
            # is already past it and nothing changes. Both read EFFECTIVE Might
            # at resolution, and the difference goes onto the source's "this
            # turn" modifier -- so it expires with the turn like any pump.
            # `target_b` names the unit RAISED when it is not the source:
            # "increase ITS Might to the Might of another friendly unit"
            # (Convergent Mutation).
            up = (_slot(state, still_legal, op.target_b, source, ctx, seat,
                        subj, ctx2) if op.target_b != -1 else source)
            if up < 0 or state.perms[up, P_ALIVE] != 1:
                log["fizzled"].append(op.op)
                continue
            gap = combat.might(state, table, a) - combat.might(state, table, up)
            if gap > 0:
                combat.set_might_mod(state, table, up, gap, None)
            log["might_up_to"] = max(0, gap)
        elif op.op == OP_FIGHT:
            # "They deal damage equal to their Mights to each other" (Challenge).
            # SIMULTANEOUS: both amounts are read before either is marked, so
            # the first unit dying cannot shrink what it deals. Marking A's
            # damage on B and then reading B's Might off a corpse would let
            # whichever op ran first win every even trade.
            b = _slot(state, still_legal, op.target_b, source, ctx,
                      seat, subj, ctx2)
            if a < 0 or b < 0 or state.perms[a, P_ALIVE] != 1 \
                    or state.perms[b, P_ALIVE] != 1:
                log["fizzled"].append(op.op)
                continue
            dmg_to_b = combat.might(state, table, a)
            dmg_to_a = combat.might(state, table, b)
            # 417.6.b.3/4 -- each unit deals its own damage, charged to its
            # own controller, and none of it is spell damage.
            ctrl_a = int(state.perms[a, P_CTRL])
            ctrl_b = int(state.perms[b, P_CTRL])
            if combat.mark_damage(state, table, b, dmg_to_b, ctrl_a,
                                  unit_source=True):
                log.setdefault("killed", []).append(b)
            if combat.mark_damage(state, table, a, dmg_to_a, ctrl_b,
                                  unit_source=True):
                log.setdefault("killed", []).append(a)
        elif op.op == OP_BANISH:
            # 427 -- Banish is NOT a subset of Kill (427.2.a): no [Deathknell]
            # fires and the card reaches no trash, so it answers a recursion
            # deck in a way killing never does. It IS a leaving, which is what
            # `combat.banish` fires the leaves-board watchers for.
            if a < 0 or state.perms[a, P_ALIVE] != 1:
                log["fizzled"].append(op.op)
                continue
            combat.banish(state, table, a)
            log.setdefault("banished", []).append(a)
        elif op.op == OP_STUN:
            # `stun` returns False on a redundant stun (423.1.a.1), which
            # "when you stun an enemy unit" triggers must not fire on.
            log["stunned"] = log.get("stunned", [])
            if state.stun(a):
                log["stunned"].append(a)
                if seat >= 0:
                    chain.fire_watchers(state, table, seat, TR_STUN, subj=a)
        elif op.op == OP_BLINK:
            # 427 -- Banish, then the OWNER plays it again. Not a kill
            # (427.2.a), so nothing is trashed and no [Deathknell] fires.
            #
            # **The OWNER's, not the banisher's.** Portal Rescue's errata is
            # explicit: "its OWNER plays it to THEIR base". The two come apart
            # once a card is on the board under someone else's control
            # (718.5.f) -- which Kharox now creates -- so this reads `P_OWNER`.
            row = state.perms[a]
            # Portal Rescue's errata is explicit: "its OWNER plays it to THEIR
            # base". So the replay is the owner's, not the banisher's -- which
            # is the difference the moment a card is on the board under someone
            # else's control (718.5.f), and the case Kharox now creates.
            bcard, bctrl = int(row[P_CARD]), int(row[P_OWNER])
            dst = base_loc(bctrl) if op.to_base else int(row[P_LOC])
            if op.target_b != -1:
                # "...plays it to any battlefield" (Thrill of the Hunt).
                _d = _slot(state, still_legal, op.target_b, source, ctx, seat,
                           subj, ctx2)
                if _d >= 0:
                    dst = _d
            combat.banish(state, table, a)
            # The replay is a PLAY, so it is bound by what forbids plays there:
            # Rockfall Path ("units can't be played here", RiftJudge #11673) and
            # the rule that a unit can only be played to its controller's OWN
            # base -- a stolen unit sent to the thief's base cannot come back
            # there (#11767). Either way it simply stays in Banishment.
            if not table.is_token(bcard) and (
                    (is_battlefield(dst) and combat.bf_forbids_play(state, table, dst))
                    or (not is_battlefield(dst) and dst != base_loc(bctrl))):
                log.setdefault("banished", []).append(a)
                log["resolved"].append(op.op)
                continue
            # 427 -- the Banish is real but MOMENTARY: the card is played back
            # in the same breath, so it is taken out of Banishment again rather
            # than left there. Without this it is counted in both zones at once
            # and the conservation gate reads it as a card minted from nothing.
            #
            # Popped rather than skipped, so anything that comes to watch a
            # banish still sees one -- the same reasoning as Nocturne's
            # banish-then-play.
            if not table.is_token(bcard):
                n_b = int(state.n_banished[bctrl])
                assert n_b and int(state.banished[bctrl, n_b - 1]) == bcard, \
                    "blink did not find the card it just banished"
                state.n_banished[bctrl] = n_b - 1
                state.banished[bctrl, n_b - 1] = -1
            if table.is_token(bcard):
                # 186 -- a token in any non-board zone ceases to exist, so it
                # never comes back. Banishing a token is straight removal.
                log.setdefault("banished", []).append(a)
                log["resolved"].append(op.op)
                continue
            # It returns as a NEW object: no damage, no Buff (705), no "this
            # turn" modifiers -- and "its owner PLAYS it", so for a unit the
            # whole play follows: [Legion], play watchers, entry triggers, and
            # its own "I enter ready". A gear keeps the gear default (359.2.d).
            if table.is_type(bcard, "Unit"):
                new = combat.record_effect_play(state, table, bctrl, bcard, dst,
                                                bctrl)
            else:
                new = state.add_permanent(
                    bcard, bctrl, dst,
                    ready=combat.permanent_enters_ready(state, table, bctrl,
                                                        bcard, False),
                    is_unit=False)
                if chain.has_trigger(table, bcard, TR_PLAY_ME):
                    chain.queue(state, TR_PLAY_ME, new, dst)
            log["blinked"] = (a, new)
        elif op.op == OP_BUFF:
            # 426.1.b.1 -- a unit that already has a Buff does not get another,
            # and 426.1.c is explicit that it can still be CHOSEN for the
            # effect. So this is not a targeting restriction; it simply does
            # nothing on an already-buffed unit.
            if (state.perms[a, P_FLAGS] & F_BUFFED
                    and table.names[int(state.perms[a, P_CARD])] in MULTI_BUFF):
                state.extra_buffs[a] += 1            # Lee Sin - Ascetic
                log.setdefault("buffed", []).append(a)
                if seat >= 0:
                    chain.fire_watchers(state, table, seat, TR_BUFFED, subj=a)
            elif not (state.perms[a, P_FLAGS] & F_BUFFED):
                state.perms[a, P_FLAGS] |= F_BUFFED
                log.setdefault("buffed", []).append(a)
                if seat >= 0:
                    chain.fire_watchers(state, table, seat, TR_BUFFED, subj=a)
        elif op.op == OP_BUFF_ALL_AT:
            # `who` / `except_target` narrow it the way they narrow the sweeps:
            # "buff all OTHER FRIENDLY units there" (Peak Guardian).
            spared = (_slot(state, still_legal, op.except_target, source, ctx,
                            seat, subj, ctx2)
                      if op.except_target != -1 else -1)
            _pool = (state.units_at(a) if op.target != -1 else
                     [i for i in range(state.n_perms)
                      if state.perms[i, P_ALIVE] == 1
                      and table.is_type(int(state.perms[i, P_CARD]), "Unit")])
            for i in _pool:
                if int(i) == spared:
                    continue
                mine = int(state.perms[i, P_CTRL]) == seat
                if (op.who == W_FRIENDLY and not mine) or (
                        op.who == W_ENEMY and mine):
                    continue
                if not (state.perms[i, P_FLAGS] & F_BUFFED):
                    state.perms[i, P_FLAGS] |= F_BUFFED
                    log.setdefault("buffed", []).append(int(i))
                    if seat >= 0:
                        chain.fire_watchers(state, table, seat, TR_BUFFED,
                                            subj=int(i))
        elif op.op == OP_ADD_ENERGY:
            state.pool_energy[seat] += op.n
        elif op.op == OP_ADD_POWER:
            state.pool_power[seat, op.domain] += op.n
        elif op.op == OP_RECYCLE_SELF:
            # "Recycle me." A Deathknell resolves with its card already in the
            # trash (808.1.d.2 puts the ability on the Chain before the card
            # moves), so this lifts it back out of the pile rather than off the
            # board. 416.1.c -- to its OWNER's deck, which for a Deathknell is
            # the seat whose trash it is sitting in.
            # `dead_source`, not `source`: 383.2.c.2 blanks a source that has
            # left the board, and a Deathknell's source is dead by definition.
            # "Recycle ME" is one of the few things a corpse is still the
            # authority on -- it names a card, not a board position -- so this
            # reads the row that was kept for exactly that purpose.
            who = source if source >= 0 else dead_source
            if who >= 0:
                card = int(state.perms[who, P_CARD])
                n = int(state.n_trash[seat])
                for k in range(n - 1, -1, -1):        # newest first: it is
                    if int(state.trash[seat, k]) == card:   # the one just added
                        state.trash[seat, k:n - 1] = state.trash[seat, k + 1:n]
                        state.trash[seat, n - 1] = -1
                        state.n_trash[seat] = n - 1
                        if not table.is_token(card):
                            state.recycle_card(seat, card)
                        log["recycled_self"] = table.names[card]
                        break
        elif op.op == OP_DISCARD_CHOOSE:
            # Suspend for the player to pick WHICH card. The branch its type
            # selects is applied by `actions._finish_discard`.
            #
            # **Anything that must happen AFTER the discard goes in `then_key`,
            # not in a following op.** Resolution does not stop here -- it sets
            # the pending decision and carries on down the op list -- so Zaun
            # Warrens' "discard 1, THEN draw 1" written as two ops drew first
            # and made the fresh card discardable, which is the opposite of
            # what it says. The follow-up runs from `_finish_discard`, once the
            # card is actually gone.
            if int(state.n_hand[seat]) > 0:
                state.pend_discard = seat
                state.pend_discard_ops = op.branch_key
                state.pend_discard_src = source
                state.pend_discard_tgt = a
                if op.then_key >= 0:
                    state.pend_then[:] = (op.then_key, source)
                log["discard_choice"] = seat
            else:
                # An empty hand discards nothing -- but "then draw 1" is
                # sequencing, not a condition, so the follow-up still runs.
                # Inline rather than deferred: there is no decision to wait for.
                log["discard_choice"] = -1
                if op.then_key >= 0 and FOLLOWUPS[op.then_key]:
                    _sub = resolve(state, table, cfg,
                                   CardSpec(speed=SPEED_MAIN,
                                            ops=FOLLOWUPS[op.then_key]),
                                   seat, [], -1, True, source=source)
                    log["resolved"].extend(_sub["resolved"])
        elif op.op == OP_READY_LEGEND:
            # "Ready your legend" (Hall of Legends). A legend is a Game Object
            # that exhausts to pay for its own ability, so readying it buys a
            # second use in one turn -- and the cards that say it are all
            # optional and all cost something, which is the tell that a second
            # activation is meant to be worth paying for.
            #
            # A no-op on a legend that is already ready, and on a seat with no
            # legend at all (a random-pool deal has none). Neither is an error:
            # 415 readies what is able to be readied and says nothing about the
            # rest.
            _ls = (1 - seat) if op.who == W_ENEMY else seat
            log["readied_legend"] = bool(state.legend[_ls] >= 0
                                         and not state.legend_ready[_ls])
            if state.legend[_ls] >= 0:
                state.legend_ready[_ls] = 1
        elif op.op == OP_EXHAUST_LEGEND:
            _ls = (1 - seat) if op.who == W_ENEMY else seat
            if state.legend[_ls] >= 0:
                state.legend_ready[_ls] = 0
        elif op.op == OP_REVEAL_RUNE:
            # Reveal the top rune and recycle it (to the bottom of the ring);
            # what it does next is its own Chain Item, by domain.
            if int(state.rune_left[seat]) <= 0:
                log["fizzled"].append(op.op)
                continue
            from rl.engine.state import RUNE_RING
            h = int(state.rune_head[seat])
            dom = int(state.rune_deck[seat, h])
            left = int(state.rune_left[seat])
            state.rune_head[seat] = (h + 1) % RUNE_RING
            state.rune_deck[seat, (h + left) % RUNE_RING] = dom
            log["revealed_rune"] = dom
            if source >= 0:
                chain.queue(state, TR_RUNE_BODY + dom, source,
                            int(state.perms[source, P_LOC]))
        elif op.op == OP_WIN:
            # "You win the game." Terminal at once (`actions.terminal`).
            if seat >= 0:
                state.winner = seat
                log["won"] = seat
        elif op.op == OP_MIGHT_THIS_COMBAT:
            amount = (combat.might(state, table, a) if op.n_from_might != -1
                      else op.n)
            if int(state.combat_might_ply[a]) != int(state.ply):
                state.combat_might_ply[a] = int(state.ply)
                state.combat_might_val[a] = 0
            state.combat_might_val[a] += amount
        elif op.op == OP_READY_RUNES and op.at_end_of_turn:
            # "Ready 2 runes AT THE END OF THIS TURN" (Targon's Peak). Banked
            # rather than performed: `phases.ending` pays it out. The promise
            # is what the card is worth -- it is made the moment the
            # battlefield is conquered, so the runes spent taking it come back
            # before the opponent's turn rather than after.
            state.pending_ready_runes[seat] += op.n
            log["ready_runes_pending"] = op.n
        elif op.op == OP_READY_RUNES and op.n_less_filled:
            # "Ready up to 4 units, gear, and/or runes" -- whatever the
            # permanent slots did not use goes to runes, which are
            # interchangeable, so there is nothing further to choose.
            left = op.n - sum(1 for k, x in enumerate(still_legal)
                              if x >= 0 and k < spec.n_targets
                              and spec.targets[k].kind == TK_UNIT)
            for dom in np.argsort(-state.runes_spent[seat]):
                if left <= 0:
                    break
                take = min(left, int(state.runes_spent[seat, dom]))
                state.runes_spent[seat, dom] -= take
                state.runes_ready[seat, dom] += take
                left -= take
        elif op.op == OP_RETURN_FACEDOWN:
            # The facedown card at that battlefield, to its OWNER's hand.
            i = bf_index(a) if a >= 0 and is_battlefield(a) else -1
            # The FIRST facedown card there. A battlefield holds one (107.3.f)
            # unless it is Bandle Tree, and "the facedown card at that
            # battlefield" names one card either way -- the older of the two,
            # which is the lower slot.
            k = next((s for s in fd_slots(i) if int(state.fd_card[s]) >= 0),
                     -1) if i >= 0 else -1
            if k < 0:
                log["fizzled"].append(op.op)
                continue
            owner, fc = int(state.fd_owner[k]), int(state.fd_card[k])
            h = int(state.n_hand[owner])
            assert h < state.hand.shape[1], "hand overflow"
            state.hand[owner, h] = fc
            state.n_hand[owner] = h + 1
            state.fd_card[k] = -1
            state.fd_owner[k] = -1
            state.fd_ply[k] = -1
            log["returned_facedown"] = table.names[fc]
        elif op.op == OP_READY_RUNES:
            # "Ready up to N runes." A rune readies by moving from spent back
            # to ready -- the same direction the Awaken Phase moves them, just
            # bounded. "Up to" and there is nothing to choose between: runes of
            # a domain are interchangeable (which is why they are counts and
            # not objects), so readying the most-held domain first is not a
            # choice being taken away from anyone.
            left = op.n
            for dom in np.argsort(-state.runes_spent[seat]):
                if left <= 0:
                    break
                take = min(left, int(state.runes_spent[seat, dom]))
                state.runes_spent[seat, dom] -= take
                state.runes_ready[seat, dom] += take
                left -= take
            log["readied_runes"] = op.n - left
        elif op.op == OP_SWAP_MIGHT:
            b = _slot(state, still_legal, op.target_b, source, ctx,
                      seat, subj, ctx2)
            if b < 0 or a == b or state.perms[b, P_ALIVE] != 1:
                log["fizzled"].append(op.op)
                continue
            # Swap the EFFECTIVE Mights, which is what the card says -- statics
            # and buffs included, not the printed corners. Expressed through
            # the turn-scoped modifier, so it expires with the turn and
            # `set_might_mod` re-checks lethality for both (143.2.a): swapping
            # a big unit's Might onto a damaged small one can kill it at once.
            ma = combat.might(state, table, a)
            mb = combat.might(state, table, b)
            if ma != mb:
                # `set_might_mod` takes a DELTA. Passing the old modifier plus
                # the difference counted an earlier "+1 this turn" twice
                # (Irelia, Fervent chosen by this Switcheroo, RiftJudge #11861).
                # Mel, Newly Awakened (Empowered): the DECREASE half is a -Might
                # given to a unit the spell chose, so it gets 1 more; the
                # increase half is untouched (433.1.a/b, RiftJudge #12520).
                ward = _ward_count(state, table, seat) if seat >= 0 else 0

                def _swap_delta(x: int, delta: int) -> int:
                    if delta >= 0:
                        return delta
                    # Gangplank, Naval (Empowered): the decrease is a -Might
                    # given to a unit the spell chose -> +3 instead (#11757).
                    if (table.names[int(state.perms[x, P_CARD])]
                            in EMPOWERED_CHOSEN_TO_MIGHT and state.empower_count(x)):
                        return 3
                    return delta - ward
                combat.set_might_mod(state, table, a, _swap_delta(a, mb - ma))
                combat.set_might_mod(state, table, b, _swap_delta(b, ma - mb))
            log["swapped_might"] = (a, b)
        elif op.op == OP_ANY_DAMAGE_KILLS:
            state.any_damage_kills = 1
            log["any_damage_kills"] = True
        elif op.op == OP_UNCHOOSABLE_TURN:
            if a >= 0 and state.perms[a, P_ALIVE] == 1:
                state.set_flag(a, F_UNCHOOSABLE_TURN)
        elif op.op == OP_NO_MOVE:
            # "They can't move it this turn." Turn-scoped, cleared by the same
            # end-of-turn sweep as [Stun].
            if a >= 0 and state.perms[a, P_ALIVE] == 1:
                state.set_flag(a, F_NO_MOVE)
                log["no_move"] = a
        elif op.op == OP_EACH_KILLS_OWN:
            # Open the sequential choice; the action layer walks the seats.
            # Starting with the resolving player, which is the turn order the
            # rules default to for "each player".
            # Skip straight past any seat with no unit to kill -- "each
            # player kills one of their units" asks nothing of a player who
            # has none, and an empty decision point would deadlock the turn.
            # Which TYPE is killed is the op's, not this branch's: Cull the
            # Weak takes units and Acceptable Losses takes gear, and every
            # site that walks the cull has to ask the same question.
            want = op.card_type or "Unit"
            state.pend_cull_type = CARD_TYPES.index(want)
            state.pend_cull_mode = op.cull_mode
            dest = (_slot(state, still_legal, op.target_b, source,
                          ctx, seat, subj, ctx2)
                    if op.target_b != -1 else -1)
            # "The defender must kill one of their units HERE" -- with the
            # source off the board, "here" names nothing and the instruction
            # does nothing (359.3.e.7): Atakhan bounced in answer to his own
            # attack trigger takes nothing with him (RiftJudge #10215). A -1
            # destination means "anywhere", which is what Acceptable Losses
            # wants, so a LOST location must not decay into it.
            if op.target_b != -1 and dest < 0:
                log["fizzled"].append(op.op)
                continue
            state.pend_cull_dest = dest
            state.pend_cull_keep[:] = -1
            state.pend_cull_skip = seat if op.who == W_ENEMY else -1
            state.cull_spell_seat = seat
            first = (seat + 1) % N_SEATS if op.start_next else seat
            state.pend_cull_first = first
            from rl.engine.actions import first_cull_seat
            state.pend_cull = first_cull_seat(state, table, first)
            if state.pend_cull < 0 and op.cull_mode == CULL_KEEP_OWN:
                from rl.engine.actions import finish_keep_cull
                finish_keep_cull(state, table)
            log["cull"] = int(state.pend_cull)
        elif op.op == OP_SCORE:
            # "You score N points." Straight onto the score; the winner check
            # is a Cleanup concern (194.2) and happens on its own.
            # `who=W_ENEMY` -- "choose an opponent. THEY score 1 point"
            # (Draven - Audacious). The watcher fires for whoever is the
            # OPPONENT of the player who actually scored.
            scorer = (1 - seat) if op.who == W_ENEMY else seat
            if combat.points_blocked(state, table, scorer):
                log["fizzled"].append(op.op)          # Tianna Crownguard
                continue
            state.points[scorer] += op.n
            log["scored_points"] = op.n
            from rl.engine.effects import TR_OPPONENT_SCORES
            chain.fire_watchers(state, table, 1 - scorer, TR_OPPONENT_SCORES)
        elif op.op == OP_REVEAL_HAND:
            # The opponent reveals; the caster then chooses. Nothing is copied
            # out of the hand -- `pend_reveal` names the two seats and the
            # action layer reads the candidates live, so a card that leaves the
            # hand in between simply is not offered.
            foe = 1 - seat
            state.pend_reveal[:] = (seat, foe)
            # 383.3.b -- "you may PAY 2 XP to choose a card from their hand".
            # The price is on the CHOICE, not on the ability: the reveal is
            # unconditional and only the pick costs, so it rides the pending
            # decision rather than the Chain Item's cost.
            state.pend_reveal_xp = op.cost_xp
            # A follow-up for what happens AFTER the pick ("...and draw 1").
            # Set here for the same reason the look and the discard set theirs:
            # `_run_followup` reads `pend_then`, and an op that suspends has to
            # leave the rest of its sentence somewhere the decision can find it.
            if op.then_key >= 0:
                state.pend_then[:] = (op.then_key, source)
            state.look_pick_dest = op.pick_dest
            state.reveal_hold_return = int(op.hold_return)
            state.reveal_play_loc = (
                _slot(state, still_legal, op.target_b, source, ctx, seat,
                      subj, ctx2) if op.reveal_play_there else -1)
            if op.reveal_play_there and state.reveal_play_loc < 0:
                state.pend_reveal[:] = (-1, -1)     # the battlefield is gone
                log["fizzled"].append(op.op)
                continue
            state.look_domain = op.domain
            state.look_type_mask = 0
            for _t in op.pick_types:
                state.look_type_mask |= LOOK_TYPE_BIT[_t]
            log["revealed"] = int(state.n_hand[foe])
        elif op.op == OP_SEE_HAND:
            # "They reveal their hand." A standing permission rather than a
            # choice, so unlike OP_REVEAL_HAND nothing is picked and nothing
            # moves -- the only effect is on what the observation shows.
            #
            # **This is an approximation, and a deliberate one.** A reveal is
            # instantaneous in the rules; the information then lives in the
            # opponent's MEMORY, which the engine has no concept of. Modelled
            # as visibility for the rest of the turn: less than perfect recall
            # (a human remembers past this turn) and slightly more within it
            # (a card drawn after the reveal is also seen). The alternative --
            # snapshotting the revealed ids -- models a memory nothing else in
            # the engine has, and would still have to pick a duration.
            state.saw_hand[seat] = int(state.ply)
            log["saw_hand"] = 1 - seat
        elif op.op == OP_SEE_FACEDOWN:
            # "You can look at their facedown cards this turn" -- explicitly
            # turn-scoped on the card itself, so no approximation here.
            state.saw_fd[seat] = int(state.ply)
            log["saw_facedown"] = 1 - seat
        elif op.op == OP_DEATH_GUARD:
            # Register the delayed replacement on its controller. One at a
            # time: a second Zhonya's simply overwrites, which is right because
            # each says "the NEXT time" and only one death can be the next one.
            if source >= 0:
                state.death_guard[seat] = source
                log["death_guard"] = source
        elif op.op == OP_CHANNEL:
            # 430.1 -- take runes off the top of the Rune Deck onto the board.
            # 430.4.b is the permission these cards use; the two-per-turn of
            # 430.4.a is `phases.channel` and is a different thing.
            got = []
            for _who in ((int(state.active), 1 - int(state.active))
                         if op.each_player else (seat,)):
                for _ in range(op.n):
                    dom = state.channel_one(_who, ready=op.ready_runes)
                    if dom < 0:
                        break                  # an empty Rune Deck, not a loss
                    got.append(dom)
            log["channelled"] = got
            if op.draw_if_short and len(got) < op.n:
                # "If you couldn't channel N this way, draw 1" -- the
                # consolation is for coming up SHORT, so it pays out on a
                # partial channel as well as on none at all.
                log["drew"] = phases.draw_for(state, seat, op.draw_if_short)
        elif op.op == OP_EMPOWER:
            # 827.1.b -- Empower "Empowers the source of the ability", and
            # 827.1.b.1 is explicit that the source is NOT a target. So this
            # never reads a slot: it always acts on the permanent the ability
            # is printed on. 441.1.b/c make re-empowering a no-op, which
            # setting a flag already is.
            # 827.1.b.1 makes [Empower]'s own target the source and NOT a
            # target -- but a card that says "empower SOMETHING" (Tornado
            # Warrior, Profiteer) does choose one, and that choice is an
            # ordinary slot. `op.target < 0` keeps the keyword's behaviour,
            # which is what every [Empower] entry in ABILITIES relies on.
            tgt = a if op.target >= 0 else source
            if is_legend_src(tgt):
                # A legend empowering itself (Zed - Master of Shadows, Mel,
                # Ambessa - Matriarch of War). No row, so no count to climb:
                # 441.1.a makes the status binary and `legend_emp` holds it.
                if state.src_empower(tgt):
                    log["empowered"] = tgt
                    chain.fire_empowered(state, table, tgt)
            elif tgt >= 0 and state.perms[tgt, P_ALIVE] == 1:
                source = tgt
                # The COUNT is the real record; the flag stays in sync because
                # seven other places read it as "Empowered at all" (828.1.c).
                # Capped, so a card that somehow resolves a second Empower it
                # was not entitled to cannot climb past its printed limit --
                # `actions.legal_actions` refuses to offer it, and 441.1.b
                # makes the overflow a no-op rather than an error.
                lim = empower_limit(table, int(state.perms[source, P_CARD]))
                # 441.1.b/c -- Empowering something already Empowered is a
                # no-op, and a no-op is not an event. Read BEFORE the write, so
                # "when I become Empowered" fires on the transition and not on
                # every attempt. Kayle, Justified's second and third Empowers
                # ARE transitions (she climbs a count, not a flag), which is
                # why this asks the count against her own limit.
                grew = state.empower_count(source) < lim
                if grew:
                    state.perms[source, P_EMPOWER] += 1
                state.set_flag(source, F_EMPOWERED)
                log["empowered"] = source
                if op.eot_revert:
                    state.eot_ply[source] = int(state.ply)
                    state.eot_kind[source] = EOT_DISEMPOWER
                if grew:
                    chain.fire_empowered(state, table, source)
        elif op.op == OP_DISEMPOWER:
            # 441.2 -- spend the Empowered status. `op.target < 0` means the
            # source disempowers ITSELF, which is the shape every "Disempower
            # this, Exhaust:" cost takes; a slot means the card chose something.
            tgt = a if op.target >= 0 else source
            if is_legend_src(tgt):
                if state.src_disempower(tgt):
                    log["disempowered"] = tgt
            elif tgt >= 0 and state.perms[tgt, P_ALIVE] == 1 \
                    and state.disempower(tgt):
                log["disempowered"] = tgt
                if op.eot_revert:
                    state.eot_ply[tgt] = int(state.ply)
                    state.eot_kind[tgt] = EOT_EMPOWER
            else:
                log["fizzled"].append(op.op)
        elif op.op == OP_DISCARD:
            # `n < 0` is "their hand": the hand's own size, read at resolution.
            if op.each_player:
                # Turn player first, the default order for a simultaneous
                # per-player instruction.
                for _p in (int(state.active), 1 - int(state.active)):
                    log.setdefault("discarded", []).extend(phases.discard(
                        state, table, _p,
                        int(state.n_hand[_p]) if op.n < 0 else op.n))
            else:
                # `who=W_ENEMY` -- "choose a player. THEY discard 1" (Bewitching
                # Spirit's opponent mode).
                _d = (1 - seat) if op.who == W_ENEMY else seat
                log["discarded"] = phases.discard(
                    state, table, _d,
                    int(state.n_hand[_d]) if op.n < 0 else op.n)
        elif op.op == OP_REVEAL_PLAY:
            state.rp_cost = op.cost
            state.rp_discount = op.play_discount
            state.rp_here = source_loc(state, source) if op.play_here else -1
            state.rp_empower = int(op.play_empower)
            if op.from_opponent or op.until_type:
                # No choice among the cards: straight to the play decision.
                owner = (1 - seat) if op.from_opponent else seat
                ptr, end = int(state.deck_ptr[owner]), int(state.n_deck[owner])
                hit, passed = -1, []
                for k in range(ptr, end):
                    c = int(state.deck[owner, k])
                    if op.from_opponent or any(table.is_type(c, t)
                                               for t in op.pick_types):
                        hit = c
                        state.deck_ptr[owner] = k + 1
                        break
                    passed.append(c)
                else:
                    state.deck_ptr[owner] = end
                for c in passed:
                    state.recycle_card(owner, c)
                if hit < 0:
                    log["fizzled"].append(op.op)
                    continue
                state.banish_card(owner, hit)
                state.rp_owner = owner
                state.rp_card = hit
                state.rp_seat = seat
                log["revealed_play"] = table.names[hit]
                continue
            # A look whose pick is banished; `actions._finish_look` then opens
            # the play decision for it.
            ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
            take = min(op.n, end - ptr)
            state.n_look = take
            state.look_cards[:] = -1
            for k in range(take):
                state.look_cards[k] = state.deck[seat, ptr + k]
            state.deck_ptr[seat] = ptr + take
            state.look_pick_dest = DEST_BANISH
            state.look_rest_dest = op.rest_dest
            state.look_optional = int(op.pick_optional)
            state.look_multi = 0
            state.look_min_energy = 0
            state.look_type_mask = 0
            for _t in op.pick_types:
                state.look_type_mask |= LOOK_TYPE_BIT[_t]
            state.pend_look = seat if take else -1
            state.rp_armed = int(bool(take))
            if op.pick_max_might_killed >= 0:
                km = log.get("killed_might")
                state.look_max_might = (int(km) + op.pick_max_might_killed
                                        if km is not None else -2)
            log["looked"] = take
        elif op.op == OP_QUEUE_FOLLOWUP:
            if source >= 0:
                chain.queue(state, TR_FOLLOWUP, source,
                            int(state.perms[source, P_LOC]))
        elif op.op == OP_REVEAL_COUNT_DAMAGE:
            ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
            take = min(op.n, end - ptr)
            shown = [int(state.deck[seat, ptr + k]) for k in range(take)]
            state.deck_ptr[seat] = ptr + take
            hits = sum(1 for c in shown if table.has(c, op.keyword))
            for c in shown:
                state.recycle_card(seat, c)
            log["revealed_hits"] = hits
            if hits and a >= 0 and state.perms[a, P_ALIVE] == 1:
                if combat.mark_damage(state, table, a, hits, seat):
                    log.setdefault("killed", []).append(a)
        elif op.op == OP_LOOK_TOP:
            # "Look at the top N cards of your Main Deck." The cards come off
            # the deck NOW and the player picks among them afterwards, through
            # `pend_look` in the action layer -- the same suspend-and-ask shape
            # as the mulligan, because the choice is made during resolution and
            # so cannot go through the target machinery (355.10).
            #
            # Between the two the cards are in NO zone. That is faithful (they
            # are being looked at, not held) but it means `cards_owned` has to
            # count the buffer, and it means this op must be the LAST one on
            # its card -- an op after it would run before the player had
            # chosen. `effects.py` asserts that at import.
            ptr, end = int(state.deck_ptr[seat]), int(state.n_deck[seat])
            take = min(op.n, end - ptr)
            state.n_look = take
            state.look_cards[:] = -1
            for k in range(take):
                state.look_cards[k] = state.deck[seat, ptr + k]
            state.deck_ptr[seat] = ptr + take
            # "As I'm revealed from your deck, ..." (Undertitan). The card is
            # in NO zone at this moment -- off the deck, not yet anywhere --
            # and it has no permanent row, so this cannot go on the Chain
            # through the ordinary source machinery. Every such ability in the
            # pool is `immediate` (337.2, a resource add), so it is executed
            # inline here, which is also the only ordering that lets the energy
            # exist before the player picks.
            if op.reveal == LOOK_REVEAL_ALL:
                for k in range(take):
                    _run_revealed_abilities(state, table, cfg, seat,
                                            int(state.look_cards[k]), log)
            state.look_reveal = op.reveal
            state.look_pick_dest = op.pick_dest
            state.look_rest_dest = op.rest_dest
            state.look_optional = int(op.pick_optional)
            state.look_multi = int(op.pick_multi)
            state.look_min_energy = op.pick_min_energy
            state.look_type_mask = 0
            for _t in op.pick_types:
                state.look_type_mask |= LOOK_TYPE_BIT[_t]
            # An empty deck makes this a no-op rather than a stuck decision.
            state.pend_look = seat if take else -1
            if take:
                state.pend_then[:] = (op.then_key, source)
            log["looked"] = take
        elif op.op == OP_KILL_ALL:
            # "Kill all gear" is the same sweep as "kill all units" with one
            # word changed, so the TYPE is a field rather than a second op.
            # Defaults to Unit, which is what every existing entry meant.
            want = op.card_type or "Unit"
            if want == "Unit" and (op.at != -1 or op.who != W_ANY
                                   or op.damaged_only):
                # Scoped: "kill all damaged enemy units here" (Warwick).
                rows = _sweep(state, table, op, seat, still_legal, source,
                              ctx, subj, ctx2)
            else:
                rows = [i for i in range(state.n_perms)
                        if state.perms[i, P_ALIVE] == 1
                        and table.is_type(int(state.perms[i, P_CARD]), want)]
            for i in rows:
                combat.destroy(state, table, i)
                log.setdefault("killed", []).append(i)
        elif op.op == OP_READY_ALL:
            # "Ready your units." Units only -- the card does not say gear --
            # and a readying from exhausted is a TRANSITION, so "when you ready
            # a unit" watchers see each one (the Awaken reading).
            readied = []
            for i in range(state.n_perms):
                r = state.perms[i]
                if (r[P_ALIVE] == 1 and int(r[P_CTRL]) == seat
                        and table.is_type(int(r[P_CARD]), "Unit")
                        and not int(r[P_READY])
                        and not combat.ready_blocked(state, table, i)):
                    r[P_READY] = 1
                    readied.append(i)
            log["readied_all"] = readied
            from rl.engine.effects import TR_READIED
            for i in readied:
                chain.fire_watchers(state, table, seat, TR_READIED, subj=i)
        elif op.op == OP_RETURN_ALL:
            # "Return all units and gear to their owners' hands." Every player's.
            # Each goes to its OWNER; tokens cease to exist (185.3). Attached
            # Equipment is returned in the same sweep rather than left detached,
            # and each departure fires its leaves-the-board watchers.
            for i in range(state.n_perms):
                r = state.perms[i]
                if r[P_ALIVE] != 1:
                    continue
                card = int(r[P_CARD])
                if not (table.is_type(card, "Unit") or table.is_type(card, "Gear")):
                    continue
                if op.sweep_max_might >= 0 and not (
                        table.is_type(card, "Unit")
                        and combat.might(state, table, i) <= op.sweep_max_might):
                    continue
                owner = int(r[P_OWNER])
                combat.queue_leaves_board(state, table, i)
                r[P_ALIVE] = 0
                if not table.is_token(card):
                    h = int(state.n_hand[owner])
                    assert h < state.hand.shape[1], "hand overflow from a bounce"
                    state.hand[owner, h] = card
                    state.n_hand[owner] = h + 1
        elif op.op == OP_UNITS_ENTER_READY:
            state.units_enter_ready_turn[seat] = int(state.ply)
        elif op.op == OP_EXHAUST_ALL:
            for i in range(state.n_perms):
                r = state.perms[i]
                if (r[P_ALIVE] == 1 and int(r[P_CTRL]) == seat
                        and table.is_type(int(r[P_CARD]), "Unit")):
                    r[P_READY] = 0
        elif op.op == OP_HEAL_AT:
            # "heal your units here" -- removes marked damage (no rule allows
            # healing to kill, so no 143.2.a re-check is needed).
            for i in state.units_at(a, seat):
                state.perms[i, P_DMG] = 0
            log["healed_at"] = a
        elif op.op == OP_DAMAGE_ALL:
            # "Deal N to all units at battlefields" -- untargeted (355.10) and,
            # unscoped, indiscriminate: it hits the caster's units too.
            # `_sweep` narrows it to one location, one side, or everything but
            # an already-chosen unit, which is what Crescent Strike's "1 to
            # each OTHER enemy unit there" needs.
            for i in _sweep(state, table, op, seat, still_legal, source, ctx,
                            subj, ctx2):
                if combat.mark_damage(state, table, i, amount, seat):
                    log.setdefault("killed", []).append(i)
        elif op.op == OP_MODIFY_MIGHT_ALL:
            # "give enemy units -3 Might this turn" -- no count, no choice, so
            # not targets (355.10) and no slot. Each unit it reaches gets the
            # same 143.2.a re-check a single Might change would.
            # Mel, Newly Awakened (Empowered) replaces only the -Might given to
            # a unit the spell CHOSE: Moonfall's pulled unit gets -3, the rest
            # of the battlefield -2 (RiftJudge #11737).
            ward = _ward_count(state, table, seat) if seat >= 0 and op.n < 0 else 0
            chosen = ({still_legal[k] for k, ts in enumerate(spec.targets)
                       if k < len(still_legal) and ts.kind == TK_UNIT}
                      if ward else set())
            for i in _sweep(state, table, op, seat, still_legal, source, ctx,
                            subj, ctx2):
                n = op.n - ward if i in chosen else op.n
                if combat.set_might_mod(state, table, i, n, op.floor):
                    log.setdefault("killed_by_might", []).append(i)
        elif op.op == OP_READY and a >= 0 and combat.ready_blocked(state, table, a):
            log["fizzled"].append(op.op)                # Mageseeker Warden
        elif op.op == OP_READY:
            woke = int(state.perms[a, P_READY]) == 0
            state.perms[a, P_READY] = 1
            log.setdefault("readied", []).append(a)
            if woke:
                from rl.engine.effects import TR_READIED
                chain.fire_watchers(state, table, int(state.perms[a, P_CTRL]),
                                    TR_READIED, subj=a)
        elif op.op == OP_SWAP_LOC:
            b = _slot(state, still_legal, op.target_b, source, ctx,
                      seat, subj, ctx2)
            if b < 0:
                log["fizzled"].append(op.op)
                continue
            la, lb = int(state.perms[a, P_LOC]), int(state.perms[b, P_LOC])
            # A swap is two Moves, and each is checked on its own: Zed at
            # Vilemaw's Lair cannot move to base, but the Shadow Clone at base
            # still moves to him. The half that can happen does (356.3.e.11,
            # RiftJudge #12421), and a unit that did not move fires nothing.
            # ...and "can't move it this turn" (Vex - Apathetic): a stunned
            # Tideturner stays while the unit it chose still moves to it
            # (RiftJudge #11188, FAQ #10318).
            a_ok = not ((not is_battlefield(lb)
                         and combat.cant_move_to_base(state, table, a))
                        or (state.has_flag(a, F_NO_MOVE)
                            and seat == int(state.perms[a, P_CTRL])))
            b_ok = not ((not is_battlefield(la)
                         and combat.cant_move_to_base(state, table, b))
                        or (state.has_flag(b, F_NO_MOVE)
                            and seat == int(state.perms[b, P_CTRL])))
            if a_ok:
                combat.queue_move_trigger(state, table, a, la, lb)
            if b_ok:
                combat.queue_move_trigger(state, table, b, lb, la)
            if a_ok:
                state.set_location(a, lb)
            if b_ok:
                state.set_location(b, la)
            log["swapped"] = (a if a_ok else -1, b if b_ok else -1)
        else:
            raise ValueError(f"unknown op {op.op}")
        log["resolved"].append(op.op)
    return log
