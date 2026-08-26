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
from rl.engine.state import (N_BF, P_ALIVE, P_CARD, P_LOC, GameState,
                             base_loc, bf_loc)

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
from rl.engine.effects import (ABILITIES, TR_PLAY_ME, W_ANY,
                               pack_trash, unpack_trash)

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
    """Card names behind a list of PACKED trash targets."""
    return sorted(T.names[unpack_trash(c)[1]] for c in cs)


def mine(*cards):
    """Pack cards as seat 0's, the seat every case below casts from."""
    return [pack_trash(0, c) for c in cards]


# The slot's restrictions are on the CARD, since there is no permanent to ask.
s = trash_state([PLAIN[2], GEAR, MORBID])
cases = [
    (SPECS["Morbid Return"], mine(PLAIN[2]), "a unit"),
    (ABILITIES["Aspiring Engineer"][0], mine(GEAR), "a gear"),
    (ABILITIES["Annie - Stubborn"][0], mine(MORBID), "a spell"),
    (ABILITIES["Guardian of the Passage"][0], mine(PLAIN[2], GEAR),
     "a unit or gear"),
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
if not rsv.legal_targets(s, T, GW, 1, 0, mine(HID), -1):
    die("trash", "with two copies present, both slots should be able to take one")
ok("two slots may name the same card when the trash holds two copies")

# With only one copy, the second slot may not repeat it. This is the case a
# `not in chosen` membership test gets right by accident and a raw index test
# gets wrong: it has to COUNT.
s = trash_state([HID])
if rsv.legal_targets(s, T, GW, 1, 0, mine(HID), -1):
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
if len(tgts) != 1 or tgts[0].arg != pack_trash(0, PLAIN[2]):
    die("trash", f"the target offer should be the packed card, got {tgts}")
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

# ---------------------------------------------------------------------------
print("\n[15] Fizz - Trickster: play from the trash, then RECYCLE (416.1.a)")

from rl.engine.state import (COST_NO_ENERGY, C_CARD, C_COST, C_DEST,
                             DEST_RECYCLE)

FIZZ = T.id_of("Fizz - Trickster")


def fizz_state(trash=(DREDGE,), runes=8):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    s.runes_ready[:, :] = runes
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.hand[0, 0] = FIZZ
    s.n_hand[0] = 1
    for i, c in enumerate(trash):
        s.trash[0, i] = c
    s.n_trash[0] = len(trash)
    return s


def run(s, prefer, limit=24):
    """Drive the game forward, preferring these action kinds in order."""
    out = []
    for _ in range(limit):
        seat = A.acting_seat(s)
        if seat < 0:
            break
        acts = A.legal_actions(s, T, V1, seat)
        if not acts:
            break
        act = next((a for k in prefer for a in acts if a.kind == k), None)
        if act is None:
            break
        out.append(A.apply(s, T, V1, act))
    return out


PREFER = (A.A_PLAY, A.A_PLAY_AT, A.A_ACCEPT, A.A_TARGET, A.A_PASS)

s = fizz_state()
deck_before = int(s.n_deck[0])
run(s, PREFER)
if int(s.n_trash[0]) != 0:
    die("fizz", "the replayed spell should have left the trash")
if int(s.n_deck[0]) != deck_before + 1 or int(s.deck[0, deck_before]) != DREDGE:
    die("fizz", f"'Recycle that spell' puts it on the BOTTOM of the main deck "
                f"(416.1.a); deck went {deck_before} -> {int(s.n_deck[0])}")
if int(s.n_banished[0]):
    die("fizz", "recycle is not banish -- the card must come back around")
ok("the spell is played from the trash and RECYCLED, not trashed or banished")

# It really resolved: Dredge Up draws 1. Counted off `deck_ptr` rather than the
# hand, because `run` keeps playing whatever it draws.
if int(s.deck_ptr[0]) != 1:
    die("fizz", f"the replayed spell did not resolve: {int(s.deck_ptr[0])} "
                f"cards drawn")
if not any(int(s.perms[i, P_CARD]) == FIZZ and s.perms[i, P_ALIVE] == 1
           for i in range(s.n_perms)):
    die("fizz", "Fizz should be on the board -- her ETB does not replace her")
ok("...and it actually resolved, drawing a card, with Fizz on the board")

# The replayed spell goes on the CHAIN (349), so it is respondable. This is the
# difference between playing a card and just applying its text, and it is why
# Fizz can be answered at all.
s = fizz_state()
run(s, (A.A_PLAY, A.A_PLAY_AT, A.A_ACCEPT, A.A_TARGET))   # stop before passing
item = next((i for i in range(s.n_chain)
             if int(s.chain[i, C_CARD]) == DREDGE), -1)
if item < 0:
    # It is pushed during the ABILITY's resolution, so drive one more pass pair.
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
                           if a.kind == A.A_PASS))
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
                           if a.kind == A.A_PASS))
    item = next((i for i in range(s.n_chain)
                 if int(s.chain[i, C_CARD]) == DREDGE), -1)
if item < 0:
    die("fizz", "the replayed spell never appeared on the Chain -- playing a "
                "card means putting it on the Chain (349), not applying it")
if int(s.chain[item, C_COST]) != COST_NO_ENERGY:
    die("fizz", "the replayed spell must be paid for with its Energy ignored")
if int(s.chain[item, C_DEST]) != DEST_RECYCLE:
    die("fizz", "the recycle destination was not recorded on the chain item")
ok("the replayed spell is a real Chain Item: respondable, and counterable")

# Killing it there proves the point, and proves the destination is per-ITEM:
# a countered Fizz spell still recycles, because 'recycle that spell after you
# play it' attached when it was played, not when it resolved.
deck_before = int(s.n_deck[0])
chain_mod.counter(s, T, int(s.chain[item, C_UID]))
if int(s.n_deck[0]) != deck_before + 1:
    die("fizz", "a countered replayed spell should still recycle -- the "
                "instruction attached when it was PLAYED")
ok("countering it still recycles it: the destination is per-item, not per-card")

# --- affordability is part of target legality -----------------------------
# "You must still pay its Power cost." A spell whose Power cannot be paid was
# never a legal choice -- offering it would announce something that can never
# be finalized, the same deadlock shape as a target dead-end.
def populated(trash, runes):
    """A Fizz board with something for a replayed spell to point at."""
    s = fizz_state(trash=trash, runes=runes)
    s.runes_ready[0, :] = runes
    s.add_permanent(PLAIN[2], 0, bf_loc(0))
    s.add_permanent(PLAIN[3], 1, bf_loc(0))
    s.add_permanent(PLAIN[2], 0, base_loc(0))
    return s


# Every implemented spell cheap enough for Fizz has at least one target slot,
# so the Power case is checked on a board that satisfies the rest.
FIZZ_ABIL = ABILITIES["Fizz - Trickster"][0]
POWERED = next(c for c in range(T.n)
               if T.is_type(c, "Spell") and spec_for(T, c) is not None
               and int(T.power[c]) > 0 and int(T.energy[c]) <= 3
               and rsv.can_be_cast(populated([], 6), T, spec_for(T, c), 0, -1,
                                   card=c))
