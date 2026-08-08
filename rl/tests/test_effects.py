"""Effect DSL tests -- the targeting rules, which are where the subtlety is.

Run: python3 rl/tests/test_effects.py

The rules this checks are the ones the project owner supplied from the FAQ, and
each one is a case where a plausible implementation is wrong:

  [1] Slot restrictions -- friendly/enemy, and "at a battlefield".
  [2] Relations between slots -- Facebreaker's "at the same battlefield" and
      Smoke and Mirrors' "at a different location", including that "another
      unit" can never be the same unit.
  [3] Locality binds per SLOT, not per card (811.1.d.2.a), and only for cards
      played from a Facedown Zone.
  [4] Resolution re-checks targets; a dead target fizzles its op, and losing
      every target counters the whole card (359.3.e.5/e.6).
  [5] Conditions are not restrictions -- they fail at resolution rather than
      narrowing the legal choices.
"""
import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.config import Config
from rl.engine import resolve
from rl.engine.cardtable import full_table
from rl.engine import phases
from rl.engine.effects import (LOC_BOUND, LOC_FREE, OP_DRAW, OP_STUN,
                               OP_SWAP_LOC, SPECS, spec_for)
from rl.engine.state import (P_ALIVE, P_CARD, P_LOC, GameState, base_loc,
                             bf_loc)

T = full_table()
CFG = Config()


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def unit(might, kw=None, exclude=("Tank", "Backline")):
    for c in range(T.n):
        if not T.is_type(c, "Unit") or T.might[c] != might:
            continue
        if kw and not T.has(c, kw):
            continue
        if any(T.has(c, k) for k in exclude):
            continue
        return c
    raise LookupError(f"no unit might={might} kw={kw}")


PLAIN = {m: unit(m) for m in (2, 3, 5)}

def temporary_unit():
    """Any non-token unit with [Temporary]; its Might is incidental here.

    This asked for `might=2` and found one only because `keyword_mask` used to
    credit a card with every keyword its text MENTIONED. With attribution
    fixed, the pool holds exactly two [Temporary] units and neither is a 2.
    """
    for c in range(T.n):
        if T.is_type(c, "Unit") and T.has(c, "Temporary") and not T.is_token(c):
            return c
    raise LookupError("no non-token [Temporary] unit in the pool")


TEMP = temporary_unit()


def fresh():
    s = GameState()
    s.n_deck[:] = 10
    s.deck[:, :10] = PLAIN[2]
    return s


BACK_OFF = SPECS["Back Off"]
FACEBREAKER = SPECS["Facebreaker"]
SMOKE = SPECS["Smoke and Mirrors"]

# ---------------------------------------------------------------------------
print("\n[1] slot restrictions: who, and where")
s = fresh()
mine_base = s.add_permanent(PLAIN[2], 0, base_loc(0))
mine_bf = s.add_permanent(PLAIN[3], 0, bf_loc(0))
theirs_bf = s.add_permanent(PLAIN[2], 1, bf_loc(0))

got = resolve.legal_targets(s, T, BACK_OFF, 0, 0, [], -1)
assert sorted(got) == [mine_base, mine_bf, theirs_bf], got
ok("Back Off targets any unit anywhere (no restriction printed)")

# Facebreaker slot 0 is friendly AND at a battlefield -- base units excluded.
got = resolve.legal_targets(s, T, FACEBREAKER, 0, 0, [], -1)
if got != [mine_bf]:
    die("slots", f"friendly-at-battlefield gave {got}, expected [{mine_bf}]")
ok("Facebreaker's friendly slot excludes units at base")

got = resolve.legal_targets(s, T, FACEBREAKER, 1, 0, [mine_bf], -1)
if got != [theirs_bf]:
    die("slots", f"enemy slot gave {got}")
ok("Facebreaker's enemy slot excludes your own units")


# ---------------------------------------------------------------------------
print("\n[2] relations between slots")
s = fresh()
a0 = s.add_permanent(PLAIN[2], 0, bf_loc(0))
e0 = s.add_permanent(PLAIN[2], 1, bf_loc(0))
e1 = s.add_permanent(PLAIN[3], 1, bf_loc(1))

got = resolve.legal_targets(s, T, FACEBREAKER, 1, 0, [a0], -1)
if got != [e0]:
    die("relations", f"same-battlefield gave {got}, expected [{e0}] "
                     f"({e1} is at the other battlefield)")
ok("'at the same battlefield' excludes the enemy at the other battlefield")

s = fresh()
u0 = s.add_permanent(PLAIN[2], 0, bf_loc(0))
u1 = s.add_permanent(PLAIN[2], 0, bf_loc(0))     # same location as u0
u2 = s.add_permanent(PLAIN[3], 0, base_loc(0))   # different location
got = resolve.legal_targets(s, T, SMOKE, 1, 0, [u0], -1)
if got != [u2]:
    die("relations", f"different-location gave {got}, expected [{u2}]")
if u0 in got:
    die("relations", "'another unit you control' matched the same unit")
ok("'at a different location' excludes co-located units and the unit itself")


# ---------------------------------------------------------------------------
print("\n[3] locality binds per slot, and only from hiding")
s = fresh()
here = s.add_permanent(PLAIN[2], 1, bf_loc(0))
there = s.add_permanent(PLAIN[3], 1, bf_loc(1))
home = s.add_permanent(PLAIN[2], 0, base_loc(0))

# From hand (bound_bf = -1): no locality at all.
got = resolve.legal_targets(s, T, BACK_OFF, 0, 0, [], -1)
assert sorted(got) == sorted([here, there, home]), got
ok("played from hand, a bound slot reaches the whole board")

# Hidden at battlefield 0: Back Off's slot is LOC_BOUND, so only battlefield 0.
got = resolve.legal_targets(s, T, BACK_OFF, 0, 0, [], 0)
if got != [here]:
    die("locality", f"hidden at B1 reached {got}, expected [{here}]")
ok("played from hiding, a bound slot reaches only that battlefield (811.1.d.2.a)")

# Smoke and Mirrors' slots are LOC_FREE: it chooses rather than targets
# (355.10.a), so hiding location does not restrict it. This is the case that
# corrected an earlier per-card reading of the rule.
s2 = fresh()
f0 = s2.add_permanent(TEMP, 0, bf_loc(1))
f1 = s2.add_permanent(PLAIN[3], 0, base_loc(0))
got = resolve.legal_targets(s2, T, SMOKE, 0, 0, [], 0)   # hidden at B0
if sorted(got) != sorted([f0, f1]):
    die("locality", f"a free slot was restricted by hiding location: {got}")
