"""Game state, laid out for speed and for a later Rust port.

Three rules govern this file, all from PLAN.md §1.8:

  1. No Python objects in the hot loop. Cards are `u16` ids into the frozen
     `CardTable`; locations, phases and seats are small ints. Nothing here holds
     a string.
  2. Fixed-capacity arrays, never lists that grow. Overflow is a bug, asserted.
  3. `clone()` is a handful of `ndarray.copy()` calls, so search (ISMCTS later)
     and speculative rollouts stay cheap.

The deliberate departure from `sim/engine/state.py`: **runes are counts, not
objects**. Two Calm runes are interchangeable, so tracking individual `Rune`
instances with generated ids buys nothing and costs an allocation per rune plus a
non-resettable global counter. `runes_ready[seat, domain]` says everything the
rules need.
"""

from __future__ import annotations

import numpy as np

from rl.config import DOMAINS

# ---------------------------------------------------------------------------
# Enumerations. These are wire format -- append only, never reorder.
# ---------------------------------------------------------------------------
AWAKEN, BEGINNING, CHANNEL, DRAW, MAIN, ENDING = range(6)
PHASE_NAMES = ("Awaken", "Beginning", "Channel", "Draw", "Main", "Ending")

N_DOMAINS = len(DOMAINS)
N_SEATS = 2
N_BF = 2  # battlefields in play (rule 485.4); each player chose one

# Locations are ints. Seat s' base is `s`; battlefield i is `N_SEATS + i`.
LOC_NONE = -1
N_LOCATIONS = N_SEATS + N_BF


def base_loc(seat: int) -> int:
    return seat


def bf_loc(index: int) -> int:
    return N_SEATS + index


def is_battlefield(loc: int) -> bool:
    return loc >= N_SEATS


def bf_index(loc: int) -> int:
    return loc - N_SEATS


# Permanent columns. One int16 matrix so a clone is a single copy.
P_CARD, P_CTRL, P_LOC, P_READY, P_DMG, P_ALIVE, P_ARRIVED, P_FLAGS = range(8)
N_PERM_COLS = 8

# Bits in P_FLAGS. Statuses live in one column rather than one column each, so
# adding the next one costs nothing.
F_STUNNED = 1 << 0           # rule 423: the game status itself
F_NO_COMBAT_DAMAGE = 1 << 1  # 423.1.b, and any effect worded "deals no damage"

# Statuses that expire during the end-of-turn cleanup (423.1.a.2, 317.2).
TURN_SCOPED_FLAGS = F_STUNNED | F_NO_COMBAT_DAMAGE

# Capacities. Generous enough that overflow means a real bug, small enough that
# cloning stays cheap.
MAX_PERMS = 48
MAX_HAND = 20
MAX_DECK = 60
MAX_TRASH = 80
MAX_CHAIN = 16
RUNE_RING = 16   # >= rune_deck_size; recycled runes cycle back through it

# Chain columns.
C_CARD, C_CTRL = range(2)

# Showdown steps (PLAN.md Phase 1.3).
SD_NONE, SD_PRIORITY, SD_DAMAGE, SD_CLEANUP = range(4)