s = populated([POWERED], 0)
got = rsv.legal_targets(s, T, ABILITIES["Fizz - Trickster"][0], 0, 0, [], -1)
if got:
    die("fizz", f"a spell whose Power cost cannot be paid was offered: "
                f"{names(got)}")
s = populated([POWERED], 6)
got = rsv.legal_targets(s, T, ABILITIES["Fizz - Trickster"][0], 0, 0, [], -1)
if got != [pack_trash(0, POWERED)]:
    die("fizz", f"with runes available it should be reachable: {names(got)}")
ok("an unpayable Power cost makes a trash spell not a target (359.3.e.14.a)")

# A spell whose own targets cannot all be chosen is likewise not a choice --
# and, because a priority window sits between finalizing Fizz's ability and
# resolving it, the same question is re-asked at resolution. Two real-deck
# fuzz deadlocks came from checking only the first time.
REBUKE = T.id_of("Rebuke")           # "return a unit AT A BATTLEFIELD"
s = fizz_state(trash=[REBUKE])
if rsv.legal_targets(s, T, ABILITIES["Fizz - Trickster"][0], 0, 0, [], -1):
    die("fizz", "Rebuke needs a unit at a battlefield; with none on the board "
                "it can never be played, so it is not a legal choice")
s.add_permanent(PLAIN[2], 1, bf_loc(0))
if rsv.legal_targets(s, T, ABILITIES["Fizz - Trickster"][0], 0, 0, [], -1) \
        != mine(REBUKE):
    die("fizz", "with a unit at a battlefield Rebuke becomes reachable")
ok("a spell that cannot fill its own targets is not a legal choice either")

# ...and if the board changes in the response window, the play fizzles rather
# than deadlocking a spell that can never be finalized.
s = fizz_state(trash=[REBUKE])
victim = s.add_permanent(PLAIN[2], 1, bf_loc(0))
run(s, (A.A_PLAY, A.A_PLAY_AT, A.A_ACCEPT, A.A_TARGET))
s.perms[victim, P_ALIVE] = 0           # answered before the ability resolves
run(s, (A.A_PASS,))
if any(int(s.chain[i, C_CARD]) == REBUKE for i in range(s.n_chain)):
    die("fizz", "Rebuke was put on the Chain with no legal target -- it would "
                "sit Pending with an empty option list, which deadlocks")
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != REBUKE:
    die("fizz", "a play that never happened must leave the card in the trash")
ok("a target lost in the response window fizzles the play, not the game")

# The Energy restriction is on the PRINTED cost, not on what is paid.
EXPENSIVE = next((c for c in range(T.n)
                  if T.is_type(c, "Spell") and spec_for(T, c) is not None
                  and int(T.energy[c]) > 3), -1)
if EXPENSIVE >= 0:
    s = fizz_state(trash=[EXPENSIVE])
    if rsv.legal_targets(s, T, ABILITIES["Fizz - Trickster"][0], 0, 0, [], -1):
        die("fizz", f"{T.names[EXPENSIVE]!r} costs more than {{3 energy}} and "
                    f"must be out of reach even though Fizz pays no Energy")
    ok("'no more than {3 energy}' reads the printed cost, not the cost paid")

# 355.8 -- an empty trash means no legal choice, so the ability never fires.
s = fizz_state(trash=())
run(s, PREFER)
if int(s.n_chain):
    die("fizz", "Fizz with an empty trash should leave nothing on the Chain")
ok("with an empty trash the ability never reaches the Chain (355.8)")

# 383.3.a -- "you MAY play a spell" is a choice, not an obligation, and it is
# made at finalization. Having a perfectly legal target does not force the
# replay: a spell that does not help right now should be left in the trash.
# So the decline has to be a real offered action, not merely the absence of
# targets.
s = fizz_state(trash=[DREDGE])
run(s, (A.A_PLAY, A.A_PLAY_AT))          # play Fizz, stop at her "you may"
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_DECLINE not in kinds or A.A_ACCEPT not in kinds:
    die("fizz", f"both accept and decline must be offered, got "
                f"{sorted(A.KIND_NAMES[k] for k in kinds)}")
run(s, (A.A_DECLINE, A.A_PASS))
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != DREDGE:
    die("fizz", "383.3.a.2 -- declining counts as never having triggered, so "
                "the spell stays in the trash untouched")
if int(s.deck_ptr[0]):
    die("fizz", "the declined spell must not have resolved")
ok("with a legal target available, the 'you may' can still be declined")

# ---------------------------------------------------------------------------
print("\n[16] reanimation: playing a UNIT from the trash (337.2, 806.3)")

HARROW = T.id_of("The Harrowing")
MATRON = ABILITIES["Spectral Matron"][0]


def harrow_state(trash=(), control_bf=(0,)):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    s.runes_ready[:, :] = 9
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.hand[0, 0] = HARROW
    s.n_hand[0] = 1
    for i, c in enumerate(trash):
        s.trash[0, i] = c
    s.n_trash[0] = len(trash)
    for i in control_bf:
        s.bf_ctrl[i] = 0
    return s


# **A unit is playable whether or not its text is encoded; a spell is not.**
# 337.2 resolves a unit immediately and it simply stands there, so a unit whose
# rules text the DSL cannot express is still a perfectly good unit -- the engine
# plays them from hand every game. Requiring a spec of both made The Harrowing
# able to reanimate nothing at all.
UNENCODED = next(c for c in range(T.n)
                 if T.is_type(c, "Unit") and not T.is_token(c)
                 and spec_for(T, c) is None and T.residual_text(c))
s = harrow_state(trash=[UNENCODED])
if rsv.legal_targets(s, T, SPECS["The Harrowing"], 0, 0, [], -1) \
        != mine(UNENCODED):
    die("reanimate", f"{T.names[UNENCODED]!r} has text the DSL cannot express, "
                     f"but a unit is playable regardless -- it just stands there")
ok("a unit with unencoded text is still a legal reanimation target")

# A SPELL is not: with nothing to do on resolution it would be a card spent on
# a no-op, and its unfilled target slots could dead-end.
s = harrow_state(trash=[DREDGE])
if rsv.legal_targets(s, T, SPECS["The Harrowing"], 0, 0, [], -1):
    die("reanimate", "'play a UNIT from your trash' must not reach a spell")
ok("...and a spell is not a unit, so it is out of reach entirely")

# 806.3 -- the destination is your base or a Battlefield YOU CONTROL, never
# every battlefield. Offering the difference would let this drop a unit onto
# contested ground as a free Conquer, which is the whole reason 806.3 exists.
s = harrow_state(trash=[PLAIN[2]], control_bf=(0,))
s.bf_ctrl[1] = 1
locs = rsv.legal_targets(s, T, SPECS["The Harrowing"], 1, 0,
                         mine(PLAIN[2]), -1)
if bf_loc(1) in locs:
    die("reanimate", f"806.3 -- a battlefield the opponent controls was "
                     f"offered as a play destination: {locs}")
if sorted(locs) != sorted([base_loc(0), bf_loc(0)]):
    die("reanimate", f"expected base + the controlled battlefield, got {locs}")
ok("806.3 -- only your base and Battlefields you control are destinations")

