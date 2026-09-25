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
from rl.engine.state import (C_CARD, C_FINAL, F_BUFFED, F_STUNNED, P_ALIVE,
                             P_CTRL,
                             P_FLAGS, P_LOC,
                             GameState, base_loc, bf_loc)

T = full_table()
V0 = Config().at_victory_score(3).with_solved_damage()                      # units only
V1 = replace(Config().at_victory_score(3).with_solved_damage(), units_only=False)

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
                and not any(T.has(c, k) for k in ("Tank", "Backline", "Temporary",
                                                  "Deflect"))
                # No rules text, so scripting a card never turns a fixture
                # into something that fires triggers (Apprentice Smith did).
                and not T.residual_text(c)
                and not T.tags[c] & {"Bird", "Cat", "Dog", "Poro"}):
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
in_play_before = int(s.runes_in_play(0).sum())
ring_before = int(s.rune_left[0])

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
# 811.1.b's cost is [A] -- POWER, and a rune only makes Power by being
# RECYCLED (164.2.b). So the rune must LEAVE the board for the bottom of the
# Rune Deck, not merely exhaust. The `runes_ready` check above cannot tell the
# two apart on a board of all-ready runes, which is exactly how charging an
# exhaust here went unnoticed; these two can.
if int(s.runes_in_play(0).sum()) != in_play_before - 1:
    die("hidden", "[A] is Power -- hiding must RECYCLE the rune, not exhaust "
                  "it; the board should be one rune smaller")
if int(s.rune_left[0]) != ring_before + 1:
    die("hidden", "the recycled rune must be back in the Rune Deck (416.1.b)")
ok("hiding recycles one rune for [A], opens no chain, fills the facedown zone")

# The other half of the same rule, and the half that was refusing legal plays:
# recycling has NO ready requirement (164.2.b), so a board of nothing but
# EXHAUSTED runes can still pay [A]. The old gate asked for a ready rune and
# said no.
s2 = fresh(hand0=(BACK_OFF,))
s2.add_permanent(unit(3), 0, bf_loc(0))
s2.bf_ctrl[0] = 0
s2.runes_spent[0] += s2.runes_ready[0]         # tap out entirely
s2.runes_ready[0] = 0
if not [a for a in A.legal_actions(s2, T, V1, 0) if a.kind == A.A_HIDE]:
    die("hidden", "164.2.b -- an exhausted rune is still a legal Power source, "
                  "so a tapped-out board can still pay [A] to hide")
spent_before = int(s2.runes_spent[0].sum())
A.apply(s2, T, V1, next(a for a in A.legal_actions(s2, T, V1, 0)
                        if a.kind == A.A_HIDE))
A.apply(s2, T, V1, A.Action(A.A_HIDE_AT, 0))
if int(s2.runes_spent[0].sum()) != spent_before - 1:
    die("hidden", "the exhausted rune should have been the one recycled")
ok("...and an exhausted rune pays it, because recycling needs no ready rune")

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
print("\n[8] a spell that drags a unit in opens a Showdown the defender can answer")
# 464.2.d/345 give Focus to the player who applied Contested. 340.2.a's "focus
# passes to the next player" does NOT apply here, and both of its conditions are
# why: it is scoped to a Chain emptying *during* a Showdown, and this Showdown
# does not exist until the Cleanup that follows opens it. The defender still
# gets a window -- second rather than first -- which is what the window is for.
#
# **Seat 0 casts the spell and seat 1 ends up the Attacker**, which is worth
# reading twice. 190.3.a applies Contested "when a Unit controlled by a Player
# who does not currently Control that Battlefield ... becomes present there",
# and 464.2.c.1 designates the player whose UNIT did so. Charm makes seat 1's
# unit become present at a battlefield seat 1 does not control, so seat 1
# applied Contested and seat 1 attacks -- the caster is the defender of their
# own ground. That is not a quirk of this test; it is what makes drag effects
# double-edged, since 466.1.a.2 then Recalls the dragged unit if the defender
# survives. The engine used to answer "whoever moved last", which named seat 0
# here and inverted [Assault]/[Shield] and the Recall with it.
CHARM, GUST = T.id_of("Charm"), T.id_of("Gust")
# The Reaction sits in the CASTER's hand, because the caster is the defender
# here -- see the note above.
s = fresh(hand0=(CHARM, GUST), hand1=())
s.n_deck[:] = 5
s.deck[:, :5] = T.id_of("Stupefy")
mine = s.add_permanent(unit(3), 0, bf_loc(0))
s.bf_ctrl[0] = 0
foe = s.add_permanent(unit(2), 1, base_loc(1))

play = next(a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == CHARM)
A.apply(s, T, V1, play)
A.apply(s, T, V1, A.Action(A.A_TARGET, foe))
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(0)))
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, A.PASS)                       # Charm resolves, chain empties

if s.showdown_bf < 0:
    die("priority", "dragging an enemy in should stage a Combat (461)")
if int(s.attacker) != 1:
    die("priority", f"464.2.c.1 -- seat 1's unit applied Contested, so seat 1 "
                    f"attacks; got seat {int(s.attacker)}")
if A.acting_seat(s) != 1:
    die("priority", f"464.2.d -- the Attacker gains Focus as the Showdown "
                    f"opens, got seat {A.acting_seat(s)}")
A.apply(s, T, V1, A.PASS)                       # the attacker declines
if A.acting_seat(s) != 0:
    die("priority", f"Focus should pass to the defender, got "
                    f"seat {A.acting_seat(s)}")
if not any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("priority", "the defender must be able to answer before combat locks in")
ok("the Attacker opens the window; the defender answers before combat locks in")

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
from rl.engine.effects import ABILITIES, SPECS as _SPECS
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

# A target restricted by DOMAIN ("an enemy Chaos unit or gear"), and a
# condition on the rune BOARD ("if you control 4 or fewer runes" -- ready plus
# spent, since an exhausted rune is still controlled).

CHAOS_UNIT = next(c for c in range(T.n) if T.is_type(c, "Unit")
                  and not T.is_token(c) and int(T.domain_mask[c]) >> 2 & 1)
OTHER_UNIT = next(c for c in range(T.n) if T.is_type(c, "Unit")
                  and not T.is_token(c) and not (int(T.domain_mask[c]) >> 2 & 1))

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
chaos = s.add_permanent(CHAOS_UNIT, 1, bf_loc(0))
s.add_permanent(OTHER_UNIT, 1, bf_loc(0))
if rsv.legal_targets(s, T, _SPECS["Decree of Unity"], 0, 0, [], -1) != [chaos]:
    die("domain", "only the enemy CHAOS unit is a legal target")
ok("a domain-restricted slot admits only that domain")

ECLIPSE_AB = ABILITIES["Eclipse Dragon"][0]
for runes, want in ((4, 1), (5, 0)):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    d = s.add_permanent(T.id_of("Eclipse Dragon"), 0, bf_loc(0))
    s.runes_ready[0, 0] = runes
    s.n_deck[0] = 10
    # 383.2.a.1 -- "When I move, IF you control 4 or fewer runes" is part of
    # the trigger condition, asked as it triggers (`chain.ability_cond_holds`).
    from rl.engine.chain import ability_cond_holds as _ach
    if _ach(s, T, ECLIPSE_AB, 0, d):
        rsv.resolve(s, T, V1, ECLIPSE_AB, 0, [], -1, True, source=d)
    if int(s.n_hand[0]) != want:
        die("runes", f"with {runes} runes the draw should be {want}")
ok("...and '4 or fewer runes' is exact at the boundary")

# Thermo Beam: "Kill all gear." The board sweep had always been units-only,
# because every wipe before this one was -- so the TYPE is a field on the op
# rather than a second op, defaulting to Unit so nothing existing changes.

TB_GEAR = next(c for c in range(T.n) if T.is_type(c, "Gear") and not T.is_token(c))
TB_UNIT = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
mine_g = s.add_permanent(TB_GEAR, 0, base_loc(0))
their_g = s.add_permanent(TB_GEAR, 1, base_loc(1))
mine_u = s.add_permanent(TB_UNIT, 0, bf_loc(0))
their_u = s.add_permanent(TB_UNIT, 1, bf_loc(0))
rsv.resolve(s, T, V1, _SPECS["Thermo Beam"], 0, [], -1, True)
if s.perms[mine_g, P_ALIVE] or s.perms[their_g, P_ALIVE]:
    die("thermo", "'all gear' reaches BOTH players, the caster's included")
if not (s.perms[mine_u, P_ALIVE] and s.perms[their_u, P_ALIVE]):
    die("thermo", "...and leaves units alone")
ok("a typed board sweep: 'kill all gear' spares every unit")

# Thwonk!: "Stun an ATTACKING unit." 459 designates the Attacker's units at the
# contested battlefield as the attacking ones, so outside a Showdown nothing is
# attacking and the card cannot be played at all (355.8).

TW_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))
s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
atk = s.add_permanent(TW_BODY, 0, bf_loc(0))
s.add_permanent(TW_BODY, 1, bf_loc(0))
if rsv.legal_targets(s, T, _SPECS["Thwonk!"], 0, 1, [], -1):
    die("thwonk", "outside a Showdown nothing is attacking")
combat.open_showdown(s, T, 0, attacker=0)
if rsv.legal_targets(s, T, _SPECS["Thwonk!"], 0, 1, [], -1) != [atk]:
    die("thwonk", "only the ATTACKER's units at the contested battlefield")
ok("459 -- 'an attacking unit' needs a Showdown, and means the attacker's")

# Piercing Light: "Deal 2 to a unit at a battlefield, then deal 2 to up to one
# OTHER unit." The second slot is "up to one" (355.14, may be left empty) and
# "other" -- a different UNIT, with no location clause of its own, so it can
# reach a unit sitting safely in a base.
#
# `distinct_from`, not `rel`: every `rel` value ties the two slots' LOCATIONS
# together, and REL_DIFFERENT_LOC means a different PLACE. Using it for
# "another" is a mistake this codebase has made before.

PL_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))
s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
at_bf_a = s.add_permanent(PL_BODY, 1, bf_loc(0))
at_bf_b = s.add_permanent(PL_BODY, 1, bf_loc(0))
in_base = s.add_permanent(PL_BODY, 1, base_loc(1))

if in_base in rsv.legal_targets(s, T, _SPECS["Piercing Light"], 0, 0, [], -1):
    die("piercing", "slot 0 says 'at a battlefield'")
second = rsv.legal_targets(s, T, _SPECS["Piercing Light"], 1, 0, [at_bf_a], -1)
if at_bf_a in second:
    die("piercing", "'OTHER unit' excludes the one already chosen")
