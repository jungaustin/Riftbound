"""Chain / FEPR tests (rules 332-340).

Run: python3 rl/tests/test_chain.py

The claim under test, stated by the project owner and confirmed at 340.4:
*there is a chance to react after each spell on the chain resolves, so you can
react to something from five spells ago once the ones above it resolve.*

  [1] Ordering -- oldest finalizes (337.1.b), newest resolves (340.1).
  [2] One item per priority round, and priority reopens after each resolution.
  [3] Five deep: an item buried under four others is still respondable, and the
      responses interleave in the right order.
  [4] Priority routing after a resolution (340.2 / 340.2.a / 340.4).
  [5] Targets are stored per item and survive other items resolving.
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from dataclasses import replace

from rl.config import Config
from rl.engine import phases
from rl.engine import chain
from rl.engine.cardtable import full_table
from rl.engine.state import (C_CARD, C_UID, F_STUNNED, P_FLAGS,
                             GameState, bf_loc)

T = full_table()
CFG = Config().with_solved_damage()
CFG_V1 = replace(Config().with_solved_damage(), units_only=False)

BACK_OFF = T.id_of("Back Off")


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def unit(might):
    for c in range(T.n):
        if (T.is_type(c, "Unit") and T.might[c] == might
                and not any(T.has(c, k) for k in ("Tank", "Backline"))):
            return c
    raise LookupError(might)


U2 = unit(2)


def fresh():
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = U2
    return s


# ---------------------------------------------------------------------------
print("\n[1] oldest finalizes, newest resolves")
s = fresh()
a = chain.push(s, BACK_OFF, 0)
b = chain.push(s, BACK_OFF, 1)
c = chain.push(s, BACK_OFF, 0)
assert chain.oldest_pending(s) == a, "337.1.b -- the OLDEST pending finalizes"
chain.finalize(s, a)
assert chain.oldest_pending(s) == b
chain.finalize(s, b)
chain.finalize(s, c)
assert chain.newest_finalized(s) == c, "340.1 -- the NEWEST finalized resolves"
ok("oldest finalizes first, newest resolves first -- opposite ends")


# ---------------------------------------------------------------------------
print("\n[2] one item resolves per priority round")
s = fresh()
v = s.add_permanent(U2, 1, bf_loc(0))
for seat in (0, 1, 0):
    i = chain.push(s, BACK_OFF, seat)
    chain.set_target(s, i, 0, v)
    chain.finalize(s, i)
assert s.n_chain == 3

chain.resolve_top(s, T, CFG)
if s.n_chain != 2:
    die("chain", f"{3 - s.n_chain} items resolved at once; 340.1 says one")
ok("resolving takes exactly one item off the chain, not the whole stack")

chain.after_resolution(s)
if s.passes != 0:
    die("chain", "the pass count must reset so a new window really opens")
ok("the pass count resets, so a fresh priority window opens (340.4)")


# ---------------------------------------------------------------------------
print("\n[3] five deep: an item buried under four is still respondable")
s = fresh()
victim = s.add_permanent(unit(5), 1, bf_loc(0))

# Seat 0 plays the bottom item, then four more pile on top of it.
bottom = chain.push(s, BACK_OFF, 0)
chain.set_target(s, bottom, 0, victim)
chain.finalize(s, bottom)
for k in range(4):
    i = chain.push(s, BACK_OFF, (k + 1) % 2)
    chain.set_target(s, i, 0, victim)
    chain.finalize(s, i)
assert s.n_chain == 5

# Resolve the four on top, one at a time. After each, a window opens and the
# bottom item is still sitting there un-resolved and still respondable.
windows = 0
for expected_left in (4, 3, 2, 1):
    chain.resolve_top(s, T, CFG)
    chain.after_resolution(s)
    if s.n_chain != expected_left:
        die("five-deep", f"expected {expected_left} left, got {s.n_chain}")
    if s.n_chain:
        windows += 1
        # A response added now goes ON TOP of the still-pending bottom item.
        if chain.newest_finalized(s) == bottom and s.n_chain > 1:
            die("five-deep", "the bottom item resolved out of order")
if windows != 4:
    die("five-deep", f"{windows} priority windows opened, expected 4")
assert s.n_chain == 1 and int(s.chain[0, C_CARD]) == BACK_OFF
ok("4 priority windows opened above it; the bottom item is still on the chain")

# And a response played into that last window resolves BEFORE the bottom item.
late = chain.push(s, BACK_OFF, 1)
chain.set_target(s, late, 0, victim)
chain.finalize(s, late)
assert chain.newest_finalized(s) == late, "a late response must resolve first"
chain.resolve_top(s, T, CFG)
assert s.n_chain == 1, "the late response resolved, the original still waits"
ok("a response added five items later still resolves before the original")


# ---------------------------------------------------------------------------
print("\n[4] priority routing after a resolution")
s = fresh()
v = s.add_permanent(U2, 1, bf_loc(0))
s.active = 0
i0 = chain.push(s, BACK_OFF, 0); chain.set_target(s, i0, 0, v); chain.finalize(s, i0)
i1 = chain.push(s, BACK_OFF, 1); chain.set_target(s, i1, 0, v); chain.finalize(s, i1)
chain.resolve_top(s, T, CFG)          # i1 resolves
chain.after_resolution(s)
if int(s.priority) != 0:
    die("priority", f"340.4: controller of the newest item (seat 0) should hold "
                    f"priority, got {int(s.priority)}")
ok("340.4 -- after a resolution, the newest item's controller gains priority")

chain.resolve_top(s, T, CFG)          # i0 resolves; chain now empty
chain.after_resolution(s)
if s.n_chain or int(s.priority) != 0:
    die("priority", f"340.2: outside a showdown the turn player acts again")
ok("340.2 -- an empty chain outside a showdown returns priority to the turn player")

s.showdown_bf, s.focus = 0, 0
i = chain.push(s, BACK_OFF, 0); chain.set_target(s, i, 0, v); chain.finalize(s, i)
chain.resolve_top(s, T, CFG)
chain.after_resolution(s)
if int(s.focus) != 1:
    die("priority", "340.2.a -- focus must pass when the chain empties in a showdown")
ok("340.2.a -- focus passes when the chain empties during a showdown")


# ---------------------------------------------------------------------------
print("\n[5] each item keeps its own targets")
s = fresh()
x = s.add_permanent(unit(4), 1, bf_loc(0))
y = s.add_permanent(unit(3), 1, bf_loc(1))
ix = chain.push(s, BACK_OFF, 0); chain.set_target(s, ix, 0, x); chain.finalize(s, ix)
iy = chain.push(s, BACK_OFF, 0); chain.set_target(s, iy, 0, y); chain.finalize(s, iy)

chain.resolve_top(s, T, CFG)                     # iy resolves -> stuns y
if not (s.perms[y, P_FLAGS] & F_STUNNED):
    die("targets", "the newest item did not stun its own target")
if s.perms[x, P_FLAGS] & F_STUNNED:
    die("targets", "resolving one item stunned the other item's target")
ok("the newest item stunned y and left x alone")

chain.resolve_top(s, T, CFG)                     # ix resolves -> stuns x
if not (s.perms[x, P_FLAGS] & F_STUNNED):
    die("targets", "the remaining item lost its target when the other resolved")
ok("the surviving item kept its own target through the other's resolution")


# ---------------------------------------------------------------------------
print("\n[6] countering: uids are stable, and a counter beats what it answers")
from rl.engine import resolve as rsv
from rl.engine.effects import SPECS, TK_SPELL
from rl.engine.state import C_UID

LULLABY, DEFY = SPECS["Lilting Lullaby"], SPECS["Defy"]
BIG = T.id_of("Lilting Lullaby")        # 2E 2P -- too expensive for Defy

s = fresh()
v = s.add_permanent(U2, 1, bf_loc(0))
a = chain.push(s, BACK_OFF, 0); chain.set_target(s, a, 0, v); chain.finalize(s, a)
b = chain.push(s, BACK_OFF, 1); chain.set_target(s, b, 0, v); chain.finalize(s, b)
uid_a = int(s.chain[a, C_UID])

# The newest item is excluded (a spell cannot counter itself); the older is fair
# game.
c = chain.push(s, T.id_of("Lilting Lullaby"), 1)
opts = rsv.legal_targets(s, T, LULLABY, 0, 1, [], -1)
if int(s.chain[c, C_UID]) in opts:
    die("counter", "a spell was offered as a target for itself")
if uid_a not in opts:
    die("counter", f"an older finalized item should be counterable: {opts}")
ok("a counterspell may target older chain items but never itself")

# **The OFFER, with the counter not yet on the Chain.** Every check above
# queries targets with the counter already pushed, which is why this went
# unnoticed: `_spell_targets` also skipped the newest item, and at offer time
# the newest item is the spell being answered. Against a single spell -- the
# ordinary case -- no counterspell in the pool was ever offered.
s_offer = fresh()
v_offer = s_offer.add_permanent(U2, 1, bf_loc(0))
lone = chain.push(s_offer, BACK_OFF, 1)
chain.set_target(s_offer, lone, 0, v_offer)
chain.finalize(s_offer, lone)
s_offer.active, s_offer.priority = 1, 0
s_offer.hand[0, 0] = BIG
s_offer.n_hand[0] = 1
s_offer.runes_ready[0, :] = 4
if not chain.playable_hand_indices(s_offer, T, CFG_V1, 0):
    die("counter", "a counterspell must be offered against a LONE spell on the "
                   "Chain -- the newest item is the spell being answered")
ok("...and it is offered against a lone spell, before it is itself pushed")

# Uids survive other items resolving -- the whole reason they exist.
chain.set_target(s, c, 0, uid_a)
chain.finalize(s, c)
before_idx = chain.index_of_uid(s, uid_a)
chain.resolve_top(s, T, CFG)            # the Lullaby resolves, countering a
if chain.index_of_uid(s, uid_a) >= 0:
    die("counter", "the targeted item was not removed from the chain")
if not s.no_spells[0]:
    die("counter", "'its controller can't play spells this turn' did not apply")
ok("countering removes the targeted item and restricts its controller")

# The restriction is turn-scoped and blocks that seat from playing spells.
assert not chain.playable_hand_indices(s, T, CFG_V1, 0), \
    "a restricted seat must not be offered spells"
# This fixture built the chain by hand and left items on it. A real turn never
# ends that way -- `legal_actions` only offers A_END_TURN in a Neutral Open
# State -- and `compact_permanents` asserts as much, so clear it first.
s.n_chain = 0
phases.end_turn(s, CFG_V1)
if s.no_spells[0]:
    die("counter", "the restriction must clear at end of turn")
ok("the restriction blocks spells, then expires at end of turn")

# Defy's printed cost limit is a target RESTRICTION, not a condition.
s = fresh()
cheap = chain.push(s, BACK_OFF, 0); chain.finalize(s, cheap)      # 3E, 0P
pricey = chain.push(s, BIG, 0); chain.finalize(s, pricey)         # 2E, 2P
_ = chain.push(s, T.id_of("Defy"), 1)
opts = rsv.legal_targets(s, T, DEFY, 0, 1, [], -1)
if int(s.chain[pricey, C_UID]) in opts:
    die("counter", "Defy targeted a spell costing more than {any rune}")
if int(s.chain[cheap, C_UID]) not in opts:
    die("counter", f"Defy should reach a 3E 0P spell: {opts}")
ok("Defy's cost limit narrows the legal targets (a restriction, not a condition)")

# --- countering an ABILITY moves no card anywhere -------------------------
# 151.2.a.1: an activated ability behaves "like a spell without an associated
# card", and a triggered ability is the same (383.3). Its source is a permanent
# that is still on the board, or already dead and in the trash -- either way,
# removing the ability from the Chain must not put anything in a zone.
#
# This trashed the SOURCE'S card a second time, minting a duplicate out of
# nothing. Caught by the fuzz gate's per-seat card conservation, not by any
# rules test: a phantom copy in a trash is indistinguishable from a card that
# was legitimately trashed, right up until Fizz or Forge of the Future names a
# copy the game never had.
s = fresh()
src = s.add_permanent(T.id_of("Watchful Sentry"), 1, bf_loc(0))
s.trash[1, 0] = T.id_of("Watchful Sentry")     # its card, already dead
s.n_trash[1] = 1
item = chain.push(s, T.id_of("Watchful Sentry"), 1, abil=0, src=src)
chain.finalize(s, item)
before = (int(s.n_trash[1]), int(s.n_banished[1]))
name = chain.counter(s, T, int(s.chain[item, C_UID]))
if name is None or s.n_chain:
    die("counter", "the ability should have left the Chain")
if (int(s.n_trash[1]), int(s.n_banished[1])) != before:
    die("counter", f"countering an ability moved a card: trash/banish "
                   f"{before} -> {(int(s.n_trash[1]), int(s.n_banished[1]))}")
ok("countering an ABILITY moves no card -- an ability has no card to move")

# ...while countering a real spell still trashes it, which is the whole point
# of the distinction.
s = fresh()
item = chain.push(s, BACK_OFF, 1)
chain.finalize(s, item)
chain.counter(s, T, int(s.chain[item, C_UID]))
if int(s.n_trash[1]) != 1 or int(s.trash[1, 0]) != BACK_OFF:
    die("counter", "a countered SPELL was played, so it still goes to the trash")
ok("...but a countered spell still reaches the trash: it was played (349)")


# --- "Counter a spell" means a SPELL --------------------------------------
# Unlike Magic, a unit is not a spell here. 337.2 resolves a unit immediately
# at finalization, so it never becomes a Chain Item and there is nothing for a
# counterspell to point at -- you answer a unit by killing it, not by
# countering it. Abilities DO sit on the Chain (383.3), which is the case that
# actually needed fixing: "Counter a spell" was reaching them.
from rl.engine.effects import (SPECS, TK_SPELL, W_ANY, W_ENEMY,
                               CardSpec, TargetSpec)
from rl.engine.state import C_ABIL

s = fresh()
spell = chain.push(s, BACK_OFF, 1)
chain.finalize(s, spell)
src = s.add_permanent(T.id_of("Watchful Sentry"), 1, bf_loc(0))
abil = chain.push(s, T.id_of("Watchful Sentry"), 1, abil=0, src=src)
chain.finalize(s, abil)
_ = chain.push(s, T.id_of("Defy"), 0)          # the newest item: the counter

opts = rsv.legal_targets(s, T, SPECS["Wind Wall"], 0, 0, [], -1)
if int(s.chain[abil, C_UID]) in opts:
    die("counter", "'Counter a spell' must not reach an ABILITY on the Chain")
if int(s.chain[spell, C_UID]) not in opts:
    die("counter", f"...but it must still reach the spell: {opts}")
ok("'Counter a spell' reaches spells only, never abilities (383.3)")

# "Counter an enemy spell or ability" -- both halves opted into explicitly.
both = CardSpec(speed=SPECS["Wind Wall"].speed,
                targets=(TargetSpec(kind=TK_SPELL, who=W_ENEMY,
                                    chain_abilities=True),),
                ops=SPECS["Wind Wall"].ops)
opts = rsv.legal_targets(s, T, both, 0, 0, [], -1)
if int(s.chain[abil, C_UID]) not in opts:
    die("counter", "'spell or ability' must reach the ability")
ok("...and 'spell or ability' reaches both, because those cards say so")

# `who` on a chain slot: an "enemy spell" slot cannot answer your own.
s = fresh()
own = chain.push(s, BACK_OFF, 0)
chain.finalize(s, own)
_ = chain.push(s, T.id_of("Defy"), 0)
enemy_only = CardSpec(speed=SPECS["Wind Wall"].speed,
                      targets=(TargetSpec(kind=TK_SPELL, who=W_ENEMY),),
                      ops=SPECS["Wind Wall"].ops)
if rsv.legal_targets(s, T, enemy_only, 0, 0, [], -1):
    die("counter", "an 'enemy spell' slot reached the caster's own spell")
if not rsv.legal_targets(s, T, SPECS["Wind Wall"], 0, 0, [], -1):
    die("counter", "a plain 'a spell' slot may answer your own spell")
ok("who narrows a chain slot: 'an enemy spell' vs the unqualified 'a spell'")


# ---------------------------------------------------------------------------
# [6] A required target that disappears AFTER the trigger was placed.
#
# 355.8 is enforced at placement -- `chain.fire` will not push an ability with
# no legal target -- and that used to be the only check, so an ability whose
# target was legal when it triggered and gone by the time it resolved left its
# controller with an empty action list. `acting_seat` still named them, so the
# game stopped dead rather than fizzling.
#
# Found by the v1 fuzz on seed 565: Yuumi ("when I attack or defend, give one
# of your OTHER units HERE +3 Might") triggered on defence beside Overzealous
# Fan, which then paid its own optional cost by killing itself. Placed last,
# Yuumi resolved first (383.3.d) -- alone at her battlefield, with a required
# slot and nothing legal to put in it.
from rl.engine import actions as _A
from rl.engine import combat as _combat
from rl.engine.effects import TR_ATTACK_OR_DEFEND

_yuumi = T.id_of("Yuumi - Magical Cat")


def _defending(*rows):
    """A Combat at battlefield 0 with seat 0 defending, holding `rows`."""
    st = fresh()
    st.showdown_bf = 0
    st.attacker = 1
    out = [st.add_permanent(c, 0, bf_loc(0)) for c in rows]
    return st, out


# Fired with a legal target present, so 355.8 lets it onto the Chain...
_s, (_yr, _mate) = _defending(_yuumi, T.id_of("First Mate"))
if not chain.fire(_s, T, CFG_V1, TR_ATTACK_OR_DEFEND, _yr):
    die("fizzle", "Yuumi's trigger did not fire beside a legal target, so "
                  "this tests nothing")
# A trigger reaches the Chain without anyone acting, so something has to
# finalize it -- that is what opens the target slot (359.3.b).
_A._advance_pending(_s, T, CFG_V1)
if int(_s.pend_slot) < 0:
    die("fizzle", "no target slot opened; the fixture is wrong")
_args = {a.arg for a in _A.legal_actions(_s, T, CFG_V1, 0)
         if a.kind == _A.A_TARGET}
if _mate not in _args:
    die("fizzle", "the legal target at the same battlefield was not offered")
if -1 in _args:
    die("fizzle", "the skip was offered alongside a legal target, so a "
                  "required slot could be declined")
ok("a required slot offers its legal targets and no skip")

# ...and then the target leaves, exactly as Overzealous Fan did by killing
# itself to pay its own cost, while the ability is still waiting to resolve.
_combat.destroy(_s, T, _mate)
_legal = _A.legal_actions(_s, T, CFG_V1, 0)
if not _legal:
    die("fizzle", "a required slot whose only target died left the controller "
                  "with no action at all -- the game deadlocks here")
if [a for a in _legal if a.kind == _A.A_TARGET and a.arg != -1]:
    die("fizzle", "a dead permanent was still offered as a target")
ok("...and once it dies the slot fizzles instead of deadlocking")


print("\n\033[32mall chain tests passed\033[0m")
