"""Spells end to end through the action layer.

Run: python3 rl/tests/test_spells.py

  [1] v0 is untouched -- units_only=True still offers no spell at all.
  [2] Playing a spell goes on the Chain and does NOT resolve; the opponent gets
      a real priority window before it does.
  [3] Target slots fill one at a time, and later slots depend on earlier ones.
  [4] Speed: [Action] is playable on your turn or in a showdown, never on the
      opponent's turn outside one.
  [5] A response resolves before the card it responded to, and a combat trick
      actually changes the combat.
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from dataclasses import replace

import numpy as np

from rl.config import Config
from rl.engine import actions as A
from rl.engine import chain, combat
from rl.engine.cardtable import full_table
from rl.engine.state import (C_CARD, F_STUNNED, P_ALIVE, P_FLAGS, P_LOC,
                             GameState, base_loc, bf_loc)

T = full_table()
V0 = Config().at_victory_score(3)                      # units only
V1 = replace(Config().at_victory_score(3), units_only=False)

BACK_OFF = T.id_of("Back Off")
FACEBREAKER = T.id_of("Facebreaker")


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def unit(might):
    for c in range(T.n):
        if (T.is_type(c, "Unit") and T.might[c] == might
                and not any(T.has(c, k) for k in ("Tank", "Backline", "Temporary"))):
            return c
    raise LookupError(might)


def fresh(hand0=(), hand1=(), runes=8):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = unit(2)
    for seat, hand in ((0, hand0), (1, hand1)):
        for j, c in enumerate(hand):
            s.hand[seat, j] = c
        s.n_hand[seat] = len(hand)
        s.runes_ready[seat, :] = runes // 6 + 2      # plenty, every domain
    s.phase = 4                                       # MAIN
    s.active = 0
    s.priority = 0
    return s


def kinds(acts):
    return {a.kind for a in acts}


# ---------------------------------------------------------------------------
print("\n[1] v0 is untouched")
s = fresh(hand0=(BACK_OFF, unit(2)))
acts = A.legal_actions(s, T, V0, 0)
plays = [a for a in acts if a.kind == A.A_PLAY]
if any(int(s.hand[0, a.arg]) == BACK_OFF for a in plays):
    die("v0", "units_only=True offered a spell")
ok("units_only=True still offers units only -- v0 stays frozen")


# ---------------------------------------------------------------------------
print("\n[2] a spell goes on the Chain and waits for a response")
s = fresh(hand0=(BACK_OFF,))
victim = s.add_permanent(unit(5), 1, bf_loc(0))
acts = A.legal_actions(s, T, V1, 0)
play = next(a for a in acts if a.kind == A.A_PLAY
            and int(s.hand[0, a.arg]) == BACK_OFF)
A.apply(s, T, V1, play)
if s.n_chain != 1:
    die("chain", f"playing a spell should push one chain item, got {s.n_chain}")
if s.pend_slot != 0:
    die("chain", "target slot 0 should be open")
ok("playing a spell pushes a Pending chain item and opens slot 0")

tgt = A.legal_actions(s, T, V1, 0)
assert kinds(tgt) == {A.A_TARGET}, kinds(tgt)
A.apply(s, T, V1, next(a for a in tgt if a.arg == victim))
if s.perms[victim, P_FLAGS] & F_STUNNED:
    die("chain", "the spell RESOLVED at finalization -- it must wait on the chain")
ok("finalizing does not resolve it; the stun has not happened yet")

# The opponent now gets a real window.
if A.acting_seat(s) != 0:
    die("priority", f"337.1.a -- the caster keeps priority, got seat "
                    f"{A.acting_seat(s)}")
A.apply(s, T, V1, A.PASS)
if A.acting_seat(s) != 1:
    die("priority", "the opponent must get a window before it resolves")
opp = A.legal_actions(s, T, V1, 1)
assert A.A_PASS in kinds(opp), opp
ok("the caster keeps priority, then the opponent gets a genuine window")

A.apply(s, T, V1, A.PASS)                # both passed -> 339.1 -> resolve
if not (s.perms[victim, P_FLAGS] & F_STUNNED):
    die("chain", "mutual pass should have resolved the spell")
if s.n_chain != 0:
    die("chain", "the chain should be empty after resolving the only item")
ok("mutual pass resolves it: the target is stunned and the chain is empty")


# ---------------------------------------------------------------------------
print("\n[3] target slots fill one at a time, later depending on earlier")
s = fresh(hand0=(FACEBREAKER,))
mine = s.add_permanent(unit(3), 0, bf_loc(0))
theirs_same = s.add_permanent(unit(2), 1, bf_loc(0))
theirs_other = s.add_permanent(unit(4), 1, bf_loc(1))

play = next(a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == FACEBREAKER)
A.apply(s, T, V1, play)
slot0 = [a.arg for a in A.legal_actions(s, T, V1, 0)]
if slot0 != [mine]:
    die("targets", f"slot 0 (friendly, at a battlefield) gave {slot0}")
A.apply(s, T, V1, A.Action(A.A_TARGET, mine))

slot1 = [a.arg for a in A.legal_actions(s, T, V1, 0)]
if slot1 != [theirs_same]:
    die("targets", f"slot 1 must be the enemy at the SAME battlefield; "
                   f"got {slot1} (the other is at B2)")
ok("slot 1's options depend on slot 0 -- 'at the same battlefield' holds")

A.apply(s, T, V1, A.Action(A.A_TARGET, theirs_same))
A.apply(s, T, V1, A.PASS); A.apply(s, T, V1, A.PASS)
if not (s.perms[mine, P_FLAGS] & F_STUNNED and
        s.perms[theirs_same, P_FLAGS] & F_STUNNED):
    die("targets", "both targets should be stunned")
if s.perms[theirs_other, P_FLAGS] & F_STUNNED:
    die("targets", "the untargeted unit was stunned")
ok("Facebreaker stuns exactly its two targets")


# ---------------------------------------------------------------------------
print("\n[4] [Action] speed: your turn, or a showdown")
s = fresh(hand1=(BACK_OFF,))
s.add_permanent(unit(3), 0, bf_loc(0))
s.active, s.priority = 0, 1              # seat 1 holds priority on seat 0's turn
if chain.playable_hand_indices(s, T, V1, 1):
    die("speed", "[Action] was playable on the opponent's turn with no showdown")
ok("[Action] is not playable on the opponent's turn outside a showdown")

s.showdown_bf = 0
if not chain.playable_hand_indices(s, T, V1, 1):
    die("speed", "[Action] must be playable in a showdown on either turn")
ok("[Action] becomes playable once a showdown is running")


# ---------------------------------------------------------------------------
print("\n[5] a combat trick actually changes the combat")
# Seat 0 attacks a 5-might defender with a 5-might attacker. Even trade
# normally; seat 1 stuns the attacker in the showdown, so it deals 0 and dies
# while the defender lives -- and 466.1.a.2 recalls nothing because the
# attacker is dead.
s = fresh(hand1=(BACK_OFF,))
atk = s.add_permanent(unit(5), 0, base_loc(0))
dfd = s.add_permanent(unit(5), 1, bf_loc(0))
s.bf_ctrl[0] = 1

combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, atk)
combat.commit_declaration(s, T, V1)

if s.showdown_bf < 0:
    die("trick", "combat must yield a priority window now that a spell exists")
ok("combat yields a real showdown window once a Reaction is affordable")

# Seat 1 stuns the attacker.
holder = A.acting_seat(s)
while holder != 1:
    A.apply(s, T, V1, A.PASS)
    holder = A.acting_seat(s)
play = next(a for a in A.legal_actions(s, T, V1, 1)
            if a.kind == A.A_PLAY and int(s.hand[1, a.arg]) == BACK_OFF)
A.apply(s, T, V1, play)
A.apply(s, T, V1, A.Action(A.A_TARGET, atk))
for _ in range(8):
    if s.showdown_bf < 0:
        break
    A.apply(s, T, V1, A.PASS)

if s.perms[atk, P_ALIVE] == 1:
    die("trick", "the stunned attacker dealt no damage but survived a 5-might "
                 "defender")
if s.perms[dfd, P_ALIVE] != 1:
    die("trick", "the defender took damage from a stunned attacker (423.1.b)")
if int(s.bf_ctrl[0]) != 1:
    die("trick", "the defender held the battlefield, so control should not move")
ok("Back Off blanks the attacker: it dies, the defender lives, no conquer")


# ---------------------------------------------------------------------------
print("\n[6] random games with spells enabled stay legal and terminate")
from collections import Counter
from rl.engine import game
from rl.tests.fuzz import v0_pool

_spells = [T.id_of(n) for n in ("Back Off", "Facebreaker", "Smoke and Mirrors")]
_units = v0_pool(T)
_bfs = [c for c in range(T.n) if T.is_type(c, "Battlefield")][:2]


def _v1_game(seed, spell_rate=0.34):
    """Spell-heavy decks on purpose: at the natural rate, response windows are
    too rare for a fuzz to exercise the Chain at all."""
    rng = np.random.default_rng(seed)
    decks = [[int(rng.choice(_spells if rng.random() < spell_rate else _units))
              for _ in range(30)] for _ in range(2)]
    runes = [[int(rng.integers(6)) for _ in range(12)] for _ in range(2)]
    return game.new_game(T, V1, decks, runes, _bfs, seed=seed)


N = int(sys.argv[1]) if len(sys.argv) > 1 else 600
w, steps, trunc = Counter(), [], 0
for i in range(N):
    r = game.play_game(T, V1, _v1_game(i),
                       [game.random_agent(np.random.default_rng(i))] * 2,
                       check=True)
    w[r["winner"]] += 1
    steps.append(r["steps"])
    trunc += r["truncated"]
if trunc:
    die("v1 fuzz", f"{trunc}/{N} games truncated")
if w[-1]:
    die("v1 fuzz", f"{w[-1]}/{N} games undecided")
seat0 = w[0] / N
if not 0.42 <= seat0 <= 0.58:
    die("v1 fuzz", f"seat 0 won {seat0:.1%} -- a seat asymmetry appeared")
ok(f"{N} spell-heavy games: 0 truncated, invariants held, "
   f"seat0 {seat0:.1%}, {np.mean(steps):.0f} decisions/game")


# ---------------------------------------------------------------------------
print("\n[7] [Hidden]: hide, wait a turn, then react for free")
from rl.engine import phases

s = fresh(hand0=(BACK_OFF,))
mine = s.add_permanent(unit(3), 0, bf_loc(0))
s.bf_ctrl[0] = 0
runes_before = int(s.runes_ready[0].sum())

acts = A.legal_actions(s, T, V1, 0)
hide = [a for a in acts if a.kind == A.A_HIDE]
if not hide:
    die("hidden", "a [Hidden] card at a controlled battlefield must be hideable")
A.apply(s, T, V1, hide[0])
spots = A.legal_actions(s, T, V1, 0)
assert {a.kind for a in spots} == {A.A_HIDE_AT}, spots
A.apply(s, T, V1, A.Action(A.A_HIDE_AT, 0))

if int(s.fd_owner[0]) != 0 or int(s.fd_card[0]) != BACK_OFF:
    die("hidden", "the card is not in the facedown zone")
if s.n_chain != 0:
    die("hidden", "811.1.c.2 -- hiding must NOT open a chain")
if int(s.runes_ready[0].sum()) != runes_before - 1:
    die("hidden", "hiding should cost exactly one rune")
ok("hiding costs one rune, opens no chain, and fills the facedown zone")

# 811.1.b -- "Beginning on the NEXT turn". Not playable yet.
if chain.hidden_playable(s, T, V1, 0):
    die("hidden", "811.1.b -- a card hidden this turn must not be playable "
                  "this turn")
ok("it is NOT playable on the turn it was hidden (811.1.b)")

phases.end_turn(s, V1)
if not chain.hidden_playable(s, T, V1, 0):
    die("hidden", "it should be live from the next turn")
ok("it becomes live once the turn ends")

# It has [Reaction] while facedown (811.6), so seat 0 may play it on seat 1's
# turn -- and for free.
s.priority = 0
s.showdown_bf = 0
s.bf_contested[0] = 1
s.attacker = 1
victim = s.add_permanent(unit(4), 1, bf_loc(0))
runes_before = int(s.runes_ready[0].sum())
acts = A.legal_actions(s, T, V1, 0)
ph = [a for a in acts if a.kind == A.A_PLAY_HIDDEN]
if not ph:
    die("hidden", "811.6 -- a facedown card must be playable on the "
                  "opponent's turn")
A.apply(s, T, V1, ph[0])
A.apply(s, T, V1, A.Action(A.A_TARGET, victim))
if int(s.runes_ready[0].sum()) != runes_before:
    die("hidden", "811.1.b -- playing from hidden must cost 0 energy")
if int(s.fd_owner[0]) >= 0:
    die("hidden", "the facedown zone should be empty after playing the card")
ok("played from hiding on the opponent's turn, for free")

# 811.1.d.2.a -- a BOUND slot only reaches that battlefield.
s2 = fresh(hand0=())
s2.bf_ctrl[0] = 0
s2.fd_owner[0], s2.fd_card[0], s2.fd_ply[0] = 0, BACK_OFF, -1
s2.add_permanent(unit(3), 0, bf_loc(0))
here = s2.add_permanent(unit(2), 1, bf_loc(0))
there = s2.add_permanent(unit(4), 1, bf_loc(1))
A.apply(s2, T, V1, A.Action(A.A_PLAY_HIDDEN, 0))
opts = [a.arg for a in A.legal_actions(s2, T, V1, 0)]
if there in opts:
    die("hidden", f"a bound slot reached B2 from a card hidden at B1: {opts}")
if here not in opts:
    die("hidden", f"a bound slot should reach its own battlefield: {opts}")
ok("811.1.d.2.a -- targets are bound to the battlefield it was hidden at")

print("\n\033[32mall spell tests passed\033[0m")