if in_base not in second:
    die("piercing", "...but carries no location clause, so a base unit qualifies")
ok("'up to one other unit' is a different UNIT, not a different location")

# Draws scaled by a board count.
#
# Right of Conquest: "Draw 1, then draw 1 FOR EACH battlefield you control."
# Kadregrin: "draw 1 for each of your [Mighty] units" -- 5+ Might, and
# EFFECTIVE Might, so statics and buffs count. Kadregrin is already on the
# board when this resolves (359.2.b), so it counts itself if it qualifies.

def _u_of(m):
    return next(c for c in range(T.n) if T.is_type(c, "Unit")
                and not T.is_token(c) and int(T.might[c]) == m)


for n_bf in (0, 1, 2):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.n_deck[0] = 20
    for i in range(n_bf):
        s.bf_ctrl[i] = 0
    rsv.resolve(s, T, V1, _SPECS["Right of Conquest"], 0, [], -1, True)
    if int(s.n_hand[0]) != 1 + n_bf:
        die("conquest", f"1 plus one per battlefield: {n_bf} should draw {1+n_bf}")
ok("a draw scaled by battlefields controlled")

KADREGRIN = T.id_of("Kadregrin the Infernal")
s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
s.n_deck[0] = 20
k = s.add_permanent(KADREGRIN, 0, base_loc(0))
for m in (2, 6, 5):
    s.add_permanent(_u_of(m), 0, base_loc(0))
rsv.resolve(s, T, V1, ABILITIES["Kadregrin the Infernal"][0], 0, [], -1, True,
            source=k)
# Mighty = 5+: Kadregrin itself, the 6 and the 5. The 2 does not count.
want = 1 + sum(1 for m in (6, 5) if m >= 5)
if int(s.n_hand[0]) != want:
    die("kadregrin", f"[Mighty] is 5+ Might; expected {want} draws")
ok("...and one by [Mighty] units, counting itself and excluding the small one")

# Against the Odds: "+2 Might this turn FOR EACH enemy unit there." The count
# MULTIPLIES `n` rather than replacing it, so `n` is the per-enemy rate --
# and "there" is the chosen unit's location, not the caster's, so an enemy at
# the other battlefield does not count.

ATO_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))
for n_enemies in (0, 1, 3):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    friend = s.add_permanent(ATO_BODY, 0, bf_loc(0))
    for _ in range(n_enemies):
        s.add_permanent(ATO_BODY, 1, bf_loc(0))
    s.add_permanent(ATO_BODY, 1, bf_loc(1))        # elsewhere: must not count
    before = combat.might(s, T, friend)
    rsv.resolve(s, T, V1, _SPECS["Against the Odds"], 0, [friend], -1, True)
    if combat.might(s, T, friend) - before != 2 * n_enemies:
        die("odds", f"{n_enemies} enemies there should give +{2*n_enemies}")
ok("'for each enemy unit THERE' scales by the target's location, not the caster's")


# ---------------------------------------------------------------------------
print("\n[9] a printed 'kill a [...] as an additional cost' (820)")
SACRIFICE = T.id_of("Sacrifice")
MIGHTY = unit(5)          # a friendly [Mighty] (5+ Might) candidate
SMALL = unit(2)           # friendly, but too small to pay the cost
BIG_ENEMY = unit(6)       # Mighty, but not friendly

# With nothing eligible, Sacrifice cannot be played at all -- the same
# 359.3.e.14.a deadlock `can_be_cast` catches for an ordinary target, applied
# to a REQUIRED cost instead.
s = fresh(hand0=(SACRIFICE,))
s.add_permanent(SMALL, 0, base_loc(0))
s.add_permanent(BIG_ENEMY, 1, base_loc(1))
acts = A.legal_actions(s, T, V1, 0)
if any(a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == SACRIFICE for a in acts):
    die("cost_kill gate", "Sacrifice offered with no eligible kill target")
ok("an unpayable printed kill cost keeps the card off the play list entirely")

# With one, the cost is chosen (and paid) before the card's own effect: only
# a friendly [Mighty] unit is ever offered -- never the small friendly body,
# never the Mighty enemy.
s = fresh(hand0=(SACRIFICE,))
small = s.add_permanent(SMALL, 0, base_loc(0))
mighty = s.add_permanent(MIGHTY, 0, base_loc(0))
enemy = s.add_permanent(BIG_ENEMY, 1, base_loc(1))
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == SACRIFICE)
A.apply(s, T, V1, play)
if s.pend_cost_kill < 0:
    die("cost_kill", "playing Sacrifice should open the cost-kill decision")
opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
if opts != {mighty}:
    die("cost_kill options", f"expected only the Mighty unit, got {opts}")
ok("only a friendly [Mighty] unit is offered to pay the cost")

hand_before = int(s.n_hand[0])
A.apply(s, T, V1, A.Action(A.A_TARGET, mighty))
# 820 -- the cost is paid at finalization, immediately; the SPELL itself is
# only finalized, not resolved, so it still waits on mutual pass (339.1)
# exactly like any other Chain item.
if s.perms[mighty, P_ALIVE] != 0:
    die("cost_kill", "the chosen unit should already be dead -- a cost, not "
                     "part of resolution")
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != MIGHTY:
    die("cost_kill", "a killed cost target is a real kill -- it lands in the trash")
if int(s.n_hand[0]) != hand_before:
    die("cost_kill", "the draw is the SPELL's effect and must wait on the chain")
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, A.PASS)                # both passed -> 339.1 -> resolve
if int(s.n_hand[0]) != hand_before + 2:
    die("cost_kill", "mutual pass should resolve Sacrifice's own effect (draw 2)")
if s.perms[small, P_ALIVE] != 1 or s.perms[enemy, P_ALIVE] != 1:
    die("cost_kill", "only the chosen unit should have died")
ok("paying the cost kills exactly the chosen unit; the card's own effect "
   "still waits on mutual pass")


# ---------------------------------------------------------------------------
print("\n[10] the same printed cost, on a UNIT (337.2 -- no Chain at all)")
from rl.engine.state import P_CARD
CRUEL_PATRON = T.id_of("Cruel Patron")
PATRON_FODDER = unit(2)

# With nothing to kill, Cruel Patron cannot be played at all -- same gate as
# Sacrifice, but reached through the unit hand-play loop instead of
# `chain.playable_hand_indices`.
s = fresh(hand0=(CRUEL_PATRON,))
acts = A.legal_actions(s, T, V1, 0)
if any(a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == CRUEL_PATRON
      for a in acts):
    die("unit cost_kill gate", "Cruel Patron offered with no eligible target")
ok("an unpayable printed kill cost keeps a UNIT off the play list too")

# With one, playing it opens the kill-target decision BEFORE the destination
# choice -- Stalking Wolf's "you may play me to its battlefield" needs this
# order, even though Cruel Patron itself does not use it.
s = fresh(hand0=(CRUEL_PATRON,))
fodder = s.add_permanent(PATRON_FODDER, 0, base_loc(0))
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == CRUEL_PATRON)
A.apply(s, T, V1, play)
if s.pend_kill_play < 0:
    die("unit cost_kill", "playing Cruel Patron should open the kill decision")
if s.pend_play >= 0:
    die("unit cost_kill", "the destination choice must wait for the cost")
opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
if opts != {fodder}:
    die("unit cost_kill options", f"expected only the one friendly unit, got {opts}")
A.apply(s, T, V1, A.Action(A.A_TARGET, fodder))
if s.perms[fodder, P_ALIVE] != 0 or int(s.n_trash[0]) != 1:
    die("unit cost_kill", "the chosen unit should be dead, paid as the cost")
if s.pend_play < 0:
    die("unit cost_kill", "paying the cost should open the destination choice")
dsts = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT]
if not dsts:
    die("unit cost_kill", "Cruel Patron should now have a base to land on")
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, dsts[0]))
if not any(s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == CRUEL_PATRON
          for i in range(s.n_perms)):
    die("unit cost_kill", "Cruel Patron should be on the board")
ok("a UNIT's own printed kill cost is paid before its destination is chosen, "
   "with no Chain item involved")


# ---------------------------------------------------------------------------
print("\n[11] a printed destination tied to the SAME cost_kill (820 + 822.1.d)")
STALKING_WOLF = T.id_of("Stalking Wolf")
CAT_FODDER = T.id_of("Pakaa Cub")
NON_TAGGED = unit(2)

# Only a Bird/Cat/Dog/Poro pays the cost -- an ordinary friendly unit does
# not, even though Sacrifice's plain W_FRIENDLY would take it.
s = fresh(hand0=(STALKING_WOLF,))
s.add_permanent(NON_TAGGED, 0, base_loc(0))
acts = A.legal_actions(s, T, V1, 0)
if any(a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == STALKING_WOLF
      for a in acts):
    die("wolf tag gate", "Stalking Wolf offered with only a non-tagged unit")
ok("only a tagged (Bird/Cat/Dog/Poro) unit pays the cost, not any friendly")

# Killing it AT A BATTLEFIELD opens that battlefield as an extra destination,
# on top of the ordinary base -- with no ally of ours there at all.
s = fresh(hand0=(STALKING_WOLF,))
cat = s.add_permanent(CAT_FODDER, 0, bf_loc(0))
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == STALKING_WOLF)
A.apply(s, T, V1, play)
A.apply(s, T, V1, A.Action(A.A_TARGET, cat))
if int(s.pend_kill_play_loc) != bf_loc(0):
    die("wolf loc", "the killed unit's battlefield should be captured")
dsts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT}
if dsts != {base_loc(0), bf_loc(0)}:
    die("wolf dest", f"expected base + the kill's own battlefield, got {dsts}")
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, bf_loc(0)))
if int(s.pend_kill_play_loc) != -1:
    die("wolf loc leak", "the captured location must not survive the play")
if not any(s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == STALKING_WOLF
          and int(s.perms[i, P_LOC]) == bf_loc(0) for i in range(s.n_perms)):
    die("wolf dest", "Stalking Wolf should have landed at the vacated battlefield")
ok("killing a tagged unit AT A BATTLEFIELD opens that battlefield as a destination")

# Killing one at a BASE grants nothing extra -- "its BATTLEFIELD", not "its
# location".
s = fresh(hand0=(STALKING_WOLF,))
cat = s.add_permanent(CAT_FODDER, 0, base_loc(0))
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == STALKING_WOLF)
A.apply(s, T, V1, play)
A.apply(s, T, V1, A.Action(A.A_TARGET, cat))
dsts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT}
if dsts != {base_loc(0)}:
    die("wolf base kill", f"a base kill should grant no battlefield, got {dsts}")