class GameState:
    """Mutable game state. Treat every array as private to the engine."""

    __slots__ = (
        "perms", "n_perms",
        "hand", "n_hand", "deck", "deck_ptr", "n_deck", "trash", "n_trash",
        "runes_ready", "runes_spent", "rune_deck", "rune_head", "rune_left",
        "pool_energy", "pool_power",
        "bf_card", "bf_ctrl", "bf_contested", "fd_owner", "fd_card", "bf_scored",
        "chain", "n_chain",
        "points", "burned_out",
        "legend", "champion",
        "turn", "active", "phase", "priority", "focus",
        "showdown_bf", "showdown_step", "attacker", "passes",
        "decl_dst", "decl_mask", "pend_play",
        "winner", "truncated",
        "rng",
    )

    def __init__(self) -> None:
        self.perms = np.zeros((MAX_PERMS, N_PERM_COLS), np.int16)
        self.n_perms = 0

        self.hand = np.full((N_SEATS, MAX_HAND), -1, np.int16)
        self.n_hand = np.zeros(N_SEATS, np.int16)
        self.deck = np.full((N_SEATS, MAX_DECK), -1, np.int16)
        self.deck_ptr = np.zeros(N_SEATS, np.int16)   # next card to draw
        self.n_deck = np.zeros(N_SEATS, np.int16)     # cards originally dealt
        self.trash = np.full((N_SEATS, MAX_TRASH), -1, np.int16)
        self.n_trash = np.zeros(N_SEATS, np.int16)

        # Runes are fungible within a domain -- counts, not objects.
        self.runes_ready = np.zeros((N_SEATS, N_DOMAINS), np.int16)
        self.runes_spent = np.zeros((N_SEATS, N_DOMAINS), np.int16)
        # Rune Deck as a ring buffer: Recycle returns a rune to it (416.1.b), so
        # it is not a one-way stack. `rune_head` is the next rune to channel and
        # `rune_left` how many remain; a recycled rune is written at the tail.
        self.rune_deck = np.full((N_SEATS, RUNE_RING), -1, np.int8)  # domain ids
        self.rune_head = np.zeros(N_SEATS, np.int16)
        self.rune_left = np.zeros(N_SEATS, np.int16)

        # Rune Pool -- emptied at Main start and turn end (rule 167).
        self.pool_energy = np.zeros(N_SEATS, np.int16)
        self.pool_power = np.zeros((N_SEATS, N_DOMAINS), np.int16)

        self.bf_card = np.full(N_BF, -1, np.int16)
        self.bf_ctrl = np.full(N_BF, -1, np.int8)      # -1 = uncontrolled
        self.bf_contested = np.zeros(N_BF, np.int8)
        # Facedown Zone: max occupancy 1 (107.3.b); public zone, private card
        # (107.3.f). Only the battlefield's controller may occupy it (107.3.c).
        self.fd_owner = np.full(N_BF, -1, np.int8)
        self.fd_card = np.full(N_BF, -1, np.int16)
        # Rule 470: a player may Score a given Battlefield only once per turn,
        # by either method. Reset for both seats at the start of every turn.
        self.bf_scored = np.zeros((N_SEATS, N_BF), np.int8)

        self.chain = np.full((MAX_CHAIN, 2), -1, np.int16)
        self.n_chain = 0

        self.points = np.zeros(N_SEATS, np.int16)
        self.burned_out = np.zeros(N_SEATS, np.int8)
        self.legend = np.full(N_SEATS, -1, np.int16)
        self.champion = np.full(N_SEATS, -1, np.int16)

        self.turn = 1
        self.active = 0
        self.phase = MAIN
        self.priority = 0
        self.focus = -1
        self.showdown_bf = -1
        self.showdown_step = SD_NONE
        self.attacker = -1   # seat that applied Contested (464.2.c.1)
        self.passes = 0      # consecutive passes in the current priority loop

        # In-progress Move declaration (PLAN.md §1.3.a). One destination, a
        # bitmask over permanent rows, committed as a single group.
        self.decl_dst = -1
        self.decl_mask = 0
        # Hand index of a card whose location choice is still open, or -1. The
        # second factored decision point; target selection joins these later.
        self.pend_play = -1

        self.winner = -1
        self.truncated = False
        self.rng: np.random.Generator | None = None

    # ---- cloning ---------------------------------------------------------

    def clone(self) -> "GameState":
        s = GameState.__new__(GameState)
        for name in GameState.__slots__:
            v = getattr(self, name)
            setattr(s, name, v.copy() if isinstance(v, np.ndarray) else v)
        return s

    def state_hash(self) -> int:
        """Stable hash over everything that defines the position.

        Used to prove determinism: same seed twice must produce an identical
        hash trace. Excludes `rng`, which is an object, not state.
        """
        parts = []
        for name in GameState.__slots__:
            if name == "rng":
                continue
            v = getattr(self, name)
            # 8 bytes, not 4: `decl_mask` is a bitmask over MAX_PERMS rows.
            parts.append(v.tobytes() if isinstance(v, np.ndarray)
                         else int(v).to_bytes(8, "little", signed=True))
        return hash(b"".join(parts))

    # ---- the four states (rules 308-310) ---------------------------------

    @property
    def is_open(self) -> bool:
        """Open iff no Chain exists (309.2)."""
        return self.n_chain == 0

    @property
    def is_neutral(self) -> bool:
        """Neutral iff no Showdown or Combat is in progress (308.2)."""
        return self.showdown_bf < 0

    # ---- permanents ------------------------------------------------------

    def add_permanent(self, card: int, ctrl: int, loc: int,
                      ready: bool = True) -> int:
        assert self.n_perms < MAX_PERMS, "MAX_PERMS overflow"
        i = self.n_perms
        row = self.perms[i]
        row[P_CARD] = card
        row[P_CTRL] = ctrl
        row[P_LOC] = loc
        row[P_READY] = int(ready)
        row[P_DMG] = 0
        row[P_ALIVE] = 1
        row[P_ARRIVED] = self.turn
        row[P_FLAGS] = 0
        self.n_perms = i + 1
        return i

    def stun(self, perm: int) -> bool:
        """Apply Stun. Returns False if it was already Stunned (423.1.a.1).

        The return value is load-bearing: "when you stun an enemy unit" triggers
        (Eclipse Herald) must NOT fire on a redundant stun.
        """
        if self.perms[perm, P_FLAGS] & F_STUNNED:
            return False
        self.perms[perm, P_FLAGS] |= F_STUNNED | F_NO_COMBAT_DAMAGE
        return True

    def has_flag(self, perm: int, flag: int) -> bool:
        return bool(self.perms[perm, P_FLAGS] & flag)

    def live(self) -> np.ndarray:
        """Boolean mask over permanent rows that are still on the board."""
        return self.perms[:self.n_perms, P_ALIVE] == 1

    def units_at(self, loc: int, seat: int | None = None) -> np.ndarray:
        """Indices of live permanents at `loc`, optionally filtered by seat."""
        p = self.perms[:self.n_perms]
        m = (p[:, P_ALIVE] == 1) & (p[:, P_LOC] == loc)
        if seat is not None:
            m &= p[:, P_CTRL] == seat
        return np.flatnonzero(m)

    def has_units_at(self, loc: int, seat: int) -> bool:
        return self.units_at(loc, seat).size > 0

    def seats_at(self, loc: int) -> tuple[bool, bool]:
        """(seat 0 has units here, seat 1 has units here)."""
        return self.has_units_at(loc, 0), self.has_units_at(loc, 1)

    # ---- move declaration (PLAN.md §1.3.a) -------------------------------

    @property
    def declaring(self) -> bool:
        return self.decl_dst >= 0

    def declared(self) -> list[int]:
        """Permanent rows currently in the pending Move declaration."""
        m, out, i = self.decl_mask, [], 0
        while m:
            if m & 1:
                out.append(i)
            m >>= 1
            i += 1
        return out

    def clear_declaration(self) -> None:
        self.decl_dst = -1
        self.decl_mask = 0

    # ---- runes -----------------------------------------------------------

    def total_ready_runes(self, seat: int) -> int:
        return int(self.runes_ready[seat].sum())

    def runes_in_play(self, seat: int) -> np.ndarray:
        """Per-domain count of runes on the board, ready or exhausted.

        This is the pool Power draws from. Recycling has no ready requirement
        (164.2.b), so an exhausted rune is still a legal Power source -- which is
        why a card's rune requirement is max(energy, power), not the sum.
        """
        return self.runes_ready[seat] + self.runes_spent[seat]

    def channel_one(self, seat: int) -> int:
        """Pop the next rune from the Rune Deck, or -1 if it is empty."""
        if self.rune_left[seat] <= 0:
            return -1
        h = int(self.rune_head[seat])
        dom = int(self.rune_deck[seat, h])
        self.rune_head[seat] = (h + 1) % RUNE_RING
        self.rune_left[seat] -= 1
        self.runes_ready[seat, dom] += 1
        return dom

    def recycle_rune(self, seat: int, domain: int) -> None:
        """Return a rune of `domain` to the bottom of the Rune Deck (416.1.b).

        Spends an exhausted rune first: exhausted runes are already used up this
        turn, so recycling one costs strictly less than recycling a ready one.
        """
        if self.runes_spent[seat, domain] > 0:
            self.runes_spent[seat, domain] -= 1
        else:
            assert self.runes_ready[seat, domain] > 0, "no rune of that domain"
            self.runes_ready[seat, domain] -= 1
        assert self.rune_left[seat] < RUNE_RING, "rune ring overflow"
        tail = (int(self.rune_head[seat]) + int(self.rune_left[seat])) % RUNE_RING
        self.rune_deck[seat, tail] = domain
        self.rune_left[seat] += 1

    def clear_pools(self) -> None:
        self.pool_energy[:] = 0
        self.pool_power[:] = 0

    # ---- scoring ---------------------------------------------------------

    def check_winner(self, victory_score: int) -> int:
        """Winner at a cleanup, or -1 (rules 194.2, 194.2.a).

        A tie on points at or above the Victory Score is not a win -- play
        continues until one player has strictly more (194.2.b).
        """
        qualified = [s for s in range(N_SEATS) if self.points[s] >= victory_score]
        if not qualified:
            return -1
        best = max(int(self.points[s]) for s in qualified)
        leaders = [s for s in qualified if self.points[s] == best]
        return leaders[0] if len(leaders) == 1 else -1