# End to end: the unit leaves the trash, enters EXHAUSTED (359.2.c) at the
# chosen location, and the spell itself goes to the trash.
s = harrow_state(trash=[PLAIN[2]])
run(s, (A.A_PLAY, A.A_TARGET, A.A_PASS))
live = [i for i in range(s.n_perms)
        if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == PLAIN[2]]
if len(live) != 1:
    die("reanimate", f"expected the reanimated unit on the board, got {live}")
if s.perms[live[0], P_READY]:
    die("reanimate", "359.2.c -- a played unit enters exhausted")
if int(s.n_trash[0]) != 1 or int(s.trash[0, 0]) != HARROW:
    die("reanimate", "the unit should have left the trash and the spell "
                     "entered it")
ok("the unit leaves the trash and enters exhausted; the spell trashes")

# "ignoring its cost" waives BOTH halves; "ignoring its Energy cost" does not.
# Spectral Matron and Soulgorger are the same card with the two wordings, which
# is why the cost mode rides on the slot rather than being assumed.
POWER_UNIT = next(c for c in range(T.n)
                  if T.is_type(c, "Unit") and not T.is_token(c)
                  and int(T.power[c]) > 0 and int(T.energy[c]) <= 3)
s = harrow_state(trash=[POWER_UNIT])
s.runes_ready[0, :] = 0                       # no runes at all
if rsv.legal_targets(s, T, MATRON, 0, 0, [], -1) != mine(POWER_UNIT):
    die("reanimate", "'ignoring its cost' waives the Power cost too, so a "
                     "rune-less board can still reanimate")
if rsv.legal_targets(s, T, SPECS["The Harrowing"], 0, 0, [], -1):
    die("reanimate", "'ignoring its ENERGY cost' still owes Power -- the "
                     "reminder text on the card exists because this is missed")
ok("'ignoring its cost' waives Power; 'ignoring its Energy cost' does not")

# ---------------------------------------------------------------------------
print("\n[17] whose trash: an unqualified 'trashes' reaches both (416.1.c)")

from rl.engine.effects import (SPEED_MAIN, CardSpec, W_ENEMY,
                               W_FRIENDLY)

FORGE = T.id_of("Forge of the Future")
SHADOWS = T.id_of("Shadows of the Past")


def two_trashes(mine_cards, theirs):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN[2]
    for seat, cards in ((0, mine_cards), (1, theirs)):
        for i, c in enumerate(cards):
            s.trash[seat, i] = c
        s.n_trash[seat] = len(cards)
    s.runes_ready[:, :] = 6
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


# The three readings of the same slot, on one board. Seat 0 casts; PLAIN[2] is
# in both trashes, so the only thing distinguishing the two offers is the pile.
s = two_trashes([PLAIN[2]], [PLAIN[2], PLAIN[3]])
UNIT_SLOT = SPECS["Shadows of the Past"].targets[0]
cases = [
    (W_FRIENDLY, [pack_trash(0, PLAIN[2])], "your trash"),
    (W_ENEMY, [pack_trash(1, PLAIN[2]), pack_trash(1, PLAIN[3])],
     "an opponent's trash"),
    (W_ANY, [pack_trash(0, PLAIN[2]), pack_trash(1, PLAIN[2]),
             pack_trash(1, PLAIN[3])], "trashes"),
]
for who, want, label in cases:
    got = rsv.legal_targets(s, T, CardSpec(speed=SPEED_MAIN,
                                           targets=(UNIT_SLOT._replace(who=who),)),
                            0, 0, [], -1)
    if sorted(got) != sorted(want):
        die("whose", f"{label!r} offered {got}, wanted {want}")
ok("who selects the PILE: your trash / an opponent's / both")

# The same card in both trashes is TWO offers, not one -- unlike two copies in
# one pile, which collapse. They are not interchangeable: 416.1.c sends each to
# a different deck.
if len({pack_trash(0, PLAIN[2]), pack_trash(1, PLAIN[2])}) != 2:
    die("whose", "a card in each trash must pack to two distinct choices")
ok("one card in two piles stays two decisions; two in one pile collapse")

# --- Forge of the Future: recycle to the OWNER's deck ----------------------
s = two_trashes([MORBID], [PLAIN[3]])
forge = s.add_permanent(FORGE, 0, base_loc(0))
chain.fire(s, T, V1, TR_PLAY_ME, forge)
settle(s)
RECRUIT = T.id_of("Recruit (271) // Buff")
tok = [i for i in range(s.n_perms)
       if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == RECRUIT]
if len(tok) != 1 or int(s.perms[tok[0], P_LOC]) != base_loc(0):
    die("forge", "the ETB token belongs at YOUR base, wherever the gear sits")
ok("'at your base' resolves to the controller's base, not the source's location")

acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("forge", "'Kill this:' should be activatable on a live gear")
A.apply(s, T, V1, acts[0])
deck0, deck1 = int(s.n_deck[0]), int(s.n_deck[1])

# Targets are chosen BEFORE the cost is paid (337.1), so the gear is still
# alive here -- and its own card is not yet in the trash, which is why Forge
# can never recycle itself.
if not s.perms[forge, P_ALIVE]:
    die("forge", "the cost is paid at finalization, after targets are chosen")

# Slot 0 takes their card, slot 1 takes mine, slots 2-3 are declined.
for want in (pack_trash(1, PLAIN[3]), pack_trash(0, MORBID), -1, -1):
    tg = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
    if any(a.arg == pack_trash(0, FORGE) for a in tg):
        die("forge", "the gear is still on the board while targets are chosen, "
                     "so it cannot be among the cards its own ability recycles")
    pick = next((a for a in tg if a.arg == want), None)
    if pick is None:
        die("forge", f"wanted target {want}, offered {[a.arg for a in tg]}")
    A.apply(s, T, V1, pick)

# The last slot finalizes the ability, which is when 204.1.b's cost is paid.
# The opponent's response window therefore happens over the gear's corpse.
if s.perms[forge, P_ALIVE]:
    die("forge", "204.1.b -- a 'Kill this' cost is paid at finalization, so "
                 "the gear is already dead while the ability is on the Chain")
settle(s)

if int(s.n_trash[1]) != 0 or int(s.n_deck[1]) != deck1 + 1:
    die("forge", "their card should have gone to the bottom of THEIR deck")
if int(s.deck[1, deck1]) != PLAIN[3]:
    die("forge", "416.1.a -- recycle is the BOTTOM of the deck")
if int(s.n_deck[0]) != deck0 + 1 or int(s.deck[0, deck0]) != MORBID:
    die("forge", "my card should have gone to the bottom of MY deck, not theirs")
ok("416.1.c -- each recycled card goes to its own owner's deck, not the caster's")

# The gear's own corpse is in the trash, not recycled or banished: killing is a
# cost here, but a kill is still a kill (427.2.a).
if FORGE not in [int(c) for c in s.trash[0, :int(s.n_trash[0])]]:
    die("forge", "the killed gear belongs in its controller's trash")
ok("the gear killed as a cost lands in its trash, not the Banishment")

# --- Shadows of the Past: to their OWNERS' hands ---------------------------
s = two_trashes([], [PLAIN[3]])
s.hand[0, 0] = SHADOWS
s.n_hand[0] = 1
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_PLAY))
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_TARGET
                       and a.arg == pack_trash(1, PLAIN[3])))
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_TARGET and a.arg == -1))
settle(s)
if int(s.n_hand[1]) != 1 or int(s.hand[1, 0]) != PLAIN[3]:
    die("shadows", "'to their owners' hands' means the OPPONENT gets it back, "
                   f"not the caster: their hand is {int(s.n_hand[1])}")
