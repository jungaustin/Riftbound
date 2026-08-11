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
from rl.engine.state import (C_CARD, C_FINAL, F_STUNNED, P_ALIVE, P_CTRL,
                             P_FLAGS, P_LOC,
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


# ---------------------------------------------------------------------------
print("\n[8] when the Chain empties into a staged Combat, the DEFENDER acts first")
# 340.2.a. The opposite of 464.2.d, which gives the Attacker Focus when a Move
# declaration opens the Showdown -- the two routes into a Showdown hand priority
# to opposite players. This is the window in which a defender answers a spell
# that dragged a unit in, before combat locks in.
CHARM, GUST = T.id_of("Charm"), T.id_of("Gust")
s = fresh(hand0=(CHARM,), hand1=(GUST,))
s.n_deck[:] = 5
s.deck[:, :5] = T.id_of("Stupefy")
mine = s.add_permanent(unit(3), 0, bf_loc(0))
s.bf_ctrl[0] = 0
foe = s.add_permanent(unit(2), 1, base_loc(1))

play = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY)
A.apply(s, T, V1, play)
A.apply(s, T, V1, A.Action(A.A_TARGET, foe))
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(0)))
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, A.PASS)                       # Charm resolves, chain empties

if s.showdown_bf < 0:
    die("priority", "dragging an enemy in should stage a Combat (461)")
if A.acting_seat(s) != 1:
    die("priority", f"340.2.a -- the defender should hold priority when the "
                    f"chain empties, got seat {A.acting_seat(s)}")
if not any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 1)):
    die("priority", "the defender must be able to answer before combat locks in")
ok("the defender gets Focus and Priority, and can answer with a Reaction")

# ---------------------------------------------------------------------------
# [6] [A] -- Power of any Domain (135.2.e.5)
#
# The Gold gear token (187.5) adds one, and it is NOT Power of some particular
# domain: it "can be spent to pay a Power cost of any Domain" (135.2.e.5.b).
# It rides as an extra column on `pool_power`; these check that the column is
# actually reachable by a payment and that it is spent LAST.

from rl.engine import cost as _cost
from rl.engine.state import D_ANY, N_DOMAINS

_pow = [c for c in range(T.n) if int(T.power[c]) == 1
        and T.is_type(c, "Spell") and _cost.card_domains(T, c)]
if not _pow:
    die("wildcard", "no single-Power spell in the pool to test with")
CARD = _pow[0]
DOM = _cost.card_domains(T, CARD)[0]
OFF = next(d for d in range(N_DOMAINS) if d != DOM)

# Energy is a separate axis (163) and would fail first, so float enough of it
# that the Power half is what the check is actually about.
E = int(T.energy[CARD])

s = GameState()
s.pool_energy[0] = E
s.pool_power[0, D_ANY] = 1
if _cost.plan_payment(s, T, 0, CARD) is None:
    die("wildcard", "[A] in the pool must pay a Power cost of any Domain")
ok("135.2.e.5.b -- floating [A] pays a Power cost of any Domain")

# It is a WILDCARD, not a seventh domain: an off-domain rune must not pay.
s = GameState()
s.pool_energy[0] = E
s.pool_power[0, OFF] = 1
if _cost.plan_payment(s, T, 0, CARD) is not None:
    die("wildcard", "Power of the wrong domain must not pay a domain cost")
ok("...while ordinary Power stays domain-locked")

# Domain-locked Power is spent first, so the flexible resource survives.
s = GameState()
s.pool_energy[0] = E
s.pool_power[0, DOM] = 1
s.pool_power[0, D_ANY] = 1
_cost.pay(s, T, 0, CARD, recycle=[])
if int(s.pool_power[0, DOM]) != 0 or int(s.pool_power[0, D_ANY]) != 1:
    die("wildcard", f"expected the domain rune spent and [A] kept, got "
                    f"dom={int(s.pool_power[0, DOM])} any={int(s.pool_power[0, D_ANY])}")
ok("...and [A] is spent last, keeping the flexible Power for the next card")

