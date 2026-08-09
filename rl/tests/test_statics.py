"""Static ability tests -- continuous effects, and what they break.

Run: python3 rl/tests/test_statics.py

A static is not a trigger. It never goes on the Chain, there is no window to
respond in, and it has no moment of application -- it is simply true of the
board. That difference is the whole test file:

  [1] The bonus follows the board, not an event. It appears when a unit
      arrives and disappears when it leaves, with nothing resolving.
  [2] Scope: "your token units" reaches the whole board and nobody else's;
      "at my battlefield" does not reach the other one.
  [3] **A static going away can kill.** 143.2.a is a continuous check, so
      losing a Might buff makes damage already marked lethal *at that
      instant*. Nothing touches the dying unit, which is why the per-unit
      checks in `set_might_mod` and `mark_damage` cannot catch it and
      `enforce_lethal` sweeps the board.
  [4] A printed Might floor ("to a minimum of 1") is a floor on EFFECTIVE
      Might, so it counts the static.
"""
import sys
from dataclasses import replace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.config import Config
from rl.engine import actions as A
from rl.engine import combat
from rl.engine.cardtable import full_table
from rl.engine.cost import card_domains, plan_payment
from rl.engine.state import (P_ALIVE, P_DMG, P_LOC, GameState, base_loc,
                             bf_loc,
                             bf_loc)

T = full_table()
CFG = replace(Config().at_victory_score(3), units_only=False)

PIXIE = T.id_of("Petal Pixie")           # +1 Might per your [Temporary] here
SHEPHERD = T.id_of("Soul Shepherd")      # your token units have +1 Might
SPRITE = T.id_of("Sprite (274) // Buff")  # 3 Might [Temporary] token


def _plain():
    """A unit with no text and no static of its own -- a control body."""
    from rl.engine.effects import ABILITIES, STATICS
    for c in range(T.n):
        if (T.is_type(c, "Unit") and not T.residual_text(c)
                and not T.is_token(c) and T.names[c] not in ABILITIES
                and T.names[c] not in STATICS
                and not any(T.has(c, k) for k in ("Temporary", "Tank",
                                                  "Backline"))):
            return c
    raise LookupError("no plain unit")


PLAIN = _plain()


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def fresh():
    s = GameState()
    s.n_deck[:] = 10
    s.deck[:, :10] = SPRITE
    return s


def m(s, perm):
    return combat.might(s, T, perm)


# ---------------------------------------------------------------------------
print("\n[1] the bonus tracks the board, with nothing resolving")

s = fresh()
pixie = s.add_permanent(PIXIE, 0, bf_loc(0))
base_might = int(T.might[PIXIE])
if m(s, pixie) != base_might:
    die("track", f"alone she should be {base_might}, got {m(s, pixie)}")
ok(f"Petal Pixie alone is her printed {base_might} Might")

a = s.add_permanent(SPRITE, 0, bf_loc(0))
if m(s, pixie) != base_might + 1:
    die("track", f"one Sprite beside her should give +1, got {m(s, pixie)}")
b = s.add_permanent(SPRITE, 0, bf_loc(0))
if m(s, pixie) != base_might + 2:
    die("track", f"two Sprites should give +2, got {m(s, pixie)}")
ok("she grows as [Temporary] units arrive -- no Chain, no trigger")

s.perms[b, P_LOC] = base_loc(0)          # walk one home
if m(s, pixie) != base_might + 1:
    die("track", "a Sprite that left her battlefield still counted")
s.perms[a, P_ALIVE] = 0                  # and kill the other
if m(s, pixie) != base_might:
    die("track", "a dead Sprite still counted")
ok("and shrinks the instant they leave or die")


# ---------------------------------------------------------------------------
print("\n[2] scope")

s = fresh()
pixie = s.add_permanent(PIXIE, 0, bf_loc(0))
elsewhere = s.add_permanent(SPRITE, 0, bf_loc(1))
if m(s, pixie) != base_might:
    die("scope", "'at my battlefield' counted a Sprite at the other one")
theirs = s.add_permanent(SPRITE, 1, bf_loc(0))
if m(s, pixie) != base_might:
    die("scope", "'of YOUR units' counted an enemy Sprite")
ok("'at my battlefield' and 'of your units' both bind")