if int(s.n_hand[0]) != 0:
    die("shadows", "the caster must not receive an opponent's card")
ok("a unit pulled from their trash returns to THEIR hand, not the caster's")


# ---------------------------------------------------------------------------
print("\n[18] battlefield slots, and sweeps scoped to one")

from rl.engine.state import P_MIGHT_MOD

BIG = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
           and int(T.might[c]) >= 5 and not T.residual_text(c))


def bf_board(bf_ctrl=()):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = BIG
    s.runes_ready[:, :] = 8
    s.phase, s.active, s.priority = MAIN, 0, 0
    for i, who in bf_ctrl:
        s.bf_ctrl[i] = who
    return s


# A battlefield slot returns LOCATIONS, never battlefield indices -- so the ops
# that move and sweep need no idea which kind of slot named the place.
s = bf_board()
e1 = s.add_permanent(BIG, 1, bf_loc(0))
e2 = s.add_permanent(BIG, 1, bf_loc(0))
friend = s.add_permanent(BIG, 0, bf_loc(0))
far = s.add_permanent(BIG, 1, bf_loc(1))
got = rsv.legal_targets(s, T, SPECS["Crescent Strike"], 0, 0, [], -1)
if got != [bf_loc(i) for i in range(N_BF)]:
    die("bf", f"an unqualified battlefield slot should offer every one: {got}")
if base_loc(0) in got or base_loc(1) in got:
    die("bf", "a battlefield slot must never offer a base")
ok("a battlefield slot offers battlefields as LOCATIONS, and never a base")

# "an enemy unit THERE" -- a relation pointing at a battlefield slot, which
# holds a location rather than a unit row.
got = rsv.legal_targets(s, T, SPECS["Crescent Strike"], 1, 0, [bf_loc(0)], -1)
if sorted(got) != sorted([e1, e2]):
    die("bf", f"'enemy unit there' offered {got}, wanted the two at B0")
ok("REL_SAME_BF against a battlefield slot reads the LOCATION, not a unit row")

rsv.resolve(s, T, V1, SPECS["Crescent Strike"], 0, [bf_loc(0), e1], -1, True)
if int(s.perms[e1, P_DMG]) != 4:
    die("bf", f"the chosen unit takes 4, got {int(s.perms[e1, P_DMG])}")
if int(s.perms[e2, P_DMG]) != 1:
    die("bf", f"each OTHER enemy there takes 1, got {int(s.perms[e2, P_DMG])}")
if int(s.perms[friend, P_DMG]) or int(s.perms[far, P_DMG]):
    die("bf", "the sweep must spare friendly units and the other battlefield")
ok("except_target spares the chosen unit; the sweep stays on one side, one place")

# "a battlefield you control" excludes the uncontrolled and the enemy's.
s = bf_board(bf_ctrl=((0, 0), (1, 1)))
u_base = s.add_permanent(BIG, 0, base_loc(0))
u_there = s.add_permanent(BIG, 0, bf_loc(0))
if rsv.legal_targets(s, T, SPECS["Resonating Strike"], 0, 0, [], -1) != [bf_loc(0)]:
    die("bf", "'a battlefield you control' reached one you do not")
got = rsv.legal_targets(s, T, SPECS["Resonating Strike"], 1, 0, [bf_loc(0)], -1)
if got != [u_base]:
    die("bf", f"'at a different location' offered {got}, wanted only the base unit")
rsv.resolve(s, T, V1, SPECS["Resonating Strike"], 0, [bf_loc(0), u_base], -1, True)
if int(s.perms[u_base, P_LOC]) != bf_loc(0) or int(s.perms[u_base, P_MIGHT_MOD]) != 2:
    die("bf", "the unit should have moved to the battlefield and gained +2")
ok("who on a battlefield slot reads CONTROL; REL_DIFFERENT_LOC works off it")

# "where you have units" is a restriction, and the sweep runs AFTER the move,
# so a unit dragged in is caught by it.
s = bf_board()
mine0 = s.add_permanent(BIG, 0, bf_loc(0))
foe = s.add_permanent(BIG, 1, base_loc(1))
foe2 = s.add_permanent(BIG, 1, bf_loc(0))
if rsv.legal_targets(s, T, SPECS["Moonfall"], 0, 0, [], -1) != [bf_loc(0)]:
    die("bf", "'where you have units' offered a battlefield with none of yours")
rsv.resolve(s, T, V1, SPECS["Moonfall"], 0, [bf_loc(0), foe], -1, True)
if int(s.perms[foe, P_LOC]) != bf_loc(0) or int(s.perms[foe, P_MIGHT_MOD]) != -2:
    die("bf", "a unit dragged in must be caught by the sweep that follows")
if int(s.perms[foe2, P_MIGHT_MOD]) != -2 or int(s.perms[mine0, P_MIGHT_MOD]):
    die("bf", "the sweep must hit every enemy there and no friendly unit")
ok("op order matters: the dragged unit is swept because the move came first")

# 355.14 -- "up to one" keeps the card playable with nothing to drag.
s = bf_board()
s.add_permanent(BIG, 0, bf_loc(0))
alone = s.add_permanent(BIG, 1, bf_loc(0))
rsv.resolve(s, T, V1, SPECS["Moonfall"], 0, [bf_loc(0), -1], -1, True)
if int(s.perms[alone, P_MIGHT_MOD]) != -2:
    die("bf", "with the optional slot empty the Might sweep must still happen")
ok("an empty 'up to one' slot skips its op and leaves the rest of the card")


# ---------------------------------------------------------------------------
print("\n[19] [Legion]: 'if you've played another card this turn' (822)")

from rl.engine.cost import effective_energy
from rl.engine.state import F_LEGION, P_FLAGS

HOPE = T.id_of("Noxus Hopeful")
CAPT = T.id_of("Vanguard Captain")
GLORY = T.id_of("Trifarian Gloryseeker")
VANILLA = next(c for c in range(T.n) if T.is_type(c, "Unit")
               and not T.is_token(c) and not T.residual_text(c)
               and int(T.energy[c]) <= 2)


def legion_board():
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = VANILLA
    s.runes_ready[:, :] = 9
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


def play_out(s, card, loc):
    """Play a card from hand and settle everything it triggers."""
    s.hand[0, int(s.n_hand[0])] = card
    s.n_hand[0] += 1
    A.apply(s, T, V1, A.Action(A.A_PLAY, int(s.n_hand[0]) - 1))
    A.apply(s, T, V1, A.Action(A.A_PLAY_AT, loc))
    for _ in range(12):
        seat = A.acting_seat(s)
        if seat < 0:
            break
        act = next((a for a in A.legal_actions(s, T, V1, seat)
                    if a.kind in (A.A_TARGET, A.A_PASS)), None)
        if act is None:
            break
        A.apply(s, T, V1, act)


def row_of(s, card):
    return next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == card)