ok("...but killing one AT A BASE grants no battlefield -- the text says so")

# The dynamic destination also makes it AMBUSH-playable with no ally of ours
# already at any battlefield -- the whole point of the "(even if you don't
# have other units there)" reminder.
s = fresh(hand0=(STALKING_WOLF,))
s.add_permanent(CAT_FODDER, 0, bf_loc(0))
if int(s.pend_kill_play_loc) != -1:
    die("wolf ambush setup", "no kill has happened yet")
hand_idx = next(i for i in range(int(s.n_hand[0]))
               if int(s.hand[0, i]) == STALKING_WOLF)
if hand_idx not in A.ambush_playable(s, T, V1, 0):
    die("wolf ambush offer", "should be ambush-playable: killing the Cat "
                             "opens a legal destination even with no allies "
                             "already at any battlefield")
ok("ambush offering accounts for a destination the cost itself would open")


# ---------------------------------------------------------------------------
print("\n[12] a later slot CAPPED by the same cost_kill (820, coupled slots)")
HEEDLESS = T.id_of("Heedless Resurrection")
CHEAP_KILL = T.id_of("Determined Sentry")     # 1 energy, 0 power
PRICEY_KILL = T.id_of("Arachnoid Horror")     # 6 energy, 1 power
TRASH_UNIT = T.id_of("Apprentice Smith")      # 2 energy, 0 power -- too much
                                              # for CHEAP_KILL, fine for PRICEY

# With only the cheap kill available, NO trash unit ever qualifies -- offering
# the card at all would be a deadlock waiting to happen (359.3.e.14.a).
s = fresh(hand0=(HEEDLESS,))
s.add_permanent(CHEAP_KILL, 0, base_loc(0))
s.trash[0, 0] = TRASH_UNIT
s.n_trash[0] = 1
acts = A.legal_actions(s, T, V1, 0)
if any(a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == HEEDLESS for a in acts):
    die("heedless deadlock", "offered with no kill choice that unlocks a "
                             "legal trash unit -- this would deadlock")
ok("a card whose ONLY kill choice deadlocks its own later slot is not offered")

# With a second, pricier candidate on the board, the card becomes playable --
# but the CHEAP kill must not be offered as a choice, because taking it would
# still deadlock the trash-unit slot right after.
s = fresh(hand0=(HEEDLESS,))
cheap = s.add_permanent(CHEAP_KILL, 0, base_loc(0))
pricey = s.add_permanent(PRICEY_KILL, 0, base_loc(0))
s.trash[0, 0] = TRASH_UNIT
s.n_trash[0] = 1
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == HEEDLESS)
A.apply(s, T, V1, play)
kill_opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
if kill_opts != {pricey}:
    die("heedless kill choice", f"only the kill that unlocks a trash unit "
                                f"should be offered, got {kill_opts}")
ok("only the kill choice that leaves the trash-unit slot fillable is offered")

A.apply(s, T, V1, A.Action(A.A_TARGET, pricey))
if s.perms[pricey, P_ALIVE] != 0 or s.perms[cheap, P_ALIVE] != 1:
    die("heedless kill", "the chosen (pricey) unit should be the one dead")
trash_opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
from rl.engine.resolve import pack_trash
want = pack_trash(0, TRASH_UNIT)
# The just-killed unit is now IN the trash too, but it is NOT a choice: the
# trash unit is chosen before the kill cost is paid (355 before 357), so the
# killed unit was not there to be chosen (RiftJudge #11472).
if trash_opts != {want}:
    die("heedless trash slot", f"expected {TRASH_UNIT} and the killed unit "
                               f"itself, got {trash_opts}")
A.apply(s, T, V1, A.Action(A.A_TARGET, want))
# The destination is the spell's OWN second target slot (TK_LOCATION), so
# it is an A_TARGET too, not A_PLAY_AT -- that action belongs to the
# separate direct unit/gear-from-hand flow this spell never goes through.
dst = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET)
A.apply(s, T, V1, dst)
if any(s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == TRASH_UNIT
      for i in range(s.n_perms)):
    die("heedless resurrect", "finalizing must not resolve it -- it still "
                              "waits on mutual pass, same as any spell")
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, A.PASS)                # both passed -> 339.1 -> resolve
if not any(s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == TRASH_UNIT
          for i in range(s.n_perms)):
    die("heedless resurrect", "the trash unit should now be on the board")
# The killed unit stays there, and Heedless Resurrection itself joins it once
# it resolves (349) -- the resurrected unit is the only card that LEFT.
trash_now = {int(x) for x in s.trash[0, :int(s.n_trash[0])]}
if trash_now != {PRICEY_KILL, HEEDLESS}:
    die("heedless trash", f"expected the killed unit plus the spell itself, "
                          f"got {trash_now}")
ok("the capped slot resolves correctly, and the reanimated unit is free")


# ---------------------------------------------------------------------------
print("\n[13] a PERMANENT played from face down (811.1.d.1, 811.6)")
from rl.engine import phases as _ph
from rl.engine.effects import SPEED_MAIN
from rl.engine.state import F_FROM_HIDDEN
PAKAA_CUB = T.id_of("Pakaa Cub")          # [Hidden] vanilla unit, no spec

# A [Hidden] UNIT is hideable at all. It has no `SPECS` entry -- none of the
# pool's 14 [Hidden] units do -- and requiring one buried every one of them.
s = fresh(hand0=(PAKAA_CUB,))
s.add_permanent(unit(3), 0, bf_loc(0))
s.bf_ctrl[0] = 0
hide = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE]
if not hide:
    die("hidden unit", "a [Hidden] UNIT must be hideable -- it needs no spec, "
                       "337.2 just puts it on the board")
A.apply(s, T, V1, hide[0])
A.apply(s, T, V1, A.Action(A.A_HIDE_AT, 0))
ok("a [Hidden] unit with no DSL spec can be hidden (it is not a spell)")

_ph.end_turn(s, V1)
if not chain.hidden_playable(s, T, V1, 0):
    die("hidden unit", "a hidden unit should be playable from the next turn")
ok("...and is playable from hiding on the next turn")

# 811.1.d.1 -- it goes to the battlefield it was hidden at, with NO
# destination choice: `pend_play` never opens.
s.active, s.phase, s.priority = 0, MAIN, 0
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY_HIDDEN)
A.apply(s, T, V1, play)
if s.pend_play >= 0:
    die("hidden unit", "811.1.d.1 -- a hidden permanent has no destination "
                       "choice; it must go to its own battlefield")
row = next((i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
           and int(s.perms[i, P_CARD]) == PAKAA_CUB), -1)
if row < 0 or int(s.perms[row, P_LOC]) != bf_loc(0):
    die("hidden unit", "it should be on the board at the bound battlefield")
if not int(s.perms[row, P_FLAGS]) & F_FROM_HIDDEN:
    die("hidden unit", "F_FROM_HIDDEN should record how it arrived")
if int(s.fd_owner[0]) != -1:
    die("hidden unit", "the facedown zone should be empty again")
ok("811.1.d.1 -- it lands on its own battlefield, no destination decision")

# 811.6 -- THE RULE THIS SECTION EXISTS FOR. A card that is Hidden gains
# [Reaction] while facedown, "and may be played any time a card with Reaction
# may be played as a result". Pakaa Cub is a plain Main-speed unit: no
# [Reaction], no [Ambush]. From hand it is a Main-Phase-only play, and
# `speed_ok` refuses it in a Showdown on the opponent's turn. From HIDING it
# must be offered in exactly that window.
s = fresh(hand0=(PAKAA_CUB,))
s.bf_ctrl[0] = 0
s.fd_owner[0], s.fd_card[0], s.fd_ply[0] = 0, PAKAA_CUB, -1
s.n_hand[0] = 0                           # it is facedown, not in hand
s.add_permanent(unit(3), 0, bf_loc(0))
s.active = 1                              # the OPPONENT's turn
s.priority = 0                            # ...and we hold priority in a window
s.showdown_bf = 0
s.bf_contested[0] = 1
s.attacker = 1
s.add_permanent(unit(4), 1, bf_loc(0))
if chain.speed_ok(s, V1, 0, SPEED_MAIN):
    die("811.6", "test setup wrong -- a Main-speed card should be refused "
                 "in this window, or the check below proves nothing")
if 0 not in chain.hidden_playable(s, T, V1, 0):
    die("811.6", "a facedown Main-speed unit must still be playable on the "
                 "opponent's turn -- 811.6 grants it [Reaction]")
acts = A.legal_actions(s, T, V1, 0)
if not any(a.kind == A.A_PLAY_HIDDEN and a.arg == 0 for a in acts):
    die("811.6", "the action layer must offer it too, not just the predicate")
A.apply(s, T, V1, A.Action(A.A_PLAY_HIDDEN, 0))
if not any(s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == PAKAA_CUB
          and int(s.perms[i, P_LOC]) == bf_loc(0) for i in range(s.n_perms)):
    die("811.6", "it should have arrived at the contested battlefield")
ok("811.6 -- a NON-Reaction card is playable reactively from face down, "
   "mid-Showdown on the opponent's turn")


# ---------------------------------------------------------------------------
print("\n[14] 'when you play me FROM FACE DOWN on your turn' (Evelynn)")
EVELYNN = T.id_of("Evelynn - Entrancing")

def _evelynn_hidden(active=0):
    """Evelynn facedown at battlefield 0, with an enemy at each location."""
    st = fresh(hand0=())
    st.bf_ctrl[0] = 0
    st.fd_owner[0], st.fd_card[0], st.fd_ply[0] = 0, EVELYNN, -1
    st.add_permanent(unit(3), 0, bf_loc(0))
    st.active, st.priority = active, 0
    return st

# Played from HAND the trigger must not fire at all -- "from face down" is a
# narrowing of the trigger (359.3.f), not a condition that fizzles the effect.
# A fizzling version would still ask the "you may", which is the tell.
s = fresh(hand0=(EVELYNN,))
s.bf_ctrl[0] = 0
here = s.add_permanent(unit(3), 0, bf_loc(0))
far = s.add_permanent(unit(4), 1, bf_loc(1))
play = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == EVELYNN)
A.apply(s, T, V1, play)
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, bf_loc(0)))
if s.pend_may >= 0 or s.n_chain:
    die("evelynn", "played from HAND, the trigger must not fire at all")
if int(s.perms[far, P_LOC]) != bf_loc(1):
    die("evelynn", "nothing should have moved")
ok("played from hand it does nothing -- the trigger never fires")

