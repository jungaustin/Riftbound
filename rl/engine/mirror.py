"""Seat mirror: relabel seat 0 as seat 1 and vice versa.

This exists to test one claim, and it is the claim the whole single-network
self-play design rests on: **the observation is canonical**. One net plays both
seats, so a position must encode identically no matter which seat label it
happens to be wearing. `mirror(s)` produces the same position with the labels
swapped; the test is then

    encode(s, seat=0) == encode(mirror(s), seat=1)      byte for byte

If that fails, the net is learning "seat 0" and "seat 1" as different games and
half its experience is wasted -- a failure that looks like slow learning rather
than like a bug, which is why it gets a test rather than a comment.

**Every slot is classified explicitly and completeness is asserted at import.**
Adding a field to `GameState` without deciding how it mirrors is exactly the
mistake that makes the canonicalization test start silently lying, so this file
refuses to load until the new field is named below.
"""

from __future__ import annotations

import numpy as np

from rl.engine.state import (C_CTRL, C_CTX, C_CTX2, C_OWNER, N_SEATS, P_CTRL, P_LOC,
                             P_OWNER,
                             GameState, base_loc, is_battlefield)

# Rows are per-seat: swap axis 0.
SEAT_AXIS = (
    "hand", "n_hand", "deck", "deck_ptr", "n_deck", "trash", "n_trash",
    # The registered decklist and whether the opponent knows it. Card ids,
    # which mirroring does not touch -- the row swaps wholesale.
    "decklist", "n_decklist", "deck_known",
    "runes_ready", "runes_spent", "rune_deck", "rune_head", "rune_left",
    "banished", "n_banished",
    "pool_energy", "pool_power", "bf_scored", "bf_first_use", "points",
    "burned_out",
    "legend", "champion", "champion_reg", "legend_ready", "legend_emp",
    "legend_once",
    "equip_played_ply",
    "pending_ready_runes",
    "pending_add_any",
    "no_spells", "no_cards", "cards_played", "cards_completed",
    "spells_played", "xp",
    "unit_died_ply", "discarded_ply", "chose_enemy_ply", "big_spell_ply",
    "unit_tax_ply", "free_hide_ply", "desig_seat",
    # Permanent ROWS, one per seat: the row swaps, the values do not.
    "pend_cull_keep",
    "bf_conquered_ply", "buff_bonus_ply", "buff_bonus_n",
    "next_unit_ready_ply", "extra_turns",
    "hold_points_ply", "hold_points", "power_spent_ply", "power_spent",
    "excess_ply", "excess_amt", "excess_attacking",
    "next_spell_bonus_ply", "next_spell_repeat_ply", "bonus_uid",
    "next_spell_discount",
    # Per-seat turn stamp, so the row swaps.
    "units_enter_ready_turn", "xp_gained_ply",
    # An (energy, power) pair PER SEAT, so the whole row swaps -- the numbers
    # in it belong to no seat of their own.
    "next_discount",
    # Delayed Abilities are armed PER SEAT and hold card ids, which mirroring
    # does not touch -- so the rows swap wholesale, exactly like `no_spells`.
    "delayed",
    "played_types", "died_in_beginning",
    # Combat damage assignment, per seat. `pend_dmg_targets` / `pend_dmg_kills`
    # hold permanent ROWS, which mirroring leaves in place, and the pools and
    # counts are plain numbers -- so each seat's row swaps wholesale and
    # nothing inside it is rewritten. Same shape as `pend_cull_keep`.
    "pend_dmg_pool", "pend_dmg_targets", "pend_dmg_n_tgt",
    "pend_dmg_kills", "pend_dmg_n_kill", "pend_dmg_done",
    # [Show Off], per seat. `show_off_perm` holds a permanent ROW and
    # `show_off_card` a CARD id -- mirroring moves neither -- so each seat's
    # entry swaps wholesale, like `pend_cull_keep`.
    "show_off_perm", "show_off_card", "show_off_ply",
    # Turn stamps indexed BY the seat that may look, so the permission follows
    # its owner across a swap.
    "saw_hand", "saw_fd",
    # Rows into `perms`, which mirroring leaves in place, so the VALUES
    # stay valid -- only which seat owns the guard swaps.
    "death_guard",
    # Card ids waiting to return to that seat's hand (Ashe - Focused).
    "hold_return", "n_hold_return",
    "draw_ply", "draw_count", "second_draw_ply", "pool_rstr_e", "pool_rstr_p",
    "rune_recycled_n", "banished_n", "chose_enemy_n", "legend_pile",
    "legend_pile_n",
    "recycled_n", "free_gear_ply", "flow_grant_card", "flow_grant_e",
    "flow_grant_p", "flow_grant_ply", "flow_grant_banish", "sarc_cards", "n_sarc",
    "zero_cards", "n_zero",
    # Rows swap, and the VALUES are seats too (flipped by hand below).
    "zero_owner", "pf_cards", "dj_rune_keep", "dj_hand_keep", "riches_on",
)

