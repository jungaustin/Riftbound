"""Observation encoding -- PLAN.md §5.2.

Three rules, in priority order.

**1. The viewer is the spec.** `viewer.view(state, table, cfg, seat)` defines
what a seat may legitimately see. This module encodes that and nothing more:
own hand, both trashes as counts, deck and opponent-hand counts but never
contents, and the Facedown Zone as a public slot with a private card (107.3.f).
`privileged` is the one deliberate exception -- it is critic-only and training-
only (asymmetric actor-critic, §6.4), and it is a separate field precisely so
that "did this leak?" is answerable by looking at which field a number is in.

**2. Canonicalize.** Everything is encoded from the acting seat's point of view:
"mine" and "theirs", "own base" and "enemy base", never "seat 0" and "seat 1".
One network then serves both seats. `rl/engine/mirror.py` exists to test this.

**3. Attributes, never card ids.** A card is its stat line, type, domains and
keywords. No id one-hots, so a card the net never saw in training still gets a
sensible embedding from its features -- which is the entire reason this can
become a deck evaluator rather than a bot for one decklist (§1.1).

Battlefields are *not* mirrored between seats: both are public ground and are
told apart by their card features, not by whose they are.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rl.config import DOMAINS, Config
from rl.engine import actions as A
from rl.engine import chain, combat
from rl.engine.cardtable import CardTable
from rl.engine.effects import (TK_LOCATION, TK_SPELL, TK_TRASH_CARD, TK_UNIT,
                               unpack_trash)
from rl.engine.state import (C_CARD, C_SRC, F_NO_COMBAT_DAMAGE,
                             F_STUNNED, MAX_HAND, MAX_PERMS, N_BF,
                             N_DOMAINS, N_SEATS, P_ALIVE, P_ARRIVED, P_CARD,
                             P_CTRL, P_DMG, P_FLAGS, P_LOC, P_READY,
                             PHASE_NAMES, GameState, base_loc, bf_index,
                             bf_loc, is_battlefield)

# --- per-row context block, appended to every card feature row --------------
# Uniform across zones so a single shared card encoder can process all of them
# (§6.1). Fields meaningless in a zone are zero there.
(CX_ZONE_HAND, CX_ZONE_BOARD, CX_ZONE_BF, CX_ZONE_FD,
 CX_MINE, CX_READY, CX_DMG, CX_STUNNED, CX_NODMG,
 CX_LOC,                       # 4 slots: own base, enemy base, B0, B1
 CX_AFFORD, CX_ARRIVED,
 CX_CTRL_MINE, CX_CTRL_OPP, CX_CTRL_NONE, CX_CONTESTED,
 CX_SCORED_MINE, CX_SCORED_OPP, CX_FD_PRESENT, CX_FD_LIVE,
 CX_ZONE_LEGEND) = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23)
CTX_DIM = 24

# Slot counts. Overflow is a bug, not a resize -- silently dropping a card from
# the observation would be invisible in training.
# Both derived from the engine's own caps for the same reason, twice learned:
# `HAND_SLOTS` was 16 ("spells draw cards; 12 was reachable") and real decks
# reached 23. Tracking `MAX_HAND` is the one value that cannot be outgrown
# without the engine itself refusing the state first.
HAND_SLOTS = MAX_HAND
# **Derived, not chosen.** This was 24, picked as "far above anything a legal
# game reaches" -- and then 806.3 landed, games got ~3x longer, and boards of 31
# live permanents appeared in ordinary random play. A hand-tuned headroom
# constant has to be re-tuned every time the game changes and only announces
# itself by crashing mid-run. `MAX_PERMS` is the engine's own hard cap, so
# tracking it is the one value that cannot be outgrown.
BOARD_SLOTS = MAX_PERMS

# 5*N_DOMAINS: runes_ready + runes_spent for both seats (4), plus this seat's
# pool_power (1). The +1 is pool_power's [A] column -- see state.D_ANY.
# The +2 is `pending_ready_runes` for both seats -- see `_globals`.
GLOBAL_DIM = 40 + 5 * N_DOMAINS + 1 + 2

# Action-row layout after the kind one-hot and card block.
ACT_EXTRA = 4 + 1 + 3 + 1 + 1 + 1 + 1 + 2 + 1
# loc, is_bf, ctrl(3), counts, might, cost, whose
#
# The last slot is "whose thing is this", and it exists because a target's
# owner is not always recoverable from the rest of the row. A permanent target
# carries its controller in the location block; a card in a TRASH does not, and
# "recycle a card from trashes" reaches both piles. Recycling your own card
# refills your deck, recycling theirs denies them a redraw -- opposite plays
# from one action kind, indistinguishable without this bit.


@dataclass(frozen=True)
class Obs:
    """One decision point, as the acting seat sees it."""
    zones: dict[str, np.ndarray]      # {name: [slots, row_dim] float32}
    zone_mask: dict[str, np.ndarray]  # {name: [slots] bool}
    globals: np.ndarray               # [GLOBAL_DIM] float32
    legal_actions: np.ndarray         # [A_max, act_dim] float32
    action_mask: np.ndarray           # [A_max] bool
    to_move: int
    n_legal: int
    privileged: np.ndarray | None     # critic-only, training-only

    def public_bytes(self) -> bytes:
        """Everything the policy may see, flattened. Used by the leak test."""
        parts = [self.globals.tobytes(), self.legal_actions.tobytes(),
                 self.action_mask.tobytes()]
        for k in sorted(self.zones):
            parts.append(self.zones[k].tobytes())
            parts.append(self.zone_mask[k].tobytes())
        return b"".join(parts)


def _loc_slot(loc: int, seat: int) -> int:
    """Location as 0=own base, 1=enemy base, 2+i=battlefield i. Canonical."""
    if is_battlefield(loc):
        return 2 + bf_index(loc)
    return 0 if loc == base_loc(seat) else 1


class Encoder:
    """Builds `Obs` from `GameState`. Holds the frozen card feature matrix."""

    def __init__(self, table: CardTable, cfg: Config,
                 privileged: bool = True) -> None:
        self.table = table
        self.cfg = cfg
        self.want_privileged = privileged
        self.cards = table.features().astype(np.float32)     # [n_cards, D]
        self.card_dim = int(self.cards.shape[1])
        self.row_dim = self.card_dim + CTX_DIM
        self.act_dim = len(A.KIND_NAMES) + 1 + self.card_dim + ACT_EXTRA
        self.a_max = cfg.max_actions
        self.priv_dim = (HAND_SLOTS + N_BF) * self.card_dim

    # -- rows ------------------------------------------------------------

    def _row(self, card: int, zone: int) -> np.ndarray:
        r = np.zeros(self.row_dim, np.float32)
        if card >= 0:
            r[:self.card_dim] = self.cards[card]
        r[self.card_dim + zone] = 1.0
        return r

    def _hand(self, state: GameState, seat: int):
        """Cards in hands this seat may see.

        Normally that is its own hand alone. A card that reveals the opponent's
        hand (Scuttle Crab) adds THEIR cards to the same zone rather than a new
        one: the rows already carry `CX_MINE`, so ownership is a feature the
        net reads rather than a shape it has to be rebuilt for. That keeps the
        observation shape -- and every checkpoint -- valid.
        """
        z = np.zeros((HAND_SLOTS, self.row_dim), np.float32)
        m = np.zeros(HAND_SLOTS, bool)
        seats = [seat]
        if int(state.saw_hand[seat]) == int(state.turn):
            seats.append(1 - seat)
        k = 0
        for owner in seats:
            n = int(state.n_hand[owner])
            if owner == seat:
                # The seat's OWN hand must always fit -- MAX_HAND == HAND_SLOTS
                # by construction, so this is a real invariant.
                assert n <= HAND_SLOTS, (
                    f"hand of {n} exceeds HAND_SLOTS={HAND_SLOTS}")
            else:
                # The revealed half is EXTRA information the policy would not
                # have at all without the card, so if two hands somehow cannot
                # both fit, showing fewer revealed cards is strictly better
                # than an assertion that takes down a training run. Measured
                # peak for both hands together is 15 against 60 slots, so this
                # is headroom rather than a live cap -- but MAX_HAND is 60, and
                # hand-picked capacities in this engine have a history of being
                # overtaken.
                n = min(n, HAND_SLOTS - k)
            for j in range(n):
                card = int(state.hand[owner, j])
                r = self._row(card, CX_ZONE_HAND)
                r[self.card_dim + CX_MINE] = float(owner == seat)
                # Affordability is a genuine feature, not a shortcut: it is the
                # single fact that most changes what a hand card means right
                # now, and the net would otherwise have to rederive
                # max(energy, power) against the rune board from scratch.
                # Read against the card's OWNER -- for your own hand that is
                # you, and for a revealed one "can they actually cast it" is
                # the question worth asking.
                r[self.card_dim + CX_AFFORD] = float(
                    A.plan_payment(state, self.table, owner, card) is not None)
                z[k] = r
                m[k] = True
                k += 1
        return z, m

    def _board(self, state: GameState, seat: int):
        z = np.zeros((BOARD_SLOTS, self.row_dim), np.float32)
        m = np.zeros(BOARD_SLOTS, bool)
        k = 0
        for i in range(state.n_perms):
            row = state.perms[i]
            if row[P_ALIVE] != 1:
                continue
            assert k < BOARD_SLOTS, f"more than {BOARD_SLOTS} live permanents"
            r = self._row(int(row[P_CARD]), CX_ZONE_BOARD)
            c = self.card_dim
            r[c + CX_MINE] = float(row[P_CTRL] == seat)
            r[c + CX_READY] = float(row[P_READY])
            r[c + CX_DMG] = float(row[P_DMG]) / 5.0
            r[c + CX_STUNNED] = float(bool(row[P_FLAGS] & F_STUNNED))
            r[c + CX_NODMG] = float(bool(row[P_FLAGS] & F_NO_COMBAT_DAMAGE))
            r[c + CX_LOC + _loc_slot(int(row[P_LOC]), seat)] = 1.0
            r[c + CX_ARRIVED] = float(int(row[P_ARRIVED]) == state.turn)
            z[k] = r
            m[k] = True
            k += 1
        return z, m

    def _battlefields(self, state: GameState, seat: int):
        z = np.zeros((N_BF, self.row_dim), np.float32)
        m = np.ones(N_BF, bool)
        for i in range(N_BF):
            r = self._row(int(state.bf_card[i]), CX_ZONE_BF)
            c = self.card_dim
            ctrl = int(state.bf_ctrl[i])
            r[c + (CX_CTRL_NONE if ctrl < 0 else
                   CX_CTRL_MINE if ctrl == seat else CX_CTRL_OPP)] = 1.0
            r[c + CX_MINE] = float(ctrl == seat)
            r[c + CX_CONTESTED] = float(state.bf_contested[i])
            r[c + CX_SCORED_MINE] = float(state.bf_scored[seat, i])
            r[c + CX_SCORED_OPP] = float(state.bf_scored[1 - seat, i])
            r[c + CX_FD_PRESENT] = float(state.fd_owner[i] >= 0)
            r[c + CX_FD_LIVE] = float(state.fd_owner[i] >= 0
                                      and int(state.fd_ply[i]) < int(state.ply))
            r[c + CX_LOC + _loc_slot(bf_loc(i), seat)] = 1.0
            z[i] = r
        return z, m

    def _facedown(self, state: GameState, seat: int):
        """107.3.f -- the zone is public, the card is not.

        A slot the opponent occupies is encoded as *present, identity unknown*:
        the mask says a card is there, the card block stays zero. That gap is
        the belief head's target in Phase 6, so it must be a real hole in the
        observation rather than a quietly filled-in one.
        """
        z = np.zeros((N_BF, self.row_dim), np.float32)
        m = np.zeros(N_BF, bool)
        for i in range(N_BF):
            owner = int(state.fd_owner[i])
            if owner < 0:
                continue
            mine = owner == seat
            # "You can look at their facedown cards this turn" fills exactly
            # this hole -- the slot was already public (107.3.f), only the
            # identity was not.
            seen = mine or int(state.saw_fd[seat]) == int(state.turn)
            r = self._row(int(state.fd_card[i]) if seen else -1, CX_ZONE_FD)
            c = self.card_dim
            r[c + CX_MINE] = float(mine)
            r[c + CX_FD_PRESENT] = 1.0
            # 811.1.b -- a card hidden this turn is not playable until the next
            # one. Public information (everyone saw when it was hidden), and
            # decisive for whether the threat is real right now.
            r[c + CX_FD_LIVE] = float(int(state.fd_ply[i]) < int(state.ply))
            r[c + CX_LOC + _loc_slot(bf_loc(i), seat)] = 1.0
            z[i] = r
            m[i] = True
        return z, m

    def _legends(self, state: GameState, seat: int):
        """107.4 -- the Legend Zone, one Champion Legend per seat.

        Public and permanent: 174.2.b establishes it at the start of the game
        and it never leaves (107.4.d), so unlike every other zone here there is
        no hidden information and no arrival to track. What DOES change is
        `CX_READY` -- nearly every legend charges "Exhaust:" for its ability, so
        whether it is spent is the single fact that decides what the seat can do
        this turn.

        Not a location (107.4.b), so no `CX_LOC` block is set.
        """
        z = np.zeros((N_SEATS, self.row_dim), np.float32)
        m = np.zeros(N_SEATS, bool)
        for k, owner in enumerate((seat, 1 - seat)):     # canonical: mine first
            card = int(state.legend[owner])
            if card < 0:
                continue
            r = self._row(card, CX_ZONE_LEGEND)
            c = self.card_dim
            r[c + CX_MINE] = float(owner == seat)
            r[c + CX_READY] = float(state.legend_ready[owner])
            z[k] = r
            m[k] = True
        return z, m

    # -- globals ---------------------------------------------------------

    def _globals(self, state: GameState, seat: int) -> np.ndarray:
        foe = 1 - seat
        cfg = self.cfg
        vs = float(cfg.victory_score)
        g: list[float] = [
            float(state.points[seat]) / vs,
            float(state.points[foe]) / vs,
            float(state.points[seat] - state.points[foe]) / vs,
            float(state.turn) / float(cfg.turn_cap),
        ]
        phase = [0.0] * len(PHASE_NAMES)
        phase[int(state.phase)] = 1.0
        g += phase
        g += [
            float(state.active == seat),
            float(state.priority == seat),
            float(state.is_open),
            float(state.showdown_bf >= 0),
            # ...and WHICH kind. A Combat Showdown ends in the damage step; the
            # Non-Combat one 344.2 opens ends in somebody Conquering (348.2.a).
            # Both present as "a showdown is open with me holding priority",
            # and the right play in them is completely different -- answer the
            # damage, or answer the Conquer -- so the policy needs the bit.
            float(bool(state.showdown_combat)),
            float(state.attacker == seat),
            float(state.attacker == foe),
            float(state.showdown_bf == 0),
            float(state.showdown_bf == 1),
            float(state.declaring),
            float(state.decl_dst == bf_loc(0)),
            float(state.decl_dst == bf_loc(1)),
            float(len(state.declared())) / 4.0,
            float(state.pend_play >= 0),
            float(state.n_hand[seat]) / 10.0,
            float(state.n_hand[foe]) / 10.0,
            float(state.n_deck[seat] - state.deck_ptr[seat]) / 30.0,
            float(state.n_deck[foe] - state.deck_ptr[foe]) / 30.0,
            float(state.n_trash[seat]) / 20.0,
            float(state.n_trash[foe]) / 20.0,
            float(state.burned_out[seat]),
            float(state.burned_out[foe]),
            float(state.rune_left[seat]) / float(cfg.rune_deck_size),
            float(state.rune_left[foe]) / float(cfg.rune_deck_size),
            float(state.pool_energy[seat]) / 5.0,
            # The Chain. Depth matters: an item five deep is respondable only
            # after the ones above it clear (340.4).
            float(state.n_chain) / 4.0,
            float(state.pend_slot >= 0),
            # Facedown zones. Presence is public (107.3.f), identity is not --
            # the *contents* stay out of the observation, which is what the
            # belief head will be asked to predict.
            float(any(state.fd_owner[i] == seat for i in range(N_BF))),
            float(any(state.fd_owner[i] == foe for i in range(N_BF))),
            float(any(state.fd_owner[i] == foe
                      and int(state.fd_ply[i]) < int(state.ply)
                      for i in range(N_BF))),
        ]
        # Runes are on the board face up, so both boards are public.
        for s in (seat, foe):
            g += list(state.runes_ready[s].astype(np.float32) / 4.0)
            g += list(state.runes_spent[s].astype(np.float32) / 4.0)
        g += list(state.pool_power[seat].astype(np.float32) / 3.0)
        # Runes promised at end of turn (Targon's Peak). Public -- the conquer
        # that banked them happened in the open -- and it changes what tapping
        # out costs, which is the single decision runes drive. Left out, the
        # whole point of the card ("delayed, so the refund lands before the
        # OPPONENT's turn") would be invisible to the policy.
        g += [float(state.pending_ready_runes[seat]) / 2.0,
              float(state.pending_ready_runes[foe]) / 2.0]

        out = np.asarray(g, np.float32)
        assert out.size == GLOBAL_DIM, f"{out.size} globals, expected {GLOBAL_DIM}"
        return out

    # -- actions ---------------------------------------------------------

    def _open_slot_kind(self, state: GameState) -> int:
        """The TK_* kind of the target slot currently being filled."""
        return chain.open_slot_kind(state, self.table)

    def _action_row(self, act: A.Action, state: GameState,
                    seat: int) -> np.ndarray:
        r = np.zeros(self.act_dim, np.float32)
        nk = len(A.KIND_NAMES)
        r[act.kind] = 1.0

        card, loc, might = -1, -1, -1
        whose = -1.0
        k = act.kind
        if k == A.A_PLAY:
            card = int(state.hand[seat, act.arg])
        elif k in (A.A_PLAY_AT, A.A_PLAY_AT_FAST):
            loc = act.arg
            if state.pend_play >= 0:
                card = int(state.hand[seat, state.pend_play])
        elif k == A.A_DECLARE:
            loc = act.arg
        elif k == A.A_ACTIVATE:
            if A.is_legend_activate(int(act.arg)):
                # A legend activation names an ability index, not rows -- and
                # the Legend Zone is not a location (107.4.b), so there is no
                # `loc` to set. The card alone distinguishes the candidates
                # while a legend has one ability; the day one has two, the
                # index is what tells them apart and belongs here.
                card = int(state.legend[seat])
            else:
                # The arg may be a packed (permanent, donor) pair --
                # Heimerdinger borrows abilities, so the row alone no longer
                # says which one. The DONOR's card is what distinguishes the
                # candidates; the location is the activating permanent's.
                _perm, _donor = A.unpack_activate(int(act.arg))
                card = int(state.perms[_donor, P_CARD])
                loc = int(state.perms[_perm, P_LOC])
        elif k in (A.A_ADD, A.A_RETREAT):
            # The location a unit is *leaving*; the destination is fixed for the
            # whole decision, so it could not discriminate between candidates.
            card = int(state.perms[act.arg, P_CARD])
            loc = int(state.perms[act.arg, P_LOC])
            might = combat.might(state, self.table, act.arg)
        elif k == A.A_COMMIT:
            loc = int(state.decl_dst)
        elif k == A.A_HIDE:
            card = int(state.hand[seat, act.arg])
        elif k == A.A_HIDE_AT:
            loc = bf_loc(act.arg)
        elif k == A.A_PLAY_FLOW:
            # The trash is public information (108.5), so naming the card here
            # leaks nothing.
            card = int(state.trash[seat, act.arg])
        elif k == A.A_PLAY_HIDDEN:
            # The card's identity is legitimate here: only its owner is ever
            # offered this action, and they know what they hid.
            card = int(state.fd_card[act.arg])
            loc = bf_loc(act.arg)
        elif k == A.A_PICK:
            # The whole decision is WHICH card, so naming it is the only
            # feature that could discriminate between the candidates -- and it
            # leaks nothing in any of the three cases: the look buffer is this
            # player's own cards off their own deck, the revealed hand was
            # revealed to them by a card that says so, and a discard is out of
            # their own hand. Only the deciding seat is ever offered the
            # action.
            #
            # Which of the three the arg indexes is `pick_card`'s business, not
            # this encoder's -- see the note there for why that must be one
            # shared answer.
            card = A.pick_card(state, act.arg)
        elif k == A.A_TARGET:
            # **`arg` means whatever the open slot's KIND says it means**: a
            # permanent row, a location, or a Chain Item uid. This read
            # `state.perms[act.arg]` unconditionally, so a location target
            # (Sprite Call, Ride The Wind) described permanent row 0-3 and a
            # counterspell target (Defy, Lilting Lullaby) described a row
            # chosen by a monotonic counter. Valid indices, meaningless
            # features -- on exactly the decisions that need them most.
            kind = self._open_slot_kind(state)
            if kind == TK_LOCATION:
                loc = int(act.arg)
            elif kind == TK_SPELL:
                i = chain.index_of_uid(state, int(act.arg))
                if i >= 0:
                    card = int(state.chain[i, C_CARD])
            elif kind == TK_TRASH_CARD:
                # A packed (owner, card); the trash is public (108.2), so
                # naming it leaks nothing. There is no row and no location to
                # describe -- the choice is "which card, out of whose pile".
                owner, card = unpack_trash(int(act.arg))
                whose = 1.0 if owner == seat else 0.0
            else:
                card = int(state.perms[act.arg, P_CARD])
                loc = int(state.perms[act.arg, P_LOC])
                might = combat.might(state, self.table, act.arg)
        elif k in (A.A_ACCEPT, A.A_DECLINE):
            # 383.3.a -- the choice is about one triggered ability, so the
            # candidates differ only by yes/no. What distinguishes the decision
            # is whose ability it is.
            item = int(state.pend_may)
            if item >= 0:
                card = int(state.chain[item, C_CARD])
                src = int(state.chain[item, C_SRC])
                if src >= 0:
                    loc = int(state.perms[src, P_LOC])

        if card >= 0:
            r[nk] = 1.0
            r[nk + 1:nk + 1 + self.card_dim] = self.cards[card]
        o = nk + 1 + self.card_dim

        if loc >= 0:
            r[o + _loc_slot(loc, seat)] = 1.0
            r[o + 4] = float(is_battlefield(loc))
            if is_battlefield(loc):
                i = bf_index(loc)
                ctrl = int(state.bf_ctrl[i])
                r[o + 5 + (2 if ctrl < 0 else 0 if ctrl == seat else 1)] = 1.0
                r[o + 8] = state.units_at(loc, 1 - seat).size / 4.0
                r[o + 9] = state.units_at(loc, seat).size / 4.0
                r[o + 10] = float(state.bf_contested[i])
        if might >= 0:
            r[o + 11] = might / 5.0
        if card >= 0:
            r[o + 12] = float(self.table.energy[card]) / 5.0
            r[o + 13] = float(self.table.power[card]) / 3.0
        if whose >= 0.0:
            r[o + 14] = whose
        return r

    def _actions(self, legal: list[A.Action], state: GameState, seat: int):
        n = len(legal)
        assert n <= self.a_max, (
            f"{n} legal actions exceeds max_actions={self.a_max}; raise the cap "
            f"in Config after checking the distribution")
        z = np.zeros((self.a_max, self.act_dim), np.float32)
        m = np.zeros(self.a_max, bool)
        for i, act in enumerate(legal):
            z[i] = self._action_row(act, state, seat)
            m[i] = True
        return z, m

    # -- privileged ------------------------------------------------------

    def _privileged(self, state: GameState, seat: int) -> np.ndarray:
        """Exactly the information the policy is denied: the opponent's hand and
        every facedown card. Kept in its own field so a leak is a type error
        rather than an archaeology problem."""
        foe = 1 - seat
        out = np.zeros((HAND_SLOTS + N_BF, self.card_dim), np.float32)
        n = min(int(state.n_hand[foe]), HAND_SLOTS)
        for j in range(n):
            out[j] = self.cards[int(state.hand[foe, j])]
        for i in range(N_BF):
            if state.fd_owner[i] >= 0:
                out[HAND_SLOTS + i] = self.cards[int(state.fd_card[i])]
        return out.reshape(-1)

    # -- entry point -----------------------------------------------------

    def encode(self, state: GameState, seat: int,
               legal: list[A.Action]) -> Obs:
        zones, masks = {}, {}
        for name, fn in (("hand", self._hand), ("board", self._board),
                         ("battlefields", self._battlefields),
                         ("facedown", self._facedown),
                         ("legends", self._legends)):
            zones[name], masks[name] = fn(state, seat)
        acts, amask = self._actions(legal, state, seat)
        return Obs(
            zones=zones,
            zone_mask=masks,
            globals=self._globals(state, seat),
            legal_actions=acts,
            action_mask=amask,
            to_move=seat,
            n_legal=len(legal),
            privileged=(self._privileged(state, seat)
                        if self.want_privileged else None),
        )

    def shapes(self) -> dict[str, tuple]:
        """Everything a network builder needs to size its layers."""
        return {
            "row_dim": self.row_dim,
            "card_dim": self.card_dim,
            "hand": (HAND_SLOTS, self.row_dim),
            "board": (BOARD_SLOTS, self.row_dim),
            "battlefields": (N_BF, self.row_dim),
            "facedown": (N_BF, self.row_dim),
            "legends": (N_SEATS, self.row_dim),
            "globals": (GLOBAL_DIM,),
            "actions": (self.a_max, self.act_dim),
            "privileged": (self.priv_dim,),
        }