# Played from face down on YOUR turn: the "you may" is offered, and the only
# legal target is the enemy at a DIFFERENT location.
s = _evelynn_hidden(active=0)
near = s.add_permanent(unit(2), 1, bf_loc(0))   # same battlefield -- illegal
far = s.add_permanent(unit(4), 1, bf_loc(1))    # different -- the only option
A.apply(s, T, V1, A.Action(A.A_PLAY_HIDDEN, 0))
if s.pend_may < 0:
    die("evelynn", "383.3.a -- the 'you may' should be offered at finalization")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
if opts != {far}:
    die("evelynn", f"'at a different location' should offer only the far "
                   f"enemy, got {opts}")
ok("only an enemy at a DIFFERENT location is a legal target")

A.apply(s, T, V1, A.Action(A.A_TARGET, far))
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, A.PASS)
if int(s.perms[far, P_LOC]) != bf_loc(0):
    die("evelynn", "the enemy should have been dragged to her battlefield")
if int(s.perms[near, P_LOC]) != bf_loc(0):
    die("evelynn", "the near enemy should not have moved")
ok("...and it is dragged to her battlefield (T_HERE is where she was hidden)")

# 811.6 lets her be played on the OPPONENT'S turn -- and then "on your turn"
# excludes the trigger. The card is still playable; it just does nothing.
s = _evelynn_hidden(active=1)
s.add_permanent(unit(4), 1, bf_loc(1))
if 0 not in chain.hidden_playable(s, T, V1, 0):
    die("evelynn", "811.6 -- she is still PLAYABLE on the opponent's turn")
A.apply(s, T, V1, A.Action(A.A_PLAY_HIDDEN, 0))
if s.pend_may >= 0 or s.n_chain:
    die("evelynn", "'on your turn' must suppress the trigger on the "
                   "opponent's turn -- 811.6 makes this reachable")
ok("...but on the OPPONENT's turn the trigger is suppressed by 'on your turn'")


# ---------------------------------------------------------------------------
print("\n[15] bystanders watching the Facedown Zone (811.1.c.1)")
from rl.engine.state import P_DMG, P_READY
KATARINA = T.id_of("Katarina - Reckless")

# 811.1.c.1 -- "Hide is not a subset of Play". Katarina prints BOTH clauses
# because neither implies the other, so the two events must not cross-fire.
s = fresh(hand0=(BACK_OFF,))
s.bf_ctrl[0] = 0
s.add_permanent(unit(3), 0, bf_loc(0))
kat = s.add_permanent(KATARINA, 0, base_loc(0))
foe = s.add_permanent(unit(4), 1, bf_loc(1))
s.perms[kat, P_READY] = 0                 # exhausted, so readying is visible

hide = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE)
A.apply(s, T, V1, hide)
A.apply(s, T, V1, A.Action(A.A_HIDE_AT, 0))
# 811.1.c.2 keeps the HIDE itself off the Chain, but the ability it triggers
# is an ordinary Chain Item and still waits on mutual pass (339.1).
if s.n_chain != 1:
    die("katarina", "the hide watcher should be a Chain Item awaiting priority")
if s.perms[kat, P_READY]:
    die("katarina", "it must not resolve before both players pass")
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, A.PASS)
if not s.perms[kat, P_READY]:
    die("katarina", "'when you hide a card, ready me' should have fired")
if int(s.perms[foe, P_DMG]):
    die("katarina", "811.1.c.1 -- hiding is NOT playing; the shoot half must "
                    "not fire on a hide")
ok("hiding fires the hide watcher only -- Hide is not a subset of Play")

# ...and now playing it back fires the OTHER half, not the first.
s.perms[kat, P_READY] = 0                 # re-exhaust: readying must not recur
s.fd_ply[0] = -1                          # 811.1.b -- live now
A.apply(s, T, V1, A.Action(A.A_PLAY_HIDDEN, 0))
# Back Off (the hidden card) is the older Chain Item, so 359.3.b fills ITS
# slot first -- and 811.1.d.2 binds that slot to battlefield 0, which is why
# the far enemy is not among its options. Katarina's watcher is a separate,
# unbound item behind it.
for _ in range(12):
    seat_now = A.acting_seat(s)
    if seat_now < 0:
        break
    acts = A.legal_actions(s, T, V1, seat_now)
    pick = next((a for a in acts if a.kind == A.A_TARGET and a.arg == foe),
                None)
    if pick is not None:
        A.apply(s, T, V1, pick)
        continue
    tgt = [a for a in acts if a.kind == A.A_TARGET]
    A.apply(s, T, V1, tgt[0] if tgt else A.PASS)
    if not s.n_chain and not s.n_trig:
        break
if int(s.perms[foe, P_DMG]) < 2:
    die("katarina", "'when you play a card from face down, deal 2' should "
                    f"have dealt 2, marked {int(s.perms[foe, P_DMG])}")
if s.perms[kat, P_READY]:
    die("katarina", "playing from face down is NOT hiding; the ready half "
                    "must not fire on a play")
ok("...and playing it back fires the play watcher only, never both")

# ---------------------------------------------------------------------------
print("\n[16] Hard Bargain: counter a spell UNLESS its controller pays {2}")
# The first effect in the pool that hands a decision to the player whose card
# is being answered, in the middle of someone else's spell resolving.

HARD_BARGAIN = T.id_of("Hard Bargain")


def _taxed(energy1=5, runes1=0):
    """Seat 1's Back Off on the Chain, seat 0's Hard Bargain answering it."""
    st = fresh()
    st.pool_energy[0] = 5
    st.pool_energy[1] = energy1
    st.runes_ready[1, :] = 0
    if runes1:
        st.runes_ready[1, 0] = runes1
    victim = chain.push(st, BACK_OFF, 1)
    chain.finalize(st, victim)
    hb = chain.push(st, HARD_BARGAIN, 0)
    st.chain_targets[chain.index_of_uid(st, hb)][0] = victim
    chain.finalize(st, hb)
    chain.resolve_top(st, T, V1)
    return st, victim


# The choice belongs to the SPELL's controller, not to Hard Bargain's.
s, victim = _taxed()
if int(s.pend_tax) != 1:
    die("tax", "the spell's controller is the one asked to pay, not the "
               f"player who cast Hard Bargain (pend_tax={int(s.pend_tax)})")
if A.acting_seat(s) != 1:
    die("tax", "acting_seat must follow the pending tax to seat 1")
if A.legal_actions(s, T, V1, 0):
    die("tax", "the taxing player has no say in whether the tax is paid")
if {a.kind for a in A.legal_actions(s, T, V1, 1)} != {A.A_ACCEPT,
                                                              A.A_DECLINE}:
    die("tax", "the taxed seat is offered exactly pay-or-refuse")
ok("the tax is asked of the target spell's controller, and only them")

# Paying keeps the spell on the Chain and costs the energy.
s, victim = _taxed()
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
if int(s.pool_energy[1]) != 3:
    die("tax", f"paying {{2}} left {int(s.pool_energy[1])} of 5 energy")
if chain.index_of_uid(s, victim) < 0:
    die("tax", "a paid spell must survive -- 'unless' means the counter does "
               "not happen")
ok("paying {2 energy} keeps the spell on the Chain")

# Refusing counters it, and the card still reaches the trash (349).
s, victim = _taxed()
A.apply(s, T, V1, A.Action(A.A_DECLINE))
if int(s.pool_energy[1]) != 5:
    die("tax", "refusing must cost nothing")
if chain.index_of_uid(s, victim) >= 0:
    die("tax", "refusing must counter the spell")
if int(s.n_trash[1]) != 1:
    die("tax", "a countered spell was still played, so it reaches the trash")
ok("refusing counters it, and the countered card still reaches the trash")

# A seat that cannot pay is never asked -- a one-option choice is not a choice.
s, victim = _taxed(energy1=0)
if int(s.pend_tax) >= 0:
    die("tax", "a seat that cannot afford the tax must not be asked to decide")
if chain.index_of_uid(s, victim) >= 0:
    die("tax", "an unaffordable tax counters outright")
ok("an unaffordable tax counters outright instead of pending a fake choice")

# ...and "cannot pay" means runes too, not just the pool. Reading pool_energy
# alone would tax out a player with a full rune board for free.
s, victim = _taxed(energy1=0, runes1=3)
if int(s.pend_tax) < 0:
    die("tax", "three ready runes can pay {2 energy}; affordability must "
               "count runes the seat could still exhaust, not just the pool")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
if int(s.runes_ready[1].sum()) != 1:
    die("tax", "paying from runes must exhaust exactly two of them")
if chain.index_of_uid(s, victim) < 0:
    die("tax", "the spell paid for with runes must survive")
ok("...and affordability counts ready runes, not just the energy pool")


# ---------------------------------------------------------------------------
print("\n[17] Rally the Troops: a Delayed Trigger (389-390)")
# "When a friendly unit is played this turn, buff it. Draw 1."
#
# [Buff] was already implemented -- the blocker was the DELAYED half. 390.2
# makes this a real Triggered Ability with a window, not a continuous effect,
# so each firing is its own Chain Item and is finalized like any other
# (355.5.b). Its source is a spell that is in the trash by then, which is why
# it needs a sentinel source rather than a permanent row.

RALLY = T.id_of("Rally the Troops")
MATE = T.id_of("First Mate")


def _rallied(seat=0):
    st = fresh()
    st.deck[:, :20] = MATE
    h = chain.push(st, RALLY, seat)
    chain.finalize(st, h)
    chain.resolve_top(st, T, V1)
    return st


def _play_unit(st, seat, loc=None):
    """Play a unit for `seat` and drain whatever it triggers."""
    row = st.add_permanent(MATE, seat, bf_loc(0) if loc is None else loc)
    chain.fire_play_unit(st, T, seat, MATE, row)
    for _ in range(8):
        if int(st.n_trig):
            chain.place(st, T, V1, 0)
        elif int(st.n_chain):
            chain.finalize(st, 0)
            chain.resolve_top(st, T, V1)
        else:
            break
    return row


s = _rallied()
if int(s.delayed[0, 0]) != RALLY:
    die("rally", "resolving it must arm a Delayed Ability for its controller")
if int(s.n_hand[0]) != 1:
    die("rally", "the 'Draw 1' half must still happen on resolution")
ok("resolving arms a Delayed Ability and draws 1")

# A unit played afterwards is buffed -- via the Chain, not immediately.
s = _rallied()
row = s.add_permanent(MATE, 0, bf_loc(0))
chain.fire_play_unit(s, T, 0, MATE, row)
if int(s.n_trig) != 1:
    die("rally", "a friendly unit play must QUEUE the delayed trigger; "
                 f"queued {int(s.n_trig)}")
