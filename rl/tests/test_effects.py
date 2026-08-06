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
from rl.engine.effects import (LOC_BOUND, LOC_FREE, OP_DRAW, OP_STUN,
                               OP_SWAP_LOC, SPECS, spec_for)
from rl.engine.state import (P_ALIVE, P_LOC, GameState, base_loc, bf_loc)

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


PLAIN = {m: unit(m) for m in (2, 3)}
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

print("\n\033[32mall effect tests passed\033[0m")
