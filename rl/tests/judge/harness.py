"""Shared staging and driving helpers for the RiftJudge scenario suite.

Imported by `rl/tests/test_judge.py` and every `rl/tests/judge/cases_*.py`.
"""

import sys


from dataclasses import replace


sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))


from rl.config import Config


from rl.engine import actions as A


from rl.engine import chain as chain_mod


from rl.engine import combat, phases


from rl.engine import resolve as rsv


from rl.engine.cardtable import full_table


from rl.engine.effects import SPECS, abilities_for


from rl.engine.state import (GameState, MAIN, P_ALIVE, P_CARD, P_CTRL, P_DMG,
                             P_FLAGS, P_LOC, P_READY, F_NON_UNIT, F_STUNNED,
                             base_loc, bf_loc, fd_slots)


T = full_table()


V1 = replace(Config().at_victory_score(8).with_solved_damage(), units_only=False)

# Staging a gear with `add_permanent` must mark it a non-unit, the way every
# play path does (`is_unit=table.is_type(card, "Unit")`); otherwise the gear
# counts as a friendly unit for "alone" checks and the like.
_orig_add_permanent = GameState.add_permanent


def _add_permanent(self, card, ctrl, loc, ready=True, is_unit=None, owner=None):
    if is_unit is None:
        is_unit = bool(T.is_type(int(card), "Unit"))
    return _orig_add_permanent(self, card, ctrl, loc, ready=ready, is_unit=is_unit,
                               owner=owner)


GameState.add_permanent = _add_permanent


RESULTS = []

# Cases the engine is KNOWN to answer wrong, with the rule it violates and the
# reason the fix is not a one-liner. Distinct from `rejected.json`, which is for
# rulings the engine disagrees with *on rule grounds* -- these are ones where the
# ruling is right and the engine is wrong.
#
# **Strict, not a mute.** A known-bad case that starts PASSING is reported as a
# FAILURE telling you to delete the entry, so a fix cannot quietly leave a stale
# exemption behind. The suite exits 0 while they fail and 1 the moment one is
# fixed without being removed from here.
KNOWN_BAD = {
    "AJ-02": "372 -- when two Replacement Effects apply to one death, the "
             "controller of the object being acted on picks the order. "
             "`combat._destroy` hard-codes Smite's banish ahead of Zhonya's "
             "guard, so the choice is never offered and the save is "
             "unreachable. Needs a real decision point (backlog D6), which "
             "widens the action space.",
}


def case(qid, title):
    def deco(fn):
        try:
            fn()
        except Skip as e:
            RESULTS.append(("SKIP", qid, title, str(e)))
        except AssertionError as e:
            RESULTS.append(("KNOWN" if qid in KNOWN_BAD else "FAIL",
                            qid, title, str(e)))
        except Exception as e:                       # a crash is a failure too
            RESULTS.append(("KNOWN" if qid in KNOWN_BAD else "FAIL",
                            qid, title, f"{type(e).__name__}: {e}"))
        else:
            if qid in KNOWN_BAD:
                RESULTS.append(("FAIL", qid, title,
                                "this KNOWN_BAD case now PASSES -- delete its "
                                "entry from harness.KNOWN_BAD"))
            else:
                RESULTS.append(("PASS", qid, title, ""))
        return fn
    return deco


class Skip(Exception):
    pass


def need(*names):
    """Skip a case whose cards the engine does not play as printed yet."""
    from rl.decks import plays_as_printed
    for n in names:
        try:
            cid = T.id_of(n)
        except Exception:
            raise Skip(f"{n!r} is not in the card table")
        if not plays_as_printed(T, cid):
            raise Skip(f"{n!r} is not scripted yet")


def fresh(hand=(), seat=0, runes=6, plain_card=None):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = plain_card if plain_card is not None else VANILLA
    for j, c in enumerate(hand):
        s.hand[seat, j] = c
    s.n_hand[seat] = len(hand)
    s.runes_ready[:, :] = runes
    s.phase = MAIN
    s.active = seat
    s.priority = seat
    return s


# The only unit in the pool with no text AND no keyword at every Might is
# Shipyard Skulker (3). Any other Might is set through the same "base Might
# becomes N" path Dragon Form uses, so a scenario still measures one card.
VANILLA = next(c for c in range(T.n)
               if T.names[c] == "Shipyard Skulker")


