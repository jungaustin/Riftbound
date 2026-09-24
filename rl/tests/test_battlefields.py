"""Battlefield tests -- the ground is a card too.

Run: python3 rl/tests/test_battlefields.py

A battlefield is not a permanent: it has no row, no controller of its own and
cannot die (107.3). What it does have is a LOCATION, and everything printed on
one is about the units standing there, the player who holds it, or the rules of
the game itself. Those three shapes are the three sections here:

  [1] Triggers -- queued through `combat._queue_bf_trigger`, which carries the
      seat the trigger fired FOR, and fire ONCE for the player where a unit's
      version fires once per unit.
  [2] Statics and granted abilities -- reaching the units standing on it.
  [3] Rules changes -- costs, scoring and the Victory Score, which no static
      scope can express and which live in their own registries.
"""
import sys
from dataclasses import replace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.config import Config
from rl.engine import actions as A
from rl.engine import chain, combat, phases
from rl.engine import resolve as rsv
from rl.engine.cardtable import full_table
from rl.engine.effects import SPECS
from rl.engine.state import (MAIN, P_ALIVE, P_CARD, P_CTRL, P_DMG, P_LOC,
                             P_READY, GameState, base_loc, bf_loc, fd_slots)

T = full_table()
V1 = replace(Config().at_victory_score(8), units_only=False)
VANILLA = next(c for c in range(T.n) if T.names[c] == "Shipyard Skulker")


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def fresh(bf=None, seat=0, runes=6, hand=()):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = VANILLA
    for j, c in enumerate(hand):
        s.hand[seat, j] = c
    s.n_hand[seat] = len(hand)
    s.runes_ready[:, :] = runes
    s.phase, s.active, s.priority = MAIN, seat, seat
    if bf is not None:
        s.bf_card[0] = T.id_of(bf)
    return s


def body(s, seat, loc, ready=False):
    return s.add_permanent(VANILLA, seat, loc, ready=ready)


def drain(s, limit=40):
    for _ in range(limit):
        A._settle(s, T, V1)
        if s.n_chain == 0 and s.n_trig == 0 and not chain.decision_open(s) \
                and s.pend_slot < 0 and s.pend_may < 0:
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            return
        pick = next((a for a in legal if a.kind == A.A_ORDER),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)


def hold(s, seat=0, i=0):
    """`seat` holds battlefield `i` and everything it queued resolves."""
    s.bf_ctrl[i] = seat
    phases.score_holds(s, V1, T)
    drain(s)


# ---------------------------------------------------------------------------
print("[1] triggers on the ground: once for the player, wherever it fires")

s = fresh("Altar to Unity")
body(s, 0, bf_loc(0))
body(s, 0, bf_loc(0))                       # two units, ONE trigger
hold(s)
recruits = [i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
            and "Recruit" in T.names[int(s.perms[i, P_CARD])]]
if len(recruits) != 1:
    die("altar to unity", f"one token for the player, got {len(recruits)}")
ok("a hold trigger on the ground fires once, not once per unit")

s = fresh("Sigil of the Storm")
body(s, 0, bf_loc(0))
before = int(s.runes_ready[0].sum() + s.runes_spent[0].sum())
hold(s)                                     # holding is not conquering
if int(s.runes_ready[0].sum() + s.runes_spent[0].sum()) != before:
    die("sigil", "the cost is on CONQUER, not on hold")
s2 = fresh("Sigil of the Storm")
s2.bf_ctrl[0] = -1
mover = body(s2, 0, base_loc(0), ready=True)
before2 = int(s2.runes_ready[0].sum() + s2.runes_spent[0].sum())
A.apply(s2, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
A.apply(s2, T, V1, A.Action(A.A_ADD, mover))
A.apply(s2, T, V1, A.Action(A.A_COMMIT))
drain(s2)
if int(s2.runes_ready[0].sum() + s2.runes_spent[0].sum()) != before2 - 1:
    die("sigil", "conquering here costs a rune off the board")
ok("Sigil of the Storm charges its rune, and only on a conquer")

# The Grand Plaza: "if you have 7+ units here, you win the game."
s = fresh("The Grand Plaza")
for _ in range(6):
    body(s, 0, bf_loc(0))
hold(s)
if s.winner >= 0:
    die("grand plaza", "six units is not seven")
s = fresh("The Grand Plaza")
for _ in range(7):
    body(s, 0, bf_loc(0))
hold(s)
if s.winner != 0:
    die("grand plaza", f"seven units here wins, got winner={s.winner}")
ok("The Grand Plaza counts the garrison and ends the game at seven")

# Abandoned Hall fires for WHOEVER played the spell.
SPELL = next(c for c in range(T.n) if T.is_type(c, "Spell")
             and int(T.energy[c]) <= 2 and int(T.power[c]) == 0
             and T.names[c] in SPECS and not SPECS[T.names[c]].targets)
s = fresh("Abandoned Hall", hand=[SPELL])
mine = body(s, 0, bf_loc(0))
base_might = combat.might(s, T, mine)
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A._settle(s, T, V1)
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACCEPT]:
    die("abandoned hall", "419.4.a -- nothing triggers until the spell resolves")