if s.perms[row, P_FLAGS] & F_BUFFED:
    die("rally", "the buff must not apply before the trigger resolves -- "
                 "390.2 makes it a Triggered Ability, so it is respondable")
chain.place(s, T, V1, 0)
if int(s.n_chain) != 1:
    die("rally", "the delayed trigger must become a real Chain Item")
chain.finalize(s, 0)
chain.resolve_top(s, T, V1)
if not (s.perms[row, P_FLAGS] & F_BUFFED):
    die("rally", "the unit was not buffed once the trigger resolved")
if combat.might(s, T, row) != int(T.might[MATE]) + 1:
    die("rally", "703 -- a Buff counter is +1 Might")
ok("a friendly unit played after it is buffed, through the Chain")

# The window is "this turn" (390.2), and 359.3.e.16 is the other half.
s = _rallied()
_ph.end_turn(s, V1, T)
if int(s.delayed[0, 0]) >= 0:
    die("rally", "390.2 -- the delayed ability's window is THIS TURN")
row = s.add_permanent(MATE, 0, bf_loc(0))
chain.fire_play_unit(s, T, 0, MATE, row)
if int(s.n_trig):
    die("rally", "359.3.e.16 -- an expired delayed ability must not fire")
ok("the window ends with the turn, and an expired one never fires")

# "a FRIENDLY unit" -- the opponent's plays are not watched.
s = _rallied(seat=0)
foe_row = s.add_permanent(MATE, 1, bf_loc(0))
chain.fire_play_unit(s, T, 1, MATE, foe_row)
if int(s.n_trig):
    die("rally", "'a friendly unit' must not watch the opponent's plays")
ok("...and only the arming seat's own unit plays fire it")

# A unit already on the board when it resolves is untouched: the trigger
# watches PLAYS, and that one already happened.
s = fresh()
s.deck[:, :20] = MATE
early = s.add_permanent(MATE, 0, bf_loc(0))
h = chain.push(s, RALLY, 0)
chain.finalize(s, h)
chain.resolve_top(s, T, V1)
if s.perms[early, P_FLAGS] & F_BUFFED:
    die("rally", "a unit already on the board was never 'played this turn' "
                 "after the spell, so it must not be buffed")
ok("a unit already on the board is not buffed -- it watches plays, not bodies")


# ---------------------------------------------------------------------------
print("\n[18] the turn cannot end underneath an open Showdown")
# An [Action] spell may be played during the ENDING Phase, and Moonfall ("you
# may move up to one enemy unit to that battlefield") initiates a Combat when
# it resolves. A Combat is not a Chain Item and queues no trigger while it
# runs, so the two guards `_resume_phase` had could not see one: the Chain went
# empty, the turn resumed, and `end_turn` reached `compact_permanents` with the
# Showdown still open. Found by the real-deck fuzz on seed 90.
from rl.engine.state import ENDING as _ENDING

s = fresh()
s.phase = _ENDING
s.pend_phase = _ENDING            # the Ending Phase is suspended mid-step
mine = s.add_permanent(MATE, 0, bf_loc(0))
theirs = s.add_permanent(MATE, 1, bf_loc(0))
s.showdown_bf = 0                 # ...and a Combat opened while it was
s.attacker = 1
turn_before = int(s.turn)
A._settle(s, T, V1)
if int(s.turn) != turn_before:
    die("ending", "the turn ended while a Showdown was still open -- a Combat "
                  "is not on the Chain, so the Chain-empty guard cannot see it")
if int(s.pend_phase) != _ENDING:
    die("ending", "the suspension must survive until the Combat closes")
ok("a suspended Ending Phase waits for an open Showdown, not just the Chain")

# The other half: once the Combat closes, the same path finishes the turn.
s.showdown_bf = -1
s.attacker = -1
A._settle(s, T, V1)
if int(s.pend_phase) == _ENDING:
    die("ending", "with the Showdown closed the turn must finish; guarding on "
                  "it must not strand the suspension")
ok("...and finishes it as soon as the Showdown closes")


# ---------------------------------------------------------------------------
print("\n[19] Mindsplitter discards; Sabotage recycles (same op, two dests)")
# "When you play me, choose an opponent. They reveal their hand. Choose a card
# from it, and they discard that card."
#
# `OP_REVEAL_HAND` already existed for Sabotage, and it was SETTING
# `look_pick_dest` while `_finish_reveal` recycled unconditionally. Invisible
# while Sabotage was the only user -- it recycles -- and silently wrong here.
MINDSPLITTER = T.id_of("Mindsplitter")
SABOTAGE = T.id_of("Sabotage")


def _reveal(hand1):
    st = fresh()
    st.deck[:, :20] = MATE
    for j, c in enumerate(hand1):
        st.hand[1, j] = c
    st.n_hand[1] = len(hand1)
    return st


def _drain(st):
    for _ in range(8):
        if int(st.n_trig):
            chain.place(st, T, V1, 0)
        elif int(st.n_chain):
            chain.finalize(st, 0)
            chain.resolve_top(st, T, V1)
        else:
            break


s = _reveal([MATE, BACK_OFF])
row = s.add_permanent(MINDSPLITTER, 0, bf_loc(0))
chain.fire(s, T, V1, 0, row)              # TR_PLAY_ME
_drain(s)
if int(s.pend_reveal[0]) != 0 or int(s.pend_reveal[1]) != 1:
    die("mindsplitter", "the caster chooses out of the OPPONENT's hand")
picks = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK}
if picks != {0, 1}:
    die("mindsplitter", "'a card' has no type filter, so every card in the "
                        f"revealed hand is choosable; offered {sorted(picks)}")
deck_before = int(s.n_deck[1])
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if int(s.n_hand[1]) != 1:
    die("mindsplitter", "the chosen card must leave the hand")
if int(s.n_trash[1]) != 1:
    die("mindsplitter", "'they discard that card' puts it in the OWNER's "
                        "trash")
if int(s.n_deck[1]) != deck_before:
    die("mindsplitter", "a discard is not a recycle -- the deck must not grow")
ok("Mindsplitter discards the chosen card to its owner's trash")

# The other half, and the reason the destination has to be read: the same op
# on Sabotage must still recycle.
s = _reveal([MATE, BACK_OFF])
h = chain.push(s, SABOTAGE, 0)
chain.finalize(s, h)
chain.resolve_top(s, T, V1)
picks = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK}
if picks != {1}:
    die("sabotage", "Sabotage takes a NON-UNIT card, so only the spell is "
                    f"choosable; offered {sorted(picks)}")
deck_before, trash_before = int(s.n_deck[1]), int(s.n_trash[1])
A.apply(s, T, V1, A.Action(A.A_PICK, 1))
if int(s.n_trash[1]) != trash_before:
    die("sabotage", "Sabotage recycles; it must not trash")
if int(s.n_deck[1]) != deck_before + 1:
    die("sabotage", "416.1.c -- recycled to its OWNER's Main Deck")
ok("...and Sabotage still recycles, with its non-unit filter intact")


# ---------------------------------------------------------------------------
print("\n[20] Shuriken Flip: 'up to one', and a move that must actually move")
# "Deal 2 to up to one enemy unit at a battlefield, then move a friendly unit."
_SF = T.id_of("Shuriken Flip")


def _flip():
    st = fresh(hand0=(_SF,))
    st.runes_ready[:, :] = 4
    foe = st.add_permanent(MATE, 1, bf_loc(0))
    mine = st.add_permanent(MATE, 0, base_loc(0))
    return st, foe, mine


s, foe, mine = _flip()
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
_slot0 = {a.arg for a in A.legal_actions(s, T, V1, 0)}
if -1 not in _slot0:
    die("flip", "'up to one' must offer the skip (355.14)")
if foe not in _slot0:
    die("flip", "the enemy unit at a battlefield must be choosable")
A.apply(s, T, V1, A.Action(A.A_TARGET, foe))

# The destination slot is offered BEFORE the unit, and the enemy base is never
# a Move destination.
_dests = {a.arg for a in A.legal_actions(s, T, V1, 0)}
if base_loc(1) in _dests:
    die("flip", "movement is base<->battlefield to a unit's OWN base; the "
                "enemy base is never a destination")
# Own base is pruned here, and correctly: the only friendly unit is already
# there, so choosing it would leave the next slot with nothing legal. That is
# the coupled-slot lookahead, not a missing destination.
if base_loc(0) in _dests:
    die("flip", "choosing the base the only friendly unit already occupies "
                "would deadlock the next slot, so it must not be offered")
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(1)))
if {a.arg for a in A.legal_actions(s, T, V1, 0)} != {mine}:
    die("flip", "the friendly unit slot must exclude units already there")
A.apply(s, T, V1, A.Action(A.A_TARGET, mine))
for _ in range(6):
    _st = A.acting_seat(s)
    if _st < 0 or (not s.n_chain and not s.n_trig):
        break
    A.apply(s, T, V1, A.legal_actions(s, T, V1, _st)[0])
if int(s.perms[foe, P_DMG]) != 2:
    die("flip", "the damage half deals 2")
if int(s.perms[mine, P_LOC]) != bf_loc(1):
    die("flip", "the move half moves the chosen unit to the chosen location")
ok("both halves resolve, and the destination excludes the enemy base")

# Skipping the optional target fizzles ONLY the damage.
s, foe, mine = _flip()
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, -1))
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(1)))
A.apply(s, T, V1, A.Action(A.A_TARGET, mine))
for _ in range(6):
    _st = A.acting_seat(s)
    if _st < 0 or (not s.n_chain and not s.n_trig):
        break
    A.apply(s, T, V1, A.legal_actions(s, T, V1, _st)[0])
if int(s.perms[foe, P_DMG]):
    die("flip", "a skipped 'up to one' must deal no damage")
if int(s.perms[mine, P_LOC]) != bf_loc(1):
    die("flip", "...while the move, which is not optional, still happens")
ok("skipping 'up to one' fizzles the damage and leaves the move")

# 355.8 -- the move is required, so no friendly unit means no legal play.
s2 = fresh(hand0=(_SF,))
s2.runes_ready[:, :] = 4
s2.add_permanent(MATE, 1, bf_loc(0))
if [a for a in A.legal_actions(s2, T, V1, 0) if a.kind == A.A_PLAY]:
    die("flip", "355.8 -- a required target with no legal choice makes the "
                "card unplayable, rather than castable for half its text")
ok("...and with no friendly unit to move it cannot be played at all (355.8)")