def body(s, seat, loc, might=3, ready=False):
    """A textless, keywordless unit of exactly `might`."""
    i = s.add_permanent(VANILLA, seat, loc, ready=ready)
    if might != int(T.might[VANILLA]):
        s.base_might_ply[i] = int(s.ply)
        s.base_might_val[i] = might
    return i


def drain(s, limit=60):
    """Both players pass until nothing is pending."""
    for _ in range(limit):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0 \
                and s.pend_may < 0 and not chain_mod.decision_open(s):
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            return
        pick = next((a for a in legal if a.kind == A.A_ORDER),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)


def pass_priority_to(s, seat):
    """Let the other seat pass so `seat` holds priority in this window."""
    for _ in range(4):
        if int(s.priority) == seat:
            return
        other = A.acting_seat(s)
        if other < 0:
            return
        legal = A.legal_actions(s, T, V1, other)
        nxt = next((a for a in legal if a.kind == A.A_PASS), None)
        if nxt is None:
            return
        A.apply(s, T, V1, nxt)


def kinds(s, seat):
    return {a.kind for a in A.legal_actions(s, T, V1, seat)}


def hand_plays(s, seat):
    """Card names `seat` is currently offered as a play from hand."""
    return {T.names[int(s.hand[seat, a.arg])]
            for a in A.legal_actions(s, T, V1, seat)
            if a.kind in (A.A_PLAY, A.A_PLAY_REPEAT)
            and a.arg < int(s.n_hand[seat])}


def act(s, kind, arg=None, seat=None):
    """Take the one legal action of `kind` (and `arg`) for the acting seat."""
    who = A.acting_seat(s) if seat is None else seat
    legal = A.legal_actions(s, T, V1, who)
    for a in legal:
        if a.kind == kind and (arg is None or a.arg == arg):
            A.apply(s, T, V1, a)
            return a
    raise AssertionError(f"seat {who} has no {A.KIND_NAMES[kind]}"
                         f"({'' if arg is None else arg}): {legal}")


_CHOICE_KINDS = (A.A_TARGET, A.A_PLAY_AT, A.A_PICK, A.A_ORDER, A.A_PLAY_AT_FAST)


def choose(s, arg):
    """Answer the open decision with `arg`, whatever kind of choice it is."""
    who = A.acting_seat(s)
    legal = A.legal_actions(s, T, V1, who)
    for a in legal:
        if a.kind in _CHOICE_KINDS and a.arg == arg:
            A.apply(s, T, V1, a)
            return a
    raise AssertionError(f"seat {who} cannot choose {arg}: {legal}")


def hand_index(s, seat, name):
    cid = T.id_of(name)
    for j in range(int(s.n_hand[seat])):
        if int(s.hand[seat, j]) == cid:
            return j
    raise AssertionError(f"{name!r} is not in seat {seat}'s hand")


def cast(s, seat, name, *choices, repeat=False):
    """Play `name` from hand through the action layer, then make `choices`."""
    pass_priority_to(s, seat)
    act(s, A.A_PLAY_REPEAT if repeat else A.A_PLAY,
        hand_index(s, seat, name), seat)
    for c in choices:
        choose(s, c)


def give(s, seat, *names):
    for n in names:
        s.hand[seat, int(s.n_hand[seat])] = T.id_of(n)
        s.n_hand[seat] += 1


def alive(s, i):
    return s.perms[i, P_ALIVE] == 1


def rune_deck(s, n=12):
    """Give both seats a Rune Deck to channel from (fresh() leaves it empty)."""
    s.rune_deck[:, :n] = 0
    s.rune_head[:] = 0
    s.rune_left[:] = n


def runes(s, seat):
    return int(s.runes_in_play(seat).sum())


def perm_of(s, name, seat=None):
    cid = T.id_of(name)
    return [i for i in range(s.n_perms) if alive(s, i)
            and int(s.perms[i, P_CARD]) == cid
            and (seat is None or int(s.perms[i, P_CTRL]) == seat)]


def fight(s, limit=80):
    """`drain`, but also through an open Showdown until it closes."""
    for _ in range(limit):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0 \
                and s.pend_may < 0 and not chain_mod.decision_open(s) \
                and s.showdown_bf < 0:
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            return
        pick = next((a for a in legal if a.kind == A.A_ORDER),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)


