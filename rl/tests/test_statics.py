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
from rl.engine import resolve
from rl.engine.effects import SPECS
from rl.engine.cardtable import full_table
from rl.engine.cost import card_domains, plan_payment
from rl.engine.state import (F_EMPOWERED, MAIN, P_ALIVE, P_DMG, P_LOC,
                             GameState, base_loc, bf_loc)

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


# ---------------------------------------------------------------------------
print("\n[8] statics that grant a KEYWORD")

MOSS = T.id_of("Mosstomper")
FARRON = T.id_of("Captain Farron")
VANILLA = [c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
           and not T.residual_text(c) and not list(T.unread_keywords(c))][0]

# One sentence, two statics: "+1 Might AND [Deflect]" is a Might static beside
# a keyword static, and both are gated on the same level.
s = GameState()
s.n_deck[:] = 20
moss = s.add_permanent(MOSS, 0, bf_loc(0))
for xp, want_kw in ((0, 0), (2, 0), (3, 1)):
    s.xp[0] = xp
    got = combat.perm_kw(s, T, moss, "Deflect")
    if got != want_kw:
        die("kwstatic", f"[Level 3] [Deflect] at {xp} XP gave {got}")
    if m(s, moss) != int(T.might[MOSS]) + (1 if xp >= 3 else 0):
        die("kwstatic", f"the Might half disagreed with the keyword half at {xp}")
ok("a level-gated static grants a keyword and Might together, at the threshold")

# "OTHER friendly units HERE" is both narrowings at once. Without them this is
# a much better card: it would pump Farron himself and reach the whole board.
s = GameState()
s.n_deck[:] = 20
farron = s.add_permanent(FARRON, 0, bf_loc(0))
here = s.add_permanent(VANILLA, 0, bf_loc(0))
away = s.add_permanent(VANILLA, 0, bf_loc(1))
foe = s.add_permanent(VANILLA, 1, bf_loc(0))
cases = ((farron, 0, "itself -- 'other'"), (here, 1, "a friendly unit here"),
         (away, 0, "a friendly unit elsewhere"), (foe, 0, "an enemy unit here"))
for row, want, label in cases:
    got = combat.perm_kw(s, T, row, "Assault")
    if got != want:
        die("kwstatic", f"{label} got Assault {got}, wanted {want}")
ok("scope_not_self and scope_same_loc narrow it to exactly 'other ... here'")

# It is CONTINUOUS: the grant follows the unit, and dies with its source.
s.perms[here, P_LOC] = bf_loc(1)
if combat.perm_kw(s, T, here, "Assault"):
    die("kwstatic", "walking away from Farron must drop the grant")
s.perms[here, P_LOC] = bf_loc(0)
if not combat.perm_kw(s, T, here, "Assault"):
    die("kwstatic", "walking back must restore it")
s.perms[farron, P_ALIVE] = 0
if combat.perm_kw(s, T, here, "Assault"):
    die("kwstatic", "killing the source must remove the grant instantly")
ok("...and it is continuous: moving or killing the source changes it at once")


# A GRANTED keyword has to reach the same read path a printed one does, or the
# grant is silently inert. Taric - Protector gives "other friendly units here"
# [Shield], which is worth testing precisely because nothing about the grant is
# visible on the unit that receives it -- it shows up only as Might during a
# Combat, through `combat_role_bonus`.

TARIC = T.id_of("Taric - Protector")
_PLAIN = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.might[c] == 2
              and not T.residual_text(c) and not T.is_token(c)
              and not any(T.has(c, k) for k in ("Tank", "Backline",
                                                "Temporary")))


