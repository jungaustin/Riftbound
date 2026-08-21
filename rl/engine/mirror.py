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

from rl.engine.state import (C_CTRL, C_CTX, C_CTX2, N_SEATS, P_CTRL, P_LOC,
                             GameState, base_loc, is_battlefield)

# Rows are per-seat: swap axis 0.
SEAT_AXIS = (
    "hand", "n_hand", "deck", "deck_ptr", "n_deck", "trash", "n_trash",
    "runes_ready", "runes_spent", "rune_deck", "rune_head", "rune_left",
    "banished", "n_banished",
    "pool_energy", "pool_power", "bf_scored", "points", "burned_out",
    "legend", "champion", "legend_ready", "pending_ready_runes",
    "no_spells", "cards_played", "xp",
    "played_types", "died_in_beginning",
    # Turn stamps indexed BY the seat that may look, so the permission follows
    # its owner across a swap.
    "saw_hand", "saw_fd",
    # Rows into `perms`, which mirroring leaves in place, so the VALUES
    # stay valid -- only which seat owns the guard swaps.
    "death_guard",
)

# The value *is* a seat id: flip it, but leave the -1 "nobody" sentinel alone.
SEAT_VALUED_SCALAR = ("active", "priority", "attacker", "focus", "winner",
                      "pend_order", "pend_play_seat", "pend_mull",
                      # Only one look is ever pending, so the BUFFER is
                      # seat-agnostic (it lists card ids) while this names who
                      # is looking -- the same split as pend_mull.
                      "pend_look", "pend_cull", "pend_discard")
SEAT_VALUED_ARRAY = ("bf_ctrl", "fd_owner", "bf_contester")

# Seat-agnostic: battlefield identities, phase, counters, the RNG.
UNCHANGED = (
    "n_perms", "bf_card", "bf_contested", "fd_card", "n_chain", "turn",
    "phase", "showdown_bf", "showdown_step", "showdown_combat",
    "passes", "decl_dst",
    "decl_mask", "pend_play", "truncated", "rng", "mull_mask",
    # Affects BOTH players' units, so a seat swap leaves it alone.
    "any_damage_kills", "pend_discard_ops",
    # A permanent ROW, and mirroring keeps rows in place.
    "pend_discard_src",
    # (followup key, source ROW) -- neither changes under a seat swap.
    "pend_then",
    # Chain targets are permanent ROW indices, and mirroring preserves row
    # order (it rewrites P_CTRL in place rather than reordering), so the
    # indices stay valid. `pend_slot` is a slot number on a card, not a seat.
    "chain_targets", "pend_slot",
    # The look buffer holds CARD ids and its destinations are constants, so
    # none of it changes under a seat swap -- only `pend_look` above does.
    "look_cards", "n_look", "look_pick_dest", "look_rest_dest",
    "look_optional",
    # Parallel to `perms` by ROW, which mirroring leaves in place.
    "once_used",
    # (source ROW, token CARD, LOCATION). The row and the card survive a
    # seat swap untouched; the location is flipped by hand below, the same
    # way C_CTX is.
    "pend_double",
    # (chooser seat, revealer seat) -- BOTH are seats, so a swap must flip
    # both. Handled by hand below rather than by a list, since no list
    # means "every element of this array is a seat id".
    "pend_reveal", "look_type_mask",
    # Parallel to `perms` by ROW, and mirroring rewrites P_CTRL in place
    # rather than reordering rows, so the indices stay valid untouched.
    "kw_grant", "kw_grant_turn",
    # `fd_ply` and `ply` are turn counters, and `pend_hide` is a hand index
    # in the acting seat's own hand -- none of them names a seat.
    "fd_ply", "ply", "pend_hide", "chain_uid", "chain_from_trigger",
    # A chain INDEX, not a seat: which pending item is waiting on a "you may".
    "pend_may", "n_trig",
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
        p[:, P_LOC] = [mirror_loc(int(x)) for x in p[:, P_LOC]]

    if s.n_chain:
        c = s.chain[:s.n_chain]
        c[:, C_CTRL] = np.where(c[:, C_CTRL] >= 0,
                                N_SEATS - 1 - c[:, C_CTRL], c[:, C_CTRL])
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

    # A declaration only ever targets a Battlefield, so it needs no mirroring.
    # Assert rather than assume: if lateral or base-targeted movement ever
    # lands, this is the line that should fail first.
    assert s.decl_dst < 0 or is_battlefield(int(s.decl_dst)), \
        "decl_dst is not a battlefield; mirror_loc must now be applied to it"
    return s