# `plan_*` returning [] means the POOL covered it, not that it was free --
# `pay_ability_cost` has to debit the pool or one [A] pays for every Flow
# spell in the turn.
s = GameState()
s.pool_power[0, D_ANY] = 1
_cost.pay_ability_cost(s, T, 0, 0, [], power=1, card=CARD)
if int(s.pool_power[0, D_ANY]) != 0:
    die("wildcard", "an ability/Flow cost covered by the pool must debit it")
ok("204.1.b -- Power covered by the pool is debited, not silently free")

# ---------------------------------------------------------------------------
# [7] "Look at the top N" is a choice made DURING resolution
#
# Not targeting (355.10): no count is announced at finalization and the
# opponent cannot respond to it. So it cannot use the target machinery -- the
# op lifts the cards off the deck and `pend_look` asks afterwards, the same
# suspend-and-ask shape as the mulligan. Between the two the cards are in NO
# zone, which is why `fuzz.cards_owned` counts the buffer.

from rl.engine import resolve as rsv
from rl.engine.effects import SPECS as _SPECS
from rl.engine.state import MAIN

BODY_A = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))
BODY_B = next(c for c in range(T.n) if T.is_type(c, "Unit")
              and not T.is_token(c) and c != BODY_A)


def looking(card_name):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.n_deck[0] = 6
    for i in range(6):
        s.deck[0, i] = BODY_A if i % 2 == 0 else BODY_B
    rsv.resolve(s, T, V1, _SPECS[card_name], 0, [], -1, True)
    return s, [int(s.look_cards[i]) for i in range(int(s.n_look))]


s, looked = looking("Stacked Deck")
if int(s.n_look) != 3 or int(s.pend_look) != 0:
    die("look", f"expected 3 cards pended to seat 0, got n_look={int(s.n_look)} "
                f"pend_look={int(s.pend_look)}")
if int(s.n_deck[0]) - int(s.deck_ptr[0]) != 3:
    die("look", "the three cards must come OFF the deck while being looked at")
ok("355.10 -- the cards leave the deck and the pick is pended, not targeted")

if A.acting_seat(s) != 0:
    die("look", "the looking seat is the one being asked")
acts = A.legal_actions(s, T, V1, 0)
if [a.kind for a in acts] != [A.A_PICK] * 3:
    die("look", f"a mandatory pick offers exactly the N cards, got {acts}")
ok("...and a mandatory pick offers exactly those cards, with no way to decline")

A.apply(s, T, V1, A.Action(A.A_PICK, 1))
if int(s.n_hand[0]) != 1 or int(s.hand[0, 0]) != looked[1]:
    die("look", "the picked card goes to hand")
end = int(s.n_deck[0])
if sorted([int(s.deck[0, end - 2]), int(s.deck[0, end - 1])]) != \
        sorted([looked[0], looked[2]]):
    die("look", "the REST recycle to the bottom of the deck (416.1.a)")
if int(s.pend_look) != -1 or int(s.n_look) != 0:
    die("look", "the buffer must be empty afterwards -- no card left in limbo")
ok("416.1.a -- picked to hand, the rest to the BOTTOM of the deck")

# Lightning Rush is the same shape with two words changed: the pick is
# optional and the rest go to the trash.
s, looked = looking("Lightning Rush")
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_PICK_NONE not in kinds:
    die("look", "'you MAY choose' has to offer declining")
A.apply(s, T, V1, A.Action(A.A_PICK_NONE))
if int(s.n_hand[0]) != 0:
    die("look", "declining takes nothing")
if int(s.n_trash[0]) != 3:
    die("look", f"all three go to the trash on a decline, got {int(s.n_trash[0])}")
ok("'you may choose' -- declining is legal, and all N take the rest-destination")

# "You may reveal a GEAR from among them" (Ornn) -- a type restriction on the
# pick, not on where the rest go. Four cards need contain no gear at all, so a
# restricted pick must always leave a way out; `effects.py` asserts that every
# such card prints "you may".
from rl.engine.effects import ABILITIES as _ABIL