# The value *is* a seat id: flip it, but leave the -1 "nobody" sentinel alone.
SEAT_VALUED_SCALAR = ("pend_cull_first", "pend_cull_skip", "cull_spell_seat",
                      "active", "priority", "attacker", "focus", "winner",
                      "pend_order", "pend_play_seat", "pend_kill_play_seat",
                      # Who is being asked to pay a "counter ... unless its
                      # controller pays" tax. A seat, not a chain index -- the
                      # item it would counter is `pend_tax_uid`.
                      "pend_tax", "pend_ask", "pend_ask_caster", "pend_hand_play",
                      "pend_mull",
                      # Only one look is ever pending, so the BUFFER is
                      # seat-agnostic (it lists card ids) while this names who
                      # is looking -- the same split as pend_mull.
                      "pend_look", "pend_cull", "pend_discard",
                      # Which seat is being asked to [Show Off] a unit.
                      "pend_show_off",
                      # Which seat is assigning combat damage right now. The
                      # battlefield it happens at is `pend_dmg_bf`, which is a
                      # BF slot shared by both players and so does not flip.
                      "pend_dmg",
                      "pend_repeat_seat", "rp_seat", "rp_owner", "pend_split",
                      "pend_amount", "steal_seat", "pend_name", "resume_seat",
                      "pend_group_loc",
                      "pf_first", "dj_seat", "dj_first",
                      # Both are seats and they are deliberately NOT the same
                      # one: Kharox lets you dig in the OPPONENT's trash, so
                      # the chooser and the pile's owner must flip together
                      # but independently.
                      "pend_grave", "pend_grave_owner")
SEAT_VALUED_ARRAY = ("bf_ctrl", "fd_owner", "bf_contester", "mark_seat",
                     "bf_prev_ctrl")