ok("a free slot is unrestricted from hiding, even at another battlefield")

assert BACK_OFF.targets[0].locality == LOC_BOUND
assert all(t.locality == LOC_FREE for t in SMOKE.targets)
ok("locality is stored per slot, so one card can mix bound and free")


# ---------------------------------------------------------------------------
print("\n[4] resolution re-checks targets")
s = fresh()
victim = s.add_permanent(PLAIN[3], 1, bf_loc(0))
log = resolve.resolve(s, T, CFG, BACK_OFF, 0, [victim], -1, from_hand=True)
assert log["stunned"] == [victim], log
assert OP_DRAW in log["resolved"], f"from-hand rider should have drawn: {log}"
ok("Back Off from hand stuns and draws")

# Same card, but the target died between finalization and resolution.
s = fresh()
victim = s.add_permanent(PLAIN[3], 1, bf_loc(0))
s.perms[victim, P_ALIVE] = 0
log = resolve.resolve(s, T, CFG, BACK_OFF, 0, [victim], -1, from_hand=True)
if not log.get("countered"):
    die("resolution", f"every target illegal must counter the card: {log}")
ok("losing every target counters the whole card (359.3.e.5/e.6)")

# Played from hiding: the rider is conditional on having played it from hand.
s = fresh()
victim = s.add_permanent(PLAIN[3], 1, bf_loc(0))
log = resolve.resolve(s, T, CFG, BACK_OFF, 0, [victim], 0, from_hand=False)
assert log["stunned"] == [victim], log
if OP_DRAW in log["resolved"]:
    die("resolution", "drew a card despite not being played from hand")
ok("played from hiding, Back Off stuns but does not draw")


# ---------------------------------------------------------------------------
print("\n[5] conditions fail at resolution, they do not restrict choice")
s = fresh()
plain0 = s.add_permanent(PLAIN[2], 0, bf_loc(0))
plain1 = s.add_permanent(PLAIN[3], 0, base_loc(0))
# Neither has [Temporary], so the swap condition fails -- but both were legal
# choices, which is the whole distinction (355.9.b).
got = resolve.legal_targets(s, T, SMOKE, 1, 0, [plain0], -1)
assert plain1 in got, "the condition must not narrow the legal choices"
log = resolve.resolve(s, T, CFG, SMOKE, 0, [plain0, plain1], -1, from_hand=True)
if "swapped" in log:
    die("conditions", "swapped without a [Temporary] unit involved")
if OP_SWAP_LOC not in log["fizzled"]:
    die("conditions", f"the swap should have fizzled: {log}")
assert OP_DRAW in log["resolved"], "the unconditional draw still happens"
ok("no [Temporary] unit: the swap fizzles, the draw still resolves")

s = fresh()
temp = s.add_permanent(TEMP, 0, bf_loc(0))
other = s.add_permanent(PLAIN[3], 0, base_loc(0))
log = resolve.resolve(s, T, CFG, SMOKE, 0, [temp, other], -1, from_hand=True)
if log.get("swapped") != (temp, other):
    die("conditions", f"expected a swap: {log}")
if int(s.perms[temp, P_LOC]) != base_loc(0) or int(s.perms[other, P_LOC]) != bf_loc(0):
    die("conditions", "units did not actually change places")
ok("with a [Temporary] unit: the two units trade locations")


# ---------------------------------------------------------------------------
print("\n[6] Might modification is not damage (142.4.b, 143.2.a/b)")
from rl.engine import combat
from rl.engine.state import P_DMG, P_MIGHT_MOD
from rl.engine.effects import SPECS as _S

STUPEFY, DISCIPLINE, SMOKE_SCREEN = _S["Stupefy"], _S["Discipline"], _S["Smoke Screen"]

# A unit reduced to 0 Might does NOT die. The project owner's point, and
# 142.4.b: lethal damage is a NON-ZERO amount >= Might.
s = fresh()
u = s.add_permanent(PLAIN[3], 1, bf_loc(0))
combat.set_might_mod(s, T, u, -3)          # no floor: straight to 0
if combat.might(s, T, u) != 0:
    die("might", f"expected 0 Might, got {combat.might(s,T,u)}")
if s.perms[u, P_ALIVE] != 1:
    die("might", "a unit at 0 Might must NOT die -- lethal damage is non-zero")
ok("a unit reduced to 0 Might survives (142.4.b)")

# 143.2.b -- Might below 0 is treated as 0, never negative, in the damage pool.
combat.set_might_mod(s, T, u, -5)
if combat.might(s, T, u) != 0 or combat.might_for_pool(s, T, u) != 0:
    die("might", "Might below 0 must be treated as 0 (143.2.b)")
ok("Might below zero floors at 0 for references and for the damage pool")

# The rulebook's own Frigid Touch example: 5 Might, 3 damage marked, drop to
# 3 Might -> lethal. Reduction kills, but only via damage already present.
s = fresh()
v = s.add_permanent(PLAIN[5], 1, bf_loc(0))
s.perms[v, P_DMG] = 3
killed = combat.set_might_mod(s, T, v, -2)
if not killed or s.perms[v, P_ALIVE] == 1:
    die("might", "5 Might with 3 damage, reduced to 3 Might, must die (143.2.a)")
ok("reduction to meet damage already marked DOES kill (the Frigid Touch case)")

# ...but the same reduction with no damage marked does not.
s = fresh()
v = s.add_permanent(PLAIN[5], 1, bf_loc(0))
if combat.set_might_mod(s, T, v, -2) or s.perms[v, P_ALIVE] != 1:
    die("might", "reduction with no damage marked must never kill")
ok("the same reduction with no damage marked leaves it alive")

# Stupefy's printed floor of 1 is stricter than the general floor of 0.
s = fresh()
w = s.add_permanent(PLAIN[2], 1, bf_loc(0))
resolve.resolve(s, T, CFG, STUPEFY, 0, [w], -1, from_hand=True)
if combat.might(s, T, w) != 1:
    die("might", f"Stupefy on a 2 should give 1, got {combat.might(s,T,w)}")
resolve.resolve(s, T, CFG, SMOKE_SCREEN, 0, [w], -1, from_hand=True)
if combat.might(s, T, w) != 1:
    die("might", "'to a minimum of 1 Might' must clamp, not stack past 1")
ok("card-printed floors clamp: Stupefy then Smoke Screen leaves 1 Might, not -3")