def attack(s, seat, bf, *units):
    s.active = s.priority = seat
    act(s, A.A_DECLARE, bf_loc(bf), seat)
    for u in units:
        act(s, A.A_ADD, u, seat)
    act(s, A.A_COMMIT, None, seat)


def _top_uid(s):
    from rl.engine.state import C_UID
    return int(s.chain[s.n_chain - 1, C_UID])


def _sprite_at(s, seat, bf):
    """A [Temporary] Sprite token of `seat`'s at battlefield `bf`."""
    s.bf_ctrl[bf] = seat
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], seat, [bf_loc(bf)], -1, True)
    A._settle(s, T, V1)
    return [i for i in range(s.n_perms) if alive(s, i)
            and T.is_token(int(s.perms[i, P_CARD]))][-1]


def _next_own_turn(s):
    """Jump to seat 0's next turn and run its Beginning Step (315.2.a)."""
    s.ply += 2
    s.active = s.priority = 0
    phases.start_turn(s, T, V1)
    A._settle(s, T, V1)


def run(s, prefer=None, limit=60, stop=None):
    """Drive both seats until nothing is pending (or `stop(s)` is true).

    `prefer(s, who, legal)` may return the Action to take; otherwise ORDER,
    then PASS, then the first legal action. Showdowns are played through.
    Triggers queued by direct engine calls (a `destroy`, a `draw_for`) are
    settled first, the way `apply` would have.
    """
    A._settle(s, T, V1)
    for _ in range(limit):
        if stop is not None and stop(s):
            return
        if (s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0
                and s.pend_may < 0 and not chain_mod.decision_open(s)
                and s.showdown_bf < 0 and int(s.pend_phase) < 0):
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            return
        pick = prefer(s, who, legal) if prefer else None
        if pick is None:
            pick = next((a for a in legal if a.kind == A.A_ORDER),
                        next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)


def picking(*args, accept=True):
    """A `prefer` that takes the first of `args` it is offered as a choice,
    accepts every "you may" (or declines, with accept=False), and passes."""
    def pref(s, who, legal):
        for want in args:
            for a in legal:
                if a.kind in _CHOICE_KINDS and a.arg == want:
                    return a
        k = A.A_ACCEPT if accept else A.A_DECLINE
        return next((a for a in legal if a.kind == k), None)
    return pref


def picks(*args, accept=True):
    """A `prefer` that answers successive choices with `args` IN ORDER (each
    one used once), accepts or declines every "you may", and otherwise passes."""
    queue = list(args)

    def pref(s, who, legal):
        if queue:
            for a in legal:
                if a.kind in _CHOICE_KINDS and a.arg == queue[0]:
                    queue.pop(0)
                    return a
        k = A.A_ACCEPT if accept else A.A_DECLINE
        return next((a for a in legal if a.kind == k), None)
    return pref


def tokens(s, seat=None, loc=None):
    return [i for i in range(s.n_perms) if alive(s, i)
            and T.is_token(int(s.perms[i, P_CARD]))
            and (seat is None or int(s.perms[i, P_CTRL]) == seat)
            and (loc is None or int(s.perms[i, P_LOC]) == loc)]


__all__ = ['RESULTS', 'Skip', 'T', 'V1', 'VANILLA', '_CHOICE_KINDS', '_next_own_turn', '_sprite_at', '_top_uid', 'act', 'alive', 'attack', 'body', 'case', 'cast', 'choose', 'drain', 'fight', 'fresh', 'give', 'hand_index', 'hand_plays', 'kinds', 'need', 'pass_priority_to', 'perm_of', 'picking', 'picks', 'run', 'rune_deck', 'runes', 'tokens', 'A', 'chain_mod', 'combat', 'phases', 'rsv', 'SPECS', 'abilities_for', 'GameState', 'MAIN', 'P_ALIVE', 'P_CARD', 'P_CTRL', 'P_DMG', 'P_FLAGS', 'P_LOC', 'P_READY', 'F_NON_UNIT', 'F_STUNNED', 'base_loc', 'bf_loc', 'fd_slots', 'replace', 'Config', 'full_table', 'sys']