# The COST side reads the counter LIVE, because the card being priced has not
# been played yet -- so any nonzero count is "another card".
s = legion_board()
if effective_energy(s, T, 0, HOPE) != int(T.energy[HOPE]):
    die("legion", "the first card of a turn has no Legion, so no discount")
s.cards_played[0] = 1
if effective_energy(s, T, 0, HOPE) != int(T.energy[HOPE]) - 2:
    die("legion", "with another card played, Legion should cut 2 energy")
ok("a Legion cost discount reads the counter live: off first, on afterwards")

# The ABILITY side reads the snapshot, because by resolution the source HAS
# been counted -- reading live here would fire Legion for the first card of
# every turn, which is exactly backwards.
s = legion_board()
play_out(s, CAPT, base_loc(0))
cap = row_of(s, CAPT)
if int(s.perms[cap, P_FLAGS]) & F_LEGION:
    die("legion", "the first card played must not be flagged")
tokens = [i for i in range(s.n_perms)
          if s.perms[i, P_ALIVE] == 1 and T.is_token(int(s.perms[i, P_CARD]))]
if tokens:
    die("legion", f"un-Legioned Vanguard Captain made {len(tokens)} tokens")
ok("as the first card, a Legion ETB resolves and does nothing")

s = legion_board()
play_out(s, VANILLA, base_loc(0))
play_out(s, CAPT, base_loc(0))
if not int(s.perms[row_of(s, CAPT), P_FLAGS]) & F_LEGION:
    die("legion", "the second card played should carry the snapshot")
tokens = [i for i in range(s.n_perms)
          if s.perms[i, P_ALIVE] == 1 and T.is_token(int(s.perms[i, P_CARD]))]
if len(tokens) != 2:
    die("legion", f"Legioned Vanguard Captain made {len(tokens)} tokens, want 2")
ok("as the second card, the same ETB plays both Recruit tokens")

# The snapshot must survive the end of turn: it records what was true when the
# unit was played, unlike a Stun, which is turn-scoped.
s = legion_board()
play_out(s, VANILLA, base_loc(0))
play_out(s, GLORY, base_loc(0))
g = row_of(s, GLORY)
if combat.might(s, T, g) != int(T.might[GLORY]) + 1:
    die("legion", "a Legioned Gloryseeker should have buffed itself")
phases.end_turn(s, V1)
if not int(s.perms[row_of(s, GLORY), P_FLAGS]) & F_LEGION:
    die("legion", "F_LEGION records a past fact and must outlive the turn")
ok("the snapshot is not turn-scoped: it records how the unit was played")

# The counter itself IS turn-scoped, or Legion would be permanently on from
# turn two onward.
s = legion_board()
s.cards_played[0] = 3
phases.end_turn(s, V1)
if int(s.cards_played[0]):
    die("legion", "the played-this-turn count must reset at end of turn")
ok("...but the counter resets, so Legion is off again next turn")


# ---------------------------------------------------------------------------
print("\n[20] an amount read off another target, and a self-swap")

PLAINS = [c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
          and not T.residual_text(c)]
BIGGEST = max(PLAINS, key=lambda c: int(T.might[c]))
SMALLEST = min(PLAINS, key=lambda c: int(T.might[c]))
TIDE = T.id_of("Tideturner")


def two_friendly(a, b, loc_a=None, loc_b=None):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = SMALLEST
    s.phase, s.active, s.priority = MAIN, 0, 0
    ra = s.add_permanent(a, 0, bf_loc(0) if loc_a is None else loc_a)
    rb = s.add_permanent(b, 0, bf_loc(0) if loc_b is None else loc_b)
    return s, ra, rb


# "ANOTHER friendly unit" means a different unit, not a different location --
# the two are usually standing together, which is the whole point of the card.
s, sac, tgt = two_friendly(BIGGEST, SMALLEST)
if rsv.legal_targets(s, T, SPECS["Deathgrip"], 1, 0, [sac], -1) != [tgt]:
    die("amount", "'another friendly unit' must reach the one standing beside it")
ok("'another' excludes only the unit already chosen, not its whole location")

# The amount is read at RESOLUTION, off the sacrifice's current Might.
rsv.resolve(s, T, V1, SPECS["Deathgrip"], 0, [sac, tgt], -1, True)
want = int(T.might[SMALLEST]) + int(T.might[BIGGEST])
if combat.might(s, T, tgt) != want:
    die("amount", f"target should be {want}, got {combat.might(s, T, tgt)}")
if s.perms[sac, P_ALIVE]:
    die("amount", "the sacrificed unit should be dead")
ok("'+Might equal to its Might' reads the sacrifice, and the sacrifice dies")

# ...and it reads the CURRENT Might, so a buff on the sacrifice carries over.
# A printed-value implementation passes the case above and fails this one.
s, sac, tgt = two_friendly(BIGGEST, SMALLEST)
combat.set_might_mod(s, T, sac, 3)
rsv.resolve(s, T, V1, SPECS["Deathgrip"], 0, [sac, tgt], -1, True)
gained = combat.might(s, T, tgt) - int(T.might[SMALLEST])
if gained != int(T.might[BIGGEST]) + 3:
    die("amount", f"a +3 on the sacrifice should carry: gained {gained}")
ok("...current Might, not printed -- a buffed sacrifice is worth more")

# Tideturner swaps with a friendly unit and never with itself: "a friendly
# unit" would otherwise include the source, and a self-swap is a legal-looking
# no-op that still burns the trigger.
s, tide, other = two_friendly(TIDE, SMALLEST, loc_a=base_loc(0))
ab = ABILITIES["Tideturner"][0]
got = rsv.legal_targets(s, T, ab, 0, 0, [], -1, source=tide)
if got != [other]:
    die("swap", f"Tideturner offered {got}, wanted only the other unit")
rsv.resolve(s, T, V1, ab, 0, [other], -1, False, source=tide)
if int(s.perms[tide, P_LOC]) != bf_loc(0) or int(s.perms[other, P_LOC]) != base_loc(0):
    die("swap", "the two units should have traded places")
ok("not_self keeps a swap from targeting its own source")

# 355.8 -- alone on the board there is nothing to trade with, so the ability
# never reaches the Chain rather than resolving into nothing.
s = GameState()
s.n_deck[:] = 20
s.phase, s.active, s.priority = MAIN, 0, 0
lonely = s.add_permanent(TIDE, 0, base_loc(0))
if chain.fire(s, T, V1, TR_PLAY_ME, lonely) or s.n_chain:
    die("swap", "with no other friendly unit the trigger must not fire")
ok("...and with nobody to swap with, it never triggers at all (355.8)")


# ---------------------------------------------------------------------------
print("\n[21] granting a keyword")

VANILLA = [c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
           and not T.residual_text(c) and not list(T.unread_keywords(c))][0]


def grant_board():
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = VANILLA
    s.runes_ready[:, :] = 6
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


# [Assault 3] is CONDITIONAL Might (807.1.c), not a +3 modifier: it exists only
# while the unit is an attacker, so a granted Assault does nothing out of
# combat and nothing on defence.
s = grant_board()
atk = s.add_permanent(VANILLA, 0, bf_loc(0))
dfn = s.add_permanent(VANILLA, 1, bf_loc(0))
base = combat.might(s, T, atk)
resolve.resolve(s, T, V1, SPECS["Cleave"], 0, [atk], -1, True)
if combat.might(s, T, atk) != base:
    die("grant", "[Assault] must not raise Might outside a Combat")