UNIT_C = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))
GEAR_C = next(c for c in range(T.n) if T.is_type(c, "Gear") and not T.is_token(c))
ORNN = _ABIL["Ornn - Blacksmith"][0]


def ornn_look(deck_cards):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.n_deck[0] = len(deck_cards)
    for i, c in enumerate(deck_cards):
        s.deck[0, i] = c
    rsv.resolve(s, T, V1, ORNN, 0, [], -1, True)
    return s, A.legal_actions(s, T, V1, 0)


s, acts = ornn_look([UNIT_C] * 4)
if [a.kind for a in acts] != [A.A_PICK_NONE]:
    die("look-type", f"no gear among them leaves only a decline, got {acts}")
A.apply(s, T, V1, acts[0])
if int(s.n_hand[0]) != 0:
    die("look-type", "declining draws nothing")
ok("a type-restricted pick with no match still offers a way out")

s, acts = ornn_look([UNIT_C, UNIT_C, GEAR_C, UNIT_C])
if [(a.kind, a.arg) for a in acts] != [(A.A_PICK, 2), (A.A_PICK_NONE, -1)]:
    die("look-type", f"only the gear may be picked, got {acts}")
A.apply(s, T, V1, A.Action(A.A_PICK, 2))
if not T.is_type(int(s.hand[0, 0]), "Gear"):
    die("look-type", "the picked card must be the gear")
ok("...and only cards of the named type are offered")

# [Predict] (436.1) -- "look at a single card from the top of the Main Deck and
# choose whether or not to Recycle it". The look mechanic with N=1, where
# recycling is the pick and DECLINING puts the card back on TOP. That
# distinction is the whole keyword: Predict is information, not selection, so a
# declined Predict must leave the deck bit-identical.

def eclipse_board():
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.n_deck[0] = 4
    for i, c in enumerate([UNIT_C, GEAR_C, UNIT_C, GEAR_C]):
        s.deck[0, i] = c
    s.add_permanent(UNIT_C, 1, bf_loc(0))
    rsv.resolve(s, T, V1, _SPECS["Eclipse"], 0, [0], -1, True)
    return s


def deck_list(s):
    return [int(s.deck[0, i]) for i in range(int(s.deck_ptr[0]), int(s.n_deck[0]))]


s = eclipse_board()
before = [UNIT_C, GEAR_C, UNIT_C, GEAR_C]
A.apply(s, T, V1, A.Action(A.A_PICK_NONE))
if deck_list(s) != before:
    die("predict", f"declining a Predict must leave the deck untouched, "
                   f"got {deck_list(s)} not {before}")
ok("436.1 -- a declined Predict puts the card back on TOP, deck unchanged")

s = eclipse_board()
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if deck_list(s) != before[1:] + before[:1]:
    die("predict", f"recycling sends the top card to the BOTTOM, got {deck_list(s)}")
ok("...and accepting recycles it to the bottom (416.1.a)")

# ---------------------------------------------------------------------------
# [8] [Repeat] (820) -- an Optional Additional Cost buying ONE extra execution
#
# 820.1.d: "You may pay [Cost] as an additional cost as you play this. If you
# do, execute the instructions of this chain item one additional time during
# resolution." Not a loop (820.1.c.3, each Repeat cost is payable once), and it
# does not re-target: the targets were chosen at finalization.

DESERTS_CALL = T.id_of("Desert's Call")


def deserts_call(pay_repeat, runes=8):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.n_hand[0] = 1
    s.hand[0, 0] = DESERTS_CALL
    s.n_deck[0] = 10
    s.runes_ready[0, 0] = runes
    acts = A.legal_actions(s, T, V1, 0)
    want = A.A_PLAY_REPEAT if pay_repeat else A.A_PLAY
    act = next((a for a in acts if a.kind == want), None)
    if act is None:
        return s, None
    spent_before = int(s.runes_ready[0].sum())
    A.apply(s, T, V1, act)
    while s.pend_slot >= 0:
        A.apply(s, T, V1, A.legal_actions(s, T, V1, A.acting_seat(s))[0])
    for _ in range(8):
        if s.n_chain == 0:
            break
        A.apply(s, T, V1, A.Action(A.A_PASS))
    made = sum(1 for i in range(s.n_perms)
               if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CTRL]) == 0)
    return s, (made, spent_before - int(s.runes_ready[0].sum()))