# Buffs go the other way and stack.
s = fresh()
b = s.add_permanent(PLAIN[3], 0, bf_loc(0))
log = resolve.resolve(s, T, CFG, DISCIPLINE, 0, [b], -1, from_hand=True)
if combat.might(s, T, b) != 5:
    die("might", f"Discipline +2 on a 3 should give 5, got {combat.might(s,T,b)}")
assert OP_DRAW in log["resolved"], "Discipline draws"
ok("Discipline gives +2 and draws")

# "this turn" -- the modifier is gone after the end-of-turn cleanup.
phases.end_turn(s, CFG)
if int(s.perms[b, P_MIGHT_MOD]) != 0 or combat.might(s, T, b) != 3:
    die("might", "a 'this turn' modifier must clear at end of turn")
ok("modifiers expire at end of turn, like other turn-scoped effects")


# ---------------------------------------------------------------------------
print("\n[7] tokens: ready, Temporary, and bound to the hidden battlefield")
from rl.engine.state import P_READY, P_CTRL
SPRITE_CALL, SPRITE_BURST = SPECS["Sprite Call"], SPECS["Sprite Burst"]

# From Hidden at battlefield 0 -> the token must arrive THERE (811.1.d.3).
s = fresh()
s.bf_ctrl[0] = 0
log = resolve.resolve(s, T, CFG, SPRITE_CALL, 0, [bf_loc(0)], 0, from_hand=False)
tok = log["tokens"]
if len(tok) != 1:
    die("token", f"Sprite Call makes one token, got {len(tok)}")
if int(s.perms[tok[0], P_LOC]) != bf_loc(0):
    die("token", "811.1.d.3 -- a token from a hidden spell must arrive at that "
                 "battlefield")
if int(s.perms[tok[0], P_READY]) != 1:
    die("token", "'Play a READY 3 Might Sprite' must enter ready, not exhausted")
if combat.might(s, T, tok[0]) != 3:
    die("token", f"expected 3 Might, got {combat.might(s,T,tok[0])}")
ok("Sprite Call from hiding: one ready 3-Might token, at that battlefield")

# It carries [Temporary] from the token card itself, so it expires through the
# existing Beginning-Phase path -- and that is the conquer-vs-hold inversion:
# an empty battlefield is a lost battlefield (190.4.c).
if not T.has(int(s.perms[tok[0], P_CARD]), "Temporary"):
    die("token", "the Sprite token should carry [Temporary]")
s.active = 0
killed = phases.expire_temporary(s, T)
if tok[0] not in killed or s.perms[tok[0], P_ALIVE] == 1:
    die("token", "the [Temporary] token must die at the start of Beginning")
ok("the token is [Temporary] and dies before scoring, as the inversion requires")

# Sprite Burst makes two.
s = fresh()
log = resolve.resolve(s, T, CFG, SPRITE_BURST, 1, [base_loc(1)], -1, from_hand=True)
if len(log["tokens"]) != 2:
    die("token", f"Sprite Burst makes two tokens, got {len(log['tokens'])}")
if any(int(s.perms[i, P_CTRL]) != 1 for i in log["tokens"]):
    die("token", "tokens must be controlled by the caster")
ok("Sprite Burst makes two tokens for the caster")


# ---------------------------------------------------------------------------
print("\n[8] location slots, movement and bounce")
from rl.engine.effects import TK_LOCATION
RIDE, CHARM = SPECS["Ride The Wind"], SPECS["Charm"]
GUST, STARX = SPECS["Gust"], SPECS["Star-Crossed"]

# A LOC_BOUND location slot is pinned to the hidden battlefield (811.1.d.3);
# a LOC_FREE one is not. This is the fix that replaced an approximation.
s = fresh()
opts_free = resolve.legal_targets(s, T, RIDE, 1, 0, [], 0)     # hidden at B0
if len(opts_free) < 3:
    die("location", f"a LOC_FREE location slot should reach everywhere: {opts_free}")
opts_bound = resolve.legal_targets(s, T, SPRITE_CALL, 0, 0, [], 0)
if opts_bound != [bf_loc(0)]:
    die("location", f"a bound token must land at the hidden battlefield: {opts_bound}")
ok("location slots respect per-slot locality, so tokens pin but moves do not")

# Ride The Wind moves and readies -- readying is the point of the card.
s = fresh()
u = s.add_permanent(PLAIN[3], 0, base_loc(0), ready=False)
resolve.resolve(s, T, CFG, RIDE, 0, [u, bf_loc(1)], -1, from_hand=True)
from rl.engine.state import P_READY
if int(s.perms[u, P_LOC]) != bf_loc(1) or int(s.perms[u, P_READY]) != 1:
    die("move", "Ride The Wind must move the unit AND ready it")
ok("Ride The Wind moves a friendly unit and readies it")

# Charm moves an ENEMY unit; moving it into your units stages combat (461).
s = fresh()
mine = s.add_permanent(PLAIN[5], 0, bf_loc(0))
s.bf_ctrl[0] = 0
foe = s.add_permanent(PLAIN[2], 1, base_loc(1))
resolve.resolve(s, T, CFG, CHARM, 0, [foe, bf_loc(0)], -1, from_hand=True)
# The combat is STAGED, not initiated: 321 forbids a Cleanup while Chain Items
# are resolving, so `resolve` deliberately does not run one. The action layer
# runs the Cleanup once the Chain empties.
if int(s.perms[foe, P_LOC]) != bf_loc(0) or s.perms[foe, P_ALIVE] != 1:
    die("move", "Charm should move the enemy without resolving combat inline")
combat.cleanup(s, T, CFG, mover=0, dst=bf_loc(0))
if s.perms[foe, P_ALIVE] == 1:
    die("move", "a 2-Might unit charmed into a 5-Might garrison should die")
ok("Charm stages combat by presence (461); the Cleanup then resolves it")

# Gust's "3 Might or less" is a restriction, and bounce returns to hand.
s = fresh()
small = s.add_permanent(PLAIN[3], 1, bf_loc(0))
big = s.add_permanent(PLAIN[5], 1, bf_loc(0))
opts = resolve.legal_targets(s, T, GUST, 0, 0, [], -1)
if big in opts or small not in opts:
    die("bounce", f"Gust should reach only the 3-Might unit: {opts}")
before = int(s.n_hand[1])
resolve.resolve(s, T, CFG, GUST, 0, [small], -1, from_hand=True)
if s.perms[small, P_ALIVE] == 1 or int(s.n_hand[1]) != before + 1:
    die("bounce", "the unit should leave the board and enter its owner's hand")