def taric_board():
    """Seat 0 defends bf0 with Taric and a friend; seat 1 attacks it."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.showdown_bf, s.attacker = 0, 1
    return s, (s.add_permanent(TARIC, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, base_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 1, bf_loc(0), is_unit=True))


s, (tar, mate, away, foe) = taric_board()
if combat.perm_kw(s, T, mate, "Shield") != 1:
    die("taric", "a friendly unit at Taric's battlefield must have [Shield]")
if combat.perm_kw(s, T, away, "Shield") != 0:
    die("taric", "'HERE' -- a unit in the base is not at his battlefield")
if combat.perm_kw(s, T, foe, "Shield") != 0:
    die("taric", "'FRIENDLY' -- the enemy standing on him gets nothing")
ok("Taric grants [Shield] to friendly units at his location, and only those")

# Falsified rather than merely asserted: a static that reads as present because
# the CARD prints [Shield] itself would pass the check above without granting
# anything at all.
s.perms[tar, P_ALIVE] = 0
if combat.perm_kw(s, T, mate, "Shield") != 0:
    die("taric", "the grant must be Taric's -- it has to stop when he dies")
ok("...and it is his: the grant lapses the moment he leaves the board")

print("\n\033[32mall static tests passed\033[0m")

# ---------------------------------------------------------------------------
print("\n[9] Lillia - Protector of Dreams: a watcher AND a static")

LIL = T.id_of("Lillia - Protector of Dreams")
SPRITE_TOK = T.id_of("Sprite (274) // Buff")
REAL = [c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
        and not T.residual_text(c) and not list(T.unread_keywords(c))][0]


def lil_board():
    s = GameState()
    s.n_deck[:] = 20
    s.runes_ready[:, :] = 8
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s, s.add_permanent(LIL, 0, bf_loc(0))


def lil_drain(s):
    while s.n_trig:
        chain_mod.place(s, T, CFG_V1, 0)
    for i in range(int(s.n_chain)):
        s.chain[i, C_FINAL] = 1
    while s.n_chain:
        chain_mod.resolve_top(s, T, CFG_V1)


# `scope_token` is the whole restriction: without it she hands [Tank] to every
# unit you control, which is a different card.
s, lil = lil_board()
tok = s.add_permanent(SPRITE_TOK, 0, bf_loc(0))
real = s.add_permanent(REAL, 0, bf_loc(0))
foe = s.add_permanent(SPRITE_TOK, 1, bf_loc(0))
if not combat.perm_kw(s, T, tok, "Tank"):
    die("lillia", "your token units should have [Tank]")
if combat.perm_kw(s, T, real, "Tank") or combat.perm_kw(s, T, foe, "Tank"):
    die("lillia", "'your TOKEN units' excludes real units and the opponent's")
ok("the static reaches your token units only")

# The trigger is a WATCHER on another permanent being played, not an ETB.
s, lil = lil_board()
_base = m(s, lil)
chain_mod.fire_play_unit(s, T, 0, SPRITE_TOK)
lil_drain(s)
if m(s, lil) != _base + 1:
    die("lillia", f"playing a token should give +1, got {m(s, lil)}")
chain_mod.fire_play_unit(s, T, 0, REAL)
lil_drain(s)
if m(s, lil) != _base + 1:
    die("lillia", "a NON-token unit must not trigger it")
ok("the watcher fires on token units and ignores real ones")

# **187 -- a token is PLAYED.** A watcher wired only to hand plays would be
# blind to the token deck it exists to reward, so the effect path fires it too.
s, lil = lil_board()
_base = m(s, lil)
resolve.resolve(s, T, CFG_V1, SPECS["Sprite Burst"], 0, [bf_loc(0)], -1, True)
lil_drain(s)
if m(s, lil) != _base + 2:
    die("lillia", f"two tokens from one spell should trigger twice, "
                  f"got {m(s, lil) - _base}")
ok("tokens made by an EFFECT count as played, and each one triggers")



# ---------------------------------------------------------------------------
# [Empower] (827) / [Empowered] (828)
#
# 441.1.a -- Empowered is a BINARY state, so it is a flag. 827.1.c.1 makes
# "[Empower Cost]" short for "[Cost]: Empower this. Play only if not
# Empowered", and 828.1.b.1 makes "[Empowered] - Text" short for "While I have
# the Empowered status, this card gains 'Text'". The engine owns the status,
# the once-only gate and the condition; each card still states its own cost,
# which is why `decks._encodes_empower` credits the keyword by evidence.

SUNHAWK = T.id_of("Solari Sunhawk")      # [Empower] {2}; +1 Might and [Deflect 2]

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
hawk = s.add_permanent(SUNHAWK, 0, base_loc(0))
s.runes_ready[0, 0] = 6

base_might = combat.might(s, T, hawk)
if combat.perm_kw(s, T, hawk, "Deflect"):
    die("empower", "the dependent ability must be OFF before Empowering")

acts = [a for a in A.legal_actions(s, T, CFG, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("empower", "the Empower ability should be activatable")
A.apply(s, T, CFG, acts[0])
for _ in range(6):
    if s.n_chain == 0 and s.n_trig == 0:
        break
    A.apply(s, T, CFG, A.Action(A.A_PASS))

if not s.has_flag(hawk, F_EMPOWERED):
    die("empower", "827.1.b -- paying the cost Empowers the source")
if combat.might(s, T, hawk) != base_might + 1:
    die("empower", f"828.1.b.1 -- the dependent +1 Might should be live, "
                   f"got {combat.might(s, T, hawk)} not {base_might + 1}")
if combat.perm_kw(s, T, hawk, "Deflect") != 2:
    die("empower", "...and so should the dependent [Deflect 2]")
ok("828.1.b.1 -- a dependent ability switches on with the Empowered status")

if [a for a in A.legal_actions(s, T, CFG, 0) if a.kind == A.A_ACTIVATE]:
    die("empower", "827.1.c.1 -- 'only if not Empowered' must withdraw the "
                   "ability once the status is held")
ok("827.1.c.1/441.1.b -- an Empowered permanent cannot be Empowered again")

# A GRANTED keyword has to reach the same read path a printed one does, or the
# grant is silently inert. Taric - Protector gives "other friendly units here"
# [Shield], which is worth testing precisely because nothing about the grant is
# visible on the unit that receives it -- it shows up only as Might during a
# Combat, through `combat_role_bonus`.

TARIC = T.id_of("Taric - Protector")
_PLAIN = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.might[c] == 2
              and not T.residual_text(c) and not T.is_token(c)
              and not any(T.has(c, k) for k in ("Tank", "Backline",
                                                "Temporary")))


def taric_board():
    """Seat 0 defends bf0 with Taric and a friend; seat 1 attacks it."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.showdown_bf, s.attacker = 0, 1
    return s, (s.add_permanent(TARIC, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, base_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 1, bf_loc(0), is_unit=True))