combat.open_showdown(s, T, 0, attacker=0)
if combat.might(s, T, atk) != base + 3:
    die("grant", f"a granted [Assault 3] should apply while attacking, "
                 f"got {combat.might(s, T, atk)}")
if combat.might(s, T, dfn) != base:
    die("grant", "the defender must be untouched")
ok("a granted [Assault 3] is conditional Might, live only while attacking")

# Two grants from one card, and [Tank] changes damage ORDER rather than Might.
s = grant_board()
atk = s.add_permanent(VANILLA, 0, bf_loc(0))
dfn = s.add_permanent(VANILLA, 1, bf_loc(0))
other = s.add_permanent(VANILLA, 1, bf_loc(0))
resolve.resolve(s, T, V1, SPECS["Block"], 1, [dfn], -1, True)
combat.open_showdown(s, T, 0, attacker=0)
if combat.might(s, T, dfn) != base + 3:
    die("grant", "[Shield 3] should apply while defending")
tiers = combat._tiers(s, T, [other, dfn])
if tiers[0] != [dfn]:
    die("grant", f"a granted [Tank] must be assigned damage first: {tiers}")
ok("one card grants two keywords, and [Tank] reorders damage assignment")

# **The grant is not always 'this turn'.** [Temporary] kills at the start of
# its controller's next Beginning Phase, so a turn-scoped grant would expire
# before it ever fired and the card would have no drawback at all.
s = grant_board()
u = s.add_permanent(VANILLA, 0, bf_loc(0))
if resolve.legal_targets(s, T, SPECS["Shadow's Call"], 0, 0, [], -1) != [u]:
    die("grant", "a unit without [Temporary] should be a legal choice")
resolve.resolve(s, T, V1, SPECS["Shadow's Call"], 0, [u], -1, True)
if resolve.legal_targets(s, T, SPECS["Shadow's Call"], 0, 0, [], -1):
    die("grant", "'without [Temporary]' must exclude a unit already given it")
ok("lacks_keyword reads the GRANTED value, not just the printed one")

phases.end_turn(s, V1)
phases.start_turn(s, T, V1)
if s.perms[u, P_ALIVE] != 1:
    die("grant", "[Temporary] kills on its CONTROLLER's Beginning Phase, and "
                 "this was the opponent's")
phases.end_turn(s, V1)
phases.start_turn(s, T, V1)
if s.perms[u, P_ALIVE] == 1:
    die("grant", "...but it must die at the start of its own controller's turn")
ok("a granted [Temporary] survives the opponent's turn and dies on its own")

# A turn-scoped grant really does expire.
s = grant_board()
u = s.add_permanent(VANILLA, 0, bf_loc(0))
resolve.resolve(s, T, V1, SPECS["Cleave"], 0, [u], -1, True)
phases.end_turn(s, V1)
if combat.perm_kw(s, T, u, "Assault"):
    die("grant", "'this turn' grants must clear in the end-of-turn cleanup")
ok("...while a 'this turn' grant clears with the turn")

# Grants are stored PARALLEL to `perms`, and compaction renumbers rows. A grant
# left behind would silently transfer to whatever unit landed on that index.
s = grant_board()
dead = s.add_permanent(VANILLA, 0, bf_loc(0))
keep = s.add_permanent(VANILLA, 0, bf_loc(0))
resolve.resolve(s, T, V1, SPECS["Shadow's Call"], 0, [keep], -1, True)
s.perms[dead, P_ALIVE] = 0
s.compact_permanents()
moved = next(i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1)
if not combat.perm_kw(s, T, moved, "Temporary"):
    die("grant", "compaction dropped the grant from the row it moved")
if s.n_perms > 1 and combat.perm_kw(s, T, 1, "Temporary"):
    die("grant", "compaction left a stale grant behind")
ok("compaction moves grants with their rows instead of stranding them")


# ---------------------------------------------------------------------------
print("\n[22] [Ambush]: an extra destination, and conditional Reaction speed")

from rl.engine import chain as chain_mod

AMB = T.id_of("Soulspinner")            # [Ambush] and nothing else
PLAINU = [c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
          and not T.residual_text(c) and not list(T.unread_keywords(c))
          and c != AMB][0]


def amb_board(units_at_bf0=True, bf0_ctrl=-1):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAINU
    s.runes_ready[:, :] = 8
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.bf_ctrl[0] = bf0_ctrl
    if units_at_bf0:
        s.add_permanent(PLAINU, 0, bf_loc(0))
    s.hand[0, 0] = AMB
    s.n_hand[0] = 1
    return s


# 822.1.b -- "a battlefield where you CONTROL UNITS" is wider than "a
# battlefield you control": a CONTESTED battlefield with a unit of yours on it
# qualifies, and reinforcing a fight you are losing is the whole keyword.
s = amb_board(bf0_ctrl=-1)
got = A.play_destinations(s, T, V1, 0, AMB)
if bf_loc(0) not in got:
    die("ambush", f"[Ambush] should reach an uncontrolled battlefield where "
                  f"you have units: {got}")
if A.play_destinations(s, T, V1, 0, PLAINU) != [base_loc(0)]:
    die("ambush", "a unit WITHOUT [Ambush] must still be base-only here")
ok("[Ambush] adds a battlefield you have units on, controlled or not (806.3)")

# No units there, no permission -- the keyword grants nothing on its own.
s = amb_board(units_at_bf0=False)
if A.play_destinations(s, T, V1, 0, AMB) != [base_loc(0)]:
    die("ambush", "with no units at any battlefield [Ambush] adds nothing")
if A.ambush_playable(s, T, V1, 0):
    die("ambush", "...and with no destination there is no Reaction speed")
ok("with no units at a battlefield it grants neither a place nor the speed")

# The Reaction half, on the OPPONENT's turn, inside a window.
s = amb_board()
s.active, s.priority = 1, 0
chain_mod.push(s, T.id_of("Stupefy"), 1)
chain_mod.finalize(s, 0)
plays = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY]
if not plays:
    die("ambush", "an [Ambush] unit should be playable into a response window")
A.apply(s, T, V1, plays[0])
dsts = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT]
if dsts != [bf_loc(0)]:
    die("ambush", f"in a window the ONLY legal destination is the Ambush one, "
                  f"not the base: {dsts}")
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, dsts[0]))
row = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == AMB)
if int(s.perms[row, P_LOC]) != bf_loc(0) or int(s.n_hand[0]) != 0:
    die("ambush", "the unit should have left the hand and landed there")
ok("822.1.b's Reaction is CONDITIONAL: in a window, only Ambush spots are legal")


# ---------------------------------------------------------------------------
# Printed play-destination permissions (exceptions to 806.3)
#
# 806.3/813.3.a restrict a Unit to its controller's base or a Battlefield they
# already control. A handful of cards print an exception, and each one ADDS
# destinations rather than replacing them -- the base is always still legal.
# "Open" and "occupied" are card vocabulary, not defined rules terms, so the
# readings live in `effects.PLAY_PERMISSIONS` where a wrong one is visible.