ok("Gust bounces a 3-Might unit to its owner's hand, not the 5-Might one")

# 185.3 -- a token that leaves the board ceases to exist, it does not bounce.
s = fresh()
s.bf_ctrl[0] = 1
log = resolve.resolve(s, T, CFG, SPRITE_CALL, 1, [bf_loc(0)], 0, from_hand=False)
tokn = log["tokens"][0]
before = int(s.n_hand[1])
resolve.resolve(s, T, CFG, GUST, 0, [tokn], -1, from_hand=True)
if s.perms[tokn, P_ALIVE] == 1:
    die("bounce", "the token should leave the board")
if int(s.n_hand[1]) != before:
    die("bounce", "185.3 -- a token must cease to exist, not go to hand")
ok("185.3 -- a bounced token ceases to exist rather than entering a hand")

# ---------------------------------------------------------------------------
print("\n[6] cost discounts: ordering is solved, not chosen (356.1/356.4.e)")

from itertools import permutations
from functools import reduce
from rl.engine.cost import apply_discounts, order_discounts

# The rulebook's own example. Eager Apprentice is -1 with a floor of 1; Sky
# Splitter's own discount is -7 with no floor. 8 -> 7 -> 0, not 8 -> 1 -> 1.
if apply_discounts(8, [(1, 1), (7, 0)]) != 0:
    die("discounts", "356.4.e -- the floored discount must be applied first, "
                     "so the unfloored one can take the cost to 0")
ok("Sky Splitter reaches 0 Energy, not 1 -- the floor binds only its own discount")

# Descending floor is OPTIMAL, not a heuristic: it must equal exhaustive search.
def fold(cost, ds):
    return reduce(lambda c, d: min(c, max(c - d[0], d[1])), ds, cost)

rng = np.random.default_rng(7)
for _ in range(3000):
    cost = int(rng.integers(0, 13))
    ds = [(int(rng.integers(0, 6)), int(rng.choice([0, 0, 1, 2, 3])))
          for _ in range(int(rng.integers(2, 5)))]
    best = min(fold(cost, p) for p in permutations(ds))
    if apply_discounts(cost, ds) != best:
        die("discounts", f"greedy order was not optimal for cost={cost} ds={ds}")
ok("descending-floor order matches exhaustive search on 3000 random cases")

# A discount never raises a cost, and never goes below zero.
if apply_discounts(2, [(9, 0)]) != 0 or apply_discounts(0, [(3, 2)]) != 0:
    die("discounts", "a discount must never raise a cost or go below 0")
ok("discounts never raise a cost and never go negative")

# ---------------------------------------------------------------------------
print("\n[7] [Deflect] taxes the OPPONENT's targeting (809)")

from dataclasses import replace as _replace
from rl.engine import actions as A
from rl.engine import chain
from rl.engine.state import MAIN

V1 = _replace(Config().at_victory_score(3), units_only=False)
BIRD = T.id_of("Bird")                     # 1 Might, [Deflect]
RUNE_PRISON = T.id_of("Rune Prison")       # [Action] 2e1p: Stun a unit

if int(T.deflect[BIRD]) != 1:
    die("deflect", "the Bird token should carry Deflect 1 (809.1.b.3)")

def _board(runes):
    """A board with `runes` runes in the spell's own domain, and nothing else.

    Rune Prison costs {2 energy}{1 power}, so its printed Power needs one rune
    of ITS domain; the Deflect surcharge may then come from any domain
    (809.1.c.1), which here means the same pile.
    """
    dom = next(d for d in range(6) if int(T.domain_mask[RUNE_PRISON]) >> d & 1)
    s = GameState()
    s.n_deck[:] = 10
    s.deck[:, :10] = PLAIN[2]
    s.hand[0, 0] = RUNE_PRISON
    s.n_hand[0] = 1
    s.runes_ready[0, :] = 0
    s.runes_ready[0, dom] = runes
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s

# Enemy Bird: the surcharge applies. Friendly Bird: it does not (809.1.c).
s = _board(runes=3)
mine = s.add_permanent(BIRD, 0, bf_loc(0))
theirs = s.add_permanent(BIRD, 1, bf_loc(1))
if resolve.deflect_cost(s, T, 0, [mine]) != 0:
    die("deflect", "targeting your OWN Deflect unit must cost nothing")
if resolve.deflect_cost(s, T, 0, [theirs]) != 1:
    die("deflect", "targeting an enemy Deflect unit costs 1 Power")
if resolve.deflect_cost(s, T, 0, [theirs, theirs]) != 2:
    die("deflect", "809.1.c is per CHOICE -- choosing it twice pays twice")
ok("the surcharge is the opponent's only, and is charged per choice")

# With runes to spare, both are legal targets.
opts = resolve.legal_targets(s, T, SPECS["Rune Prison"], 0, 0, [], -1,
                             card=RUNE_PRISON)
if sorted(opts) != sorted([mine, theirs]):
    die("deflect", f"with 3 runes both should be targetable, got {opts}")
ok("with Power to spare, a Deflect unit is a legal target like any other")

# Exactly enough for the card and nothing for the surcharge: the enemy Bird
# stops being a legal choice, rather than being announced and then stuck.
#
# Punch First is {1 energy}{2 power}: the rune requirement is max(1, 2) = 2 and
# ALL of it is recycled for Power, so two runes leave nothing behind. Rune
# Prison cannot show this -- it recycles only 1 of its 2 runes, so the spare
# always covers the surcharge.
PUNCH = T.id_of("Punch First")
dom_p = next(d for d in range(6) if int(T.domain_mask[PUNCH]) >> d & 1)
s2 = GameState()
s2.n_deck[:] = 10
s2.deck[:, :10] = PLAIN[2]
s2.hand[0, 0] = PUNCH
s2.n_hand[0] = 1
s2.runes_ready[0, :] = 0
s2.runes_ready[0, dom_p] = 2
s2.phase, s2.active, s2.priority = MAIN, 0, 0
mine2 = s2.add_permanent(BIRD, 0, bf_loc(0))
theirs2 = s2.add_permanent(BIRD, 1, bf_loc(1))
opts2 = resolve.legal_targets(s2, T, SPECS["Punch First"], 0, 0, [], -1,
                              card=PUNCH)
if theirs2 in opts2:
    die("deflect", "an unaffordable Deflect surcharge must remove the target; "
                   "otherwise the card announces and can never finalize")
if mine2 not in opts2:
    die("deflect", "the free (friendly) target was wrongly removed too")