s, (tar, mate, away, foe) = taric_board()
if combat.perm_kw(s, T, mate, "Shield") != 1:
    die("taric", "a friendly unit at Taric's battlefield must have [Shield]")
if combat.perm_kw(s, T, away, "Shield") != 0:
    die("taric", "'HERE' -- a unit in the base is not at his battlefield")
if combat.perm_kw(s, T, foe, "Shield") != 0:
    die("taric", "'FRIENDLY' -- the enemy standing on him gets nothing")
ok("Taric grants [Shield] to friendly units at his location, and only those")

# Falsified rather than merely asserted: a static that reads as present because
# the CARD prints [Shield] itself would pass the check above without granting
# anything at all.
s.perms[tar, P_ALIVE] = 0
if combat.perm_kw(s, T, mate, "Shield") != 0:
    die("taric", "the grant must be Taric's -- it has to stop when he dies")
ok("...and it is his: the grant lapses the moment he leaves the board")

print("\n\033[32mall static tests passed\033[0m")


# ---------------------------------------------------------------------------
# Zilean - Time Mage: a replacement on playing a token unit
#
# "Once each turn, if you would play a token unit while I'm at a battlefield,
# you may play that token and an additional copy of it instead." Three
# restrictions and a choice, and each is worth its own check because dropping
# any one of them makes a strictly stronger card.

from rl.engine.state import MAIN as _MAIN, P_CTRL as _P_CTRL

ZILEAN = T.id_of("Zilean - Time Mage")


def zilean_board(at_battlefield=True, turn=1):
    s = GameState()
    s.phase, s.active, s.priority = _MAIN, 0, 0
    s.turn = turn
    z = s.add_permanent(ZILEAN, 0,
                        bf_loc(0) if at_battlefield else base_loc(0))
    return s, z


def play_tokens(s):
    resolve.resolve(s, T, CFG, SPECS["Recruit the Vanguard"], 0,
                    [base_loc(0)], -1, True)
    return sum(1 for i in range(s.n_perms)
               if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, _P_CTRL]) == 0)


s, z = zilean_board()
n = play_tokens(s)
if int(s.pend_double[0]) < 0:
    die("zilean", "playing token units should offer the replacement")
A.apply(s, T, CFG, A.Action(A.A_ACCEPT))
after = sum(1 for i in range(s.n_perms)
            if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, _P_CTRL]) == 0)
if after != n + 1:
    die("zilean", f"accepting adds exactly ONE additional copy, got {after - n}")
ok("'and an additional copy of it' -- one extra token, not a doubling of all")

