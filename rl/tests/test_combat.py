"""Combat tests. Run from the repo root: python .../test_combat.py"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

import numpy as np
from rl.config import Config
from rl.engine import combat, phases, invariants
from rl.engine.cardtable import full_table
from rl.engine.effects import (TR_ACTIVATED, TR_PLAY_ME, abilities_for,
                               statics_for)
from rl.engine.state import (GameState, P_ALIVE, P_LOC, P_READY, P_DMG,
                             base_loc, bf_loc)

T = full_table()
CFG = Config()

# A fixture must be INERT in the step under test, or the test measures the
# card instead of the rule. `_COMBAT_MODIFIERS` below records the first time
# that bit -- a [Shield 2] Tank whose Might was different during combat -- and
# a scripted ABILITY is the same hazard one layer up: `PLAIN[5]` resolved to
# Ambessa, Respected and Feared, and the day her "when I attack, kill a
# smaller unit" was transcribed the combat tests started queueing a trigger
# nothing here drains.
#
# So a fixture may carry no static at all, and no ability that these tests can
# fire. TR_PLAY_ME is allowed because `put` adds a permanent directly rather
# than playing it, and TR_ACTIVATED because nothing here activates anything;
# both exclusions would leave some Might values with no card in the pool.
_INERT_TRIGGERS = (TR_PLAY_ME, TR_ACTIVATED)


def _inert(cid) -> bool:
    if statics_for(T, cid):
        return False
    return all(a.trigger in _INERT_TRIGGERS for a in abilities_for(T, cid))


# Pick real cards by might so the test exercises the actual card table.
def card_with(might, kw=None, exclude_kw=()):
    for cid in range(len(T.names)):
        if not T.is_type(cid, "Unit") or T.might[cid] != might:
            continue
        if kw and not T.has(cid, kw):
            continue
        if any(T.has(cid, k) for k in exclude_kw):
            continue
        if not _inert(cid):
            continue
        return cid
    raise LookupError(f"no unit with might={might} kw={kw}")

# [Shield] and [Assault] change Might DURING combat (814.1.c / 807.1.c), so a
# fixture carrying either has a different Might in the very step under test.
# TANK3 used to resolve to Shen - Kinkou, who has [Shield 2] and is therefore a
# 5-Might defender -- the "3 damage kills the Tank" assertion started failing
# the moment the engine stopped ignoring the keyword. The fixtures now exclude
# them so the numbers in these tests mean what they say.
_COMBAT_MODIFIERS = ("Shield", "Assault")

PLAIN = {m: card_with(m, exclude_kw=("Tank", "Backline", "Temporary")
                      + _COMBAT_MODIFIERS)
         for m in (1, 2, 3, 4, 5)}
# The smallest shieldless Tank the pool offers. No 3-Might one exists, so the
# tests below take their numbers from the card rather than hardcoding them.
TANK3 = next(cid for m in (1, 2, 3, 4, 5)
             for cid in [card_with(m, "Tank", exclude_kw=_COMBAT_MODIFIERS)
                         if any(T.is_type(c, "Unit") and T.might[c] == m
                                and T.has(c, "Tank")
                                and not any(T.has(c, k) for k in _COMBAT_MODIFIERS)
                                for c in range(len(T.names))) else None]
             if cid is not None)
TANK_M = int(T.might[TANK3])
BACK = next(cid for cid in range(len(T.names))
            if T.is_type(cid, "Unit") and T.has(cid, "Backline")
            and not any(T.has(cid, k) for k in _COMBAT_MODIFIERS))

print(f"cards: plain={ {m: T.names[c] for m, c in PLAIN.items()} }")
print(f"       tank3={T.names[TANK3]!r}  backline={T.names[BACK]!r} "
      f"({T.might[BACK]} might)")


def fresh():
    s = GameState()
    s.n_deck[:] = 10
    s.deck[:, :10] = PLAIN[1]
    return s


def put(s, card, seat, loc, ready=True):
    return s.add_permanent(card, seat, loc, ready)


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
print("\n[1] undefended battlefield -> conquer, no combat")
s = fresh()
s.active = 0
u = put(s, PLAIN[3], 0, base_loc(0))
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, u)
invariants.check(s)
log = combat.commit_declaration(s, T, CFG)
invariants.check(s)
assert s.perms[u, P_LOC] == bf_loc(0), "unit did not arrive"
assert s.perms[u, P_READY] == 0, "unit should arrive exhausted"
assert s.bf_ctrl[0] == 0, f"expected seat 0 control, got {s.bf_ctrl[0]}"
assert s.points[0] == 1, f"expected 1 conquer point, got {s.points[0]}"
assert log["scored"] == [(0, "conquer")], log
ok("moved in, took it, scored 1")

print("[1b] retaking a battlefield already scored this turn pays nothing")
s.bf_ctrl[0] = -1                      # pretend it flipped away and back
log = combat._establish_control(s, T, CFG, 0)
assert s.bf_ctrl[0] == 0 and s.points[0] == 1, (s.bf_ctrl[0], s.points[0])
assert log == [], log
ok("rule 470 cap holds")

# ---------------------------------------------------------------------------
print("\n[2] attacker wipes the garrison -> conquer")
s = fresh()
s.active = 0
atk = [put(s, PLAIN[3], 0, base_loc(0)), put(s, PLAIN[3], 0, base_loc(0))]
dfn = put(s, PLAIN[5], 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
for u in atk:
    combat.add_to_declaration(s, u)
log = combat.commit_declaration(s, T, CFG)
invariants.check(s)
assert s.perms[dfn, P_ALIVE] == 0, "defender (5 might) should die to a 6 pool"
survivors = [u for u in atk if s.perms[u, P_ALIVE] == 1]
# The 5-pool buys exactly one 3-might kill; the leftover 2 is not lethal and
# heals away (465.2.c.4), so precisely one attacker comes through.
assert len(survivors) == 1, f"expected 1 surviving attacker, got {len(survivors)}"
assert s.bf_ctrl[0] == 0 and s.points[0] == 1, (s.bf_ctrl[0], s.points[0])
assert log["result"] == "won", log
ok("6 kills the 5; the 5 buys one 3 and the spare 2 heals away")

# ---------------------------------------------------------------------------
print("\n[3] defender survives -> ATTACKERS RECALLED (466.1.a.2)")
s = fresh()
s.active = 0
atk = put(s, PLAIN[3], 0, base_loc(0))
dfn = [put(s, PLAIN[4], 1, bf_loc(0)), put(s, PLAIN[4], 1, bf_loc(0))]
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, atk)
log = combat.commit_declaration(s, T, CFG)
invariants.check(s)
assert s.perms[atk, P_ALIVE] == 0, "3-might attacker should die to an 8 pool"
assert all(s.perms[d, P_ALIVE] == 1 for d in dfn), "3 damage kills neither 4"
assert s.bf_ctrl[0] == 1 and s.points[0] == 0, (s.bf_ctrl[0], s.points[0])
ok("failed attack: attacker dead, defender keeps the field, no points")

print("[3b] surviving attacker is sent home rather than sharing the field")
s = fresh()
s.active = 0
atk = put(s, PLAIN[5], 0, base_loc(0))
dfn = [put(s, PLAIN[1], 1, bf_loc(0)), put(s, PLAIN[1], 1, bf_loc(0)),
       put(s, PLAIN[1], 1, bf_loc(0))]
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, atk)
log = combat.commit_declaration(s, T, CFG)
invariants.check(s)
alive = [d for d in dfn if s.perms[d, P_ALIVE] == 1]
assert s.perms[atk, P_ALIVE] == 1, "5 might survives 3 damage"
assert len(alive) == 0, f"5 damage should kill three 1-might units, {len(alive)} left"
assert s.bf_ctrl[0] == 0 and s.points[0] == 1
ok("5-pool spends exact lethal three times over and takes the field")

print("[3c] vanilla combat is ALWAYS decisive -- the recall is unreachable in v1")
# Both sides surviving needs the attacker pool too small to kill any defender
# AND the defender pool too small to kill every attacker, i.e. SA < SD and
# SD < SA at once. With no Shield, prevention or mid-combat arrivals that is a
# contradiction, so one side is always wiped. Property-check it.
rng = np.random.default_rng(7)
both_survived = 0
for trial in range(3000):
    s = fresh()
    s.active = 0
    na, nd = int(rng.integers(1, 4)), int(rng.integers(1, 4))
    pool = list(PLAIN.values()) + [TANK3, BACK]
    atk = [put(s, int(rng.choice(pool)), 0, base_loc(0)) for _ in range(na)]
    dfn = [put(s, int(rng.choice(pool)), 1, bf_loc(0)) for _ in range(nd)]
    s.bf_ctrl[0] = 1
    combat.declare_move(s, bf_loc(0))
    for u in atk:
        combat.add_to_declaration(s, u)
    combat.commit_declaration(s, T, CFG)
    invariants.check(s)
    a_left = any(s.perms[u, P_ALIVE] == 1 for u in atk)
    d_left = any(s.perms[u, P_ALIVE] == 1 for u in dfn)
    if a_left and d_left:
        both_survived += 1
assert both_survived == 0, f"{both_survived}/3000 combats left both sides alive"
ok("3000 randomized combats, every one wiped a side; invariants held throughout")

print("[3d] the recall path itself, forced directly")
s = fresh()
s.active = 0
a = put(s, PLAIN[3], 0, bf_loc(0))     # already there, both sides present
d = put(s, PLAIN[3], 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.open_showdown(s, T, 0, attacker=0)
log = {}
done = combat.resolution_step(s, T, CFG, 0, attacker=0, log=log)   # no damage step
assert done and log["recalled"] == [a], log
assert s.perms[a, P_LOC] == base_loc(0), "attacker was not sent home"
assert s.bf_ctrl[0] == 1 and s.points[0] == 0, "defender keeps it, attacker scores 0"
invariants.check(s)
ok("defender alive at the Resolution Step -> attacker walked home for nothing")

# ---------------------------------------------------------------------------
print("\n[4] [Tank] cannot be skipped")
s = fresh()
s.active = 0
atk = [put(s, PLAIN[TANK_M], 0, base_loc(0))]     # pool exactly lethal on it
tank = put(s, TANK3, 1, bf_loc(0))
juicy = put(s, PLAIN[1], 1, bf_loc(0))            # 1 might, would be free
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, atk[0])
combat.commit_declaration(s, T, CFG)
assert s.perms[tank, P_ALIVE] == 0, f"{TANK_M} damage must go to the Tank"
assert s.perms[juicy, P_ALIVE] == 1, "the 1-might unit is unreachable behind Tank"
ok(f"{TANK_M} damage kills the Tank, not the cheap unit behind it")

print("[4b] pool too small for the Tank kills nothing at all")
s = fresh()
s.active = 0
a = put(s, PLAIN[TANK_M - 1], 0, base_loc(0))     # one short of the Tank
tank = put(s, TANK3, 1, bf_loc(0))
soft = put(s, PLAIN[1], 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
combat.commit_declaration(s, T, CFG)
assert s.perms[tank, P_ALIVE] == 1 and s.perms[soft, P_ALIVE] == 1, "nothing dies"
assert s.perms[a, P_ALIVE] == 0, "attacker eats the defending pool"
ok(f"{TANK_M - 1} damage into Tank {TANK_M} + unit 1 destroys nothing")

print("[4c] [Backline] is reached only once everything else is dead")
s = fresh()
s.active = 0
bm = int(T.might[BACK])
pool_needed = bm + 2
a = put(s, PLAIN[min(5, pool_needed)], 0, base_loc(0))
back = put(s, BACK, 1, bf_loc(0))
front = put(s, PLAIN[2], 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
combat.commit_declaration(s, T, CFG)
if int(T.might[PLAIN[min(5, pool_needed)]]) >= pool_needed:
    assert s.perms[back, P_ALIVE] == 0 and s.perms[front, P_ALIVE] == 0
    ok(f"pool cleared the 2-might front then reached Backline ({bm} might)")
else:
    assert s.perms[back, P_ALIVE] == 1, "Backline must not be reachable first"
    ok(f"Backline ({bm} might) shielded: front unit died first")

# ---------------------------------------------------------------------------
print("\n[5] mutual annihilation -> battlefield goes uncontrolled")
s = fresh()
s.active = 0
a = put(s, PLAIN[3], 0, base_loc(0))
d = put(s, PLAIN[3], 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
log = combat.commit_declaration(s, T, CFG)
invariants.check(s)
assert s.perms[a, P_ALIVE] == 0 and s.perms[d, P_ALIVE] == 0, "both 3s trade"
assert s.bf_ctrl[0] == -1, f"expected uncontrolled, got {s.bf_ctrl[0]}"
assert s.points.tolist() == [0, 0], s.points.tolist()
ok("simultaneous damage kills both; nobody controls or scores")

# ---------------------------------------------------------------------------
print("\n[6] all damage heals board-wide after combat")
s = fresh()
s.active = 0
a = put(s, PLAIN[1], 0, base_loc(0))
d = put(s, PLAIN[5], 1, bf_loc(0))
bystander = put(s, PLAIN[4], 0, base_loc(0))
s.perms[bystander, P_DMG] = 2      # pretend residue from earlier
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
combat.commit_declaration(s, T, CFG)
assert s.perms[d, P_DMG] == 0, f"defender kept {s.perms[d, P_DMG]} damage"
assert s.perms[bystander, P_DMG] == 0, "bystander not healed -- heal must be board-wide"
invariants.check(s)
ok("1 chip damage vanished; a unit at base was healed too")

# ---------------------------------------------------------------------------
print("\n[7] movement legality")
s = fresh()
s.active = 0
gank = next((cid for cid in range(len(T.names))
             if T.is_type(cid, "Unit") and T.has(cid, "Ganking")), None)
plain = put(s, PLAIN[3], 0, bf_loc(0))
assert not combat.can_move(s, T, CFG, plain, bf_loc(1)), "lateral move without Ganking"
assert combat.can_move(s, T, CFG, plain, base_loc(0)), "retreat to base must be legal"
if gank is not None:
    g = put(s, gank, 0, bf_loc(0))
    assert combat.can_move(s, T, CFG, g, bf_loc(1)), "[Ganking] enables lateral"
    ok(f"lateral blocked; {T.names[gank]!r} with [Ganking] allowed")
exh = put(s, PLAIN[3], 0, base_loc(0), ready=False)
assert not combat.can_move(s, T, CFG, exh, bf_loc(0)), "exhausted unit moved"
s.active = 1
assert not combat.can_move(s, T, CFG, plain, base_loc(0)), "moved on opponent's turn"
ok("exhausted units and off-turn movement rejected")

# ---------------------------------------------------------------------------
print("\n[8] retreat gives up next turn's hold, not this turn's")
s = fresh()
s.active = 0
u = put(s, PLAIN[3], 0, bf_loc(0))
s.bf_ctrl[0] = 0
phases.start_turn(s, T, CFG)
assert s.points[0] == 1, f"hold should bank first, got {s.points[0]}"
combat.retreat(s, T, CFG, u)
invariants.check(s)
assert s.bf_ctrl[0] == -1, "leaving must give up control"
assert s.points[0] == 1, "the banked point must not be clawed back"
ok("held for 1, then walked away still holding the point")

# ---------------------------------------------------------------------------
print("\n[9] two showdowns at one battlefield lose to one big one")
def attack(split):
    s = fresh()
    s.active = 0
    atk = [put(s, PLAIN[3], 0, base_loc(0)), put(s, PLAIN[3], 0, base_loc(0))]
    put(s, PLAIN[5], 1, bf_loc(0))
    s.bf_ctrl[0] = 1
    if split:
        for u in atk:                      # one at a time: two showdowns
            combat.declare_move(s, bf_loc(0))
            combat.add_to_declaration(s, u)
            combat.commit_declaration(s, T, CFG)
    else:
        combat.declare_move(s, bf_loc(0))
        for u in atk:
            combat.add_to_declaration(s, u)
        combat.commit_declaration(s, T, CFG)
    return s

together, apart = attack(False), attack(True)
assert together.bf_ctrl[0] == 0, "3+3 at once should beat a 5"
assert apart.bf_ctrl[0] == 1, "3 then 3 should lose to a 5 twice"
assert int(apart.perms[:apart.n_perms, P_ALIVE].sum()) == 1, "both attackers fed in"
ok("6 in one wave takes it; 3+3 in two waves loses both units for nothing")

# ---------------------------------------------------------------------------
print("\n[10] determinism and clone independence")
s = fresh()
s.active = 0
a = put(s, PLAIN[3], 0, base_loc(0))
put(s, PLAIN[2], 1, bf_loc(0))
snapshot = s.clone()
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
combat.commit_declaration(s, T, CFG)
h1 = s.state_hash()

s2 = snapshot.clone()
combat.declare_move(s2, bf_loc(0))
combat.add_to_declaration(s2, a)
combat.commit_declaration(s2, T, CFG)
assert s2.state_hash() == h1, "same input, different result"
assert snapshot.perms[a, P_LOC] == base_loc(0), "clone was mutated by the original"
ok("identical hashes from a cloned position; the snapshot is untouched")

# ---------------------------------------------------------------------------
print("\n[11] [Stun] breaks the symmetry -- the owner's 5-into-9 scenario")
BIG = next(cid for cid in range(len(T.names))
           if T.is_type(cid, "Unit") and T.might[cid] == 9
           and not any(T.has(cid, k) for k in ("Tank", "Backline", "Temporary"))
           and _inert(cid))
s = fresh()
s.active = 0
a = put(s, PLAIN[5], 0, base_loc(0))
d = put(s, BIG, 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
assert s.stun(d), "stun should apply"
assert not s.stun(d), "423.1.a.1 -- a stunned unit cannot be stunned again"
assert combat.might_for_pool(s, T, d) == 0, "423.1.b -- stunned adds 0 to the pool"
assert combat.lethal_cost(s, T, d) == 9, "423.1.c -- still needs FULL might to die"
log = combat.commit_declaration(s, T, CFG)
invariants.check(s)
assert s.perms[a, P_ALIVE] == 1, "attacker took 0 damage from the stunned unit"
assert s.perms[d, P_ALIVE] == 1, "5 damage is not lethal to a 9"
assert s.perms[a, P_LOC] == base_loc(0), "defender lived -> attacker must be Recalled"
assert s.bf_ctrl[0] == 1 and s.points[0] == 0, "no conquer"
assert log["recalled"] == [a], log
ok(f"5 into a stunned 9 ({T.names[BIG]!r}): both live, attacker walks home, 0 points")

print("[11b] Stun wears off at the end of the turn it was applied (423.1.a.2)")
assert s.has_flag(d, 1), "still stunned during this turn"
phases.end_turn(s, CFG)
assert not s.has_flag(d, 1), "stun must clear at end of turn"
assert combat.might_for_pool(s, T, d) == 9, "and the unit hits again next turn"
ok("one-turn window, not a lasting debuff")

print("[11c] assignment is only a decision when you cannot wipe them")
s = fresh()
big = put(s, PLAIN[4], 1, bf_loc(0))
small = put(s, PLAIN[2], 1, bf_loc(0))
assert not combat.assignment_is_a_choice(s, T, 6, [big, small]), "6 wipes both -- forced"
assert combat.assignment_is_a_choice(s, T, 5, [big, small]), "5 must pick one -- a choice"
ok("gate for exposing assignment to the policy behaves as specified")


print("[12] the Final Point (471.1.b) demands the whole board")
CFG8 = Config().at_victory_score(8)


def at_score(points, scored):
    s = fresh()
    s.points[0] = points
    for j, v in enumerate(scored):
        s.bf_scored[0, j] = v
    put(s, PLAIN[2], 0, bf_loc(0))
    return s


# 7 points, conquering B1 having NOT scored B2 -> no point, draw a card instead.
s = at_score(7, [0, 0])
hand = int(s.n_hand[0])
log = combat._establish_control(s, T, CFG8, 0)
assert int(s.points[0]) == 7, "the Final Point must not land without the board"
assert int(s.n_hand[0]) == hand + 1, "471.1.b -- they draw a card instead"
assert log == [(0, "final_point_denied")], log
ok("at 7, a lone Conquer scores nothing and draws instead")

# Same, but B2 was already Scored this turn -> the Final Point lands.
s = at_score(7, [0, 1])
combat._establish_control(s, T, CFG8, 0)
assert int(s.points[0]) == 8 and s.winner == 0, "every battlefield scored -> win"
ok("at 7 with the other battlefield already Scored, the Final Point lands")

# Below the threshold the restriction does not apply at all.
s = at_score(3, [0, 0])
combat._establish_control(s, T, CFG8, 0)
assert int(s.points[0]) == 4, "only the FINAL point is restricted"
ok("below 1-from-victory, Conquer is unrestricted")

# 471.1.a.1 -- Hold is exempt, so it can take the Final Point alone.
s = fresh()
s.points[0] = 7
s.bf_ctrl[0] = 0
put(s, PLAIN[2], 0, bf_loc(0))
s.active = 0
phases.score_holds(s, CFG8)
assert int(s.points[0]) == 8, "471.1.a.1 -- non-Conquer sources are exempt"
ok("Hold is exempt and can take the Final Point on its own")

# ---------------------------------------------------------------------------
print("\n[9] a trigger that fires for a unit other than its own source")

from rl.engine import chain as chain_mod
from dataclasses import replace as _replace
from rl.engine.state import C_FINAL, MAIN, P_MIGHT_MOD

# Triggers do not fire under `units_only` -- that is what keeps v0
# bit-identical -- so this section needs the v1 config.
CFG_V1 = _replace(Config(), units_only=False)

MASK = T.id_of("Mask of Foresight")
MASK_UNIT = next(c for c in range(T.n) if T.is_type(c, "Unit")
                 and not T.is_token(c) and not T.residual_text(c)
                 and int(T.might[c]) >= 3)


def mask_board(n_friendly, mask_seat=0):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = MASK_UNIT
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.add_permanent(MASK, mask_seat, base_loc(mask_seat))   # gear, at a BASE
    rows = [s.add_permanent(MASK_UNIT, 0, bf_loc(0)) for _ in range(n_friendly)]
    foe = s.add_permanent(MASK_UNIT, 1, bf_loc(0))
    return s, rows, foe


def drain(s):
    """Place every queued trigger, finalize it, and resolve the chain."""
    while s.n_trig:
        chain_mod.place(s, T, CFG_V1, 0)
    for i in range(int(s.n_chain)):
        s.chain[i, C_FINAL] = 1
    while s.n_chain:
        chain_mod.resolve_top(s, T, CFG_V1)


# The gear sits at a base and watches a battlefield, so the ability's SOURCE
# and its SUBJECT are different permanents -- the first trigger in the pool for
# which C_SRC could not do both jobs.
s, rows, _ = mask_board(1)
combat.open_showdown(s, T, 0, attacker=0)
drain(s)
if int(s.perms[rows[0], P_MIGHT_MOD]) != 1:
    die("mask", f"a lone attacker should get +1, got "
                f"{int(s.perms[rows[0], P_MIGHT_MOD])}")
ok("a trigger fires for another permanent, and the effect finds it (T_SUBJECT)")

# 740.2.a -- "alone" is a LOCATION predicate, not a count of attackers. A
# second friendly unit standing there breaks it for BOTH of them.
s, rows, _ = mask_board(2)
combat.open_showdown(s, T, 0, attacker=0)
drain(s)
if any(int(s.perms[r, P_MIGHT_MOD]) for r in rows):
    die("mask", "with two friendly units at the battlefield neither is alone")
ok("740.2.a -- a second friendly unit there means nobody attacked alone")

# "attacks OR DEFENDS alone": the same gear works on defence, and never for
# the opponent's units.
s, rows, foe = mask_board(1, mask_seat=1)
combat.open_showdown(s, T, 0, attacker=0)
drain(s)
if int(s.perms[foe, P_MIGHT_MOD]) != 1:
    die("mask", "a lone DEFENDER should get +1 too")
if int(s.perms[rows[0], P_MIGHT_MOD]):
    die("mask", "the enemy attacker must not be buffed by their opponent's gear")
ok("...and it reads 'attacks or defends', on the controller's units only")


# ---------------------------------------------------------------------------
print("\n[10] killing a corpse mints a card")

# A pseudo-slot is not a target, so 359.3.e never re-checks it: the unit a
# trigger fired FOR can die during the priority window before the ability
# resolves. `_destroy` then ran a second time on the same row and appended its
# card to the trash again -- a card created from nothing.
#
# Caught by the per-seat card-conservation gate at victory 8, on a real deck.
# Victory 3 never reached it: the games are too short.
s = fresh()
u = s.add_permanent(MASK_UNIT, 0, bf_loc(0))
combat._destroy(s, T, u)
if int(s.n_trash[0]) != 1:
    die("corpse", "a first death puts exactly one card in the trash")
combat._destroy(s, T, u)
if int(s.n_trash[0]) != 1:
    die("corpse", f"destroying an already-dead permanent must do nothing, "
                  f"trash is now {int(s.n_trash[0])}")
ok("_destroy is idempotent: a corpse cannot die twice into the trash")

# The same guard on the Might path, which is how it was actually reached: a
# buff aimed at a dead subject reported a kill and re-destroyed it.
s = fresh()
u = s.add_permanent(MASK_UNIT, 0, bf_loc(0))
s.perms[u, P_DMG] = 99
combat._destroy(s, T, u)
if combat.set_might_mod(s, T, u, 1):
    die("corpse", "modifying a dead permanent's Might must not report a kill")
if int(s.n_trash[0]) != 1:
    die("corpse", "...and must not trash its card a second time")
ok("a Might change on a dead permanent is a no-op, not a second death")


# ---------------------------------------------------------------------------
# [10] "When I attack" is not "when I attack or defend" (459)
#
# Both readings used to collapse into one trigger, and `open_showdown` applied
# Mask of Foresight's "...alone" clause to every card that used it. These check
# the three axes that were merged: which SIDE triggers, WHOSE attack it watches,
# and whether "here" means the source's battlefield or any of them.

ANIVIA = T.id_of("Anivia - Primal")


def anivia_board(attacker_seat):
    """Anivia and an enemy at bf0; a second enemy parked at bf1."""
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = MASK_UNIT
    s.phase, s.active, s.priority = MAIN, 0, 0
    an = s.add_permanent(ANIVIA, 0, bf_loc(0))
    near = s.add_permanent(MASK_UNIT, 1, bf_loc(0))
    far = s.add_permanent(MASK_UNIT, 1, bf_loc(1))
    friend = s.add_permanent(MASK_UNIT, 0, bf_loc(0))
    combat.open_showdown(s, T, 0, attacker=attacker_seat)
    drain(s)
    return s, an, near, far, friend


s, an, near, far, friend = anivia_board(attacker_seat=0)
if int(s.perms[near, P_DMG]) != 3:
    die("attack-only", f"an attacking Anivia deals 3 to the enemy here, got "
                       f"{int(s.perms[near, P_DMG])}")
ok("ROLE_ATTACK fires when its controller is the Attacker")

if int(s.perms[far, P_DMG]):
    die("here", "'here' is the source's battlefield -- bf1 must be untouched")
ok("same_loc_as_source/at=T_HERE confines a sweep to the source's location")

if int(s.perms[friend, P_DMG]):
    die("who", "'all ENEMY units here' must spare the controller's own unit")
ok("...and who=W_ENEMY spares friendly units standing there")

# The same board with the opponent attacking: Anivia now DEFENDS, and a card
# that says "When I attack" says nothing about that.
s, an, near, far, friend = anivia_board(attacker_seat=1)
if int(s.perms[near, P_DMG]):
    die("attack-only", "'When I attack' must not fire while defending")
ok("459 -- ROLE_ATTACK is silent on defence")

# ---------------------------------------------------------------------------
# [11] A Combat in progress is resumed, not re-initiated (461)
#
# `staged_combat` reads presence, which stays true for the whole Combat. The
# Cleanup that follows an emptied Chain would find the same two units and open
# the Showdown again, re-queueing every attack/defend trigger with it. That is
# a livelock: the pass that should advance the Combat restarts it instead.
# Caught in training as episodes of 1500 decisions inside 3 turns, with a
# Mask of Foresight unit at +1270 Might.

s, rows, _ = mask_board(1)
combat.open_showdown(s, T, 0, attacker=0)
drain(s)
first = int(s.perms[rows[0], P_MIGHT_MOD])
if first != 1:
    die("resume", f"expected +1 from the first trigger, got {first}")

# The Chain is empty and a Showdown is live -- exactly the state the A_PASS
# branch reaches before it calls a Cleanup.
if int(s.showdown_bf) < 0:
    die("resume", "the fixture should still be in a Showdown")
combat.cleanup(s, T, CFG_V1, mover=0, dst=-1)
if int(s.n_trig):
    die("resume", f"the Cleanup re-opened the Showdown and queued "
                  f"{int(s.n_trig)} more trigger(s)")
drain(s)
if int(s.perms[rows[0], P_MIGHT_MOD]) != first:
    die("resume", f"Might grew from +{first} to "
                  f"+{int(s.perms[rows[0], P_MIGHT_MOD])} without a new Combat")
ok("461 -- a Cleanup during a live Showdown does not re-initiate the Combat")

# ---------------------------------------------------------------------------
# [12] Zhonya's Hourglass -- a delayed replacement on death
#
# "The next time a friendly unit would die, kill this instead. Recall that unit
# exhausted." It replaces the DEATH, not its cause -- and it does NOT heal,
# where Guardian Angel's effect text explicitly says "Heal me" (136.2.d). So it
# answers targeted removal and does almost nothing against damage, which is the
# difference the two cards are priced on.

from rl.engine import resolve as _rsv
from rl.engine.effects import ABILITIES as _AB
from rl.engine.state import P_READY as _P_READY, P_DMG as _P_DMG

ZHONYA = T.id_of("Zhonya's Hourglass")
VICTIM = next(c for c in range(T.n) if T.is_type(c, "Unit")
              and not T.is_token(c) and int(T.might[c]) >= 4)


def guarded():
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    g = s.add_permanent(ZHONYA, 0, base_loc(0))
    u = s.add_permanent(VICTIM, 0, bf_loc(0))
    _rsv.resolve(s, T, CFG_V1, _AB["Zhonya's Hourglass"][0], 0, [], -1, True,
                 source=g)
    return s, g, u


s, g, u = guarded()
combat.destroy(s, T, u)
if s.perms[u, P_ALIVE] != 1:
    die("zhonya", "a kill effect must be replaced, not applied")
if int(s.perms[u, P_LOC]) != base_loc(0) or int(s.perms[u, _P_READY]) != 0:
    die("zhonya", "455/456 -- the unit is Recalled to base, exhausted")
if s.perms[g, P_ALIVE] != 0:
    die("zhonya", "the Hourglass is killed instead")
ok("455 -- a death replacement recalls the unit and kills the guard instead")

combat.destroy(s, T, u)
if s.perms[u, P_ALIVE] != 0:
    die("zhonya", "'the NEXT time' is one-shot -- a second death goes through")
ok("...and it is consumed, so the next death is not replaced")

# **Damage is the case the errata changed.** The PRINTED text is "Recall that
# unit exhausted" with no heal, and read that way the replacement replaces the
# death and not its cause: the marked damage survives, 143.2.a is a continuous
# check, and the unit dies again on the spot. `data/errata.json` supersedes it
# with "Heal that unit, exhaust it, and recall it", so the damage goes and the
# unit genuinely survives a lethal hit -- which turns Zhonya's from an answer
# to targeted removal into an answer to damage as well.
if "Heal that unit" not in T.raw_text[ZHONYA]:
    die("zhonya", "this test reads the ERRATA text; if the overlay stopped "
                  "being applied, `cardtable._raw_cards` is the place to look")
s, g, u = guarded()
combat.mark_damage(s, T, u, int(T.might[VICTIM]))
if s.perms[u, P_ALIVE] != 1:
    die("zhonya", "the replacement should fire on lethal damage too")
if int(s.perms[u, _P_DMG]) != 0:
    die("zhonya", "the errata heals the unit, so no damage stays marked")
combat.enforce_lethal(s, T)
if s.perms[u, P_ALIVE] != 1:
    die("zhonya", "healed, the unit must survive 143.2.a's next check")
ok("...and the errata's heal makes it answer damage, not just removal")

print("\n\033[32mall combat tests passed\033[0m")
