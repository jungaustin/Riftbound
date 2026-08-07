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
TEMP = unit(2, "Temporary", exclude=())


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
if s.perms[foe, P_ALIVE] == 1:
    die("move", "a 2-Might unit charmed into a 5-Might garrison should die")
ok("Charm drags an enemy into your garrison and combat resolves (461)")

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

print("\n\033[32mall effect tests passed\033[0m")