RENGAR_TH = T.id_of("Rengar, Trophy Hunter")
OCEAN_DRAKE = T.id_of("Ocean Drake")
PLAIN_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                  and not T.is_token(c) and not T.has(c, "Ambush")
                  and T.names[c] not in ("Rengar, Trophy Hunter", "Ocean Drake"))


def destinations(card, enemy_bf=None):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    if enemy_bf is not None:
        s.add_permanent(PLAIN_BODY, 1, bf_loc(enemy_bf))
    return sorted(A.play_destinations(s, T, CFG, 0, card))


if destinations(RENGAR_TH) != [base_loc(0)]:
    die("perm", "with no enemy anywhere, Rengar has no extra destination")
if destinations(RENGAR_TH, 0) != sorted([base_loc(0), bf_loc(0)]):
    die("perm", "Rengar may be played where there ARE enemy units")
ok("806.3 exception -- 'a battlefield where there are enemy units'")

if destinations(OCEAN_DRAKE) != sorted([base_loc(0), bf_loc(0), bf_loc(1)]):
    die("perm", "both battlefields are open when nobody is on them")
if destinations(OCEAN_DRAKE, 0) != sorted([base_loc(0), bf_loc(1)]):
    die("perm", "a battlefield with a unit on it is no longer OPEN")
ok("...and 'an open battlefield' means one with no units at all")

if destinations(PLAIN_BODY, 0) != [base_loc(0)]:
    die("perm", "a card without a printed permission is unaffected")
ok("...while a card that prints no exception keeps the 806.3 default")

# "I can be played to a battlefield you're ATTACKING" (Rengar - Pouncing) is the
# first permission scoped to a COMBAT rather than to the board: it depends on
# holding the Attacker designation (459) at a live Showdown, so the same
# battlefield is legal or not depending purely on which side of the fight you
# are on. Outside a Showdown nobody is attacking and the card is an ordinary
# base play -- which is what stops it being a free "play anywhere".
RENGAR_P = T.id_of("Rengar - Pouncing")


def attacking_destinations(showdown_bf, attacker):
    st = GameState()
    st.phase, st.active, st.priority = MAIN, 0, 0
    st.add_permanent(PLAIN_BODY, 0, bf_loc(0))
    st.add_permanent(PLAIN_BODY, 1, bf_loc(0))
    st.showdown_bf, st.attacker = showdown_bf, attacker
    return sorted(A.play_destinations(st, T, CFG, 0, RENGAR_P))


if attacking_destinations(-1, -1) != [base_loc(0)]:
    die("perm", "outside a Showdown nothing is being attacked")
if attacking_destinations(0, 0) != sorted([base_loc(0), bf_loc(0)]):
    die("perm", "the battlefield I am ATTACKING is a legal destination")
if attacking_destinations(0, 1) != [base_loc(0)]:
    die("perm", "defending is not attacking -- the same battlefield, the "
                "other side of the fight, and it must not be offered")
ok("...and 'a battlefield you're attacking' turns on the Attacker designation")

# ---------------------------------------------------------------------------
# Printed exceptions to "units enter exhausted" (359.2.c)
#
# [Accelerate] is the exception the engine already knew. These two print their
# own, each with a different condition, so the condition is per card while the
# hook is shared.

XIN_ZHAO = T.id_of("Xin Zhao - Vigilant")
SHADOW_WATCHER = T.id_of("Shadow Watcher")
ER_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
               and not T.is_token(c))


def enters_ready(card, others_at_base=0, died_in_beginning=False):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    for _ in range(others_at_base):
        s.add_permanent(ER_BODY, 0, base_loc(0))
    if died_in_beginning:
        s.died_in_beginning[0] = 1
    s.n_hand[0] = 1
    s.hand[0, 0] = card
    s.runes_ready[0, :] = 8
    s.n_deck[0] = 10
    act = next(x for x in A.legal_actions(s, T, CFG, 0) if x.kind == A.A_PLAY)
    A.apply(s, T, CFG, act)
    A.apply(s, T, CFG, A.legal_actions(s, T, CFG, 0)[0])
    return int(s.perms[s.n_perms - 1, P_READY]) == 1


# "two or more OTHER units" -- Xin Zhao is not on the board yet when the card
# asks, so every friendly unit at the base is an "other" one. The boundary is
# the part worth checking: one is not two.
if enters_ready(XIN_ZHAO, 0) or enters_ready(XIN_ZHAO, 1):
    die("enter-ready", "fewer than two others -- Xin Zhao enters exhausted")
if not enters_ready(XIN_ZHAO, 2):
    die("enter-ready", "two others at the base is the condition")
ok("359.2.c exception -- 'two or more other units in your base'")

if enters_ready(SHADOW_WATCHER, died_in_beginning=False):
    die("enter-ready", "with no death this Beginning Phase it enters exhausted")
if not enters_ready(SHADOW_WATCHER, died_in_beginning=True):
    die("enter-ready", "a friendly death in the Beginning Phase readies it")
ok("...and a PAST-tense one, recorded when the death happened")

# ---------------------------------------------------------------------------
print("\n[17] Might restrictions on a target slot read EFFECTIVE Might")

# `combat.might` is the single read path for a permanent's Might, and a slot
# restriction is no exception: "with 3 Might or less" asks what the unit's
# Might IS. Reading `table.might` let a 2-Might body pumped to 7 stay a legal
# choice -- and because `_matches` runs again at resolution (359.3.e), it also
# meant a target pumped during the response window stayed in range.

from rl.engine import combat as _cbt
from rl.engine.effects import SPECS as _SPECS, TargetSpec as _TS, W_ANY as _WANY
from rl.engine.state import MAIN as _MAIN, base_loc as _base, bf_loc as _bf

_PLAIN = {m: next(c for c in range(T.n) if T.is_type(c, "Unit")
                  and T.might[c] == m and not T.is_token(c))
          for m in (2, 4, 6)}


def _board():
    st = GameState()
    st.phase, st.active, st.priority = _MAIN, 0, 0
    return st


st = _board()
victim = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
small = _TS(who=_WANY, at_battlefield=True, max_might=3)
if not resolve._matches(st, T, small, victim, 0, [], -1):
    die("max_might", "a 2-Might unit is within '3 Might or less'")
_cbt.set_might_mod(st, T, victim, +5)
if resolve._matches(st, T, small, victim, 0, [], -1):
    die("max_might", "pumped to 7, it is no longer '3 Might or less' -- the "
                     "restriction must read effective Might, not the corner")
ok("'3 Might or less' follows a buff out of range (combat.might, not the table)")

# Public Execution: "Choose a friendly unit. Kill an enemy unit with less
# Might than it." The bar is a unit you picked, so it moves with your board.
pe = _SPECS["Public Execution"]
st = _board()
mine = st.add_permanent(_PLAIN[4], 0, _base(0), is_unit=True)
weak = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
same = st.add_permanent(_PLAIN[4], 1, _bf(0), is_unit=True)
big = st.add_permanent(_PLAIN[6], 1, _bf(0), is_unit=True)
if not resolve._matches(st, T, pe.targets[1], weak, 0, [mine], -1):
    die("public execution", "2 is less than 4")
if resolve._matches(st, T, pe.targets[1], same, 0, [mine], -1):
    die("public execution", "'LESS Might' is strict -- equal must not qualify")