# Seat-agnostic: battlefield identities, phase, counters, the RNG.
UNCHANGED = (
    "n_perms", "bf_card", "bf_replaced", "empower_src", "victory_bonus",
    "bf_contested",
    "fd_card", "n_chain",
    "turn",
    "phase", "showdown_bf", "showdown_step", "showdown_combat",
    "passes", "decl_dst",
    "decl_mask", "pend_play", "pend_kill_play", "truncated", "rng", "mull_mask",
    # `pend_kill_play_loc` is a LOCATION and needs `mirror_loc`, handled by
    # hand below, same as `pend_double`'s third slot. `pend_grave_dest` is the
    # same shape -- where a unit dug out of a trash will land.
    "pend_kill_play_loc", "pend_grave_dest", "hp_dest",
    # Affects BOTH players' units, so a seat swap leaves it alone.
    "any_damage_kills", "pend_discard_ops", "no_effect_damage_ply",
    "resolving_bonus", "resolving_paid", "pend_repeat_card",
    # Chain-target values, classified like `chain_targets`; a bf INDEX.
    "pend_repeat_tgts", "pend_repeat_bound", "pend_repeat_hand",
    # A card id, a cost mode and amount, flags; `rp_here` is a location and
    # is flipped by hand below.
    "rp_card", "rp_cost", "rp_discount", "rp_empower", "rp_armed", "rp_here",
    "rp_kill",
    "look_max_might", "look_last_pick", "reveal_hold_return", "last_token",
    "reveal_play_loc", "pend_cull_dest", "split_left", "split_loc",
    "split_xp", "split_spell", "split_alloc", "amt_kind", "amt_loc", "amt_spell",
    "armory_ply", "last_burned", "hp_kw", "hp_spells",
    "rp_zone", "rp_power", "rp_from_sarc", "kill_disc_e", "kill_disc_p",
    # A Chain uid, a stage, a slot, and chain-target values.
    "steal_uid", "steal_stage", "steal_slot", "steal_targets", "extra_buffs",
    "tag_grant", "named", "name_kind", "name_src", "name_opts", "n_name_opts",
    "copy_of", "copy_via", "last_token_n", "copy_pending", "granted_card",
    "granted_ply", "grenade_ply", "grenade_hits", "ctrl_link",
    "n_group_loc",
    "resume_kind", "resume_card", "resume_idx", "resume_op", "resume_src",
    "resume_subj", "resume_hand", "resume_bound", "resume_tgts", "pf_stage",
    "dj_cat", "dj_keep",
    # Locations, flipped by hand below.
    "resume_ctx", "resume_ctx2", "group_loc", "group_loc_opts",
    # Per-row LOCATIONS, flipped by hand below.
    "move_from", "move_to",
    # A card-type index (config.CARD_TYPES), which belongs to no seat.
    "pend_cull_type", "pend_cull_mode",
    # A per-game constant that belongs to neither seat (194.3).
    "victory_score",
    # A permanent ROW, and mirroring keeps rows in place.
    "pend_discard_src", "pend_discard_tgt",
    # (followup key, source ROW) -- neither changes under a seat swap.
    "pend_then",
    # Chain targets are permanent ROW indices, and mirroring preserves row
    # order (it rewrites P_CTRL in place rather than reordering), so the
    # indices stay valid. `pend_slot` is a slot number on a card, not a seat.
    "chain_targets", "pend_slot",
    # The look buffer holds CARD ids and its destinations are constants, so
    # none of it changes under a seat swap -- only `pend_look` above does.
    "look_cards", "n_look", "look_pick_dest", "look_rest_dest",
    "look_optional", "look_multi",
    # A LOOK-BUFFER index, and only the seat named by `pend_look` is ever
    # offered it, so it names no seat of its own -- the same shape as
    # `pend_hide`'s hand index.
    "pend_play_look",
    # A plain count of Attached rows -- belongs to no seat, and mirroring keeps
    # rows in place so the total cannot change.
    "n_attached",
    # A permanent ROW: the row does not move when the seats swap.
    "pend_altar",
    # A BATTLEFIELD slot (0..N_BF-1), not a location and not a seat: both
    # players share the same three battlefields, so the index is already
    # canonical. `bf_loc` turns it into a location where one is needed.
    "pend_dmg_bf",
    # Parallel to `perms` by ROW, which mirroring leaves in place.
    "once_used", "desig", "altar_ply", "death_shield_ply", "guillotine_ply",
    "mark_ply", "mark_slot", "move_ply", "move_count",
    "mode_used_ply", "mode_used_mask", "eot_ply", "eot_kind",
    "base_might_ply", "base_might_val", "shield_ply", "shield_amt",
    "block_next_ply", "conquer_ply",
    # A flag relative to the row's own CONTROLLER ("an opponent dealt some of
    # this damage"), so it names no seat and survives a swap untouched.
    "foe_dmg", "might_hi",
    "double_dmg_ply", "banish_death_ply", "combat_might_ply", "combat_might_val",
    # (source ROW, token CARD, LOCATION). The row and the card survive a
    # seat swap untouched; the location is flipped by hand below, the same
    # way C_CTX is.
    "pend_double",
    # (chooser seat, revealer seat) -- BOTH are seats, so a swap must flip
    # both. Handled by hand below rather than by a list, since no list
    # means "every element of this array is a seat id".
    "pend_reveal", "look_type_mask", "look_min_energy", "look_domain",
    "look_reveal",
    # An XP PRICE on the pending reveal's pick -- a number, belonging to
    # neither seat. Which seat pays it is `pend_reveal[0]`, which is flipped.
    "pend_reveal_xp",
    # Parallel to `perms` by ROW, and mirroring rewrites P_CTRL in place
    # rather than reordering rows, so the indices stay valid untouched.
    "kw_grant", "kw_grant_turn",
    # `fd_ply` and `ply` are turn counters, and `pend_hide` is a hand index
    # in the acting seat's own hand -- none of them names a seat.
    "fd_ply", "ply", "pend_hide", "chain_uid", "chain_from_trigger",
    # A chain INDEX, not a seat: which pending item is waiting on a "you may".
    "pend_may", "n_trig",
    # A chain INDEX too -- which pending item is waiting on its printed
    # "kill a [...] as an additional cost" target (820), same shape as
    # `pend_may`.
    "pend_cost_kill",
    # Same shape again: the chain item owing a recycle cost, and a count --
    # neither names a seat, and the payer is read off the item's C_CTRL.
    "pend_cost_recycle", "pend_cost_recycle_n",
    # A Chain UID and an energy amount. A uid is allocated by a monotonic
    # counter and belongs to no seat, and energy is just a number, so both
    # survive a mirror untouched.
    "pend_tax_uid", "pend_tax_cost",
    # FOLLOWUPS keys, a permanent ROW and a card id -- no seat among them.
    "pend_ask_yes", "pend_ask_no", "pend_ask_subj", "pend_ask_card",
    # A mask, numbers, a cost mode, a permanent ROW and a hand index. `hp_dest`
    # is a LOCATION when >= 0 and is flipped by hand below.
    "hp_types", "hp_tag", "hp_max_energy", "hp_cost", "hp_discount",
    "hp_attach", "hp_optional", "hp_pick",
    # A PHASE marker -- "the turn is suspended in the Beginning Step" -- which
    # names a step and not a player. The suspended turn belongs to `active`,
    # and that is flipped separately.
    "pend_phase",
)