# ---------------------------------------------------------------------------
print("\n[21] Acceptable Losses: the cull takes a TYPE, not always units")
# "Each player kills one of their gear." Cull the Weak's op with a type on it.
# That type was hardcoded to "Unit" in four separate places, and this is the
# card that differs.
_AL = T.id_of("Acceptable Losses")
_CW = T.id_of("Cull the Weak")
_GEAR = T.id_of("Treasure Trove")


def _cull(card, both=True):
    st = fresh()
    st.runes_ready[:, :] = 4
    rows = {"g0": st.add_permanent(_GEAR, 0, base_loc(0)),
            "u0": st.add_permanent(MATE, 0, bf_loc(0))}
    if both:
        rows["g1"] = st.add_permanent(_GEAR, 1, base_loc(1))
        rows["u1"] = st.add_permanent(MATE, 1, bf_loc(0))
    h = chain.push(st, card, 0)
    chain.finalize(st, h)
    chain.resolve_top(st, T, V1)
    return st, rows


s, r = _cull(_AL)
if {a.arg for a in A.legal_actions(s, T, V1, 0)} != {r["g0"]}:
    die("cull", "'one of their GEAR' must offer gear only, never units")
A.apply(s, T, V1, A.Action(A.A_TARGET, r["g0"]))
if {a.arg for a in A.legal_actions(s, T, V1, 1)} != {r["g1"]}:
    die("cull", "the second seat is asked the same question")
A.apply(s, T, V1, A.Action(A.A_TARGET, r["g1"]))
if s.perms[r["g0"], P_ALIVE] or s.perms[r["g1"], P_ALIVE]:
    die("cull", "both players' chosen gear dies")
if not s.perms[r["u0"], P_ALIVE] or not s.perms[r["u1"], P_ALIVE]:
    die("cull", "units are untouched by a gear cull")
ok("each player kills one of their GEAR, and units are untouched")

# The regression that matters: the op's default is still Unit.
s, r = _cull(_CW)
if {a.arg for a in A.legal_actions(s, T, V1, 0)} != {r["u0"]}:
    die("cull", "Cull the Weak still takes UNITS; the gear must not be "
                "offered to it")
ok("...and Cull the Weak still takes units, unchanged")

# A player with none of that type is skipped rather than asked -- an empty
# decision point would deadlock the turn.
s = fresh()
s.runes_ready[:, :] = 4
s.add_permanent(MATE, 0, bf_loc(0))            # seat 0: a unit, no gear
_g1 = s.add_permanent(_GEAR, 1, base_loc(1))
_h = chain.push(s, _AL, 0)
chain.finalize(s, _h)
chain.resolve_top(s, T, V1)
if int(s.pend_cull) != 1:
    die("cull", "a seat with no gear is skipped straight past, not asked")
ok("...and a player with no gear is skipped, never asked for nothing")


# ---------------------------------------------------------------------------
print("\n[22] Burn Out (431.2) actually happens, and [Burn N] can cause it")
# `burned_out` was set, exposed to the observation, and read by no rule: a
# player who emptied their deck simply stopped drawing, for free. Both
# consequences that make decking a cost were missing.
from rl.engine import phases as _ph2

_s = fresh()
_s.n_deck[0] = 0
_s.deck_ptr[0] = 0
_s.trash[0, :3] = [11, 12, 13]
_s.n_trash[0] = 3
_s.active = 0
_drawn = _ph2.draw(_s, 1)
if int(_s.n_trash[0]) != 0 or int(_s.n_deck[0]) - int(_s.deck_ptr[0]) != 2:
    die("burnout", "431.2.b -- the trash is recycled into the Main Deck")
if int(_s.points[1]) != 1:
    die("burnout", "431.2.c -- an opponent gains 1 point")
if not _drawn:
    die("burnout", "431.2.d -- the draw that caused it still completes")
ok("431.2 -- recycle the trash, pay a point, then finish the draw")

# 431.3.a -- with deck AND trash empty it repeats, one point per attempt.
_s2 = fresh()
_s2.n_deck[0] = 0
_s2.deck_ptr[0] = 0
_s2.n_trash[0] = 0
_s2.active = 0
_ph2.draw(_s2, 3)
if int(_s2.points[1]) != 3:
    die("burnout", "431.3.a -- burning out repeatedly pays a point each time; "
                   f"3 attempts gave {int(_s2.points[1])}")
ok("...and with nothing to recycle it repeats, a point per attempt (431.3.a)")

# [Burn N] is self-mill and takes the same path.
_s3 = fresh()
_s3.n_deck[0] = 5
_s3.deck[0, :5] = [21, 22, 23, 24, 25]
_s3.deck_ptr[0] = 0
_s3.n_trash[0] = 0
if _ph2.burn(_s3, 0, 2) != [21, 22]:
    die("burn", "[Burn 2] puts the TOP 2 of the Main Deck into the trash")
if int(_s3.n_trash[0]) != 2:
    die("burn", "...into the trash, not the banishment")
ok("[Burn N] mills the top N into its own controller's trash")

# Shadow Order Disciple: "you may [Burn 1] to give me +1 Might this turn."
_DISC = T.id_of("Shadow Order Disciple")
from rl.engine.effects import TR_MOVE as _TR_MOVE2


def _disciple(deck=5):
    st = fresh()
    st.n_deck[0] = deck
    if deck:
        st.deck[0, :deck] = list(range(31, 31 + deck))
    st.deck_ptr[0] = 0
    st.n_trash[0] = 0
    return st, st.add_permanent(_DISC, 0, bf_loc(0))


for _label, _take, _want_might, _want_trash in (("accept", True, 1, 1),
                                                ("decline", False, 0, 0)):
    _d, _r = _disciple()
    chain.fire(_d, T, V1, _TR_MOVE2, _r)
    A._advance_pending(_d, T, V1)
    A.apply(_d, T, V1, A.Action(A.A_ACCEPT if _take else A.A_DECLINE))
    for _ in range(6):
        _st = A.acting_seat(_d)
        if _st < 0 or (not _d.n_chain and not _d.n_trig):
            break
        A.apply(_d, T, V1, A.legal_actions(_d, T, V1, _st)[0])
    if combat.might(_d, T, _r) != int(T.might[_DISC]) + _want_might:
        die("disciple", f"{_label}: Might should move by {_want_might}")
    if int(_d.n_trash[0]) != _want_trash:
        die("disciple", f"{_label}: the burn is a COST, paid only on accept")
ok("the optional [Burn 1] cost is paid on accept and skipped on decline")

# The cost is always AFFORDABLE -- an empty deck makes paying it a Burn Out,
# which is a price, not a prohibition.
_d, _r = _disciple(deck=0)
chain.fire(_d, T, V1, _TR_MOVE2, _r)
A._advance_pending(_d, T, V1)
if A.A_ACCEPT not in {a.kind for a in A.legal_actions(_d, T, V1, 0)}:
    die("disciple", "an empty deck must not make the cost unofferable")
A.apply(_d, T, V1, A.Action(A.A_ACCEPT))
if int(_d.points[1]) != 1:
    die("disciple", "paying [Burn 1] off an empty deck is a Burn Out, and "
                    "431.2.c hands the opponent a point")
ok("...and paying it off an empty deck burns out, at a point's cost")


# ---------------------------------------------------------------------------
print("\n[23] Brittle Steel: a REQUIRED gear slot, and [Flow] out of the trash")
# "Kill a gear.  [Flow] {4 energy}{Fury rune}"
#
# Salvage's required sibling. The missing "you may" is the whole difference:
# 355.8 refuses the play outright with no gear on the board, and that bites
# twice, because [Flow] gives the card a second life from the trash (829.1.b)
# and a replay has to fill its own slot too.
_BS = T.id_of("Brittle Steel")
_GEAR = next(c for c in range(T.n)
             if T.is_type(c, "Gear") and not T.is_type(c, "Unit")
             and not T.is_token(c))

s = fresh(hand0=(_BS,))
# 355.8 -- no gear anywhere, so the card cannot be played at all.
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY]:
    die("brittle steel", "355.8 -- with no gear on the board the play must be "
                         "refused, not offered and then fizzled")
ok("with no gear anywhere, 355.8 refuses the play outright")

# An ENEMY gear is a legal choice: the slot says "a gear", unqualified, and
# targets scope by omission.
s = fresh(hand0=(_BS,))
mine = s.add_permanent(_GEAR, 0, base_loc(0), is_unit=False)
theirs = s.add_permanent(_GEAR, 1, base_loc(1), is_unit=False)
play = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY)
A.apply(s, T, V1, play)
opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
if opts != {mine, theirs}:
    die("brittle steel", f"'a gear' reaches both players' gear, got {opts}")
ok("...and 'a gear' unqualified reaches either player's")

A.apply(s, T, V1, A.Action(A.A_TARGET, theirs))
for _ in range(6):
    if not s.n_chain:
        break
    A.apply(s, T, V1, A.PASS)
if s.perms[theirs, P_ALIVE] or not s.perms[mine, P_ALIVE]:
    die("brittle steel", "it kills the gear it chose and nothing else")
# 829.1.b -- and it is now in the trash with a Flow cost, so it can come back.
if _BS not in [int(s.trash[0, i]) for i in range(int(s.n_trash[0]))]:
    die("brittle steel", "a resolved spell belongs in its owner's trash")
ok("...and the chosen gear dies, leaving the spell in the trash for [Flow]")

# The replay has to fill its own slot. The board still has `mine`, so it can.
flow = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]
if not flow:
    die("brittle steel", "829.1.b -- with a gear still standing and the runes "
                         "to pay, the Flow replay must be offered")
ok("...and [Flow] offers it back out of the trash while a gear remains")

# Kill the last gear and the Flow play has to go away with it -- 355.8 again,
# one zone further out.
s.perms[mine, P_ALIVE] = 0
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]:
    die("brittle steel", "a Flow replay must fill its own slot too, or it "
                         "deadlocks on an empty board")
ok("...and with the board cleared of gear the replay is refused too")


# ---------------------------------------------------------------------------
print("\n[24] Arise!: counting Equipment, attached or not")
# "Play a 2 Might Sand Soldier unit token for each Equipment you control.
#  Then ready two of them."
#
# The first card to count Equipment, and it needs none of the Might Bonus data
# that `cards.json` is missing -- which is exactly why it is scriptable while
# Long Sword is not.
_ARISE = T.id_of("Arise!")
_SOLDIER = T.id_of("Sand Soldier")
_CAPE2 = T.id_of("Forgefire Cape")


def _soldiers(st):
    return [i for i in range(st.n_perms)
            if int(st.perms[i, P_CARD]) == _SOLDIER and st.perms[i, P_ALIVE]]


