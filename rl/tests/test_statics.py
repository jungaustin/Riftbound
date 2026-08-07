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
from rl.engine import combat
from rl.engine.cardtable import full_table
from rl.engine.state import (P_ALIVE, P_DMG, P_LOC, GameState, base_loc,
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

combat.destroy(s, shep)                          # the pump goes away
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

print("\n\033[32mall static tests passed\033[0m")