play_tokens(s)
if int(s.pend_double[0]) >= 0:
    die("zilean", "'Once each turn' -- a second token play gets no offer")
ok("...and 'Once each turn' spends the opportunity for the rest of the turn")

# A new turn re-arms it: the stamp is compared against the turn, not cleared.
s.turn += 1
play_tokens(s)
if int(s.pend_double[0]) < 0:
    die("zilean", "the once-each-turn stamp must re-arm on a new turn")
A.apply(s, T, CFG, A.Action(A.A_DECLINE))
if int(s.pend_double[0]) >= 0:
    die("zilean", "declining clears the offer")
ok("...re-arming next turn, and declining is a real option (it can break 'alone')")

s, z = zilean_board(at_battlefield=False)
play_tokens(s)
if int(s.pend_double[0]) >= 0:
    die("zilean", "'while I'm at a battlefield' -- a Zilean at base does nothing")
ok("...and it only applies while Zilean is AT A BATTLEFIELD")

# A GRANTED keyword has to reach the same read path a printed one does, or the
# grant is silently inert. Taric - Protector gives "other friendly units here"
# [Shield], which is worth testing precisely because nothing about the grant is
# visible on the unit that receives it -- it shows up only as Might during a
# Combat, through `combat_role_bonus`.

TARIC = T.id_of("Taric - Protector")
_PLAIN = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.might[c] == 2
              and not T.residual_text(c) and not T.is_token(c)
              and not any(T.has(c, k) for k in ("Tank", "Backline",
                                                "Temporary")))


def taric_board():
    """Seat 0 defends bf0 with Taric and a friend; seat 1 attacks it."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.showdown_bf, s.attacker = 0, 1
    return s, (s.add_permanent(TARIC, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, base_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 1, bf_loc(0), is_unit=True))


s, (tar, mate, away, foe) = taric_board()
if combat.perm_kw(s, T, mate, "Shield") != 1:
    die("taric", "a friendly unit at Taric's battlefield must have [Shield]")
if combat.perm_kw(s, T, away, "Shield") != 0:
    die("taric", "'HERE' -- a unit in the base is not at his battlefield")
if combat.perm_kw(s, T, foe, "Shield") != 0:
    die("taric", "'FRIENDLY' -- the enemy standing on him gets nothing")
ok("Taric grants [Shield] to friendly units at his location, and only those")

# Falsified rather than merely asserted: a static that reads as present because
# the CARD prints [Shield] itself would pass the check above without granting
# anything at all.
s.perms[tar, P_ALIVE] = 0
if combat.perm_kw(s, T, mate, "Shield") != 0:
    die("taric", "the grant must be Taric's -- it has to stop when he dies")
ok("...and it is his: the grant lapses the moment he leaves the board")

print("\n\033[32mall static tests passed\033[0m")


# ---------------------------------------------------------------------------
# LeBlanc - Everywhere At Once: "Your [Temporary] effects at my battlefield
# don't trigger."
#
# 816's reminder -- "Kill it at the start of its controller's Beginning Phase"
# -- is the trigger being suppressed. Two restrictions in the wording, and
# dropping either one makes a much stronger card: "YOUR" effects (never an
# opponent's) and "at my BATTLEFIELD" (never from a base).

from rl.engine import phases as _phases
from rl.engine.state import BEGINNING as _BEGINNING

LEBLANC = T.id_of("LeBlanc - Everywhere At Once")
TEMP_TOKEN = T.id_of("Sprite (274) // Buff")     # 3 Might [Temporary] token


def expires(lb_loc, lb_seat=0, temp_loc=None):
    s = GameState()
    s.phase, s.active, s.priority = _BEGINNING, 0, 0
    if lb_loc is not None:
        s.add_permanent(LEBLANC, lb_seat, lb_loc)
    t = s.add_permanent(TEMP_TOKEN, 0, temp_loc, is_unit=True)
    _phases.expire_temporary(s, T)
    return s.perms[t, P_ALIVE] != 1


if not expires(None, temp_loc=bf_loc(0)):
    die("leblanc", "without LeBlanc a [Temporary] unit expires as normal")
if expires(bf_loc(0), temp_loc=bf_loc(0)):
    die("leblanc", "a friendly LeBlanc at the same battlefield suppresses it")
ok("816 -- LeBlanc suppresses the [Temporary] expiry at her battlefield")

if not expires(bf_loc(1), temp_loc=bf_loc(0)):
    die("leblanc", "'at MY battlefield' -- the other battlefield is not hers")
if not expires(base_loc(0), temp_loc=base_loc(0)):
    die("leblanc", "'at my BATTLEFIELD' -- a base is not one")
ok("...only at HER battlefield, and never from a base")

if not expires(bf_loc(0), lb_seat=1, temp_loc=bf_loc(0)):
    die("leblanc", "'YOUR effects' -- an enemy LeBlanc spares nothing of mine")
ok("...and only for its own controller's units")

# A GRANTED keyword has to reach the same read path a printed one does, or the
# grant is silently inert. Taric - Protector gives "other friendly units here"
# [Shield], which is worth testing precisely because nothing about the grant is
# visible on the unit that receives it -- it shows up only as Might during a
# Combat, through `combat_role_bonus`.

TARIC = T.id_of("Taric - Protector")
_PLAIN = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.might[c] == 2
              and not T.residual_text(c) and not T.is_token(c)
              and not any(T.has(c, k) for k in ("Tank", "Backline",
                                                "Temporary")))


def taric_board():
    """Seat 0 defends bf0 with Taric and a friend; seat 1 attacks it."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.showdown_bf, s.attacker = 0, 1
    return s, (s.add_permanent(TARIC, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, base_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 1, bf_loc(0), is_unit=True))