_, plain = deserts_call(False)
_, twice = deserts_call(True)
if plain[0] != 1 or twice[0] != 2:
    die("repeat", f"expected 1 token plain and 2 repeated, got {plain[0]} and {twice[0]}")
ok("820.1.d -- a paid Repeat executes the instructions one additional time")

if twice[1] != plain[1] + 2:
    die("repeat", f"the Repeat cost must be charged: {plain[1]} -> {twice[1]}, "
                  f"expected +2")
ok("820.1.c.1 -- and the additional cost is actually paid")

_, unaffordable = deserts_call(True, runes=2)
if unaffordable is not None:
    die("repeat", "play_repeat must not be offered when the combined cost is "
                  "unaffordable")
_, affordable = deserts_call(False, runes=2)
if affordable is None:
    die("repeat", "the plain play is still legal at 2 runes")
ok("...and it is withheld when only the base cost can be paid")

# ---------------------------------------------------------------------------
# [9] Cull the Weak -- "Each player kills one of their units."
#
# Each player chooses their OWN casualty, so there is no target slot: the
# caster does not pick the opponent's unit. Sequential, in turn order, and a
# seat with no units is skipped rather than being handed an empty decision --
# which would deadlock the turn.

CULL_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                 and not T.is_token(c))


def alive_for(s, seat):
    return sum(1 for i in range(s.n_perms)
               if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CTRL]) == seat)


s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
for _ in range(2):
    s.add_permanent(CULL_BODY, 0, bf_loc(0))
for _ in range(3):
    s.add_permanent(CULL_BODY, 1, bf_loc(1))
rsv.resolve(s, T, V1, _SPECS["Cull the Weak"], 0, [], -1, True)

if int(s.pend_cull) != 0:
    die("cull", "the resolving player chooses first")
if any(a.arg for a in A.legal_actions(s, T, V1, 0)
       if int(s.perms[a.arg, P_CTRL]) != 0):
    die("cull", "a player may only choose among their OWN units")
if A.legal_actions(s, T, V1, 1):
    die("cull", "the other seat waits its turn")
A.apply(s, T, V1, A.legal_actions(s, T, V1, 0)[0])
if (alive_for(s, 0), int(s.pend_cull)) != (1, 1):
    die("cull", "after the first seat kills one, the choice passes on")
A.apply(s, T, V1, A.legal_actions(s, T, V1, 1)[0])
if (alive_for(s, 0), alive_for(s, 1), int(s.pend_cull)) != (1, 2, -1):
    die("cull", "each player loses exactly one, then the effect is done")
ok("'each player kills one of their units' -- own units, in turn order")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
s.add_permanent(CULL_BODY, 1, bf_loc(0))
rsv.resolve(s, T, V1, _SPECS["Cull the Weak"], 0, [], -1, True)
if int(s.pend_cull) != 1:
    die("cull", "a seat with no units is skipped, not offered an empty choice")
ok("...and a player with no units is skipped rather than deadlocked")

# ---------------------------------------------------------------------------
# [10] Not So Fast, and Imperial Decree
#
# Not So Fast: "Counter an enemy spell or ability THAT CHOOSES a friendly unit
# or gear." The clause restricts what the countered item PICKED, not the item
# itself, so it reads that item's own recorded targets -- and only its
# permanent slots, since a location slot holds 0-3 and a Chain-uid slot holds a
# counter, both valid row indices and neither a permanent.

NSF_CARD = T.id_of("Not So Fast")
DECREE = T.id_of("Imperial Decree")
NSF_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                and not T.is_token(c))
VENGEANCE = T.id_of("Vengeance")          # "Kill a unit" -- one unit slot