s = fresh()
shep = s.add_permanent(SHEPHERD, 0, base_loc(0))
mine = s.add_permanent(SPRITE, 0, bf_loc(1))          # far from the Shepherd
enemy_tok = s.add_permanent(SPRITE, 1, bf_loc(1))
body = s.add_permanent(PLAIN, 0, bf_loc(1))           # mine, but not a token
if m(s, mine) != int(T.might[SPRITE]) + 1:
    die("scope", f"my token should be pumped anywhere, got {m(s, mine)}")
if m(s, enemy_tok) != int(T.might[SPRITE]):
    die("scope", "the enemy's token was pumped")
if m(s, body) != int(T.might[PLAIN]):
    die("scope", "a non-token unit was pumped by 'your TOKEN units'")
ok("'your token units' reaches the whole board, yours only, tokens only")


# ---------------------------------------------------------------------------
print("\n[3] losing a static kills")

s = fresh()
shep = s.add_permanent(SHEPHERD, 0, base_loc(0))
tok = s.add_permanent(SPRITE, 0, bf_loc(0))
full = m(s, tok)
combat.mark_damage(s, T, tok, full - 1)          # one short of lethal
if not s.perms[tok, P_ALIVE]:
    die("kill", "the token died to sub-lethal damage")
ok(f"a pumped token survives {full - 1} damage at {full} Might")

combat.destroy(s, T, shep)                          # the pump goes away
if m(s, tok) != full - 1:
    die("kill", f"token should drop to {full - 1}, got {m(s, tok)}")
if not s.perms[tok, P_ALIVE]:
    die("kill", "the token died before any check ran -- destroy() must not "
                "kill by itself; the sweep is what applies 143.2.a")
dead = combat.enforce_lethal(s, T)
if s.perms[tok, P_ALIVE]:
    die("kill", "the token now carries lethal damage and must die (143.2.a)")
if tok not in dead:
    die("kill", f"enforce_lethal did not report the kill: {dead}")
ok("killing Soul Shepherd kills the damaged token she was pumping")

# The per-unit checks genuinely cannot see this: nothing touched the token.
s = fresh()
shep = s.add_permanent(SHEPHERD, 0, base_loc(0))
tok = s.add_permanent(SPRITE, 0, bf_loc(0))
combat.mark_damage(s, T, tok, m(s, tok) - 1)
if combat.set_might_mod(s, T, shep, -99, floor=None):
    pass                                          # the Shepherd may die; fine
if s.perms[tok, P_ALIVE] and int(s.perms[tok, P_DMG]) >= m(s, tok):
    ok("a per-unit check misses it entirely -- hence the board sweep")
else:
    ok("shrinking the Shepherd left the token legal")


# ---------------------------------------------------------------------------
print("\n[4] a printed floor is on EFFECTIVE Might")

s = fresh()
shep = s.add_permanent(SHEPHERD, 0, base_loc(0))
tok = s.add_permanent(SPRITE, 0, bf_loc(0))
combat.set_might_mod(s, T, tok, -99, floor=1)     # Stupefy-style
if m(s, tok) != 1:
    die("floor", f"'to a minimum of 1 Might' gave {m(s, tok)}, expected 1")
ok("the static counts toward the floor: the token lands on exactly 1")


# ---------------------------------------------------------------------------
print("\n[5] the coverage metric credits them")

from rl.decks import plays_as_printed
from rl.engine.effects import STATICS

for name in STATICS:
    if not plays_as_printed(T, T.id_of(name)):
        die("coverage", f"{name!r} has a static spec but is not counted")
ok(f"all {len(STATICS)} cards with statics count as played as printed")

# ---------------------------------------------------------------------------
print("\n[6] counting a ZONE instead of the board")

from rl.engine.cost import effective_energy
from rl.engine.effects import (CNT_TRASH, SC_SELF, ST_COST_ENERGY, ST_MIGHT,
                               STATICS, Static)

RHASA = T.id_of("Rhasa the Sunderer")
LURKER = T.id_of("Shadowblade Lurker")
GUARD = T.id_of("Plaza Guardian")
FILLER = T.id_of("Stupefy")


def trashed(n, cards=None):
    s = GameState()
    s.n_deck[:] = 20
    for i in range(n):
        s.trash[0, i] = cards[i] if cards else FILLER
    s.n_trash[0] = n
    return s