s, (tar, mate, away, foe) = taric_board()
if combat.perm_kw(s, T, mate, "Shield") != 1:
    die("taric", "a friendly unit at Taric's battlefield must have [Shield]")
if combat.perm_kw(s, T, away, "Shield") != 0:
    die("taric", "'HERE' -- a unit in the base is not at his battlefield")
if combat.perm_kw(s, T, foe, "Shield") != 0:
    die("taric", "'FRIENDLY' -- the enemy standing on him gets nothing")
ok("Taric grants [Shield] to friendly units at his location, and only those")

# Falsified rather than merely asserted: a static that reads as present because
# the CARD prints [Shield] itself would pass the check above without granting
# anything at all.
s.perms[tar, P_ALIVE] = 0
if combat.perm_kw(s, T, mate, "Shield") != 0:
    die("taric", "the grant must be Taric's -- it has to stop when he dies")
ok("...and it is his: the grant lapses the moment he leaves the board")

print("\n\033[32mall static tests passed\033[0m")


# ---------------------------------------------------------------------------
# Swain, Visionary: "When I conquer, if you've played a non-token unit, a
# non-token gear, and a spell this turn, you score 1 point."
#
# `cards_played` is a bare count and cannot answer this, so `played_types`
# tracks the KINDS. Set at the moment each card is played (349) rather than at
# resolution, so a countered spell still counts -- it was played.

from rl.engine.state import (PT_GEAR as _PT_GEAR, PT_SPELL as _PT_SPELL,
                             PT_UNIT as _PT_UNIT)

SWAIN = T.id_of("Swain, Visionary")
SWAIN_AB = ABILITIES["Swain, Visionary"][0]


def swain_score(bits):
    s = GameState()
    s.phase, s.active, s.priority = _MAIN, 0, 0
    w = s.add_permanent(SWAIN, 0, bf_loc(0))
    s.played_types[0] = bits
    resolve.resolve(s, T, CFG, SWAIN_AB, 0, [], -1, True, source=w)
    return int(s.points[0])


for bits, label in ((0, "nothing"), (_PT_UNIT, "a unit"),
                    (_PT_UNIT | _PT_GEAR, "unit and gear"),
                    (_PT_GEAR | _PT_SPELL, "gear and spell")):
    if swain_score(bits) != 0:
        die("swain", f"{label} is not the full trio -- no point should score")
if swain_score(_PT_UNIT | _PT_GEAR | _PT_SPELL) != 1:
    die("swain", "all three kinds this turn scores exactly 1 point")
ok("Swain scores only on the full trio, and any two of three is not enough")

# "non-token unit" -- tokens are played (187) but are not the non-token kind.
s = GameState()
s.phase, s.active, s.priority = _MAIN, 0, 0
s.n_deck[0] = 10
resolve.resolve(s, T, CFG, SPECS["Recruit the Vanguard"], 0, [base_loc(0)],
                -1, True)
if int(s.played_types[0]) & _PT_UNIT:
    die("swain", "token units must not satisfy 'a NON-TOKEN unit'")