ok("an unpayable surcharge makes it not a target -- no announce-then-deadlock")

# ---------------------------------------------------------------------------
print("\n[8] Banish is not a Kill (427.2.a), and a blink returns a NEW object")

from rl.engine import combat as _combat
from rl.engine.state import F_BUFFED, P_DMG, P_FLAGS, P_READY

TB = T.id_of("Temporal Breach")
YORDLE = T.id_of("Lecturing Yordle")      # [Tank] + ETB draw 1

s = GameState()
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN[2]
s.hand[0, 0] = TB
s.n_hand[0] = 1
s.runes_ready[:, :] = 6
s.phase, s.active, s.priority = MAIN, 0, 0
u = s.add_permanent(YORDLE, 0, bf_loc(0), ready=True)
s.perms[u, P_FLAGS] |= F_BUFFED
_combat.mark_damage(s, T, u, 1)
hand_before = int(s.n_hand[0])

A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, u))
for _ in range(12):
    if s.n_chain == 0 and s.n_trig == 0:
        break
    seat = A.acting_seat(s)
    if seat < 0:
        break
    acts = A.legal_actions(s, T, V1, seat)
    A.apply(s, T, V1, next((x for x in acts if x.kind == A.A_PASS), acts[0]))

live = [i for i in range(s.n_perms)
        if int(s.perms[i, P_CARD]) == YORDLE and s.perms[i, P_ALIVE] == 1]
if len(live) != 1 or live[0] == u:
    die("banish", f"expected one NEW row for the returned unit, got {live}")
new = live[0]
if int(s.perms[new, P_LOC]) != bf_loc(0):
    die("banish", "'to the same location' was not honoured")
if int(s.perms[new, P_DMG]) or (s.perms[new, P_FLAGS] & F_BUFFED):
    die("banish", "it came back with its damage or Buff -- 705 removes buffs "
                  "when a unit leaves play, and it is a new object")
if s.perms[new, P_READY]:
    die("banish", "359.2.c -- a played unit enters exhausted")
ok("it returns as a new object: no damage, no Buff, entering exhausted")

# It was PLAYED, so its own entry trigger fires.
if int(s.n_hand[0]) != hand_before - 1 + 1:
    die("banish", f"the returned unit's ETB did not fire: hand "
                  f"{int(s.n_hand[0])}")
ok("'its owner plays it' fires the unit's own when-you-play-me trigger")

# 427.2.a -- not a Kill: only the spell reached the trash, not the unit.
if int(s.n_trash[0]) != 1:
    die("banish", f"trash holds {int(s.n_trash[0])}; banishing must not trash "
                  f"the unit (427.2.a) -- only Temporal Breach itself goes")
ok("427.2.a -- banish is not a kill: no trash, and no [Deathknell]")

# ---------------------------------------------------------------------------
print("\n[9] [Flow] plays from the trash, then BANISHES (829.1.b)")

DREDGE = T.id_of("Dredge Up")             # Draw 1.  [Flow] {2 energy}
if int(T.flow_energy[DREDGE]) != 2:
    die("flow", "the Flow cost is an alternate cost and must parse (829.1.c)")

s = GameState()
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN[2]
s.trash[0, 0] = DREDGE
s.n_trash[0] = 1
s.runes_ready[:, :] = 4
s.phase, s.active, s.priority = MAIN, 0, 0

offers = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]
if not offers:
    die("flow", "a [Flow] spell in the trash was never offered")
ok("a [Flow] spell is playable from the trash")

A.apply(s, T, V1, offers[0])
for _ in range(8):
    if s.n_chain == 0:
        break
    seat = A.acting_seat(s)
    A.apply(s, T, V1, next(x for x in A.legal_actions(s, T, V1, seat)
                           if x.kind == A.A_PASS))
if int(s.n_hand[0]) != 1:
    die("flow", "the spell did not resolve")
if int(s.n_trash[0]) != 0 or int(s.n_banished[0]) != 1:
    die("flow", f"829.1.b -- 'then banish it'. trash={int(s.n_trash[0])} "
                f"banished={int(s.n_banished[0])}; landing back in the trash "
                f"would make it replayable every turn forever")
ok("it is BANISHED, not trashed -- the loop is closed (829.1.b.1)")

if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]:
    die("flow", "the banished card is still being offered from the trash")
ok("and cannot be played again")

# ---------------------------------------------------------------------------
print("\n[10] [Flow] zone bookkeeping: which zone, and how many copies")

# The project owner's question, and it is the right one to ask: a card with
# [Flow] has TWO destinations depending on where it was played from, and the
# engine picks between them from a single flag on the chain row. If that flag
# were set from the card rather than from the play, every Flow spell would
# banish itself out of the deck the first time it was cast from hand.
#
# Zone counts are kept as card IDS in a flat array, not as unique per-copy
# objects, so "do two copies count as two" is a real question about the
# bookkeeping rather than one answered by construction.


def flow_state(hand=(), trash=()):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    for i, c in enumerate(hand):
        s.hand[0, i] = c
    s.n_hand[0] = len(hand)
    for i, c in enumerate(trash):
        s.trash[0, i] = c
    s.n_trash[0] = len(trash)
    s.runes_ready[:, :] = 4
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


def settle(s, limit=12):
    """Pass until the chain empties."""
    for _ in range(limit):
        if s.n_chain == 0:
            return
        seat = A.acting_seat(s)
        if seat < 0:
            return
        acts = A.legal_actions(s, T, V1, seat)
        A.apply(s, T, V1, next(x for x in acts if x.kind == A.A_PASS))
    raise AssertionError("chain never emptied")


# (a) played from HAND, a Flow card goes to the TRASH like any other spell.
s = flow_state(hand=[DREDGE])
play = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY]
if not play:
    die("flow", "a [Flow] card in hand must still be playable for its printed cost")
A.apply(s, T, V1, play[0])
settle(s)
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != DREDGE:
    die("flow", f"played from HAND it must go to the trash; trash holds "
                f"{int(s.n_trash[0])}")
if int(s.n_banished[0]) != 0:
    die("flow", "played from hand it was BANISHED -- 829.1.b.1 replaces the "
                "destination only for a card played from the trash, so this "
                "would eat the card on its first ordinary cast")
ok("from hand -> trash (the Flow banish does not apply to a normal cast)")

# It is now in the trash, so the Flow line has become available -- the round
# trip hand -> trash -> chain -> banishment, in one game.
if not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]:
    die("flow", "after being cast from hand it should be Flow-playable")