# Handled by hand below: they carry seat ids *inside* a matrix.
SPECIAL = ("perms", "chain", "trig")

_CLASSIFIED = set(SEAT_AXIS + SEAT_VALUED_SCALAR + SEAT_VALUED_ARRAY
                  + UNCHANGED + SPECIAL)
_MISSING = set(GameState.__slots__) - _CLASSIFIED
assert not _MISSING, (
    f"mirror.py does not know how to mirror {sorted(_MISSING)}. Classify each "
    f"new GameState slot above -- guessing here silently breaks the "
    f"canonicalization test.")


def _flip(v: int) -> int:
    """Swap a seat id, preserving the -1 sentinel."""
    return v if v < 0 else N_SEATS - 1 - v


def mirror_loc(loc: int) -> int:
    """Bases swap; battlefields are shared ground and do not move.

    Battlefield identity is *not* a per-seat thing here. Each player brings one
    (486.5), but once both are in play they are two named cards on the table --
    the state records no ownership, and the observation tells them apart by card
    features. So mirroring must leave them alone; swapping them would be
    mirroring a different game.
    """
    if loc < 0 or is_battlefield(loc):
        return loc
    return base_loc(_flip(loc))


def mirror(state: GameState) -> GameState:
    """The same position with the two seats relabelled."""
    s = state.clone()

    for name in SEAT_AXIS:
        arr = getattr(s, name)
        arr[[0, 1]] = arr[[1, 0]]

    for name in SEAT_VALUED_SCALAR:
        setattr(s, name, _flip(int(getattr(s, name))))

    for name in SEAT_VALUED_ARRAY:
        arr = getattr(s, name)
        arr[:] = np.where(arr >= 0, N_SEATS - 1 - arr, arr)

    if s.n_perms:
        p = s.perms[:s.n_perms]
        p[:, P_CTRL] = N_SEATS - 1 - p[:, P_CTRL]
        # Flipped alongside, and separately: the two are different seats on a
        # card played out of someone else's zone (Kharox), so mirroring one and
        # not the other would silently hand the card over.
        p[:, P_OWNER] = N_SEATS - 1 - p[:, P_OWNER]
        p[:, P_LOC] = [mirror_loc(int(x)) for x in p[:, P_LOC]]

    if s.n_chain:
        c = s.chain[:s.n_chain]
        c[:, C_CTRL] = np.where(c[:, C_CTRL] >= 0,
                                N_SEATS - 1 - c[:, C_CTRL], c[:, C_CTRL])
        c[:, C_OWNER] = np.where(c[:, C_OWNER] >= 0,
                                 N_SEATS - 1 - c[:, C_OWNER], c[:, C_OWNER])
        # C_SRC is a permanent row and rows keep their order under mirroring.
        # C_CTX and C_CTX2 are captured LOCATIONS -- the two ends of a Move --
        # so both move with the bases (359.3.f.3).
        c[:, C_CTX] = [mirror_loc(int(x)) for x in c[:, C_CTX]]
        c[:, C_CTX2] = [mirror_loc(int(x)) for x in c[:, C_CTX2]]

    if s.n_trig:
        # [trigger kind, source ROW, captured LOCATION, subject ROW, second
        # captured LOCATION, controlling SEAT]. Rows survive mirroring untouched
        # (they keep their order); locations and seats do not.
        #
        # The source column is left alone even when it is a battlefield
        # sentinel: battlefield SLOTS are shared ground and are not mirrored
        # (see `obs._battlefields`), so the slot index means the same thing to
        # both seats -- unlike the seat in the last column, which does not.
        t = s.trig[:s.n_trig]
        t[:, 2] = [mirror_loc(int(x)) for x in t[:, 2]]
        t[:, 4] = [mirror_loc(int(x)) for x in t[:, 4]]
        t[:, 5] = np.where(t[:, 5] >= 0, N_SEATS - 1 - t[:, 5], t[:, 5])

    if int(s.pend_reveal[0]) >= 0:
        s.pend_reveal[:] = [N_SEATS - 1 - int(x) for x in s.pend_reveal]

    # `pend_double`'s third slot is a LOCATION and a token may be created at a
    # base, so unlike `decl_dst` this one genuinely needs flipping.
    if int(s.pend_double[0]) >= 0:
        s.pend_double[2] = mirror_loc(int(s.pend_double[2]))

    # `pend_kill_play_loc` is a LOCATION the cost_kill target stood at, and
    # that can be either seat's base -- unlike `decl_dst`, this one moves.
    if int(s.pend_kill_play_loc) >= 0:
        s.pend_kill_play_loc = mirror_loc(int(s.pend_kill_play_loc))
    if int(s.pend_grave_dest) >= 0:
        s.pend_grave_dest = mirror_loc(int(s.pend_grave_dest))
    if int(s.hp_dest) >= 0:
        s.hp_dest = mirror_loc(int(s.hp_dest))
    # Where a scattered group may settle, and where it did: LOCATIONS, and
    # either seat's base is among the candidates.
    if int(s.group_loc) >= 0:
        s.group_loc = mirror_loc(int(s.group_loc))
    for _i in range(int(s.n_group_loc)):
        if int(s.group_loc_opts[_i]) >= 0:
            s.group_loc_opts[_i] = mirror_loc(int(s.group_loc_opts[_i]))
    for _arr in (s.move_from, s.move_to):
        for _i in range(len(_arr)):
            if int(_arr[_i]) >= 0:
                _arr[_i] = mirror_loc(int(_arr[_i]))
    s.zero_owner[:] = np.where(s.zero_owner >= 0, N_SEATS - 1 - s.zero_owner,
                               s.zero_owner)
    if int(s.resume_ctx) >= 0:
        s.resume_ctx = mirror_loc(int(s.resume_ctx))
    if int(s.resume_ctx2) >= 0:
        s.resume_ctx2 = mirror_loc(int(s.resume_ctx2))
    if int(s.amt_loc) >= 0:
        s.amt_loc = mirror_loc(int(s.amt_loc))
    if int(s.split_loc) >= 0:
        s.split_loc = mirror_loc(int(s.split_loc))
    if int(s.pend_cull_dest) >= 0:
        s.pend_cull_dest = mirror_loc(int(s.pend_cull_dest))
    if int(s.reveal_play_loc) >= 0:
        s.reveal_play_loc = mirror_loc(int(s.reveal_play_loc))
    if int(s.rp_here) >= 0:
        s.rp_here = mirror_loc(int(s.rp_here))

    # A declaration only ever targets a Battlefield, so it needs no mirroring.
    # Assert rather than assume: if lateral or base-targeted movement ever
    # lands, this is the line that should fail first.
    assert s.decl_dst < 0 or is_battlefield(int(s.decl_dst)), \
        "decl_dst is not a battlefield; mirror_loc must now be applied to it"
    return s