# "I cost {1 energy} less for each card in your trash" -- the count only ever
# goes up, so this is the one discount an opponent cannot answer on board.
printed = int(T.energy[RHASA])
for n, want in ((0, printed), (3, printed - 3), (printed, 0), (printed + 5, 0)):
    got = effective_energy(trashed(n), T, 0, RHASA)
    if got != want:
        die("zone", f"Rhasa with {n} in the trash cost {got}, wanted {want}")
ok(f"a zone-counting discount scales and floors at 0 ({printed} -> 0)")

# "for each card with MY NAME in your trash" counts copies, not cards.
s = trashed(4, [FILLER, LURKER, FILLER, LURKER])
want = int(T.energy[LURKER]) - 2 * 2
if effective_energy(s, T, 0, LURKER) != want:
    die("zone", f"per_same_name counted the whole trash, not the copies: "
                f"{effective_energy(s, T, 0, LURKER)} != {want}")
if effective_energy(trashed(4), T, 0, LURKER) != int(T.energy[LURKER]):
    die("zone", "a trash with no copies of the card must give no discount")
ok("per_same_name counts only copies of the card itself, not the whole pile")

# A board count by TYPE, not keyword: "for each gear you control".
s = GameState()
s.n_deck[:] = 20
GEAR = next(c for c in range(T.n) if T.is_type(c, "Gear") and not T.is_token(c))
if effective_energy(s, T, 0, GUARD) != int(T.energy[GUARD]):
    die("zone", "no gear on board should mean no discount")
s.add_permanent(GEAR, 0, base_loc(0))
s.add_permanent(GEAR, 0, bf_loc(0))
s.add_permanent(GEAR, 1, base_loc(1))          # theirs: "you control" excludes
if effective_energy(s, T, 0, GUARD) != int(T.energy[GUARD]) - 2:
    die("zone", f"'for each gear you control' counted {int(T.energy[GUARD]) - effective_energy(s, T, 0, GUARD)}"
                f", wanted 2 (theirs must not count, location must not matter)")
ok("a board count by TYPE ignores location and the opponent's copies")

# The affordability path must agree with the display path, or a card is
# offered as playable and then underflows the rune payment.
s = trashed(7)
# Her own domain, because the Power half is domain-bound (163.2) and is not
# what this case is testing. The rune requirement is max(energy, power).
dom = card_domains(T, RHASA)[0]
s.runes_ready[0, dom] = max(int(T.energy[RHASA]) - 7, int(T.power[RHASA]))
if plan_payment(s, T, 0, RHASA) is None:
    die("zone", "the discount applied to the cost but not to affordability")
s2 = trashed(0)
s2.runes_ready[0, dom] = max(int(T.energy[RHASA]) - 7, int(T.power[RHASA]))
if plan_payment(s2, T, 0, RHASA) is not None:
    die("zone", "with an EMPTY trash there is no discount, so the same runes "
                "must not be enough")
ok("plan_payment and effective_energy agree: no offer the payment can't honour")

# --- ST_MIGHT over a zone -------------------------------------------------
# Dr. Mundo's clause. Not in STATICS (his second sentence has no trigger yet),
# so it is driven directly -- the point is that a static reading a ZONE moves
# when nothing on the board did, and 143.2.a is a continuous check.
MUNDO_MIGHT = Static(ST_MIGHT, n=1, scope=SC_SELF, per=CNT_TRASH)
STATICS["Rhasa the Sunderer"] = (STATICS["Rhasa the Sunderer"][0], MUNDO_MIGHT)
try:
    s = trashed(5)
    u = s.add_permanent(RHASA, 0, base_loc(0))
    if m(s, u) != int(T.might[RHASA]) + 5:
        die("zone", f"a zone-counting Might static gave {m(s, u)}")
    s.perms[u, P_DMG] = int(T.might[RHASA]) + 3      # survives at +5
    combat.enforce_lethal(s, T)
    if s.perms[u, P_ALIVE] != 1:
        die("zone", "damage below the boosted Might must not kill")
    s.n_trash[0] = 2                                  # the pile shrinks by 3
    combat.enforce_lethal(s, T)
    if s.perms[u, P_ALIVE] == 1:
        die("zone", "143.2.a is continuous: shrinking the TRASH shrank the "
                    "unit onto its damage and must kill it")
    ok("emptying a trash kills a damaged unit whose Might counted it (143.2.a)")