for _ in range(4):                      # both pass: the spell resolves
    offer = [a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
             if a.kind == A.A_ACCEPT]
    if offer:
        break
    A.apply(s, T, V1, A.PASS)
if not offer:
    die("abandoned hall", "playing a spell should offer the +1 (383.3.a)")
A.apply(s, T, V1, offer[0])
tgt = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if not tgt:
    die("abandoned hall", "...and then ask which unit gets it")
A.apply(s, T, V1, next(a for a in tgt if a.arg == mine))
drain(s)
if combat.might(s, T, mine) != base_might + 1:
    die("abandoned hall", "+1 Might this turn to a unit you control here")
ok("Abandoned Hall answers the player who played the spell")

# Back-Alley Bar: "when a unit moves FROM here".
s = fresh("Back-Alley Bar")
s.bf_ctrl[0] = 0
mover = body(s, 0, bf_loc(0), ready=True)
was = combat.might(s, T, mover)
A.apply(s, T, V1, A.Action(A.A_RETREAT, mover))
drain(s)
if int(s.perms[mover, P_LOC]) != base_loc(0):
    die("back-alley bar", "the unit went home")
if combat.might(s, T, mover) != was + 1:
    die("back-alley bar", f"+1 Might for leaving, got "
                          f"{combat.might(s, T, mover)}")
ok("Back-Alley Bar pays the unit that leaves it")

# Frozen Fortress: 1 damage to each unit here at the start of a turn.
# Two states rather than one board: a friendly and an enemy unit at the same
# battlefield would stage a Combat in the Cleanup that follows this trigger,
# and Combat Cleanup heals the board (461.1.a.1) -- the damage is real, it just
# does not survive the fight it starts.
s = fresh("Frozen Fortress")
mine = body(s, 0, bf_loc(0))
away = body(s, 0, base_loc(0))
elsewhere = body(s, 0, bf_loc(1))
phases.start_turn(s, T, V1)
drain(s)
if int(s.perms[mine, P_DMG]) != 1:
    die("frozen fortress", f"a unit here takes 1, got "
                           f"{int(s.perms[mine, P_DMG])}")
if int(s.perms[away, P_DMG]) or int(s.perms[elsewhere, P_DMG]):
    die("frozen fortress", "...and nothing at a base or another battlefield")

s2 = fresh("Frozen Fortress")               # the turn player's own Beginning
theirs = body(s2, 1, bf_loc(0))             # ...reaches the ENEMY garrison too
phases.start_turn(s2, T, V1)
drain(s2)
if int(s2.perms[theirs, P_DMG]) != 1:
    die("frozen fortress", "'each unit here' is not 'each of your units here'")
ok("Frozen Fortress damages the whole garrison each Beginning Phase")

# ---------------------------------------------------------------------------
print("\n[2] statics and granted abilities reach the units standing there")

s = fresh("Vilemaw's Lair")
s.bf_ctrl[0] = 0
stuck = body(s, 0, bf_loc(0), ready=True)
if combat.cant_move_to_base(s, T, stuck) is not True:
    die("vilemaw's lair", "units here cannot go home")
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_RETREAT]:
    die("vilemaw's lair", "...so no retreat is offered")
ok("Vilemaw's Lair keeps what walks onto it")

# Brush: +1 Might for its five tags and nothing else (Ivern's token).
s = fresh("Brush")
plain = body(s, 0, bf_loc(0))
if combat.might(s, T, plain) != int(T.might[VANILLA]):
    die("brush", "a Pirate is none of the five tags")
PORO = next(c for c in range(T.n) if T.is_type(c, "Unit")
            and "Poro" in T.tags[c] and not T.is_token(c))
poro = s.add_permanent(PORO, 0, bf_loc(0))
if combat.might(s, T, poro) != int(T.might[PORO]) + 1:
    die("brush", f"a Poro here is +1, got {combat.might(s, T, poro)}")
ok("Brush grows exactly the five tags it names")