def counter_candidates(victim_seat):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 1, 1
    mine = s.add_permanent(NSF_BODY, 0, bf_loc(0))
    theirs = s.add_permanent(NSF_BODY, 1, bf_loc(0))
    it = chain.push(s, VENGEANCE, 1, from_hand=True, bound_bf=-1)
    s.chain_targets[it, 0] = mine if victim_seat == 0 else theirs
    s.chain[it, C_FINAL] = 1
    # Not So Fast itself must be on the Chain: `_spell_targets` excludes the
    # newest item, which is how "a spell cannot counter itself" is enforced.
    chain.push(s, NSF_CARD, 0, from_hand=True, bound_bf=-1)
    return rsv.legal_targets(s, T, _SPECS["Not So Fast"], 0, 0, [], -1)


if not counter_candidates(victim_seat=0):
    die("nsf", "an enemy spell aimed at MY unit is exactly what this counters")
if counter_candidates(victim_seat=1):
    die("nsf", "an enemy spell aimed at their OWN unit chooses no friendly "
               "permanent, so it is not a legal target")
ok("'that chooses a friendly unit or gear' restricts by the item's own targets")

# Imperial Decree: "When any unit takes damage this turn, kill it." ANY unit,
# both players', and 143.2.a's nonzero clause still holds.
s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
big = max((c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)),
          key=lambda c: int(T.might[c]))
mine = s.add_permanent(big, 0, bf_loc(0))
theirs = s.add_permanent(big, 1, bf_loc(0))
if combat.mark_damage(s, T, mine, 1):
    die("decree", "1 damage should not kill a big unit before the Decree")
rsv.resolve(s, T, V1, _SPECS["Imperial Decree"], 0, [], -1, True)
if not combat.mark_damage(s, T, mine, 1):
    die("decree", "under the Decree any damage is lethal")
if not combat.mark_damage(s, T, theirs, 1):
    die("decree", "'ANY unit' -- it reaches both players, not just the enemy")
s2 = GameState()
s2.phase, s2.active, s2.priority = MAIN, 0, 0
u = s2.add_permanent(big, 0, bf_loc(0))
s2.any_damage_kills = 1
if combat.mark_damage(s2, T, u, 0):
    die("decree", "143.2.a still requires NONZERO damage")
ok("Imperial Decree makes any nonzero damage lethal, for both players")

# Switcheroo: "Swap the Might of two units at the same battlefield this turn."
# The EFFECTIVE Mights swap, statics and buffs included -- not the printed
# corners -- and it goes through the turn-scoped modifier, so `set_might_mod`
# re-checks lethality for both. Swapping a damaged unit's Might DOWN kills it
# on the spot (143.2.a is continuous), which is the whole trick of the card.

def _unit_of_might(m):
    return next(c for c in range(T.n) if T.is_type(c, "Unit")
                and not T.is_token(c) and int(T.might[c]) == m)


SW_SMALL, SW_BIG = _unit_of_might(2), _unit_of_might(6)

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
a = s.add_permanent(SW_SMALL, 0, bf_loc(0))
b = s.add_permanent(SW_BIG, 1, bf_loc(0))
rsv.resolve(s, T, V1, _SPECS["Switcheroo"], 0, [a, b], -1, True)
if (combat.might(s, T, a), combat.might(s, T, b)) != (6, 2):
    die("switcheroo", "the two Mights should have swapped")
ok("Switcheroo swaps two units' effective Might")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
x = s.add_permanent(SW_BIG, 0, bf_loc(0))
y = s.add_permanent(SW_SMALL, 1, bf_loc(0))
combat.mark_damage(s, T, x, 3)
if s.perms[x, P_ALIVE] != 1:
    die("switcheroo", "3 damage on a 6-Might unit is survivable")
rsv.resolve(s, T, V1, _SPECS["Switcheroo"], 0, [x, y], -1, True)
if s.perms[x, P_ALIVE] == 1:
    die("switcheroo", "143.2.a is continuous -- swapping Might DOWN onto "
                      "marked damage kills at once")
ok("...and 143.2.a rechecks lethality, so a damaged unit swapped down dies")

print("\n\033[32mall spell tests passed\033[0m")