ok("...and token units do not count toward it (187 plays them, but not as that)")

# **A card with more than one type counts for EVERY one of them.** A gear unit
# is both a gear and a unit for Swain. No card in the export carries two types
# yet, so this drives `_played_bits` directly rather than through a real card --
# the alternative is leaving the rule untested until the set that prints one
# lands, by which time the if/elif it replaced would have been wrong for months.
from rl.engine.actions import _played_bits as _bits


class _GearUnit:
    def is_type(self, cid, ty):
        return ty in ("Gear", "Unit")


class _AllThree:
    def is_type(self, cid, ty):
        return True


b = _bits(_GearUnit(), 0)
if not (b & _PT_UNIT and b & _PT_GEAR):
    die("swain", "a gear unit must count as BOTH a gear and a unit")
if b & _PT_SPELL:
    die("swain", "...but not as a type it does not have")
if _bits(_AllThree(), 0) != (_PT_UNIT | _PT_GEAR | _PT_SPELL):
    die("swain", "a card of all three kinds completes the trio by itself")
ok("...while a multi-type card counts for every kind it has, not just one")

# A GRANTED keyword has to reach the same read path a printed one does, or the
# grant is silently inert. Taric - Protector gives "other friendly units here"
# [Shield], which is worth testing precisely because nothing about the grant is
# visible on the unit that receives it -- it shows up only as Might during a
# Combat, through `combat_role_bonus`.

TARIC = T.id_of("Taric - Protector")
_PLAIN = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.might[c] == 2
              and not T.residual_text(c) and not T.is_token(c)
              and not any(T.has(c, k) for k in ("Tank", "Backline",
                                                "Temporary")))