# Gardens of Becoming: "units here have 'Exhaust: Gain 1 XP.'"
s = fresh("Gardens of Becoming")
s.bf_ctrl[0] = 0
u = body(s, 0, bf_loc(0), ready=True)
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("gardens", "the ground gives every unit standing on it an ability")
A.apply(s, T, V1, acts[0])
drain(s)
if int(s.xp[0]) != 1 or int(s.perms[u, P_READY]):
    die("gardens", f"exhaust for 1 XP: xp={int(s.xp[0])}")
away = body(s, 0, base_loc(0), ready=True)
if len([a for a in A.legal_actions(s, T, V1, 0)
        if a.kind == A.A_ACTIVATE]) != 0:
    die("gardens", "a unit at a base was never given the ability")
ok("Gardens of Becoming lends its ability to the garrison only")

# ---------------------------------------------------------------------------
print("\n[3] rules the ground changes: costs, scoring, the Victory Score")

# Ornn's Forge: the first friendly non-token gear each turn costs 1 less.
GEAR = next(c for c in range(T.n) if T.is_type(c, "Gear")
            and not T.is_token(c) and int(T.energy[c]) >= 2)
from rl.engine.cost import effective_energy, note_bf_first_use
s = fresh("Ornn's Forge")
s.bf_ctrl[0] = 1                            # theirs first
if effective_energy(s, T, 0, GEAR) != int(T.energy[GEAR]):
    die("ornn's forge", "'while YOU control this battlefield'")
s.bf_ctrl[0] = 0
if effective_energy(s, T, 0, GEAR) != int(T.energy[GEAR]) - 1:
    die("ornn's forge", "the first gear is 1 cheaper")
note_bf_first_use(s, T, 0, GEAR, False)     # ...as playing one spends it
if effective_energy(s, T, 0, GEAR) != int(T.energy[GEAR]):
    die("ornn's forge", "the second gear this turn is full price")
ok("Ornn's Forge discounts one gear a turn, for its controller")

# Mystic Vortex: [Reaction] cards cost {any rune} more during showdowns here.
REACT = next(c for c in range(T.n) if T.is_type(c, "Spell")
             and T.has(c, "Reaction") and T.names[c] in SPECS)
from rl.engine.cost import effective_power
s = fresh("Mystic Vortex")
base_p = int(T.power[REACT])
if effective_power(s, T, 0, REACT) != base_p:
    die("mystic vortex", "outside a showdown it taxes nothing")
s.showdown_bf, s.showdown_combat = 0, 1
if effective_power(s, T, 0, REACT) != base_p + 1:
    die("mystic vortex", "a Reaction costs {any rune} more in a showdown here")
if effective_power(s, T, 0, SPELL) != int(T.power[SPELL]):
    die("mystic vortex", "...and a Main-phase spell is untaxed")
ok("Mystic Vortex taxes Reactions inside its own showdown")

# Aspirant's Climb: the Victory Score itself moves.
from rl.engine import game as game_mod
s = fresh()
s.victory_bonus = 1
s.points[0] = 8
if s.check_winner(8) != -1:
    die("aspirant's climb", "8 points is not enough at 9")
s.points[0] = 9
if s.check_winner(8) != 0:
    die("aspirant's climb", "9 is")
ok("Aspirant's Climb raises the points needed to win")

# Forgotten Monument: nobody scores here until their third turn.
s = fresh("Forgotten Monument")
body(s, 0, bf_loc(0))
s.turn = 0
hold(s)
if int(s.points[0]):
    die("forgotten monument", "no points on turn 1")
s2 = fresh("Forgotten Monument")
body(s2, 0, bf_loc(0))
s2.turn = 2                                 # the third turn
hold(s2)
if not int(s2.points[0]):
    die("forgotten monument", "...and points from the third turn on")
ok("Forgotten Monument locks scoring for the first two turns")

# ---------------------------------------------------------------------------
print("\n[4] the three that needed a mechanic of their own")

# Dragon Roost: "any player may pay {any rune}{any rune} as an additional cost
# to play a Dragon. If they do, they play it to this battlefield."
DRAGON = next(c for c in range(T.n) if "Dragon" in T.tags[c]
              and T.is_type(c, "Unit") and not T.is_token(c)
              and int(T.energy[c]) <= 4)
PLAIN = next(c for c in range(T.n) if T.is_type(c, "Unit")
             and "Dragon" not in T.tags[c] and not T.is_token(c)
             and int(T.energy[c]) <= 3)
s = fresh("Dragon Roost", hand=[DRAGON], runes=8)
s.bf_ctrl[0] = 1                            # THEIRS -- "any player" may pay
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
dests = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT]
if bf_loc(0) not in dests:
    die("dragon roost", f"the ground sells its own location: {dests}")