def _cast_arise(st):
    A.apply(st, T, V1, next(a for a in A.legal_actions(st, T, V1, 0)
                            if a.kind == A.A_PLAY
                            and int(st.hand[0, a.arg]) == _ARISE))
    # "Play a Sand Soldier" names no location: base or a battlefield you control.
    A.apply(st, T, V1, next(a for a in A.legal_actions(st, T, V1, 0)
                            if a.kind == A.A_TARGET and a.arg == base_loc(0)))
    for _ in range(8):
        if not st.n_chain and not st.n_trig:
            break
        A.apply(st, T, V1, A.PASS)


# No Equipment: `n` is a RATE, so an empty board plays no tokens rather than
# the one a flat count would give.
s = fresh(hand0=(_ARISE,))
_cast_arise(s)
if _soldiers(s):
    die("arise", "'for each Equipment you control' with none must play none")
ok("with no Equipment it plays nothing -- the count is a rate, not a floor")

# Three Equipment, one of them ATTACHED and one of them the OPPONENT's.
# 718.5.a keeps an Attached card's Tags, so the equipped one still counts;
# 718.5.e/f make control of an Attached card independent of its unit's, so the
# question is asked of the Equipment itself.
s = fresh(hand0=(_ARISE,))
loose = s.add_permanent(_CAPE2, 0, base_loc(0), is_unit=False)
worn = s.add_permanent(_CAPE2, 0, base_loc(0), is_unit=False)
theirs = s.add_permanent(_CAPE2, 1, base_loc(1), is_unit=False)
unit_ = s.add_permanent(unit(2), 0, base_loc(0))
s.attach(worn, unit_)
_cast_arise(s)
made = _soldiers(s)
if len(made) != 2:
    die("arise", f"two Equipment you control -> two Soldiers, got {len(made)} "
                 "(an attached one still counts, the opponent's does not)")
ok("...and an ATTACHED Equipment still counts, while the opponent's does not")

# "Then ready two of them" -- and 359.2.c says units arrive exhausted, so this
# is the clause doing the work. Which two is not a decision: the tokens are
# identical, so offering the choice would put a solved problem in the action
# space.
if sum(int(s.perms[i, P_READY]) for i in made) != 2:
    die("arise", "'then ready two of them' -- exactly two, over 359.2.c's "
                 "default of arriving exhausted")
ok("...and exactly two of them are readied, against 359.2.c's default")

# Four Equipment: four bodies, still only two ready.
s = fresh(hand0=(_ARISE,))
for _ in range(4):
    s.add_permanent(_CAPE2, 0, base_loc(0), is_unit=False)
_cast_arise(s)
made = _soldiers(s)
if len(made) != 4 or sum(int(s.perms[i, P_READY]) for i in made) != 2:
    die("arise", f"four Equipment -> four Soldiers, two ready; got "
                 f"{len(made)} and {sum(int(s.perms[i, P_READY]) for i in made)}")
ok("...and the readied count stays at two however many bodies arrive")


# ---------------------------------------------------------------------------
print("\n[25] Wind and Ghosts: a partition on effective Might")
# "Choose a unit at a battlefield. If it has 3 Might or less, banish it.
#  Otherwise, return it to its owner's hand."
#
# Two ops on complementary conditions, so exactly one runs. 427.2.a makes the
# halves genuinely different answers: a banish leaves no card to recur from,
# a bounce hands it straight back.
_WAG = T.id_of("Wind and Ghosts")
_SMALL = next(c for c in range(T.n)
              if T.is_type(c, "Unit") and not T.is_token(c)
              and int(T.might[c]) <= 3 and not T.residual_text(c))
_BIG = next(c for c in range(T.n)
            if T.is_type(c, "Unit") and not T.is_token(c)
            and int(T.might[c]) >= 5 and not T.residual_text(c))


def _cast_wag(st, victim):
    A.apply(st, T, V1, next(a for a in A.legal_actions(st, T, V1, 0)
                            if a.kind == A.A_PLAY
                            and int(st.hand[0, a.arg]) == _WAG))
    A.apply(st, T, V1, A.Action(A.A_TARGET, victim))
    for _ in range(8):
        if not st.n_chain:
            break
        A.apply(st, T, V1, A.PASS)


# At or below the line: banished. 427.2.a -- no trash, so nothing to recur.
s = fresh(hand0=(_WAG,))
v = s.add_permanent(_SMALL, 1, bf_loc(0))
_trash, _hand = int(s.n_trash[1]), int(s.n_hand[1])
_cast_wag(s, v)
if s.perms[v, P_ALIVE]:
    die("wind and ghosts", "3 Might or less is banished")
if int(s.n_trash[1]) != _trash:
    die("wind and ghosts", "427.2.a -- a banish is not a kill, so the card "
                           "must NOT reach a trash")
if int(s.n_hand[1]) != _hand:
    die("wind and ghosts", "...nor a hand: exactly one half of the sentence runs")
ok("at or below 3 Might it is banished, reaching neither trash nor hand")

# Above the line: bounced to its OWNER's hand, not the caster's.
s = fresh(hand0=(_WAG,))
v = s.add_permanent(_BIG, 1, bf_loc(0))
_mine = int(s.n_hand[0])
_cast_wag(s, v)
if s.perms[v, P_ALIVE]:
    die("wind and ghosts", "the unit leaves the board either way")
if int(s.n_hand[1]) != 1:
    die("wind and ghosts", "above 3 Might it returns to its OWNER's hand")
if int(s.n_hand[0]) != _mine - 1:
    die("wind and ghosts", "...and not to the caster's -- their hand only "
                           "loses the spell they played")
ok("...and above it, back to its owner's hand and not the caster's")

# **Effective Might, not the printed corner.** A pump in the response window
# flips which half happens -- the counterplay the card offers.
s = fresh(hand0=(_WAG,))
v = s.add_permanent(_SMALL, 1, bf_loc(0))
from rl.engine.state import P_MIGHT_MOD as _P_MM
s.perms[v, _P_MM] = 3            # pumped over the line before it resolves
_trash = int(s.n_trash[1])
_cast_wag(s, v)
if int(s.n_hand[1]) != 1:
    die("wind and ghosts", "a pumped target reads as over the line and is "
                           "BOUNCED -- effective Might, not the printed corner")
if int(s.n_trash[1]) != _trash:
    die("wind and ghosts", "...and is certainly not both")
ok("...and a pump in the response window turns the banish into a bounce")


# ---------------------------------------------------------------------------
print("\n[26] 108.6 -- a banished card is IN Banishment, not nowhere")
# `combat.banish` cleared P_ALIVE and stored the card nowhere. That was
# invisible while OP_BLINK was its only caller -- blink banishes and replays in
# the same breath, so the card came straight back and nothing noticed it had
# been in no zone at all. The first real banish (Wind and Ghosts) made cards
# evaporate, and the per-seat conservation gate caught it in BOTH the spell and
# deck fuzzes.
from rl.tests.fuzz import cards_owned as _owned2

s = fresh(hand0=(_WAG,))
v = s.add_permanent(_SMALL, 1, bf_loc(0))
_before = [_owned2(s, T, k) for k in range(2)]
_ban = int(s.n_banished[1])
_cast_wag(s, v)
if int(s.n_banished[1]) != _ban + 1:
    die("banish", "108.6 -- the card goes to its OWNER's Banishment")
if int(s.banished[1, _ban]) != _SMALL:
    die("banish", "...and it is the card that was banished")
if [_owned2(s, T, k) for k in range(2)] != _before:
    die("banish", f"cards are conserved across a banish: {_before} -> "
                  f"{[_owned2(s, T, k) for k in range(2)]}")
ok("a banished card lands in its owner's Banishment, and is conserved")

# A TOKEN is the exception: 186 has it cease to exist off the board, so there
# is nothing to store -- the same carve-out the trash makes.
s2 = fresh(hand0=(_WAG,))
tok = next(c for c in range(T.n)
           if T.is_type(c, "Unit") and T.token[c] and int(T.might[c]) <= 3)
tv = s2.add_permanent(tok, 1, bf_loc(0))
_ban2 = int(s2.n_banished[1])
_cast_wag(s2, tv)
if s2.perms[tv, P_ALIVE]:
    die("banish", "the token is removed")
if int(s2.n_banished[1]) != _ban2:
    die("banish", "186 -- a token in a non-board zone ceases to exist, so "
                  "banishing one stores nothing")
ok("...while a token ceases to exist instead (186)")


# ---------------------------------------------------------------------------
print("\n[27] Challenge, Invert Timelines, Turn to Dust")
_P2 = unit(2)
_CHAL = T.id_of("Challenge")
_INVT = T.id_of("Invert Timelines")
_TTD = T.id_of("Turn to Dust")


def _cast(st, card, *targets):
    A.apply(st, T, V1, next(a for a in A.legal_actions(st, T, V1, 0)
                            if a.kind == A.A_PLAY and int(st.hand[0, a.arg]) == card))
    for t in targets:
        A.apply(st, T, V1, A.Action(A.A_TARGET, t))
    for _ in range(10):
        if not st.n_chain:
            break
        A.apply(st, T, V1, A.PASS)


# Challenge -- an EVEN trade kills both. Sequential damage would let whichever
# op ran first survive, because the second would read Might off a corpse.
_even = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
             and int(T.might[c]) == 3 and not T.residual_text(c)
             and not T.has(c, "Shield") and not T.has(c, "Tank"))
s = fresh(hand0=(_CHAL,))
m = s.add_permanent(_even, 0, bf_loc(0))
e = s.add_permanent(_even, 1, bf_loc(0))
_cast(s, _CHAL, m, e)
if s.perms[m, P_ALIVE] or s.perms[e, P_ALIVE]:
    die("challenge", "3 Might into 3 Might is simultaneous -- BOTH die")
ok("Challenge is simultaneous: an even trade kills both units")

# ...and an uneven one kills only the smaller.
_big = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
            and int(T.might[c]) >= 5 and not T.residual_text(c))
s = fresh(hand0=(_CHAL,))
m = s.add_permanent(_big, 0, bf_loc(0))
e = s.add_permanent(_even, 1, bf_loc(0))
_cast(s, _CHAL, m, e)
if not s.perms[m, P_ALIVE] or s.perms[e, P_ALIVE]:
    die("challenge", "the bigger unit survives and the smaller dies")
if int(s.perms[m, P_DMG]) != 3:
    die("challenge", "...having taken damage equal to the smaller one's Might")
ok("...and an uneven one kills the smaller, marking damage on the bigger")

