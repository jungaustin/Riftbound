"""Combat tests. Run from the repo root: python .../test_combat.py"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

import numpy as np
from rl.config import Config
from rl.engine import combat, phases, invariants
from rl.engine.cardtable import full_table
from rl.engine.state import (GameState, P_ALIVE, P_LOC, P_READY, P_DMG,
                             base_loc, bf_loc)

T = full_table()
CFG = Config()

# Pick real cards by might so the test exercises the actual card table.
def card_with(might, kw=None, exclude_kw=()):
    for cid in range(len(T.names)):
        if not T.is_type(cid, "Unit") or T.might[cid] != might:
            continue
        if kw and not T.has(cid, kw):
            continue
        if any(T.has(cid, k) for k in exclude_kw):
            continue
        return cid
    raise LookupError(f"no unit with might={might} kw={kw}")

PLAIN = {m: card_with(m, exclude_kw=("Tank", "Backline", "Temporary"))
         for m in (1, 2, 3, 4, 5)}
TANK3 = card_with(3, "Tank")
BACK = next(cid for cid in range(len(T.names))
            if T.is_type(cid, "Unit") and T.has(cid, "Backline"))

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
combat.open_showdown(s, 0, attacker=0)
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
atk = [put(s, PLAIN[3], 0, base_loc(0))]          # pool 3
tank = put(s, TANK3, 1, bf_loc(0))                # 3 might, Tank
juicy = put(s, PLAIN[1], 1, bf_loc(0))            # 1 might, would be free
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, atk[0])
combat.commit_declaration(s, T, CFG)
assert s.perms[tank, P_ALIVE] == 0, "3 damage must go to the Tank"
assert s.perms[juicy, P_ALIVE] == 1, "the 1-might unit is unreachable behind Tank"
ok("3 damage kills the Tank, not the cheap unit behind it")

print("[4b] pool too small for the Tank kills nothing at all")
s = fresh()
s.active = 0
a = put(s, PLAIN[2], 0, base_loc(0))
tank = put(s, TANK3, 1, bf_loc(0))
soft = put(s, PLAIN[1], 1, bf_loc(0))
s.bf_ctrl[0] = 1
combat.declare_move(s, bf_loc(0))
combat.add_to_declaration(s, a)
combat.commit_declaration(s, T, CFG)
assert s.perms[tank, P_ALIVE] == 1 and s.perms[soft, P_ALIVE] == 1, "nothing dies"
assert s.perms[a, P_ALIVE] == 0, "attacker eats 4 might"
ok("2 damage into Tank 3 + unit 1 destroys nothing")

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
           and not any(T.has(cid, k) for k in ("Tank", "Backline", "Temporary")))
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

print("\n\033[32mall combat tests passed\033[0m")