runes0 = int(s.runes_ready[0].sum() + s.runes_spent[0].sum())
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, bf_loc(0)))
drake = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == DRAGON)
if int(s.perms[drake, P_LOC]) != bf_loc(0):
    die("dragon roost", "...and the Dragon lands there")
paid = runes0 - int(s.runes_ready[0].sum() + s.runes_spent[0].sum())
if paid != int(T.power[DRAGON]) + 2:
    die("dragon roost", f"its own Power plus the ground's two: paid {paid}")
s2 = fresh("Dragon Roost", hand=[PLAIN], runes=8)
s2.bf_ctrl[0] = 1
A.apply(s2, T, V1, A.Action(A.A_PLAY, 0))
if bf_loc(0) in [a.arg for a in A.legal_actions(s2, T, V1, 0)
                 if a.kind == A.A_PLAY_AT]:
    die("dragon roost", "a non-Dragon is not sold the destination")
ok(f"Dragon Roost sells its ground to either player's Dragons")

# Bandle Tree: "you may hide an additional card here."
HIDDEN = next(c for c in range(T.n) if T.has(c, "Hidden") and T.names[c] in SPECS)


def hides_at(bf):
    s = fresh(bf, runes=9)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0))                   # hold it, or 190.4.c takes it back
    s.hand[0, :3] = HIDDEN
    s.n_hand[0] = 3
    n = 0
    for _ in range(4):
        acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE]
        if not acts:
            break
        A.apply(s, T, V1, acts[0])
        spots = [a for a in A.legal_actions(s, T, V1, 0)
                 if a.kind == A.A_HIDE_AT]
        if not spots:
            s.pend_hide = -1
            break
        A.apply(s, T, V1, spots[0])
        n += 1
    return s, n


s, n = hides_at("Bandle Tree")
if n != 2:
    die("bandle tree", f"107.3.f's one card, plus its additional one: {n}")
plain, n1 = hides_at("Seat of Power")
if n1 != 1:
    die("bandle tree", f"every other battlefield still holds exactly one: {n1}")
# ...and both come back out: `hidden_playable` names SLOTS, not battlefields.
for k in fd_slots(0):
    s.fd_ply[k] = -5                        # hidden last turn, so they are live
live = chain.hidden_playable(s, T, V1, 0)
if sorted(live) != sorted(fd_slots(0)):
    die("bandle tree", f"both hidden cards are playable: {live}")
ok("Bandle Tree holds two facedown cards, and both play back out")

# Altar of Blood: "if a unit here would die during combat, its controller may
# pay {any rune}{any rune}{any rune} to heal it, exhaust it, and recall it."
def altar_combat(answer):
    s = fresh("Altar of Blood", runes=6)
    s.bf_ctrl[0] = 1
    dfn = body(s, 1, bf_loc(0))
    atk = body(s, 0, base_loc(0), ready=True)
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    A.apply(s, T, V1, A.Action(A.A_ADD, atk))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    if int(s.pend_altar) != dfn:
        die("altar of blood", "the death stops and its controller is asked")
    if A.acting_seat(s) != 1:
        die("altar of blood", "...asked of the unit's CONTROLLER")
    kinds = {a.kind for a in A.legal_actions(s, T, V1, 1)}
    if kinds != {A.A_ACCEPT, A.A_DECLINE}:
        die("altar of blood", f"a yes/no and nothing else: {kinds}")
    A.apply(s, T, V1, A.Action(answer))
    drain(s)
    return s, dfn


s, dfn = altar_combat(A.A_ACCEPT)
if s.perms[dfn, P_ALIVE] != 1:
    die("altar of blood", "paying replaces the death (136.2.d)")
if int(s.perms[dfn, P_LOC]) != base_loc(1) or int(s.perms[dfn, P_READY]):
    die("altar of blood", "healed, EXHAUSTED and recalled")
if int(s.perms[dfn, P_DMG]):
    die("altar of blood", "...healed means healed")
if int(s.runes_ready[1].sum() + s.runes_spent[1].sum()) != 6 * 6 - 3:
    die("altar of blood", "three runes recycled for it")
if int(s.n_trash[1]):
    die("altar of blood", "nothing died, so nothing reached a trash")

s, dfn = altar_combat(A.A_DECLINE)
if s.perms[dfn, P_ALIVE] == 1:
    die("altar of blood", "declining lets the death happen")
if int(s.runes_ready[1].sum() + s.runes_spent[1].sum()) != 6 * 6:
    die("altar of blood", "...and costs nothing")
ok("Altar of Blood buys a death back, or does not")

print("\n\033[32mall battlefield tests passed\033[0m")