# Invert Timelines -- EACH player, not just the caster.
s = fresh(hand0=(_INVT, _P2, _P2))
s.hand[1, :5] = _P2
s.n_hand[1] = 5
_cast(s, _INVT)
if int(s.n_hand[0]) != 4 or int(s.n_hand[1]) != 4:
    die("invert timelines", f"each player ends on 4 cards, got "
                            f"{int(s.n_hand[0])} and {int(s.n_hand[1])}")
if int(s.n_trash[1]) < 5:
    die("invert timelines", "the opponent discarded their whole hand too")
ok("Invert Timelines empties BOTH hands and refills each to 4")

# Turn to Dust -- the grant is permanent, so the gear dies next Beginning.
_GEAR2 = T.id_of("Treasure Trove")
s = fresh(hand0=(_TTD,))
g = s.add_permanent(_GEAR2, 1, base_loc(1), is_unit=False)
_cast(s, _TTD, g)
if not combat.perm_kw(s, T, g, "Temporary"):
    die("turn to dust", "the gear is given [Temporary]")
phases.end_turn(s, V1)
if not combat.perm_kw(s, T, g, "Temporary"):
    die("turn to dust", "a 'this turn' grant would expire before [Temporary] "
                        "could ever fire; this one must survive the turn")
s.active = 1
phases.expire_temporary(s, T)
if s.perms[g, P_ALIVE]:
    die("turn to dust", "at its controller's Beginning Phase it is killed")
ok("Turn to Dust's [Temporary] survives the turn and kills the gear on schedule")


# ---------------------------------------------------------------------------
print("\n[28] Ocean Drake and Hand Hammer")
_DRAKE = T.id_of("Ocean Drake")
_HAMMER = T.id_of("Hand Hammer")

from rl.engine import resolve as _rsvD
from rl.engine.effects import ABILITIES as _ABD
_spec = _ABD["Ocean Drake"][0]
s = fresh()
d = s.add_permanent(_DRAKE, 0, bf_loc(0))
other_dragon = s.add_permanent(_DRAKE, 1, bf_loc(1))
foe = s.add_permanent(_P2, 1, bf_loc(1))
mine = s.add_permanent(_P2, 0, base_loc(0))
opts = set(_rsvD.legal_targets(s, T, _spec, 0, 0, [], -1, source=d))
if other_dragon in opts or d in opts:
    die("ocean drake", "'a NON-Dragon unit' -- no Dragon is a legal choice")
if foe not in opts or mine not in opts:
    die("ocean drake", "'a unit' is unqualified, so either player's non-Dragon")
ok("Ocean Drake bounces any non-Dragon unit, and no Dragon")

# Hand Hammer -- EXACTLY one other friendly unit, at a battlefield.
s = fresh()
u = s.add_permanent(_P2, 0, bf_loc(0))
h = s.add_permanent(_HAMMER, 0, bf_loc(0), is_unit=False)
s.attach(h, u)
_base = int(T.might[_P2]) + int(T.might_bonus[_HAMMER])
if combat.might(s, T, u) != _base:
    die("hand hammer", "alone, only the flat Might Bonus applies")
s.add_permanent(_P2, 0, bf_loc(0))
if combat.might(s, T, u) != _base + 2:
    die("hand hammer", "with exactly one other friendly unit here: +2")
s.add_permanent(_P2, 0, bf_loc(0))
if combat.might(s, T, u) != _base:
    die("hand hammer", "EXACTLY one -- a second ally switches it off")
ok("Hand Hammer's +2 needs exactly one other friendly unit at the battlefield")


# ---------------------------------------------------------------------------
print("\n[29] Blood Money: the payout depends on whose unit died")
_BM = T.id_of("Blood Money")
_GOLD = T.id_of("Gold // Buff")
_TWO = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
            and int(T.might[c]) == 2 and not T.residual_text(c))


def _golds(st):
    return sum(1 for i in range(st.n_perms)
               if st.perms[i, P_ALIVE] and int(st.perms[i, P_CARD]) == _GOLD)


for side, want in ((1, 1), (0, 2)):
    s = fresh(hand0=(_BM,))
    v = s.add_permanent(_TWO, side, bf_loc(0))
    _cast(s, _BM, v)
    if s.perms[v, P_ALIVE]:
        die("blood money", "the unit is killed")
    if _golds(s) != want:
        die("blood money", f"{'enemy' if side else 'friendly'} victim -> {want} "
                           f"Gold, got {_golds(s)} (exactly one branch runs)")
ok("an enemy victim pays one Gold and a friendly one pays two -- never three")

# 355.9.b -- "with 2 Might or less" is effective Might, so a 3 is not a target.
s = fresh(hand0=(_BM,))
big = s.add_permanent(_TWO, 1, bf_loc(0))
from rl.engine.state import P_MIGHT_MOD as _PMM2
s.perms[big, _PMM2] = 1
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY]:
    die("blood money", "a pumped 3-Might unit is out of range, so 355.8 "
                       "refuses the play with nothing else to target")
ok("...and a unit pumped past 2 Might is out of range")


# ---------------------------------------------------------------------------
print("\n[30] Abandon: a counter that sends the spell home, not to the trash")
_ABAN = T.id_of("Abandon")
_STUP = T.id_of("Stupefy")

s = fresh(hand0=(_ABAN,), hand1=(_STUP,))
foe_unit = s.add_permanent(unit(2), 0, bf_loc(0))
s.active, s.priority = 1, 1
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 1)
                       if a.kind == A.A_PLAY and int(s.hand[1, a.arg]) == _STUP))
for _ in range(4):
    if s.pend_slot < 0:
        break
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 1)
                           if a.kind == A.A_TARGET))
# Seat 0 answers with Abandon.
A.apply(s, T, V1, A.PASS)
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == _ABAN))
stup_uid = next(a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET)
A.apply(s, T, V1, A.Action(A.A_TARGET, stup_uid))
_hand1, _trash1 = int(s.n_hand[1]), int(s.n_trash[1])
for _ in range(12):
    if s.pend_look >= 0 or not s.n_chain:
        break
    _st = A.acting_seat(s)
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, _st)
                           if a.kind == A.A_PASS))
if int(s.n_hand[1]) != _hand1 + 1:
    die("abandon", "the countered spell returns to its owner's HAND")
if int(s.n_trash[1]) != _trash1:
    die("abandon", "...INSTEAD of their trash")
if s.pend_look < 0:
    die("abandon", "then [Predict] opens its look")
ok("Abandon returns the countered spell to hand instead of the trash, then Predicts")


# ---------------------------------------------------------------------------
print("\n[31] On the Hunt, Detonate, Downwell")
_HUNT = T.id_of("On the Hunt")
_DET = T.id_of("Detonate")
_DOWN = T.id_of("Downwell")

s = fresh(hand0=(_HUNT,))
u1 = s.add_permanent(unit(2), 0, base_loc(0)); s.perms[u1, P_READY] = 0
u2 = s.add_permanent(unit(2), 1, base_loc(1)); s.perms[u2, P_READY] = 0
_cast(s, _HUNT)
if not int(s.perms[u1, P_READY]) or int(s.perms[u2, P_READY]):
    die("on the hunt", "'Ready YOUR units' -- mine ready, the opponent's do not")
ok("On the Hunt readies your units and not the opponent's")

s = fresh(hand0=(_DET,))
# Not Treasure Trove: it draws when it LEAVES the board, which would make the
# count +3 and test the wrong card. Iron Ballista has no leave trigger.
g = s.add_permanent(T.id_of("Iron Ballista"), 1, base_loc(1), is_unit=False)
_h1 = int(s.n_hand[1])
_cast(s, _DET, g)
if s.perms[g, P_ALIVE] or int(s.n_hand[1]) != _h1 + 2:
    die("detonate", "the gear dies and ITS CONTROLLER draws 2")
ok("Detonate kills the gear and its controller draws 2")

from rl.tests.fuzz import cards_owned as _own4
s = fresh(hand0=(_DOWN,))
a0 = s.add_permanent(unit(2), 0, base_loc(0))
b1 = s.add_permanent(unit(2), 1, bf_loc(0))
tk = s.add_permanent(T.id_of("Sand Soldier"), 0, base_loc(0))
dug = s.add_permanent(unit(3), 0, bf_loc(1), owner=1)     # mine to play, theirs to own
_before = [_own4(s, T, k) for k in range(2)]
_cast(s, _DOWN)
if any(s.perms[i, P_ALIVE] for i in (a0, b1, tk, dug)):
    die("downwell", "every unit and gear leaves the board")
if [_own4(s, T, k) for k in range(2)] != _before:
    die("downwell", "cards are conserved per owner -- a token just ceases")
if unit(3) not in [int(x) for x in s.hand[1, :int(s.n_hand[1])]]:
    die("downwell", "a card goes to its OWNER's hand, not its controller's")
ok("Downwell returns everything to its OWNER's hand, and tokens simply cease")


# ---------------------------------------------------------------------------
print("\n[32] Disintegrate and Decree of Rage")
_DIS = T.id_of("Disintegrate")
for m, want in ((2, 1), (8, 0)):
    s = fresh(hand0=(_DIS,))
    v = s.add_permanent(unit(m), 1, bf_loc(0))
    _h = int(s.n_hand[0])
    _cast(s, _DIS, v)
    if int(s.n_hand[0]) - (_h - 1) != want:
        die("disintegrate", f"'if this kills it, draw 1' -- {m}-Might target "
                            f"should draw {want}")
ok("Disintegrate draws only when its 3 damage kills")

# Decree of Rage may still be CHOSEN by a counter (RiftJudge #11722): the
# counter simply fails as it resolves, and Decree stays on the Chain.
_DEC = T.id_of("Decree of Rage")
_LUL = T.id_of("Lilting Lullaby")
s = fresh(hand0=(_LUL,))
calm = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
            and int(T.domain_mask[c]) >> 1 & 1 and not T.residual_text(c))
tgt = s.add_permanent(calm, 0, bf_loc(0))
it = chain.push(s, _DEC, 1)
chain.set_target(s, it, 0, tgt)
chain.finalize(s, it)
s.active, s.priority = 1, 0
if not chain.playable_hand_indices(s, T, V1, 0):
    die("decree of rage", "'can't be countered' is not untargetable")
from rl.engine.state import C_UID as _CU32
chain.counter(s, T, int(s.chain[it, _CU32]))
if chain.index_of_uid(s, int(s.chain[it, _CU32])) < 0:
    die("decree of rage", "'This can't be countered' -- the counter must fail")
ok("Decree of Rage can be chosen by a counter, but the counter fails")


print("\n\033[32mall spell tests passed\033[0m")