def taric_board():
    """Seat 0 defends bf0 with Taric and a friend; seat 1 attacks it."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.showdown_bf, s.attacker = 0, 1
    return s, (s.add_permanent(TARIC, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, bf_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 0, base_loc(0), is_unit=True),
               s.add_permanent(_PLAIN, 1, bf_loc(0), is_unit=True))


s, (tar, mate, away, foe) = taric_board()
if combat.perm_kw(s, T, mate, "Shield") != 1:
    die("taric", "a friendly unit at Taric's battlefield must have [Shield]")
if combat.perm_kw(s, T, away, "Shield") != 0:
    die("taric", "'HERE' -- a unit in the base is not at his battlefield")
if combat.perm_kw(s, T, foe, "Shield") != 0:
    die("taric", "'FRIENDLY' -- the enemy standing on him gets nothing")
ok("Taric grants [Shield] to friendly units at his location, and only those")

# Falsified rather than merely asserted: a static that reads as present because
# the CARD prints [Shield] itself would pass the check above without granting
# anything at all.
s.perms[tar, P_ALIVE] = 0
if combat.perm_kw(s, T, mate, "Shield") != 0:
    die("taric", "the grant must be Taric's -- it has to stop when he dies")
ok("...and it is his: the grant lapses the moment he leaves the board")

print("\n\033[32mall static tests passed\033[0m")


# ---------------------------------------------------------------------------
print("\n[Empower, continued] two costs, an 'instead', and a status "
      "requirement")

# 827: "Pay EITHER cost: Empower me." Legion Marauder prints {1 energy} OR
# {Body rune}, which is two activated abilities rather than one with an
# internal choice -- so a seat that can afford only one is offered only that
# one, and the player picks by picking which to activate.
from rl.config import DOMAINS as _DOMS

MARAUDER = T.id_of("Legion Marauder")
_BODY = _DOMS.index("Body")


def marauder_offers(body_runes, other_runes):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.add_permanent(MARAUDER, 0, base_loc(0))
    s.runes_ready[0, _BODY] = body_runes
    s.runes_ready[0, (_BODY + 1) % len(_DOMS)] = other_runes
    return len([a for a in A.legal_actions(s, T, CFG, 0)
                if a.kind == A.A_ACTIVATE])


if marauder_offers(body_runes=2, other_runes=0) != 2:
    die("either cost", "with both affordable, BOTH costs are offered")
ok("'pay either cost' is two activated abilities, not one")

# The asymmetry the two costs actually have: Energy is generic (163.1.a) and
# comes from exhausting ANY ready rune, so a Body board pays both; {Body rune}
# is Power (163.2) and is bound to its domain, so a board with no Body rune
# pays only the Energy half. There is no mirror case -- no board can pay the
# Power cost and not the Energy one -- which is itself the rule showing.
if marauder_offers(body_runes=0, other_runes=2) != 1:
    die("either cost", "with no Body rune to recycle, only the Energy cost is "
                       "payable and only that one should be offered")
ok("...so a seat that can afford one of them is offered exactly that one")

if marauder_offers(body_runes=0, other_runes=0) != 0:
    die("either cost", "with an empty board neither cost is payable")
ok("...and an empty board is offered neither")


# "Your units have +1 Might. If I'm [Empowered], they have +2 INSTEAD."
# Written as two statics that ADD, which is the same number by a different
# route -- the board must read +2 and never +3.
AMP = T.id_of("Rage Amplifier")
s = fresh()
amp = s.add_permanent(AMP, 0, base_loc(0), is_unit=False)
friend = s.add_permanent(_PLAIN, 0, bf_loc(0))
printed = int(T.might[_PLAIN])
if m(s, friend) != printed + 1:
    die("instead", f"the ungated half is +1, got {m(s, friend) - printed}")
ok("Rage Amplifier is worth +1 the turn it lands, before any Empowering")

s.set_flag(amp, F_EMPOWERED)
if m(s, friend) != printed + 2:
    die("instead", f"'+2 INSTEAD' must read +2, got {m(s, friend) - printed} "
                   f"-- two statics that add, not two that stack")
ok("...and +2 once Empowered: 'instead' is arithmetic, never +3")


# "Your units THAT ARE [Empowered] have +2 Might (including me)." Both
# readings of the status in one sentence: the static exists only while the
# GENERAL is Empowered, and it then reaches only units that are.
GENERAL = T.id_of("Aurok General")
s = fresh()
gen = s.add_permanent(GENERAL, 0, bf_loc(0))
plain_friend = s.add_permanent(_PLAIN, 0, bf_loc(0))
other = s.add_permanent(_PLAIN, 0, bf_loc(0))
gen_printed, friend_printed = int(T.might[GENERAL]), int(T.might[_PLAIN])

s.set_flag(other, F_EMPOWERED)
if m(s, other) != friend_printed:
    die("aurok", "with the General not Empowered the static does not exist")
ok("Aurok General's static is off while HE is not Empowered")

s.set_flag(gen, F_EMPOWERED)
if m(s, other) != friend_printed + 2:
    die("aurok", "an Empowered friendly unit gets +2")
if m(s, plain_friend) != friend_printed:
    die("aurok", "'units THAT ARE Empowered' -- a plain unit gets nothing")
if m(s, gen) != gen_printed + 2:
    die("aurok", "'(including me)' -- he is a friendly Empowered unit too")
ok("...and then reaches only Empowered units, himself among them")

print("\n\033[32mall static tests passed\033[0m")


# ---------------------------------------------------------------------------
print("\n[two activated abilities on one permanent]")

# `activatable` used to `break` after the first activated ability and
# `pack_activate` carried no index, so the second was unreachable: a card on
# the board that could not do half of what it prints. Tools of Empire is the
# discriminating case, because its two abilities have DIFFERENT effects --
# [Empower] {2 energy}, and "Exhaust: give a unit +2 Might this turn".
TOOLS = T.id_of("Tools of Empire")

s = fresh()
tools = s.add_permanent(TOOLS, 0, base_loc(0), is_unit=False)
victim = s.add_permanent(_PLAIN, 0, bf_loc(0))
s.runes_ready[0, :] = 4

acts = [a for a in A.legal_actions(s, T, CFG, 0) if a.kind == A.A_ACTIVATE]
if len(acts) != 2:
    die("two abilities", f"both abilities should be offered, got {len(acts)}")
if len({a.arg for a in acts}) != 2:
    die("two abilities", "the two offers must be DISTINGUISHABLE args, or the "
                         "policy is choosing between two identical actions")
ok("a permanent printing two activated abilities offers both, distinctly")

for a in acts:
    _perm, _donor, _k = A.unpack_activate(int(a.arg))
    if _perm != tools or _donor != tools:
        die("two abilities", f"arg {a.arg} decoded to the wrong row")
if {A.unpack_activate(int(a.arg))[2] for a in acts} != {0, 1}:
    die("two abilities", "the args must decode to ability indices 0 and 1")
ok("...and each decodes back to its own ability index")


# The pump ability is index 1. Running it must give +2 and NOT Empower.
def use(k, target=None):
    st = fresh()
    src = st.add_permanent(TOOLS, 0, base_loc(0), is_unit=False)
    tgt = st.add_permanent(_PLAIN, 0, bf_loc(0))
    st.runes_ready[0, :] = 4
    A.apply(st, T, CFG, A.Action(A.A_ACTIVATE, A.pack_activate(src, src, k)))
    if st.pend_slot >= 0:
        A.apply(st, T, CFG, A.Action(A.A_TARGET, tgt))
    for _ in range(8):
        if st.n_chain == 0 and st.n_trig == 0 and st.pend_slot < 0:
            break
        A.apply(st, T, CFG, A.Action(A.A_PASS))
    return st, src, tgt


st, src, tgt = use(1)
if m(st, tgt) != int(T.might[_PLAIN]) + 2:
    die("two abilities", f"ability 1 gives +2 Might, got "
                         f"{m(st, tgt) - int(T.might[_PLAIN])}")
if st.has_flag(src, F_EMPOWERED):
    die("two abilities", "ability 1 is the pump, not the [Empower]")
ok("...and activating index 1 runs the pump, not the [Empower]")

st, src, tgt = use(0)
if not st.has_flag(src, F_EMPOWERED):
    die("two abilities", "ability 0 is the [Empower]")
ok("...while index 0 runs the [Empower], which is the whole point of an index")

# "If this is [Empowered], give that unit +4 INSTEAD" -- the same two-ops-that-
# add arithmetic, now on a live board.
st = fresh()
src = st.add_permanent(TOOLS, 0, base_loc(0), is_unit=False)
tgt = st.add_permanent(_PLAIN, 0, bf_loc(0))
st.runes_ready[0, :] = 4
st.set_flag(src, F_EMPOWERED)
A.apply(st, T, CFG, A.Action(A.A_ACTIVATE, A.pack_activate(src, src, 1)))
A.apply(st, T, CFG, A.Action(A.A_TARGET, tgt))
for _ in range(8):
    if st.n_chain == 0 and st.n_trig == 0 and st.pend_slot < 0:
        break
    A.apply(st, T, CFG, A.Action(A.A_PASS))
if m(st, tgt) != int(T.might[_PLAIN]) + 4:
    die("two abilities", f"'+4 INSTEAD' must read +4, got "
                         f"{m(st, tgt) - int(T.might[_PLAIN])}")
ok("...and Empowered it gives +4, never +6")


# ---------------------------------------------------------------------------
print("\n[less Might than ME] -- a comparison against the source, not a slot")

# Ambessa, Respected and Feared: "[Empowered] when I attack, kill an enemy unit
# here with less Might than me." `less_might_than` compares against an earlier
# SLOT; the source is not a slot, so the two cannot share a field.
from rl.engine.effects import TR_ATTACK_OR_DEFEND, abilities_for as _abils
from rl.engine import resolve as _res

AMBESSA = T.id_of("Ambessa, Respected and Feared")
_KILL = next(a for a in _abils(T, AMBESSA) if a.trigger == TR_ATTACK_OR_DEFEND)

s = fresh()
amb = s.add_permanent(AMBESSA, 0, bf_loc(0))
small = s.add_permanent(_PLAIN, 1, bf_loc(0))          # 2 Might
big = s.add_permanent(T.id_of("Kadregrin the Infernal"), 1, bf_loc(0))
elsewhere = s.add_permanent(_PLAIN, 1, bf_loc(1))

got = _res.legal_targets(s, T, _KILL, 0, 0, [], -1, source=amb)
if small not in got:
    die("less than me", "a smaller enemy standing with her is a legal choice")
if big in got:
    die("less than me", "a BIGGER enemy is not 'less Might than me'")
if elsewhere in got:
    die("less than me", "'here' -- an enemy at the other battlefield is out")
ok("'less Might than me' reads the source's own Might, and only 'here'")

# Effective Might on both sides: pump the small one out of range.
combat.set_might_mod(s, T, small, 20)
if small in _res.legal_targets(s, T, _KILL, 0, 0, [], -1, source=amb):
    die("less than me", "the comparison must read EFFECTIVE Might, so a unit "
                        "pumped in the response window leaves range")
ok("...and both sides are effective Might, so a trick answers it")

print("\n\033[32mall static tests passed\033[0m")