ok("...and is then Flow-playable out of that trash")

# (b) a copy ALREADY in the trash does not stop the hand copy being played, and
# the trash ends up holding BOTH.
s = flow_state(hand=[DREDGE], trash=[DREDGE])
acts = A.legal_actions(s, T, V1, 0)
if not [a for a in acts if a.kind == A.A_PLAY_FLOW]:
    die("flow", "the trash copy should be Flow-playable")
play = [a for a in acts if a.kind == A.A_PLAY]
if not play:
    die("flow", "the hand copy should be playable for its printed cost")
A.apply(s, T, V1, play[0])
if int(s.n_trash[0]) != 1:
    die("flow", "announcing from hand disturbed the trash")
settle(s)
if int(s.n_trash[0]) != 2 or list(s.trash[0, :2]) != [DREDGE, DREDGE]:
    die("flow", f"two copies must be two entries; trash = "
                f"{list(s.trash[0, :3])} n={int(s.n_trash[0])}")
if int(s.n_banished[0]) != 0:
    die("flow", "the hand copy banished itself because a copy sat in the trash")
ok("a trash copy + a hand cast = TWO in the trash, nothing banished")

# (c) two identical copies in the trash: Flow consumes exactly one.
s = flow_state(trash=[DREDGE, DREDGE])
offers = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]
if len(offers) != 1:
    die("flow", f"two identical copies should collapse to ONE offer, got "
                f"{len(offers)} -- the choices are indistinguishable and "
                f"duplicates only inflate the branching factor")
A.apply(s, T, V1, offers[0])
settle(s)
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != DREDGE:
    die("flow", f"Flow must consume exactly one copy; trash = "
                f"{list(s.trash[0, :3])} n={int(s.n_trash[0])}")
if int(s.n_banished[0]) != 1:
    die("flow", "the played copy was not banished")
if not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]:
    die("flow", "the SECOND copy should still be Flow-playable")
ok("of two copies in the trash, Flow banishes one and leaves the other playable")

# (d) a COUNTERED Flow spell is banished too (829.1.b.1).
#
# The rule hangs the banish on *leaving the Chain after being finalized*, not on
# resolving. Trashing a countered Flow spell would refund it to the exact zone
# Flow plays from, so countering one would be a favour: the same copy returns
# every turn. This is the loop the keyword's own banish exists to close, and it
# reopens through a function that never mentions Flow.
from rl.engine import chain as chain_mod
from rl.engine.state import C_UID

s = flow_state(trash=[DREDGE])
offers = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]
A.apply(s, T, V1, offers[0])
if s.n_chain != 1:
    die("flow", "the Flow spell should be a finalized chain item awaiting priority")
uid = int(s.chain[0, C_UID])
name = chain_mod.counter(s, T, uid)
if name != "Dredge Up":
    die("flow", f"counter did not remove the Flow spell: {name}")
if int(s.n_trash[0]) != 0 or int(s.n_banished[0]) != 1:
    die("flow", f"829.1.b.1 -- a countered Flow spell leaves the chain after "
                f"finalization, so it is BANISHED. trash={int(s.n_trash[0])} "
                f"banished={int(s.n_banished[0])}; trashing it refunds the "
                f"card and countering becomes a favour")
ok("a countered Flow spell is banished, not refunded to the trash")

# ...but an ordinary countered spell still goes to the trash. The Flow branch
# must be reading the chain row, not the card.
s = flow_state(hand=[DREDGE])
i = chain_mod.push(s, DREDGE, 0)
chain_mod.finalize(s, i)
chain_mod.counter(s, T, int(s.chain[i, C_UID]))
if int(s.n_trash[0]) != 1 or int(s.n_banished[0]) != 0:
    die("flow", "a countered NON-Flow play of the same card must go to the trash")
ok("the same card countered on a normal cast still goes to the trash")

# ---------------------------------------------------------------------------
print("\n[11] recycle is a third destination, not a synonym (416)")

# Trash, Banishment and the bottom of the deck are three different places, and
# the only one of them that gives the card back is Recycle. Pinned here as a
# primitive because the trash-recursion and deck-manipulation clusters both
# spend it, and both would otherwise each invent their own answer.
s = GameState()
s.n_deck[0] = 3
s.deck[0, :3] = [PLAIN[2], PLAIN[3], PLAIN[5]]
s.deck_ptr[0] = 1                                  # one card already drawn
s.recycle_card(0, DREDGE)
if int(s.n_deck[0]) != 4 or int(s.deck[0, 3]) != DREDGE:
    die("recycle", f"416.1.a -- recycle goes to the BOTTOM of the main deck; "
                   f"deck = {list(s.deck[0, :5])}")
if int(s.n_trash[0]) or int(s.n_banished[0]):
    die("recycle", "recycle is not the trash and not the Banishment")
ok("416.1.a -- a recycled card lands on the bottom of its owner's main deck")

# It is drawable again: that is the whole difference from banishing.
s.deck_ptr[0] = 3
s.active = 0
if phases.draw(s, 1) != [DREDGE]:
    die("recycle", "a recycled card must come back around -- it is not removal")
ok("...and comes back on the draw, which banishing never does")

# Bottom means bottom for the OWNER (416.1.c), so seat 1's deck is untouched.
if int(s.n_deck[1]) != 0:
    die("recycle", "416.1.c -- each player recycles to their own deck")
ok("416.1.c -- it is the owner's deck, whoever was told to do the recycling")

# The array is not infinite, but the drawn prefix is dead space. Filling the
# deck and recycling once must reclaim it rather than overflow.
s = GameState()
cap = s.deck.shape[1]
s.n_deck[0] = cap
s.deck[0, :cap] = PLAIN[2]
s.deck_ptr[0] = 10
s.recycle_card(0, DREDGE)
if int(s.n_deck[0]) != cap - 10 + 1 or int(s.deck_ptr[0]) != 0:
    die("recycle", f"a full deck array should reclaim the drawn prefix; "
                   f"n_deck={int(s.n_deck[0])} ptr={int(s.deck_ptr[0])}")
if int(s.deck[0, cap - 10]) != DREDGE:
    die("recycle", "the recycled card is not on the bottom after compaction")
ok("a full deck array reclaims the drawn prefix instead of overflowing")

# ---------------------------------------------------------------------------
print("\n[12] trash recursion: naming a card in an unordered zone (108.2.c)")

from rl.engine import resolve as rsv
from rl.engine.effects import ABILITIES, TR_PLAY_ME