if resolve._matches(st, T, pe.targets[1], big, 0, [mine], -1):
    die("public execution", "6 is not less than 4")
ok("'less Might than it' compares against an earlier slot, strictly")

_cbt.set_might_mod(st, T, mine, +3)          # 4 -> 7
if not resolve._matches(st, T, pe.targets[1], big, 0, [mine], -1):
    die("public execution", "pumping the CHOSEN unit widens what it can kill")
ok("...and both sides of the comparison are effective Might")

# ---------------------------------------------------------------------------
print("\n[18] 'I can't be chosen by enemy spells and abilities'")

RUIN = T.id_of("Ruin Runner")
st = _board()
own = st.add_permanent(RUIN, 0, _bf(0), is_unit=True)
foe = st.add_permanent(RUIN, 1, _bf(0), is_unit=True)
bystander = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
any_unit = _TS(who=_WANY)

if resolve._matches(st, T, any_unit, foe, 0, [], -1):
    die("ruin runner", "an ENEMY Ruin Runner must not be a legal choice")
if not resolve._matches(st, T, any_unit, own, 0, [], -1):
    die("ruin runner", "'ENEMY spells' -- its own controller still targets it")
if not resolve._matches(st, T, any_unit, bystander, 0, [], -1):
    die("ruin runner", "the protection is its own, not an aura over the board")
ok("only enemy choices are refused, and only on the card itself")

# The restriction is on CHOOSING (355.10). Damage and sweeps name nobody, so
# they still land -- which is what keeps the card answerable at all.
_cbt.mark_damage(st, T, foe, 99)
_cbt.enforce_lethal(st, T)
if st.perms[foe, P_ALIVE] == 1:
    die("ruin runner", "damage does not CHOOSE, so it must still kill")
ok("...while damage, which chooses nothing, still kills it")


# ---------------------------------------------------------------------------
print("\n[23] a sweep is scoped by its location, its side, and its kin")

# "Deal 2 to all enemy units IN COMBAT" (Cannon Barrage). "In combat" is 459's
# contested battlefield -- every unit standing there is an Attacker or a
# Defender -- so the sweep is scoped to `showdown_bf` and reaches defenders
# too, which the `attacking` designation would have spared.
BARRAGE = _SPECS["Cannon Barrage"]

st = _board()
st.showdown_bf = 0
here_foe = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
here_mine = st.add_permanent(_PLAIN[2], 0, _bf(0), is_unit=True)
away_foe = st.add_permanent(_PLAIN[2], 1, _bf(1), is_unit=True)
base_foe = st.add_permanent(_PLAIN[2], 1, _base(1), is_unit=True)
resolve.resolve(st, T, CFG, BARRAGE, 0, [], -1, from_hand=True)
if int(st.perms[here_foe, P_DMG]) != 2:
    die("in combat", "the enemy at the contested battlefield took no damage")
if int(st.perms[here_mine, P_DMG]):
    die("in combat", "'enemy units' must not reach your own")
if int(st.perms[away_foe, P_DMG]) or int(st.perms[base_foe, P_DMG]):
    die("in combat", "an enemy off the contested battlefield is not in combat")
ok("'in combat' is the contested battlefield, both sides of it")

# Outside a Showdown there IS no contested battlefield, and a sweep that names
# a location it cannot find must reach nothing. Falling through to the unscoped
# branch instead would make this a board wipe -- the one answer never right.
st = _board()
st.showdown_bf = -1
foe = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
mine = st.add_permanent(_PLAIN[2], 0, _base(0), is_unit=True)
resolve.resolve(st, T, CFG, BARRAGE, 0, [], -1, from_hand=True)
if int(st.perms[foe, P_DMG]) or int(st.perms[mine, P_DMG]):
    die("in combat", "with no combat running the sweep must find no units")
ok("...and with no Showdown it hits nothing rather than everything")

# The same guard, reached the other way: an ability's `at=T_HERE` sweep whose
# source died in the response window (383.2.c.2). Renekton's "deal 2 to all
# enemy units here" has no "here" left once he is a corpse.
from rl.engine.effects import abilities_for as _abils
RENEKTON = T.id_of("Renekton, Rage Fueled")
st = _board()
st.runes_ready[0, :] = 0                       # so COND_FEW_RUNES holds
src = st.add_permanent(RENEKTON, 0, _bf(0), is_unit=True)
near = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
far = st.add_permanent(_PLAIN[2], 1, _bf(1), is_unit=True)
st.perms[src, P_ALIVE] = 0                     # answered before it resolved
resolve.resolve(st, T, CFG, _abils(T, RENEKTON)[0], 0, [], -1,
                from_hand=False, source=src)
if int(st.perms[far, P_DMG]):
    die("dead source", "a dead source's 'here' swept the whole board")
if int(st.perms[near, P_DMG]):
    die("dead source", "383.2.c.2 -- an ability may not reference a source "
                       "that has left the board")
ok("a dead source's 'here' sweeps nothing, not everything (383.2.c.2)")

# "Give your MECHS +1 Might this turn" (Danger Zone) -- a kin restriction on a
# sweep. Still not a target: no count, no choice.
DANGER = _SPECS["Danger Zone"]
MECH = next(c for c in range(T.n) if T.is_type(c, "Unit")
            and "Mech" in T.tags[c] and not T.is_token(c))
st = _board()
my_mech = st.add_permanent(MECH, 0, _base(0), is_unit=True)
my_other = st.add_permanent(_PLAIN[2], 0, _base(0), is_unit=True)
their_mech = st.add_permanent(MECH, 1, _bf(0), is_unit=True)
resolve.resolve(st, T, CFG, DANGER, 0, [], -1, from_hand=True)
if _cbt.might(st, T, my_mech) != int(T.might[MECH]) + 1:
    die("kin", "your own Mech missed the pump")
if _cbt.might(st, T, my_other) != int(T.might[_PLAIN[2]]):
    die("kin", "a non-Mech was pumped; 'your Mechs' is a kin restriction")
if _cbt.might(st, T, their_mech) != int(T.might[MECH]):
    die("kin", "'YOUR Mechs' must not reach the opponent's")
ok("'your Mechs' narrows a sweep by tag as well as by side")


# ---------------------------------------------------------------------------
print("\n[24] two slots, related by location rather than by battlefield")

# Heroic Charge: "Give a friendly unit +1 Might and [Stun] an enemy unit at ITS
# LOCATION." A base is a location too, so the relation must not require either
# unit to be standing on a battlefield.
CHARGE = _SPECS["Heroic Charge"]
st = _board()
mine_base = st.add_permanent(_PLAIN[2], 0, _base(0), is_unit=True)
foe_base = st.add_permanent(_PLAIN[2], 1, _base(0), is_unit=True)
foe_bf = st.add_permanent(_PLAIN[2], 1, _bf(0), is_unit=True)
got = resolve.legal_targets(st, T, CHARGE, 1, 0, [mine_base], -1)
if got != [foe_base]:
    die("heroic charge", f"'at its location' gave {got}, expected [{foe_base}]")
ok("'at its location' reaches a shared BASE, not only a battlefield")

print("\n\033[32mall effect tests passed\033[0m")