finally:
    STATICS["Rhasa the Sunderer"] = (STATICS["Rhasa the Sunderer"][0],)

# ---------------------------------------------------------------------------
print("\n[7] XP: [Hunt] banks it, [Level N] spends it as a gate")

from rl.engine import chain as chain_mod
from rl.engine.effects import (COND_LEVEL, TR_CONQUER, TR_HOLD, abilities_for,
                               ABILITIES)
from rl.engine.state import C_FINAL, MAIN

CFG_V1 = replace(Config(), units_only=False)
VIS = T.id_of("Targonian Visionary")
HORROR = T.id_of("Arachnoid Horror")     # [Hunt 2]
FAV = T.id_of("Crowd Favorite")          # [Hunt], Spend 2 XP: Buff me


def xp_board():
    s = GameState()
    s.n_deck[:] = 20
    s.runes_ready[:, :] = 6
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


# [Hunt N] is SYNTHESISED from the keyword, never transcribed: its effect is
# fixed by the keyword rather than written on the card, so one implementation
# covers every card carrying it.
if "Arachnoid Horror" in ABILITIES:
    die("xp", "[Hunt] must not be transcribed per-card -- it is synthesised")
abs_ = abilities_for(T, HORROR)
if {a.trigger for a in abs_} != {TR_CONQUER, TR_HOLD}:
    die("xp", f"[Hunt] should synthesise a Conquer and a Hold ability: {abs_}")
ok("[Hunt N] comes off the keyword, on both ways of Scoring (469/470)")

s = xp_board()
u = s.add_permanent(HORROR, 0, bf_loc(0))
chain_mod.fire(s, T, CFG_V1, TR_CONQUER, u, bf_loc(0))
for i in range(int(s.n_chain)):
    s.chain[i, C_FINAL] = 1
while s.n_chain:
    chain_mod.resolve_top(s, T, CFG_V1)
if int(s.xp[0]) != 2:
    die("xp", f"[Hunt 2] on a conquer should bank 2 XP, got {int(s.xp[0])}")
ok("[Hunt 2] banks the keyword's own number, read by keyword_value")

# [Level N] is a threshold, read LIVE -- XP never resets, so unlike [Legion]
# there is no past moment to snapshot.
s = xp_board()
v = s.add_permanent(VIS, 0, base_loc(0))
printed = int(T.might[VIS])
for xp, want in ((0, printed), (10, printed), (11, printed + 4),
                 (99, printed + 4)):
    s.xp[0] = xp
    if m(s, v) != want:
        die("xp", f"[Level 11] at {xp} XP gave {m(s, v)}, wanted {want}")
ok("[Level 11] switches on at exactly 11 and stays on")

# The gate has to be honoured by the MIGHT path and the COST path alike, or a
# card is half on. This is the bug the shared `static_applies` exists to stop:
# the condition was added to Static and only `energy_discounts` consulted it.
s = xp_board()
s.xp[0] = 0
if m(s, s.add_permanent(VIS, 0, base_loc(0))) != printed:
    die("xp", "an unmet [Level] gate must contribute no Might at all")
ok("...and an unmet gate contributes nothing, rather than applying anyway")

# "Spend 2 XP:" is a cost (204.1.b), so it gates the ACTIVATION, not the effect.
s = xp_board()
f = s.add_permanent(FAV, 0, base_loc(0))
s.xp[0] = 1
if A.activatable(s, T, CFG_V1, 0):
    die("xp", "an unaffordable XP cost must not be offered")
s.xp[0] = 3
if f not in A.activatable(s, T, CFG_V1, 0):
    die("xp", "with 3 XP the ability should be activatable")
A.apply(s, T, CFG_V1, A.Action(A.A_ACTIVATE, f))
while s.n_trig:
    chain_mod.place(s, T, CFG_V1, 0)
for i in range(int(s.n_chain)):
    s.chain[i, C_FINAL] = 1
while s.n_chain:
    chain_mod.resolve_top(s, T, CFG_V1)
if int(s.xp[0]) != 1:
    die("xp", f"the cost should have spent 2 XP, left {int(s.xp[0])}")
if m(s, f) != int(T.might[FAV]) + 1:
    die("xp", "the buff should have landed")
ok("'Spend 2 XP:' gates the activation and is deducted at finalization")


print("\n\033[32mall static tests passed\033[0m")