MORBID = T.id_of("Morbid Return")
GEAR = next(c for c in range(T.n) if T.is_type(c, "Gear") and not T.is_token(c))
DOG = T.id_of("Starhound")                       # tags: Dog, Mount Targon


def trash_state(cards, seat=0):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    for i, c in enumerate(cards):
        s.trash[seat, i] = c
    s.n_trash[seat] = len(cards)
    s.runes_ready[:, :] = 6
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


def names(cs):
    return sorted(T.names[c] for c in cs)


# The slot's restrictions are on the CARD, since there is no permanent to ask.
s = trash_state([PLAIN[2], GEAR, MORBID])
cases = [
    (SPECS["Morbid Return"], [PLAIN[2]], "a unit"),
    (ABILITIES["Aspiring Engineer"][0], [GEAR], "a gear"),
    (ABILITIES["Annie - Stubborn"][0], [MORBID], "a spell"),
    (ABILITIES["Guardian of the Passage"][0], [PLAIN[2], GEAR], "a unit or gear"),
]
for spec, want, label in cases:
    got = rsv.legal_targets(s, T, spec, 0, 0, [], -1)
    if names(got) != names(want):
        die("trash", f"{label!r} slot offered {names(got)}, wanted {names(want)}")
ok("card_type narrows a trash slot: unit / spell / gear / unit-or-gear")

# Tags, not types: Starhound returns "a Bird, Cat, Dog, or Poro" and says
# nothing about what type the thing is.
s = trash_state([PLAIN[2], DOG])
got = rsv.legal_targets(s, T, ABILITIES["Starhound"][0], 0, 0, [], -1)
if names(got) != [T.names[DOG]]:
    die("trash", f"the tag whitelist offered {names(got)}")
ok("a tag whitelist reaches the Dog and not the plain unit")

# --- duplicates, the whole reason the slot holds a CARD and not an index ---
# 108.2.c: the trash is unordered, so two copies are one choice.
s = trash_state([PLAIN[2], PLAIN[2]])
got = rsv.legal_targets(s, T, SPECS["Morbid Return"], 0, 0, [], -1)
if len(got) != 1:
    die("trash", f"two copies of one card must be ONE offer, got {len(got)}")
ok("two copies of a card in the trash collapse to one offer (108.2.c)")

# ...but a SECOND slot may name it again, because a second copy is there.
HID = next(c for c in range(T.n) if T.has(c, "Hidden") and not T.is_token(c))
GW = SPECS["Guerilla Warfare"]
s = trash_state([HID, HID])
if not rsv.legal_targets(s, T, GW, 1, 0, [HID], -1):
    die("trash", "with two copies present, both slots should be able to take one")
ok("two slots may name the same card when the trash holds two copies")

# With only one copy, the second slot may not repeat it. This is the case a
# `not in chosen` membership test gets right by accident and a raw index test
# gets wrong: it has to COUNT.
s = trash_state([HID])
if rsv.legal_targets(s, T, GW, 1, 0, [HID], -1):
    die("trash", "the second slot took a copy that was already spoken for")
ok("with one copy, the second slot cannot name it again")

# --- a full play-through ---------------------------------------------------
s = trash_state([PLAIN[2]])
s.hand[0, 0] = MORBID
s.n_hand[0] = 1
play = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY]
if not play:
    die("trash", "Morbid Return was not playable with a unit in the trash")
A.apply(s, T, V1, play[0])
tgts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if len(tgts) != 1 or tgts[0].arg != PLAIN[2]:
    die("trash", f"the target offer should be the CARD id, got {tgts}")
A.apply(s, T, V1, tgts[0])
settle(s)
if int(s.n_hand[0]) != 1 or int(s.hand[0, 0]) != PLAIN[2]:
    die("trash", f"the unit did not reach the hand: "
                 f"{[T.names[c] for c in s.hand[0, :max(1, int(s.n_hand[0]))]]}")
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != MORBID:
    die("trash", "the trash should now hold Morbid Return and nothing else")
ok("Morbid Return moves the unit trash -> hand and itself hand -> trash")

# --- 355.8: an empty trash must not put an unfillable ability on the Chain --
s = GameState()
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN[2]
s.runes_ready[:, :] = 6
s.phase, s.active, s.priority = MAIN, 0, 0
u = s.add_permanent(T.id_of("Cemetery Attendant"), 0, base_loc(0))
if chain.fire(s, T, V1, TR_PLAY_ME, u) or s.n_chain:
    die("trash", "355.8 -- an ability with no legal choice must never reach "
                 "the Chain; with an empty trash it would sit Pending forever")
ok("355.8 -- an ETB that needs the trash does not fire on an empty one")

# --- 359.3.e: a target that leaves the trash before resolution fizzles ------
s = trash_state([PLAIN[2]])
s.hand[0, 0] = MORBID
s.n_hand[0] = 1
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_PLAY))
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_TARGET))
s.n_trash[0] = 0                      # something else claimed it mid-chain
s.trash[0, 0] = -1
settle(s)
if int(s.n_hand[0]) != 0:
    die("trash", "a card that left the trash between finalization and "
                 "resolution must not still arrive in hand (359.3.e)")
ok("a target that leaves the trash mid-chain fizzles rather than crashing")

# ---------------------------------------------------------------------------
print("\n[13] board slots that name a TYPE or a TAG")

from rl.engine.effects import TR_DEATH
from rl.engine.state import P_READY

# Salvage kills a GEAR. Gear are permanents like any other, so this is the
# same slot machinery -- but a slot defaults to "a unit", and without
# `card_type` the card would happily kill a unit instead.
s = GameState()
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN[2]
s.runes_ready[:, :] = 6
s.phase, s.active, s.priority = MAIN, 0, 0
gear = s.add_permanent(GEAR, 0, base_loc(0))
foe_unit = s.add_permanent(PLAIN[3], 1, bf_loc(0))
got = rsv.legal_targets(s, T, SPECS["Salvage"], 0, 0, [], -1)
if got != [gear]:
    die("types", f"'kill a gear' offered {got}, wanted only the gear row")
ok("card_type on a board slot reaches the gear and not the units")

# ...and "you may kill a gear" stays playable with no gear on the board, since
# 355.14's optional slot can be left empty. The draw is unconditional.
s2 = GameState()
s2.n_deck[:] = 20
s2.deck[:, :20] = PLAIN[2]
s2.runes_ready[:, :] = 6
s2.phase, s2.active, s2.priority = MAIN, 0, 0
s2.hand[0, 0] = T.id_of("Salvage")
s2.n_hand[0] = 1
if not [a for a in A.legal_actions(s2, T, V1, 0) if a.kind == A.A_PLAY]:
    die("types", "'You may kill a gear. Draw 1' must be playable with no gear")
ok("an optional slot keeps the card playable when nothing fits it (355.14)")

# Bubble Bot readies ANOTHER friendly Mech -- a tag whitelist plus not_self.
s = GameState()
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN[2]
s.phase, s.active, s.priority = MAIN, 0, 0
bot = s.add_permanent(T.id_of("Bubble Bot"), 0, base_loc(0))
mech = s.add_permanent(T.id_of("Mech"), 0, base_loc(0))
plain = s.add_permanent(PLAIN[2], 0, base_loc(0))
s.perms[[bot, mech, plain], P_READY] = 0
got = rsv.legal_targets(s, T, ABILITIES["Bubble Bot"][0], 0, 0, [], -1, bot)
if got != [mech]:
    die("types", f"'another friendly Mech' offered {got}, wanted [{mech}] -- "
                 f"Bubble Bot is itself a Mech and must be excluded")
ok("a tag whitelist plus not_self excludes the source from its own trigger")

# ---------------------------------------------------------------------------
print("\n[14] [Deathknell] with a condition: Lonely Poro (808.1)")

PORO = T.id_of("Lonely Poro")


def poro_board(others_here: int, others_elsewhere: int = 0, enemies: int = 0):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    s.phase, s.active, s.priority = MAIN, 0, 0
    p = s.add_permanent(PORO, 0, bf_loc(0))
    for _ in range(others_here):
        s.add_permanent(PLAIN[2], 0, bf_loc(0))
    for _ in range(others_elsewhere):
        s.add_permanent(PLAIN[2], 0, base_loc(0))
    for _ in range(enemies):
        s.add_permanent(PLAIN[2], 1, bf_loc(0))
    return s, p


def drain(s):
    """Put queued triggers on the Chain and run it out, as `apply` would.

    Goes through `chain.place` rather than `chain.fire`: `_destroy` has already
    QUEUED the trigger, and firing on top of it would put the same Deathknell
    on the Chain twice -- which is what a hand-rolled fixture does when it
    forgets that the drain is centralised in `actions._settle`.
    """
    while s.n_trig:
        seat = chain.next_placer(s)
        chain.place(s, T, V1, chain.orderable(s, T, seat)[0])
    settle(s)


def poro_death(*args, **kw):
    """Kill a Lonely Poro through the REAL death path and drain its trigger."""
    s, p = poro_board(*args, **kw)
    combat._destroy(s, T, p)
    drain(s)
    return int(s.n_hand[0])


if poro_death(0) != 1:
    die("deathknell", "a Poro that died with no other friendly unit there "
                      "should draw 1")
ok("'if I died alone' draws when nothing friendly is there")

if poro_death(1) != 0:
    die("deathknell", "a Poro that died beside a friendly unit is not alone")
ok("...and does not draw with a friendly unit beside it")

# "Here" is the location, not the board: friends elsewhere do not crowd it, and
# enemies are not friendly.
if poro_death(0, others_elsewhere=2) != 1:
    die("deathknell", "friendly units at ANOTHER location must not count -- "
                      "'alone' is about this location")
if poro_death(0, enemies=2) != 1:
    die("deathknell", "enemy units are not friendly units")
ok("'here' means this location, and 'friendly' excludes the opponent's units")

# The captured answer must survive the response window. 808.1.d.2 puts the
# Deathknell on the Chain before the card reaches the trash, and priority
# passes before it resolves -- so a friendly unit can walk in first. It died
# alone regardless: past tense.
s, p = poro_board(0)
combat._destroy(s, T, p)
while s.n_trig:
    chain.place(s, T, V1, chain.orderable(s, T, chain.next_placer(s))[0])
s.add_permanent(PLAIN[2], 0, bf_loc(0))       # arrives while the trigger waits
settle(s)
if int(s.n_hand[0]) != 1:
    die("deathknell", "a unit arriving after the death changed the answer -- "
                      "359.3.f.3 captures at trigger time, and 'I DIED alone' "
                      "is settled in the past tense")
ok("a unit arriving after the death cannot un-alone it (359.3.f.3)")

# Simultaneous deaths: 143.2.a is a continuous check, so everything it catches
# dies at one instant. Two friendly Poros dying together at one battlefield
# each had the other there, so NEITHER died alone -- and crucially the answer
# must not depend on which row the sweep reached first.
for order in (0, 1):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    s.phase, s.active, s.priority = MAIN, 0, 0
    a = s.add_permanent(PORO, 0, bf_loc(0))
    b = s.add_permanent(PORO, 0, bf_loc(0))
    for perm in (a, b):
        s.perms[perm, P_DMG] = 99             # lethal to both at one instant
    killed = combat.enforce_lethal(s, T)
    if sorted(killed) != sorted([a, b]):
        die("deathknell", f"both Poros should die together, got {killed}")
    if order:
        s.trig[:2] = s.trig[[1, 0]]           # place them the other way round
    drain(s)
    if int(s.n_hand[0]) != 0:
        die("deathknell", f"two Poros dying together each had the other there, "
                          f"so neither died alone -- drew {int(s.n_hand[0])}. "
                          f"Destroying inline made this depend on row order.")
ok("two units dying together: neither died alone, in either trigger order")

# The batch-mate does not need a Deathknell of its own. A Poro dying at the
# same instant as any friendly unit did not die alone -- and this is the case
# the old inline destroy got wrong most often, because a plain unit queues no
# trigger and so left no trace that it had ever been there.
for first_poro in (True, False):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    s.phase, s.active, s.priority = MAIN, 0, 0
    rows = ([s.add_permanent(PORO, 0, bf_loc(0)),
             s.add_permanent(PLAIN[2], 0, bf_loc(0))] if first_poro else
            [s.add_permanent(PLAIN[2], 0, bf_loc(0)),
             s.add_permanent(PORO, 0, bf_loc(0))])
    for perm in rows:
        s.perms[perm, P_DMG] = 99
    combat.enforce_lethal(s, T)
    drain(s)
    if int(s.n_hand[0]) != 0:
        die("deathknell", f"a Poro dying at the same instant as a plain "
                          f"friendly unit did not die alone (poro first="
                          f"{first_poro}); drew {int(s.n_hand[0])}")
ok("...and the other unit needs no Deathknell of its own to count")

print("\n\033[32mall effect tests passed\033[0m")
